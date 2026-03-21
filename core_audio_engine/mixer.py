"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
from pathlib import Path
from pydub import AudioSegment

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
    The 'NPR Standard' Phase-Aligned Envelope Mixer.
    Instead of annoying 'pumping' sidechain compression, we use mathematically 
    perfect volume crossfades. The music drops to a whisper (-26dB) and stays 
    completely flat while the hosts talk, so it never overpowers them.
    """
    logger.info("Executing Broadcast-Grade Phase-Aligned Volume Envelope...")
    
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)
    
    voice = AudioSegment.from_wav(str(voice_path))
    music = AudioSegment.from_file(str(music_path))
    
    # 1. Loop music to ensure it covers the entire voice track
    if len(music) < len(voice):
        loops = (len(voice) // len(music)) + 1
        music = music * loops
    music = music[:len(voice)]
    
    # 2. Failsafe for very short test clips
    if len(voice) < 20000:
        logger.warning("Clip too short for complex envelope. Using static background mix.")
        mixed = (music - 24).overlay(voice)
        mixed.export(str(output_path), format="wav")
        return output_path

    # =========================================================================
    # 🎛️ THE PHASE-PERFECT AUTOMATION ENVELOPE
    # We extract slices of the EXACT SAME track at different volumes and 
    # crossfade them together. This guarantees 0 phase-cancellation and 
    # perfectly smooth volume swells.
    # =========================================================================
    
    V = len(voice)
    
    # Intro: Play at -8dB (Present, but not deafening)
    loud_intro = music[:7000] - 8
    
    # Body: Drop to -26dB (Deep in the background, out of the way)
    quiet_body = music[5000:V-8000] - 26
    
    # Outro: Swell back up to -8dB to close the show
    loud_outro = music[V-10000:] - 8
    
    # Assemble with 2-second overlapping crossfades
    # loud_intro ends at 7s, quiet_body starts at 5s -> crossfade from 5s to 7s
    part1 = loud_intro.append(quiet_body, crossfade=2000)
    
    # part1 ends at V-8s, loud_outro starts at V-10s -> crossfade from V-10s to V-8s
    final_dynamic_music = part1.append(loud_outro, crossfade=2000)
    
    # 3. Fuse the perfectly ducked music bed with the voices
    logger.info("Fusing whispered music bed with enhanced voices...")
    
    # Small master boost to the voices to guarantee they sit on top of the mix
    voice = voice + 2 
    
    mixed = final_dynamic_music.overlay(voice)
    
    mixed.export(str(output_path), format="wav")
    logger.info("✅ Phase-Perfect Mix Complete!")
    return output_path
