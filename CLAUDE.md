# CLAUDE.md

## Git
- Don't mention claude models as co-author in commit messages — the repository already considers it.

## Project overview
- **Domain**: Chilean customs document processing (Agencia de Aduanas)
- **Core**: Python 3.12 backend in `backend/app/`
- **Pipeline**: `services/pipeline.py` orchestrates OCR → classify+extract → split → validate → rename → ZIP
- **LLM providers**: Anthropic Claude, OpenAI GPT, Google Gemini, Nanonets OCR2+ — unified in `services/llm.py`
- **OCR**: PyMuPDF first pass (free), then configurable fallback (Textract, Mistral, OpenAI, Google, Nanonets)
- **Vision path**: when `ocr_provider == llm_provider` and provider is vision-capable, OCR + classify + extract merge into one call
- **Post-validation**: `services/post_validate.py` cross-checks LLM output against PyMuPDF raw text (regex + Levenshtein)
- **Deployment target**: AWS serverless (Lambda, S3, DynamoDB, SQS, Amplify)
- **Frontend**: Next.js 16 + Tailwind CSS v4 + shadcn/ui v4 in `frontend/`

## Code conventions
- Linter: `ruff check app/` (run from `backend/`)
- All models use Pydantic v2 (`BaseModel`, `BaseSettings`)
- Services are pure functions or use module-level lazy singletons for API clients (including httpx in `ocr.py` and `llm.py`)
- `pipeline.process_job()` is transport-agnostic (ports & adapters) — no S3/Lambda/HTTP awareness
- Document types defined in `models/document.py`; prompt tool schemas derive enums via `[dt.value for dt in DocumentType]` — no hardcoded lists
- Tool schemas defined in Anthropic format; `llm.py` translates to each provider's convention
- `PIPELINE_STAGES` in `frontend/src/lib/types.ts` must match the stage order emitted by `pipeline.py`
- Duplicate uploaded filenames are disambiguated in pipeline with `(N)` suffix

## Commands
```bash
# Backend
cd backend
source .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
ruff check app/
pytest

# Frontend
cd frontend
npm run dev     # localhost:3000
npm run build
npm run lint

# Local end-to-end
cd backend && uvicorn app.local_server:app --reload --port 8000
cd frontend && npm run dev
```
