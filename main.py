from __future__ import annotations

import json
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

# ---------------------------------------------------------------------------
# Persistent task storage
# ---------------------------------------------------------------------------
TASKS_DIR = Path("tasks")
TASKS_DIR.mkdir(parents=True, exist_ok=True)


def _task_file(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def save_task(task_id: str, data: dict) -> None:
    try:
        _task_file(task_id).write_text(json.dumps(data))
    except Exception as exc:
        logger.warning("Failed to save task %s: %s", task_id, exc)


def load_task(task_id: str) -> dict | None:
    try:
        f = _task_file(task_id)
        if f.is_file():
            return json.loads(f.read_text())
    except Exception as exc:
        logger.warning("Failed to load task %s: %s", task_id, exc)
    return None


def update_task(task_id: str, **kwargs) -> None:
    task = load_task(task_id) or {}
    task.update(kwargs)
    save_task(task_id, task)


def set_progress(task_id: str, message: str) -> None:
    update_task(task_id, progress=message)
    logger.info("[%s] %s", task_id[:8], message)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Radio Show Editor API",
    description="Upload a podcast, process it, download the finished radio show.",
    version="0.6.0",
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

ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "video/mp4",
    "application/octet-stream",
}

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".mp4", ".m4a", ".aac", ".ogg"}


# ---------------------------------------------------------------------------
# Background processing
# ---------------------------------------------------------------------------
def process_audio(task_id: str, file_path: str, mood: str = "") -> None:
    from core_audio_engine.engine import run_pipeline
    from core_audio_engine.music_fetch import fetch_music_for_mood

    update_task(task_id, status="PROCESSING")

    original_fp = Path(file_path)
    if not original_fp.is_file():
        update_task(
            task_id,
            status="FAILURE",
            error="Uploaded file not found: " + str(original_fp),
        )
        return

    job_dir     = original_fp.parent
    output_dir  = job_dir / "output"
    output_file = job_dir / "radio_show_final.wav"

    # Re-encode to clean WAV
    set_progress(task_id, "🔄 Re-encoding audio to clean WAV format...")
    clean_path = job_dir / "clean_upload.wav"
    try:
        if original_fp.suffix.lower() == ".wav" and clean_path.is_file():
            audio_to_process = original_fp
            set_progress(task_id, "✅ Audio already clean, skipping re-encode")
        else:
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
    except subprocess.CalledProcessError as exc:
        logger.warning("ffmpeg re-encode failed: %s", exc.stderr.decode())
        audio_to_process = original_fp

    # Resolve background music
    set_progress(task_id, "🎵 Fetching background music for mood: " + mood)
    music_path = None

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
            logger.warning("Music fetch failed: %s", exc)
            set_progress(task_id, "⚠️ Music fetch failed, using default track")

    if not music_path:
        music_path = os.environ.get(
            "BACKGROUND_MUSIC_PATH",
            str(Path(__file__).resolve().parent / "assets" / "background_music.wav"),
        )
        set_progress(task_id, "✅ Using default background music")

    # Run pipeline with progress patches
    try:
        set_progress(task_id, "🎙️ Loading AI speaker diarization model...")

        import core_audio_engine.diarize  as diarize_mod
        import core_audio_engine.enhance  as enhance_mod
        import core_audio_engine.sfx      as sfx_mod
        import core_audio_engine.mixer    as mixer_mod
        import core_audio_engine.producer as producer_mod

        _orig_diarize = diarize_mod.diarize_speakers
        _orig_enhance = enhance_mod.enhance_voice
        _orig_master  = enhance_mod.master_audio
        _orig_sfx     = sfx_mod.apply_sfx
        _orig_mix     = mixer_mod.mix_with_ducking
        _orig_analyze = producer_mod.analyze_with_claude

        def _patched_diarize(*a, **kw):
            set_progress(task_id, "🎙️ Separating speakers — AI identifying voices...")
            r = _orig_diarize(*a, **kw)
            set_progress(task_id, "✅ Speakers separated successfully")
            return r

        def _patched_enhance(*a, **kw):
            set_progress(task_id, "🎚️ Enhancing voice quality — EQ and compression...")
            return _orig_enhance(*a, **kw)

        def _patched_master(*a, **kw):
            set_progress(task_id, "🏆 Mastering to broadcast standards...")
            r = _orig_master(*a, **kw)
            set_progress(task_id, "✅ Mastering complete")
            return r

        def _patched_analyze(*a, **kw):
            set_progress(task_id, "🤖 Claude AI analyzing conversation...")
            r = _orig_analyze(*a, **kw)
            title = r.get("show_title", "")
            set_progress(task_id, "✅ Production plan ready: " + title)
            update_task(
                task_id,
                show_title=r.get("show_title", ""),
                show_tagline=r.get("show_tagline", ""),
                show_summary=r.get("show_summary", ""),
                keywords=r.get("keywords", []),
                segments=r.get("segments", []),
                highlights=r.get("highlights", []),
                production_notes=r.get("production_notes", ""),
            )
            return r

        def _patched_sfx(*a, **kw):
            set_progress(task_id, "✨ Applying AI-directed sound effects...")
            r = _orig_sfx(*a, **kw)
            set_progress(task_id, "✅ Sound effects applied")
            return r

        def _patched_mix(*a, **kw):
            set_progress(task_id, "🎵 Mixing voices with background music...")
            r = _orig_mix(*a, **kw)
            set_progress(task_id, "✅ Mix complete")
            return r

        diarize_mod.diarize_speakers     = _patched_diarize
        enhance_mod.enhance_voice        = _patched_enhance
        enhance_mod.master_audio         = _patched_master
        producer_mod.analyze_with_claude = _patched_analyze
        sfx_mod.apply_sfx                = _patched_sfx
        mixer_mod.mix_with_ducking       = _patched_mix

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
        diarize_mod.diarize_speakers     = _orig_diarize
        enhance_mod.enhance_voice        = _orig_enhance
        enhance_mod.master_audio         = _orig_master
        producer_mod.analyze_with_claude = _orig_analyze
        sfx_mod.apply_sfx                = _orig_sfx
        mixer_mod.mix_with_ducking       = _orig_mix

        # Convert WAV to MP3
        set_progress(task_id, "🎵 Converting to MP3...")
        mp3_path    = Path(str(final_path)).with_suffix(".mp3")
        result_file = str(final_path)

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(final_path),
                    "-codec:a", "libmp3lame",
                    "-qscale:a", "2",
                    str(mp3_path),
                ],
                check=True,
                capture_output=True,
            )
            result_file = str(mp3_path)
            set_progress(task_id, "✅ MP3 conversion complete")
            logger.info("Converted to MP3 → %s", mp3_path)
        except subprocess.CalledProcessError as exc:
            logger.warning("MP3 conversion failed: %s", exc.stderr.decode())

        # Save duration
        try:
            from pydub import AudioSegment as _AS
            _audio     = _AS.from_file(result_file)
            duration_s = len(_audio) / 1000.0
            update_task(task_id, duration=duration_s)
        except Exception:
            pass

        set_progress(task_id, "🎉 Your radio show is ready!")
        update_task(
            task_id,
            status="SUCCESS",
            result_file=result_file,
            wav_file=str(final_path),
            progress="🎉 Your radio show is ready!",
        )
        logger.info("Pipeline complete → %s (task %s)", result_file, task_id)

    except Exception as exc:
        logger.exception("Pipeline failed for task %s", task_id)
        try:
            diarize_mod.diarize_speakers     = _orig_diarize
            enhance_mod.enhance_voice        = _orig_enhance
            enhance_mod.master_audio         = _orig_master
            producer_mod.analyze_with_claude = _orig_analyze
            sfx_mod.apply_sfx                = _orig_sfx
            mixer_mod.mix_with_ducking       = _orig_mix
        except Exception:
            pass
        update_task(
            task_id,
            status="FAILURE",
            error=str(exc),
            progress="❌ Failed: " + str(exc)[:100],
        )


