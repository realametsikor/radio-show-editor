from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Show style personalities — tells Claude HOW to produce each style
# ---------------------------------------------------------------------------
SHOW_PERSONALITIES: dict[str, dict] = {
    "lo-fi": {
        "style": "Chill study session host — relaxed, thoughtful, conversational",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "calm, intellectual, cozy",
    },
    "upbeat": {
        "style": "High-energy morning show host — enthusiastic, fast-paced, exciting",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "moderate",
        "tone": "exciting, positive, energetic",
    },
    "hiphop": {
        "style": "Urban radio DJ — slick, confident, street-smart, hype",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "prominent",
        "tone": "cool, hype, urban, confident",
    },
    "gospel": {
        "style": "Inspirational radio host — uplifting, spiritual, motivational",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "moderate",
        "tone": "uplifting, spiritual, warm, encouraging",
    },
    "afrobeats": {
        "style": "Afro radio host — vibrant, cultural, celebratory, rhythmic",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "prominent",
        "tone": "vibrant, cultural, joyful, rhythmic",
    },
    "news": {
        "style": "Professional news anchor — authoritative, clear, serious",
        "energy": "medium",
        "sfx_frequency": "minimal",
        "music_presence": "subtle",
        "tone": "authoritative, serious, professional, clear",
    },
    "morning_drive": {
        "style": "Morning drive radio host — cheerful, energetic, relatable",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "moderate",
        "tone": "cheerful, energetic, fun, relatable",
    },
    "comedy": {
        "style": "Comedy show host — hilarious, witty, playful, unpredictable",
        "energy": "high",
        "sfx_frequency": "very_frequent",
        "music_presence": "moderate",
        "tone": "hilarious, witty, playful, surprising",
    },
    "true_crime": {
        "style": "True crime narrator — dark, suspenseful, dramatic, gripping",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "subtle",
        "tone": "dark, suspenseful, dramatic, gripping",
    },
    "tech": {
        "style": "Tech podcast host — smart, analytical, forward-thinking",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "subtle",
        "tone": "intelligent, analytical, innovative, clear",
    },
    "sports": {
        "style": "Sports radio commentator — passionate, intense, exciting",
        "energy": "very_high",
        "sfx_frequency": "very_frequent",
        "music_presence": "moderate",
        "tone": "passionate, intense, exciting, dramatic",
    },
    "war": {
        "style": "Military documentary narrator — intense, dramatic, powerful",
        "energy": "high",
        "sfx_frequency": "moderate",
        "music_presence": "subtle",
        "tone": "intense, powerful, dramatic, serious",
    },
    "documentary": {
        "style": "Documentary narrator — thoughtful, informative, engaging",
        "energy": "medium",
        "sfx_frequency": "minimal",
        "music_presence": "subtle",
        "tone": "thoughtful, informative, engaging, credible",
    },
    "talk_show": {
        "style": "Late night talk show host — charming, witty, entertaining",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "moderate",
        "tone": "charming, witty, entertaining, smooth",
    },
    "business": {
        "style": "Business podcast host — professional, insightful, motivating",
        "energy": "medium",
        "sfx_frequency": "minimal",
        "music_presence": "subtle",
        "tone": "professional, insightful, motivating, clear",
    },
    "spiritual": {
        "style": "Spiritual guide host — peaceful, wise, meditative, gentle",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "peaceful, wise, meditative, gentle",
    },
    "horror": {
        "style": "Horror podcast narrator — eerie, suspenseful, chilling, dark",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "subtle",
        "tone": "eerie, suspenseful, chilling, dark",
    },
    "kids": {
        "style": "Kids show host — playful, excited, fun, encouraging",
        "energy": "very_high",
        "sfx_frequency": "very_frequent",
        "music_presence": "moderate",
        "tone": "playful, excited, fun, encouraging",
    },
    "romance": {
        "style": "Romance drama narrator — warm, emotional, intimate, soulful",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "warm, emotional, intimate, soulful",
    },
    "science": {
        "style": "Science show host — curious, enthusiastic, mind-blowing",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "subtle",
        "tone": "curious, enthusiastic, mind-blowing, educational",
    },
    "cinematic": {
        "style": "Epic cinematic narrator — powerful, dramatic, grand",
        "energy": "high",
        "sfx_frequency": "moderate",
        "music_presence": "prominent",
        "tone": "powerful, dramatic, grand, epic",
    },
    "jazz": {
        "style": "Late night jazz lounge host — smooth, cool, laid-back",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "smooth, cool, sophisticated, laid-back",
    },
    "rnb": {
        "style": "R&B radio host — soulful, emotional, smooth, passionate",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "moderate",
        "tone": "soulful, emotional, smooth, passionate",
    },
    "reggae": {
        "style": "Reggae vibes host — positive, easy-going, conscious, chill",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "positive, easy-going, conscious, chill",
    },
    "classical": {
        "style": "Classical arts host — refined, eloquent, cultured, elegant",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "refined, eloquent, cultured, elegant",
    },
    "country": {
        "style": "Country radio host — friendly, down-to-earth, storytelling",
        "energy": "medium",
        "sfx_frequency": "moderate",
        "music_presence": "moderate",
        "tone": "friendly, authentic, storytelling, warm",
    },
    "latin": {
        "style": "Latin radio host — passionate, lively, festive, warm",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "moderate",
        "tone": "passionate, lively, festive, warm",
    },
    "ambient": {
        "style": "Ambient podcast host — calm, introspective, mindful",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "prominent",
        "tone": "calm, introspective, mindful, peaceful",
    },
    "electronic": {
        "style": "Electronic music show host — futuristic, cool, innovative",
        "energy": "high",
        "sfx_frequency": "frequent",
        "music_presence": "prominent",
        "tone": "futuristic, cool, innovative, energetic",
    },
    "acoustic": {
        "style": "Acoustic session host — intimate, genuine, heartfelt",
        "energy": "low",
        "sfx_frequency": "minimal",
        "music_presence": "moderate",
        "tone": "intimate, genuine, heartfelt, warm",
    },
}

