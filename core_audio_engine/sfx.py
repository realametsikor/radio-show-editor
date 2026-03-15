"""Sound effects generation and application for radio show production."""
from __future__ import annotations

import json
import logging
import os
import random
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects, generators

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _tone(freq: float, ms: int, vol: float = 0.3) -> AudioSegment:
    """Generate a sine tone at given frequency, duration and relative volume."""
    t = generators.Sine(freq).to_audio_segment(duration=ms)
    # Convert vol (0-1 linear) to dB attenuation
    if vol <= 0:
        return AudioSegment.silent(duration=ms)
    import math
    db = 20 * math.log10(max(vol, 0.001))
    return t + db


def _add_room_reverb(audio: AudioSegment, decay_ms: int = 300, wet: float = 0.2) -> AudioSegment:
    """Add simple reverb-like ambiance by layering delayed/attenuated copies."""
    result = audio
    num_reflections = 4
    for i in range(1, num_reflections + 1):
        delay = int(decay_ms * i / num_reflections)
        attenuation = -6 * i - 3  # Each reflection quieter
        if delay < len(audio):
            delayed = AudioSegment.silent(duration=delay) + (audio + attenuation)
            delayed = delayed[:len(audio)]
            result = result.overlay(delayed * wet + result * (1 - wet) if False else
                                    result.overlay(delayed, position=0))
    # Mix wet/dry
    return effects.normalize(result) + (audio.dBFS - effects.normalize(result).dBFS)


def _shaped_noise(duration_ms: int, low_freq: int = 200, high_freq: int = 8000) -> AudioSegment:
    """Generate band-limited noise that sounds more natural than raw white noise."""
    noise = generators.WhiteNoise().to_audio_segment(duration=duration_ms)
    # We can't do band-pass in pydub easily, but we can layer filtered tones
    # to create a warmer noise texture
    base = noise - 20  # Start quiet
    # Add low rumble
    for freq in range(low_freq, min(high_freq, 2000), 200):
        t = generators.Sine(freq).to_audio_segment(duration=duration_ms)
        t = t + random.uniform(-30, -22)
        base = base.overlay(t)
    return base


# ---------------------------------------------------------------------------
# SFX Generation — Richer, more layered sounds
# ---------------------------------------------------------------------------

def _gen_applause() -> AudioSegment:
    """Crowd applause: layered noise bursts with natural envelope."""
    duration = 2500
    base = AudioSegment.silent(duration=duration)

    # Layer 1: Dense clapping (filtered noise bursts)
    for i in range(0, 2200, 25):
        burst_len = random.randint(15, 35)
        burst = generators.WhiteNoise().to_audio_segment(duration=burst_len)
        burst = burst + random.uniform(-26, -20)
        base = base.overlay(burst, position=i)

    # Layer 2: Lower crowd rumble
    rumble = _tone(180, duration, 0.08)
    rumble2 = _tone(260, duration, 0.06)
    base = base.overlay(rumble).overlay(rumble2)

    # Layer 3: A few distinct louder claps
    for _ in range(8):
        pos = random.randint(200, 2000)
        clap = generators.WhiteNoise().to_audio_segment(duration=random.randint(8, 18))
        clap = clap + random.uniform(-16, -12)
        base = base.overlay(clap, position=pos)

    return base.fade_in(600).fade_out(1000) - 4


def _gen_laugh() -> AudioSegment:
    """Audience laugh: layered voice-like tones with breathy texture."""
    duration = 1500
    base = AudioSegment.silent(duration=duration)

    # Ha-ha-ha pattern with varying pitch
    for i in range(6):
        freq = random.uniform(240, 380)
        syllable_len = random.randint(100, 180)
        t = _tone(freq, syllable_len, 0.20)
        # Add breathiness
        breath = generators.WhiteNoise().to_audio_segment(duration=syllable_len) - 30
        syllable = t.overlay(breath)
        syllable = syllable.fade_in(15).fade_out(40)
        base = base.overlay(syllable, position=i * random.randint(140, 200))

    # Background crowd murmur
    murmur = generators.WhiteNoise().to_audio_segment(duration=duration) - 32
    base = base.overlay(murmur)

    return base.fade_in(100).fade_out(500) - 5


