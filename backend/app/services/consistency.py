"""Cross-document consistency validation.

Compares extracted data across all documents in a batch to verify they
belong to the same shipment: matching transport IDs, container numbers,
and presence of required document types.
"""

import logging

from app.models.document import (
    DOCUMENT_LABELS,
    REQUIRED_DOCUMENT_TYPES,
    DocumentType,
)
from app.models.schemas import Alert, AlertSeverity, ClassifiedDocument

logger = logging.getLogger(__name__)


def check_consistency(documents: list[ClassifiedDocument]) -> list[Alert]:
    """Cross-reference all documents to verify they belong to the same shipment."""
    alerts: list[Alert] = []

    primary = _find_primary(documents)
    if not primary:
        alerts.append(
            Alert(
                severity=AlertSeverity.WARNING,
                message="No se encontró Documento de Transporte (BL/AWB/CRT) en el lote",
            )
        )
        return alerts

    primary_transport_id = _get_primary_transport_id(primary)
    primary_containers = set(primary.extracted_data.container_numbers)

    # Check each secondary document against the primary
    for doc in documents:
        if doc is primary:
            continue

        # Check transport ID references
        if primary_transport_id and doc.extracted_data.transport_ids:
            if primary_transport_id not in doc.extracted_data.transport_ids:
                label = DOCUMENT_LABELS.get(doc.doc_type, doc.doc_type.value)
                alerts.append(
                    Alert(
                        severity=AlertSeverity.WARNING,
                        document=doc.source_filename,
                        message=(
                            f"{label} no hace referencia a {primary_transport_id} "
                            f"— Posible mezcla de embarques"
                        ),
                    )
                )

        # Check container number consistency
        if primary_containers and doc.extracted_data.container_numbers:
            doc_containers = set(doc.extracted_data.container_numbers)
            if not doc_containers & primary_containers:
                label = DOCUMENT_LABELS.get(doc.doc_type, doc.doc_type.value)
                alerts.append(
                    Alert(
                        severity=AlertSeverity.WARNING,
                        document=doc.source_filename,
                        message=(
                            f"Números de contenedor en {label} no coinciden "
                            f"con el Documento de Transporte"
                        ),
                    )
                )

    # Check for missing required documents
    found_types = {doc.doc_type for doc in documents}
    for required_type in REQUIRED_DOCUMENT_TYPES:
        if required_type not in found_types:
            label = DOCUMENT_LABELS[required_type]
            alerts.append(
                Alert(
                    severity=AlertSeverity.INFO,
                    message=f"Documento faltante: {label}",
                )
            )

    return alerts


def _find_primary(documents: list[ClassifiedDocument]) -> ClassifiedDocument | None:
    for doc in documents:
        if doc.doc_type == DocumentType.TRANSPORT_DOCUMENT:
            return doc
    return None


def _get_primary_transport_id(primary: ClassifiedDocument) -> str | None:
    if primary.extracted_data.transport_ids:
        return primary.extracted_data.transport_ids[0]
    return None
