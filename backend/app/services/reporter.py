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

    missing_labels = [
        alert.message.removeprefix("Documento faltante: ")
        for alert in alerts
        if alert.message.startswith("Documento faltante:")
    ]

    return Report(
        job_id=job_id,
        total_files_ingested=total_files_ingested,
        documents_found=found,
        missing_types=missing_labels,
        alerts=alerts,
    )
