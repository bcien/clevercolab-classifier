"""FastAPI local development server.

Wraps the processing pipeline with REST endpoints and in-memory job state.
No DynamoDB, no S3 — results saved to local filesystem.

Usage:
    cd backend
    uvicorn app.local_server:app --reload --port 8000
"""

import json
import logging
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.models.schemas import (
    STAGE_LABELS,
    JobInput,
    JobResult,
    JobStage,
    PdfInput,
    Report,
)
from app.services.pipeline import process_job

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(settings.local_output_dir or "output")

# ---------------------------------------------------------------------------
# In-memory job state (replaces DynamoDB)
# ---------------------------------------------------------------------------


@dataclass
class JobState:
    job_id: str
    stage: JobStage = JobStage.PENDING
    progress: float = 0.0
    detail: str = ""
    report: Report | None = None
    error: str | None = None


_jobs: dict[str, JobState] = {}
_lock = Lock()
_executor = ThreadPoolExecutor(max_workers=2)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Clevercolab Classifier — Local Dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/upload")
async def upload_files(files: list[UploadFile]) -> JSONResponse:
    """Accept PDF files and start processing in background."""
    if not files:
        return JSONResponse({"error": "No files provided"}, status_code=400)

    job_id = uuid.uuid4().hex[:12]
    pdfs: list[PdfInput] = []

    for f in files:
        content = await f.read()
        pdfs.append(PdfInput(filename=f.filename or "unknown.pdf", content=content))

    job_input = JobInput(job_id=job_id, pdfs=pdfs)

    with _lock:
        _jobs[job_id] = JobState(job_id=job_id)

    _executor.submit(_run_pipeline, job_id, job_input)

    return JSONResponse({"job_id": job_id})


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> JSONResponse:
    """Return current job status, progress, and report when complete."""
    with _lock:
        job = _jobs.get(job_id)

    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    data: dict = {
        "job_id": job.job_id,
        "stage": job.stage.value,
        "stage_label": STAGE_LABELS.get(job.stage, ""),
        "progress": job.progress,
        "detail": job.detail,
    }

    if job.report:
        data["report"] = json.loads(job.report.model_dump_json())

    if job.error:
        data["error"] = job.error

    return JSONResponse(data)


@app.get("/api/jobs/{job_id}/download")
async def download_zip(job_id: str) -> FileResponse | JSONResponse:
    """Serve the result ZIP file."""
    zip_path = OUTPUT_DIR / job_id / "result.zip"
    if not zip_path.exists():
        return JSONResponse({"error": "ZIP not found"}, status_code=404)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"clevercolab_{job_id}.zip",
    )


@app.get("/api/jobs/{job_id}/files")
async def list_output_files(job_id: str) -> JSONResponse:
    """List individual output files for review."""
    files_dir = OUTPUT_DIR / job_id / "files"
    if not files_dir.exists():
        return JSONResponse({"files": []})

    files = [
        {"name": f.name, "size": f.stat().st_size}
        for f in sorted(files_dir.iterdir())
        if f.is_file()
    ]
    return JSONResponse({"files": files})


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------


def _run_pipeline(job_id: str, job_input: JobInput) -> None:
    """Run the processing pipeline in a background thread."""

    def on_progress(stage: JobStage, pct: float, detail: str = "") -> None:
        with _lock:
            job = _jobs[job_id]
            job.stage = stage
            job.progress = pct
            job.detail = detail

    try:
        result = process_job(job_input, on_progress=on_progress)
        _save_results(job_id, result)

        with _lock:
            job = _jobs[job_id]
            job.stage = JobStage.COMPLETE
            job.progress = 1.0
            job.report = result.report

        logger.info("Job %s completed — %d documents", job_id, len(result.report.documents_found))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        with _lock:
            job = _jobs[job_id]
            job.stage = JobStage.FAILED
            job.error = str(exc)


def _save_results(job_id: str, result: JobResult) -> None:
    """Save pipeline results to local filesystem."""
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save report JSON
    report_path = job_dir / "report.json"
    report_path.write_text(
        result.report.model_dump_json(indent=2), encoding="utf-8"
    )

    # Save ZIP
    zip_path = job_dir / "result.zip"
    zip_path.write_bytes(result.zip_bytes)

    # Extract individual files for easy review
    files_dir = job_dir / "files"
    files_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(BytesIO(result.zip_bytes)) as zf:
        for name in zf.namelist():
            # Sanitize: skip entries with path traversal or absolute paths
            if ".." in name or Path(name).is_absolute():
                logger.warning("Skipping suspicious ZIP entry: %s", name)
                continue
            (files_dir / name).write_bytes(zf.read(name))

    logger.info("Saved results to %s", job_dir)
