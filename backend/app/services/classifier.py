"""Document boundary detection and classification.

Sends page texts to the configured LLM to identify where one document
ends and the next begins within a multi-document PDF, and classifies
each segment into a DocumentType.
"""

import logging

from app.models.document import DocumentType
from app.models.schemas import DocumentSegment, PageText
from app.prompts.classify import (
    CLASSIFY_AND_SPLIT_SYSTEM,
    CLASSIFY_AND_SPLIT_TOOL,
    CLASSIFY_AND_SPLIT_USER,
)
from app.services.llm import tool_use_request

logger = logging.getLogger(__name__)


def classify_and_split(pages: list[PageText]) -> list[DocumentSegment]:
    """Send all page texts to the LLM to detect document boundaries and classify each segment."""
    pages_text = "\n\n".join(
        f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages if p.text
    )

    result = tool_use_request(
        system=CLASSIFY_AND_SPLIT_SYSTEM,
        user_message=CLASSIFY_AND_SPLIT_USER.format(
            total_pages=len(pages), pages_text=pages_text
        ),
        tools=[CLASSIFY_AND_SPLIT_TOOL],
        forced_tool="report_document_segments",
        max_tokens=2048,
    )

    segments = [
        DocumentSegment(
            start_page=s["start_page"],
            end_page=s["end_page"],
            doc_type=DocumentType(s["doc_type"]),
            confidence=s["confidence"],
        )
        for s in result.input.get("segments", [])
    ]
    logger.info("Classified %d document segments", len(segments))
    return segments
