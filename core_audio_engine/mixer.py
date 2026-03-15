from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)


def add_natural_pauses(audio: AudioSegment) -> AudioSegment:
    """Add subtle breathing room to AI-generated speech."""
    try:
        silence_thresh = audio.dBFS - 14
        nonsilent = detect_nonsilent(
            audio,
            min_silence_len=250,
            silence_thresh=silence_thresh,
            seek_step=50,
        )
        if not nonsilent or len(nonsilent) < 2:
            return audio

        result   = AudioSegment.empty()
        prev_end = 0

        for i, (start, end) in enumerate(nonsilent):
            # Add existing gap with slight extension
            if start > prev_end:
                gap = audio[prev_end:start]
                if len(gap) < 350:
                    gap = gap + AudioSegment.silent(
                        duration=min(120, len(gap)),
                        frame_rate=audio.frame_rate,
                    )
                result += gap

            chunk = audio[start:end]
            if len(chunk) > 80:
                chunk = chunk.fade_in(8).fade_out(8)
            result += chunk

            # Micro pause every 4 speech segments
            if i > 0 and i % 4 == 0 and i < len(nonsilent) - 1:
                result += AudioSegment.silent(
                    duration=100,
                    frame_rate=audio.frame_rate,
                )
            prev_end = end

        if prev_end < len(audio):
            result += audio[prev_end:]

        logger.info(
            "Pauses: %.1fs → %.1fs",
            len(audio) / 1000,
            len(result) / 1000,
        )
        return result

    except Exception as exc:
        logger.warning("add_natural_pauses failed: %s", exc)
        return audio


def _duck_music_under_voice(
    music: AudioSegment,
    voice: AudioSegment,
    *,
    music_volume_db: float = -18,
    ducked_volume_db: float = -32,
    silence_thresh_offset: float = -14,
    attack_ms: int = 200,
    release_ms: int = 600,
) -> AudioSegment:
    """
    Pure pydub manual ducking:
    - When voice is speaking: music drops to ducked_volume_db
    - When voice is silent: music rises to music_volume_db
    - Smooth transitions between states
    """
    chunk_ms     = 100   # Process in 100ms chunks
    total_ms     = max(len(music), len(voice))
    voice_thresh = voice.dBFS + silence_thresh_offset

    # Detect voice activity
    voice_active: list[bool] = []
    for i in range(0, total_ms, chunk_ms):
        chunk = voice[i:i + chunk_ms] if i < len(voice) else AudioSegment.silent(duration=chunk_ms)
        voice_active.append(len(chunk) > 0 and chunk.dBFS > voice_thresh)

    # Build music with dynamic volume
    result = AudioSegment.silent(duration=total_ms, frame_rate=44100)

    current_db    = music_volume_db
    target_db     = music_volume_db
    attack_steps  = max(1, attack_ms  // chunk_ms)
    release_steps = max(1, release_ms // chunk_ms)

    for i, is_speaking in enumerate(voice_active):
        pos_ms = i * chunk_ms

        # Set target volume
        target_db = ducked_volume_db if is_speaking else music_volume_db

        # Smooth transition
        if target_db < current_db:
            step      = (target_db - current_db) / attack_steps
            current_db = max(target_db, current_db + step)
        elif target_db > current_db:
            step      = (target_db - current_db) / release_steps
            current_db = min(target_db, current_db + step)

        # Get music chunk
        if pos_ms < len(music):
            chunk = music[pos_ms:pos_ms + chunk_ms]
            if len(chunk) < chunk_ms:
                chunk = chunk + AudioSegment.silent(
                    duration=chunk_ms - len(chunk),
                    frame_rate=music.frame_rate,
                )
        else:
            chunk = AudioSegment.silent(duration=chunk_ms, frame_rate=44100)

        # Apply volume
        db_diff = current_db - chunk.dBFS if chunk.dBFS != float("-inf") else 0
        chunk   = chunk + db_diff
        result  = result.overlay(chunk, position=pos_ms)

    return result


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    base_music_volume_db: float = -18,
    ducked_music_volume_db: float = -34,
    attack_ms: int = 200,
    release_ms: int = 800,
) -> Path:
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading voice and music...")

    # Load voice
    voice = AudioSegment.from_wav(str(voice_path))

    # Add natural pauses
    try:
        voice = add_natural_pauses(voice)
        logger.info("Natural pauses added")
    except Exception as exc:
        logger.warning("Pauses failed: %s", exc)

    voice_duration_ms = len(voice)

    # Load music
    try:
        music = AudioSegment.from_file(str(music_path))
        logger.info("Music loaded: %.1fs", len(music) / 1000)
    except Exception as exc:
        logger.warning("Music load failed: %s — voice only", exc)
        voice = effects.normalize(voice)
        voice.export(str(output_path), format="wav")
        return output_path.resolve()

    # Convert to stereo if mono
    if music.channels == 1:
        music = music.set_channels(2)

    # Loop music to cover full voice duration + buffer
    while len(music) < voice_duration_ms + 10000:
        music = music + music
    music = music[:voice_duration_ms + 8000]

    # Normalize music
    music = effects.normalize(music)

    logger.info(
        "Starting manual ducking mix — voice: %.1fs, music: %.1fs",
        voice_duration_ms / 1000,
        len(music) / 1000,
    )

    # Apply manual ducking
    try:
        ducked_music = _duck_music_under_voice(
            music,
            voice,
            music_volume_db=base_music_volume_db,
            ducked_volume_db=ducked_music_volume_db,
            attack_ms=attack_ms,
            release_ms=release_ms,
        )
        logger.info("Ducking applied ✅")
    except Exception as exc:
        logger.warning("Ducking failed: %s — using simple volume reduction", exc)
        ducked_music = music + base_music_volume_db

    # Fade music in/out
    ducked_music = ducked_music.fade_in(2000).fade_out(4000)

    # Convert voice to stereo for mixing
    if voice.channels == 1:
        voice_stereo = voice.set_channels(2)
    else:
        voice_stereo = voice

    # Overlay voice on top of ducked music
    total_duration_ms = max(len(ducked_music), len(voice_stereo))
    if len(ducked_music) < total_duration_ms:
        ducked_music = ducked_music + AudioSegment.silent(
            duration=total_duration_ms - len(ducked_music),
            frame_rate=44100,
            channels=2,
        )

    mixed = ducked_music.overlay(voice_stereo, position=0)

    # Normalize final mix
    mixed = effects.normalize(mixed)

    # Export
    mixed.export(str(output_path), format="wav")
    logger.info(
        "Mix complete → %.1fs, dBFS=%.1f",
        len(mixed) / 1000,
        mixed.dBFS,
    )

    return output_path.resolve()
