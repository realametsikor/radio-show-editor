"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def add_natural_pauses(voice_audio: AudioSegment) -> AudioSegment:
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
    A 100% Bulletproof PyDub Dynamic Mixer. 
    It manually builds an automation envelope to guarantee the music swells 
    at the intro/outro and cleanly ducks behind the voices without using fragile FFmpeg filters.
    """
    logger.info("Executing Bulletproof PyDub Envelope Ducker...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # 1. Ensure the music track is long enough
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
        
    music = music[:len(voice)]
    
    # =========================================================================
    # 🎛️ THE VOLUME AUTOMATION ENVELOPE
    # We know engine.py adds exactly 6000ms to the start and 10000ms to the end.
    # =========================================================================
    
    fade_duration = 1500 # 1.5 second smooth swell/dip
    
    try:
        # INTRO: First 6 seconds at 100% Volume
        intro_music = music[:6000]
        
        # BODY: The talking section dropped by 16 decibels
        body_end = len(voice) - 10000
        if body_end <= 6000:
            body_end = len(voice) # Failsafe for short clips
            
        body_music = music[6000:body_end] - 16
        
        # OUTRO: Last 10 seconds at 100% Volume
        outro_music = music[body_end:]
        
        # Apply the cinematic fades so the transitions are buttery smooth
        intro_music = intro_music.fade_out(fade_duration)
        body_music = body_music.fade_in(fade_duration).fade_out(fade_duration)
        outro_music = outro_music.fade_in(fade_duration)
        
        # Assemble the dynamic backing track
        dynamic_music = intro_music + body_music + outro_music
        
        # Overlay the voices
        logger.info("Fusing dynamic music track with enhanced voices...")
        mixed = dynamic_music.overlay(voice)
        
        mixed.export(str(output_path), format="wav")
        logger.info("✅ Perfect Mix Complete!")
        return output_path
        
    except Exception as e:
        logger.error(f"Dynamic mixer failed, executing basic static mix: {e}")
        # Extreme Failsafe: Just drop music by 14dB and mix
        music = music - 14
        mixed = music.overlay(voice)
        mixed.export(str(output_path), format="wav")
        return output_path
