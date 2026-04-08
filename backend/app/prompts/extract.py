EXTRACT_SYSTEM = """You are an expert data extractor specializing in international trade \
and Chilean customs documentation.

You will receive text from a single logistics document. Extract all relevant reference \
identifiers and metadata.

## What to extract

- **transport_ids**: Bill of Lading numbers, AWB numbers, CRT numbers, booking numbers. \
  Look for patterns like "BL", "B/L", "MBOL", "HBOL", "AWB", "CRT", followed by alphanumeric IDs.
- **container_numbers**: ISO container numbers (e.g., MSCU1234567, TRIU9876543). \
  Format: 4 uppercase letters + 7 digits.
- **invoice_numbers**: Invoice or factura numbers.
- **po_numbers**: Purchase order numbers.
- **consignee**: The receiving party / importer name.
- **shipper**: The sending party / exporter name.
- **port_of_loading**: Port of origin / puerto de embarque.
- **port_of_discharge**: Destination port / puerto de destino.

## Rules

- Extract exact values as they appear in the document.
- If a field is not present, return an empty list or null.
- For transport documents, the transport_ids field is the most important."""


EXTRACT_USER = """Extract reference identifiers and metadata from this {doc_type} document:

{document_text}"""


EXTRACT_TOOL = {
    "name": "report_extracted_data",
    "description": "Report the extracted reference identifiers and metadata",
    "input_schema": {
        "type": "object",
        "properties": {
            "transport_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "BL, AWB, CRT, or booking numbers found",
            },
            "container_numbers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "ISO container numbers found",
            },
            "invoice_numbers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Invoice or factura numbers found",
            },
            "po_numbers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Purchase order numbers found",
            },
            "consignee": {
                "type": ["string", "null"],
                "description": "Receiving party / importer name",
            },
            "shipper": {
                "type": ["string", "null"],
                "description": "Sending party / exporter name",
            },
            "port_of_loading": {
                "type": ["string", "null"],
                "description": "Port of origin",
            },
            "port_of_discharge": {
                "type": ["string", "null"],
                "description": "Destination port",
            },
        },
        "required": [
            "transport_ids",
            "container_numbers",
            "invoice_numbers",
            "po_numbers",
        ],
    },
}
