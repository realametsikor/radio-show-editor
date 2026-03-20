"""enhance.py — Vocal EQ, dynamics processing, and format filtering."""
from __future__ import annotations

import logging
import subprocess
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

def enhance_voice(audio_path: str | Path, output_path: str | Path) -> Path:
    """
    Applies light, transparent leveling to the speaker's voice track.
    (NotebookLM audio is already highly processed, so we avoid heavy EQ here).
    """
    audio_path = Path(audio_path)
    output_path = Path(output_path)
    
    logger.info(f"Applying transparent studio leveler to track: {output_path.name}")
    
    # Just a gentle compressor to catch stray peaks. No heavy Bass/Treble boosts.
    eq_filter = (
        "acompressor=threshold=-15dB:ratio=2:attack=10:release=100:makeup=2dB,"
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
    logger.info("Applying final safety limiter to assembled mix...")
    pre_master = Path(pre_master)
    output_path = Path(output_path)
    
    master_filter = "alimiter=limit=-1.5dB:level_in=1:level_out=1"
    
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
