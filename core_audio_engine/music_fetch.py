"""music_fetch.py — Dynamic music curation and atmosphere generator."""
from __future__ import annotations

import logging
import random
import uuid
from pathlib import Path

import requests
from pydub import AudioSegment

logger = logging.getLogger(__name__)

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

ATMOSPHERE_URLS = {
    "vinyl": "https://ia800305.us.archive.org/30/items/vinyl-crackle/vinyl-crackle.mp3",
    "rain": "https://ia801602.us.archive.org/15/items/rain-noise/rain-noise.mp3"
}

def build_music_track(mood: str, output_path: str | Path, work_dir: str | Path) -> Path:
    """
    Builds the background music medley with Emotion Shifting and Physical Atmosphere.
    Returns the path to the fully mixed backing track.
    """
    logger.info(f"Curating dynamic SoundHelix playlist for vibe: {mood}...")
    
    work_dir = Path(work_dir)
    output_path = Path(output_path)
    
    target_tags = VIBE_MAPPER.get(mood, ["Chill", "Ambient", "Lo-Fi"])
    
    matching_tracks = [
        t["url"] for t in ALL_TRACKS 
        if t["genre"] in target_tags or t["mood"] in target_tags
    ]
    
    # 🎭 EMOTION SHIFTING: The Curveball Track
    contrast_pool = [t["url"] for t in ALL_TRACKS if t["url"] not in matching_tracks]
    
    if len(matching_tracks) < 2:
        matching_tracks.extend(contrast_pool[:2])
        
    unique_tracks = list(set(matching_tracks))
    random.shuffle(unique_tracks)
    random.shuffle(contrast_pool)
    
    urls_to_fetch = unique_tracks[:2] 
    if contrast_pool:
        urls_to_fetch.append(contrast_pool[0]) 
        logger.info("Added 1 Contrast Track to shift emotion mid-show.")
        
    master_playlist = AudioSegment.empty()
    
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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
         master_playlist = master_playlist * 8  # Loop for ~48 mins

    # 2. FETCH AND OVERLAY ATMOSPHERE
    atmosphere_type = None
    if mood in ["lo-fi", "jazz", "acoustic", "talk_show"]:
        atmosphere_type = "vinyl"
    elif mood in ["true_crime", "horror", "documentary", "war", "ambient"]:
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
                
                # Drop volume so it hugs the bottom floor (-22dB)
                atmo_segment = atmo_segment - 22 
                
                # Loop the static/rain to perfectly match our giant music track
                needed_loops = (len(master_playlist) // len(atmo_segment)) + 1
                atmo_segment = atmo_segment * needed_loops
                atmo_segment = atmo_segment[:len(master_playlist)] 
                
                # Merge the crackle directly into the music medley
                master_playlist = master_playlist.overlay(atmo_segment)
                temp_atmo.unlink()
        except Exception as e:
            logger.warning(f"Failed to apply atmosphere layer, continuing with clean music: {e}")

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
    
    target_tags = VIBE_MAPPER.get(mood, ["Chill", "Ambient", "Lo-Fi"])
    matching_tracks = [t["url"] for t in ALL_TRACKS if t["genre"] in target_tags or t["mood"] in target_tags]
    
    if not matching_tracks:
        matching_tracks = [t["url"] for t in ALL_TRACKS]
        
    url = random.choice(matching_tracks)
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
