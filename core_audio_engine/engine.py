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
    from pydub import AudioSegment

    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Diarize
    logger.info("Step 1/3 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )

    # Step 2: SFX on host A (skip if SFX files missing)
    logger.info("Step 2/3 — Applying SFX …")
    host_a_sfx = output_dir / "host_A_sfx.wav"
    try:
        apply_sfx(audio_path=host_a, output_path=host_a_sfx)
    except Exception as exc:
        logger.warning("SFX step failed (%s) — using original host_A audio", exc)
        import shutil
        shutil.copy(str(host_a), str(host_a_sfx))

    # Step 3: Combine both speakers into one track
    logger.info("Combining speaker tracks …")
    combined_path = output_dir / "combined_voices.wav"
    try:
        audio_a = AudioSegment.from_wav(str(host_a_sfx))
        audio_b = AudioSegment.from_wav(str(host_b))
        # Overlay both speakers to preserve both voices
        combined = audio_a.overlay(audio_b)
        combined.export(str(combined_path), format="wav")
        voice_to_mix = combined_path
        logger.info("Combined both speakers → %s", combined_path)
    except Exception as exc:
        logger.warning("Could not combine speakers (%s) — using host_A only", exc)
        voice_to_mix = host_a_sfx

    # Step 4: Mix with background music
    logger.info("Step 3/3 — Mixing with background music …")
    final = mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=output_path,
    )

    return final
