from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects, generators

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SFX Generation — subtle and professional
# ---------------------------------------------------------------------------

def _tone(freq: float, ms: int, vol: float = 0.3) -> AudioSegment:
    t = generators.Sine(freq).to_audio_segment(duration=ms)
    return t + (20 * (vol - 1))


def _gen_applause() -> AudioSegment:
    """Warm, natural-sounding applause — not too long."""
    import random
    base = AudioSegment.silent(duration=2000)
    for i in range(0, 1800, 30):
        freq  = random.randint(800, 2800)
        burst = generators.WhiteNoise().to_audio_segment(duration=22) - 22
        base  = base.overlay(burst, position=i)
    # Natural swell shape
    return base.fade_in(400).fade_out(700) - 3


def _gen_laugh() -> AudioSegment:
    """Subtle laugh track — warm not canned."""
    base = AudioSegment.silent(duration=1400)
    for i, freq in enumerate([260, 300, 340, 320, 280]):
        t     = _tone(freq, 160, 0.28)
        noise = generators.WhiteNoise().to_audio_segment(duration=160) - 30
        base  = base.overlay(t.overlay(noise), position=i * 190)
    return base.fade_in(100).fade_out(500) - 4


def _gen_dramatic() -> AudioSegment:
    """Deep cinematic sting — subtle tension builder."""
    base = AudioSegment.silent(duration=1800)
    for freq, vol in [(55, 0.55), (82, 0.38), (110, 0.22)]:
        t    = _tone(freq, 1600, vol)
        base = base.overlay(t)
    return base.fade_in(200).fade_out(800) - 2


def _gen_cash() -> AudioSegment:
    """Clean coin/register sound."""
    base = AudioSegment.silent(duration=500)
    for i, (freq, vol) in enumerate([(1318, 0.65), (1760, 0.45), (2093, 0.30)]):
        t    = _tone(freq, 100, vol).fade_out(70)
        base = base.overlay(t, position=i * 110)
    return base.fade_out(80) - 2


def _gen_shock() -> AudioSegment:
    """Short sharp alert — not annoying."""
    base = AudioSegment.silent(duration=600)
    for i in range(3):
        beep = _tone(1480 + i * 80, 60, 0.5).fade_out(40)
        base = base.overlay(beep, position=i * 140)
    return base.fade_out(100) - 3


def _gen_success() -> AudioSegment:
    """Uplifting 4-note chime."""
    base = AudioSegment.silent(duration=900)
    for i, freq in enumerate([523, 659, 784, 1047]):
        t    = _tone(freq, 200, 0.42).fade_in(15).fade_out(120)
        base = base.overlay(t, position=i * 170)
    return base.fade_out(120) - 3


def _gen_fail() -> AudioSegment:
    """Gentle descending tone — not harsh."""
    base = AudioSegment.silent(duration=700)
    for i, freq in enumerate([440, 370, 311, 262]):
        t    = _tone(freq, 160, 0.38).fade_out(100)
        base = base.overlay(t, position=i * 140)
    return base.fade_out(120) - 3


def _gen_transition() -> AudioSegment:
    """Smooth radio-style swoosh."""
    base = AudioSegment.silent(duration=500)
    for i, freq in enumerate(range(250, 2000, 220)):
        t    = _tone(freq, 45, 0.22).fade_in(8).fade_out(25)
        base = base.overlay(t, position=i * 35)
    return base.fade_in(15).fade_out(100) - 5


def _gen_crowd_wow() -> AudioSegment:
    """Crowd reaction — short and warm."""
    base = AudioSegment.silent(duration=1200)
    for i, freq in enumerate([180, 220, 250, 230, 200]):
        noise = generators.WhiteNoise().to_audio_segment(duration=200) - 26
        t     = _tone(freq, 200, 0.22)
        base  = base.overlay(noise.overlay(t), position=i * 160)
    return base.fade_in(180).fade_out(500) - 4


