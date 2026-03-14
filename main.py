"""
main.py — FastAPI Application for the Radio Show Editor
========================================================
Provides three endpoints:

    POST   /upload            Upload a .wav file → returns ``{task_id}``
    GET    /status/{task_id}  Poll task progress → PENDING / PROCESSING / SUCCESS / FAILURE
    GET    /download/{task_id}  Download the final mixed .wav file

Designed for deployment on Hugging Face Spaces (Docker, port 7860).
Uses FastAPI BackgroundTasks with an in-memory dict instead of Celery/Redis.

Run the server:
    uvicorn main:app --host 0.0.0.0 --port 7860
"""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------
# Tracks task status across the lifetime of the process.
# Structure: { task_id: {"status": str, "result_file": str|None, "error": str|None} }
tasks: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Radio Show Editor API",
    description="Upload a podcast, let the pipeline process it, download the finished radio show.",
    version="0.2.0",
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
# Background processing function
# ---------------------------------------------------------------------------
def process_audio(task_id: str, file_path: str) -> None:
    """Run the full pipeline in a background thread.

    Updates the in-memory ``tasks`` dict so the /status endpoint can
    report progress.
    """
    from core_audio_engine.engine import run_pipeline

    tasks[task_id]["status"] = "PROCESSING"

    fp = Path(file_path)
    if not fp.is_file():
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = f"Uploaded file not found: {fp}"
        return

    output_dir = fp.parent / "output"
    output_file = fp.parent / "radio_show_final.wav"

    music_path = os.environ.get(
        "BACKGROUND_MUSIC_PATH",
        str(Path(__file__).resolve().parent / "assets" / "background_music.wav"),
    )

    logger.info("Starting pipeline for %s (task %s)", fp, task_id)

    try:
        final_path = run_pipeline(
            raw_audio=str(fp),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(final_path)
        logger.info("Pipeline complete → %s (task %s)", final_path, task_id)
    except Exception as exc:
        logger.exception("Pipeline failed for %s (task %s)", fp, task_id)
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Accept an audio file upload, save it to disk, and dispatch the
    processing task as a background job.

    Returns ``{"task_id": "<uuid>"}`` immediately.
    """
    # Validate content type
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"Expected an audio file, got '{file.content_type}'.",
        )

    # Create a unique directory for this job
    task_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / task_id
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

    # Register task and dispatch background processing
    tasks[task_id] = {"status": "PENDING", "result_file": None, "error": None}
    background_tasks.add_task(process_audio, task_id, str(file_path.resolve()))

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """Check the current state of a processing task.

    Possible states:
        - PENDING: Task is queued but not yet started.
        - PROCESSING: Task is actively running.
        - SUCCESS: Task finished; the result file is ready for download.
        - FAILURE: Task failed; an error message is included.
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")

    entry = tasks[task_id]
    response: dict = {"task_id": task_id, "status": entry["status"]}

    if entry["status"] == "SUCCESS":
        response["result_file"] = entry["result_file"]
    elif entry["status"] == "FAILURE":
        response["error"] = entry["error"] or "Unknown error"

    return response


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    """Serve the final mixed .wav file if the task completed successfully."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")

    entry = tasks[task_id]

    if entry["status"] != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail=f"Task is not complete yet. Current status: {entry['status']}",
        )

    output_path = Path(entry["result_file"])

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
