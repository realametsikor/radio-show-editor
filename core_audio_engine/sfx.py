from __future__ import annotations

import json
import logging
import os
import urllib.request
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Free SFX URLs from Freesound / public domain sources
# ---------------------------------------------------------------------------
SFX_URLS: dict[str, str] = {
    "applause":      "https://assets.mixkit.co/sfx/preview/mixkit-small-group-clapping-474.mp3",
    "laugh":         "https://assets.mixkit.co/sfx/preview/mixkit-laughing-crowd-333.mp3",
    "dramatic":      "https://assets.mixkit.co/sfx/preview/mixkit-cinematic-mystery-suspense-transition-522.mp3",
    "cash":          "https://assets.mixkit.co/sfx/preview/mixkit-coins-handling-1939.mp3",
    "shock":         "https://assets.mixkit.co/sfx/preview/mixkit-alert-bells-echo-765.mp3",
    "success":       "https://assets.mixkit.co/sfx/preview/mixkit-winning-chimes-2015.mp3",
    "fail":          "https://assets.mixkit.co/sfx/preview/mixkit-losing-bleeps-2026.mp3",
    "transition":    "https://assets.mixkit.co/sfx/preview/mixkit-fast-small-sweep-transition-166.mp3",
    "crowd_wow":     "https://assets.mixkit.co/sfx/preview/mixkit-crowd-wow-469.mp3",
    "rimshot":       "https://assets.mixkit.co/sfx/preview/mixkit-drum-joke-accent-2165.mp3",
}

SFX_VOLUME_DB = -8


def _download_sfx(sfx_dir: Path) -> dict[str, Path]:
    """Download SFX files if not already cached."""
    sfx_dir.mkdir(parents=True, exist_ok=True)
    available: dict[str, Path] = {}

    for name, url in SFX_URLS.items():
        dest = sfx_dir / f"{name}.mp3"
        if not dest.is_file():
            try:
                logger.info("Downloading SFX: %s", name)
                urllib.request.urlretrieve(url, dest)
            except Exception as exc:
                logger.warning("Failed to download SFX '%s': %s", name, exc)
                continue
        available[name] = dest

    return available


def _transcribe(audio_path: Path, whisper_model: str = "base") -> list[dict]:
    """Transcribe audio and return word-level timestamps."""
    import whisper
    logger.info("Loading Whisper model '%s' …", whisper_model)
    model = whisper.load_model(whisper_model)
    logger.info("Transcribing '%s' …", audio_path)
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en")

    words = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w.get("word", "").strip(),
                "start": w.get("start", 0),
                "end": w.get("end", 0),
            })
    return words


def _get_sfx_cues_from_claude(
    words: list[dict],
    available_sfx: list[str],
) -> list[dict]:
    """Use Claude AI to decide where to place SFX based on transcript context."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set — falling back to keyword matching")
        return _keyword_fallback(words, available_sfx)

    # Build transcript with timestamps
    transcript_lines = []
    for i, seg in enumerate(words):
        transcript_lines.append(f"[{seg['start']:.1f}s] {seg['word']}")
    transcript_text = " ".join(
        f"[{w['start']:.1f}s]{w['word']}" for w in words
    )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a professional radio show sound effects editor.
Given this transcript with timestamps, decide where to place sound effects to make it fun and engaging like a real radio show.

Available SFX: {', '.join(available_sfx)}

SFX guide:
- "applause" → after a good point, achievement, or end of segment
- "laugh" → after a joke or funny moment
- "dramatic" → before a big reveal or shocking statement
- "cash" → when money, prices, or financial topics are mentioned
- "shock" → after a surprising or shocking fact
- "success" → when something positive or winning is mentioned
- "fail" → when something goes wrong or fails
- "transition" → between topic changes
- "crowd_wow" → after an impressive statement or fact
- "rimshot" → after a pun or weak joke

Transcript:
{transcript_text}

Respond ONLY with a JSON array of cues like this (max 8 cues, pick the best moments):
[
  {{"timestamp": 4.2, "sfx": "applause", "reason": "host made a great point"}},
  {{"timestamp": 12.5, "sfx": "dramatic", "reason": "shocking reveal coming"}}
]
Only return the JSON array, nothing else."""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        # Clean up any markdown
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        cues = json.loads(response_text)
        logger.info("Claude suggested %d SFX cues", len(cues))
        return cues
    except Exception as exc:
        logger.warning("Claude SFX analysis failed (%s) — falling back to keywords", exc)
        return _keyword_fallback(words, available_sfx)


