"""Professional radio mixer — pure pydub, no ffmpeg filter_complex.
Implements proper sidechain ducking with chunk-based voice activity detection
and AI-driven music curve automation.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)

CHUNK_MS = 50  # 50ms chunks for smooth ducking


def add_natural_pauses(audio: AudioSegment) -> AudioSegment:
    """Add micro-pauses to AI speech that has no natural breathing room."""
    try:
        thresh = audio.dBFS - 14
        nonsilent = detect_nonsilent(
            audio,
            min_silence_len=200,
            silence_thresh=thresh,
            seek_step=CHUNK_MS,
        )
        if not nonsilent or len(nonsilent) < 2:
            return audio

        result   = AudioSegment.empty()
        prev_end = 0

        for i, (start, end) in enumerate(nonsilent):
            if start > prev_end:
                gap = audio[prev_end:start]
                # Extend short gaps slightly for breathing room
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

            # Add micro-pause every 5 speech bursts
            if i > 0 and i % 5 == 0 and i < len(nonsilent) - 1:
                result += AudioSegment.silent(
                    duration=80,
                    frame_rate=audio.frame_rate,
                )
            prev_end = end

        if prev_end < len(audio):
            result += audio[prev_end:]

        logger.info("Pauses: %.1fs → %.1fs", len(audio)/1000, len(result)/1000)
        return result

    except Exception as exc:
        logger.warning("add_natural_pauses failed: %s", exc)
        return audio


def _detect_voice_activity(voice: AudioSegment, chunk_ms: int = CHUNK_MS) -> list[bool]:
    """Return list of booleans indicating voice activity per chunk."""
    thresh = voice.dBFS - 12  # 12dB below mean = silence
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


def _smooth_activity(activity: list[bool], lookahead: int = 4, lookbehind: int = 2) -> list[bool]:
    """
    Smooth voice activity to prevent rapid ducking.
    Lookahead: start ducking before voice (anticipate)
    Lookbehind: keep ducked briefly after voice ends (hold)
    """
    n      = len(activity)
    smooth = list(activity)

    # Lookahead — if voice starts soon, duck now
    for i in range(n):
        if not smooth[i]:
            for j in range(1, lookahead + 1):
                if i + j < n and activity[i + j]:
                    smooth[i] = True
                    break

    # Lookbehind — hold duck after voice ends
    for i in range(n - 1, -1, -1):
        if not smooth[i]:
            for j in range(1, lookbehind + 1):
                if i - j >= 0 and activity[i - j]:
                    smooth[i] = True
                    break

    return smooth


def _interpolate_music_curve(
    music_curve: list[dict] | None,
    total_ms: int,
    chunk_ms: int,
) -> list[float] | None:
    """
    Convert Claude AI music curve into per-chunk intensity values (0.0 - 1.0).
    Returns None if no valid curve is provided.
    """
    if not music_curve or len(music_curve) < 2:
        return None

    # Sort by timestamp and convert to ms
    points = sorted(music_curve, key=lambda p: float(p.get("timestamp", 0)))
    curve_pts = []
    for p in points:
        t_ms = int(float(p.get("timestamp", 0)) * 1000)
        intensity = max(0.0, min(1.0, float(p.get("intensity", 0.5))))
        curve_pts.append((t_ms, intensity))

    num_chunks = (total_ms + chunk_ms - 1) // chunk_ms
    intensities = []

    for i in range(num_chunks):
        pos_ms = i * chunk_ms

        # Find surrounding curve points for interpolation
        if pos_ms <= curve_pts[0][0]:
            intensities.append(curve_pts[0][1])
        elif pos_ms >= curve_pts[-1][0]:
            intensities.append(curve_pts[-1][1])
        else:
            # Linear interpolation between surrounding points
            for j in range(len(curve_pts) - 1):
                t0, v0 = curve_pts[j]
                t1, v1 = curve_pts[j + 1]
                if t0 <= pos_ms <= t1:
                    if t1 == t0:
                        intensities.append(v0)
                    else:
                        frac = (pos_ms - t0) / (t1 - t0)
                        intensities.append(v0 + frac * (v1 - v0))
                    break
            else:
                intensities.append(0.5)

    return intensities


def _loop_music_with_crossfade(
    music: AudioSegment,
    target_ms: int,
    crossfade_ms: int = 3000,
) -> AudioSegment:
    """
    Loop music to reach target_ms with smooth crossfades between loops.
    Avoids jarring hard-cut transitions.
    """
    if len(music) >= target_ms:
        return music[:target_ms]

    # Ensure crossfade doesn't exceed half the music length
    xfade = min(crossfade_ms, len(music) // 3)

    result = music
    while len(result) < target_ms:
        if xfade > 50:
            # Crossfade: overlap end of current with start of next loop
            result = result.append(music, crossfade=xfade)
        else:
            result = result + music

    return result[:target_ms]


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    music_full_db: float   = -14,   # Music volume during silence/pauses
    music_ducked_db: float = -32,   # Music volume when voice is active
    attack_ms: int         = 150,   # How fast music ducks (ms)
    release_ms: int        = 600,   # How fast music comes back (ms)
) -> Path:
    """
    Professional radio mixing with sidechain ducking and AI music curve.

    Strategy:
    - Load voice + music separately
    - Detect voice activity every 50ms
    - Use Claude AI music curve to set base music intensity over time
    - Smoothly lower music when voice is present (sidechain ducking)
    - Smoothly raise music during pauses (music breathes naturally)
    - Overlay voice on top at full volume
    - Normalize final mix
    """
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load voice ─────────────────────────────────────────────────────
    logger.info("Loading voice...")
    voice = AudioSegment.from_wav(str(voice_path))

    # Add natural pauses to AI speech
    voice = add_natural_pauses(voice)

    # Normalize voice to consistent level
    voice = effects.normalize(voice)

    voice_ms = len(voice)
    logger.info("Voice ready: %.1fs dBFS=%.1f", voice_ms/1000, voice.dBFS)

    # ── Load music ─────────────────────────────────────────────────────
    logger.info("Loading music...")
    try:
        music = AudioSegment.from_file(str(music_path))
    except Exception as exc:
        logger.warning("Music load failed: %s — exporting voice only", exc)
        if voice.channels == 1:
            voice = voice.set_channels(2)
        voice.export(str(output_path), format="wav")
        return output_path.resolve()

    # Ensure stereo music for proper spatial feel
    if music.channels == 1:
        music = music.set_channels(2)

    # Match sample rate
    if music.frame_rate != 44100:
        music = music.set_frame_rate(44100)

    # Loop music with crossfade to cover full voice + buffer
    target_music_ms = voice_ms + 10000
    music = _loop_music_with_crossfade(music, target_music_ms)

    # Normalize music
    music = effects.normalize(music)
    logger.info("Music ready: %.1fs dBFS=%.1f", len(music)/1000, music.dBFS)

    # ── Voice activity detection ───────────────────────────────────────
    logger.info("Detecting voice activity...")
    raw_activity    = _detect_voice_activity(voice, CHUNK_MS)
    smooth_activity = _smooth_activity(raw_activity, lookahead=6, lookbehind=4)

    speaking_chunks = sum(smooth_activity)
    total_chunks    = len(smooth_activity)
    logger.info(
        "Voice activity: %d/%d chunks (%.0f%% speaking)",
        speaking_chunks, total_chunks,
        100 * speaking_chunks / max(total_chunks, 1),
    )

    # ── Compute AI music curve ─────────────────────────────────────────
    curve_intensities = _interpolate_music_curve(music_curve, len(music), CHUNK_MS)
    if curve_intensities:
        logger.info("Music curve active: %d control points → %d chunk values",
                     len(music_curve), len(curve_intensities))
    else:
        logger.info("No music curve — using voice-only ducking")

    # ── Build ducked music track ───────────────────────────────────────
    logger.info("Building ducked music track...")

    attack_steps  = max(1, attack_ms  // CHUNK_MS)
    release_steps = max(1, release_ms // CHUNK_MS)
    current_db    = music_full_db

    # Pre-allocate list for efficient concatenation
    music_chunks: list[AudioSegment] = []

    for i, is_speaking in enumerate(smooth_activity):
        # Determine target dB — combine ducking with music curve
        if curve_intensities and i < len(curve_intensities):
            curve_intensity = curve_intensities[i]
            # Music curve controls the "full" level; ducking goes below that
            # Intensity 0.0 = silence, 1.0 = full music volume
            curve_db = -40 + (curve_intensity * 28)  # Range: -40dB to -12dB
            if is_speaking:
                # Duck below the curve level, but never louder than ducked_db
                target_db = min(music_ducked_db, curve_db - 18)
            else:
                target_db = curve_db
        else:
            target_db = music_ducked_db if is_speaking else music_full_db

        # Smooth transition
        if current_db > target_db:
            # Ducking — fast attack
            step       = (current_db - target_db) / attack_steps
            current_db = max(target_db, current_db - step)
        elif current_db < target_db:
            # Releasing — slower release for natural feel
            step       = (target_db - current_db) / release_steps
            current_db = min(target_db, current_db + step)

        pos_ms = i * CHUNK_MS
        if pos_ms < len(music):
            chunk = music[pos_ms:pos_ms + CHUNK_MS]
            if len(chunk) == 0:
                chunk = AudioSegment.silent(duration=CHUNK_MS, frame_rate=44100)
        else:
            chunk = AudioSegment.silent(duration=CHUNK_MS, frame_rate=44100)

        # Apply volume — convert dB target to adjustment
        if chunk.dBFS != float("-inf"):
            db_adjust = current_db - chunk.dBFS
            chunk     = chunk + db_adjust
        else:
            chunk = chunk + current_db

        music_chunks.append(chunk)

    # Efficient concatenation: batch join instead of O(n²) sum()
    ducked_music = _batch_concat(music_chunks)
    logger.info(
        "Ducked music: %.1fs dBFS=%.1f",
        len(ducked_music)/1000,
        ducked_music.dBFS,
    )

    # ── Fade music in/out ──────────────────────────────────────────────
    fade_in_ms  = 2000
    fade_out_ms = 4000
    ducked_music = ducked_music.fade_in(fade_in_ms).fade_out(fade_out_ms)

    # ── Convert voice to stereo ────────────────────────────────────────
    if voice.channels == 1:
        voice_stereo = voice.set_channels(2)
    else:
        voice_stereo = voice

    # ── Overlay voice on ducked music ──────────────────────────────────
    logger.info("Overlaying voice on ducked music...")

    # Pad music to match voice length
    if len(ducked_music) < len(voice_stereo):
        padding = AudioSegment.silent(
            duration=len(voice_stereo) - len(ducked_music),
            frame_rate=44100,
        ).set_channels(2)
        ducked_music = ducked_music + padding

    mixed = ducked_music.overlay(voice_stereo, position=0)

    # ── Final mix processing ───────────────────────────────────────────
    # Normalize to consistent level
    mixed = effects.normalize(mixed)

    logger.info(
        "Mix complete: %.1fs dBFS=%.1f max=%.1f",
        len(mixed)/1000,
        mixed.dBFS,
        mixed.max_dBFS,
    )

    mixed.export(str(output_path), format="wav")
    return output_path.resolve()


def _batch_concat(segments: list[AudioSegment], batch_size: int = 200) -> AudioSegment:
    """
    Concatenate AudioSegments efficiently using batch reduction.
    Avoids the O(n²) cost of sum(segments, AudioSegment.empty()).
    """
    if not segments:
        return AudioSegment.empty()

    # First pass: concatenate in batches
    while len(segments) > 1:
        batches = []
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i + batch_size]
            combined = batch[0]
            for seg in batch[1:]:
                combined = combined + seg
            batches.append(combined)
        segments = batches

    return segments[0]
