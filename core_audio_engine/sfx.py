from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Optional

from pydub import AudioSegment, effects

logger = logging.getLogger(__name__)

SFX_URLS: dict[str, str] = {
    "applause":   "https://assets.mixkit.co/sfx/preview/mixkit-small-group-clapping-474.mp3",
    "laugh":      "https://assets.mixkit.co/sfx/preview/mixkit-laughing-crowd-333.mp3",
    "dramatic":   "https://assets.mixkit.co/sfx/preview/mixkit-cinematic-mystery-suspense-transition-522.mp3",
    "cash":       "https://assets.mixkit.co/sfx/preview/mixkit-coins-handling-1939.mp3",
    "shock":      "https://assets.mixkit.co/sfx/preview/mixkit-alert-bells-echo-765.mp3",
    "success":    "https://assets.mixkit.co/sfx/preview/mixkit-winning-chimes-2015.mp3",
    "fail":       "https://assets.mixkit.co/sfx/preview/mixkit-losing-bleeps-2026.mp3",
    "transition": "https://assets.mixkit.co/sfx/preview/mixkit-fast-small-sweep-transition-166.mp3",
    "crowd_wow":  "https://assets.mixkit.co/sfx/preview/mixkit-crowd-wow-469.mp3",
    "rimshot":    "https://assets.mixkit.co/sfx/preview/mixkit-drum-joke-accent-2165.mp3",
}


def _download_sfx(sfx_dir: Path) -> dict[str, Path]:
    sfx_dir.mkdir(parents=True, exist_ok=True)
    available: dict[str, Path] = {}
    for name, url in SFX_URLS.items():
        dest = sfx_dir / f"{name}.mp3"
        if not dest.is_file():
            try:
                logger.info("Downloading SFX: %s", name)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    dest.write_bytes(r.read())
            except Exception as exc:
                logger.warning("Failed to download SFX '%s': %s", name, exc)
                continue
        if dest.is_file():
            available[name] = dest
    return available


def _transcribe_full(audio_path: Path) -> tuple[list[dict], str]:
    """Transcribe and return words + full transcript text."""
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

    full_text = result.get("text", "")
    return words, full_text


def _get_sfx_cues_from_claude(
    words: list[dict],
    full_text: str,
    available_sfx: list[str],
    audio_duration: float,
) -> list[dict]:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — falling back to keywords")
        return _keyword_fallback(words, available_sfx)

    # Build a concise timestamped transcript (every 5th word to save tokens)
    sampled = [f"[{w['start']:.1f}s]{w['word']}" for w in words]
    transcript_excerpt = " ".join(sampled[:300])  # limit tokens

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an expert radio show sound designer and producer.

Your job: analyze this podcast transcript and place sound effects strategically to make it sound like a PROFESSIONAL, FUN radio show.

Audio duration: {audio_duration:.1f} seconds
Available SFX: {', '.join(available_sfx)}

SFX usage guide:
- "applause" → after impressive facts, achievements, good points (2-3 times max)
- "laugh" → after jokes or genuinely funny moments
- "dramatic" → BEFORE a big reveal or surprising fact (builds suspense)
- "cash" → when money/financial figures are mentioned
- "shock" → after truly surprising statistics or revelations  
- "success" → when wins, breakthroughs, or positives are mentioned
- "fail" → when failures, problems, or negatives are mentioned
- "transition" → at clear topic changes (2-3 times max)
- "crowd_wow" → after impressive statements or mind-blowing facts
- "rimshot" → after puns or dad jokes ONLY

Full transcript summary:
{full_text[:500]}

Timestamped transcript:
{transcript_excerpt}

Rules:
1. Place SFX AFTER the moment (0.3-0.5s delay), not during speech
2. Maximum 10 cues total, spread throughout the audio
3. Don't cluster more than 2 SFX within 30 seconds
4. Make it feel natural and enhance the content, not overwhelm it
5. Prioritize moments that would genuinely benefit from audio punctuation

Respond ONLY with a JSON array:
[
  {{"timestamp": 5.8, "sfx": "dramatic", "reason": "host about to reveal surprising fact"}},
  {{"timestamp": 23.1, "sfx": "cash", "reason": "mentioned million dollar figure"}}
]
Return ONLY the JSON array, no other text."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        # Find JSON array in response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        cues = json.loads(text)
        logger.info("Claude placed %d SFX cues", len(cues))
        for c in cues:
            logger.info("  %.1fs → %s (%s)", c.get("timestamp", 0), c.get("sfx"), c.get("reason", ""))
        return cues
    except Exception as exc:
        logger.warning("Claude SFX failed (%s) — using keyword fallback", exc)
        return _keyword_fallback(words, available_sfx)


def _keyword_fallback(words: list[dict], available_sfx: list[str]) -> list[dict]:
    keyword_map = {
        "laugh":      ["funny", "joke", "hilarious", "haha", "laughing"],
        "cash":       ["money", "dollar", "billion", "million", "price", "cost", "paid"],
        "shock":      ["shocking", "unbelievable", "crazy", "insane", "impossible"],
        "applause":   ["amazing", "incredible", "excellent", "brilliant", "genius"],
        "dramatic":   ["secret", "revealed", "actually", "truth", "discovered", "hidden"],
        "success":    ["won", "success", "achieved", "record", "breakthrough"],
        "fail":       ["failed", "disaster", "terrible", "worst", "collapsed"],
        "crowd_wow":  ["wow", "massive", "enormous", "largest", "biggest"],
        "rimshot":    ["anyway", "moving on"],
        "transition": ["next", "meanwhile", "however", "speaking of"],
    }
    cues = []
    last_cue_time = -15.0
    for word_info in words:
        word = word_info["word"].lower().strip(".,!?;:'\"")
        t = word_info["start"]
        if t - last_cue_time < 15:
            continue
        for sfx, triggers in keyword_map.items():
            if sfx in available_sfx and word in triggers:
                cues.append({"timestamp": t + 0.4, "sfx": sfx, "reason": f"keyword: {word}"})
                last_cue_time = t
                break
    return cues[:10]


def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_map: Optional[dict] = None,
    whisper_model: str = "small",
    sfx_volume_db: float = -6,
) -> Path:
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Download SFX
    sfx_dir = Path("/tmp/sfx_cache")
    available_sfx = _download_sfx(sfx_dir)

    base_audio = AudioSegment.from_wav(str(audio_path))
    audio_duration = len(base_audio) / 1000.0

    if not available_sfx:
        logger.warning("No SFX available — copying original")
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    # Transcribe
    try:
        words, full_text = _transcribe_full(audio_path)
        logger.info("Transcribed %d words", len(words))
    except Exception as exc:
        logger.warning("Transcription failed (%s) — skipping SFX", exc)
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
                clip = AudioSegment.from_file(sfx_path)
                # Normalize SFX volume
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

        # Fade in/out SFX for natural feel
        sfx_clip = sfx_clip.fade_in(50).fade_out(100)
        base_audio = base_audio.overlay(sfx_clip, position=position_ms)
        applied += 1
        logger.info("✓ Applied '%s' at %.1fs", sfx_name, timestamp)

    logger.info("Applied %d/%d SFX cues", applied, len(cues))
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