def _keyword_fallback(words: list[dict], available_sfx: list[str]) -> list[dict]:
    """Simple keyword-based SFX placement as fallback."""
    keyword_map = {
        "laugh": ["funny", "joke", "hilarious", "haha", "laugh"],
        "cash": ["money", "dollar", "price", "cost", "pay", "billion", "million"],
        "shock": ["shocking", "unbelievable", "crazy", "insane", "wow"],
        "applause": ["amazing", "great", "excellent", "congratulations", "well done"],
        "dramatic": ["secret", "reveal", "actually", "truth", "discovered"],
        "success": ["won", "success", "achieved", "breakthrough"],
        "fail": ["failed", "lost", "disaster", "terrible", "worst"],
        "rimshot": ["pun", "get it", "anyway"],
    }

    cues = []
    for word_info in words:
        word = word_info["word"].lower().strip(".,!?")
        for sfx, triggers in keyword_map.items():
            if sfx in available_sfx and word in triggers:
                cues.append({
                    "timestamp": word_info["start"],
                    "sfx": sfx,
                    "reason": f"keyword: {word}"
                })
    return cues[:8]


def apply_sfx(
    audio_path: str | Path,
    output_path: str | Path = "audio_with_sfx.wav",
    sfx_map: Optional[dict] = None,
    whisper_model: str = "base",
    sfx_volume_db: float = SFX_VOLUME_DB,
) -> Path:
    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Download SFX files
    sfx_dir = Path("/tmp/sfx_cache")
    available_sfx = _download_sfx(sfx_dir)

    if not available_sfx:
        logger.warning("No SFX available — copying original audio")
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    # Transcribe
    try:
        words = _transcribe(audio_path, whisper_model)
    except Exception as exc:
        logger.warning("Transcription failed (%s) — skipping SFX", exc)
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    if not words:
        logger.warning("No words transcribed — skipping SFX")
        import shutil
        shutil.copy(str(audio_path), str(output_path))
        return output_path.resolve()

    # Get SFX cues from Claude
    cues = _get_sfx_cues_from_claude(words, list(available_sfx.keys()))

    # Apply SFX to audio
    base_audio = AudioSegment.from_wav(str(audio_path))
    sfx_cache: dict[str, AudioSegment] = {}
    applied = 0

    for cue in cues:
        sfx_name = cue.get("sfx")
        timestamp = cue.get("timestamp", 0)

        if sfx_name not in available_sfx:
            continue

        sfx_path = available_sfx[sfx_name]

        if str(sfx_path) not in sfx_cache:
            try:
                sfx_cache[str(sfx_path)] = AudioSegment.from_file(str(sfx_path)) + sfx_volume_db
            except Exception as exc:
                logger.warning("Could not load SFX '%s': %s", sfx_name, exc)
                continue

        sfx_clip = sfx_cache[str(sfx_path)]
        position_ms = int(timestamp * 1000)

        remaining_ms = len(base_audio) - position_ms
        if remaining_ms <= 0:
            continue
        if len(sfx_clip) > remaining_ms:
            sfx_clip = sfx_clip[:remaining_ms]

        base_audio = base_audio.overlay(sfx_clip, position=position_ms)
        applied += 1
        logger.info("Applied '%s' SFX at %.1fs (%s)", sfx_name, timestamp, cue.get("reason", ""))

    logger.info("Applied %d SFX cues → %s", applied, output_path)
    base_audio.export(str(output_path), format="wav")
    return output_path.resolve()
