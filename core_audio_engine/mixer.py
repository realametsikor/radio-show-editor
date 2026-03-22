"""mixer.py — Intelligent audio ducking and pacing."""
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
    Pure Volume Automation (No complex mixing or sidechain algorithms).
    Literally scans the audio for pauses and turns the background music 
    up or down exactly like a human audio engineer riding a fader.
    """
    logger.info("Executing Pure Volume Automation (Documentary Style)...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # 1. Loop music to cover the voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    # 2. Detect literal pauses in the conversation
    # Looks for any silence longer than 1.2 seconds (including the Intro & Outro)
    logger.info("Scanning for pauses and breaths to automate volume...")
    pauses = silence.detect_silences(voice, min_silence_len=1200, silence_thresh=-45)
    
    # 3. Build the dynamic background track block by block
    final_music = AudioSegment.empty()
    last_end = 0
    
    # --- DOCUMENTARY VOLUME SETTINGS ---
    TALKING_DROP = 28  # Drops music 28dB so it is deeply in the background when hosts talk
    PAUSE_DROP = 14    # Raises music to -14dB during intro, outro, and mid-sentence breaths
    FADE_MS = 500      # A smooth half-second glide so the volume change doesn't "click" or jerk
    
    for start, end in pauses:
        # A. Add the talking section (Turn Volume DOWN)
        if start > last_end:
            talking_chunk = music[last_end:start] - TALKING_DROP
            final_music += talking_chunk
            
        # B. Add the paused section (Turn Volume UP)
        pause_chunk = music[start:end] - PAUSE_DROP
        
        # Apply smooth glides to the pause chunk so it feels natural
        fade_in_len = min(FADE_MS, len(pause_chunk) // 2)
        fade_out_len = min(FADE_MS, len(pause_chunk) // 2)
        
        if fade_in_len > 0:
            pause_chunk = pause_chunk.fade_in(fade_in_len).fade_out(fade_out_len)
            
        final_music += pause_chunk
        last_end = end
        
    # Add any remaining talking section at the very end of the file
    if last_end < len(music):
        final_music += music[last_end:] - TALKING_DROP
        
    # Ensure lengths match perfectly to the millisecond
    final_music = final_music[:len(voice)]
    
    # 4. Pure Overlay 
    # Just laying the clean voices straight over the clean music track
    logger.info("Overlaying pristine voices onto the automated volume track...")
    mixed = final_music.overlay(voice)
    
    mixed.export(str(output_path), format="wav")
    logger.info("✅ Pure Volume Automation Mix Complete!")
    return output_path
