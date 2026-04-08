CLASSIFY_AND_SPLIT_SYSTEM = """\
You are an expert document analyst specializing in international trade \
and Chilean customs (Agencia de Aduanas) documentation.

You will receive the text extracted from each page of a PDF. Your task is to:
1. Identify which consecutive pages belong to the same document.
2. Classify each document into exactly one category.

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

## Rules

- A single document may span multiple consecutive pages.
- Look for headers, footers, document numbers, and layout changes to detect boundaries.
- A Bill of Lading is typically 1-2 pages.
- An invoice typically starts with "INVOICE" or "FACTURA" and seller/buyer info.
- A packing list contains weight/dimension tables.
- Return your analysis as a structured JSON array."""


CLASSIFY_AND_SPLIT_USER = """Below is the text extracted from a PDF with {total_pages} pages.
Analyze the content and identify the document boundaries and types.

{pages_text}

Return a JSON array of document segments. Each segment must have:
- start_page: 0-indexed first page of the document
- end_page: 0-indexed last page of the document (inclusive)
- doc_type: one of the category IDs listed above
- confidence: your confidence score from 0.0 to 1.0"""


CLASSIFY_AND_SPLIT_TOOL = {
    "name": "report_document_segments",
    "description": "Report the identified document segments in the PDF",
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
                            "enum": [
                                "transport_document",
                                "commercial_invoice",
                                "packing_list",
                                "certificate_of_origin",
                                "insurance_certificate",
                                "vb_certificate",
                                "mandato",
                                "declaracion_jurada",
                                "other",
                            ],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": ["start_page", "end_page", "doc_type", "confidence"],
                },
            }
        },
        "required": ["segments"],
    },
}
