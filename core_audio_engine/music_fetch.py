from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MOOD_TAG_MAP: dict[str, list[str]] = {
    "lo-fi":       ["lofi", "chillhop", "chill+study"],
    "upbeat":      ["upbeat+pop", "happy+energetic", "uplifting"],
    "news":        ["corporate+news", "background+news", "informational"],
    "ambient":     ["ambient+calm", "atmospheric", "meditation"],
    "jazz":        ["jazz+smooth", "lounge+jazz", "bossa+nova"],
    "cinematic":   ["cinematic+epic", "orchestral", "dramatic+film"],
    "acoustic":    ["acoustic+guitar", "folk+acoustic", "singer+songwriter"],
    "electronic":  ["electronic+modern", "synthwave", "chillwave"],
}

JAMENDO_API_URL = "https://api.jamendo.com/v3.0/tracks/"


def fetch_music_for_mood(
    mood: str,
    output_dir: str | Path,
    client_id: Optional[str] = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cid = client_id or os.environ.get("JAMENDO_CLIENT_ID", "")
    if not cid:
        raise RuntimeError("JAMENDO_CLIENT_ID not set.")

    # Try each tag variant until we get results
    tag_variants = MOOD_TAG_MAP.get(mood, [mood])
    results = []

    for tags in tag_variants:
        logger.info("Searching Jamendo: mood=%s tags='%s'", mood, tags)
        params = {
            "client_id": cid,
            "format": "json",
            "limit": 10,
            "tags": tags,
            "audioformat": "mp32",
            "order": "popularity_total",
            "include": "musicinfo",
            # Only instrumental tracks — no vocals over podcast speech
            "vocalinstrumental": "instrumental",
        }

        try:
            resp = requests.get(JAMENDO_API_URL, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                logger.info("Found %d tracks for tags '%s'", len(results), tags)
                break
        except requests.RequestException as exc:
            logger.warning("Jamendo request failed for tags '%s': %s", tags, exc)
            continue

    # Fallback without instrumental filter
    if not results:
        logger.info("Retrying without instrumental filter...")
        params = {
            "client_id": cid,
            "format": "json",
            "limit": 10,
            "tags": tag_variants[0],
            "audioformat": "mp32",
            "order": "popularity_total",
        }
        try:
            resp = requests.get(JAMENDO_API_URL, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:
            raise RuntimeError(f"Jamendo API failed: {exc}") from exc

    if not results:
        raise RuntimeError(f"No music found on Jamendo for mood '{mood}'.")

    # Pick a random track from top 5 for variety
    top_results = results[:5]
    random.shuffle(top_results)

    track = None
    audio_url = None

    for candidate in top_results:
        url = candidate.get("audiodownload") or candidate.get("audio")
        if url:
            track = candidate
            audio_url = url
            break

    if not track or not audio_url:
        raise RuntimeError("No downloadable track found on Jamendo.")

    logger.info(
        "Selected: '%s' by '%s'",
        track.get("name", "unknown"),
        track.get("artist_name", "unknown"),
    )

    # Download
    output_file = output_dir / f"background_music_{mood}.mp3"

    try:
        dl_resp = requests.get(audio_url, timeout=60, stream=True)
        dl_resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to download track: {exc}") from exc

    with open(output_file, "wb") as f:
        for chunk in dl_resp.iter_content(chunk_size=65536):
            f.write(chunk)

    logger.info(
        "Downloaded %.1f MB → %s",
        output_file.stat().st_size / 1_048_576,
        output_file,
    )

    return output_file.resolve()