def _gen_rimshot() -> AudioSegment:
    """Classic radio rimshot — tight and punchy."""
    base   = AudioSegment.silent(duration=600)
    kick   = _tone(80, 90, 0.65).fade_out(70)
    snare  = (generators.WhiteNoise().to_audio_segment(duration=75) - 14).fade_out(55)
    cymbal = (generators.WhiteNoise().to_audio_segment(duration=280) - 20).fade_out(240)
    base   = base.overlay(kick,   position=0)
    base   = base.overlay(snare,  position=140)
    base   = base.overlay(cymbal, position=280)
    return base.fade_out(120) - 2


def _gen_news_sting() -> AudioSegment:
    """Short news broadcast sting."""
    base = AudioSegment.silent(duration=1200)
    for i, freq in enumerate([880, 1046, 1318, 1046, 880]):
        t    = _tone(freq, 180, 0.45).fade_in(10).fade_out(80)
        base = base.overlay(t, position=i * 160)
    return base.fade_in(50).fade_out(200) - 2


def _gen_record_scratch() -> AudioSegment:
    """Record scratch for comedy moments."""
    noise = generators.WhiteNoise().to_audio_segment(duration=300) - 12
    sweep = AudioSegment.silent(duration=300)
    for i, freq in enumerate(range(3000, 200, -350)):
        t     = _tone(freq, 30, 0.3)
        sweep = sweep.overlay(t, position=i * 20)
    return (noise.overlay(sweep)).fade_in(10).fade_out(100) - 3


def _generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    """Generate all SFX files."""
    sfx_dir.mkdir(parents=True, exist_ok=True)

    generators_map = {
        "applause":       _gen_applause,
        "laugh":          _gen_laugh,
        "dramatic":       _gen_dramatic,
        "cash":           _gen_cash,
        "shock":          _gen_shock,
        "success":        _gen_success,
        "fail":           _gen_fail,
        "transition":     _gen_transition,
        "crowd_wow":      _gen_crowd_wow,
        "rimshot":        _gen_rimshot,
        "news_sting":     _gen_news_sting,
        "record_scratch": _gen_record_scratch,
    }

    available: dict[str, Path] = {}
    for name, fn in generators_map.items():
        dest = sfx_dir / f"{name}.wav"
        if not dest.is_file():
            try:
                fn().export(str(dest), format="wav")
                logger.info("Generated SFX: %s", name)
            except Exception as exc:
                logger.warning("Failed to generate '%s': %s", name, exc)
                continue
        available[name] = dest

    return available


# ---------------------------------------------------------------------------
# Intro / Outro
# ---------------------------------------------------------------------------

def generate_intro(duration_ms: int = 4000, mood: str = "") -> AudioSegment:
    """Generate a professional radio intro sting tailored to mood."""
    base = AudioSegment.silent(duration=duration_ms)

    # Mood-specific frequency sets
    mood_chords = {
        "hiphop":    [65, 98, 130, 196],
        "gospel":    [261, 329, 392, 523, 659],
        "afrobeats": [196, 261, 329, 392, 523],
        "jazz":      [220, 277, 330, 440],
        "news":      [440, 554, 659, 880],
        "horror":    [55, 73, 110, 146],
        "sports":    [329, 415, 523, 659, 830],
        "comedy":    [523, 659, 784, 1047],
        "cinematic": [82, 110, 164, 220, 329],
    }

    freqs = mood_chords.get(mood, [261, 329, 392, 523, 659])

    for i, freq in enumerate(freqs):
        t    = _tone(freq, duration_ms - 400, 0.22).fade_in(200).fade_out(600)
        base = base.overlay(t, position=i * 60)

    bass = _tone(freqs[0] / 2, duration_ms, 0.40).fade_in(300).fade_out(800)
    base = base.overlay(bass)

    # Add transition sweep at start
    sweep = _gen_transition()
    base  = base.overlay(sweep, position=0)

    return effects.normalize(base).fade_in(80).fade_out(200) - 2


