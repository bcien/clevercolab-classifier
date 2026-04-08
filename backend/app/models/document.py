from enum import StrEnum


class DocumentType(StrEnum):
    TRANSPORT_DOCUMENT = "transport_document"
    COMMERCIAL_INVOICE = "commercial_invoice"
    PACKING_LIST = "packing_list"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    VB_CERTIFICATE = "vb_certificate"
    MANDATO = "mandato"
    DECLARACION_JURADA = "declaracion_jurada"
    OTHER = "other"


DOCUMENT_LABELS: dict[DocumentType, str] = {
    DocumentType.TRANSPORT_DOCUMENT: "Documento de Transporte (BL/CRT/AWB)",
    DocumentType.COMMERCIAL_INVOICE: "Factura Comercial",
    DocumentType.PACKING_LIST: "Lista de Empaque",
    DocumentType.CERTIFICATE_OF_ORIGIN: "Certificado de Origen",
    DocumentType.INSURANCE_CERTIFICATE: "Certificado de Seguro",
    DocumentType.VB_CERTIFICATE: "Certificado Visto Bueno / Resolución",
    DocumentType.MANDATO: "Mandato para Despacho / Poder",
    DocumentType.DECLARACION_JURADA: "Declaración Jurada del Valor",
    DocumentType.OTHER: "Otro",
}

DOCUMENT_FILE_NAMES: dict[DocumentType, str] = {
    DocumentType.TRANSPORT_DOCUMENT: "DocumentoTransporte",
    DocumentType.COMMERCIAL_INVOICE: "FacturaComercial",
    DocumentType.PACKING_LIST: "ListaEmpaque",
    DocumentType.CERTIFICATE_OF_ORIGIN: "CertificadoOrigen",
    DocumentType.INSURANCE_CERTIFICATE: "CertificadoSeguro",
    DocumentType.VB_CERTIFICATE: "CertificadoVB",
    DocumentType.MANDATO: "Mandato",
    DocumentType.DECLARACION_JURADA: "DeclaracionJurada",
    DocumentType.OTHER: "Otro",
}

REQUIRED_DOCUMENT_TYPES: set[DocumentType] = {
    DocumentType.TRANSPORT_DOCUMENT,
    DocumentType.COMMERCIAL_INVOICE,
    DocumentType.PACKING_LIST,
}
