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
    """
    Add subtle natural pauses to AI-generated speech that has no breathing room.
    Detects silent gaps and slightly extends them for a more human feel.
    """
    from pydub.silence import detect_nonsilent

    logger.info("Adding natural pauses to AI-generated speech...")

    chunk_ms = 50
    silence_thresh = audio.dBFS - 16
    min_silence_ms = 300

    nonsilent = detect_nonsilent(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh,
        seek_step=chunk_ms,
    )

    if not nonsilent:
        return audio

    result = AudioSegment.empty()
    prev_end = 0

    for i, (start, end) in enumerate(nonsilent):
        # Add existing silence between chunks
        if start > prev_end:
            gap = audio[prev_end:start]
            # Slightly extend short gaps for more natural breathing
            if len(gap) < 400:
                gap = gap + AudioSegment.silent(
                    duration=min(200, len(gap)),
                    frame_rate=audio.frame_rate
                )
            result += gap

        chunk = audio[start:end]

        # Add very subtle fade in/out to each speech segment
        if len(chunk) > 100:
            chunk = chunk.fade_in(15).fade_out(15)

        result += chunk

        # Add micro pause between sentences (every few segments)
        if i > 0 and i % 4 == 0 and i < len(nonsilent) - 1:
            micro_pause = AudioSegment.silent(
                duration=180,
                frame_rate=audio.frame_rate
            )
            result += micro_pause

        prev_end = end

    # Add remaining audio
    if prev_end < len(audio):
        result += audio[prev_end:]

    logger.info(
        "Natural pauses added — original: %.1fs, new: %.1fs",
        len(audio) / 1000,
        len(result) / 1000,
    )
    return result


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
        raise FileNotFoundError(f"Voice not found: {voice_path}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music not found: {music_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load voice and add natural pauses
    voice = AudioSegment.from_wav(str(voice_path))
    try:
        voice = add_natural_pauses(voice)
        enhanced_voice_path = voice_path.parent / "voice_with_pauses.wav"
        voice.export(str(enhanced_voice_path), format="wav")
        voice_path = enhanced_voice_path
    except Exception as exc:
        logger.warning("Could not add natural pauses: %s", exc)

    voice_duration_ms = len(voice)

    # Load and prepare music
    music = AudioSegment.from_file(str(music_path))

    # Loop music if needed
    while len(music) < voice_duration_ms + 10000:
        music = music + music
    music = music[:voice_duration_ms + 6000]

    # Normalize then set base volume
    music = effects.normalize(music) + base_music_volume_db

    # Apply music curve if provided by Claude producer
    if music_curve and len(music_curve) >= 2:
        music = _apply_music_curve(music, music_curve, voice_duration_ms)

    # Smooth fade in/out
    music = music.fade_in(2500).fade_out(4000)

    tmp_music = output_path.parent / "tmp_music_prepared.wav"
    music.export(str(tmp_music), format="wav")

    try:
        # Professional sidechain compression ducking
        #​​​​​​​​​​​​​​​​
