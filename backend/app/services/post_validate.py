"""Post-LLM validation of extracted data against PyMuPDF raw text.

PyMuPDF extracts text byte-for-byte from the PDF text layer — it never
hallucinates.  After the LLM returns its extracted fields, this module
cross-checks specific values against the raw text and:

- Fixes values the LLM slightly mangled (transposed digits, extra spaces).
- Flags values the LLM returned that don't appear in the raw text at all.
- Recovers values the LLM missed that regex finds in the raw text.

Only runs on text-layer pages (where PyMuPDF text is reliable).
Scanned/OCR pages are skipped because PyMuPDF had no usable text.
"""

import logging
import re

from app.models.schemas import Alert, AlertSeverity, ClassifiedDocument, ExtractedData

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for structured identifiers
# ---------------------------------------------------------------------------

# ISO 6346 container number: 4 uppercase letters + 7 digits (e.g. MSCU1234567)
_CONTAINER_RE = re.compile(r"\b([A-Z]{4}\d{7})\b")

# Transport IDs: common prefixes followed by alphanumeric IDs
# Matches: MBOL1234, HBOL-5678, BL 9012345, AWB 123-45678901, CRT-2024/001
_TRANSPORT_ID_RE = re.compile(
    r"\b(?:M?[HB]?(?:OL|[/]?L)|AWB|CRT|HAWB|MAWB)"
    r"[\s.:_#-]*"
    r"([A-Z0-9][A-Z0-9\-/]{3,25})\b",
    re.IGNORECASE,
)

# Invoice/factura numbers: "Invoice", "Factura", "Inv" followed by a number
_INVOICE_RE = re.compile(
    r"\b(?:Invoice|Factura|Inv\.?|Fact\.?)"
    r"[\s.:_#N°no-]*"
    r"([A-Z0-9][A-Z0-9\-/]{2,20})\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_extracted_data(
    documents: list[ClassifiedDocument],
) -> list[Alert]:
    """Cross-check LLM-extracted data against PyMuPDF raw text.

    Returns alerts for mismatches. Also patches extracted_data in-place
    when the raw text has values the LLM missed.
    """
    alerts: list[Alert] = []

    for doc in documents:
        # Skip documents whose text came from OCR (not reliable for validation)
        if not doc.text.strip():
            continue

        raw_text = doc.text
        data = doc.extracted_data

        alerts.extend(_check_containers(data, raw_text, doc.source_filename))
        alerts.extend(_check_transport_ids(data, raw_text, doc.source_filename))
        alerts.extend(_check_invoice_numbers(data, raw_text, doc.source_filename))

    return alerts


# ---------------------------------------------------------------------------
# Field-level checks
# ---------------------------------------------------------------------------


def _check_containers(
    data: ExtractedData, raw_text: str, source: str
) -> list[Alert]:
    """Validate container numbers against raw text."""
    alerts: list[Alert] = []
    text_containers = set(_CONTAINER_RE.findall(raw_text))

    # Check each LLM-extracted container exists in raw text
    verified: list[str] = []
    for container in data.container_numbers:
        normalized = container.replace(" ", "").replace("-", "").upper()
        if normalized in text_containers:
            verified.append(normalized)
        else:
            # Try fuzzy: maybe LLM transposed a digit
            match = _find_closest(normalized, text_containers)
            if match:
                alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    document=source,
                    message=(
                        f"Contenedor '{container}' del LLM corregido "
                        f"a '{match}' según texto PDF"
                    ),
                ))
                verified.append(match)
            else:
                alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    document=source,
                    message=(
                        f"Contenedor '{container}' extraído por el LLM "
                        f"no aparece en el texto del PDF"
                    ),
                ))
                verified.append(container)

    # Recover containers the LLM missed (use verified list, not originals)
    verified_set = set(verified)
    missed = text_containers - verified_set
    for container in sorted(missed):
        logger.info("Recovered missed container %s from raw text in %s", container, source)
        verified.append(container)
        alerts.append(Alert(
            severity=AlertSeverity.INFO,
            document=source,
            message=(
                f"Contenedor '{container}' encontrado en texto PDF "
                f"pero no reportado por el LLM — agregado"
            ),
        ))

    # Patch in-place with validated list
    if verified != data.container_numbers:
        data.container_numbers = verified

    return alerts


