from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def enhance_voice(audio_path: Path, output_path: Path) -> Path:
    """
    Professional voice enhancement chain:
    1. High-pass filter — remove rumble below 80Hz
    2. Presence boost — enhance 2-4kHz for clarity
    3. Light compression — consistent levels
    4. Gentle de-essing — reduce harshness
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    filters = ",".join([
        "highpass=f=80",
        "lowpass=f=12000",
        "equalizer=f=250:width_type=o:width=2:g=-3",
        "equalizer=f=2800:width_type=o:width=2:g=4",
        "equalizer=f=5000:width_type=o:width=1:g=-2",
        "acompressor=threshold=0.08:ratio=3:attack=8:release=80:makeup=2",
    ])

    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", filters,
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0:
            logger.info("Voice enhanced → %s", output_path.name)
            return output_path.resolve()
        else:
            logger.warning("Voice enhance failed: %s", result.stderr.decode()[:200])
    except Exception as exc:
        logger.warning("Voice enhance exception: %s", exc)

    shutil.copy(str(audio_path), str(output_path))
    return output_path.resolve()


def master_audio(audio_path: Path, output_path: Path) -> Path:
    """
    Professional mastering chain:
    1. Multiband compression — even frequency balance
    2. Stereo enhancement — wider sound
    3. Loudness normalization — broadcast standard -14 LUFS
    4. True peak limiting — prevent clipping at -1dBTP
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Two-pass mastering for best results
    tmp = output_path.parent / "master_tmp.wav"

    # Pass 1: Compression + stereo
    filters_1 = ",".join([
        "acompressor=threshold=0.03:ratio=4:attack=3:release=150:makeup=3",
        "stereotools=mlev=0.02",
        "equalizer=f=100:width_type=o:width=1:g=2",
        "equalizer=f=8000:width_type=o:width=1:g=1",
    ])

    # Pass 2: Loudness normalization to -14 LUFS (podcast standard)
    filters_2 = "loudnorm=I=-14:TP=-1:LRA=11"

    try:
        # Pass 1
        r1 = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-af", filters_1,
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(tmp),
            ],
            capture_output=True, timeout=300
        )

        if r1.returncode != 0:
            raise RuntimeError("Pass 1 failed: " + r1.stderr.decode()[:200])

        # Pass 2
        r2 = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(tmp),
                "-af", filters_2,
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                str(output_path),
            ],
            capture_output=True, timeout=300
        )

        if r2.returncode != 0:
            raise RuntimeError("Pass 2 failed: " + r2.stderr.decode()[:200])

        logger.info("Mastered to -14 LUFS → %s", output_path.name)

    except Exception as exc:
        logger.warning("Mastering failed: %s — using unmastered", exc)
        shutil.copy(str(audio_path), str(output_path))
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass

    return output_path.resolve()
