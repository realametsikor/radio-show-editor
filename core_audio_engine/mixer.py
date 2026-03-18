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
    # Add 800ms of pure silence to the beginning and end
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
    # 🎛️ THE SIDECHAIN COMPRESSOR MATRIX
    # =========================================================================
    # [0:a] is Music (Background)
    # [1:a] is Voice (Foreground)
    # 
    # Settings:
    # threshold=0.03 (-30dB): The music drops as soon as the voice hits this volume.
    # ratio=5.0: A heavy, aggressive ducking clamp (standard for radio).
    # attack=20: 20ms fast dip so the music gets out of the way of the first syllable.
    # release=1200: 1.2-second slow release so the music "swells" cinematically during pauses.
    # =========================================================================
    
    filter_complex = (
        "[0:a]volume=0.85,aformat=sample_rates=44100:channel_layouts=stereo[music];"
        "[1:a]volume=1.20,aformat=sample_rates=44100:channel_layouts=stereo[voice];"
        "[music][voice]sidechaincompress=threshold=0.03:ratio=5.0:attack=20:release=1200[ducked_music];"
        "[ducked_music][voice]amix=inputs=2:duration=shortest:weights=1 1[out]"
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
        
        # --- BULLETPROOF FAILSAFE ---
        # If the advanced FFmpeg sidechain fails for any reason, it falls back to 
        # standard Pydub mixing so the pipeline never crashes.
        logger.info("Falling back to standard Pydub static mix...")
        music = AudioSegment.from_file(str(music_path))
        voice = AudioSegment.from_wav(str(voice_path))
        
        # Drop the music volume statically by 14 decibels and overlay
        music = music - 14
        mixed = music.overlay(voice)
        
        # Crop the music to exactly match the length of the talking
        mixed = mixed[:len(voice)]
        mixed.export(str(output_path), format="wav")
        return output_path

