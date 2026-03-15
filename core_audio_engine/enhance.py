from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def enhance_voice(audio_path: Path, output_path: Path) -> Path:
    """Voice enhancement — EQ boost for clarity and compression."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = ",".join([
        "highpass=f=80",
        "lowpass=f=12000",
        "equalizer=f=250:width_type=o:width=2:g=-2",
        "equalizer=f=2800:width_type=o:width=2:g=3",
        "acompressor=threshold=0.1:ratio=3:attack=5:release=60:makeup=2",
    ])

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-af", filters,
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "1",
                str(output_path),
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Voice enhanced ✅")
            return output_path.resolve()
        else:
            logger.warning("Enhance failed: %s", result.stderr.decode()[:150])
    except Exception as exc:
        logger.warning("Enhance exception: %s", exc)

    shutil.copy(str(audio_path), str(output_path))
    return output_path.resolve()


def master_audio(audio_path: Path, output_path: Path) -> Path:
    """Master to podcast broadcast standard -14 LUFS."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-af", "loudnorm=I=-14:TP=-1:LRA=11",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(output_path),
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("Mastered to -14 LUFS ✅")
            return output_path.resolve()
        else:
            logger.warning("Master failed: %s", result.stderr.decode()[:150])
    except Exception as exc:
        logger.warning("Master exception: %s", exc)

    shutil.copy(str(audio_path), str(output_path))
    return output_path.resolve()