# ---------------------------------------------------------------------------
# Startup: mark interrupted tasks as failed
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def resume_interrupted_tasks():
    resumed = 0
    for task_file in TASKS_DIR.glob("*.json"):
        try:
            data = json.loads(task_file.read_text())
            if data.get("status") == "PROCESSING":
                data["status"]   = "FAILURE"
                data["error"]    = "Server restarted during processing. Please resubmit your file."
                data["progress"] = "❌ Server restarted — please resubmit"
                task_file.write_text(json.dumps(data))
                resumed += 1
        except Exception:
            pass
    if resumed:
        logger.info("Marked %d interrupted tasks as failed", resumed)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mood: str = Form(""),
):
    filename = file.filename or ""
    ext      = Path(filename).suffix.lower()

    content_type_ok = (
        not file.content_type
        or file.content_type in ALLOWED_CONTENT_TYPES
        or file.content_type.startswith("audio/")
    )
    extension_ok = ext in ALLOWED_EXTENSIONS or ext == ""

    if not content_type_ok and not extension_ok:
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Please upload WAV, MP3, MP4, M4A or AAC.",
        )

    task_id  = uuid.uuid4().hex
    job_dir  = UPLOAD_DIR / task_id
    job_dir.mkdir(parents=True, exist_ok=True)

    safe_name = filename or "upload.wav"
    file_path = job_dir / safe_name

    total_bytes = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="File too large. Max size is 500 MB.",
                    )
                await out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to save file: " + str(exc),
        ) from exc

    logger.info("Saved upload to %s (%d bytes)", file_path, total_bytes)

    save_task(task_id, {
        "status":           "PENDING",
        "result_file":      None,
        "wav_file":         None,
        "error":            None,
        "progress":         "⏳ Queued, waiting to start...",
        "mood":             mood,
        "file_path":        str(file_path.resolve()),
        "show_title":       "",
        "show_tagline":     "",
        "show_summary":     "",
        "keywords":         [],
        "segments":         [],
        "highlights":       [],
        "production_notes": "",
        "duration":         0,
    })

    background_tasks.add_task(
        process_audio,
        task_id,
        str(file_path.resolve()),
        mood,
    )

    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    response = {
        "task_id":  task_id,
        "status":   task.get("status", "UNKNOWN"),
        "progress": task.get("progress", ""),
        "mood":     task.get("mood", ""),
    }

    if task.get("status") == "SUCCESS":
        response["result_file"] = task.get("result_file")
    elif task.get("status") == "FAILURE":
        response["error"] = task.get("error") or "Unknown error"

    return response


