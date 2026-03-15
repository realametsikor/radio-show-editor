from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from pydub import AudioSegment, effects

logger = logging.getLogger(__name__)


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    base_music_volume_db: float = -12,
    duck_ratio: float = 6.0,
    attack_ms: int = 300,
    release_ms: int = 800,
) -> Path:
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError(f"Voice not found: {voice_path}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music not found: {music_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    voice_duration_ms = len(AudioSegment.from_wav(str(voice_path)))

    # Prepare and loop music
    music = AudioSegment.from_file(str(music_path))
    while len(music) < voice_duration_ms + 8000:
        music = music + music
    music = music[:voice_duration_ms + 5000]
    music = effects.normalize(music) + base_music_volume_db
    music = music.fade_in(2000).fade_out(3000)

    tmp_music = output_path.parent / "tmp_music_mix.wav"
    music.export(str(tmp_music), format="wav")

    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_music),
            "-i", str(voice_path),
            "-filter_complex",
            f"[1:a]asplit=2[sc][mix_voice];"
            f"[0:a][sc]sidechaincompress="
            f"threshold=0.015:"
            f"ratio={duck_ratio:.1f}:"
            f"attack={attack_ms}:"
            f"release={release_ms}:"
            f"makeup=1.5[ducked_music];"
            f"[ducked_music][mix_voice]amix=inputs=2:"
            f"duration=longest:weights=1 4[out]",
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        logger.info("Professional mix complete → %s", output_path)

    except Exception as exc:
        logger.warning("ffmpeg mix failed (%s) — simple overlay", exc)
        voice = AudioSegment.from_wav(str(voice_path))
        music_trimmed = music[:len(voice)]
        combined = music_trimmed.overlay(voice)
        combined = effects.normalize(combined)
        combined.export(str(output_path), format="wav")
    finally:
        if tmp_music.exists():
            tmp_music.unlink()

    return output_path.resolve()
