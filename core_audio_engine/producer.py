from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SHOW_PERSONALITIES: dict[str, dict] = {
    "lo-fi":        {"style": "Chill study session host",           "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "calm, intellectual, cozy"},
    "upbeat":       {"style": "High-energy morning show host",      "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "moderate",  "tone": "exciting, positive, energetic"},
    "hiphop":       {"style": "Urban radio DJ",                     "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "prominent", "tone": "cool, hype, urban, confident"},
    "gospel":       {"style": "Inspirational radio host",           "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "moderate",  "tone": "uplifting, spiritual, warm"},
    "afrobeats":    {"style": "Afro radio host",                    "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "prominent", "tone": "vibrant, cultural, joyful"},
    "news":         {"style": "Professional news anchor",           "energy": "medium",    "sfx_frequency": "minimal",       "music_presence": "subtle",    "tone": "authoritative, serious, clear"},
    "morning_drive":{"style": "Morning drive radio host",           "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "moderate",  "tone": "cheerful, energetic, fun"},
    "comedy":       {"style": "Comedy show host",                   "energy": "high",      "sfx_frequency": "very_frequent", "music_presence": "moderate",  "tone": "hilarious, witty, playful"},
    "true_crime":   {"style": "True crime narrator",                "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "subtle",    "tone": "dark, suspenseful, dramatic"},
    "tech":         {"style": "Tech podcast host",                  "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "subtle",    "tone": "intelligent, analytical, clear"},
    "sports":       {"style": "Sports radio commentator",           "energy": "very_high", "sfx_frequency": "very_frequent", "music_presence": "moderate",  "tone": "passionate, intense, exciting"},
    "war":          {"style": "Military documentary narrator",      "energy": "high",      "sfx_frequency": "moderate",      "music_presence": "subtle",    "tone": "intense, powerful, dramatic"},
    "documentary":  {"style": "Documentary narrator",               "energy": "medium",    "sfx_frequency": "minimal",       "music_presence": "subtle",    "tone": "thoughtful, informative, engaging"},
    "talk_show":    {"style": "Late night talk show host",          "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "moderate",  "tone": "charming, witty, entertaining"},
    "business":     {"style": "Business podcast host",              "energy": "medium",    "sfx_frequency": "minimal",       "music_presence": "subtle",    "tone": "professional, insightful, motivating"},
    "spiritual":    {"style": "Spiritual guide host",               "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "peaceful, wise, meditative"},
    "horror":       {"style": "Horror podcast narrator",            "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "subtle",    "tone": "eerie, suspenseful, chilling"},
    "kids":         {"style": "Kids show host",                     "energy": "very_high", "sfx_frequency": "very_frequent", "music_presence": "moderate",  "tone": "playful, excited, fun"},
    "romance":      {"style": "Romance drama narrator",             "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "warm, emotional, intimate"},
    "science":      {"style": "Science show host",                  "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "subtle",    "tone": "curious, enthusiastic, educational"},
    "cinematic":    {"style": "Epic cinematic narrator",            "energy": "high",      "sfx_frequency": "moderate",      "music_presence": "prominent", "tone": "powerful, dramatic, grand"},
    "jazz":         {"style": "Late night jazz lounge host",        "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "smooth, cool, sophisticated"},
    "rnb":          {"style": "R&B radio host",                     "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "moderate",  "tone": "soulful, emotional, smooth"},
    "reggae":       {"style": "Reggae vibes host",                  "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "positive, easy-going, conscious"},
    "classical":    {"style": "Classical arts host",                "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "refined, eloquent, cultured"},
    "country":      {"style": "Country radio host",                 "energy": "medium",    "sfx_frequency": "moderate",      "music_presence": "moderate",  "tone": "friendly, authentic, storytelling"},
    "latin":        {"style": "Latin radio host",                   "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "moderate",  "tone": "passionate, lively, festive"},
    "ambient":      {"style": "Ambient podcast host",               "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "prominent", "tone": "calm, introspective, mindful"},
    "electronic":   {"style": "Electronic music show host",         "energy": "high",      "sfx_frequency": "frequent",      "music_presence": "prominent", "tone": "futuristic, cool, innovative"},
    "acoustic":     {"style": "Acoustic session host",              "energy": "low",       "sfx_frequency": "minimal",       "music_presence": "moderate",  "tone": "intimate, genuine, heartfelt"},
}

DEFAULT_PERSONALITY = {
    "style":          "Professional radio host",
    "energy":         "medium",
    "sfx_frequency":  "moderate",
    "music_presence": "moderate",
    "tone":           "professional, engaging, entertaining",
}

SFX_FREQUENCY_MAP = {
    "minimal":       (30, 3),
    "moderate":      (20, 5),
    "frequent":      (15, 7),
    "very_frequent": (10, 9),
}

MUSIC_PRESENCE_DURING_SPEECH = {
    "subtle":    0.08,
    "moderate":  0.14,
    "prominent": 0.20,
}


def analyze_with_claude(
    transcript: str,
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
    mood: str = "",
) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using basic plan with NO SFX")
        return _basic_production_plan(words, audio_duration, available_sfx, mood)

    logger.info(
        "ANTHROPIC_API_KEY found (len=%d prefix=%s) — using Claude",
        len(api_key), api_key[:8]
    )

    personality   = SHOW_PERSONALITIES.get(mood, DEFAULT_PERSONALITY)
    min_gap, max_cues = SFX_FREQUENCY_MAP.get(personality["sfx_frequency"], (20, 5))
    music_during  = MUSIC_PRESENCE_DURING_SPEECH.get(personality["music_presence"], 0.12)

    timestamped = " ".join(
        f"[{w['start']:.1f}s]{w['word']}" for w in words[:400]
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""You are a world-class radio show producer at BBC Radio and NPR.

You are producing a "{mood.upper()}" style show.
Host personality: {personality['style']}
Energy: {personality['energy']} | Tone: {personality['tone']}
Music presence during speech: {music_during} (0=silent, 1=full volume)

Audio duration: {audio_duration:.1f} seconds

FULL TRANSCRIPT:
{transcript[:1500]}

TIMESTAMPED WORDS:
{timestamped}

AVAILABLE SFX: {', '.join(available_sfx)}

SFX GUIDE (use VERY sparingly — only where it genuinely enhances):
- applause → after impressive achievements or great points
- laugh → after genuine jokes or funny moments ONLY
- dramatic → BEFORE a big surprising reveal (builds tension)
- cash → when specific money figures mentioned
- shock → after truly surprising facts
- success → when wins or breakthroughs mentioned
- fail → when failures or problems mentioned
- transition → at clear topic changes
- crowd_wow → after mind-blowing facts
- rimshot → after puns or wordplay ONLY
- news_sting → for news/breaking information

CRITICAL RULES:
1. Maximum {max_cues} SFX total, minimum {min_gap}s gap between any two
2. Place SFX 0.3-0.5s AFTER the moment — never during speech
3. When in doubt, DO NOT add SFX — less is more
4. Music should be clearly audible during pauses and quieter during speech

MUSIC CURVE (make music prominent and enjoyable):
- Music MUST be audible throughout — this is a radio show not a voice recording
- During speech: intensity {music_during} (still audible, just lower)
- During pauses/silence: intensity 0.4-0.6 (music swells up nicely)
- At topic transitions: intensity 0.5-0.7
- Intro/outro: intensity 0.8-0.9

Respond ONLY with valid JSON:
{{
  "show_title": "Compelling {mood}-style title",
  "show_tagline": "Catchy one-liner",
  "show_summary": "2-3 sentence summary",
  "keywords": ["kw1", "kw2", "kw3"],
  "sfx_cues": [
    {{"timestamp": 5.2, "sfx": "dramatic", "reason": "about to reveal key fact", "intensity": 0.65}}
  ],
  "music_curve": [
    {{"timestamp": 0, "intensity": 0.0, "note": "silence"}},
    {{"timestamp": 1.5, "intensity": 0.85, "note": "intro swell"}},
    {{"timestamp": 4.5, "intensity": {music_during}, "note": "speech begins"}},
    {{"timestamp": {audio_duration - 4:.1f}, "intensity": {music_during}, "note": "near end"}},
    {{"timestamp": {audio_duration - 1.5:.1f}, "intensity": 0.75, "note": "outro swell"}},
    {{"timestamp": {audio_duration:.1f}, "intensity": 0.0, "note": "end"}}
  ],
  "segments": [
    {{"start": 0, "end": 30, "title": "Opening", "type": "intro", "description": "Brief description"}}
  ],
  "highlights": [
    {{"start": 10.0, "end": 25.0, "title": "Best moment", "reason": "Why compelling"}}
  ],
  "production_notes": "Key observations about this episode"
}}"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )

        text  = message.content[0].text.strip()
        text  = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end   = text.rfind("}") + 1

        if start >= 0 and end > start:
            plan = json.loads(text[start:end])
            logger.info(
                "Claude plan: '%s' — %d SFX | %d segments | %d highlights",
                plan.get("show_title"),
                len(plan.get("sfx_cues", [])),
                len(plan.get("segments", [])),
                len(plan.get("highlights", [])),
            )
            return plan

    except Exception as exc:
        logger.warning("Claude API call failed: %s", exc)

    return _basic_production_plan(words, audio_duration, available_sfx, mood)


def _basic_production_plan(
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
    mood: str = "",
) -> dict:
    """
    Fallback — NO SFX to avoid bad placement.
    Still provides good music curve.
    """
    logger.warning("Basic plan — NO SFX applied (add ANTHROPIC_API_KEY for AI production)")

    music_during = MUSIC_PRESENCE_DURING_SPEECH.get(
        SHOW_PERSONALITIES.get(mood, DEFAULT_PERSONALITY).get("music_presence", "moderate"),
        0.14,
    )

    music_curve = [
        {"timestamp": 0,                    "intensity": 0.0,         "note": "silence"},
        {"timestamp": 1.5,                  "intensity": 0.85,        "note": "intro swell"},
        {"timestamp": 4.5,                  "intensity": music_during, "note": "speech"},
        {"timestamp": audio_duration - 4,   "intensity": music_during, "note": "near end"},
        {"timestamp": audio_duration - 1.5, "intensity": 0.75,        "note": "outro swell"},
        {"timestamp": audio_duration,       "intensity": 0.0,         "note": "end"},
    ]

    return {
        "show_title":       mood.replace("_", " ").title() + " Radio Show",
        "show_tagline":     "Your podcast, professionally produced",
        "show_summary":     "A podcast transformed into a professional radio show.",
        "keywords":         [mood, "podcast", "radio"],
        "sfx_cues":         [],
        "music_curve":      music_curve,
        "segments":         [],
        "highlights":       [],
        "production_notes": "Basic plan — ANTHROPIC_API_KEY not set. Add it for AI-powered production.",
    }
