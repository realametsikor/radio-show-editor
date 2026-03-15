"""
Professional voice enhancement and audio mastering.
*** OPTIMIZED FOR NOTEBOOKLM AUDIO ***
Bypasses heavy EQ and compression to preserve the natural, 
studio-grade mastering already applied by Google's AI.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def enhance_voice(audio_path: Path, output_path: Path) -> Path:
    """
    Bypassed for NotebookLM.
    Google's AI already applies perfect EQ, compression, and noise gating.
    We simply pass the pristine audio directly to the next stage.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("Skipping voice enhancement — preserving NotebookLM quality.")
    shutil.copy(str(audio_path), str(output_path))
    
    return output_path.resolve()


def master_audio(audio_path: Path, output_path: Path) -> Path:
    """
    Bypassed for NotebookLM.
    The mix from mixer.py is already perfectly balanced. 
    Applying a second limiter/compressor will cause distortion.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info("Skipping final master — preserving natural mix dynamics.")
    shutil.copy(str(audio_path), str(output_path))
    
    return output_path.resolve()

