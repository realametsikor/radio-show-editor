"""
diarize.py — Speaker Diarization & Source Separation
=====================================================
Uses pyannote.audio to perform speaker diarization on a single podcast .wav
file, then separates the audio into per-speaker files (host_A.wav, host_B.wav).

Prerequisites:
    1. A HuggingFace token with access to the pyannote gated models.
       Set the environment variable ``HF_AUTH_TOKEN`` **or** pass the token
       directly via the ``hf_token`` parameter.
    2. Accept the pyannote model licences on HuggingFace:
       - https://huggingface.co/pyannote/speaker-diarization-3.1
       - https://huggingface.co/pyannote/segmentation-3.0

Usage:
    from core_audio_engine.diarize import diarize_speakers

    host_a, host_b = diarize_speakers("podcast.wav", output_dir="output/")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def diarize_speakers(
    audio_path: str | Path,
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
    num_speakers: int = 2,
    min_segment_ms: int = 100,
) -> tuple[Path, Path]:
    """Diarize *audio_path* into individual speaker files.

    Parameters
    ----------
    audio_path : str | Path
        Path to the input podcast .wav file.
    output_dir : str | Path
        Directory where ``host_A.wav`` and ``host_B.wav`` will be written.
    hf_token : str, optional
        HuggingFace auth token.  Falls back to the ``HF_AUTH_TOKEN`` env var.
    num_speakers : int
        Expected number of speakers (default 2 for a two-host podcast).
    min_segment_ms : int
        Minimum segment duration in milliseconds.  Segments shorter than this
        are discarded to reduce noise.

    Returns
    -------
    tuple[Path, Path]
        Paths to ``host_A.wav`` and ``host_B.wav``.

    Raises
    ------
    FileNotFoundError
        If *audio_path* does not exist.
    EnvironmentError
        If no HuggingFace token is available.
    RuntimeError
        If diarization produces fewer than 2 speakers.
    """
    from pyannote.audio import Pipeline  # noqa: E402

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # --- Resolve HuggingFace token ----------------------------------------
    token = hf_token or os.environ.get("HF_AUTH_TOKEN")
    if not token:
        raise EnvironmentError(
            "A HuggingFace auth token is required for pyannote gated models. "
            "Set the HF_AUTH_TOKEN environment variable or pass hf_token=."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Load the diarization pipeline ------------------------------------
    logger.info("Loading pyannote speaker-diarization pipeline …")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=token,
    )

    # --- Run diarization ---------------------------------------------------
    logger.info("Running diarization on '%s' (expecting %d speakers) …", audio_path, num_speakers)
    diarization = pipeline(str(audio_path), num_speakers=num_speakers)

    # --- Collect per-speaker timeline segments -----------------------------
    speaker_segments: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker_label in diarization.itertracks(yield_label=True):
        speaker_segments.setdefault(speaker_label, []).append((turn.start, turn.end))

    detected = sorted(speaker_segments.keys())
    logger.info("Detected %d speaker(s): %s", len(detected), detected)

    if len(detected) < 2:
        raise RuntimeError(
            f"Diarization found only {len(detected)} speaker(s); at least 2 are "
            "needed to separate hosts.  Try adjusting num_speakers or check the "
            "input audio."
        )

    # --- Extract audio for the two most prominent speakers ----------------
    ranked = sorted(
        detected,
        key=lambda s: sum(end - start for start, end in speaker_segments[s]),
        reverse=True,
    )
    top_two = ranked[:2]

    full_audio = AudioSegment.from_wav(str(audio_path))
    results: list[Path] = []

    for idx, speaker_label in enumerate(top_two):
        tag = "A" if idx == 0 else "B"
        segments = speaker_segments[speaker_label]

        canvas = AudioSegment.silent(duration=len(full_audio), frame_rate=full_audio.frame_rate)

        for seg_start, seg_end in segments:
            start_ms = int(seg_start * 1000)
            end_ms = int(seg_end * 1000)
            if (end_ms - start_ms) < min_segment_ms:
                continue
            segment_audio = full_audio[start_ms:end_ms]
            canvas = canvas.overlay(segment_audio, position=start_ms)

        out_file = output_dir / f"host_{tag}.wav"
        canvas.export(str(out_file), format="wav")
        logger.info(
            "Exported host_%s (%s): %.1f s of speech → %s",
            tag,
            speaker_label,
            sum(e - s for s, e in segments),
            out_file,
        )
        results.append(out_file.resolve())

    return results[0], results[1]


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Diarize a podcast into two speaker tracks.")
    parser.add_argument("audio", help="Path to the podcast .wav file")
    parser.add_argument("-o", "--output-dir", default="output", help="Output directory")
    parser.add_argument("--num-speakers", type=int, default=2, help="Expected speaker count")
    parser.add_argument("--token", default=None, help="HuggingFace auth token")
    args = parser.parse_args()

    a, b = diarize_speakers(
        args.audio,
        args.output_dir,
        hf_token=args.token,
        num_speakers=args.num_speakers,
    )
    print(f"Done → {a}, {b}")
