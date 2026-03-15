from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects, generators

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SFX Generation
# ---------------------------------------------------------------------------

def _tone(freq: float, ms: int, vol: float = 0.3) -> AudioSegment:
    t = generators.Sine(freq).to_audio_segment(duration=ms)
    return t + (20 * (vol - 1))


def _gen_applause() -> AudioSegment:
    import random
    base = AudioSegment.silent(duration=2000)
    for i in range(0, 1800, 30):
        burst = generators.WhiteNoise().to_audio_segment(duration=22) - 24
        base  = base.overlay(burst, position=i)
    return base.fade_in(500).fade_out(800) - 5


def _gen_laugh() -> AudioSegment:
    base = AudioSegment.silent(duration=1200)
    for i, freq in enumerate([270, 310, 350, 320, 280]):
        t    = _tone(freq, 140, 0.22)
        n    = generators.WhiteNoise().to_audio_segment(duration=140) - 32
        base = base.overlay(t.overlay(n), position=i * 170)
    return base.fade_in(80).fade_out(400) - 6


def _gen_dramatic() -> AudioSegment:
    base = AudioSegment.silent(duration=1500)
    for freq, vol in [(55, 0.45), (82, 0.30), (110, 0.18)]:
        t    = _tone(freq, 1300, vol)
        base = base.overlay(t)
    return base.fade_in(200).fade_out(600) - 4


def _gen_cash() -> AudioSegment:
    base = AudioSegment.silent(duration=400)
    for i, (freq, vol) in enumerate([(1318, 0.55), (1760, 0.38), (2093, 0.25)]):
        t    = _tone(freq, 90, vol).fade_out(60)
        base = base.overlay(t, position=i * 100)
    return base.fade_out(60) - 4


def _gen_shock() -> AudioSegment:
    base = AudioSegment.silent(duration=500)
    for i in range(3):
        beep = _tone(1480 + i * 70, 55, 0.40).fade_out(35)
        base = base.overlay(beep, position=i * 130)
    return base.fade_out(80) - 5


def _gen_success() -> AudioSegment:
    base = AudioSegment.silent(duration=800)
    for i, freq in enumerate([523, 659, 784, 1047]):
        t    = _tone(freq, 180, 0.35).fade_in(10).fade_out(100)
        base = base.overlay(t, position=i * 150)
    return base.fade_out(100) - 5


def _gen_fail() -> AudioSegment:
    base = AudioSegment.silent(duration=600)
    for i, freq in enumerate([440, 370, 311, 262]):
        t    = _tone(freq, 140, 0.30).fade_out(90)
        base = base.overlay(t, position=i * 120)
    return base.fade_out(100) - 5


def _gen_transition() -> AudioSegment:
    base = AudioSegment.silent(duration=400)
    for i, freq in enumerate(range(300, 1800, 200)):
        t    = _tone(freq, 40, 0.18).fade_in(5).fade_out(20)
        base = base.overlay(t, position=i * 32)
    return base.fade_in(10).fade_out(80) - 7


def _gen_crowd_wow() -> AudioSegment:
    base = AudioSegment.silent(duration=1000)
    for i, freq in enumerate([180, 220, 250, 230, 200]):
        n    = generators.WhiteNoise().to_audio_segment(duration=180) - 28
        t    = _tone(freq, 180, 0.18)
        base = base.overlay(n.overlay(t), position=i * 140)
    return base.fade_in(200).fade_out(400) - 6


def _gen_rimshot() -> AudioSegment:
    base   = AudioSegment.silent(duration=500)
    kick   = _tone(80, 80, 0.55).fade_out(60)
    snare  = (generators.WhiteNoise().to_audio_segment(duration=65) - 16).fade_out(45)
    cymbal = (generators.WhiteNoise().to_audio_segment(duration=240) - 22).fade_out(200)
    base   = base.overlay(kick,   position=0)
    base   = base.overlay(snare,  position=130)
    base   = base.overlay(cymbal, position=260)
    return base.fade_out(100) - 4


def _gen_news_sting() -> AudioSegment:
    base = AudioSegment.silent(duration=1000)
    for i, freq in enumerate([880, 1046, 1318, 1046, 880]):
        t    = _tone(freq, 160, 0.38).fade_in(8).fade_out(70)
        base = base.overlay(t, position=i * 140)
    return base.fade_in(40).fade_out(180) - 4


def _generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    sfx_dir.mkdir(parents=True, exist_ok=True)
    gen_map = {
        "applause":   _gen_applause,
        "laugh":      _gen_laugh,
        "dramatic":   _gen_dramatic,
        "cash":       _gen_cash,
        "shock":      _gen_shock,
        "success":    _gen_success,
        "fail":       _gen_fail,
        "transition": _gen_transition,
        "crowd_wow":  _gen_crowd_wow,
        "rimshot":    _gen_rimshot,
        "news_sting": _gen_news_sting,
    }
    available: dict[str, Path] = {}
    for name, fn in gen_map.items():
        dest = sfx_dir / f"{name}.wav"
        if not dest.is_file():
            try:
                fn().export(str(dest), format="wav")
            except Exception as exc:
                logger.warning("SFX gen failed '%s': %s", name, exc)
                continue
        available[name] = dest
    return available


