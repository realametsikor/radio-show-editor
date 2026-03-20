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
# 🎵 THE CURATED BROADCAST LIBRARY
# Replacing algorithmic randomness with premium, hand-picked royalty-free 
# tracks specifically suited for podcasts and radio.
# =========================================================================

# Base URL for a highly stable repository of Kevin MacLeod CC-BY Broadcast Music
BASE_ARCHIVE = "https://ia803104.us.archive.org/27/items/k-mac-leod-music/"

CURATED_LIBRARY = {
    "documentary": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Deep%20Haze.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Deliberate%20Thought.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Heartbreaking.mp3"
    ],
    "science": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Deep%20Haze.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Deliberate%20Thought.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Unanswered%20Questions.mp3"
    ],
    "lo-fi": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Backed%20Vibes%20Clean.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Chill%20Wave.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Acid%20Jazz.mp3"
    ],
    "jazz": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Backed%20Vibes%20Clean.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Hard%20Boiled.mp3"
    ],
    "true_crime": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Anxiety.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20The%20Descent.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Classic%20Horror%201.mp3"
    ],
    "upbeat": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Pamgaea.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Funk%20Game%20Loop.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Disco%20Medusae.mp3"
    ],
    "talk_show": [
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Acid%20Jazz.mp3",
        BASE_ARCHIVE + "Kevin%20MacLeod%20-%20Funk%20Game%20Loop.mp3"
    ]
}

# Safely map alternative mood inputs to our curated categories
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

ATMOSPHERE_URLS = {
    "vinyl": "https://ia800305.us.archive.org/30/items/vinyl-crackle/vinyl-crackle.mp3",
    "rain": "https://ia801602.us.archive.org/15/items/rain-noise/rain-noise.mp3"
}

def build_music_track(mood: str, output_path: str | Path, work_dir: str | Path) -> Path:
    """
    Builds the background music medley using curated broadcast tracks.
    """
    logger.info(f"Curating professional playlist for vibe: {mood}...")
    
    work_dir = Path(work_dir)
    output_path = Path(output_path)
    
    # Standardize the mood category
    mapped_category = mood.lower()
    if mapped_category not in CURATED_LIBRARY:
        mapped_category = VIBE_MAPPER.get(mapped_category, "documentary")
        
    available_tracks = CURATED_LIBRARY.get(mapped_category, CURATED_LIBRARY["documentary"])
    
    # Shuffle to keep the medley fresh, but stay within the correct genre
    urls_to_fetch = list(available_tracks)
    random.shuffle(urls_to_fetch)
    urls_to_fetch = urls_to_fetch[:2] # Grab up to 2 tracks to crossfade
        
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
            
            res = requests.get(url, headers=browser_headers, timeout=30)
            res.raise_for_status() 
            
            with open(temp_mp3, "wb") as f:
                f.write(res.content)
            
            segment = AudioSegment.from_file(str(temp_mp3))
            
            # Lower the raw track volume slightly so it sits better in the mix before ducking
            segment = segment - 4 
            
            if len(master_playlist) == 0:
                master_playlist = segment
            else:
                # 4-second smooth DJ crossfade between tracks
                crossfade_time = min(4000, len(master_playlist), len(segment))
                master_playlist = master_playlist.append(segment, crossfade=crossfade_time)
                
            temp_mp3.unlink() 
        except Exception as e:
            logger.warning(f"Failed to fetch track {url}: {e}")
            
    if len(master_playlist) == 0:
         logger.warning("All music downloads failed! Creating a silent backing track...")
         master_playlist = AudioSegment.silent(duration=60000)
    else:
         logger.info("Looping the playlist so it covers long podcasts...")
         master_playlist = master_playlist * 8  # Loop for long shows

    # 2. FETCH AND OVERLAY ATMOSPHERE
    atmosphere_type = None
    if mapped_category in ["lo-fi", "jazz", "talk_show"]:
        atmosphere_type = "vinyl"
    elif mapped_category in ["true_crime", "documentary", "science"]:
        atmosphere_type = "rain"

    if atmosphere_type:
        logger.info(f"Applying physical texture ({atmosphere_type}) layer...")
        try:
            atmo_url = ATMOSPHERE_URLS[atmosphere_type]
            atmo_res = requests.get(atmo_url, headers=browser_headers, timeout=15)
            
            if atmo_res.status_code == 200:
                temp_atmo = work_dir / "temp_atmo.mp3"
                with open(temp_atmo, "wb") as f:
                    f.write(atmo_res.content)
                    
                atmo_segment = AudioSegment.from_file(str(temp_atmo))
                atmo_segment = atmo_segment - 24 # Keep texture subtle
                
                needed_loops = (len(master_playlist) // len(atmo_segment)) + 1
                atmo_segment = atmo_segment * needed_loops
                atmo_segment = atmo_segment[:len(master_playlist)] 
                
                master_playlist = master_playlist.overlay(atmo_segment)
                temp_atmo.unlink()
        except Exception as e:
            logger.warning(f"Failed to apply atmosphere layer: {e}")

    # 3. EXPORT FINAL BACKING TRACK
    master_playlist.export(str(output_path), format="mp3")
    logger.info("✅ Base music and atmosphere track compiled.")
    return output_path

# =========================================================================
# 🔙 BACKWARD COMPATIBILITY BRIDGE (For sfx.py)
# =========================================================================
def fetch_music_for_mood(mood: str) -> str:
    """
    Acts as a bridge for legacy files (like sfx.py) that expect to fetch 
    a single track rather than building the full medley.
    """
    logger.info(f"Bridging legacy music request for mood: {mood}...")
    
    mapped_category = mood.lower()
    if mapped_category not in CURATED_LIBRARY:
        mapped_category = VIBE_MAPPER.get(mapped_category, "documentary")
        
    available_tracks = CURATED_LIBRARY.get(mapped_category, CURATED_LIBRARY["documentary"])
    url = random.choice(available_tracks)
    
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
