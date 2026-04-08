"""Structured data extraction from classified documents.

Sends document text to the configured LLM to extract reference IDs,
party names, and port information using tool_use / function-calling.
"""

import logging

from app.models.document import DOCUMENT_LABELS, DocumentType
from app.models.schemas import ExtractedData, PageText
from app.prompts.extract import EXTRACT_SYSTEM, EXTRACT_TOOL, EXTRACT_USER
from app.services.llm import tool_use_request

logger = logging.getLogger(__name__)


def extract_data(
    pages: list[PageText], doc_type: DocumentType
) -> ExtractedData:
    """Extract reference IDs and metadata from a classified document's text."""
    document_text = "\n\n".join(p.text for p in pages if p.text)
    doc_type_label = DOCUMENT_LABELS.get(doc_type, doc_type.value)

    result = tool_use_request(
        system=EXTRACT_SYSTEM,
        user_message=EXTRACT_USER.format(
            doc_type=doc_type_label, document_text=document_text
        ),
        tools=[EXTRACT_TOOL],
        forced_tool="report_extracted_data",
        max_tokens=1024,
    )

    data = result.input
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
