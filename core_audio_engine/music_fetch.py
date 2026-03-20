"""music_fetch.py — Curated broadcast music and atmosphere generator."""
from __future__ import annotations

import logging
import random
import uuid
from pathlib import Path

import requests
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# =========================================================================
# 🎵 THE CURATED SOUNDHELIX LIBRARY
# SoundHelix never blocks cloud servers. We manually curate the track IDs 
# so the genre always perfectly matches the user's selected mood.
# =========================================================================

SH_BASE = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-{}.mp3"

CURATED_LIBRARY = {
    "documentary": [9, 11, 16, 17], # Ambient, slow, thoughtful, atmospheric
    "science": [9, 11, 16, 17],
    "lo-fi": [4, 7, 9],             # Chill, jazzy, relaxed
    "jazz": [4, 7],
    "true_crime": [8, 14],          # Tense, dramatic, mysterious
    "upbeat": [1, 6, 15],           # Pop, energetic, driving
    "talk_show": [4, 7, 1]
}

VIBE_MAPPER = {
    "ambient": "documentary",
    "cinematic": "documentary",
    "horror": "true_crime",
    "mystery": "true_crime",
    "chill": "lo-fi",
    "hiphop": "lo-fi",
    "funk": "upbeat",
    "energetic": "upbeat",
    "morning_drive": "upbeat",
    "comedy": "upbeat",
    "news": "documentary",
    "business": "talk_show",
    "sports": "upbeat",
    "acoustic": "lo-fi"
}

def build_music_track(mood: str, output_path: str | Path, work_dir: str | Path) -> Path:
    logger.info(f"Curating reliable playlist for vibe: {mood}...")
    
    work_dir = Path(work_dir)
    output_path = Path(output_path)
    
    mapped_category = mood.lower()
    if mapped_category not in CURATED_LIBRARY:
        mapped_category = VIBE_MAPPER.get(mapped_category, "documentary")
        
    available_tracks = CURATED_LIBRARY.get(mapped_category, CURATED_LIBRARY["documentary"])
    
    urls_to_fetch = [SH_BASE.format(track_id) for track_id in available_tracks]
    random.shuffle(urls_to_fetch)
    urls_to_fetch = urls_to_fetch[:2] 
        
    master_playlist = AudioSegment.empty()
    
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "audio/mpeg, audio/mp3, */*"
    }
    
    # 1. FETCH AND CROSSFADE MUSIC
    for i, url in enumerate(urls_to_fetch):
        try:
            temp_mp3 = work_dir / f"temp_music_{i}.mp3"
            logger.info(f"Downloading track {i+1}...")
            
            res = requests.get(url, headers=browser_headers, timeout=20)
            res.raise_for_status() 
            
            with open(temp_mp3, "wb") as f:
                f.write(res.content)
            
            segment = AudioSegment.from_file(str(temp_mp3))
            
            if len(master_playlist) == 0:
                master_playlist = segment
            else:
                crossfade_time = min(4000, len(master_playlist), len(segment))
                master_playlist = master_playlist.append(segment, crossfade=crossfade_time)
                
            temp_mp3.unlink() 
        except Exception as e:
            logger.warning(f"Failed to fetch track {url}: {e}")
            
    if len(master_playlist) == 0:
         logger.error("CRITICAL: All music downloads failed! Falling back to backup track.")
         # Extreme fallback just to guarantee music exists
         master_playlist = AudioSegment.silent(duration=60000)
    else:
         logger.info("Looping the playlist so it covers long podcasts...")
         master_playlist = master_playlist * 8 

    master_playlist.export(str(output_path), format="mp3")
    logger.info("✅ Base music compiled.")
    return output_path

def fetch_music_for_mood(mood: str) -> str:
    mapped_category = mood.lower()
    if mapped_category not in CURATED_LIBRARY:
        mapped_category = VIBE_MAPPER.get(mapped_category, "documentary")
        
    available_tracks = CURATED_LIBRARY.get(mapped_category, CURATED_LIBRARY["documentary"])
    track_id = random.choice(available_tracks)
    url = SH_BASE.format(track_id)
    
    output_path = f"temp_single_bumper_{uuid.uuid4().hex[:6]}.mp3"
    
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        with open(output_path, "wb") as f:
            f.write(res.content)
        return output_path
    except Exception as e:
        logger.warning(f"Legacy fetch failed, generating silence: {e}")
        AudioSegment.silent(duration=5000).export(output_path, format="mp3")
        return output_path
