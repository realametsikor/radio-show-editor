"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
import subprocess
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
    The 'Subtle Breather' Sidechain Auto-Ducker.
    Allows the music to dynamically swell during pauses and breaths, 
    but strictly caps the maximum music volume at 25% so it never overshadows the hosts.
    """
    logger.info("Executing Broadcast-Grade FFmpeg Sidechain Ducker (Tuned for subtle breathing)...")
    
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)
    
    # 1. First ensure music is looped to be long enough using Pydub
    voice_seg = AudioSegment.from_wav(str(voice_path))
    music_seg = AudioSegment.from_file(str(music_path))
    
    if len(music_seg) < len(voice_seg):
        loops = (len(voice_seg) // len(music_seg)) + 1
        music_seg = music_seg * loops
        
    # Add a gentle fade out to the very end of the music tail
    music_seg = music_seg[:len(voice_seg)].fade_out(3000)
    
    # Save the looped music to a temp file for FFmpeg
    temp_music_path = music_path.parent / "temp_music_looped.wav"
    music_seg.export(str(temp_music_path), format="wav")

    # =========================================================================
    # 🎛️ THE SUBTLE BREATHING MATRIX
    # volume=0.25 on the music ensures the highest "swell" is still quiet.
    # threshold=0.015 and ratio=5.0 pushes the music extremely deep when hosts talk.
    # release=600 is the magic number for a smooth, natural swell during breaths.
    # =========================================================================
    
    filter_complex = (
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.25[music];"
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.20[voice];"
        "[voice]asplit=2[voice_sc][voice_mix];"
        "[music][voice_sc]sidechaincompress=threshold=0.015:ratio=5.0:attack=10:release=600[ducked_music];"
        "[ducked_music][voice_mix]amerge=inputs=2[merged];"
        "[merged]pan=stereo|c0<c0+c2|c1<c1+c3[out]"
    )
    
    try:
        subprocess.run([
            "ffmpeg", 
            "-i", str(temp_music_path),
            "-i", str(voice_path),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-y", str(output_path)
        ], check=True, capture_output=True)
        
        temp_music_path.unlink(missing_ok=True)
        logger.info("✅ Subtle Sidechain Mix Complete!")
        return output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"FFmpeg ducking failed: {error_msg}")
        
        # Failsafe in case of catastrophic FFmpeg failure
        logger.info("Falling back to static PyDub mix...")
        mixed = (music_seg - 20).overlay(voice_seg)
        mixed.export(str(output_path), format="wav")
        return output_path
