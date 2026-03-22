from __future__ import annotations

import logging
import os
import uuid
import json
import time
import subprocess
import gc
import shutil
from pathlib import Path

import aiofiles
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TASKS_FILE = Path("tasks_db.json")

def load_tasks() -> dict:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text())
        except Exception:
            return {}
    return {}

tasks: dict[str, dict] = load_tasks()

def save_tasks():
    try:
        TASKS_FILE.write_text(json.dumps(tasks))
    except Exception as e:
        logger.error(f"Failed to save tasks: {e}")

app = FastAPI(title="Radio Show Editor API")

_raw_origins = os.environ.get("ALLOWED_ORIGINS", "https://radio-show-editor.vercel.app")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
if "http://localhost:3000" not in _origins:
    _origins.append("http://localhost:3000")

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

def process_audio(task_id: str, file_path: str, mood: str) -> None:
    
    def update_progress(msg: str):
        logger.info(msg)
        tasks[task_id]["message"] = msg
        save_tasks()

    try:
        tasks[task_id]["status"] = "PROCESSING"
        update_progress("Initializing audio engine...")

        from core_audio_engine.engine import run_pipeline
        from core_audio_engine.music_fetch import build_music_track

        fp = Path(file_path)
        if not fp.is_file():
            raise FileNotFoundError(f"Uploaded file not found: {fp}")

        update_progress("Sanitizing audio and preparing tracks...")
        clean_audio_path = fp.parent / "clean_input.wav"
        
        try:
            voice_segment = AudioSegment.from_file(str(fp))
            voice_segment = voice_segment.set_frame_rate(16000).set_channels(1)
            voice_segment.export(str(clean_audio_path), format="wav")
        except Exception as e:
            logger.error(f"Failed to prepare audio: {e}")
            raise RuntimeError(f"Could not read uploaded audio file: {e}")
        
        output_dir = fp.parent / "output"
        output_file = fp.parent / "radio_show_final.wav"
        music_path = fp.parent / "background_music.mp3"
        
        update_progress(f"Curating professional background playlist for vibe: {mood}...")
        build_music_track(mood=mood, output_path=str(music_path), work_dir=fp.parent)

        update_progress("Running Claude AI & Pyannote Engine (This takes the longest)...")
        final_path = run_pipeline(
            raw_audio=str(clean_audio_path),
            music_path=str(music_path),
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
            mood=mood
        )
        
        update_progress("Applying Premium Podcast Mastering (Glue & Limiter)...")
        mastered_output = fp.parent / "radio_show_mastered.wav"
        
        premium_master_filter = (
            "acompressor=threshold=-24dB:ratio=1.5:attack=15:release=50:makeup=2dB,"
            "alimiter=limit=-1.0dB"
        )
        
        subprocess.run([
            "ffmpeg", "-i", str(final_path), 
            "-af", premium_master_filter, 
            "-ar", "44100", "-ac", "2", 
            str(mastered_output), "-y"
        ], check=True)

        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(mastered_output) 
        update_progress("Mix complete! Your professional podcast is ready.")

    except Exception as exc:
        logger.exception("Pipeline failed")
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)
        tasks[task_id]["message"] = f"Error: {str(exc)}"
        save_tasks()

@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    mood: str = Form("lo-fi")
):
    if file.content_type and not file.content_type.startswith(("audio/", "video/")):
        raise HTTPException(status_code=400, detail="Expected an audio or video file.")

    task_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / task_id
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / (file.filename or "upload.wav")

    total_bytes = 0
    try:
        async with aiofiles.open(file_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File too large.")
                await out.write(chunk)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")

    tasks[task_id] = {
        "task_id": task_id,
        "status": "PENDING", 
        "message": "Upload complete. Entering processing queue...",
        "result_file": None, 
        "error": None,
        "filename": file.filename or "Unknown Podcast",
        "timestamp": time.time()
    }
    save_tasks()
    
    background_tasks.add_task(process_audio, task_id, str(file_path.resolve()), mood)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    entry = tasks[task_id]
    
    response = {
        "task_id": task_id, 
        "status": entry["status"],
        "message": entry.get("message", "Processing...")
    }
    
    if entry["status"] == "SUCCESS":
        response["result_file"] = entry["result_file"]
    elif entry["status"] == "FAILURE":
        response["error"] = entry["error"] or "Unknown error"
    return response

@app.get("/download/{task_id}")
async def download_result(task_id: str, format: str = "wav"):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    entry = tasks[task_id]
    if entry["status"] != "SUCCESS":
        raise HTTPException(status_code=400, detail="Task not complete yet.")
    
    output_path = Path(entry["result_file"])
    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found.")
    
    safe_filename = entry.get("filename", "Final").replace(".mp4", "").replace(".wav", "").replace(".m4a", "").replace(".mp3", "")
    
    if format.lower() == "mp3":
        mp3_path = output_path.with_suffix(".mp3")
        
        if not mp3_path.exists():
            logger.info(f"Compressing {task_id} to MP3...")
            subprocess.run([
                "ffmpeg", "-i", str(output_path),
                "-vn", "-ar", "44100", "-ac", "2", "-b:a", "128k",
                str(mp3_path), "-y"
            ], check=True)
            
        return FileResponse(
            path=str(mp3_path), 
            media_type="audio/mpeg", 
            filename=f"Radio_Show_{safe_filename}.mp3"
        )
        
    return FileResponse(
        path=str(output_path), 
        media_type="audio/wav", 
        filename=f"Radio_Show_{safe_filename}.wav"
    )

@app.get("/recent")
async def get_recent_shows():
    successful_shows = []
    sorted_tasks = sorted(tasks.values(), key=lambda x: x.get("timestamp", 0), reverse=True)
    
    for t in sorted_tasks:
        if t["status"] == "SUCCESS":
            successful_shows.append({
                "filename": t.get("filename", "Unknown Podcast"),
                "task_id": t["task_id"],
                "download_link": f"/download/{t['task_id']}",
                "time_processed": time.ctime(t.get("timestamp", time.time()))
            })
            
    return {"recent_shows": successful_shows}

# =========================================================================
# 🗑️ NEW DELETE ENDPOINT
# Safely removes the task from the database and deletes the massive audio 
# files from the Hugging Face server.
# =========================================================================
@app.delete("/delete/{task_id}")
async def delete_task(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    
    # 1. Remove from database
    del tasks[task_id]
    save_tasks()
    
    # 2. Wipe the physical folder to save disk space
    job_dir = UPLOAD_DIR / task_id
    if job_dir.exists():
        try:
            shutil.rmtree(job_dir, ignore_errors=True)
            logger.info(f"Successfully deleted files for task: {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete directory for {task_id}: {e}")
            
    return {"message": "Show deleted successfully", "task_id": task_id}

@app.get("/debug")
async def debug_database():
    return tasks

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Radio Show Editor API is up and running!"}
