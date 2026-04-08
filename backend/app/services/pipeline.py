"""Document processing pipeline.

Orchestrates OCR -> classify -> extract -> validate -> rename -> ZIP.
This function is transport-agnostic (ports & adapters): it accepts PDFs
as bytes and returns a report + ZIP. The caller handles I/O.
"""

import logging
from collections import Counter
from collections.abc import Callable

from app.models.document import DocumentType
from app.models.schemas import (
    AnalyzedSegment,
    ClassifiedDocument,
    DocumentSegment,
    JobInput,
    JobResult,
    JobStage,
)
from app.services.analyzer import (
    classify_and_extract,
    use_vision_path,
    vision_classify_and_extract,
)
from app.services.archiver import create_zip
from app.services.consistency import check_consistency
from app.services.ocr import extract_text_from_pdf
from app.services.post_validate import validate_extracted_data
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

    vision = use_vision_path()
    if vision:
        logger.info("Using vision path (OCR + classify + extract in one call)")

    all_classified: list[ClassifiedDocument] = []
    all_split_pdf_bytes: list[bytes] = []
    renamed_files: dict[str, bytes] = {}
    rename_map: dict[str, str] = {}

    for i, pdf in enumerate(job_input.pdfs):
        file_progress = i / len(job_input.pdfs)

        # --- PyMuPDF text extraction (always runs — free and fast) ---
        _progress(
            JobStage.EXTRACTING_TEXT, file_progress, f"Procesando {pdf.filename}"
        )
        pages = extract_text_from_pdf(
            pdf.content,
            job_id=job_input.job_id,
            filename=pdf.filename,
            skip_ocr=vision,  # skip external OCR when using vision path
        )
        logger.info(
            "Extracted text from %d pages of %s", len(pages), pdf.filename
        )

        # --- Classify + Extract (single LLM call) ---
        _progress(
            JobStage.CLASSIFYING, file_progress, f"Analizando {pdf.filename}"
        )

        if vision:
            analyzed = vision_classify_and_extract(pdf.content, pages)
        else:
            analyzed = classify_and_extract(pages)

        if not analyzed:
            analyzed = [
                AnalyzedSegment(
                    start_page=0,
                    end_page=len(pages) - 1,
                    doc_type=DocumentType.OTHER,
                    confidence=0.0,
                    extracted_data=_empty_extracted_data(),
                )
            ]

        # Report EXTRACTING_DATA as done (folded into the classify call)
        _progress(
            JobStage.EXTRACTING_DATA,
            file_progress,
            f"Datos extraídos de {pdf.filename}",
        )

        # --- Split PDF ---
        _progress(
            JobStage.SPLITTING, file_progress, f"Separando {pdf.filename}"
        )
        segments = [
            DocumentSegment(
                start_page=a.start_page,
                end_page=a.end_page,
                doc_type=a.doc_type,
                confidence=a.confidence,
            )
            for a in analyzed
        ]
        split_pdfs = split_pdf(pdf.content, segments)

        # --- Build ClassifiedDocuments ---
        for seg, seg_pdf_bytes in zip(analyzed, split_pdfs):
            seg_pages = pages[seg.start_page : seg.end_page + 1]
            source_name = (
                f"{pdf.filename}[p{seg.start_page + 1}-{seg.end_page + 1}]"
                if len(analyzed) > 1
                else pdf.filename
            )

            classified = ClassifiedDocument(
                doc_type=seg.doc_type,
                confidence=seg.confidence,
                extracted_data=seg.extracted_data,
                source_filename=source_name,
                start_page=seg.start_page,
                end_page=seg.end_page,
                text="\n".join(p.text for p in seg_pages),
            )
            all_classified.append(classified)
            all_split_pdf_bytes.append(seg_pdf_bytes)

    # --- Post-LLM validation against PyMuPDF raw text ---
    _progress(JobStage.VALIDATING, 0.75, "Verificando datos contra texto PDF")
    validation_alerts = validate_extracted_data(all_classified)

    # --- Consistency check ---
    _progress(JobStage.VALIDATING, 0.85, "Validando consistencia")
    consistency_alerts = check_consistency(all_classified)
    alerts = validation_alerts + consistency_alerts

    # --- Rename and package ---
    _progress(JobStage.PACKAGING, 0.9, "Empaquetando archivos")

    primary_transport_id = _find_primary_transport_id(all_classified)
    type_counter: Counter[DocumentType] = Counter()

    for doc, pdf_bytes in zip(all_classified, all_split_pdf_bytes):
        idx = type_counter[doc.doc_type]
        type_counter[doc.doc_type] += 1
        new_name = generate_filename(doc, primary_transport_id, idx)
        renamed_files[new_name] = pdf_bytes
        rename_map[doc.source_filename] = new_name

    zip_bytes = create_zip(renamed_files)

    report = generate_report(
        job_id=job_input.job_id,
        total_files_ingested=len(job_input.pdfs),
        documents=all_classified,
        renamed_map=rename_map,
        alerts=alerts,
    )

    _progress(JobStage.COMPLETE, 1.0, "Completado")
    return JobResult(report=report, zip_bytes=zip_bytes)


def _find_primary_transport_id(
    documents: list[ClassifiedDocument],
) -> str | None:
    for doc in documents:
        if doc.doc_type == DocumentType.TRANSPORT_DOCUMENT:
            if doc.extracted_data.transport_ids:
                return doc.extracted_data.transport_ids[0]
    return None


def _empty_extracted_data():
    from app.models.schemas import ExtractedData

    return ExtractedData()
