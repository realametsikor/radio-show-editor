from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects, generators

logger = logging.getLogger(__name__)


def _generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    """Generate all SFX programmatically."""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    available: dict[str, Path] = {}

    generators_map = {
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
    }

    for name, fn in generators_map.items():
        dest = sfx_dir / f"{name}.wav"
        if not dest.is_file():
            try:
                fn().export(str(dest), format="wav")
            except Exception as exc:
                logger.warning("Failed to generate SFX '%s': %s", name, exc)
                continue
        available[name] = dest

    return available


def _tone(freq: float, ms: int, vol: float = 0.3) -> AudioSegment:
    t = generators.Sine(freq).to_audio_segment(duration=ms)
    return t + (20 * (vol - 1))


def _gen_applause() -> AudioSegment:
    import random
    base = AudioSegment.silent(duration=2500)
    for i in range(0, 2200, 35):
        freq = random.randint(600, 3500)
        burst = generators.WhiteNoise().to_audio_segment(duration=25) - 18
        base = base.overlay(burst, position=i)
    return base.fade_in(300).fade_out(800)


def _gen_laugh() -> AudioSegment:
    base = AudioSegment.silent(duration=1800)
    pattern = [280, 320, 360, 340, 300, 260]
    for i, freq in enumerate(pattern):
        t = _tone(freq, 180, 0.35)
        noise = generators.WhiteNoise().to_audio_segment(duration=180) - 28
        combined = t.overlay(noise)
        base = base.overlay(combined, position=i * 200)
    return base.fade_in(80).fade_out(400)


def _gen_dramatic() -> AudioSegment:
    base = AudioSegment.silent(duration=2000)
    for freq, vol in [(55, 0.7), (82, 0.5), (110, 0.3)]:
        t = _tone(freq, 1800, vol)
        base = base.overlay(t)
    return base.fade_in(100).fade_out(600)


def _gen_cash() -> AudioSegment:
    base = AudioSegment.silent(duration=600)
    for i, (freq, vol) in enumerate([(1318, 0.8), (1568, 0.6), (2093, 0.4)]):
        t = _tone(freq, 120, vol).fade_out(80)
        base = base.overlay(t, position=i * 120)
    return base.fade_out(100)


def _gen_shock() -> AudioSegment:
    base = AudioSegment.silent(duration=1000)
    for i in range(5):
        beep = _tone(1760 + i * 100, 70, 0.65).fade_out(40)
        base = base.overlay(beep, position=i * 130)
    return base.fade_out(200)


def _gen_success() -> AudioSegment:
    base = AudioSegment.silent(duration=1000)
    for i, freq in enumerate([523, 659, 784, 1047]):
        t = _tone(freq, 220, 0.5).fade_in(20).fade_out(100)
        base = base.overlay(t, position=i * 180)
    return base.fade_out(150)


def _gen_fail() -> AudioSegment:
    base = AudioSegment.silent(duration=800)
    for i, freq in enumerate([440, 370, 311, 262]):
        t = _tone(freq, 180, 0.5).fade_out(100)
        base = base.overlay(t, position=i * 160)
    return base.fade_out(150)


def _gen_transition() -> AudioSegment:
    base = AudioSegment.silent(duration=600)
    for i, freq in enumerate(range(300, 2400, 240)):
        t = _tone(freq, 55, 0.25).fade_in(10).fade_out(30)
        base = base.overlay(t, position=i * 38)
    return base.fade_in(20).fade_out(120)


def _gen_crowd_wow() -> AudioSegment:
    base = AudioSegment.silent(duration=1500)
    for i, freq in enumerate([180, 220, 260, 240, 200]):
        noise = generators.WhiteNoise().to_audio_segment(duration=220) - 22
        t = _tone(freq, 220, 0.25)
        base = base.overlay(noise.overlay(t), position=i * 180)
    return base.fade_in(150).fade_out(500)


def _gen_rimshot() -> AudioSegment:
    base = AudioSegment.silent(duration=700)
    kick = _tone(80, 110, 0.75).fade_out(80)
    snare = (generators.WhiteNoise().to_audio_segment(duration=90) - 12).fade_out(60)
    cymbal = (generators.WhiteNoise().to_audio_segment(duration=350) - 18).fade_out(280)
    base = base.overlay(kick, position=0)
    base = base.overlay(snare, position=160)
    base = base.overlay(cymbal, position=320)
    return base.fade_out(150)


def generate_intro(duration_ms: int = 4000) -> AudioSegment:
    base = AudioSegment.silent(duration=duration_ms)
    chord = [261, 329, 392, 523]
    for i, freq in enumerate(chord):
        t = _tone(freq, duration_ms - 500, 0.25).fade_in(200).fade_out(800)
        base = base.overlay(t, position=i * 80)
    bass = _tone(65, duration_ms, 0.45).fade_in(400).fade_out(1000)
    base = base.overlay(bass)
    sweep = _gen_transition() + AudioSegment.silent(duration=duration_ms - 600)
    base = base.overlay(sweep)
    return effects.normalize(base).fade_in(100).fade_out(300)


def generate_outro(duration_ms: int = 3500) -> AudioSegment:
    base = AudioSegment.silent(duration=duration_ms)
    chord = [523, 392, 329, 261]
    for i, freq in enumerate(chord):
        t = _tone(freq, 700, 0.22).fade_in(50).fade_out(300)
        base = base.overlay(t, position=i * 500)
    bass = _tone(65, duration_ms, 0.35).fade_in(200).fade_out(1200)
    base = base.overlay(bass)
    return effects.normalize(base).fade_in(200).fade_out(1500)


def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_cues: Optional[list[dict]] = None,
    sfx_volume_db: float = -3,
) -> Path:
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    sfx_dir = Path("/tmp/sfx_cache")
    available_sfx = _generate_sfx(sfx_dir)
    base_audio = AudioSegment.from_wav(str(audio_path))

    if not sfx_cues or not available_sfx:
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    sfx_cache: dict[str, AudioSegment] = {}
    applied = 0

    for cue in sfx_cues:
        sfx_name = cue.get("sfx")
        timestamp = float(cue.get("timestamp", 0))
        intensity = float(cue.get("intensity", 0.6))

        if sfx_name not in available_sfx:
            continue

        sfx_path = str(available_sfx[sfx_name])
        if sfx_path not in sfx_cache:
            try:
                clip = AudioSegment.from_wav(sfx_path)
                clip = effects.normalize(clip) + sfx_volume_db
                sfx_cache[sfx_path] = clip
            except Exception as exc:
                logger.warning("Could not load SFX '%s': %s", sfx_name, exc)
                continue

        # Scale SFX volume by intensity
        sfx_clip = sfx_cache[sfx_path] + (20 * (intensity - 1))
        position_ms = int(timestamp * 1000)

        if position_ms >= len(base_audio):
            continue

        remaining_ms = len(base_audio) - position_ms
        if len(sfx_clip) > remaining_ms:
            sfx_clip = sfx_clip[:remaining_ms]

        sfx_clip = sfx_clip.fade_in(20).fade_out(60)
        base_audio = base_audio.overlay(sfx_clip, position=position_ms)
        applied += 1
        logger.info("✓ SFX '%s' at %.1fs (intensity %.1f) — %s",
                    sfx_name, timestamp, intensity, cue.get("reason", ""))

    logger.info("Applied %d/%d SFX cues", applied, len(sfx_cues))
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
