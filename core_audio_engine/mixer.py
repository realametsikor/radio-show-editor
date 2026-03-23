"""mixer.py — Intelligent audio ducking and structural pacing."""
from __future__ import annotations

import logging
from pathlib import Path
from pydub import AudioSegment, silence

logger = logging.getLogger(__name__)

def mix_with_ducking(
    voice_path: str | Path, 
    music_path: str | Path, 
    output_path: str | Path, 
    music_curve: list = None
) -> Path:
    """
    Three-Tier Structural Pacing.
    Injects multiple intentional music breaks (Intro, Post-Hook, Mid, Outro) 
    and beautifully rides the volume fader around them.
    """
    logger.info("Executing Cinematic Pacing (Multi-Break System)...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # Boost voices for clarity so they command the mix
    voice = voice + 3

    # =====================================================================
    # 🎬 STRUCTURAL PACING (INJECTING THE BREAKS)
    # We actively slice the voice track to create intentional moments 
    # where the music gets to shine before speaking resumes.
    # =====================================================================
    logger.info("Scanning for optimal structural interlude points...")
    
    natural_pauses = silence.detect_silence(voice, min_silence_len=400, silence_thresh=-35)
    split_points = []
    
    if natural_pauses:
        # 1. The "Post-Hook" Break (NEW)
        # Finds the first natural pause after the host introduces the topic (between 5s and 45s)
        for p in natural_pauses:
            if 5000 < p[0] < 45000:
                split_points.append(p[0])
                logger.info(f"Injecting Post-Hook swell at {p[0]/1000} seconds")
                break
                
        # 2. The "Mid-Show" Break
        midpoint = len(voice) // 2
        mid_pause = min(natural_pauses, key=lambda p: abs(p[0] - midpoint))
        
        # Ensure the mid-pause isn't too close to the post-hook pause (e.g. on very short clips)
        if not split_points or abs(mid_pause[0] - split_points[0]) > 30000:
            split_points.append(mid_pause[0])
            logger.info(f"Injecting Mid-Show swell at {mid_pause[0]/1000} seconds")

    # Sort in reverse order! 
    # (We insert silence from the back of the track to the front so earlier timestamps don't shift)
    split_points.sort(reverse=True)
    
    # Inject the 4-second internal breaks
    for sp in split_points:
        part1 = voice[:sp]
        part2 = voice[sp:]
        voice = part1 + AudioSegment.silent(duration=4000) + part2
        
    # Add the absolute start (Cold Open) and absolute end (Outro) breaks
    voice = AudioSegment.silent(duration=4000) + voice + AudioSegment.silent(duration=5000)

    # =====================================================================
    # 🎛️ TWO-TIER VOLUME AUTOMATION
    # =====================================================================
    # Loop music to cover the newly lengthened, beautifully paced voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    logger.info("Scanning for dynamic swells to orchestrate the music bed...")
    pauses = silence.detect_silence(voice, min_silence_len=700, silence_thresh=-35)
    
    final_music = AudioSegment.empty()
    last_end = 0
    
    # --- DYNAMIC BROADCAST SETTINGS ---
    TALKING_DROP = 38    # Absolute whisper while speaking
    BREATH_DROP = 22     # Gentle background swell during normal conversation pauses
    INTERLUDE_DROP = 14  # Prominent, beautiful swell during our injected 4-second breaks!
    FADE_MS = 800        # Smooth 0.8-second cinematic volume glide
    
    for start, end in pauses:
        # A. Add the talking section (Turn Volume DOWN)
        if start > last_end:
            talking_chunk = music[last_end:start] - TALKING_DROP
            final_music += talking_chunk
            
        # B. Add the paused section (Determine if it's a breath or an interlude)
        pause_duration = end - start
        if pause_duration >= 3500:
            # This is one of our injected structural breaks! Let it soar.
            pause_chunk = music[start:end] - INTERLUDE_DROP
        else:
            # This is just a normal conversation breath. Keep it subtle.
            pause_chunk = music[start:end] - BREATH_DROP
            
        # Apply buttery smooth glides
        fade_in_len = min(FADE_MS, len(pause_chunk) // 2)
        fade_out_len = min(FADE_MS, len(pause_chunk) // 2)
        
        if fade_in_len > 0:
            pause_chunk = pause_chunk.fade_in(fade_in_len).fade_out(fade_out_len)
            
        final_music += pause_chunk
        last_end = end
        
    # Add any remaining talking section at the very end
    if last_end < len(music):
        final_music += music[last_end:] - TALKING_DROP
        
    final_music = final_music[:len(voice)]
    
    logger.info("Fusing the dynamically paced music bed with voices...")
    mixed = final_music.overlay(voice)
    
    mixed.export(str(output_path), format="wav")
    logger.info("✅ Multi-Break Cinematic Mix Complete!")
    return output_path