def _check_transport_ids(
    data: ExtractedData, raw_text: str, source: str
) -> list[Alert]:
    """Validate transport IDs against raw text and patch corrections in-place."""
    alerts: list[Alert] = []
    text_ids = set(_TRANSPORT_ID_RE.findall(raw_text))

    # Normalize for comparison
    text_ids_upper = {tid.upper().strip() for tid in text_ids}

    verified: list[str] = []
    for tid in data.transport_ids:
        tid_upper = tid.upper().strip()
        if _value_in_text(tid_upper, raw_text):
            verified.append(tid)
        else:
            # Check if a close match exists in regex results
            match = _find_closest(tid_upper, text_ids_upper)
            if match:
                alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    document=source,
                    message=(
                        f"ID transporte '{tid}' del LLM corregido "
                        f"a '{match}' según texto PDF"
                    ),
                ))
                verified.append(match)
            else:
                alerts.append(Alert(
                    severity=AlertSeverity.WARNING,
                    document=source,
                    message=(
                        f"ID transporte '{tid}' extraído por el LLM "
                        f"no aparece en el texto del PDF"
                    ),
                ))
                verified.append(tid)

    # Patch in-place with validated list
    if verified != data.transport_ids:
        data.transport_ids = verified

    return alerts


def _check_invoice_numbers(
    data: ExtractedData, raw_text: str, source: str
) -> list[Alert]:
    """Validate invoice numbers against raw text."""
    alerts: list[Alert] = []

    for inv in data.invoice_numbers:
        if not _value_in_text(inv, raw_text):
            alerts.append(Alert(
                severity=AlertSeverity.WARNING,
                document=source,
                message=(
                    f"Factura '{inv}' extraída por el LLM "
                    f"no aparece en el texto del PDF"
                ),
            ))

    # Try to recover missed invoices
    text_invoices = set(_INVOICE_RE.findall(raw_text))
    llm_invoices = {inv.upper().strip() for inv in data.invoice_numbers}
    for inv in sorted(text_invoices):
        if inv.upper().strip() not in llm_invoices:
            if not any(inv.upper() in llm_inv for llm_inv in llm_invoices):
                logger.info(
                    "Recovered missed invoice %s from raw text in %s", inv, source
                )
                data.invoice_numbers.append(inv)
                alerts.append(Alert(
                    severity=AlertSeverity.INFO,
                    document=source,
                    message=(
                        f"Factura '{inv}' encontrada en texto PDF "
                        f"pero no reportada por el LLM — agregada"
                    ),
                ))

    return alerts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _value_in_text(value: str, text: str) -> bool:
    """Check if a value appears in the raw text (case-insensitive, whitespace-tolerant)."""
    # Direct substring match
    if value.lower() in text.lower():
        return True
    # Try without common separators
    stripped = value.replace("-", "").replace("/", "").replace(" ", "")
    text_stripped = text.replace("-", "").replace("/", "").replace(" ", "")
    return stripped.lower() in text_stripped.lower()


def _find_closest(value: str, candidates: set[str], max_dist: int = 2) -> str | None:
    """Find the closest match in candidates by character edit distance.

    Only returns a match if the edit distance is <= max_dist, indicating
    a likely typo (transposed digit, extra/missing character).
    """
    best_match = None
    best_dist = max_dist + 1

    for candidate in candidates:
        dist = _levenshtein(value, candidate)
        if dist < best_dist:
            best_dist = dist
            best_match = candidate

    return best_match if best_dist <= max_dist else None


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,       # insert
                prev_row[j + 1] + 1,   # delete
                prev_row[j] + cost,     # substitute
            ))
        prev_row = curr_row

    return prev_row[-1]
