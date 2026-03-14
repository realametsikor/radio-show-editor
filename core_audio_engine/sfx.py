"""
sfx.py — Keyword-Triggered Sound Effects Overlay
=================================================
Uses OpenAI Whisper to transcribe an audio file with word-level timestamps,
searches for configurable trigger keywords, and overlays short SFX audio clips
at the exact moments those words are spoken.

Usage:
    from core_audio_engine.sfx import apply_sfx

    result = apply_sfx(
        audio_path="host_A.wav",
        sfx_map={
            "laugh":  "sfx/laugh.wav",
            "money":  "sfx/cash_register.wav",
            "wow":    "sfx/wow_stinger.wav",
        },
        output_path="host_A_with_sfx.wav",
    )
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default keyword → SFX mapping (override via parameter)
# ---------------------------------------------------------------------------
DEFAULT_SFX_MAP: dict[str, str] = {
    "laugh":  "sfx/laugh.wav",
    "money":  "sfx/cash_register.wav",
    "wow":    "sfx/wow_stinger.wav",
}

# Maximum SFX volume reduction (dB) so effects don't overpower the voice.
SFX_VOLUME_REDUCTION_DB = 5


def apply_sfx(
    audio_path: str | Path,
    sfx_map: Optional[dict[str, str | Path]] = None,
    output_path: str | Path = "audio_with_sfx.wav",
    *,
    whisper_model: str = "base",
    sfx_volume_db: float = -SFX_VOLUME_REDUCTION_DB,
) -> Path:
    """Transcribe *audio_path*, find keywords, and overlay SFX at those timestamps.

    Parameters
    ----------
    audio_path : str | Path
        Path to the input .wav file to process.
    sfx_map : dict[str, str | Path], optional
        Mapping of lowercase keyword → path to a short SFX .wav file.
        Falls back to ``DEFAULT_SFX_MAP`` if not provided.
    output_path : str | Path
        Destination path for the output .wav file with SFX overlaid.
    whisper_model : str
        Whisper model size (``tiny``, ``base``, ``small``, ``medium``, ``large``).
        Larger models are more accurate but slower.
    sfx_volume_db : float
        Volume adjustment (in dB) applied to each SFX clip before mixing.
        Negative values reduce volume.

    Returns
    -------
    Path
        Resolved path to the exported file with SFX applied.

    Raises
    ------
    FileNotFoundError
        If *audio_path* or any SFX file in *sfx_map* does not exist.
    RuntimeError
        If Whisper fails to produce word-level timestamps.
    """
    # Lazy-import whisper so the module can be imported without the heavy dep.
    import whisper  # noqa: E402

    audio_path = Path(audio_path)
    output_path = Path(output_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    mapping = _resolve_sfx_map(sfx_map or DEFAULT_SFX_MAP)

    # --- Transcribe with word-level timestamps ----------------------------
    logger.info("Loading Whisper model '%s' …", whisper_model)
    model = whisper.load_model(whisper_model)

    logger.info("Transcribing '%s' …", audio_path)
    result = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language="en",
    )

    # Collect every word with its start time from the Whisper segments.
    word_hits: list[tuple[str, float, str]] = []  # (keyword, timestamp_s, sfx_path)

    for segment in result.get("segments", []):
        for word_info in segment.get("words", []):
            word_text = word_info.get("word", "").strip().lower().strip(".,!?;:'\"")
            timestamp = word_info.get("start")
            if timestamp is None:
                continue
            for keyword, sfx_path in mapping.items():
                if keyword in word_text:
                    word_hits.append((keyword, timestamp, sfx_path))
                    logger.debug(
                        "  ✓ keyword '%s' detected at %.2f s → %s", keyword, timestamp, sfx_path
                    )

    logger.info("Found %d keyword hit(s) across %d segment(s).", len(word_hits), len(result.get("segments", [])))

    if not word_hits:
        logger.warning("No keyword matches found — exporting unmodified audio.")

    # --- Overlay SFX clips ------------------------------------------------
    base_audio = AudioSegment.from_wav(str(audio_path))

    # Pre-load SFX clips to avoid reading the same file multiple times.
    sfx_cache: dict[str, AudioSegment] = {}

    for keyword, timestamp_s, sfx_path in word_hits:
        if sfx_path not in sfx_cache:
            sfx_cache[sfx_path] = AudioSegment.from_file(sfx_path) + sfx_volume_db

        sfx_clip = sfx_cache[sfx_path]
        position_ms = int(timestamp_s * 1000)

        # Ensure the overlay doesn't extend past the end of the base audio.
        remaining_ms = len(base_audio) - position_ms
        if remaining_ms <= 0:
            continue
        if len(sfx_clip) > remaining_ms:
            sfx_clip = sfx_clip[:remaining_ms]

        base_audio = base_audio.overlay(sfx_clip, position=position_ms)

    # --- Export ------------------------------------------------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base_audio.export(str(output_path), format="wav")
    logger.info("Exported audio with SFX → %s", output_path)

    return output_path.resolve()


# ---------------------------------------------------------------------------
# Transcript helper (useful for external inspection)
# ---------------------------------------------------------------------------

def transcribe_with_timestamps(
    audio_path: str | Path,
    whisper_model: str = "base",
) -> list[dict]:
    """Return a flat list of ``{word, start, end}`` dicts for *audio_path*.

    Handy for debugging or for feeding into other pipeline stages.
    """
    import whisper  # noqa: E402

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = whisper.load_model(whisper_model)
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en")

    words: list[dict] = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            words.append({
                "word": w.get("word", "").strip(),
                "start": w.get("start"),
                "end": w.get("end"),
            })
    return words


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_sfx_map(raw_map: dict[str, str | Path]) -> dict[str, str]:
    """Validate that all SFX files exist and return a normalised mapping."""
    resolved: dict[str, str] = {}
    for keyword, sfx_path in raw_map.items():
        p = Path(sfx_path)
        if not p.is_file():
            logger.warning("SFX file for keyword '%s' not found at '%s' — skipping.", keyword, p)
            continue
        resolved[keyword.lower()] = str(p)
    return resolved


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Overlay SFX on keyword triggers.")
    parser.add_argument("audio", help="Path to the input .wav file")
    parser.add_argument("-o", "--output", default="audio_with_sfx.wav", help="Output .wav path")
    parser.add_argument(
        "--sfx-map",
        type=str,
        default=None,
        help='JSON string or file mapping keywords to SFX paths, e.g. \'{"laugh": "sfx/laugh.wav"}\'',
    )
    parser.add_argument("--model", default="base", help="Whisper model size")
    args = parser.parse_args()

    # Parse the optional SFX map.
    custom_map = None
    if args.sfx_map:
        sfx_arg = Path(args.sfx_map)
        if sfx_arg.is_file():
            custom_map = json.loads(sfx_arg.read_text())
        else:
            custom_map = json.loads(args.sfx_map)

    result_path = apply_sfx(
        args.audio,
        sfx_map=custom_map,
        output_path=args.output,
        whisper_model=args.model,
    )
    print(f"Done → {result_path}")
