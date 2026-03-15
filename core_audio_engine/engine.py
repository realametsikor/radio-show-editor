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
    from core_audio_engine.sfx import apply_sfx, generate_intro, generate_outro
    from core_audio_engine.mixer import mix_with_ducking

    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Diarize
    logger.info("Step 1/5 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )

    # Step 2: Combine both speakers
    logger.info("Step 2/5 — Combining speaker tracks …")
    combined_path = output_dir / "combined_voices.wav"
    try:
        audio_a = AudioSegment.from_wav(str(host_a))
        audio_b = AudioSegment.from_wav(str(host_b))
        combined = audio_a.overlay(audio_b)
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
    except Exception as exc:
        logger.warning("Could not combine speakers: %s", exc)
        shutil.copy(str(host_a), str(combined_path))

    # Step 3: Apply AI SFX
    logger.info("Step 3/5 — Applying AI sound effects …")
    combined_sfx_path = output_dir / "combined_with_sfx.wav"
    try:
        apply_sfx(audio_path=combined_path, output_path=combined_sfx_path)
        voice_to_mix = combined_sfx_path
    except Exception as exc:
        logger.warning("SFX failed: %s", exc)
        voice_to_mix = combined_path

    # Step 4: Mix with background music
    logger.info("Step 4/5 — Mixing with background music …")
    mixed_path = output_dir / "mixed.wav"
    mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=mixed_path,
    )

    # Step 5: Add intro and outro
    logger.info("Step 5/5 — Adding intro and outro …")
    try:
        mixed = AudioSegment.from_wav(str(mixed_path))

        intro = generate_intro(duration_ms=3000)
        outro = generate_outro(duration_ms=3000)

        # 1s silence between intro and content
        gap = AudioSegment.silent(duration=800)

        final_audio = intro + gap + mixed + gap + outro
        final_audio = effects.normalize(final_audio)
        final_audio.export(str(output_path), format="wav")
        logger.info("Added intro/outro → final duration: %.1fs", len(final_audio) / 1000)
    except Exception as exc:
        logger.warning("Intro/outro failed: %s", exc)
        shutil.copy(str(mixed_path), str(output_path))

    return output_path.resolve()
