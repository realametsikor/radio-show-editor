from __future__ import annotations

import logging
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects

logger = logging.getLogger(__name__)


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

        result    = AudioSegment.empty()
        prev_end  = 0

        for i, (start, end) in enumerate(nonsilent):
            if start > prev_end:
                gap = audio[prev_end:start]
                if len(gap) < 400:
                    gap = gap + AudioSegment.silent(
                        duration=min(150, len(gap)),
                        frame_rate=audio.frame_rate,
                    )
                result += gap

            chunk = audio[start:end]
            if len(chunk) > 100:
                chunk = chunk.fade_in(10).fade_out(10)
            result += chunk

            if i > 0 and i % 5 == 0 and i < len(nonsilent) - 1:
                result += AudioSegment.silent(
                    duration=120,
                    frame_rate=audio.frame_rate,
                )
            prev_end = end

        if prev_end < len(audio):
            result += audio[prev_end:]

        logger.info(
            "Pauses added: %.1fs → %.1fs",
            len(audio) / 1000, len(result) / 1000
        )
        return result
    except Exception as exc:
        logger.warning("add_natural_pauses failed: %s", exc)
        return audio


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    base_music_volume_db: float = -12,
    duck_ratio: float = 6.0,
    attack_ms: int = 300,
    release_ms: int = 1200,
) -> Path:
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load voice
    voice = AudioSegment.from_wav(str(voice_path))

    # Add natural pauses
    try:
        voice = add_natural_pauses(voice)
        paused_path = voice_path.parent / "voice_paused.wav"
        voice.export(str(paused_path), format="wav")
        voice_to_use = paused_path
    except Exception as exc:
        logger.warning("Pause injection failed: %s", exc)
        voice_to_use = voice_path

    voice_duration_ms = len(voice)

    # Load music
    try:
        music = AudioSegment.from_file(str(music_path))
    except Exception as exc:
        logger.warning("Music load failed: %s — voice only output", exc)
        voice.export(str(output_path), format="wav")
        return output_path.resolve()

    # Loop music to be longer than voice
    while len(music) < voice_duration_ms + 15000:
        music = music + music
    music = music[:voice_duration_ms + 8000]

    # Normalize music then set volume
    # -12dB means music is clearly audible but voice dominates
    music = effects.normalize(music) + base_music_volume_db

    # Smooth fades
    music = music.fade_in(3000).fade_out(5000)

    tmp_music = output_path.parent / "tmp_music.wav"
    music.export(str(tmp_music), format="wav")

    # Try professional ffmpeg sidechain ducking
    ffmpeg_ok = False
    try:
        filter_complex = (
            "[1:a]asplit=2[sc][vox];"
            "[0:a][sc]sidechaincompress="
            "threshold=0.02:"
            "ratio=" + str(duck_ratio) + ":"
            "attack=" + str(attack_ms) + ":"
            "release=" + str(release_ms) + ":"
            "makeup=1[ducked];"
            "[ducked][vox]amix=inputs=2:duration=longest:weights=1 3[out]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_music),
            "-i", str(voice_to_use),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            ffmpeg_ok = True
            logger.info("ffmpeg sidechain mix complete")
        else:
            logger.warning("ffmpeg failed: %s", result.stderr.decode()[:300])
    except Exception as exc:
        logger.warning("ffmpeg exception: %s", exc)

    # Fallback: pydub overlay
    if not ffmpeg_ok:
        try:
            logger.info("Using pydub overlay fallback")
            voice_audio   = AudioSegment.from_wav(str(voice_to_use))
            music_trimmed = music[:len(voice_audio) + 4000]
            # Simple mix: lay music under voice
            combined = music_trimmed.overlay(voice_audio)
            combined = effects.normalize(combined)
            combined.export(str(output_path), format="wav")
            logger.info("pydub overlay complete")
            ffmpeg_ok = True
        except Exception as exc:
            logger.warning("pydub fallback failed: %s", exc)

    # Last resort: voice only
    if not ffmpeg_ok:
        shutil.copy(str(voice_to_use), str(output_path))
        logger.warning("Last resort: voice only — no music")

    try:
        tmp_music.unlink()
    except Exception:
        pass

    return output_path.resolve()
