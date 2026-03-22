from __future__ import annotations

import logging
import os
import uuid
import json
import time
import subprocess
import gc
import shutil
import requests
from pathlib import Path
from typing import Optional, List

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

def fetch_builtin_intro(selection: str, work_dir: Path) -> Path | None:
    intro_map = {
        "documentary": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3",
        "energetic": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3",
        "ethereal": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-10.mp3"
    }
    
    if selection not in intro_map:
        return None
        
    out_path = work_dir / f"builtin_intro_{selection}.mp3"
    try:
        res = requests.get(intro_map[selection], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        res.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(res.content)
            
        seg = AudioSegment.from_file(str(out_path))
        seg = seg[:6000].fade_out(1500)
        seg.export(str(out_path), format="mp3")
        return out_path
    except Exception as e:
        logger.warning(f"Failed to fetch builtin intro: {e}")
        return None

def process_audio(task_id: str, file_path: str, mood: str, intro_selection: str, custom_intro_path: str | None) -> None:
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
        
        update_progress("Sanitizing audio and preparing tracks...")
        clean_audio_path = fp.parent / "clean_input.wav"
        
        try:
            voice_segment = AudioSegment.from_file(str(fp))
            voice_segment = voice_segment.set_frame_rate(16000).set_channels(1)
            voice_segment.export(str(clean_audio_path), format="wav")
        except Exception as e:
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
        
        if intro_selection != "none":
            update_progress("Attaching Custom/Built-in Intro...")
            try:
                final_mix = AudioSegment.from_wav(str(final_path))
                intro_audio = None
                
                if intro_selection == "custom" and custom_intro_path and Path(custom_intro_path).exists():
                    intro_audio = AudioSegment.from_file(custom_intro_path)
                else:
                    fetched_path = fetch_builtin_intro(intro_selection, fp.parent)
                    if fetched_path:
                        intro_audio = AudioSegment.from_file(str(fetched_path))
                        
                if intro_audio:
                    intro_audio = intro_audio.set_frame_rate(final_mix.frame_rate).set_channels(final_mix.channels)
                    crossfade_ms = min(1500, len(intro_audio))
                    if len(intro_audio) > crossfade_ms:
                        final_mix = intro_audio.append(final_mix, crossfade=crossfade_ms)
                    else:
                        final_mix = intro_audio + final_mix
                        
                    final_mix.export(str(final_path), format="wav")
                    update_progress("✅ Intro successfully attached!")
            except Exception as e:
                logger.warning(f"Failed to attach intro, skipping: {e}")

        # =====================================================================
        # 🎛️ TRANSPARENT MASTERING
        # Uses a clean limiter so the 'Goldilocks' volume fader is respected!
        # =====================================================================
        update_progress("Applying Final Transparent Mastering...")
        mastered_output = fp.parent / "radio_show_mastered.wav"
        
        transparent_master_filter = "alimiter=limit=-1.0dB"
        
        subprocess.run([
            "ffmpeg", "-i", str(final_path), 
            "-af", transparent_master_filter, 
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

# =========================================================================
# 🎛️ MULTI-FILE UPLOAD ENDPOINT (UNLOCKED FORMATS)
# Bypasses strict browser MIME type limits so .m4a, .aac, etc. don't fail.
# =========================================================================
@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks, 
    files: List[UploadFile] = File(...),
    mood: str = Form("documentary"),
    intro_selection: str = Form("none"),
    custom_intro: Optional[UploadFile] = File(None)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    task_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / task_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Stitch multiple audio files together
    file_path = job_dir / "upload_combined.wav"
    try:
        combined_audio = AudioSegment.empty()
        first_filename = files[0].filename or "Podcast"
        
        for f in files:
            temp_path = job_dir / (f.filename or f"temp_{uuid.uuid4().hex}.wav")
            async with aiofiles.open(temp_path, "wb") as out:
                while chunk := await f.read(1024 * 1024):
                    await out.write(chunk)
            
            # Let PyDub natively decode the format (.mp3, .m4a, .ogg, etc.)
            seg = AudioSegment.from_file(str(temp_path))
            combined_audio += seg
            
            # Delete the temp part to save space
            temp_path.unlink(missing_ok=True)
            
        combined_audio.export(str(file_path), format="wav")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read or combine audio files: Make sure they are valid media files. Error: {exc}")

    # 2. Save Custom Intro (if uploaded)
    custom_intro_path = None
    if intro_selection == "custom" and custom_intro is not None:
        custom_intro_path = job_dir / (custom_intro.filename or "custom_intro.wav")
        try:
            async with aiofiles.open(custom_intro_path, "wb") as out:
                while chunk := await custom_intro.read(1024 * 1024):
                    await out.write(chunk)
        except Exception as exc:
            logger.warning(f"Failed to save custom intro: {exc}")

    tasks[task_id] = {
        "task_id": task_id,
        "status": "PENDING", 
        "message": "Upload complete. Stitching audio and entering queue...",
        "result_file": None, 
        "error": None,
        "filename": first_filename,
        "timestamp": time.time()
    }
    save_tasks()
    
    background_tasks.add_task(process_audio, task_id, str(file_path.resolve()), mood, intro_selection, str(custom_intro_path) if custom_intro_path else None)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found.")
    entry = tasks[task_id]
    response = {"task_id": task_id, "status": entry["status"], "message": entry.get("message", "Processing...")}
    if entry["status"] == "SUCCESS":
        response["result_file"] = entry["result_file"]
    elif entry["status"] == "FAILURE":
        response["error"] = entry["error"] or "Unknown error"
    return response

@app.get("/download/{task_id}")
async def download_result(task_id: str, format: str = "wav"):
    entry = tasks.get(task_id)
    if not entry or entry["status"] != "SUCCESS":
        raise HTTPException(status_code=404, detail="Task not found or incomplete.")
    
    output_path = Path(entry["result_file"])
    safe_filename = entry.get("filename", "Final").replace(".mp4", "").replace(".wav", "").replace(".m4a", "").replace(".mp3", "")
    
    if format.lower() == "mp3":
        mp3_path = output_path.with_suffix(".mp3")
        if not mp3_path.exists():
            subprocess.run(["ffmpeg", "-i", str(output_path), "-vn", "-ar", "44100", "-ac", "2", "-b:a", "128k", str(mp3_path), "-y"], check=True)
        return FileResponse(path=str(mp3_path), media_type="audio/mpeg", filename=f"Radio_Show_{safe_filename}.mp3")
        
    return FileResponse(path=str(output_path), media_type="audio/wav", filename=f"Radio_Show_{safe_filename}.wav")

@app.get("/recent")
async def get_recent_shows():
    successful_shows = [{"filename": t.get("filename", "Unknown Podcast"), "task_id": t["task_id"], "download_link": f"/download/{t['task_id']}", "time_processed": time.ctime(t.get("timestamp", time.time()))} for t in sorted(tasks.values(), key=lambda x: x.get("timestamp", 0), reverse=True) if t["status"] == "SUCCESS"]
    return {"recent_shows": successful_shows}

@app.delete("/delete/{task_id}")
async def delete_task(task_id: str):
    if task_id in tasks:
        del tasks[task_id]
        save_tasks()
    job_dir = UPLOAD_DIR / task_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    return {"message": "Show deleted successfully"}
