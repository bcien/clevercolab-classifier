# Clevercolab Classifier

Automated classification, splitting, and consistency validation of international logistics documents for Chilean customs agencies (*Agencias de Aduanas*).

## What it does

1. **OCR & text extraction** — PyMuPDF for text-layer PDFs (free, instant), with configurable fallback OCR for scanned documents (Textract, Mistral, OpenAI, Google Gemini, or Nanonets)
2. **Classification + data extraction** — identifies document types and extracts reference data (transport IDs, container numbers, etc.) in a single LLM call. Supports a **vision path** that merges OCR + classify + extract into one call for scanned pages.
3. **Post-LLM validation** — cross-checks LLM-extracted values (container numbers, transport IDs, invoice numbers) against PyMuPDF raw text using regex + Levenshtein fuzzy matching. Corrects typos, flags hallucinations, and recovers missed values.
4. **Document splitting** — separates multi-document PDFs by detected page boundaries
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
    local_server.py        # FastAPI local dev server (no AWS dependencies)
    models/
      document.py          # Document type definitions and labels
      schemas.py           # Pydantic models for the full pipeline
    services/
      pipeline.py          # Main orchestrator (JobInput -> JobResult)
      ocr.py               # Two-tier OCR: PyMuPDF + fallback (Textract/Mistral/OpenAI/Google/Nanonets)
      analyzer.py          # Combined classify + extract (text & vision paths)
      llm.py               # Unified LLM client (Anthropic, OpenAI, Google, Nanonets)
      post_validate.py     # Post-LLM validation against PyMuPDF raw text
      consistency.py       # Cross-document consistency validation
      splitter.py          # PDF splitting by page ranges
      renamer.py           # Normalized file naming
      archiver.py          # ZIP creation
      reporter.py          # Summary report generation
      classifier.py        # (legacy) Standalone classification — superseded by analyzer.py
      extractor.py         # (legacy) Standalone extraction — superseded by analyzer.py
    prompts/
      classify_extract.py  # Combined classify+extract prompt + tool schema
      classify.py          # (legacy) Classification-only prompt
      extract.py           # (legacy) Extraction-only prompt
    handlers/              # Lambda handlers (Sprint 2)
    storage/               # S3 and DynamoDB operations (Sprint 2)
frontend/                  # Next.js 16 + Tailwind + shadcn/ui
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
| `LLM_PROVIDER` | `anthropic` (default), `openai`, `google`, or `nanonets` — LLM for classify+extract |
| `ANTHROPIC_API_KEY` | Claude API key (when `LLM_PROVIDER=anthropic`) |
| `OPENAI_API_KEY` | OpenAI API key (when `LLM_PROVIDER=openai` or `OCR_PROVIDER=openai`) |
| `GOOGLE_API_KEY` | Google API key (when `LLM_PROVIDER=google` or `OCR_PROVIDER=google`) |
| `NANONETS_API_KEY` | Nanonets API key (when `LLM_PROVIDER=nanonets` or `OCR_PROVIDER=nanonets`) |
| `MISTRAL_API_KEY` | Mistral API key (only needed if `OCR_PROVIDER=mistral`) |
| `OCR_PROVIDER` | `textract` (default), `mistral`, `openai`, `google`, or `nanonets` — fallback OCR for scanned pages |
| `AWS_REGION` | AWS region for Textract, S3, DynamoDB |
| `S3_OCR_RESULTS_BUCKET` | S3 bucket for persisting raw OCR results |
| `LOCAL_OUTPUT_DIR` | Local directory for results (local dev mode, default: `output`) |

**Vision path**: When `OCR_PROVIDER` and `LLM_PROVIDER` are the same vision-capable provider (anthropic, openai, or google), the pipeline merges OCR + classify + extract into a single LLM call, reducing cost and latency.

## Architecture

- **Pipeline pattern (ports & adapters)**: `pipeline.process_job()` accepts `JobInput` (PDF bytes) and returns `JobResult` (report + ZIP bytes). It is transport-agnostic — callers (Lambda, CLI, local server) handle I/O.
- **Unified LLM abstraction** (`llm.py`): translates between Anthropic tool_use, OpenAI function-calling, Google Gemini function declarations, and Nanonets schema-based REST. All providers use the same tool schema.
- **Two processing paths**: text path (OCR → classify+extract) and vision path (classify+extract+OCR in one call for scanned pages).
- **Post-LLM validation**: PyMuPDF raw text is used as ground truth to verify, correct, and recover extracted values.
- **OCR results are preserved**: raw JSON responses saved to S3 or local filesystem for future reprocessing.

## Local development

```bash
# Terminal 1: Backend
cd backend
source .venv/Scripts/activate
uvicorn app.local_server:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
# Opens http://localhost:3000
```

## Tech stack

- Python 3.12, FastAPI, Pydantic v2
- PyMuPDF (fitz) — PDF text extraction, splitting, and page rendering
- OCR providers: AWS Textract, Mistral OCR, OpenAI Vision, Google Gemini, Nanonets OCR2+
- LLM providers: Claude Sonnet (Anthropic), GPT-5.4 (OpenAI), Gemini 3.1 Pro (Google), Nanonets OCR2+
- AWS Lambda, S3, DynamoDB, SQS — serverless deployment (Sprint 2+)
- Next.js 16, Tailwind CSS v4, shadcn/ui v4 — frontend
