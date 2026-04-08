from enum import StrEnum

from pydantic import BaseModel

from app.models.document import DocumentType

# --- OCR ---


class PageText(BaseModel):
    page_num: int
    text: str
    used_ocr: bool = False
    ocr_provider: str | None = None
    raw_ocr_result: dict | str | None = None


# --- Splitting & Classification ---


class DocumentSegment(BaseModel):
    start_page: int
    end_page: int
    doc_type: DocumentType
    confidence: float


# --- Extraction ---


class ExtractedData(BaseModel):
    transport_ids: list[str] = []
    container_numbers: list[str] = []
    invoice_numbers: list[str] = []
    po_numbers: list[str] = []
    consignee: str | None = None
    shipper: str | None = None
    port_of_loading: str | None = None
    port_of_discharge: str | None = None


# --- Analyzed Segment (combined classify + extract result) ---


class AnalyzedSegment(BaseModel):
    """Result of the combined classify+extract LLM call for one document segment."""

    start_page: int
    end_page: int
    doc_type: DocumentType
    confidence: float
    extracted_data: ExtractedData


# --- Classified Document (after full processing of one segment) ---


class ClassifiedDocument(BaseModel):
    doc_type: DocumentType
    confidence: float
    extracted_data: ExtractedData
    source_filename: str
    start_page: int
    end_page: int
    text: str


# --- Consistency ---


class AlertSeverity(StrEnum):
    WARNING = "warning"
    INFO = "info"


class Alert(BaseModel):
    severity: AlertSeverity
    document: str | None = None
    message: str


# --- Pipeline I/O ---


class PdfInput(BaseModel):
    filename: str
    content: bytes

    model_config = {"arbitrary_types_allowed": True}


class JobInput(BaseModel):
    job_id: str
    pdfs: list[PdfInput]


class ProcessedDocument(BaseModel):
    original_filename: str
    renamed_filename: str
    doc_type: DocumentType
    confidence: float
    extracted_data: ExtractedData


class Report(BaseModel):
    job_id: str
    total_files_ingested: int
    documents_found: list[ProcessedDocument]
    missing_types: list[str]
    alerts: list[Alert]


class JobResult(BaseModel):
    report: Report
    zip_bytes: bytes

    model_config = {"arbitrary_types_allowed": True}


# --- Job Status (for DynamoDB / polling) ---


class JobStage(StrEnum):
    PENDING = "pending"
    EXTRACTING_TEXT = "extracting_text"
    SPLITTING = "splitting"
    CLASSIFYING = "classifying"
    EXTRACTING_DATA = "extracting_data"
    VALIDATING = "validating"
    PACKAGING = "packaging"
    COMPLETE = "complete"
    FAILED = "failed"


class JobStatus(BaseModel):
    job_id: str
    stage: JobStage
    stage_label: str = ""
    progress: float = 0.0
    detail: str = ""
    report: Report | None = None


STAGE_LABELS: dict[JobStage, str] = {
    JobStage.PENDING: "En cola...",
    JobStage.EXTRACTING_TEXT: "Extrayendo texto...",
    JobStage.SPLITTING: "Separando documentos...",
    JobStage.CLASSIFYING: "Clasificando documentos...",
    JobStage.EXTRACTING_DATA: "Extrayendo datos clave...",
    JobStage.VALIDATING: "Validando consistencia...",
    JobStage.PACKAGING: "Empaquetando archivos...",
    JobStage.COMPLETE: "Completado",
    JobStage.FAILED: "Error en procesamiento",
}
