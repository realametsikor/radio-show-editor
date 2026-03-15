from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_with_claude(
    transcript: str,
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
) -> dict:
    """
    Use Claude as a professional radio producer to analyze the podcast
    and return a full production plan including SFX cues, music intensity
    curve, and show structure.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — using basic production plan")
        return _basic_production_plan(words, audio_duration, available_sfx)

    # Build timestamped transcript
    timestamped = " ".join(
        f"[{w['start']:.1f}s]{w['word']}" for w in words[:400]
    )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a world-class radio show producer and sound designer with 20 years of experience at BBC Radio and NPR.

Your job is to transform a raw podcast transcript into a professional, engaging radio show production plan.

Audio duration: {audio_duration:.1f} seconds
Available sound effects: {', '.join(available_sfx)}

Full transcript:
{transcript[:1000]}

Timestamped words:
{timestamped}

Create a PROFESSIONAL production plan. Think about:
1. Where does the conversation get exciting or surprising?
2. Where are natural topic transitions?
3. What moments need audio punctuation?
4. How should music intensity change throughout?

SFX guide:
- "applause" → genuine achievements, impressive facts, great points
- "laugh" → jokes, funny observations, witty remarks
- "dramatic" → BEFORE shocking reveals, surprising statistics
- "cash" → money, prices, financial figures mentioned
- "shock" → truly surprising facts or revelations
- "success" → wins, breakthroughs, positive outcomes
- "fail" → failures, problems, negative outcomes
- "transition" → clear topic changes, new segments
- "crowd_wow" → mind-blowing facts, impressive scale
- "rimshot" → puns, wordplay, dad jokes

Music intensity guide (0.0 = very quiet, 1.0 = full volume):
- During speech: 0.1-0.2 (barely audible, voice is king)
- During natural pauses: 0.4-0.6 (music swells up)
- At transitions: 0.5-0.7 (music bridges the gap)
- Intro/outro: 0.8-1.0 (full radio feel)

Rules:
- Maximum 8 SFX cues, minimum 15 seconds apart
- Place SFX 0.2-0.5 seconds AFTER the relevant moment
- Music intensity changes should be gradual (2-3 second transitions)
- Only add SFX where it genuinely enhances the show
- Think like a BBC Radio producer — subtle but impactful

Respond ONLY with this exact JSON structure:
{{
  "show_title": "Compelling title for this episode",
  "show_summary": "One sentence description",
  "sfx_cues": [
    {{"timestamp": 5.2, "sfx": "dramatic", "reason": "host about to reveal surprising fact", "intensity": 0.7}}
  ],
  "music_curve": [
    {{"timestamp": 0, "intensity": 0.0, "note": "silence before intro"}},
    {{"timestamp": 2, "intensity": 0.8, "note": "intro music swell"}},
    {{"timestamp": 5, "intensity": 0.15, "note": "voice begins, music ducks"}},
    {{"timestamp": {audio_duration:.1f}, "intensity": 0.0, "note": "fade out"}}
  ],
  "segments": [
    {{"start": 0, "end": 30, "title": "Opening", "type": "intro"}}
  ]
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(text[start:end])
            logger.info(
                "Claude production plan: '%s' — %d SFX cues, %d music points",
                plan.get("show_title", "Untitled"),
                len(plan.get("sfx_cues", [])),
                len(plan.get("music_curve", [])),
            )
            return plan
    except Exception as exc:
        logger.warning("Claude production analysis failed: %s", exc)

    return _basic_production_plan(words, audio_duration, available_sfx)


def _basic_production_plan(
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
) -> dict:
    """Fallback production plan using keyword detection."""
    keyword_map = {
        "laugh":      ["funny", "joke", "hilarious", "haha"],
        "cash":       ["money", "dollar", "billion", "million", "price"],
        "shock":      ["shocking", "unbelievable", "crazy", "impossible"],
        "applause":   ["amazing", "incredible", "excellent", "brilliant"],
        "dramatic":   ["secret", "revealed", "truth", "discovered"],
        "success":    ["won", "success", "achieved", "record"],
        "fail":       ["failed", "disaster", "terrible", "worst"],
        "crowd_wow":  ["wow", "massive", "enormous", "largest"],
        "transition": ["next", "meanwhile", "however", "moving"],
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
                cues.append({
                    "timestamp": t + 0.4,
                    "sfx": sfx,
                    "reason": f"keyword: {word}",
                    "intensity": 0.6
                })
                last_t = t
                break

    # Basic music curve
    music_curve = [
        {"timestamp": 0, "intensity": 0.0},
        {"timestamp": 2, "intensity": 0.7},
        {"timestamp": 5, "intensity": 0.15},
        {"timestamp": audio_duration - 5, "intensity": 0.15},
        {"timestamp": audio_duration - 2, "intensity": 0.6},
        {"timestamp": audio_duration, "intensity": 0.0},
    ]

    return {
        "show_title": "Radio Show",
        "show_summary": "Podcast transformed into radio show",
        "sfx_cues": cues[:8],
        "music_curve": music_curve,
        "segments": []
    }
