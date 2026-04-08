"""Combined document classification and data extraction.

Merges the classify and extract steps into a single LLM call.
Supports two paths:

- **Text path**: receives already-extracted page texts (after OCR).
- **Vision path**: receives page images directly, letting the vision
  model handle OCR + classification + extraction in one shot.
  Activated when ``ocr_provider == llm_provider`` and the provider
  is vision-capable (anthropic, openai, google).
"""

import logging

import fitz

from app.config import settings
from app.models.document import DocumentType
from app.models.schemas import AnalyzedSegment, ExtractedData, PageText
from app.prompts.classify_extract import (
    CLASSIFY_EXTRACT_SYSTEM,
    CLASSIFY_EXTRACT_TOOL,
    CLASSIFY_EXTRACT_USER_TEXT,
    CLASSIFY_EXTRACT_USER_VISION,
)
from app.services.llm import tool_use_request

logger = logging.getLogger(__name__)

VISION_CAPABLE_PROVIDERS = {"anthropic", "openai", "google"}
MAX_VISION_PAGES = 30


def use_vision_path() -> bool:
    """Return True when OCR + classify + extract can be merged into one vision call."""
    return (
        settings.ocr_provider == settings.llm_provider
        and settings.llm_provider in VISION_CAPABLE_PROVIDERS
    )


# ---------------------------------------------------------------------------
# Text path (Merge 1): classify + extract in one LLM call from page texts
# ---------------------------------------------------------------------------


def classify_and_extract(pages: list[PageText]) -> list[AnalyzedSegment]:
    """Classify document boundaries and extract data in a single LLM call."""
    pages_text = "\n\n".join(
        f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages if p.text
    )

    result = tool_use_request(
        system=CLASSIFY_EXTRACT_SYSTEM,
        user_message=CLASSIFY_EXTRACT_USER_TEXT.format(
            total_pages=len(pages), pages_text=pages_text
        ),
        tools=[CLASSIFY_EXTRACT_TOOL],
        forced_tool="report_analyzed_documents",
        max_tokens=4096,
    )

    segments = _parse_segments(result.input.get("segments", []))
    logger.info(
        "Classified and extracted %d document segments (text path)",
        len(segments),
    )
    return segments


# ---------------------------------------------------------------------------
# Vision path (Merge 2): OCR + classify + extract in one vision LLM call
# ---------------------------------------------------------------------------


def vision_classify_and_extract(
    pdf_bytes: bytes,
    pages: list[PageText],
) -> list[AnalyzedSegment]:
    """Send page images to a vision model for combined OCR + classify + extract.

    Text-layer pages (already extracted by PyMuPDF) are sent as text to save
    tokens. Only scanned pages are rendered as images.

    Args:
        pdf_bytes: Raw PDF file bytes (for rendering scanned pages).
        pages: Page texts from the PyMuPDF pass. Pages with ``used_ocr=True``
            had insufficient text and will be sent as images instead.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Separate text pages from pages that need vision
    ocr_page_nums = {p.page_num for p in pages if p.used_ocr}

    # If too many pages need images, fall back to text path
    if len(ocr_page_nums) > MAX_VISION_PAGES:
        doc.close()
        logger.info(
            "Too many scanned pages (%d > %d), falling back to text path",
            len(ocr_page_nums),
            MAX_VISION_PAGES,
        )
        return classify_and_extract(pages)

    # Build the text portion (text-layer pages + placeholders for image pages)
    text_parts: list[str] = []
    images: list[bytes] = []

    for page in pages:
        if page.page_num in ocr_page_nums:
            img_index = len(images) + 1
            text_parts.append(
                f"--- PAGE {page.page_num} [see image {img_index}] ---"
            )
            pixmap = doc[page.page_num].get_pixmap(dpi=200)
            images.append(pixmap.tobytes("png"))
        else:
            text_parts.append(
                f"--- PAGE {page.page_num} ---\n{page.text}"
            )

    doc.close()

    pages_text = "\n\n".join(text_parts)

    result = tool_use_request(
        system=CLASSIFY_EXTRACT_SYSTEM,
        user_message=CLASSIFY_EXTRACT_USER_VISION.format(
            total_pages=len(pages), pages_text=pages_text
        ),
        tools=[CLASSIFY_EXTRACT_TOOL],
        forced_tool="report_analyzed_documents",
        max_tokens=4096,
        images=images,
    )

    segments = _parse_segments(result.input.get("segments", []))
    logger.info(
        "Classified and extracted %d document segments (vision path, %d images)",
        len(segments),
        len(images),
    )
    return segments


# ---------------------------------------------------------------------------
# Shared parsing
# ---------------------------------------------------------------------------


def _parse_segments(raw_segments: list[dict]) -> list[AnalyzedSegment]:
    """Parse raw LLM output into AnalyzedSegment models."""
    return [
        AnalyzedSegment(
            start_page=s["start_page"],
            end_page=s["end_page"],
            doc_type=DocumentType(s["doc_type"]),
            confidence=s["confidence"],
            extracted_data=ExtractedData(
                transport_ids=s.get("transport_ids", []),
                container_numbers=s.get("container_numbers", []),
                invoice_numbers=s.get("invoice_numbers", []),
                po_numbers=s.get("po_numbers", []),
                consignee=s.get("consignee"),
                shipper=s.get("shipper"),
                port_of_loading=s.get("port_of_loading"),
                port_of_discharge=s.get("port_of_discharge"),
            ),
        )
        for s in raw_segments
    ]
