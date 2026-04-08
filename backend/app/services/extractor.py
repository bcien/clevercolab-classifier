import logging

import anthropic

from app.config import settings
from app.models.document import DOCUMENT_LABELS, DocumentType
from app.models.schemas import ExtractedData, PageText
from app.prompts.extract import EXTRACT_SYSTEM, EXTRACT_TOOL, EXTRACT_USER

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def extract_data(
    pages: list[PageText], doc_type: DocumentType
) -> ExtractedData:
    """Extract reference IDs and metadata from a classified document's text."""
    document_text = "\n\n".join(p.text for p in pages if p.text)
    doc_type_label = DOCUMENT_LABELS.get(doc_type, doc_type.value)

    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=EXTRACT_SYSTEM,
        tools=[EXTRACT_TOOL],
        tool_choice={"type": "tool", "name": "report_extracted_data"},
        messages=[
            {
                "role": "user",
                "content": EXTRACT_USER.format(
                    doc_type=doc_type_label, document_text=document_text
                ),
            }
        ],
    )

    return _parse_extraction_response(response)


def _parse_extraction_response(
    response: anthropic.types.Message,
) -> ExtractedData:
    for block in response.content:
        if block.type == "tool_use" and block.name == "report_extracted_data":
            data = block.input
            return ExtractedData(
                transport_ids=data.get("transport_ids", []),
                container_numbers=data.get("container_numbers", []),
                invoice_numbers=data.get("invoice_numbers", []),
                po_numbers=data.get("po_numbers", []),
                consignee=data.get("consignee"),
                shipper=data.get("shipper"),
                port_of_loading=data.get("port_of_loading"),
                port_of_discharge=data.get("port_of_discharge"),
            )

    logger.error("No tool_use block found in extraction response")
    return ExtractedData()
