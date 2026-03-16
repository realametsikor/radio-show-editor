from __future__ import annotations

import logging
import os
import uuid
import json
import time
import random
import subprocess
from pathlib import Path

import aiofiles
import requests
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Set up basic logging
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

# --- CORS Configuration ---
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "https://radio-show-editor.vercel.app")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
# Keep localhost for local testing just in case
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
MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB limit

# --- Background Processing Task ---
def process_audio(task_id: str, file_path: str) -> None:
    try:
        tasks[task_id]["status"] = "PROCESSING"
        save_tasks()

        from core_audio_engine.engine import run_pipeline

        fp = Path(file_path)
        if not fp.is_file():
            raise FileNotFoundError(f"Uploaded file not found: {fp}")

        # --- THE NEW AUDIO SANITIZER ---
        logger.info("Sanitizing and normalizing audio for Pyannote...")
        clean_audio_path = fp.parent / "clean_input.wav"
        
        # This instantly converts ANY file to a perfect 16kHz Mono WAV
        subprocess.run([
            "ffmpeg", "-i", str(fp), 
            "-ar", "16000", 
            "-ac", "1", 
            str(clean_audio_path), 
            "-y"
        ], check=True)
        # -------------------------------

        output_dir = fp.parent / "output"
        output_file = fp.parent / "radio_show_final.wav"
        
        logger.info("Fetching background music from direct links...")
        music_path = str(fp.parent / "background_music.mp3")
        
        reliable_music_links = [
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
            "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"
        ]
        
        chosen_url = random.choice(reliable_music_links)
        
        music_data = requests.get(chosen_url, timeout=15).content
        with open(music_path, "wb") as f:
            f.write(music_data)

        # Notice we are passing 'clean_audio_path' to prevent AI crashes
        final_path = run_pipeline(
            raw_audio=str(clean_audio_path),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
        
        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(final_path)
        save_tasks()
        logger.info(f"Task {task_id} completed successfully!")

    except Exception as exc:
        logger.exception("Pipeline failed")
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)
        save_tasks()


# --- API Endpoints ---
@app.post("/upload")
async def upload_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Accept both audio files and video files (like .mp4)
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
        "result_file": None, 
        "error": None,
        "filename": file.filename or "Unknown Podcast",
        "timestamp": time.time()
    }
    save_tasks()
    
    background_tasks.add_task(process_audio, task_id, str(file_path.resolve()))
    return {"task_id": task_id}


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    entry = tasks[task_id]
    response = {"task_id": task_id, "status": entry["status"]}
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
        raise HTTPException(status_code=400, detail="Task not complete yet.")
    output_path = Path(entry["result_file"])
    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="Output file not found.")
    
    return FileResponse(
        path=str(output_path), 
        media_type="audio/wav", 
        filename=f"Radio_Show_{entry.get('filename', 'Final')}.wav"
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


# --- THE SECRET DEBUG WINDOW ---
@app.get("/debug")
async def debug_database():
    """Shows the raw data so we can see the hidden Python errors."""
    return tasks


# --- THE HUGGING FACE HEALTH CHECKS ---
@app.get("/health")
async def health_check():
    """A secondary health check just in case."""
    return {"status": "ok"}

@app.get("/")
async def root():
    """Hugging Face pings this exact route to see if the server is awake. 
    Without this, the Space gets stuck on 'Starting...' forever!"""
    return {"message": "Radio Show Editor API is up and running!"}
