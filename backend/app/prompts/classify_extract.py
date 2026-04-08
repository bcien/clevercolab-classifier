"""Combined classification + extraction prompt and tool schema.

Merges the separate classify and extract steps into a single LLM call,
cutting API costs and latency in half for the core analysis pipeline.
"""

CLASSIFY_EXTRACT_SYSTEM = """\
You are an expert document analyst specializing in international trade \
and Chilean customs (Agencia de Aduanas) documentation.

You will receive content from a PDF (either extracted text or page images). \
Your task is to:
1. Identify which consecutive pages belong to the same document.
2. Classify each document into exactly one category.
3. Extract reference identifiers and metadata from each document.

## Document Categories

- transport_document: Bill of Lading (BL), Conocimiento de Embarque, Carta de Porte Terrestre \
(CRT), Air Waybill (AWB), Guía Aérea. The core contract of carriage.
- commercial_invoice: Factura Comercial, Commercial Invoice. Bill of sale with buyer, seller, \
goods, quantities, prices.
- packing_list: Lista de Empaque, Packing List. Physical contents, packaging, weight, dimensions.
- certificate_of_origin: Certificado de Origen, Certificate of Origin. Declares country of \
manufacture for TLC tariff preferences.
- insurance_certificate: Certificado de Seguro, Insurance Certificate. Proof of cargo insurance.
- vb_certificate: Certificado Visto Bueno (V°B°), Resolución. Government agency approvals \
(SAG, Seremi de Salud, ISP, SEC).
- mandato: Mandato para Despacho, Poder. Legal authorization for the customs agency to clear goods.
- declaracion_jurada: Declaración Jurada del Valor y sus Elementos. Required value declaration \
under Chilean customs norms.
- other: Any document that does not fit the above categories.

## What to extract from each document

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

- A single document may span multiple consecutive pages.
- Look for headers, footers, document numbers, and layout changes to detect boundaries.
- A Bill of Lading is typically 1-2 pages.
- An invoice typically starts with "INVOICE" or "FACTURA" and seller/buyer info.
- A packing list contains weight/dimension tables.
- Extract exact values as they appear in the document.
- If a field is not present, return an empty list or null.
- Return your analysis as a structured JSON array."""


CLASSIFY_EXTRACT_USER_TEXT = """\
Below is the text extracted from a PDF with {total_pages} pages.
Analyze the content: identify document boundaries, classify each document, \
and extract reference identifiers and metadata from each.

{pages_text}"""


CLASSIFY_EXTRACT_USER_VISION = """\
Below are the pages of a {total_pages}-page PDF. Some pages are provided as images \
(scanned pages) and some as extracted text.
Analyze all pages: identify document boundaries, classify each document, \
and extract reference identifiers and metadata from each.

{pages_text}"""


_DOC_TYPE_ENUM = [
    "transport_document",
    "commercial_invoice",
    "packing_list",
    "certificate_of_origin",
    "insurance_certificate",
    "vb_certificate",
    "mandato",
    "declaracion_jurada",
    "other",
]

CLASSIFY_EXTRACT_TOOL = {
    "name": "report_analyzed_documents",
    "description": (
        "Report the identified document segments with their classification "
        "and extracted reference data"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_page": {
                            "type": "integer",
                            "description": "0-indexed first page of the document",
                        },
                        "end_page": {
                            "type": "integer",
                            "description": "0-indexed last page (inclusive)",
                        },
                        "doc_type": {
                            "type": "string",
                            "enum": _DOC_TYPE_ENUM,
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "transport_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "BL, AWB, CRT, or booking numbers",
                        },
                        "container_numbers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "ISO container numbers",
                        },
                        "invoice_numbers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Invoice or factura numbers",
                        },
                        "po_numbers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Purchase order numbers",
                        },
                        "consignee": {
                            "type": ["string", "null"],
                            "description": "Receiving party / importer",
                        },
                        "shipper": {
                            "type": ["string", "null"],
                            "description": "Sending party / exporter",
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
                        "start_page",
                        "end_page",
                        "doc_type",
                        "confidence",
                        "transport_ids",
                        "container_numbers",
                        "invoice_numbers",
                        "po_numbers",
                    ],
                },
            }
        },
        "required": ["segments"],
    },
}