def generate_outro(duration_ms: int = 3500, mood: str = "") -> AudioSegment:
    """Generate a smooth radio outro."""
    base = AudioSegment.silent(duration=duration_ms)

    mood_chords = {
        "hiphop":    [196, 130, 98, 65],
        "gospel":    [659, 523, 392, 329, 261],
        "jazz":      [440, 330, 277, 220],
        "news":      [880, 659, 554, 440],
        "sports":    [830, 659, 523, 415, 329],
        "comedy":    [1047, 784, 659, 523],
        "cinematic": [329, 220, 164, 110, 82],
    }

    freqs = mood_chords.get(mood, [659, 523, 392, 329, 261])

    for i, freq in enumerate(freqs):
        t    = _tone(freq, 600, 0.20).fade_in(40).fade_out(300)
        base = base.overlay(t, position=i * 450)

    bass = _tone(freqs[-1] / 2, duration_ms, 0.30).fade_in(150).fade_out(1000)
    base = base.overlay(bass)

    return effects.normalize(base).fade_in(150).fade_out(1200) - 2


# ---------------------------------------------------------------------------
# Main apply_sfx
# ---------------------------------------------------------------------------

def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_cues: Optional[list[dict]] = None,
    sfx_volume_db: float = -8,
) -> Path:
    audio_path  = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sfx_dir      = Path("/tmp/sfx_cache")
    available_sfx = _generate_sfx(sfx_dir)
    base_audio   = AudioSegment.from_wav(str(audio_path))

    if not sfx_cues or not available_sfx:
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    sfx_cache: dict[str, AudioSegment] = {}
    applied = 0
    last_sfx_time = -10.0  # Minimum 10s between any SFX

    # Sort cues by timestamp
    sorted_cues = sorted(sfx_cues, key=lambda x: float(x.get("timestamp", 0)))

    for cue in sorted_cues:
        sfx_name  = cue.get("sfx")
        timestamp = float(cue.get("timestamp", 0))
        intensity = float(cue.get("intensity", 0.6))

        # Enforce minimum gap between SFX
        if timestamp - last_sfx_time < 10.0:
            logger.info(
                "Skipping '%s' at %.1fs — too close to last SFX",
                sfx_name, timestamp
            )
            continue

        if sfx_name not in available_sfx:
            continue

        sfx_path = str(available_sfx[sfx_name])
        if sfx_path not in sfx_cache:
            try:
                clip = AudioSegment.from_wav(sfx_path)
                # Normalize then apply base volume
                clip = effects.normalize(clip) + sfx_volume_db
                sfx_cache[sfx_path] = clip
            except Exception as exc:
                logger.warning("Could not load SFX '%s': %s", sfx_name, exc)
                continue

        # Scale by intensity — keep it subtle
        # Max intensity boost is +4dB to prevent SFX from being too loud
        intensity_db = min(4.0, (intensity - 0.6) * 10)
        sfx_clip     = sfx_cache[sfx_path] + intensity_db

        position_ms = int(timestamp * 1000)
        if position_ms >= len(base_audio):
            continue

        remaining_ms = len(base_audio) - position_ms
        if len(sfx_clip) > remaining_ms:
            sfx_clip = sfx_clip[:remaining_ms]

        # Gentle fade to blend naturally
        sfx_clip   = sfx_clip.fade_in(25).fade_out(50)
        base_audio = base_audio.overlay(sfx_clip, position=position_ms)
        applied   += 1
        last_sfx_time = timestamp

        logger.info(
            "✓ SFX '%s' at %.1fs (intensity %.2f) — %s",
            sfx_name, timestamp, intensity, cue.get("reason", "")
        )

    logger.info("Applied %d/%d SFX cues", applied, len(sorted_cues))
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