def _gen_dramatic() -> AudioSegment:
    """Dramatic sting: deep bass swell with tension harmonics."""
    duration = 1800
    base = AudioSegment.silent(duration=duration)

    # Deep bass foundation
    for freq, vol in [(45, 0.40), (55, 0.35), (82, 0.25), (110, 0.15)]:
        t = _tone(freq, 1500, vol)
        base = base.overlay(t, position=100)

    # Tension harmonics (minor intervals)
    for freq, vol, delay in [(146, 0.10, 200), (174, 0.08, 400), (196, 0.06, 500)]:
        t = _tone(freq, 1000, vol).fade_in(100).fade_out(400)
        base = base.overlay(t, position=delay)

    # Sub-bass rumble
    rumble = generators.WhiteNoise().to_audio_segment(duration=800) - 34
    base = base.overlay(rumble, position=300)

    return base.fade_in(300).fade_out(800) - 3


def _gen_cash() -> AudioSegment:
    """Cash register: bright metallic ting with register click."""
    base = AudioSegment.silent(duration=600)

    # Click sound
    click = generators.WhiteNoise().to_audio_segment(duration=12) - 14
    base = base.overlay(click, position=0)

    # Metallic ring tones (ascending)
    for i, (freq, vol) in enumerate([(1318, 0.50), (1760, 0.35), (2093, 0.25), (2637, 0.15)]):
        t = _tone(freq, 120, vol).fade_out(80)
        base = base.overlay(t, position=30 + i * 90)

    # Subtle bell decay
    bell = _tone(2093, 300, 0.08).fade_out(280)
    base = base.overlay(bell, position=200)

    return base.fade_out(80) - 4


def _gen_shock() -> AudioSegment:
    """Shock/surprise: descending alert with impact."""
    base = AudioSegment.silent(duration=700)

    # Impact burst
    impact = generators.WhiteNoise().to_audio_segment(duration=30) - 12
    base = base.overlay(impact, position=0)

    # Descending alert tones
    for i in range(4):
        freq = 1600 - i * 120
        beep = _tone(freq, 70, 0.35).fade_in(5).fade_out(40)
        base = base.overlay(beep, position=40 + i * 110)

    # Sub-impact
    sub = _tone(60, 200, 0.30).fade_out(180)
    base = base.overlay(sub, position=20)

    return base.fade_out(100) - 4


def _gen_success() -> AudioSegment:
    """Success fanfare: ascending major chord arpeggio."""
    base = AudioSegment.silent(duration=1000)

    # Ascending C major with octave
    for i, freq in enumerate([523, 659, 784, 1047, 1318]):
        t = _tone(freq, 220, 0.30).fade_in(10).fade_out(120)
        base = base.overlay(t, position=i * 140)

    # Sustain chord at the top
    chord_base = AudioSegment.silent(duration=400)
    for freq in [1047, 1318, 1568]:
        t = _tone(freq, 400, 0.12).fade_out(350)
        chord_base = chord_base.overlay(t)
    base = base.overlay(chord_base, position=550)

    return base.fade_out(150) - 4


def _gen_fail() -> AudioSegment:
    """Failure: descending sad trombone effect."""
    base = AudioSegment.silent(duration=900)

    # Descending notes (Bb to F — sad interval)
    for i, freq in enumerate([466, 415, 370, 349, 311]):
        dur = 140 + i * 10  # Each note slightly longer
        t = _tone(freq, dur, 0.28).fade_out(dur - 20)
        base = base.overlay(t, position=i * 130)

    # Low rumble for heaviness
    rumble = _tone(80, 500, 0.12).fade_in(50).fade_out(300)
    base = base.overlay(rumble, position=200)

    return base.fade_out(150) - 5


def _gen_transition() -> AudioSegment:
    """Smooth transition whoosh with tonal sweep."""
    base = AudioSegment.silent(duration=500)

    # Rising sweep
    steps = 12
    for i in range(steps):
        freq = 300 + int((1500 - 300) * (i / steps) ** 1.5)
        t = _tone(freq, 35, 0.15).fade_in(5).fade_out(15)
        base = base.overlay(t, position=i * 30)

    # Noise swoosh layer
    swoosh = generators.WhiteNoise().to_audio_segment(duration=350) - 26
    swoosh = swoosh.fade_in(50).fade_out(200)
    base = base.overlay(swoosh, position=50)

    return base.fade_in(15).fade_out(100) - 6


