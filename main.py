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
# 🎵 THE MASTER MUSIC LIBRARY 
# =========================================================================

SH_GENRES = ["Electronic","Lo-Fi","Jazz","Cinematic","Ambient","Funk","Electronic","Dramatic","Chill","Electronic","Atmospheric","Funk","Minimal","Tense","Upbeat","Electronic","Ambient"]
SH_MOODS = ["Energetic","Relaxed","Groovy","Mysterious","Dreamy","Groovy","Happy","Dramatic","Chill","Focused","Atmospheric","Funky","Minimal","Tense","Uplifting","Driving","Dreamy"]

ALL_TRACKS = []
for i in range(17):
    ALL_TRACKS.append({
        "genre": SH_GENRES[i], "mood": SH_MOODS[i], 
        "url": f"https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{i+1}.mp3"
    })

ADDITIONAL_TRACKS = [
    {"genre":"Corporate", "mood":"Uplifting", "url":"https://assets.mixkit.co/music/preview/mixkit-inspiring-life-210.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://assets.mixkit.co/music/preview/mixkit-tech-house-vibes-130.mp3"},
    {"genre":"Hip-Hop", "mood":"Groovy", "url":"https://assets.mixkit.co/music/preview/mixkit-hip-hop-02-738.mp3"},
    {"genre":"Ambient", "mood":"Dreamy", "url":"https://assets.mixkit.co/music/preview/mixkit-dreamy-traveler-189.mp3"},
    {"genre":"Pop", "mood":"Happy", "url":"https://assets.mixkit.co/music/preview/mixkit-happy-clapping-432.mp3"},
    {"genre":"Acoustic", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-relaxing-in-nature-522.mp3"},
    {"genre":"Cinematic", "mood":"Dramatic", "url":"https://assets.mixkit.co/music/preview/mixkit-cinematic-mystery-drums-and-bass-8.mp3"},
    {"genre":"Funk", "mood":"Groovy", "url":"https://assets.mixkit.co/music/preview/mixkit-urban-funk-247.mp3"},
    {"genre":"Chill", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-chilling-on-the-beach-609.mp3"},
    {"genre":"Classical", "mood":"Romantic", "url":"https://assets.mixkit.co/music/preview/mixkit-soft-piano-ballad-493.mp3"},
    {"genre":"Corporate", "mood":"Uplifting", "url":"https://assets.mixkit.co/music/preview/mixkit-positive-morning-420.mp3"},
    {"genre":"Lo-Fi", "mood":"Focused", "url":"https://assets.mixkit.co/music/preview/mixkit-life-is-a-dream-837.mp3"},
    {"genre":"Ambient", "mood":"Mysterious", "url":"https://assets.mixkit.co/music/preview/mixkit-mystery-ambience-519.mp3"},
    {"genre":"Cinematic", "mood":"Dramatic", "url":"https://assets.mixkit.co/music/preview/mixkit-epic-cinematic-opener-8.mp3"},
    {"genre":"Acoustic", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-sleepy-cat-135.mp3"},
    {"genre":"Pop", "mood":"Energetic", "url":"https://assets.mixkit.co/music/preview/mixkit-dance-with-me-3.mp3"},
    {"genre":"Hip-Hop", "mood":"Tense", "url":"https://assets.mixkit.co/music/preview/mixkit-trap-beat-loop-4.mp3"},
    {"genre":"Jazz", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-morning-coffee-jazz-and-bossa-nova-274.mp3"},
    {"genre":"Funk", "mood":"Groovy", "url":"https://assets.mixkit.co/music/preview/mixkit-funky-groove-321.mp3"},
    {"genre":"Ambient", "mood":"Dreamy", "url":"https://assets.mixkit.co/music/preview/mixkit-serene-view-443.mp3"},
    {"genre":"Corporate", "mood":"Uplifting", "url":"https://assets.mixkit.co/music/preview/mixkit-corporate-motivation-471.mp3"},
    {"genre":"Acoustic", "mood":"Romantic", "url":"https://assets.mixkit.co/music/preview/mixkit-acoustic-guitar-loop-2.mp3"},
    {"genre":"Electronic", "mood":"Mysterious", "url":"https://assets.mixkit.co/music/preview/mixkit-night-city-vibes-3.mp3"},
    {"genre":"Jazz", "mood":"Groovy", "url":"https://assets.mixkit.co/music/preview/mixkit-jazzy-abstract-loop-3.mp3"},
    {"genre":"Classical", "mood":"Melancholic", "url":"https://assets.mixkit.co/music/preview/mixkit-piano-reflections-22.mp3"},
    {"genre":"Hip-Hop", "mood":"Energetic", "url":"https://assets.mixkit.co/music/preview/mixkit-hip-hop-03-738.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://assets.mixkit.co/music/preview/mixkit-ukulele-fun-2.mp3"},
    {"genre":"Cinematic", "mood":"Dramatic", "url":"https://assets.mixkit.co/music/preview/mixkit-orchestral-mystery-545.mp3"},
    {"genre":"Corporate", "mood":"Uplifting", "url":"https://assets.mixkit.co/music/preview/mixkit-business-motivation-217.mp3"},
    {"genre":"Electronic", "mood":"Groovy", "url":"https://assets.mixkit.co/music/preview/mixkit-deep-urban-623.mp3"},
    {"genre":"Ambient", "mood":"Mysterious", "url":"https://assets.mixkit.co/music/preview/mixkit-space-ambience-1.mp3"},
    {"genre":"Acoustic", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-guitar-and-loop-3.mp3"},
    {"genre":"Jazz", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-lounge-jazz-217.mp3"},
    {"genre":"Electronic", "mood":"Dreamy", "url":"https://assets.mixkit.co/music/preview/mixkit-dreamy-synth-568.mp3"},
    {"genre":"Funk", "mood":"Happy", "url":"https://assets.mixkit.co/music/preview/mixkit-reggae-groove-245.mp3"},
    {"genre":"Classical", "mood":"Romantic", "url":"https://assets.mixkit.co/music/preview/mixkit-classical-ambience-loop-1.mp3"},
    {"genre":"Cinematic", "mood":"Mysterious", "url":"https://assets.mixkit.co/music/preview/mixkit-documentary-ambient-23.mp3"},
    {"genre":"Chill", "mood":"Relaxed", "url":"https://assets.mixkit.co/music/preview/mixkit-sunset-groove-1.mp3"},
    {"genre":"Corporate", "mood":"Happy", "url":"https://assets.mixkit.co/music/preview/mixkit-upbeat-corporate-458.mp3"},
    {"genre":"Lo-Fi", "mood":"Focused", "url":"https://assets.mixkit.co/music/preview/mixkit-chillhop-summer-feel-463.mp3"},
    {"genre":"Pop", "mood":"Uplifting", "url":"https://assets.mixkit.co/music/preview/mixkit-pop-uplifting-244.mp3"},
    {"genre":"Acoustic", "mood":"Melancholic", "url":"https://assets.mixkit.co/music/preview/mixkit-guitar-meditation-582.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://assets.mixkit.co/music/preview/mixkit-electronic-boost-5.mp3"},
    {"genre":"Classical", "mood":"Melancholic", "url":"https://www.bensound.com/bensound-music/bensound-memories.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://www.bensound.com/bensound-music/bensound-ukulele.mp3"},
    {"genre":"Cinematic", "mood":"Dramatic", "url":"https://www.bensound.com/bensound-music/bensound-epic.mp3"},
    {"genre":"Acoustic", "mood":"Relaxed", "url":"https://www.bensound.com/bensound-music/bensound-acousticbreeze.mp3"},
    {"genre":"Jazz", "mood":"Groovy", "url":"https://www.bensound.com/bensound-music/bensound-jazzyfrenchy.mp3"},
    {"genre":"Pop", "mood":"Happy", "url":"https://www.bensound.com/bensound-music/bensound-sunny.mp3"},
    {"genre":"Electronic", "mood":"Mysterious", "url":"https://www.bensound.com/bensound-music/bensound-scifi.mp3"},
    {"genre":"Corporate", "mood":"Uplifting", "url":"https://www.bensound.com/bensound-music/bensound-littleidea.mp3"},
    {"genre":"Classical", "mood":"Romantic", "url":"https://www.bensound.com/bensound-music/bensound-tenderness.mp3"},
    {"genre":"Chill", "mood":"Dreamy", "url":"https://www.bensound.com/bensound-music/bensound-onceagain.mp3"},
    {"genre":"Corporate", "mood":"Focused", "url":"https://www.bensound.com/bensound-music/bensound-creativeminds.mp3"},
    {"genre":"Pop", "mood":"Energetic", "url":"https://www.bensound.com/bensound-music/bensound-dance.mp3"},
    {"genre":"Ambient", "mood":"Relaxed", "url":"https://www.bensound.com/bensound-music/bensound-relaxing.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://www.bensound.com/bensound-music/bensound-dubstep.mp3"},
    {"genre":"Cinematic", "mood":"Melancholic", "url":"https://www.bensound.com/bensound-music/bensound-slowmotion.mp3"},
    {"genre":"Jazz", "mood":"Relaxed", "url":"https://www.bensound.com/bensound-music/bensound-thejazzpiano.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://www.bensound.com/bensound-music/bensound-moose.mp3"},
    {"genre":"Electronic", "mood":"Mysterious", "url":"https://www.bensound.com/bensound-music/bensound-perception.mp3"},
    {"genre":"Classical", "mood":"Romantic", "url":"https://www.bensound.com/bensound-music/bensound-love.mp3"},
    {"genre":"Pop", "mood":"Uplifting", "url":"https://www.bensound.com/bensound-music/bensound-betterdays.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://www.bensound.com/bensound-music/bensound-funnysong.mp3"},
    {"genre":"Jazz", "mood":"Groovy", "url":"https://www.bensound.com/bensound-music/bensound-hipjazz.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://www.bensound.com/bensound-music/bensound-elevate.mp3"},
    {"genre":"Cinematic", "mood":"Uplifting", "url":"https://www.bensound.com/bensound-music/bensound-tomorrow.mp3"},
    {"genre":"Corporate", "mood":"Happy", "url":"https://www.bensound.com/bensound-music/bensound-smile.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://audionautix.com/Music/NightRun.mp3"},
    {"genre":"Cinematic", "mood":"Tense", "url":"https://audionautix.com/Music/Anticipation.mp3"},
    {"genre":"Acoustic", "mood":"Relaxed", "url":"https://audionautix.com/Music/Barefoot.mp3"},
    {"genre":"Pop", "mood":"Happy", "url":"https://audionautix.com/Music/BeachParty.mp3"},
    {"genre":"Jazz", "mood":"Relaxed", "url":"https://audionautix.com/Music/CafeMusic.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://audionautix.com/Music/CountryFeel.mp3"},
    {"genre":"Ambient", "mood":"Mysterious", "url":"https://audionautix.com/Music/DarkFog.mp3"},
    {"genre":"Cinematic", "mood":"Dramatic", "url":"https://audionautix.com/Music/EpicMission.mp3"},
    {"genre":"Funk", "mood":"Groovy", "url":"https://audionautix.com/Music/FunkyConga.mp3"},
    {"genre":"Funk", "mood":"Groovy", "url":"https://audionautix.com/Music/GroovyBaby.mp3"},
    {"genre":"Classical", "mood":"Romantic", "url":"https://audionautix.com/Music/Heavenly.mp3"},
    {"genre":"Hip-Hop", "mood":"Groovy", "url":"https://audionautix.com/Music/HipHopGroove.mp3"},
    {"genre":"Ambient", "mood":"Relaxed", "url":"https://audionautix.com/Music/InspirationalMeditation.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://audionautix.com/Music/IslandSong.mp3"},
    {"genre":"Jazz", "mood":"Groovy", "url":"https://audionautix.com/Music/JazzInParis.mp3"},
    {"genre":"Hip-Hop", "mood":"Energetic", "url":"https://audionautix.com/Music/KickinItOldSchool.mp3"},
    {"genre":"Chill", "mood":"Relaxed", "url":"https://audionautix.com/Music/LatinChill.mp3"},
    {"genre":"Acoustic", "mood":"Happy", "url":"https://audionautix.com/Music/MorningMandolin.mp3"},
    {"genre":"Ambient", "mood":"Mysterious", "url":"https://audionautix.com/Music/MysteriousAmbiance.mp3"},
    {"genre":"Lo-Fi", "mood":"Focused", "url":"https://audionautix.com/Music/NightOwl.mp3"},
    {"genre":"Ambient", "mood":"Dreamy", "url":"https://audionautix.com/Music/OceanBreeze.mp3"},
    {"genre":"Classical", "mood":"Relaxed", "url":"https://audionautix.com/Music/PianoLounge.mp3"},
    {"genre":"Electronic", "mood":"Energetic", "url":"https://audionautix.com/Music/RockIntro.mp3"},
    {"genre":"Chill", "mood":"Relaxed", "url":"https://audionautix.com/Music/SmoothSailing.mp3"},
    {"genre":"Electronic", "mood":"Mysterious", "url":"https://audionautix.com/Music/Spaceship.mp3"},
    {"genre":"Pop", "mood":"Happy", "url":"https://audionautix.com/Music/TropicalIntro.mp3"},
    {"genre":"Jazz", "mood":"Happy", "url":"https://audionautix.com/Music/WalkingDownBroadway.mp3"}
]

ALL_TRACKS.extend(ADDITIONAL_TRACKS)

VIBE_MAPPER = {
    "lo-fi": ["Lo-Fi", "Chill", "Focused"],
    "upbeat": ["Energetic", "Happy", "Pop", "Upbeat"],
    "ambient": ["Ambient", "Atmospheric", "Dreamy"],
    "jazz": ["Jazz", "Groovy"],
    "cinematic": ["Cinematic", "Epic", "Dramatic"],
    "acoustic": ["Acoustic", "Relaxed"],
    "electronic": ["Electronic"],
    "hiphop": ["Hip-Hop", "Groovy", "Trap"],
    "gospel": ["Uplifting", "Corporate", "Happy"], 
    "afrobeats": ["Groovy", "Energetic", "Funk"],
    "rnb": ["Groovy", "Romantic", "Chill"],
    "reggae": ["Funk", "Happy", "Relaxed"],
    "classical": ["Classical", "Melancholic", "Romantic"],
    "country": ["Acoustic", "Happy"],
    "latin": ["Groovy", "Energetic"],
    "news": ["Corporate", "Focused"],
    "morning_drive": ["Energetic", "Upbeat", "Pop"],
    "comedy": ["Happy", "Funk", "Groovy"],
    "true_crime": ["Mysterious", "Tense", "Dramatic", "Dark Fog"],
    "tech": ["Electronic", "Focused", "Minimal"],
    "sports": ["Energetic", "Rock"],
    "war": ["Dramatic", "Tense", "Cinematic"],
    "documentary": ["Ambient", "Focused", "Mysterious"],
    "talk_show": ["Jazz", "Corporate", "Groovy"],
    "business": ["Corporate", "Focused", "Uplifting"],
    "spiritual": ["Ambient", "Relaxed", "Dreamy"],
    "horror": ["Mysterious", "Tense", "Cinematic"],
    "kids": ["Happy", "Acoustic", "Pop"],
    "romance": ["Romantic", "Classical", "Acoustic"],
    "science": ["Electronic", "Ambient", "Focused"]
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

        # --- AUDIO SANITIZER ---
        logger.info("Sanitizing and normalizing audio for Pyannote...")
        clean_audio_path = fp.parent / "clean_input.wav"
        
        subprocess.run([
            "ffmpeg", "-i", str(fp), 
            "-ar", "16000", "-ac", "1", 
            str(clean_audio_path), "-y"
        ], check=True)
        
        output_dir = fp.parent / "output"
        output_file = fp.parent / "radio_show_final.wav"
        
        # --- THE NEW SMART PLAYLIST GENERATOR ---
        logger.info(f"Building a dynamic playlist from the library for vibe: {mood}")
        music_path = str(fp.parent / "background_music.mp3")
        
        target_tags = VIBE_MAPPER.get(mood, ["Chill", "Ambient", "Lo-Fi"])
        
        matching_tracks = [
            t["url"] for t in ALL_TRACKS 
            if t["genre"] in target_tags or t["mood"] in target_tags
        ]
        
        if len(matching_tracks) < 3:
            logger.info("Not enough exact matches found. Supplementing with fallbacks...")
            matching_tracks.extend([
                "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "https://assets.mixkit.co/music/preview/mixkit-life-is-a-dream-837.mp3",
                "https://www.bensound.com/bensound-music/bensound-relaxing.mp3"
            ])
            
        random.shuffle(matching_tracks)
        urls_to_fetch = matching_tracks[:3]
        
        # 5. Download and stitch them together WITH CROSSFADES
        master_playlist = AudioSegment.empty()
        
        for i, url in enumerate(urls_to_fetch):
            try:
                temp_mp3 = fp.parent / f"temp_music_{i}.mp3"
                logger.info(f"Downloading track {i+1}...")
                music_data = requests.get(url, timeout=15).content
                
                with open(temp_mp3, "wb") as f:
                    f.write(music_data)
                
                segment = AudioSegment.from_file(str(temp_mp3))
                
                if len(master_playlist) == 0:
                    master_playlist = segment
                else:
                    # Smooth 3-second DJ crossfade between tracks!
                    crossfade_time = min(3000, len(master_playlist), len(segment))
                    master_playlist = master_playlist.append(segment, crossfade=crossfade_time)
                    
                temp_mp3.unlink() # Cleanup
            except Exception as e:
                logger.warning(f"Failed to fetch track {url}: {e}")
                
        # FAILSAFE: If all downloads completely failed, generate a silent track to prevent AI crash
        if len(master_playlist) == 0:
             logger.warning("All music downloads failed! Creating a silent backing track...")
             master_playlist = AudioSegment.silent(duration=60000)

        logger.info("Exporting the final Medley track...")
        master_playlist.export(music_path, format="mp3")
        del master_playlist
        gc.collect()

        # Run the AI Pipeline
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
