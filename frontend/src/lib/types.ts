/** Mirrors backend Pydantic models for the local dev API. */

export type JobStage =
  | "pending"
  | "extracting_text"
  | "splitting"
  | "classifying"
  | "extracting_data"
  | "validating"
  | "packaging"
  | "complete"
  | "failed";

export type AlertSeverity = "warning" | "info";

export interface ExtractedData {
  transport_ids: string[];
  container_numbers: string[];
  invoice_numbers: string[];
  po_numbers: string[];
  consignee: string | null;
  shipper: string | null;
  port_of_loading: string | null;
  port_of_discharge: string | null;
}

export interface ProcessedDocument {
  original_filename: string;
  renamed_filename: string;
  doc_type: string;
  confidence: number;
  extracted_data: ExtractedData;
}

export interface Alert {
  severity: AlertSeverity;
  document: string | null;
  message: string;
}

export interface Report {
  job_id: string;
  total_files_ingested: number;
  documents_found: ProcessedDocument[];
  missing_types: string[];
  alerts: Alert[];
}

export interface JobStatus {
  job_id: string;
  stage: JobStage;
  stage_label: string;
  progress: number;
  detail: string;
  report?: Report;
  error?: string;
}

export interface UploadResponse {
  job_id: string;
}

export interface OutputFile {
  name: string;
  size: number;
}

/** Human-readable labels for document types (Spanish). */
export const DOC_TYPE_LABELS: Record<string, string> = {
  transport_document: "Documento de Transporte",
  commercial_invoice: "Factura Comercial",
  packing_list: "Lista de Empaque",
  certificate_of_origin: "Certificado de Origen",
  insurance_certificate: "Certificado de Seguro",
  vb_certificate: "Certificado V\u00b0B\u00b0",
  mandato: "Mandato",
  declaracion_jurada: "Declaraci\u00f3n Jurada",
  other: "Otro",
};

/** Ordered pipeline stages for the progress tracker.
 *  Must match the execution order in backend pipeline.py:
 *  OCR → classify+extract (merged) → split → validate → package.
 */
export const PIPELINE_STAGES: { key: JobStage; label: string }[] = [
  { key: "extracting_text", label: "Extrayendo texto (OCR)" },
  { key: "classifying", label: "Clasificando y extrayendo datos" },
  { key: "splitting", label: "Separando documentos" },
  { key: "validating", label: "Validando consistencia" },
  { key: "packaging", label: "Empaquetando" },
];