DEFAULT_PERSONALITY = {
    "style": "Professional radio host — engaging, clear, entertaining",
    "energy": "medium",
    "sfx_frequency": "moderate",
    "music_presence": "moderate",
    "tone": "professional, engaging, entertaining",
}

SFX_FREQUENCY_MAP = {
    "minimal":       (30, 4),   # min_gap_s, max_cues
    "moderate":      (20, 6),
    "frequent":      (15, 8),
    "very_frequent": (10, 10),
}


def analyze_with_claude(
    transcript: str,
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
    mood: str = "",
) -> dict:
    """
    Use Claude as a professional radio producer to create a full
    production plan tailored to the selected show style/mood.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY — using basic production plan")
        return _basic_production_plan(words, audio_duration, available_sfx, mood)

    personality = SHOW_PERSONALITIES.get(mood, DEFAULT_PERSONALITY)
    min_gap, max_cues = SFX_FREQUENCY_MAP.get(
        personality["sfx_frequency"], (20, 6)
    )

    # Build compact timestamped transcript
    timestamped = " ".join(
        f"[{w['start']:.1f}s]{w['word']}" for w in words[:400]
    )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are a world-class radio show producer with 20+ years at BBC Radio, NPR, and major podcast networks.

You are producing a "{mood.upper()}" style radio show with these characteristics:
- Host personality: {personality['style']}
- Energy level: {personality['energy']}
- Tone: {personality['tone']}
- Music presence: {personality['music_presence']} (how audible music should be)
- SFX usage: {personality['sfx_frequency']}

Audio duration: {audio_duration:.1f} seconds
Available sound effects: {', '.join(available_sfx)}

=== FULL TRANSCRIPT ===
{transcript[:1200]}

=== TIMESTAMPED WORDS ===
{timestamped}

=== YOUR PRODUCTION TASKS ===

1. SOUND EFFECTS: Place SFX that match the {mood} show style
   - Max {max_cues} cues, minimum {min_gap}s apart
   - Place 0.2-0.5s AFTER the moment
   - Match the {personality['tone']} tone

   SFX guide:
   - "applause" → achievements, great points, impressive facts
   - "laugh" → jokes, funny moments, humor
   - "dramatic" → BEFORE shocking reveals or surprising facts
   - "cash" → money, prices, financial figures
   - "shock" → truly surprising revelations
   - "success" → wins, achievements, positive news
   - "fail" → failures, problems, bad news
   - "transition" → topic changes, new segments
   - "crowd_wow" → mind-blowing facts, impressive scale
   - "rimshot" → puns, wordplay, jokes

2. MUSIC CURVE: Define how music intensity changes over time
   - 0.0 = silence, 1.0 = full volume
   - During speech: 0.05-0.15 (voice is ALWAYS priority)
   - Natural pauses: 0.3-0.5 (music swells)
   - Transitions: 0.4-0.6
   - Intro/outro: 0.7-0.9
   - Music presence style is "{personality['music_presence']}"
     * subtle = max 0.15 during speech
     * moderate = max 0.2 during speech
     * prominent = max 0.25 during speech

3. SEGMENTS: Identify natural show segments
   - Find topic changes, new discussion points
   - Each segment needs a radio-style title

4. SHOW BRANDING: Create compelling radio show identity
   - Title should match {mood} style
   - Tagline should be catchy and style-appropriate
   - Keywords for show notes

5. HIGHLIGHT MOMENTS: Identify the 3 most compelling moments
   - These are the best clips for social media
   - Include exact timestamps

Respond ONLY with this exact JSON (no other text):
{{
  "show_title": "Compelling {mood}-style show title",
  "show_tagline": "Catchy one-line tagline",
  "show_summary": "2-3 sentence episode summary",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "sfx_cues": [
    {{
      "timestamp": 5.2,
      "sfx": "dramatic",
      "reason": "host about to reveal surprising fact",
      "intensity": 0.75
    }}
  ],
  "music_curve": [
    {{"timestamp": 0, "intensity": 0.0, "note": "silence"}},
    {{"timestamp": 1.5, "intensity": 0.8, "note": "intro music"}},
    {{"timestamp": 4.5, "intensity": 0.12, "note": "voice begins"}},
    {{"timestamp": {audio_duration - 4:.1f}, "intensity": 0.12, "note": "near end"}},
    {{"timestamp": {audio_duration - 1:.1f}, "intensity": 0.7, "note": "outro"}},
    {{"timestamp": {audio_duration:.1f}, "intensity": 0.0, "note": "end"}}
  ],
  "segments": [
    {{
      "start": 0,
      "end": 45,
      "title": "Opening",
      "type": "intro",
      "description": "Brief description"
    }}
  ],
  "highlights": [
    {{
      "start": 10.5,
      "end": 25.0,
      "title": "Best moment title",
      "reason": "Why this is compelling"
    }}
  ],
  "production_notes": "Any special production observations about this episode"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(text[start:end])
            logger.info("=" * 50)
            logger.info("🎙️ PRODUCTION PLAN: %s", plan.get("show_title"))
            logger.info("📝 %s", plan.get("show_tagline"))
            logger.info("🎵 %d SFX cues | %d segments | %d highlights",
                        len(plan.get("sfx_cues", [])),
                        len(plan.get("segments", [])),
                        len(plan.get("highlights", [])))
            logger.info("📝 Notes: %s", plan.get("production_notes", ""))
            logger.info("=" * 50)
            return plan
    except Exception as exc:
        logger.warning("Claude production failed: %s", exc)

    return _basic_production_plan(words, audio_duration, available_sfx, mood)


def _basic_production_plan(
    words: list[dict],
    audio_duration: float,
    available_sfx: list[str],
    mood: str = "",
) -> dict:
    """Fallback keyword-based production plan."""
    personality = SHOW_PERSONALITIES.get(mood, DEFAULT_PERSONALITY)
    min_gap, max_cues = SFX_FREQUENCY_MAP.get(
        personality["sfx_frequency"], (20, 6)
    )

    keyword_map = {
        "laugh":      ["funny", "joke", "hilarious", "haha", "laughing"],
        "cash":       ["money", "dollar", "billion", "million", "price", "cost"],
        "shock":      ["shocking", "unbelievable", "crazy", "impossible", "never"],
        "applause":   ["amazing", "incredible", "excellent", "brilliant", "genius"],
        "dramatic":   ["secret", "revealed", "truth", "discovered", "hidden"],
        "success":    ["won", "success", "achieved", "record", "breakthrough"],
        "fail":       ["failed", "disaster", "terrible", "worst", "collapsed"],
        "crowd_wow":  ["wow", "massive", "enormous", "largest", "biggest"],
        "transition": ["next", "meanwhile", "however", "moving", "speaking"],
        "rimshot":    ["anyway", "get it", "pun", "joke"],
    }

    cues = []
    last_t = -float(min_gap)
    for w in words:
        word = w["word"].lower().strip(".,!?;:'\"")
        t = w["start"]
        if t - last_t < min_gap:
            continue
        for sfx, triggers in keyword_map.items():
            if sfx in available_sfx and word in triggers:
                cues.append({
                    "timestamp": t + 0.4,
                    "sfx": sfx,
                    "reason": f"keyword: {word}",
                    "intensity": 0.65
                })
                last_t = t
                break

    music_curve = [
        {"timestamp": 0, "intensity": 0.0, "note": "silence"},
        {"timestamp": 1.5, "intensity": 0.75, "note": "intro"},
        {"timestamp": 4.5, "intensity": 0.12, "note": "voice begins"},
        {"timestamp": audio_duration - 4, "intensity": 0.12, "note": "near end"},
        {"timestamp": audio_duration - 1, "intensity": 0.65, "note": "outro"},
        {"timestamp": audio_duration, "intensity": 0.0, "note": "end"},
    ]

    return {
        "show_title": f"{mood.title()} Radio Show",
        "show_tagline": "Your podcast, professionally produced",
        "show_summary": "A podcast transformed into a professional radio show.",
        "keywords": [mood, "podcast", "radio"],
        "sfx_cues": cues[:max_cues],
        "music_curve": music_curve,
        "segments": [],
        "highlights": [],
        "production_notes": "Basic production plan (Claude API not available)",
    }