def _gen_crowd_wow() -> AudioSegment:
    """Crowd wow/gasp reaction."""
    duration = 1200
    base = AudioSegment.silent(duration=duration)

    # Layered crowd voices (vowel-like tones)
    for _ in range(8):
        freq = random.uniform(160, 300)
        start = random.randint(0, 200)
        dur = random.randint(300, 600)
        t = _tone(freq, dur, random.uniform(0.10, 0.20))
        breath = generators.WhiteNoise().to_audio_segment(duration=dur) - 32
        voice = t.overlay(breath).fade_in(30).fade_out(100)
        base = base.overlay(voice, position=start)

    # Rising pitch element (the "wow" trajectory)
    for i in range(5):
        freq = 180 + i * 40
        t = _tone(freq, 200, 0.12).fade_in(20).fade_out(60)
        base = base.overlay(t, position=100 + i * 120)

    return base.fade_in(150).fade_out(500) - 5


def _gen_rimshot() -> AudioSegment:
    """Ba-dum-tss rimshot."""
    base = AudioSegment.silent(duration=600)

    # Kick (ba)
    kick = _tone(80, 100, 0.50).fade_out(70)
    kick_click = generators.WhiteNoise().to_audio_segment(duration=8) - 14
    base = base.overlay(kick, position=0)
    base = base.overlay(kick_click, position=0)

    # Snare (dum)
    snare_body = _tone(200, 60, 0.30).fade_out(40)
    snare_noise = generators.WhiteNoise().to_audio_segment(duration=80) - 16
    snare_noise = snare_noise.fade_out(50)
    base = base.overlay(snare_body, position=150)
    base = base.overlay(snare_noise, position=150)

    # Cymbal (tss)
    cymbal = generators.WhiteNoise().to_audio_segment(duration=300) - 20
    cymbal = cymbal.fade_out(260)
    # Add shimmer
    shimmer = _tone(8000, 200, 0.05).fade_out(180)
    base = base.overlay(cymbal, position=300)
    base = base.overlay(shimmer, position=300)

    return base.fade_out(100) - 3


def _gen_news_sting() -> AudioSegment:
    """News bulletin sting: authoritative tonal signature."""
    duration = 1200
    base = AudioSegment.silent(duration=duration)

    # Strong opening notes
    for i, freq in enumerate([880, 1046, 1318]):
        t = _tone(freq, 180, 0.35).fade_in(8).fade_out(80)
        base = base.overlay(t, position=i * 130)

    # Resolution
    for i, freq in enumerate([1046, 880]):
        t = _tone(freq, 200, 0.30).fade_in(8).fade_out(100)
        base = base.overlay(t, position=420 + i * 160)

    # Bass foundation
    bass = _tone(220, 800, 0.20).fade_in(50).fade_out(300)
    base = base.overlay(bass, position=0)

    # Subtle presence ring
    ring = _tone(1760, 600, 0.06).fade_in(50).fade_out(500)
    base = base.overlay(ring, position=300)

    return base.fade_in(30).fade_out(250) - 3


def _generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    """Generate and cache all SFX to disk."""
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
# Intro / Outro — Musical and polished
# ---------------------------------------------------------------------------

