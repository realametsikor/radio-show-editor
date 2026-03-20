"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def add_natural_pauses(voice_audio: AudioSegment) -> AudioSegment:
    """
    Adds a slight breathable padding to the raw voice track.
    This ensures the voices don't start abruptly at 0.00s and gives the 
    Sidechain Compressor time to lock onto the audio.
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
    Uses FFmpeg's Lookahead Sidechain Compression to create a buttery smooth 
    radio ducking effect. The music will organically swell up when the host 
    stops talking and glide down when they speak.
    """
    logger.info("Executing Sidechain Compression (Radio Auto-Ducker)...")
    
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)
    
    # =========================================================================
    # 🎛️ THE FIXED SIDECHAIN COMPRESSOR MATRIX
    # Added [voice]asplit=2 so we can use the voice track to trigger the 
    # compressor AND mix it into the final output without FFmpeg crashing.
    # =========================================================================
    filter_complex = (
        "[0:a]volume=0.85,aformat=sample_rates=44100:channel_layouts=stereo[music];"
        "[1:a]volume=1.20,aformat=sample_rates=44100:channel_layouts=stereo[voice];"
        "[voice]asplit=2[voice_ctrl][voice_mix];"
        "[music][voice_ctrl]sidechaincompress=threshold=0.03:ratio=5.0:attack=20:release=1200[ducked_music];"
        "[ducked_music][voice_mix]amix=inputs=2:duration=shortest:weights=1 1[out]"
    )
    
    try:
        subprocess.run([
            "ffmpeg", 
            "-i", str(music_path),   # Input 0: Music
            "-i", str(voice_path),   # Input 1: Voice
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-y", str(output_path)
        ], check=True, capture_output=True)
        
        logger.info("✅ Sidechain ducking successful! The music is breathing with the voices.")
        return output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"FFmpeg ducking failed: {error_msg}")
        
        logger.info("Falling back to standard Pydub static mix...")
        music = AudioSegment.from_file(str(music_path))
        voice = AudioSegment.from_wav(str(voice_path))
        
        music = music - 14
        mixed = music.overlay(voice)
        
        mixed = mixed[:len(voice)]
        mixed.export(str(output_path), format="wav")
        return output_path
