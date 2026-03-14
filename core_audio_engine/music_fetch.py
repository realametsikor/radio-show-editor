"""
music_fetch.py — Dynamic Background Music Fetcher
===================================================
Fetches royalty-free background music from the Pixabay Music API based on a
user-selected mood/vibe, then downloads the best matching track into the
task's working directory.

Usage:
    from core_audio_engine.music_fetch import fetch_music_for_mood

    music_path = fetch_music_for_mood(
        mood="lo-fi",
        output_dir="/uploads/abc123/",
    )
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mood → Pixabay search query mapping
# ---------------------------------------------------------------------------
# Maps the frontend mood slugs to effective Pixabay search terms and optional
# category filters.  Pixabay's music categories include: backgrounds, beats,
# classical, electronic, etc.
MOOD_SEARCH_MAP: dict[str, dict] = {
    "lo-fi": {
        "q": "lo-fi chill",
        "category": "",
    },
    "upbeat": {
        "q": "upbeat happy energy",
        "category": "",
    },
    "news": {
        "q": "news broadcast corporate",
        "category": "",
    },
    "ambient": {
        "q": "ambient atmospheric calm",
        "category": "",
    },
    "jazz": {
        "q": "jazz smooth",
        "category": "",
    },
    "cinematic": {
        "q": "cinematic epic trailer",
        "category": "",
    },
    "acoustic": {
        "q": "acoustic warm guitar",
        "category": "",
    },
    "electronic": {
        "q": "electronic modern synth",
        "category": "",
    },
}

PIXABAY_API_URL = "https://pixabay.com/api/"


def fetch_music_for_mood(
    mood: str,
    output_dir: str | Path,
    api_key: Optional[str] = None,
) -> Path:
    """Search the Pixabay API for music matching *mood* and download the first result.

    Parameters
    ----------
    mood : str
        One of the mood keys defined in ``MOOD_SEARCH_MAP`` (e.g. "lo-fi",
        "upbeat", "news").  Falls back to a generic "background music" search
        if the mood is unrecognised.
    output_dir : str | Path
        Directory to save the downloaded music file into.
    api_key : str, optional
        Pixabay API key.  If not provided, reads from ``PIXABAY_API_KEY`` env var.

    Returns
    -------
    Path
        Resolved path to the downloaded music file.

    Raises
    ------
    RuntimeError
        If the API key is missing, no results are returned, or the download fails.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    key = api_key or os.environ.get("PIXABAY_API_KEY", "")
    if not key:
        raise RuntimeError(
            "Pixabay API key not configured. "
            "Set the PIXABAY_API_KEY environment variable."
        )

    # Resolve search parameters from mood
    search_config = MOOD_SEARCH_MAP.get(mood, {"q": "background music", "category": ""})
    search_query = search_config["q"]
    category = search_config.get("category", "")

    logger.info("Searching Pixabay music: mood=%s, query='%s'", mood, search_query)

    # ------------------------------------------------------------------
    # Step 1: Search the Pixabay API
    # ------------------------------------------------------------------
    params: dict = {
        "key": key,
        "q": search_query,
        "per_page": 5,
        "safesearch": "true",
        "order": "popular",
    }
    if category:
        params["category"] = category

    try:
        resp = requests.get(PIXABAY_API_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Pixabay API request failed: {exc}") from exc

    data = resp.json()
    hits = data.get("hits", [])

    if not hits:
        raise RuntimeError(
            f"No music found on Pixabay for mood '{mood}' (query: '{search_query}'). "
            "Try a different mood or check your API key."
        )

    # ------------------------------------------------------------------
    # Step 2: Pick the best track
    # ------------------------------------------------------------------
    # Prefer tracks that have a direct audio download URL.
    track = hits[0]
    audio_url = track.get("previewURL") or track.get("videos", {}).get("medium", {}).get("url")

    if not audio_url:
        # Fallback: try other hits
        for hit in hits[1:]:
            audio_url = hit.get("previewURL")
            if audio_url:
                track = hit
                break

    if not audio_url:
        raise RuntimeError(
            "Pixabay returned results but none had a downloadable audio URL."
        )

    # ------------------------------------------------------------------
    # Step 3: Download the track
    # ------------------------------------------------------------------
    # Determine file extension from URL or default to .mp3
    ext = ".mp3"
    if ".wav" in audio_url:
        ext = ".wav"

    output_file = output_dir / f"background_music{ext}"

    logger.info(
        "Downloading track: '%s' (id=%s) → %s",
        track.get("tags", "unknown"),
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
