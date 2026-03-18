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
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydub import AudioSegment
import gc

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

# =========================================================================
# 🎵 THE BULLETPROOF SOUNDHELIX LIBRARY 
# =========================================================================

SH_GENRES = ["Electronic","Lo-Fi","Jazz","Cinematic","Ambient","Funk","Electronic","Dramatic","Chill","Electronic","Atmospheric","Funk","Minimal","Tense","Upbeat","Electronic","Ambient"]
SH_MOODS = ["Energetic","Relaxed","Groovy","Mysterious","Dreamy","Groovy","Happy","Dramatic","Chill","Focused","Atmospheric","Funky","Minimal","Tense","Uplifting","Driving","Dreamy"]

ALL_TRACKS = []
for i in range(17):
    ALL_TRACKS.append({
        "genre": SH_GENRES[i], 
        "mood": SH_MOODS[i], 
        "url": f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{i+1}.mp3"
    })

VIBE_MAPPER = {
    "lo-fi": ["Lo-Fi", "Chill", "Focused", "Relaxed"],
    "upbeat": ["Energetic", "Happy", "Upbeat", "Driving"],
    "ambient": ["Ambient", "Atmospheric", "Dreamy"],
    "jazz": ["Jazz", "Groovy"],
    "cinematic": ["Cinematic", "Dramatic", "Tense"],
    "acoustic": ["Relaxed", "Chill", "Minimal"], 
    "electronic": ["Electronic"],
    "hiphop": ["Groovy", "Funky", "Funk"], 
    "gospel": ["Uplifting", "Happy"], 
    "afrobeats": ["Groovy", "Energetic", "Funk"],
    "rnb": ["Groovy", "Chill", "Relaxed"],
    "reggae": ["Funk", "Happy", "Relaxed"],
    "classical": ["Cinematic", "Dramatic", "Minimal"],
    "country": ["Happy", "Relaxed", "Upbeat"],
    "latin": ["Groovy", "Energetic"],
    "news": ["Focused", "Minimal", "Electronic"],
    "morning_drive": ["Energetic", "Upbeat", "Driving"],
    "comedy": ["Happy", "Funk", "Funky"],
    "true_crime": ["Mysterious", "Tense", "Dramatic"],
    "tech": ["Electronic", "Focused", "Minimal"],
    "sports": ["Energetic", "Driving"],
    "war": ["Dramatic", "Tense", "Cinematic"],
    "documentary": ["Ambient", "Focused", "Mysterious"],
    "talk_show": ["Jazz", "Groovy", "Relaxed"],
    "business": ["Focused", "Uplifting", "Minimal"],
    "spiritual": ["Ambient", "Relaxed", "Dreamy"],
    "horror": ["Mysterious", "Tense"],
    "kids": ["Happy", "Upbeat"],
    "romance": ["Dreamy", "Chill", "Relaxed"],
    "science": ["Electronic", "Ambient", "Focused", "Atmospheric"]
}