# ---------------------------------------------------------------------------
# Intro / Outro
# ---------------------------------------------------------------------------

def generate_intro(duration_ms: int = 4000, mood: str = "") -> AudioSegment:
    mood_chords = {
        "hiphop":       [65, 98, 130, 196],
        "gospel":       [261, 329, 392, 523, 659],
        "afrobeats":    [196, 261, 329, 392, 523],
        "jazz":         [220, 277, 330, 440],
        "news":         [440, 554, 659, 880],
        "horror":       [55, 73, 110, 146],
        "sports":       [329, 415, 523, 659, 830],
        "comedy":       [523, 659, 784, 1047],
        "cinematic":    [82, 110, 164, 220, 329],
        "true_crime":   [110, 138, 164, 196],
        "morning_drive":[392, 494, 587, 784],
    }
    freqs = mood_chords.get(mood, [261, 329, 392, 523, 659])
    base  = AudioSegment.silent(duration=duration_ms)
    for i, freq in enumerate(freqs):
        t    = _tone(freq, duration_ms - 500, 0.20).fade_in(200).fade_out(600)
        base = base.overlay(t, position=i * 50)
    bass = _tone(freqs[0] / 2, duration_ms, 0.35).fade_in(300).fade_out(800)
    base = base.overlay(bass)
    return effects.normalize(base).fade_in(80).fade_out(200) - 3


def generate_outro(duration_ms: int = 3500, mood: str = "") -> AudioSegment:
    mood_chords = {
        "hiphop":       [196, 130, 98, 65],
        "gospel":       [659, 523, 392, 329, 261],
        "jazz":         [440, 330, 277, 220],
        "news":         [880, 659, 554, 440],
        "sports":       [830, 659, 523, 415, 329],
        "comedy":       [1047, 784, 659, 523],
        "cinematic":    [329, 220, 164, 110, 82],
        "true_crime":   [196, 164, 138, 110],
        "morning_drive":[784, 587, 494, 392],
    }
    freqs = mood_chords.get(mood, [659, 523, 392, 329, 261])
    base  = AudioSegment.silent(duration=duration_ms)
    for i, freq in enumerate(freqs):
        t    = _tone(freq, 550, 0.18).fade_in(30).fade_out(280)
        base = base.overlay(t, position=i * 420)
    bass = _tone(freqs[-1] / 2, duration_ms, 0.25).fade_in(150).fade_out(900)
    base = base.overlay(bass)
    return effects.normalize(base).fade_in(150).fade_out(1200) - 3


# ---------------------------------------------------------------------------
# Apply SFX
# ---------------------------------------------------------------------------

def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_cues: Optional[list[dict]] = None,
    sfx_volume_db: float = -10,
) -> Path:
    audio_path  = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError("Audio not found: " + str(audio_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # No cues = no SFX, clean copy
    if not sfx_cues:
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        logger.info("No SFX cues — clean copy")
        return output_path.resolve()

    sfx_dir      = Path("/tmp/sfx_cache")
    available    = _generate_sfx(sfx_dir)
    base_audio   = AudioSegment.from_wav(str(audio_path))
    audio_len_ms = len(base_audio)

    sfx_cache:    dict[str, AudioSegment] = {}
    applied       = 0
    last_sfx_time = -15.0  # Minimum 15s gap between any SFX

    # Sort by timestamp
    sorted_cues = sorted(sfx_cues, key=lambda x: float(x.get("timestamp", 0)))

    for cue in sorted_cues:
        sfx_name  = cue.get("sfx", "")
        timestamp = float(cue.get("timestamp", 0))
        intensity = float(cue.get("intensity", 0.5))

        # Enforce minimum gap
        if timestamp - last_sfx_time < 15.0:
            logger.debug("Skip '%s' at %.1fs — too close to last", sfx_name, timestamp)
            continue

        if sfx_name not in available:
            continue

        sfx_key = str(available[sfx_name])
        if sfx_key not in sfx_cache:
            try:
                clip = AudioSegment.from_wav(sfx_key)
                # Normalize then apply volume — keep SFX subtle
                clip = effects.normalize(clip) + sfx_volume_db
                sfx_cache[sfx_key] = clip
            except Exception as exc:
                logger.warning("SFX load failed '%s': %s", sfx_name, exc)
                continue

        # Scale intensity — max +3dB boost, min -6dB reduction
        intensity_db = max(-6.0, min(3.0, (intensity - 0.6) * 8))
        sfx_clip     = sfx_cache[sfx_key] + intensity_db

        pos_ms = int(timestamp * 1000)
        if pos_ms >= audio_len_ms:
            continue

        remaining = audio_len_ms - pos_ms
        if len(sfx_clip) > remaining:
            sfx_clip = sfx_clip[:remaining]

        sfx_clip   = sfx_clip.fade_in(20).fade_out(40)
        base_audio = base_audio.overlay(sfx_clip, position=pos_ms)
        applied   += 1
        last_sfx_time = timestamp

        logger.info(
            "SFX '%s' at %.1fs (intensity %.2f) — %s",
            sfx_name, timestamp, intensity, cue.get("reason", "")
        )

    logger.info("Applied %d/%d SFX cues", applied, len(sorted_cues))
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
