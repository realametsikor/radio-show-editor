"""
engine.py — Master Radio Show Editor Pipeline
==============================================
Orchestrates the full production workflow:

    Raw podcast file
        → Diarize into host_A / host_B
        → Apply keyword-triggered SFX to each host track
        → Merge host tracks back together
        → Mix merged voice with background music (audio ducking)
        → Export radio_show_final.wav

Usage:
    from core_audio_engine.engine import run_pipeline

    run_pipeline(
        raw_audio="raw_podcast.wav",
        music_path="background_music.wav",
        sfx_map={"laugh": "sfx/laugh.wav", "money": "sfx/cash.wav"},
    )

Or from the command line:
    python -m core_audio_engine.engine raw_podcast.wav background_music.wav
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from core_audio_engine.diarize import diarize_speakers
from core_audio_engine.sfx import apply_sfx
from core_audio_engine.mixer import mix_with_ducking

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_FILENAME = "radio_show_final.wav"


def run_pipeline(
    raw_audio: str | Path,
    music_path: str | Path,
    sfx_map: Optional[dict[str, str | Path]] = None,
    output_path: str | Path = DEFAULT_OUTPUT_FILENAME,
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
    num_speakers: int = 2,
    whisper_model: str = "base",
    duck_amount_db: float = 14,
    attack_s: float = 0.3,
    release_s: float = 0.8,
    keep_intermediates: bool = True,
) -> Path:
    """Run the full radio-show production pipeline.

    Parameters
    ----------
    raw_audio : str | Path
        Path to the raw podcast .wav file.
    music_path : str | Path
        Path to the background music .wav file.
    sfx_map : dict, optional
        Keyword → SFX file mapping.  See ``sfx.apply_sfx`` for details.
    output_path : str | Path
        Final output file path.
    output_dir : str | Path
        Directory for intermediate files (diarized tracks, SFX tracks).
    hf_token : str, optional
        HuggingFace auth token for pyannote models.
    num_speakers : int
        Expected number of speakers in the podcast.
    whisper_model : str
        Whisper model size for SFX keyword detection.
    duck_amount_db : float
        How aggressively to duck the music (dB).
    attack_s : float
        Ducking attack time in seconds.
    release_s : float
        Ducking release time in seconds.
    keep_intermediates : bool
        If True, intermediate files are kept in *output_dir*.

    Returns
    -------
    Path
        Resolved path to ``radio_show_final.wav``.

    Raises
    ------
    FileNotFoundError
        If *raw_audio* or *music_path* does not exist.
    RuntimeError
        If any pipeline stage fails.
    """
    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)

    if not raw_audio.is_file():
        raise FileNotFoundError(f"Raw audio file not found: {raw_audio}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music file not found: {music_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # STEP 1 — Speaker Diarization
    # =====================================================================
    logger.info("=" * 60)
    logger.info("STEP 1/4: Speaker Diarization")
    logger.info("=" * 60)

    host_a_path, host_b_path = diarize_speakers(
        raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
        num_speakers=num_speakers,
    )
    logger.info("  host_A → %s", host_a_path)
    logger.info("  host_B → %s", host_b_path)

    # =====================================================================
    # STEP 2 — Apply SFX to each host track
    # =====================================================================
    logger.info("=" * 60)
    logger.info("STEP 2/4: Keyword-Triggered SFX")
    logger.info("=" * 60)

    host_a_sfx = output_dir / "host_A_sfx.wav"
    host_b_sfx = output_dir / "host_B_sfx.wav"

    apply_sfx(
        host_a_path,
        sfx_map=sfx_map,
        output_path=host_a_sfx,
        whisper_model=whisper_model,
    )

    apply_sfx(
        host_b_path,
        sfx_map=sfx_map,
        output_path=host_b_sfx,
        whisper_model=whisper_model,
    )
    logger.info("  host_A + SFX → %s", host_a_sfx)
    logger.info("  host_B + SFX → %s", host_b_sfx)

    # =====================================================================
    # STEP 3 — Merge host tracks back into a single voice track
    # =====================================================================
    logger.info("=" * 60)
    logger.info("STEP 3/4: Merging Host Tracks")
    logger.info("=" * 60)

    merged_voice_path = output_dir / "merged_voice.wav"
    _merge_tracks(host_a_sfx, host_b_sfx, merged_voice_path)
    logger.info("  Merged voice → %s", merged_voice_path)

    # =====================================================================
    # STEP 4 — Mix voice with background music (audio ducking)
    # =====================================================================
    logger.info("=" * 60)
    logger.info("STEP 4/4: Mixing with Background Music (Ducking)")
    logger.info("=" * 60)

    final_path = mix_with_ducking(
        voice_path=merged_voice_path,
        music_path=music_path,
        output_path=output_path,
        duck_amount_db=duck_amount_db,
        attack_s=attack_s,
        release_s=release_s,
    )

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE → %s", final_path)
    logger.info("=" * 60)

    # Optionally clean up intermediates
    if not keep_intermediates:
        for f in [host_a_path, host_b_path, host_a_sfx, host_b_sfx, merged_voice_path]:
            if f.is_file():
                f.unlink()
        logger.info("Intermediate files removed.")

    return final_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _merge_tracks(track_a: Path, track_b: Path, output: Path) -> Path:
    """Overlay two time-aligned audio tracks into one file.

    Both tracks are expected to be the same length (produced by diarize.py
    which pads silence to maintain alignment).
    """
    a = AudioSegment.from_wav(str(track_a))
    b = AudioSegment.from_wav(str(track_b))

    # Use the longer track as the base and overlay the shorter one.
    if len(a) >= len(b):
        merged = a.overlay(b)
    else:
        merged = b.overlay(a)

    output.parent.mkdir(parents=True, exist_ok=True)
    merged.export(str(output), format="wav")
    return output


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Run the full Radio Show Editor pipeline.",
    )
    parser.add_argument("raw_audio", help="Path to the raw podcast .wav file")
    parser.add_argument("music", help="Path to the background music .wav file")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_FILENAME, help="Final output path")
    parser.add_argument("--output-dir", default="output", help="Directory for intermediate files")
    parser.add_argument(
        "--sfx-map",
        default=None,
        help='JSON string or file mapping keywords to SFX paths, e.g. \'{"laugh": "sfx/laugh.wav"}\'',
    )
    parser.add_argument("--model", default="base", help="Whisper model size")
    parser.add_argument("--token", default=None, help="HuggingFace auth token")
    parser.add_argument("--keep-intermediates", action="store_true", default=True)
    parser.add_argument("--clean", action="store_true", help="Remove intermediate files after pipeline")
    args = parser.parse_args()

    custom_map = None
    if args.sfx_map:
        sfx_arg = Path(args.sfx_map)
        if sfx_arg.is_file():
            custom_map = json.loads(sfx_arg.read_text())
        else:
            custom_map = json.loads(args.sfx_map)

    result = run_pipeline(
        raw_audio=args.raw_audio,
        music_path=args.music,
        sfx_map=custom_map,
        output_path=args.output,
        output_dir=args.output_dir,
        hf_token=args.token,
        whisper_model=args.model,
        keep_intermediates=not args.clean,
    )
    print(f"\nFinal output → {result}")