# --- Background Processing Task ---
def process_audio(task_id: str, file_path: str, mood: str) -> None:
    try:
        tasks[task_id]["status"] = "PROCESSING"
        save_tasks()

        from core_audio_engine.engine import run_pipeline

        fp = Path(file_path)
        if not fp.is_file():
            raise FileNotFoundError(f"Uploaded file not found: {fp}")

        # =========================================================================
        # 🎙️ STUDIO REVERB: Removing the "Dry AI" Sound
        # =========================================================================
        logger.info("Sanitizing and adding Live Studio Reverb to voices...")
        clean_audio_path = fp.parent / "clean_input.wav"
        
        # A 20ms delay acts as a "slapback" reflection from a studio window.
        # It's subtle (0.15 volume) so it doesn't sound like a bathroom.
        studio_room_filter = "aecho=1.0:0.15:20:0.1"
        
        subprocess.run([
            "ffmpeg", "-i", str(fp), 
            "-af", studio_room_filter, 
            "-ar", "16000", "-ac", "1", 
            str(clean_audio_path), "-y"
        ], check=True)
        # =========================================================================
        
        output_dir = fp.parent / "output"
        output_file = fp.parent / "radio_show_final.wav"
        
        logger.info(f"Building a dynamic playlist from SoundHelix for vibe: {mood}")
        music_path = str(fp.parent / "background_music.mp3")
        
        target_tags = VIBE_MAPPER.get(mood, ["Chill", "Ambient", "Lo-Fi"])
        
        matching_tracks = [
            t["url"] for t in ALL_TRACKS 
            if t["genre"] in target_tags or t["mood"] in target_tags
        ]
        
        if len(matching_tracks) < 3:
            logger.info("Not enough exact matches found. Supplementing with safe fallbacks...")
            fallback_tracks = [t["url"] for t in ALL_TRACKS]
            random.shuffle(fallback_tracks)
            matching_tracks.extend(fallback_tracks[:3])
            
        unique_tracks = list(set(matching_tracks))
        random.shuffle(unique_tracks)
        urls_to_fetch = unique_tracks[:3]
        
        master_playlist = AudioSegment.empty()
        
        browser_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "audio/mpeg, audio/mp3, */*"
        }
        
        # DOWNLOAD THE MUSIC MEDLEY
        for i, url in enumerate(urls_to_fetch):
            try:
                temp_mp3 = fp.parent / f"temp_music_{i}.mp3"
                logger.info(f"Downloading track {i+1} ({url})...")
                
                res = requests.get(url, headers=browser_headers, timeout=20)
                res.raise_for_status() 
                music_data = res.content
                
                with open(temp_mp3, "wb") as f:
                    f.write(music_data)
                
                segment = AudioSegment.from_file(str(temp_mp3))
                
                if len(master_playlist) == 0:
                    master_playlist = segment
                else:
                    crossfade_time = min(3000, len(master_playlist), len(segment))
                    master_playlist = master_playlist.append(segment, crossfade=crossfade_time)
                    
                temp_mp3.unlink() 
            except Exception as e:
                logger.warning(f"Failed to fetch track {url}: {e}")
                
        if len(master_playlist) == 0:
             logger.warning("All music downloads failed! Creating a silent backing track...")
             master_playlist = AudioSegment.silent(duration=60000)
        else:
             logger.info("Looping the playlist so it covers long podcasts...")
             master_playlist = master_playlist * 8

        # THE ATMOSPHERE & TEXTURE LAYER 
        ATMOSPHERE_URLS = {
            "vinyl": "https://ia800305.us.archive.org/30/items/vinyl-crackle/vinyl-crackle.mp3",
            "rain": "https://ia801602.us.archive.org/15/items/rain-noise/rain-noise.mp3"
        }

        atmosphere_type = None
        if mood in ["lo-fi", "jazz", "acoustic", "talk_show"]:
            atmosphere_type = "vinyl"
        elif mood in ["true_crime", "horror", "documentary", "war", "ambient"]:
            atmosphere_type = "rain"

        if atmosphere_type:
            logger.info(f"Applying physical texture: {atmosphere_type}...")
            try:
                atmo_url = ATMOSPHERE_URLS[atmosphere_type]
                atmo_res = requests.get(atmo_url, headers=browser_headers, timeout=15)
                
                if atmo_res.status_code == 200:
                    temp_atmo = fp.parent / "temp_atmo.mp3"
                    with open(temp_atmo, "wb") as f:
                        f.write(atmo_res.content)
                        
                    atmo_segment = AudioSegment.from_file(str(temp_atmo))
                    atmo_segment = atmo_segment - 22 
                    needed_loops = (len(master_playlist) // len(atmo_segment)) + 1
                    atmo_segment = atmo_segment * needed_loops
                    atmo_segment = atmo_segment[:len(master_playlist)] 
                    master_playlist = master_playlist.overlay(atmo_segment)
                    temp_atmo.unlink()
            except Exception as e:
                logger.warning(f"Failed to apply atmosphere layer, continuing with clean music: {e}")

        logger.info("Exporting the final Medley track...")
        master_playlist.export(music_path, format="mp3")
        del master_playlist
        gc.collect()

        # --- RUN THE AI PIPELINE ---
        final_path = run_pipeline(
            raw_audio=str(clean_audio_path),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
        
        # --- FM BROADCAST MASTERING CHAIN ---
        logger.info("Applying FM Broadcast Mastering Chain (Bass, Treble, Comp, Limiter)...")
        mastered_output = fp.parent / "radio_show_mastered.wav"
        
        fm_eq_filter = (
            "bass=g=5:f=100:w=0.5,"                 
            "treble=g=4:f=8000:w=0.5,"              
            "acompressor=threshold=-21dB:ratio=4:attack=5:release=50:makeup=5dB," 
            "alimiter=limit=-1dB"                   
        )
        
        subprocess.run([
            "ffmpeg", "-i", str(final_path), 
            "-af", fm_eq_filter, 
            "-ar", "44100", "-ac", "2", 
            str(mastered_output), "-y"
        ], check=True)

        tasks[task_id]["status"] = "SUCCESS"
        tasks[task_id]["result_file"] = str(mastered_output) 
        save_tasks()
        logger.info(f"Task {task_id} completed successfully with FM Mastering & Textures!")

    except Exception as exc:
        logger.exception("Pipeline failed")
        tasks[task_id]["status"] = "FAILURE"
        tasks[task_id]["error"] = str(exc)
        save_tasks()


# --- API Endpoints ---
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
    response = {"task_id": task_id, "status": entry["status"]}
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

@app.get("/debug")
async def debug_database():
    return tasks

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Radio Show Editor API is up and running!"}
