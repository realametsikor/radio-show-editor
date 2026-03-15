from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects

logger = logging.getLogger(__name__)


def _db_to_amplitude(db: float) -> float:
    return 10 ** (db / 20.0)


def add_natural_pauses(audio: AudioSegment) -> AudioSegment:
    """Add subtle natural pauses to AI-generated speech."""
    try:
        from pydub.silence import detect_nonsilent

        silence_thresh = audio.dBFS - 16
        nonsilent = detect_nonsilent(
            audio,
            min_silence_len=300,
            silence_thresh=silence_thresh,
            seek_step=50,
        )

        if not nonsilent:
            return audio

        result = AudioSegment.empty()
        prev_end = 0

        for i, (start, end) in enumerate(nonsilent):
            if start > prev_end:
                gap = audio[prev_end:start]
                if len(gap) < 400:
                    gap = gap + AudioSegment.silent(
                        duration=min(200, len(gap)),
                        frame_rate=audio.frame_rate,
                    )
                result += gap

            chunk = audio[start:end]
            if len(chunk) > 100:
                chunk = chunk.fade_in(15).fade_out(15)
            result += chunk

            if i > 0 and i % 4 == 0 and i < len(nonsilent) - 1:
                result += AudioSegment.silent(
                    duration=180,
                    frame_rate=audio.frame_rate,
                )

            prev_end = end

        if prev_end < len(audio):
            result += audio[prev_end:]

        logger.info(
            "Natural pauses added — original: %.1fs, new: %.1fs",
            len(audio) / 1000,
            len(result) / 1000,
        )
        return result

    except Exception as exc:
        logger.warning("add_natural_pauses failed: %s", exc)
        return audio


def _apply_music_curve(
    music: AudioSegment,
    curve: list[dict],
    voice_duration_ms: int,
) -> AudioSegment:
    """Apply Claude's music intensity curve to the music track."""
    try:
        result = AudioSegment.empty()
        sorted_curve = sorted(curve, key=lambda x: x.get("timestamp", 0))

        for i in range(len(sorted_curve) - 1):
            point      = sorted_curve[i]
            next_point = sorted_curve[i + 1]

            start_ms  = int(point.get("timestamp", 0) * 1000)
            end_ms    = int(next_point.get("timestamp", 0) * 1000)
            intensity = float(point.get("intensity", 0.15))

            if end_ms <= start_ms:
                continue

            segment = music[start_ms:end_ms]
            if len(segment) == 0:
                continue

            if intensity <= 0:
                db_adjust = -60
            else:
                db_adjust = 20 * (intensity - 1.0) * 2

            segment = segment + db_adjust
            result += segment

        last_ts = int(sorted_curve[-1].get("timestamp", 0) * 1000)
        if last_ts < len(music):
            result += music[last_ts:]

        if len(result) > 0:
            logger.info("Music curve applied — %d control points", len(curve))
            return result

    except Exception as exc:
        logger.warning("Music curve failed: %s", exc)

    return music


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    base_music_volume_db: float = -16,
    duck_ratio: float = 8.0,
    attack_ms: int = 200,
    release_ms: int = 1000,
) -> Path:
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Add natural pauses to voice
    try:
        voice = AudioSegment.from_wav(str(voice_path))
        voice = add_natural_pauses(voice)
        enhanced_voice_path = voice_path.parent / "voice_with_pauses.wav"
        voice.export(str(enhanced_voice_path), format="wav")
        voice_to_use = enhanced_voice_path
        logger.info("Natural pauses added to voice")
    except Exception as exc:
        logger.warning("Could not add natural pauses: %s", exc)
        voice_to_use = voice_path
        voice = AudioSegment.from_wav(str(voice_path))

    voice_duration_ms = len(voice)

    # Load and prepare music
    try:
        music = AudioSegment.from_file(str(music_path))
    except Exception as exc:
        logger.warning("Could not load music file: %s", exc)
        voice.export(str(output_path), format="wav")
        return output_path.resolve()

    # Loop music if shorter than voice
    while len(music) < voice_duration_ms + 10000:
        music = music + music
    music = music[:voice_duration_ms + 6000]

    # Normalize then reduce volume
    music = effects.normalize(music) + base_music_volume_db

    # Apply Claude's music curve if provided
    if music_curve and len(music_curve) >= 2:
        music = _apply_music_curve(music, music_curve, voice_duration_ms)

    # Smooth fade in/out
    music = music.fade_in(2500).fade_out(4000)

    tmp_music = output_path.parent / "tmp_music_prepared.wav"
    music.export(str(tmp_music), format="wav")

    # Try ffmpeg sidechain ducking first
    ffmpeg_success = False
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_music),
            "-i", str(voice_to_use),
            "-filter_complex",
            (
                "[1:a]asplit=2[sc][mix_voice];"
                "[0:a][sc]sidechaincompress="
                "threshold=0.01:"
                "ratio=" + str(duck_ratio) + ":"
                "attack=" + str(attack_ms) + ":"
                "release=" + str(release_ms) + ":"
                "makeup=1.2[ducked_music];"
                "[ducked_music][mix_voice]amix="
                "inputs=2:"
                "duration=longest:"
                "weights=1 4[out]"
            ),
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            ffmpeg_success = True
            logger.info("Professional ducking mix complete")
        else:
            logger.warning("ffmpeg ducking failed: %s", result.stderr.decode()[:200])
    except Exception as exc:
        logger.warning("ffmpeg exception: %s", exc)

    # Fallback: simple pydub overlay
    if not ffmpeg_success:
        try:
            logger.info("Using pydub fallback mixer")
            voice_audio   = AudioSegment.from_wav(str(voice_to_use))
            music_trimmed = music[:len(voice_audio) + 3000]
            combined      = music_trimmed.overlay(voice_audio)
            combined      = effects.normalize(combined)
            combined.export(str(output_path), format="wav")
            logger.info("Pydub fallback mix complete")
        except Exception as exc:
            logger.warning("Pydub fallback failed: %s", exc)
            # Last resort: just use voice without music
            import shutil
            shutil.copy(str(voice_to_use), str(output_path))
            logger.info("Last resort: voice only (no music)")

    # Cleanup temp file
    try:
        if tmp_music.exists():
            tmp_music.unlink()
    except Exception:
        pass

    return output_path.resolve()
