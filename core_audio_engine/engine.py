from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def run_pipeline(
    raw_audio: str | Path,
    music_path: str | Path,
    output_path: str | Path = "radio_show_final.wav",
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
) -> Path:
    from pydub import AudioSegment, effects
    from core_audio_engine.diarize import diarize_speakers
    from core_audio_engine.sfx import apply_sfx
    from core_audio_engine.mixer import mix_with_ducking

    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Diarize
    logger.info("Step 1/4 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )

    # Step 2: Combine both speakers BEFORE SFX analysis
    logger.info("Step 2/4 — Combining speaker tracks …")
    combined_path = output_dir / "combined_voices.wav"
    try:
        audio_a = AudioSegment.from_wav(str(host_a))
        audio_b = AudioSegment.from_wav(str(host_b))
        combined = audio_a.overlay(audio_b)
        # Normalize combined voice
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
        logger.info("Combined both speakers → %s", combined_path)
    except Exception as exc:
        logger.warning("Could not combine speakers (%s) — using host_A only", exc)
        shutil.copy(str(host_a), str(combined_path))

    # Step 3: Apply AI SFX to combined audio
    logger.info("Step 3/4 — Applying AI sound effects …")
    combined_sfx_path = output_dir / "combined_with_sfx.wav"
    try:
        apply_sfx(
            audio_path=combined_path,
            output_path=combined_sfx_path,
        )
        voice_to_mix = combined_sfx_path
    except Exception as exc:
        logger.warning("SFX step failed (%s) — using combined without SFX", exc)
        voice_to_mix = combined_path

    # Step 4: Mix with background music
    logger.info("Step 4/4 — Mixing with background music …")
    final = mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=output_path,
    )

    logger.info("Pipeline complete → %s", final)
    return final
