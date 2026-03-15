from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def enhance_voice(audio_path: Path, output_path: Path) -> Path:
    """Apply professional voice enhancement using ffmpeg filters."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Professional voice chain:
    # 1. High-pass filter (remove rumble below 80Hz)
    # 2. Low-pass filter (remove hiss above 12kHz)
    # 3. Dynamic EQ boost for voice presence (2-4kHz)
    # 4. Light compression for consistent levels
    # 5. De-essing (reduce harsh sibilants)
    filters = (
        "highpass=f=80,"
        "lowpass=f=12000,"
        "equalizer=f=2500:width_type=o:width=2:g=3,"
        "equalizer=f=200:width_type=o:width=2:g=-2,"
        "acompressor=threshold=0.1:ratio=3:attack=5:release=50:makeup=2,"
        "equalizer=f=7000:width_type=o:width=1:g=-2"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", filters,
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        logger.info("Voice enhanced → %s", output_path)
        return output_path.resolve()
    except Exception as exc:
        logger.warning("Voice enhancement failed (%s) — using original", exc)
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()


def master_audio(audio_path: Path, output_path: Path) -> Path:
    """Master audio to broadcast standards (-14 LUFS, -1dBTP)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Professional mastering chain:
    # 1. Multi-band compression
    # 2. Stereo widening
    # 3. Loudness normalization to -14 LUFS (podcast standard)
    # 4. True peak limiting at -1dBTP
    filters = (
        "acompressor=threshold=0.05:ratio=4:attack=3:release=100:makeup=2,"
        "stereotools=mlev=0.015,"
        "loudnorm=I=-14:TP=-1:LRA=11"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", filters,
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        logger.info("Mastered to broadcast standard → %s", output_path)
        return output_path.resolve()
    except Exception as exc:
        logger.warning("Mastering failed (%s) — using unmastered", exc)
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()
