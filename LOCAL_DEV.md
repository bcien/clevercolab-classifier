# Local Development Guide

How to run and test the classifier locally without AWS infrastructure.

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- At least one LLM provider API key (see table below)
- AWS credentials (only if using `OCR_PROVIDER=textract`)

| Provider | Key needed | Used for |
|----------|-----------|----------|
| Anthropic | `ANTHROPIC_API_KEY` | LLM (default) |
| OpenAI | `OPENAI_API_KEY` | LLM and/or OCR |
| Google | `GOOGLE_API_KEY` | LLM and/or OCR |
| Nanonets | `NANONETS_API_KEY` | LLM and/or OCR |
| Mistral | `MISTRAL_API_KEY` | OCR only |
| AWS | credentials via `aws configure` | OCR (Textract, default) |

> Text-layer PDFs (most digital logistics documents) don't need OCR — PyMuPDF extracts text for free. OCR is only triggered for scanned/image-only pages.

---

## 1. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -e ".[dev]"
```

### Configure environment

```bash
cp ../.env.example .env
```

Edit `backend/.env`:

```env
# LLM provider for classification + extraction
LLM_PROVIDER=anthropic           # anthropic | openai | google | nanonets
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-...          # if LLM_PROVIDER=openai or OCR_PROVIDER=openai
# GOOGLE_API_KEY=...             # if LLM_PROVIDER=google or OCR_PROVIDER=google
# NANONETS_API_KEY=...           # if LLM_PROVIDER=nanonets or OCR_PROVIDER=nanonets

# OCR fallback for scanned pages
OCR_PROVIDER=textract            # textract | mistral | openai | google | nanonets
# MISTRAL_API_KEY=...            # if OCR_PROVIDER=mistral

# Leave empty to skip S3 — OCR results save locally instead
S3_OCR_RESULTS_BUCKET=

# Local output directory (relative to backend/)
LOCAL_OUTPUT_DIR=output
```

**Vision path shortcut**: If you set `OCR_PROVIDER` and `LLM_PROVIDER` to the same vision-capable provider (`anthropic`, `openai`, or `google`), the pipeline merges OCR + classify + extract into a single LLM call — faster and cheaper for scanned pages.

### Start the server

```bash
uvicorn app.local_server:app --reload --port 8000
```

The API is now available at `http://localhost:8000`. FastAPI docs at `http://localhost:8000/docs`.

---

## 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:3000`. The frontend connects to `http://localhost:8000` by default.

To point to a different backend, set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 3. Usage

1. Open `http://localhost:3000`
2. Drag-and-drop or browse for PDF files
3. Click **"Procesar documentos"**
4. Watch the progress tracker as the pipeline runs (~10–30s)
5. Review the classification report: document types, confidence scores, extracted data, consistency alerts
6. Click **"Descargar ZIP"** to get the packaged output

---

## 4. Reviewing Results Locally

After processing, output files are saved to `backend/output/{job_id}/`:

```
backend/output/a1b2c3d4e5f6/
  report.json                          # Full classification report
  result.zip                           # ZIP with all renamed PDFs
  files/
    MAWB12345_DocumentoTransporte.pdf  # Individual renamed PDFs
    MAWB12345_FacturaComercial.pdf
    MAWB12345_ListaEmpaque.pdf
    ...
  ocr_results/                         # Only if OCR was triggered
    original.pdf/
      textract/                        # or mistral/, openai/, google/, nanonets/
        page_0001.json                 # Raw OCR provider response
```

- **`report.json`** — machine-readable report with all classified documents, extracted data, alerts, and missing document types.
- **`files/`** — each PDF renamed as `[TransportID]_[DocType].pdf` for easy manual review.
- **`ocr_results/`** — raw OCR provider responses (Textract, Mistral, OpenAI, Google, or Nanonets), preserved for future reprocessing.

---

## 5. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload PDF files (multipart form, field: `files`) |
| `GET` | `/api/jobs/{id}` | Job status, progress, and report when complete |
| `GET` | `/api/jobs/{id}/download` | Download result ZIP |
| `GET` | `/api/jobs/{id}/files` | List individual output files |

### Example with curl

```bash
# Upload
curl -X POST http://localhost:8000/api/upload \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf"
# Returns: {"job_id": "a1b2c3d4e5f6"}

# Poll status
curl http://localhost:8000/api/jobs/a1b2c3d4e5f6

# Download ZIP
curl -o result.zip http://localhost:8000/api/jobs/a1b2c3d4e5f6/download
```

---

## 6. Differences from Production

| Aspect | Local | Production (AWS) |
|--------|-------|-----------------|
| Job state | In-memory dict (lost on restart) | DynamoDB |
| File storage | `backend/output/` folder | S3 buckets |
| OCR results | Local `ocr_results/` folder | S3 bucket |
| Upload | Direct POST to FastAPI | Presigned S3 URL |
| Concurrency | 2 background threads | Lambda auto-scaling |
| Auth | None | Cognito / API keys |

The processing pipeline (`pipeline.process_job()`) is identical in both environments.

---

## Troubleshooting

**"Textract OCR failed"** — You need AWS credentials configured (`aws configure`) or switch to a different `OCR_PROVIDER` (e.g., `openai`, `google`, `mistral`, `nanonets`). Text-layer PDFs work without any OCR provider.

**"API key not set, skipping OCR"** — The configured `OCR_PROVIDER` requires an API key that isn't set in `.env`. Either add the key or switch to a different provider.

**Frontend can't connect to backend** — Make sure both servers are running and CORS is enabled (the local server allows `localhost:3000` by default).

**Slow processing** — The classify+extract LLM call takes ~3–8s depending on the provider and document size. Using the vision path (matching `LLM_PROVIDER` and `OCR_PROVIDER`) reduces total time for scanned documents by eliminating a separate OCR step.

**Duplicate filenames** — If you upload multiple PDFs with the same filename, the pipeline automatically disambiguates them with a `(N)` suffix in the report.
