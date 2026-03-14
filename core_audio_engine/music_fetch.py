"""
music_fetch.py — Dynamic Background Music Fetcher (Jamendo)
============================================================
Fetches royalty-free background music from the Jamendo API based on a
user-selected mood/vibe tag, then downloads the best matching track into
the task's working directory.

Jamendo's free tier allows tag-based searching and provides direct MP3
download URLs — ideal for dynamic background music selection.

Usage:
    from core_audio_engine.music_fetch import fetch_music_for_mood

    music_path = fetch_music_for_mood(
        mood="chill",
        output_dir="/uploads/abc123/",
    )

Environment:
    JAMENDO_CLIENT_ID  —  Your Jamendo application Client ID.
    Sign up at https://developer.jamendo.com/
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mood → Jamendo tag mapping
# ---------------------------------------------------------------------------
# Maps the frontend mood slugs to Jamendo search tags.  Jamendo supports
# freeform tag strings (space- or plus-separated).
MOOD_TAG_MAP: dict[str, str] = {
    "chill": "chill",
    "lo-fi": "lofi+chill",
    "upbeat": "upbeat+happy",
    "news": "corporate+news",
    "ambient": "ambient+calm",
    "jazz": "jazz+smooth",
    "cinematic": "cinematic+epic",
    "acoustic": "acoustic+guitar",
    "electronic": "electronic+synth",
    "suspense": "suspense+dark",
}

JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks/"


def fetch_music_for_mood(
    mood: str,
    output_dir: str | Path,
    client_id: Optional[str] = None,
) -> Path:
    """Search the Jamendo API for a track matching *mood* and download it.

    Parameters
    ----------
    mood : str
        One of the mood keys defined in ``MOOD_TAG_MAP`` (e.g. "chill",
        "upbeat", "suspense").  Falls back to the raw mood string as a
        Jamendo tag if the mood is not in the map.
    output_dir : str | Path
        Directory to save the downloaded music file into.
    client_id : str, optional
        Jamendo application Client ID.  If not provided, reads from the
        ``JAMENDO_CLIENT_ID`` environment variable.

    Returns
    -------
    Path
        Resolved path to the downloaded music file.

    Raises
    ------
    RuntimeError
        If the Client ID is missing, no results are returned, or the
        download fails.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cid = client_id or os.environ.get("JAMENDO_CLIENT_ID", "")
    if not cid:
        raise RuntimeError(
            "Jamendo Client ID not configured. "
            "Set the JAMENDO_CLIENT_ID environment variable."
        )

    # Resolve tag(s) from mood
    tags = MOOD_TAG_MAP.get(mood, mood)

    logger.info("Searching Jamendo: mood=%s, tags='%s'", mood, tags)

    # ------------------------------------------------------------------
    # Step 1: Search the Jamendo API
    # ------------------------------------------------------------------
    params: dict = {
        "client_id": cid,
        "format": "json",
        "limit": 5,
        "tags": tags,
        "include": "musicinfo",
        "audioformat": "mp32",
        "order": "popularity_total",
    }

    try:
        resp = requests.get(JAMENDO_API_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Jamendo API request failed: {exc}") from exc

    data = resp.json()
    results = data.get("results", [])

    if not results:
        raise RuntimeError(
            f"No music found on Jamendo for mood '{mood}' (tags: '{tags}'). "
            "Try a different mood or check your Client ID."
        )

    # ------------------------------------------------------------------
    # Step 2: Pick the best track with a download URL
    # ------------------------------------------------------------------
    track = None
    audio_url = None

    for candidate in results:
        url = candidate.get("audiodownload") or candidate.get("audio")
        if url:
            track = candidate
            audio_url = url
            break

    if not track or not audio_url:
        raise RuntimeError(
            "Jamendo returned results but none had a downloadable audio URL."
        )

    # ------------------------------------------------------------------
    # Step 3: Download the track
    # ------------------------------------------------------------------
    output_file = output_dir / "background_music.mp3"

    logger.info(
        "Downloading track: '%s' by '%s' (id=%s) → %s",
        track.get("name", "unknown"),
        track.get("artist_name", "unknown"),
        track.get("id", "?"),
        output_file,
    )

    try:
        dl_resp = requests.get(audio_url, timeout=60, stream=True)
        dl_resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download music track: {exc}") from exc

    with open(output_file, "wb") as f:
        for chunk in dl_resp.iter_content(chunk_size=1024 * 64):
            f.write(chunk)

    file_size_mb = output_file.stat().st_size / 1_048_576
    logger.info("Downloaded %.1f MB → %s", file_size_mb, output_file)

    return output_file.resolve()
