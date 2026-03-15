from __future__ import annotations

import json
import logging
import os
import base64
import urllib.request
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects, generators

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generate SFX programmatically using pydub — no downloads needed!
# ---------------------------------------------------------------------------

def _generate_sfx(sfx_dir: Path) -> dict[str, Path]:
    """Generate all SFX programmatically so no downloads are needed."""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    available: dict[str, Path] = {}

    sfx_generators = {
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

    for name, gen_fn in sfx_generators.items():
        dest = sfx_dir / f"{name}.wav"
        if not dest.is_file():
            try:
                audio = gen_fn()
                audio.export(str(dest), format="wav")
                logger.info("Generated SFX: %s", name)
            except Exception as exc:
                logger.warning("Failed to generate SFX '%s': %s", name, exc)
                continue
        available[name] = dest

    return available


def _gen_tone(freq: float, duration_ms: int, volume: float = 0.3) -> AudioSegment:
    tone = generators.Sine(freq).to_audio_segment(duration=duration_ms)
    return tone + (20 * (volume - 1))  # adjust volume


def _gen_applause() -> AudioSegment:
    """Simulate applause with layered noise bursts."""
    import random
    base = AudioSegment.silent(duration=2000)
    for i in range(0, 1800, 40):
        freq = random.randint(800, 3000)
        burst = generators.WhiteNoise().to_audio_segment(duration=30) - 20
        base = base.overlay(burst, position=i)
    return base.fade_in(200).fade_out(500)


def _gen_laugh() -> AudioSegment:
    """Simulate laugh track with rising tones."""
    base = AudioSegment.silent(duration=1500)
    for i, freq in enumerate([300, 350, 400, 350, 300]):
        tone = _gen_tone(freq, 150, 0.4)
        base = base.overlay(tone, position=i * 180)
    return base.fade_in(100).fade_out(300)


def _gen_dramatic() -> AudioSegment:
    """Deep dramatic sting."""
    low = _gen_tone(80, 1500, 0.6)
    mid = _gen_tone(120, 1000, 0.4)
    combined = low.overlay(mid)
    return combined.fade_in(50).fade_out(400)


def _gen_cash() -> AudioSegment:
    """Cash register ding."""
    ding = _gen_tone(1200, 150, 0.7)
    ding2 = _gen_tone(1500, 100, 0.5)
    combined = ding + ding2
    return combined.fade_out(200)


def _gen_shock() -> AudioSegment:
    """Shock/alert beeps."""
    base = AudioSegment.silent(duration=800)
    for i in range(4):
        beep = _gen_tone(1800, 80, 0.6)
        base = base.overlay(beep, position=i * 150)
    return base.fade_out(100)


def _gen_success() -> AudioSegment:
    """Rising success chime."""
    base = AudioSegment.silent(duration=800)
    for i, freq in enumerate([523, 659, 784, 1047]):
        tone = _gen_tone(freq, 200, 0.5)
        base = base.overlay(tone, position=i * 150)
    return base.fade_out(200)


def _gen_fail() -> AudioSegment:
    """Descending fail sound."""
    base = AudioSegment.silent(duration=800)
    for i, freq in enumerate([400, 350, 300, 250]):
        tone = _gen_tone(freq, 200, 0.5)
        base = base.overlay(tone, position=i * 150)
    return base.fade_out(200)


def _gen_transition() -> AudioSegment:
    """Quick swoosh transition."""
    base = AudioSegment.silent(duration=500)
    for i, freq in enumerate(range(200, 2000, 200)):
        tone = _gen_tone(freq, 60, 0.3)
        base = base.overlay(tone, position=i * 40)
    return base.fade_in(20).fade_out(100)


def _gen_crowd_wow() -> AudioSegment:
    """Crowd wow effect."""
    base = AudioSegment.silent(duration=1200)
    for i, freq in enumerate([200, 250, 300, 280, 260]):
        noise = generators.WhiteNoise().to_audio_segment(duration=200) - 25
        tone = _gen_tone(freq, 200, 0.3)
        base = base.overlay(noise.overlay(tone), position=i * 150)
    return base.fade_in(100).fade_out(400)


def _gen_rimshot() -> AudioSegment:
    """Classic rimshot ba dum tss."""
    base = AudioSegment.silent(duration=600)
    kick = _gen_tone(80, 100, 0.7)
    snare = generators.WhiteNoise().to_audio_segment(duration=80) - 15
    cymbal = generators.WhiteNoise().to_audio_segment(duration=300) - 20
    base = base.overlay(kick, position=0)
    base = base.overlay(snare, position=150)
    base = base.overlay(cymbal, position=300)
    return base.fade_out(200)


# ---------------------------------------------------------------------------
# Intro / Outro generation
# ---------------------------------------------------------------------------

def generate_intro(duration_ms: int = 4000) -> AudioSegment:
    """Generate a professional radio show intro sting."""
    base = AudioSegment.silent(duration=duration_ms)

    # Rising chord progression
    freqs = [261, 329, 392, 523, 659, 784]
    for i, freq in enumerate(freqs):
        tone = _gen_tone(freq, 800, 0.3)
        tone = tone.fade_in(100).fade_out(200)
        base = base.overlay(tone, position=i * 300)

    # Add dramatic low bass
    bass = _gen_tone(65, duration_ms, 0.4)
    bass = bass.fade_in(500).fade_out(1000)
    base = base.overlay(bass)

    return effects.normalize(base).fade_in(200).fade_out(500)


def generate_outro(duration_ms: int = 3000) -> AudioSegment:
    """Generate a smooth radio show outro sting."""
    base = AudioSegment.silent(duration=duration_ms)

    # Descending resolution
    freqs = [784, 659, 523, 392, 329, 261]
    for i, freq in enumerate(freqs):
        tone = _gen_tone(freq, 600, 0.3)
        tone = tone.fade_in(50).fade_out(200)
        base = base.overlay(tone, position=i * 400)

    bass = _gen_tone(65, duration_ms, 0.3)
    bass = bass.fade_in(200).fade_out(800)
    base = base.overlay(bass)

    return effects.normalize(base).fade_in(200).fade_out(1000)


# ---------------------------------------------------------------------------
# Claude AI SFX placement
# ---------------------------------------------------------------------------

def _transcribe_full(audio_path: Path) -> tuple[list[dict], str]:
    import whisper
    logger.info("Transcribing with Whisper small model...")
    model = whisper.load_model("small")
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en")
    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w.get("word", "").strip(),
                "start": w.get("start", 0),
                "end": w.get("end", 0),
            })
    return words, result.get("text", "")


