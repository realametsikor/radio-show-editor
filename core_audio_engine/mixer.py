from __future__ import annotations

import logging
from pathlib import Path

import ffmpeg

logger = logging.getLogger(__name__)


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    *,
    silence_threshold_db: float = -30,
    duck_amount_db: float = 26,
    attack_s: float = 0.3,
    release_s: float = 0.8,
    music_volume_db: float = -18,
) -> Path:
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError(f"Voice file not found: {voice_path}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music file not found: {music_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Mixing '%s' with music '%s' → '%s'", voice_path, music_path, output_path)

    try:
        voice_input = ffmpeg.input(str(voice_path))
        # Lower music volume significantly before ducking
        music_input = ffmpeg.input(str(music_path)).audio.filter(
            "volume", f"{music_volume_db}dB"
        )

        ratio = max(2.0, duck_amount_db / 3.0)

        ducked_music = ffmpeg.filter(
            [music_input, voice_input],
            "sidechaincompress",
            level_in=1,
            threshold=f"{_db_to_amplitude(silence_threshold_db):.6f}",
            ratio=ratio,
            attack=attack_s * 1000,
            release=release_s * 1000,
        )

        voice_for_mix = ffmpeg.input(str(voice_path))

        mixed = ffmpeg.filter(
            [ducked_music, voice_for_mix],
            "amix",
            inputs=2,
            duration="longest",
            weights="1 2",  # boost voice over music
        )

        (
            mixed
            .output(str(output_path), acodec="pcm_s16le", ar=44100, ac=2)
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as exc:
        stderr_output = exc.stderr.decode() if exc.stderr else "no stderr"
        raise RuntimeError(f"ffmpeg failed: {stderr_output}") from exc

    logger.info("Mix complete → %s", output_path)
    return output_path.resolve()


def _db_to_amplitude(db: float) -> float:
    return 10 ** (db / 20.0)
