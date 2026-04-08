# CLAUDE.md

## Git
- Don't mention claude models as co-author in commit messages — the repository already considers it.

## Project overview
- **Domain**: Chilean customs document processing (Agencia de Aduanas)
- **Core**: Python 3.12 backend in `backend/app/`
- **Pipeline**: `services/pipeline.py` orchestrates OCR → split → classify → extract → validate → rename → ZIP
- **AI**: Claude Sonnet via `tool_use` for classification and extraction; prompts in `prompts/`
- **OCR**: PyMuPDF first pass (free), then Textract or Mistral fallback. Raw OCR results saved to S3.
- **Deployment target**: AWS serverless (Lambda, S3, DynamoDB, SQS, Amplify)
- **Frontend** (planned): Next.js 15 + Tailwind + shadcn/ui

## Code conventions
- Linter: `ruff check app/` (run from `backend/`)
- All models use Pydantic v2 (`BaseModel`, `BaseSettings`)
- Services are pure functions or use module-level lazy singletons for API clients
- `pipeline.process_job()` is transport-agnostic (ports & adapters) — no S3/Lambda/HTTP awareness
- Document types defined in `models/document.py`; keep `DocumentType` enum, label dicts, and prompt enums in sync

## Commands
```bash
cd backend
source .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
ruff check app/
pytest
```
