"""enhance.py — Vocal EQ, dynamics processing, and format filtering."""
from __future__ import annotations

import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

def enhance_voice(audio_path: str | Path, output_path: str | Path) -> Path:
    """
    Applies a Premium NPR/BBC Broadcast Vocal Chain.
    Adds warmth, clarity, and controlled compression to the raw AI voices.
    """
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    
    logger.info(f"Applying Premium Broadcast Vocal Chain to: {output_path.name}")
    
    # 1. Highpass (f=80): Cuts out invisible sub-bass rumble
    # 2. Bass (g=2, f=150): Adds gentle warmth and authority to the voice
    # 3. Treble (g=1.5, f=6000): Adds a subtle crispness for intelligibility
    # 4. Compressor: Smooths out loud and quiet words automatically
    eq_filter = (
        "highpass=f=80,"
        "bass=g=2:f=150:w=0.5,"
        "treble=g=1.5:f=6000:w=0.5,"
        "acompressor=threshold=-16dB:ratio=2.5:attack=10:release=150:makeup=3dB,"
        "aformat=sample_rates=16000"
    )

    try:
        subprocess.run([
            "ffmpeg", "-i", str(audio_path),
            "-af", eq_filter,
            "-ac", "1",           
            "-y", str(output_path)
        ], check=True, capture_output=True)
        return output_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Voice enhancement failed for {audio_path.name}: {e}")
        shutil.copy(str(audio_path), str(output_path))
        return output_path


def master_audio(pre_master: str | Path, output_path: str | Path) -> Path:
    """Safety limiter for the engine assembly phase."""
    logger.info("Applying engine safety limiter...")
    pre_master = Path(pre_master)
    output_path = Path(output_path)
    
    master_filter = "alimiter=limit=-1.0dB:level_in=1:level_out=1"
    
    try:
        subprocess.run([
            "ffmpeg", "-i", str(pre_master),
            "-af", master_filter,
            "-y", str(output_path)
        ], check=True, capture_output=True)
        return output_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Mastering limiter failed: {e}")
        shutil.copy(str(pre_master), str(output_path))
        return output_path
