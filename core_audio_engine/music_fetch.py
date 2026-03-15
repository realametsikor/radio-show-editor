from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

MOOD_TAG_MAP: dict[str, list[str]] = {
    # Music styles
    "lo-fi":        ["lofi", "chillhop", "chill+study"],
    "upbeat":       ["upbeat+pop", "happy+energetic", "uplifting"],
    "ambient":      ["ambient+calm", "atmospheric", "meditation"],
    "jazz":         ["jazz+smooth", "lounge+jazz", "bossa+nova"],
    "cinematic":    ["cinematic+epic", "orchestral", "dramatic+film"],
    "acoustic":     ["acoustic+guitar", "folk+acoustic", "fingerpicking"],
    "electronic":   ["electronic+modern", "synthwave", "chillwave"],
    "hiphop":       ["hiphop+instrumental", "trap+beats", "urban+instrumental"],
    "gospel":       ["gospel+inspirational", "christian+uplifting", "worship+music"],
    "afrobeats":    ["afrobeats", "african+rhythm", "afropop+instrumental"],
    "rnb":          ["rnb+soul", "soul+music", "neo+soul"],
    "reggae":       ["reggae", "dub+reggae", "caribbean+chill"],
    "classical":    ["classical+orchestra", "piano+classical", "symphony"],
    "country":      ["country+folk", "americana", "bluegrass"],
    "latin":        ["latin+jazz", "salsa+instrumental", "bossa+nova"],
    # Show styles
    "news":         ["corporate+news", "background+news", "informational"],
    "morning_drive":["upbeat+pop", "morning+energy", "feel+good"],
    "comedy":       ["funny+background", "quirky+music", "playful+instrumental"],
    "true_crime":   ["suspense+dark", "mystery+thriller", "noir+music"],
    "tech":         ["electronic+modern", "future+bass", "tech+background"],
    "sports":       ["energetic+sport", "pump+up+music", "action+background"],
    "war":          ["cinematic+war", "epic+military", "dramatic+orchestra"],
    "documentary":  ["documentary+background", "ambient+cinematic", "thoughtful"],
    "talk_show":    ["jazz+lounge", "upbeat+background", "talk+show+music"],
    "business":     ["corporate+background", "professional+music", "ambient+work"],
    "spiritual":    ["meditation+music", "spiritual+ambient", "peaceful+music"],
    "horror":       ["dark+ambient", "horror+background", "suspense+music"],
    "kids":         ["children+music", "playful+fun", "kids+background"],
    "romance":      ["romantic+music", "love+songs+instrumental", "soft+piano"],
    "science":      ["discovery+music", "space+ambient", "science+documentary"],
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
            logger.warning("Jamendo failed for '%s': %s", tags, exc)
            continue

    # Retry without instrumental filter
    if not results:
        logger.info("Retrying without instrumental filter...")
        try:
            params = {
                "client_id": cid,
                "format": "json",
                "limit": 10,
                "tags": tag_variants[0],
                "audioformat": "mp32",
                "order": "popularity_total",
            }
            resp = requests.get(JAMENDO_API_URL, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:
            raise RuntimeError(f"Jamendo API failed: {exc}") from exc

    if not results:
        raise RuntimeError(f"No music found for mood '{mood}'.")

    # Pick random from top 5 for variety
    top = results[:5]
    random.shuffle(top)

    track = None
    audio_url = None
    for candidate in top:
        url = candidate.get("audiodownload") or candidate.get("audio")
        if url:
            track = candidate
            audio_url = url
            break

    if not track or not audio_url:
        raise RuntimeError("No downloadable track found.")

    logger.info(
        "Selected: '%s' by '%s'",
        track.get("name", "unknown"),
        track.get("artist_name", "unknown"),
    )

    output_file = output_dir / f"background_music_{mood}.mp3"
    try:
        dl_resp = requests.get(audio_url, timeout=60, stream=True)
        dl_resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Download failed: {exc}") from exc

    with open(output_file, "wb") as f:
        for chunk in dl_resp.iter_content(chunk_size=65536):
            f.write(chunk)

    logger.info(
        "Downloaded %.1f MB → %s",
        output_file.stat().st_size / 1_048_576,
        output_file,
    )
    return output_file.resolve()
