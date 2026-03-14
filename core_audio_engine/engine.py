"""
engine.py — Pipeline Orchestrator
===================================
Runs the full radio-show post-production pipeline:

    1. Speaker diarization  →  host_A.wav, host_B.wav
    2. Keyword-triggered SFX →  host_A_sfx.wav
    3. Audio ducking mix     →  final radio show .wav

Usage:
    from core_audio_engine.engine import run_pipeline

    final = run_pipeline(
        raw_audio="podcast.wav",
        music_path="background_music.wav",
        output_path="radio_show_final.wav",
        output_dir="output/",
        hf_token="hf_...",
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core_audio_engine.diarize import diarize_speakers
from core_audio_engine.sfx import apply_sfx
from core_audio_engine.mixer import mix_with_ducking

logger = logging.getLogger(__name__)


def run_pipeline(
    raw_audio: str | Path,
    music_path: str | Path,
    output_path: str | Path = "radio_show_final.wav",
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
) -> Path:
    """Run the full radio-show post-production pipeline.

    Parameters
    ----------
    raw_audio : str | Path
        Path to the uploaded podcast .wav file.
    music_path : str | Path
        Path to the background music file (.wav or .mp3).
    output_path : str | Path
        Destination for the final mixed radio show .wav file.
    output_dir : str | Path
        Working directory for intermediate files (diarized tracks, etc.).
    hf_token : str, optional
        HuggingFace auth token for pyannote speaker diarization.

    Returns
    -------
    Path
        Resolved path to the final mixed .wav file.
    """
    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1: Speaker diarization
    # ------------------------------------------------------------------
    logger.info("Step 1/3 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )
    logger.info("Diarization complete: %s, %s", host_a, host_b)

    # ------------------------------------------------------------------
    # Step 2: Keyword-triggered sound effects on host A
    # ------------------------------------------------------------------
    logger.info("Step 2/3 — Applying keyword-triggered SFX …")
    host_a_sfx = output_dir / "host_A_sfx.wav"
    apply_sfx(
        audio_path=host_a,
        output_path=host_a_sfx,
    )
    logger.info("SFX applied: %s", host_a_sfx)

    # ------------------------------------------------------------------
    # Step 3: Mix voice tracks with background music (ducking)
    # ------------------------------------------------------------------
    logger.info("Step 3/3 — Mixing with background music (ducking) …")
    final = mix_with_ducking(
        voice_path=host_a_sfx,
        music_path=music_path,
        output_path=output_path,
    )
    logger.info("Pipeline complete → %s", final)

    return final
