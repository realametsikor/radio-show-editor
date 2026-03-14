"""
main.py — FastAPI Application for the Radio Show Editor
========================================================
Provides three endpoints:

    POST   /upload            Upload a .wav file → returns ``{task_id}``
    GET    /status/{task_id}  Poll task progress → PENDING / PROCESSING / SUCCESS / FAILURE
    GET    /download/{task_id}  Download the final mixed .wav file

Run the server:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import aiofiles
from celery.result import AsyncResult
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from tasks import celery_app, process_audio_task

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Radio Show Editor API",
    description="Upload a podcast, let the pipeline process it, download the finished radio show.",
    version="0.1.0",
)

# CORS: use ALLOWED_ORIGINS env var (comma-separated) in production,
# falls back to the Vercel frontend for safety.
_raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://radio-show-editor.vercel.app",
)
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temporary upload directory — each upload gets its own subfolder.
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Maximum upload size (500 MB).
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Accept an audio file upload, save it to disk, and dispatch the
    processing task to Celery.

    Returns ``{"task_id": "<celery-task-id>"}`` immediately.
    """
    # Validate content type
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"Expected an audio file, got '{file.content_type}'.",
        )

    # Create a unique directory for this job
    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Preserve original filename or fall back to a safe default
    safe_name = file.filename or "upload.wav"
    file_path = job_dir / safe_name

    # Stream the upload to disk
    total_bytes = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                await out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}") from exc

    logger.info("Saved upload to %s (%d bytes)", file_path, total_bytes)

    # Dispatch the Celery task
    task = process_audio_task.delay(str(file_path.resolve()))

    return {"task_id": task.id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Check the current state of a processing task.

    Possible states:
        - PENDING: Task is queued but not yet picked up by a worker.
        - PROCESSING: Task is actively running.
        - SUCCESS: Task finished; the result is the output file path.
        - FAILURE: Task failed; an error message is included.
    """
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        return {"task_id": task_id, "status": "PENDING"}

    if result.state == "PROCESSING":
        return {"task_id": task_id, "status": "PROCESSING"}

    if result.state == "SUCCESS":
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "result_file": result.result,
        }

    if result.state == "FAILURE":
        error_msg = str(result.result) if result.result else "Unknown error"
        return {
            "task_id": task_id,
            "status": "FAILURE",
            "error": error_msg,
        }

    # Any other Celery state (STARTED, RETRY, etc.)
    return {"task_id": task_id, "status": result.state}


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    """Serve the final mixed .wav file if the task completed successfully."""
    result = AsyncResult(task_id, app=celery_app)

    if result.state != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not complete yet. Current status: {result.state}",
        )

    output_path = Path(result.result)

    if not output_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output file not found on disk. It may have been cleaned up.",
        )

    return FileResponse(
        path=str(output_path),
        media_type="audio/wav",
        filename="radio_show_final.wav",
    )


@app.get("/health")
async def health_check():
    """Lightweight health probe for container orchestration and load balancers."""
    return {"status": "ok"}
