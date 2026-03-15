"""Professional radio mixer — pure pydub, no ffmpeg filter_complex.
Implements proper sidechain ducking with chunk-based voice activity detection.
"""
from __future__ import annotations

import logging
import math
import shutil
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)

# Increased from 50ms → 500ms = 10x faster processing
# 500ms chunks are still smooth enough for good ducking
CHUNK_MS = 500


def add_natural_pauses(audio: AudioSegment) -> AudioSegment:
    """Add micro-pauses to AI speech that has no natural breathing room."""
    try:
        thresh    = audio.dBFS - 14
        nonsilent = detect_nonsilent(
            audio,
            min_silence_len=200,
            silence_thresh=thresh,
            seek_step=50,
        )
        if not nonsilent or len(nonsilent) < 2:
            return audio

        result   = AudioSegment.empty()
        prev_end = 0

        for i, (start, end) in enumerate(nonsilent):
            if start > prev_end:
                gap = audio[prev_end:start]
                if len(gap) < 300:
                    gap = gap + AudioSegment.silent(
                        duration=min(100, len(gap)),
                        frame_rate=audio.frame_rate,
                    )
                result += gap

            chunk = audio[start:end]
            if len(chunk) > 50:
                chunk = chunk.fade_in(5).fade_out(5)
            result += chunk

            if i > 0 and i % 5 == 0 and i < len(nonsilent) - 1:
                result += AudioSegment.silent(
                    duration=80,
                    frame_rate=audio.frame_rate,
                )
            prev_end = end

        if prev_end < len(audio):
            result += audio[prev_end:]

        logger.info("Pauses: %.1fs → %.1fs", len(audio) / 1000, len(result) / 1000)
        return result

    except Exception as exc:
        logger.warning("add_natural_pauses failed: %s", exc)
        return audio


def _detect_voice_activity(voice: AudioSegment, chunk_ms: int = CHUNK_MS) -> list[bool]:
    """Return list of booleans indicating voice activity per chunk."""
    thresh = voice.dBFS - 12
    active = []
    for i in range(0, len(voice), chunk_ms):
        chunk = voice[i:i + chunk_ms]
        is_active = (
            len(chunk) > 0
            and chunk.dBFS != float("-inf")
            and chunk.dBFS > thresh
        )
        active.append(is_active)
    return active


def _smooth_activity(
    activity: list[bool],
    lookahead: int = 2,
    lookbehind: int = 1,
) -> list[bool]:
    """Smooth voice activity — lookahead/lookbehind in chunks (500ms each)."""
    n      = len(activity)
    smooth = list(activity)

    for i in range(n):
        if not smooth[i]:
            for j in range(1, lookahead + 1):
                if i + j < n and activity[i + j]:
                    smooth[i] = True
                    break

    for i in range(n - 1, -1, -1):
        if not smooth[i]:
            for j in range(1, lookbehind + 1):
                if i - j >= 0 and activity[i - j]:
                    smooth[i] = True
                    break

    return smooth


