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
    *,
    music_volume_db: float = -22,
    duck_amount_db: float = 30,
    attack_s: float = 0.2,
    release_s: float = 0.6,
) -> Path:
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError(f"Voice file not found: {voice_path}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music file not found: {music_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    voice_duration_ms = len(AudioSegment.from_wav(str(voice_path)))

    # Load and prepare music
    music = AudioSegment.from_file(str(music_path))

    # Loop music if shorter than voice
    while len(music) < voice_duration_ms + 5000:
        music = music + music
    music = music[:voice_duration_ms + 3000]

    # Normalize then reduce music volume significantly
    music = effects.normalize(music) + music_volume_db

    # Fade music in/out
    music = music.fade_in(2000).fade_out(3000)

    # Export temp files for ffmpeg
    tmp_music = output_path.parent / "tmp_music.wav"
    music.export(str(tmp_music), format="wav")

    # Use ffmpeg sidechaincompress for proper ducking
    try:
        ratio = max(3.0, duck_amount_db / 3.0)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_music),
            "-i", str(voice_path),
            "-filter_complex",
            f"[1:a]asplit=2[sc][mix_voice];"
            f"[0:a][sc]sidechaincompress="
            f"threshold=0.02:ratio={ratio:.1f}:"
            f"attack={int(attack_s*1000)}:release={int(release_s*1000)}:"
            f"makeup=1[ducked_music];"
            f"[ducked_music][mix_voice]amix=inputs=2:duration=longest:weights=1 3[out]",
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())

        logger.info("Mix complete → %s", output_path)

    except Exception as exc:
        logger.warning("ffmpeg ducking failed (%s) — using simple overlay", exc)
        # Fallback: simple overlay without ducking
        voice = AudioSegment.from_wav(str(voice_path))
        combined = music.overlay(voice)
        combined = effects.normalize(combined)
        combined.export(str(output_path), format="wav")
    finally:
        if tmp_music.exists():
            tmp_music.unlink()

    return output_path.resolve()
