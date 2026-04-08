"""Summary report generation for a processed document batch.

Builds a ``Report`` from classified documents, the rename map, and
any alerts (validation + consistency). Computes missing required
document types from the set of found types.
"""

from app.models.document import REQUIRED_DOCUMENT_TYPES
from app.models.schemas import (
    Alert,
    ClassifiedDocument,
    ProcessedDocument,
    Report,
)


def generate_report(
    job_id: str,
    total_files_ingested: int,
    documents: list[ClassifiedDocument],
    renamed_map: dict[str, str],
    alerts: list[Alert],
) -> Report:
    """Build the summary report for the processed batch."""
    found = [
        ProcessedDocument(
            original_filename=doc.source_filename,
            renamed_filename=renamed_map.get(doc.source_filename, doc.source_filename),
            doc_type=doc.doc_type,
            confidence=doc.confidence,
            extracted_data=doc.extracted_data,
        )
        for doc in documents
    ]

    found_types = {doc.doc_type for doc in documents}
    missing = [
        dt.value for dt in REQUIRED_DOCUMENT_TYPES if dt not in found_types
    ]

    return Report(
        job_id=job_id,
        total_files_ingested=total_files_ingested,
        documents_found=found,
        missing_types=missing,
        alerts=alerts,
    )
