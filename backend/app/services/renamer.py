"""Normalized file naming for classified documents.

Generates filenames in the format ``[TransportID]_[DocType].pdf``,
with a numeric suffix for duplicate types (e.g., multiple invoices).
"""

import re

from app.models.document import DOCUMENT_FILE_NAMES
from app.models.schemas import ClassifiedDocument


def generate_filename(
    doc: ClassifiedDocument, transport_id: str | None, index: int
) -> str:
    """Generate a normalized filename: [TransportID]_[DocType].pdf"""
    id_part = _sanitize(transport_id) if transport_id else "SinID"
    type_part = DOCUMENT_FILE_NAMES.get(doc.doc_type, "Otro")

    base = f"{id_part}_{type_part}"

    # Append index if there are duplicate types (e.g., multiple invoices)
    if index > 0:
        base = f"{base}_{index + 1}"

    return f"{base}.pdf"


def _sanitize(text: str) -> str:
    """Remove characters that are unsafe for filenames."""
    return re.sub(r"[^\w\-.]", "_", text).strip("_")
