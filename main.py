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
    version="0.4.0",
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


def set_progress(task_id: str, message: str) -> None:
    """Update task progress message."""
    if task_id in tasks:
        tasks[task_id]["progress"] = message
        logger.info("[%s] %s", task_id[:8], message)


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

    # ── Re-encode to clean WAV ─────────────────────────────────────────
    set_progress(task_id, "🔄 Re-encoding audio to clean WAV format...")
    clean_path = job_dir / "clean_upload.wav"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(original_fp),
                "-ar", "44100",
                "-ac", "1",
                "-sample_fmt", "s16",
                str(clean_path),
            ],
            check=True,
            capture_output=True,
        )
        audio_to_process = clean_path
        set_progress(task_id, "✅ Audio re-encoded successfully")
        logger.info("Re-encoded audio → %s", audio_to_process)
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "ffmpeg re-encode failed, using original: %s",
            exc.stderr.decode()
        )
        audio_to_process = original_fp

    # ── Resolve background music ───────────────────────────────────────
    set_progress(task_id, f"🎵 Fetching '{mood}' background music...")
    music_path: str | None = None

    if mood and os.environ.get("JAMENDO_CLIENT_ID"):
        try:
            fetched = fetch_music_for_mood(
                mood=mood,
                output_dir=str(job_dir),
            )
            music_path = str(fetched)
            set_progress(task_id, "✅ Background music ready")
            logger.info("Dynamic music downloaded → %s", music_path)
        except Exception as exc:
            logger.warning("Dynamic music fetch failed: %s", exc)
            set_progress(task_id, "⚠️ Music fetch failed, using default track")

    if not music_path:
        music_path = os.environ.get(
            "BACKGROUND_MUSIC_PATH",
            str(Path(__file__).resolve().parent / "assets" / "background_music.wav"),
        )
        set_progress(task_id, "✅ Using default background music")

    # ── Run full pipeline ──────────────────────────────────────────────
    try:
        set_progress(task_id, "🎙️ Loading AI speaker diarization model...")

        # Patch pipeline steps to emit live progress
        import core_audio_engine.diarize as diarize_mod
        import core_audio_engine.enhance as enhance_mod
        import core_audio_engine.sfx as sfx_mod
        import core_audio_engine.mixer as mixer_mod
        import core_audio_engine.producer as producer_mod

        _orig_diarize = diarize_mod.diarize_speakers
        _orig_enhance = enhance_mod.enhance_voice
        _orig_master = enhance_mod.master_audio
        _orig_sfx = sfx_mod.apply_sfx
        _orig_mix = mixer_mod.mix_with_ducking
        _orig_analyze = producer_mod.analyze_with_claude

        def _patched_diarize(*args, **kwargs):
            set_progress(task_id, "🎙️ Separating speakers — AI identifying voices...")
            result = _orig_diarize(*args, **kwargs)
            set_progress(task_id, "✅ Speakers separated successfully")
            return result

        def _patched_enhance(*args, **kwargs):
            set_progress(task_id, "🎚️ Enhancing voice quality — EQ & compression...")
            return _orig_enhance(*args, **kwargs)

        def _patched_master(*args, **kwargs):
            set_progress(task_id, "🏆 Mastering to broadcast standards...")
            result = _orig_master(*args, **kwargs)
            set_progress(task_id, "✅ Mastering complete")
            return result

        def _patched_analyze(*args, **kwargs):
            set_progress(task_id, "🤖 Claude AI analyzing conversation for production cues...")
            result = _orig_analyze(*args, **kwargs)
            title = result.get("show_title", "")
            set_progress(task_id, f"✅ Production plan ready: '{title}'")
            return result

        def _patched_sfx(*args, **kwargs):
            set_progress(task_id, "✨ Applying AI-directed sound effects...")
            result = _orig_sfx(*args, **kwargs)
            set_progress(task_id, "✅ Sound effects applied")
            return result

        def _patched_mix(*args, **kwargs):
            set_progress(task_id, "🎵 Mixing voices with background music...")
            result = _orig_mix(*args, **kwargs)
            set_progress(task_id, "✅ Mix complete")
            return result

        diarize_mod.diarize_speakers = _patched_diarize
        enhance_mod.enhance_voice = _patched_enhance
        enhance_mod.master_audio = _patched_master
        producer_mod.analyze_with_claude = _patched_analyze
        sfx_mod.apply_sfx = _patched_sfx
        mixer_mod.mix_with_ducking = _patched_mix

        set_progress(task_id, "🚀 Starting full production pipeline...")

        final_path = run_pipeline(
            raw_audio=str(audio_to_process),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
            mood=mood,
        )

        # Restore originals
        diarize_mod.diarize_speakers = _orig_diarize
        enhance_mod.enhance_voice = _orig_enhance
        enhance_mod.master_audio = _orig_master
        producer_mod.analyze_with_claude = _orig_analyze
        sfx_mod.apply_sfx = _orig_sfx
        mixer_mod.mix_with_ducking = _orig_mix

        set_progress(task_id, "🎉 Your radio show is ready!")
        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(final_path)
        logger.info("Pipeline complete → %s (task %s)", final_path, task_id)

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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {exc}"
        ) from exc

    logger.info("Saved upload to %s (%d bytes)", file_path, total_bytes)

    tasks[task_id] = {
        "status": "PENDING",
        "result_file": None,
        "error": None,
        "progress": "⏳ Queued, waiting to start...",
        "mood": mood,
    }

    background_tasks.add_task(
        process_audio,
        task_id,
        str(file_path.resolve()),
        mood,
    )

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")

    entry = tasks[task_id]
    response: dict = {
        "task_id": task_id,
        "status": entry["status"],
        "progress": entry.get("progress", ""),
        "mood": entry.get("mood", ""),
    }

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
            detail=f"Task not complete. Status: {entry['status']}",
        )

    output_path = Path(entry["result_file"])

    if not output_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output file not found. It may have been cleaned up.",
        )

    return FileResponse(
        path=str(output_path),
        media_type="audio/wav",
        filename="radio_show_final.wav",
    )


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.4.0"}
