"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def add_natural_pauses(voice_audio: AudioSegment) -> AudioSegment:
    """
    Adds a slight breathable padding to the raw voice track.
    """
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
    A mathematically perfect, phase-aligned Volume Crossfader.
    Seamlessly glides the music down deep into the background when the hosts speak, 
    and swells back up at the end without ever dropping to absolute silence.
    """
    logger.info("Executing Phase-Perfect PyDub Ducker with AGGRESSIVE ducking...")
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # 1. Ensure music is exactly the same length as the voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    # 2. Define our timeline markers (based on engine.py padding)
    intro_duration = 6000
    outro_duration = 10000
    body_end = len(voice) - outro_duration
    
    # AGGRESSIVE DUCKING: Push the music 24 decibels down so voices punch through!
    duck_amount = 24 
    
    # Failsafe for extremely short clips
    if body_end <= intro_duration:
        logger.warning("Clip too short for dynamic ducking. Applying static mix.")
        mixed = (music - duck_amount).overlay(voice)
        mixed.export(str(output_path), format="wav")
        return output_path

    # =========================================================================
    # 🎛️ THE PHASE-PERFECT VOLUME ENVELOPE
    # =========================================================================
    
    # Piece 1: The Loud Intro (0s to 5s)
    # Lowered slightly (-3dB) so the intro isn't deafening before the talking starts
    intro = music[:5000] - 3
    
    # Piece 2: The Downward Swell (5s to 6s)
    trans_down_loud = (music[5000:6000] - 3).fade_out(1000)
    trans_down_quiet = (music[5000:6000] - duck_amount).fade_in(1000)
    transition_down = trans_down_loud.overlay(trans_down_quiet)
    
    # Piece 3: The Quiet Talking Body (6s to End - 10s)
    body = music[6000:body_end] - duck_amount
    
    # Piece 4: The Upward Swell 
    trans_up_quiet = (music[body_end:body_end+1000] - duck_amount).fade_out(1000)
    trans_up_loud = (music[body_end:body_end+1000] - 3).fade_in(1000)
    transition_up = trans_up_quiet.overlay(trans_up_loud)
    
    # Piece 5: The Loud Outro (End - 9s to Finish)
    outro = (music[body_end+1000:]) - 3
    
    # Mathematically reassemble the track
    dynamic_music = intro + transition_down + body + transition_up + outro
    
    # Overlay the studio-mastered voices on top of the aggressively ducked track
    logger.info("Fusing deeply ducked music track with enhanced voices...")
    mixed = dynamic_music.overlay(voice)
    
    mixed.export(str(output_path), format="wav")
    logger.info("✅ Perfect Mix Complete!")
    return output_path