def _loop_music_with_crossfade(
    music: AudioSegment,
    target_ms: int,
    crossfade_ms: int = 2000,
) -> AudioSegment:
    """Loop music with crossfades to avoid hard cuts."""
    if len(music) >= target_ms:
        return music[:target_ms]

    xfade  = min(crossfade_ms, len(music) // 3)
    result = music
    while len(result) < target_ms:
        result = result.append(music, crossfade=xfade) if xfade > 50 else result + music

    return result[:target_ms]


def _batch_concat(segments: list[AudioSegment], batch_size: int = 100) -> AudioSegment:
    """Efficient batch concatenation — avoids O(n²) cost."""
    if not segments:
        return AudioSegment.empty()
    while len(segments) > 1:
        batches = []
        for i in range(0, len(segments), batch_size):
            batch    = segments[i:i + batch_size]
            combined = batch[0]
            for seg in batch[1:]:
                combined = combined + seg
            batches.append(combined)
        segments = batches
    return segments[0]


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    music_full_db: float   = -30,   # FIXED: was -26, too loud. -30 = music audible but not overpowering
    music_ducked_db: float = -46,   # Music under speech — very quiet so voice is clear
    attack_ms: int         = 500,   # Match chunk size
    release_ms: int        = 1500,  # Slow release — music comes back gradually
) -> Path:
    """
    Professional radio mix with sidechain ducking.
    Music is clearly audible during pauses, quietly present during speech.
    """
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load and prepare voice
    logger.info("Loading voice...")
    voice = AudioSegment.from_wav(str(voice_path))
    voice = effects.normalize(voice)
    voice_ms = len(voice)
    logger.info("Voice: %.1fs dBFS=%.1f", voice_ms / 1000, voice.dBFS)

    # Load and prepare music
    logger.info("Loading music...")
    try:
        music = AudioSegment.from_file(str(music_path))
    except Exception as exc:
        logger.warning("Music load failed: %s — voice only", exc)
        voice.set_channels(2).export(str(output_path), format="wav")
        return output_path.resolve()

    if music.channels == 1:
        music = music.set_channels(2)
    if music.frame_rate != 44100:
        music = music.set_frame_rate(44100)

    music = _loop_music_with_crossfade(music, voice_ms + 12000)
    music = effects.normalize(music)
    logger.info("Music: %.1fs dBFS=%.1f", len(music) / 1000, music.dBFS)

    # Voice activity detection
    logger.info("Detecting voice activity (chunk=%dms)...", CHUNK_MS)
    raw_activity    = _detect_voice_activity(voice, CHUNK_MS)
    smooth_activity = _smooth_activity(raw_activity, lookahead=2, lookbehind=1)

    n_speaking = sum(smooth_activity)
    n_total    = len(smooth_activity)
    logger.info(
        "Activity: %d/%d chunks speaking (%.0f%%), %d silent",
        n_speaking, n_total,
        100 * n_speaking / max(n_total, 1),
        n_total - n_speaking,
    )

    # Detect silence gaps for music swells
    swell_boost     = [0.0] * len(smooth_activity)
    MIN_GAP_CHUNKS  = max(1, int(2000 / CHUNK_MS))   # 2s min gap for swell
    SWELL_MAX_DB    = 8.0                              # max boost during swell

    i = 0
    while i < len(smooth_activity):
        if not smooth_activity[i]:
            gap_start = i
            while i < len(smooth_activity) and not smooth_activity[i]:
                i += 1
            gap_end = i
            gap_len = gap_end - gap_start

            if gap_len >= MIN_GAP_CHUNKS:
                for j in range(gap_len):
                    t     = j / max(gap_len - 1, 1)
                    boost = SWELL_MAX_DB * math.sin(t * math.pi)
                    idx   = gap_start + j
                    if idx < len(swell_boost):
                        swell_boost[idx] = boost
        else:
            i += 1

    # Build ducked music
    logger.info("Building ducked music (%d chunks)...", len(smooth_activity))
    attack_steps  = max(1, attack_ms  // CHUNK_MS)
    release_steps = max(1, release_ms // CHUNK_MS)
    current_db    = music_full_db
    music_chunks: list[AudioSegment] = []

    for i, is_speaking in enumerate(smooth_activity):
        target_db = music_ducked_db if is_speaking else music_full_db

        # Apply swell boost during silence
        if not is_speaking and i < len(swell_boost) and swell_boost[i] > 0:
            target_db = min(target_db + swell_boost[i], music_full_db + 3)

        # Smooth transition
        if current_db > target_db:
            step       = (current_db - target_db) / attack_steps
            current_db = max(target_db, current_db - step)
        elif current_db < target_db:
            step       = (target_db - current_db) / release_steps
            current_db = min(target_db, current_db + step)

        pos_ms = i * CHUNK_MS
        chunk  = (
            music[pos_ms:pos_ms + CHUNK_MS]
            if pos_ms < len(music)
            else AudioSegment.silent(duration=CHUNK_MS, frame_rate=44100)
        )
        if len(chunk) == 0:
            chunk = AudioSegment.silent(duration=CHUNK_MS, frame_rate=44100)

        if chunk.dBFS != float("-inf"):
            chunk = chunk + (current_db - chunk.dBFS)
        else:
            chunk = chunk + current_db

        music_chunks.append(chunk)

    ducked_music = _batch_concat(music_chunks)
    logger.info("Ducked music: dBFS=%.1f", ducked_music.dBFS)

    # Fade in/out
    ducked_music = ducked_music.fade_in(2000).fade_out(4000)

    # Convert voice to stereo
    voice_stereo = voice.set_channels(2) if voice.channels == 1 else voice

    # Pad if needed
    if len(ducked_music) < len(voice_stereo):
        ducked_music = ducked_music + AudioSegment.silent(
            duration=len(voice_stereo) - len(ducked_music),
            frame_rate=44100,
        ).set_channels(2)

    # Overlay voice on music
    mixed = ducked_music.overlay(voice_stereo, position=0)
    mixed = effects.normalize(mixed)

    logger.info(
        "Mix done: %.1fs dBFS=%.1f max=%.1f",
        len(mixed) / 1000,
        mixed.dBFS,
        mixed.max_dBFS,
    )

    mixed.export(str(output_path), format="wav")
    return output_path.resolve()