def _get_sfx_cues_from_claude(
    words: list[dict],
    full_text: str,
    available_sfx: list[str],
    audio_duration: float,
) -> list[dict]:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _keyword_fallback(words, available_sfx)

    sampled = " ".join(f"[{w['start']:.1f}s]{w['word']}" for w in words[:300])

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are a professional radio show sound designer.

Analyze this podcast transcript and place sound effects to make it sound like a PROFESSIONAL, FUN, MODERN radio show or podcast.

Audio duration: {audio_duration:.1f} seconds
Available SFX: {', '.join(available_sfx)}

SFX guide:
- "applause" → after impressive facts, great points, achievements
- "laugh" → after jokes or funny moments
- "dramatic" → BEFORE a big reveal (builds suspense)
- "cash" → when money/financial figures mentioned
- "shock" → after surprising statistics or revelations
- "success" → when wins or positives mentioned
- "fail" → when failures or negatives mentioned
- "transition" → at clear topic changes
- "crowd_wow" → after mind-blowing facts
- "rimshot" → after puns or jokes ONLY

Full transcript:
{full_text[:800]}

Timestamped words:
{sampled}

Rules:
1. Place SFX 0.3s AFTER the relevant moment
2. Maximum 8 cues, well spread out
3. No two SFX within 20 seconds of each other
4. Only place where it genuinely adds to the show

Return ONLY a JSON array:
[{{"timestamp": 5.8, "sfx": "dramatic", "reason": "big reveal coming"}}]"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = msg.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            cues = json.loads(text[start:end])
            logger.info("Claude placed %d SFX cues", len(cues))
            for c in cues:
                logger.info("  %.1fs → %s (%s)", c.get("timestamp", 0), c.get("sfx"), c.get("reason", ""))
            return cues
    except Exception as exc:
        logger.warning("Claude SFX failed: %s", exc)

    return _keyword_fallback(words, available_sfx)


def _keyword_fallback(words: list[dict], available_sfx: list[str]) -> list[dict]:
    keyword_map = {
        "laugh":      ["funny", "joke", "hilarious", "haha"],
        "cash":       ["money", "dollar", "billion", "million", "price"],
        "shock":      ["shocking", "unbelievable", "crazy", "impossible"],
        "applause":   ["amazing", "incredible", "excellent", "brilliant"],
        "dramatic":   ["secret", "revealed", "truth", "discovered"],
        "success":    ["won", "success", "achieved", "record"],
        "fail":       ["failed", "disaster", "terrible", "worst"],
        "crowd_wow":  ["wow", "massive", "enormous", "largest"],
        "transition": ["next", "meanwhile", "however"],
    }
    cues = []
    last_t = -20.0
    for w in words:
        word = w["word"].lower().strip(".,!?;:'\"")
        t = w["start"]
        if t - last_t < 20:
            continue
        for sfx, triggers in keyword_map.items():
            if sfx in available_sfx and word in triggers:
                cues.append({"timestamp": t + 0.4, "sfx": sfx, "reason": f"keyword: {word}"})
                last_t = t
                break
    return cues[:8]


# ---------------------------------------------------------------------------
# Main apply_sfx function
# ---------------------------------------------------------------------------

def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_map: Optional[dict] = None,
    whisper_model: str = "small",
    sfx_volume_db: float = -4,
) -> Path:
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate SFX programmatically
    sfx_dir = Path("/tmp/sfx_cache")
    available_sfx = _generate_sfx(sfx_dir)

    base_audio = AudioSegment.from_wav(str(audio_path))
    audio_duration = len(base_audio) / 1000.0

    if not available_sfx:
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    # Transcribe
    try:
        words, full_text = _transcribe_full(audio_path)
        logger.info("Transcribed %d words", len(words))
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    if not words:
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    # Get AI cues
    cues = _get_sfx_cues_from_claude(
        words, full_text, list(available_sfx.keys()), audio_duration
    )

    # Apply SFX
    sfx_cache: dict[str, AudioSegment] = {}
    applied = 0

    for cue in cues:
        sfx_name = cue.get("sfx")
        timestamp = float(cue.get("timestamp", 0))

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

        sfx_clip = sfx_cache[sfx_path]
        position_ms = int(timestamp * 1000)

        if position_ms >= len(base_audio):
            continue

        remaining_ms = len(base_audio) - position_ms
        if len(sfx_clip) > remaining_ms:
            sfx_clip = sfx_clip[:remaining_ms]

        sfx_clip = sfx_clip.fade_in(30).fade_out(80)
        base_audio = base_audio.overlay(sfx_clip, position=position_ms)
        applied += 1
        logger.info("✓ Applied '%s' at %.1fs — %s", sfx_name, timestamp, cue.get("reason", ""))

    logger.info("Applied %d/%d SFX cues", applied, len(cues))
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
