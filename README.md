# Clevercolab Classifier

Automated classification, splitting, and consistency validation of international logistics documents for Chilean customs agencies (*Agencias de Aduanas*).

## What it does

1. **OCR & text extraction** — PyMuPDF for text-layer PDFs (free, instant), with AWS Textract or Mistral OCR as fallback for scanned documents
2. **Document splitting** — detects multiple documents merged in a single PDF and splits them
3. **Classification** — identifies document types (BL/AWB/CRT, invoices, packing lists, certificates, etc.) using Claude AI
4. **Data extraction** — pulls transport IDs, container numbers, invoice numbers, and other reference data
5. **Consistency check** — cross-references all documents to verify they belong to the same shipment
6. **Packaging** — renames files (`[TransportID]_[DocType].pdf`), generates a summary report, and creates a ZIP

## Supported document types

| Type | Description |
|------|-------------|
| Documento de Transporte | BL, CRT, AWB — contract of carriage |
| Factura Comercial | Commercial invoice |
| Lista de Empaque | Packing list |
| Certificado de Origen | Certificate of origin (for TLC tariff preferences) |
| Certificado de Seguro | Insurance certificate |
| Certificado V°B° | Government agency approvals (SAG, Seremi de Salud, ISP, SEC) |
| Mandato | Legal authorization for customs clearance |
| Declaración Jurada | Value declaration under Chilean customs norms |

## Project structure

```
backend/
  app/
    config.py              # Application settings (env vars)
    models/
      document.py          # Document type definitions and labels
      schemas.py           # Pydantic models for the full pipeline
    services/
      pipeline.py          # Main orchestrator (JobInput -> JobResult)
      ocr.py               # Two-tier OCR: PyMuPDF + Textract/Mistral fallback
      classifier.py        # Claude API — document classification
      extractor.py         # Claude API — reference ID extraction
      consistency.py       # Cross-reference validation
      splitter.py          # PDF splitting by page ranges
      renamer.py           # Normalized file naming
      archiver.py          # ZIP creation
      reporter.py          # Summary report generation
    prompts/
      classify.py          # Classification prompt + tool schema
      extract.py           # Extraction prompt + tool schema
    handlers/              # Lambda handlers (Sprint 2)
    storage/               # S3 and DynamoDB operations (Sprint 2)
```

## Setup

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Linux/Mac
pip install -e ".[dev]"
cp ../.env.example .env
# Edit .env with your API keys
```

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key for classification and extraction |
| `MISTRAL_API_KEY` | Mistral API key (only needed if `OCR_PROVIDER=mistral`) |
| `OCR_PROVIDER` | `textract` (default) or `mistral` — fallback OCR for scanned pages |
| `AWS_REGION` | AWS region for Textract, S3, DynamoDB |
| `S3_OCR_RESULTS_BUCKET` | S3 bucket for persisting raw OCR results |

## Architecture

- **Pipeline pattern (ports & adapters)**: `pipeline.process_job()` accepts `JobInput` (PDF bytes) and returns `JobResult` (report + ZIP bytes). It is transport-agnostic — callers (Lambda, CLI, tests) handle I/O.
- **OCR results are preserved**: raw Textract JSON or Mistral responses are saved to S3 (`s3://{bucket}/{job_id}/{filename}/{provider}/page_NNNN.json`) for future reprocessing.
- **Claude tool_use**: classification and extraction use structured tool calls for reliable JSON output.

## Tech stack

- Python 3.12, FastAPI, Pydantic
- PyMuPDF (fitz) — PDF text extraction and splitting
- AWS Textract / Mistral OCR — fallback OCR for scanned documents
- Claude Sonnet (Anthropic) — classification and data extraction
- AWS Lambda, S3, DynamoDB, SQS — serverless deployment (Sprint 2+)
- Next.js 15, Tailwind, shadcn/ui — frontend (Sprint 3+)
