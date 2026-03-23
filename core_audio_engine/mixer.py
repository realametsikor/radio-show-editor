"""mixer.py — Intelligent audio ducking and structural pacing."""
from __future__ import annotations

import logging
from pathlib import Path
from pydub import AudioSegment, silence

logger = logging.getLogger(__name__)

def add_natural_pauses(voice_audio: AudioSegment) -> AudioSegment:
    """Adds a slight breathable padding to the raw voice track."""
    logger.info("Padding voice track with natural breath room...")
    pad = AudioSegment.silent(duration=800)
    return pad + voice_audio + pad

def mix_with_ducking(
    voice_path: str | Path, 
    music_path: str | Path, 
    output_path: str | Path, 
    music_curve: list = None
) -> Path:
    """
    Cinematic Pacing Mix.
    Injects 4-second music breaks at the start, middle, and end so the music
    can beautifully swell and carry the emotional tone of the episode.
    """
    logger.info("Executing Cinematic Pacing (Start, Mid, and End Breaks)...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # Boost voices for clarity
    voice = voice + 3

    # =====================================================================
    # 🎬 STRUCTURAL PACING (INJECTING THE BREAKS)
    # =====================================================================
    logger.info("Injecting structural music interludes...")
    
    # 1. Intro Break (4 seconds of music before talking starts)
    intro_padding = AudioSegment.silent(duration=4000)
    
    # 2. Outro Break (5 seconds of music to close the show)
    outro_padding = AudioSegment.silent(duration=5000)
    
    # 3. Mid-Show Break (4 seconds of music in the middle of the conversation)
    # Find a natural breath near the exact center to safely split it
    midpoint = len(voice) // 2
    natural_pauses = silence.detect_silence(voice, min_silence_len=400, silence_thresh=-35)
    
    if natural_pauses:
        # Safely find the breath closest to the midpoint of the episode
        closest_pause = min(natural_pauses, key=lambda p: abs(p[0] - midpoint))
        split_point = closest_pause[0]
        
        part1 = voice[:split_point]
        part2 = voice[split_point:]
        
        mid_padding = AudioSegment.silent(duration=4000)
        voice = part1 + mid_padding + part2
        
    # Apply the intro and outro
    voice = intro_padding + voice + outro_padding

    # =====================================================================
    # 🎛️ TWO-TIER VOLUME AUTOMATION
    # =====================================================================
    # Loop music to cover the newly lengthened voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    logger.info("Scanning for pauses to orchestrate the two-tier music bed...")
    pauses = silence.detect_silence(voice, min_silence_len=700, silence_thresh=-35)
    
    final_music = AudioSegment.empty()
    last_end = 0
    
    # --- DYNAMIC BROADCAST SETTINGS ---
    TALKING_DROP = 38    # Absolute whisper while speaking (Your requested volume)
    BREATH_DROP = 22     # Gentle swell during normal conversation pauses
    INTERLUDE_DROP = 14  # Prominent, beautiful swell during our injected 4-second breaks!
    FADE_MS = 800        # Smooth 0.8-second cinematic glide
    
    for start, end in pauses:
        # A. Add the talking section (Turn Volume DOWN)
        if start > last_end:
            talking_chunk = music[last_end:start] - TALKING_DROP
            final_music += talking_chunk
            
        # B. Add the paused section (Determine if it's a breath or a long interlude)
        pause_duration = end - start
        if pause_duration >= 3500:
            # This is one of our injected structural breaks! Let the music shine.
            pause_chunk = music[start:end] - INTERLUDE_DROP
        else:
            # This is just a normal conversation breath. Keep the swell subtle.
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
    logger.info("✅ Cinematic Pacing Mix Complete!")
    return output_path