def generate_intro(duration_ms: int = 4000, mood: str = "") -> AudioSegment:
    """Generate a musical intro with chord progression and rhythm."""
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
        "electronic":   [130, 196, 261, 392],
        "ambient":      [130, 196, 261, 329],
        "lo-fi":        [196, 261, 329, 392],
        "classical":    [261, 329, 392, 523],
        "reggae":       [196, 247, 329, 392],
        "latin":        [220, 329, 392, 523],
        "rnb":          [196, 261, 329, 415],
        "country":      [220, 277, 329, 440],
        "acoustic":     [220, 277, 329, 440],
    }

    freqs = mood_chords.get(mood, [261, 329, 392, 523, 659])
    base = AudioSegment.silent(duration=duration_ms)

    # Layer 1: Chord pad (sustained tones staggered for a wash)
    pad_duration = duration_ms - 400
    for i, freq in enumerate(freqs):
        t = _tone(freq, pad_duration, 0.16).fade_in(250).fade_out(500)
        base = base.overlay(t, position=80 + i * 60)

    # Layer 2: Bass foundation (octave below root)
    bass = _tone(freqs[0] / 2, duration_ms, 0.28).fade_in(400).fade_out(700)
    base = base.overlay(bass)

    # Layer 3: Rhythmic pulse for energy (subtle clicks)
    pulse_interval = 250  # ms between pulses
    for pos in range(200, duration_ms - 400, pulse_interval):
        click = generators.WhiteNoise().to_audio_segment(duration=8) - 28
        base = base.overlay(click, position=pos)

    # Layer 4: Rising shimmer for anticipation
    shimmer_start = duration_ms // 3
    shimmer_dur = duration_ms - shimmer_start - 200
    if shimmer_dur > 200:
        shimmer = _tone(freqs[-1] * 2, shimmer_dur, 0.06).fade_in(shimmer_dur // 2).fade_out(200)
        base = base.overlay(shimmer, position=shimmer_start)

    base = effects.normalize(base)
    return base.fade_in(100).fade_out(300) - 2


def generate_outro(duration_ms: int = 3500, mood: str = "") -> AudioSegment:
    """Generate a musical outro with gentle resolution."""
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
        "electronic":   [392, 261, 196, 130],
        "ambient":      [329, 261, 196, 130],
        "lo-fi":        [392, 329, 261, 196],
        "classical":    [523, 392, 329, 261],
        "reggae":       [392, 329, 247, 196],
        "latin":        [523, 392, 329, 220],
        "rnb":          [415, 329, 261, 196],
        "country":      [440, 329, 277, 220],
        "acoustic":     [440, 329, 277, 220],
    }

    freqs = mood_chords.get(mood, [659, 523, 392, 329, 261])
    base = AudioSegment.silent(duration=duration_ms)

    # Descending arpeggiated notes
    note_spacing = min(450, (duration_ms - 600) // len(freqs))
    for i, freq in enumerate(freqs):
        dur = 600 + i * 30  # Each note sustains slightly longer
        t = _tone(freq, dur, 0.18).fade_in(30).fade_out(dur // 2)
        base = base.overlay(t, position=i * note_spacing)

    # Sustained resolution chord at the end
    chord_start = len(freqs) * note_spacing
    chord_dur = max(600, duration_ms - chord_start - 200)
    if chord_dur > 200:
        for freq in freqs[-3:]:
            t = _tone(freq, chord_dur, 0.10).fade_in(50).fade_out(chord_dur - 100)
            base = base.overlay(t, position=chord_start)

    # Bass resolution
    bass = _tone(freqs[-1] / 2, duration_ms, 0.22).fade_in(200).fade_out(duration_ms // 2)
    base = base.overlay(bass)

    base = effects.normalize(base)
    return base.fade_in(200).fade_out(duration_ms // 2) - 2


# ---------------------------------------------------------------------------
# Apply SFX
# ---------------------------------------------------------------------------

def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_cues: Optional[list[dict]] = None,
    sfx_volume_db: float = -10,
) -> Path:
    """
    Apply AI-directed sound effects to audio.
    Ducks the main audio slightly around SFX placement for clarity.
    """
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
                # Normalize then apply volume — keep SFX present but not overpowering
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

        # Smooth SFX edges
        fade_in_ms = min(30, len(sfx_clip) // 4)
        fade_out_ms = min(60, len(sfx_clip) // 3)
        sfx_clip = sfx_clip.fade_in(fade_in_ms).fade_out(fade_out_ms)

        # Duck the main audio slightly around the SFX for clarity
        duck_range_ms = len(sfx_clip) + 100  # SFX duration + small buffer
        duck_start = max(0, pos_ms - 50)
        duck_end = min(audio_len_ms, pos_ms + duck_range_ms)

        if duck_end > duck_start:
            ducked_section = base_audio[duck_start:duck_end] - 2  # Gentle 2dB duck
            # Rebuild audio with ducked section
            before = base_audio[:duck_start]
            after = base_audio[duck_end:]
            base_audio = before + ducked_section + after

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
