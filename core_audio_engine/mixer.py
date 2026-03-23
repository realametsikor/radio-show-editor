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
    Pure Volume Automation (The 'Broadcast Whisper' Mix).
    Forces modern, overly-loud music tracks into the absolute basement 
    so they never distract from the professional voiceover.
    """
    logger.info("Executing Pure Volume Automation (Ultra-Quiet Broadcast Mix)...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # Give the voices a small boost to guarantee they command the mix
    voice = voice + 3
    
    # 1. Loop music to cover the voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    # 2. Detect thoughtful pauses in the conversation (700ms)
    logger.info("Scanning for 0.7s pauses to orchestrate the music bed...")
    pauses = silence.detect_silence(voice, min_silence_len=700, silence_thresh=-35)
    
    # 3. Build the dynamic background track block by block
    final_music = AudioSegment.empty()
    last_end = 0
    
    # --- THE BROADCAST WHISPER SETTINGS ---
    # We are dropping these massively to account for heavily mastered music tracks.
    TALKING_DROP = 38  # Absolute whisper. Pushes the music deep into the background.
    PAUSE_DROP = 22    # Gentle, controlled swell that never gets distracting.
    FADE_MS = 800      # 0.8-second cinematic crossfade for invisible, buttery transitions.
    
    for start, end in pauses:
        # A. Add the talking section (Turn Volume DOWN to -38dB)
        if start > last_end:
            talking_chunk = music[last_end:start] - TALKING_DROP
            final_music += talking_chunk
            
        # B. Add the paused section (Turn Volume UP to -22dB)
        pause_chunk = music[start:end] - PAUSE_DROP
        
        # Apply buttery smooth glides to the pause chunk
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
    logger.info("Fusing the ultra-quiet automated music bed with enhanced voices...")
    mixed = final_music.overlay(voice)
    
    mixed.export(str(output_path), format="wav")
    logger.info("✅ Perfect Whisper Mix Complete!")
    return output_path
