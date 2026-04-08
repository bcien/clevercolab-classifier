import logging
from collections import Counter
from collections.abc import Callable

from app.models.document import DocumentType
from app.models.schemas import (
    ClassifiedDocument,
    DocumentSegment,
    JobInput,
    JobResult,
    JobStage,
)
from app.services.archiver import create_zip
from app.services.classifier import classify_and_split
from app.services.consistency import check_consistency
from app.services.extractor import extract_data
from app.services.ocr import extract_text_from_pdf
from app.services.renamer import generate_filename
from app.services.reporter import generate_report
from app.services.splitter import split_pdf

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[JobStage, float, str], None]


def process_job(
    job_input: JobInput,
    on_progress: ProgressCallback | None = None,
) -> JobResult:
    """Run the full document processing pipeline.

    This function is transport-agnostic: it accepts PDFs as bytes and returns
    a report + ZIP as bytes. The caller (Lambda handler, CLI, etc.) is responsible
    for I/O with S3, DynamoDB, or the filesystem.
    """

    def _progress(stage: JobStage, pct: float, detail: str = "") -> None:
        if on_progress:
            on_progress(stage, pct, detail)

    all_classified: list[ClassifiedDocument] = []
    all_split_pdf_bytes: list[bytes] = []  # parallel to all_classified
    renamed_files: dict[str, bytes] = {}  # renamed_filename -> pdf bytes
    rename_map: dict[str, str] = {}  # source_filename -> renamed_filename

    # --- Stage 1: OCR + Split + Classify each input PDF ---
    for i, pdf in enumerate(job_input.pdfs):
        file_progress = i / len(job_input.pdfs)

        # Extract text
        _progress(JobStage.EXTRACTING_TEXT, file_progress, f"Procesando {pdf.filename}")
        pages = extract_text_from_pdf(pdf.content, job_id=job_input.job_id, filename=pdf.filename)
        logger.info("Extracted text from %d pages of %s", len(pages), pdf.filename)

        # Classify and detect document boundaries
        _progress(JobStage.CLASSIFYING, file_progress, f"Clasificando {pdf.filename}")
        segments = classify_and_split(pages)

        if not segments:
            segments = [
                DocumentSegment(
                    start_page=0,
                    end_page=len(pages) - 1,
                    doc_type=DocumentType.OTHER,
                    confidence=0.0,
                )
            ]

        # Split PDF into individual documents (done once, reused for packaging)
        _progress(JobStage.SPLITTING, file_progress, f"Separando {pdf.filename}")
        split_pdfs = split_pdf(pdf.content, segments)

        # Extract data from each segment
        _progress(JobStage.EXTRACTING_DATA, file_progress, f"Extrayendo datos de {pdf.filename}")
        for seg, seg_pdf_bytes in zip(segments, split_pdfs):
            seg_pages = pages[seg.start_page : seg.end_page + 1]
            extracted = extract_data(seg_pages, seg.doc_type)

            source_name = (
                f"{pdf.filename}[p{seg.start_page + 1}-{seg.end_page + 1}]"
                if len(segments) > 1
                else pdf.filename
            )

            classified = ClassifiedDocument(
                doc_type=seg.doc_type,
                confidence=seg.confidence,
                extracted_data=extracted,
                source_filename=source_name,
                start_page=seg.start_page,
                end_page=seg.end_page,
                text="\n".join(p.text for p in seg_pages),
            )
            all_classified.append(classified)
            all_split_pdf_bytes.append(seg_pdf_bytes)

    # --- Stage 2: Consistency check ---
    _progress(JobStage.VALIDATING, 0.8, "Validando consistencia")
    alerts = check_consistency(all_classified)

    # --- Stage 3: Rename and package ---
    _progress(JobStage.PACKAGING, 0.9, "Empaquetando archivos")

    primary_transport_id = _find_primary_transport_id(all_classified)
    type_counter: Counter[DocumentType] = Counter()

    for doc, pdf_bytes in zip(all_classified, all_split_pdf_bytes):
        idx = type_counter[doc.doc_type]
        type_counter[doc.doc_type] += 1
        new_name = generate_filename(doc, primary_transport_id, idx)
        renamed_files[new_name] = pdf_bytes
        rename_map[doc.source_filename] = new_name

    # Create ZIP
    zip_bytes = create_zip(renamed_files)

    # Generate report
    report = generate_report(
        job_id=job_input.job_id,
        total_files_ingested=len(job_input.pdfs),
        documents=all_classified,
        renamed_map=rename_map,
        alerts=alerts,
    )

    _progress(JobStage.COMPLETE, 1.0, "Completado")
    return JobResult(report=report, zip_bytes=zip_bytes)


def _find_primary_transport_id(documents: list[ClassifiedDocument]) -> str | None:
    for doc in documents:
        if doc.doc_type == DocumentType.TRANSPORT_DOCUMENT:
            if doc.extracted_data.transport_ids:
                return doc.extracted_data.transport_ids[0]
    return None
