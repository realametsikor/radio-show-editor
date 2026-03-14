from __future__ import annotations

import logging
import os
import subprocess
import uuid
from pathlib import Path

import aiofiles
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

tasks: dict[str, dict] = {}

app = FastAPI(
    title="Radio Show Editor API",
    description="Upload a podcast, let the pipeline process it, download the finished radio show.",
    version="0.2.0",
)

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

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def process_audio(task_id: str, file_path: str, mood: str = "") -> None:
    from core_audio_engine.engine import run_pipeline
    from core_audio_engine.music_fetch import fetch_music_for_mood

    tasks[task_id]["status"] = "PROCESSING"

    original_fp = Path(file_path)
    if not original_fp.is_file():
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = f"Uploaded file not found: {original_fp}"
        return

    job_dir = original_fp.parent
    output_dir = job_dir / "output"
    output_file = job_dir / "radio_show_final.wav"

    # Re-encode to clean 44100Hz mono WAV to fix sample mismatches
    clean_path = job_dir / "clean_upload.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(original_fp),
             "-ar", "44100", "-ac", "1", "-sample_fmt", "s16",
             str(clean_path)],
            check=True,
            capture_output=True,
        )
        audio_to_process = clean_path
        logger.info("Re-encoded audio → %s", audio_to_process)
    except subprocess.CalledProcessError as exc:
        logger.warning("ffmpeg re-encode failed, using original: %s", exc.stderr.decode())
        audio_to_process = original_fp

    # Resolve background music
    music_path: str | None = None

    if mood and os.environ.get("JAMENDO_CLIENT_ID"):
        try:
            fetched = fetch_music_for_mood(mood=mood, output_dir=str(job_dir))
            music_path = str(fetched)
        except Exception as exc:
            logger.warning("Dynamic music fetch failed: %s", exc)

    if not music_path:
        music_path = os.environ.get(
            "BACKGROUND_MUSIC_PATH",
            str(Path(__file__).resolve().parent / "assets" / "background_music.wav"),
        )

    try:
        final_path = run_pipeline(
            raw_audio=str(audio_to_process),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(final_path)
    except Exception as exc:
        logger.exception("Pipeline failed for task %s", task_id)
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)


@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mood: str = Form(""),
):
    if file.content_type and not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"Expected an audio file, got '{file.content_type}'.",
        )

    task_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / task_id
    job_dir.mkdir(parents=True, exist_ok=True)

    safe_name = file.filename or "upload.wav"
    file_path = job_dir / safe_name

    total_bytes = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
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

    tasks[task_id] = {"status": "PENDING", "result_file": None, "error": None}
    background_tasks.add_task(process_audio, task_id, str(file_path.resolve()), mood)

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
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
    return {"status": "ok"}