@app.get("/metadata/{task_id}")
async def get_metadata(task_id: str):
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not complete.")

    return {
        "show_title":       task.get("show_title",       "Your Radio Show"),
        "show_tagline":     task.get("show_tagline",     ""),
        "show_summary":     task.get("show_summary",     ""),
        "keywords":         task.get("keywords",         []),
        "segments":         task.get("segments",         []),
        "highlights":       task.get("highlights",       []),
        "production_notes": task.get("production_notes", ""),
        "mood":             task.get("mood",             ""),
        "duration":         task.get("duration",         0),
    }


@app.get("/download/{task_id}")
async def download_result(task_id: str):
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("status") != "SUCCESS":
        raise HTTPException(
            status_code=400,
            detail="Task not complete. Status: " + str(task.get("status")),
        )

    output_path = Path(task.get("result_file") or "")

    if not output_path.is_file():
        for candidate in [
            Path(task.get("wav_file") or ""),
            Path(task.get("file_path") or "").parent / "radio_show_final.mp3",
            Path(task.get("file_path") or "").parent / "radio_show_final.wav",
        ]:
            if candidate and candidate.is_file():
                output_path = candidate
                break

    if not output_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Output file not found. Please reprocess.",
        )

    media_type = "audio/mpeg" if output_path.suffix == ".mp3" else "audio/wav"
    filename   = "radio_show_final.mp3" if output_path.suffix == ".mp3" else "radio_show_final.wav"

    return FileResponse(
        path=str(output_path),
        media_type=media_type,
        filename=filename,
    )


@app.get("/download/{task_id}/{format}")
async def download_result_format(task_id: str, format: str):
    task = load_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not complete.")

    wav_path = Path(task.get("wav_file") or "")
    if not wav_path.is_file():
        fp = Path(task.get("file_path") or "")
        wav_path = fp.parent / "radio_show_final.wav"
    if not wav_path.is_file():
        wav_path = Path(task.get("result_file") or "")
    if not wav_path.is_file():
        raise HTTPException(status_code=404, detail="Source file not found.")

    if format == "wav":
        return FileResponse(
            path=str(wav_path),
            media_type="audio/wav",
            filename="radio_show_final.wav",
        )

    format_map = {
        "mp3_high": ("-b:a", "320k", "radio_show_final_320kbps.mp3"),
        "mp3_low":  ("-b:a", "96k",  "radio_show_final_96kbps.mp3"),
        "mp3":      ("-qscale:a", "2", "radio_show_final.mp3"),
    }

    if format not in format_map:
        raise HTTPException(
            status_code=400,
            detail="Unknown format: " + format,
        )

    flag, value, out_filename = format_map[format]
    out_path = wav_path.parent / out_filename

    if not out_path.is_file():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            flag, value,
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        except subprocess.CalledProcessError as exc:
            raise HTTPException(
                status_code=500,
                detail="Conversion failed: " + exc.stderr.decode(),
            )

    return FileResponse(
        path=str(out_path),
        media_type="audio/mpeg",
        filename=out_filename,
    )


@app.get("/health")
async def health_check():
    total = pending = processing = success = failed = 0
    for f in TASKS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            total += 1
            s = data.get("status", "")
            if s == "PENDING":
                pending += 1
            elif s == "PROCESSING":
                processing += 1
            elif s == "SUCCESS":
                success += 1
            elif s == "FAILURE":
                failed += 1
        except Exception:
            pass

    return {
        "status":  "ok",
        "version": "0.6.0",
        "tasks": {
            "total":      total,
            "pending":    pending,
            "processing": processing,
            "success":    success,
            "failed":     failed,
        },
    }
