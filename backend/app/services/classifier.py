import logging

import anthropic

from app.config import settings
from app.models.document import DocumentType
from app.models.schemas import DocumentSegment, PageText
from app.prompts.classify import (
    CLASSIFY_AND_SPLIT_SYSTEM,
    CLASSIFY_AND_SPLIT_TOOL,
    CLASSIFY_AND_SPLIT_USER,
)

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def classify_and_split(pages: list[PageText]) -> list[DocumentSegment]:
    """Send all page texts to Claude to detect document boundaries and classify each segment."""
    pages_text = "\n\n".join(
        f"--- PAGE {p.page_num} ---\n{p.text}" for p in pages if p.text
    )

    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system=CLASSIFY_AND_SPLIT_SYSTEM,
        tools=[CLASSIFY_AND_SPLIT_TOOL],
        tool_choice={"type": "tool", "name": "report_document_segments"},
        messages=[
            {
                "role": "user",
                "content": CLASSIFY_AND_SPLIT_USER.format(
                    total_pages=len(pages), pages_text=pages_text
                ),
            }
        ],
    )

    segments = _parse_segments_response(response)
    logger.info("Classified %d document segments", len(segments))
    return segments


def _parse_segments_response(
    response: anthropic.types.Message,
) -> list[DocumentSegment]:
    for block in response.content:
        if block.type == "tool_use" and block.name == "report_document_segments":
            raw_segments = block.input.get("segments", [])
            return [
                DocumentSegment(
                    start_page=s["start_page"],
                    end_page=s["end_page"],
                    doc_type=DocumentType(s["doc_type"]),
                    confidence=s["confidence"],
                )
                for s in raw_segments
            ]

    logger.error("No tool_use block found in classification response")
    return []
