from __future__ import annotations

import logging
import os
import gc
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

logger = logging.getLogger(__name__)


def diarize_speakers(
    audio_path: str | Path,
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
    num_speakers: int = 2,
    min_segment_ms: int = 100,
) -> tuple[Path, Path]:
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    token = hf_token or os.environ.get("HF_AUTH_TOKEN")
    if not token:
        raise EnvironmentError(
            "A HuggingFace auth token is required for pyannote gated models. "
            "Set the HF_AUTH_TOKEN environment variable or pass hf_token=."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    # Use cached pipeline from engine if available, otherwise load fresh
    try:
        from core_audio_engine.engine import _get_pipeline
        logger.info("Loading pyannote pipeline (cached) …")
        pipeline = _get_pipeline(token)
    except Exception:
        from pyannote.audio import Pipeline
        logger.info("Loading pyannote speaker-diarization pipeline (fresh) …")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=token,
        )

    logger.info("Running diarization on '%s' (expecting %d speakers) …", audio_path, num_speakers)
    result = pipeline(str(audio_path), num_speakers=num_speakers)

    # Force PyTorch to release memory after inference is done
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    gc.collect()

    # Handle both Annotation and DiarizeOutput (community model)
    if hasattr(result, "speaker_diarization"):
        annotation = result.speaker_diarization
    else:
        annotation = result

    speaker_segments: dict[str, list[tuple[float, float]]] = {}
    for turn, _, speaker_label in annotation.itertracks(yield_label=True):
        speaker_segments.setdefault(speaker_label, []).append((turn.start, turn.end))

    detected = sorted(speaker_segments.keys())
    logger.info("Detected %d speaker(s): %s", len(detected), detected)

    if len(detected) < 2:
        raise RuntimeError(
            f"Diarization found only {len(detected)} speaker(s); at least 2 are "
            "needed to separate hosts.  Try adjusting num_speakers or check the "
            "input audio."
        )

    ranked = sorted(
        detected,
        key=lambda s: sum(end - start for start, end in speaker_segments[s]),
        reverse=True,
    )
    top_two = ranked[:2]

    # Load the master audio file
    full_audio = AudioSegment.from_wav(str(audio_path))
    results: list[Path] = []

    for idx, speaker_label in enumerate(top_two):
        tag = "A" if idx == 0 else "B"
        segments = speaker_segments[speaker_label]

        logger.info(f"Building track for host_{tag} linearly (Memory Safe Mode)...")
        
        # Build an array of chunks instead of overlaying on a massive canvas
        track_chunks = []
        last_end_ms = 0

        for seg_start, seg_end in segments:
            start_ms = int(seg_start * 1000)
            end_ms = int(seg_end * 1000)
            
            if (end_ms - start_ms) < min_segment_ms:
                continue
                
            # Fill the gap with silence
            if start_ms > last_end_ms:
                track_chunks.append(AudioSegment.silent(duration=start_ms - last_end_ms, frame_rate=full_audio.frame_rate))
                
            # Add the actual speech
            track_chunks.append(full_audio[start_ms:end_ms])
            last_end_ms = end_ms

        # Pad the very end with silence if needed
        if last_end_ms < len(full_audio):
            track_chunks.append(AudioSegment.silent(duration=len(full_audio) - last_end_ms, frame_rate=full_audio.frame_rate))

        # Sum all chunks efficiently at the very end
        out_file = output_dir / f"host_{tag}.wav"
        final_track = sum(track_chunks, AudioSegment.empty())
        final_track.export(str(out_file), format="wav")

        logger.info(
            "Exported host_%s (%s): %.1f s of speech → %s",
            tag,
            speaker_label,
            sum(e - s for s, e in segments),
            out_file,
        )
        results.append(out_file.resolve())

        # The Ninja Assassin: Aggressively wipe this host's data from RAM
        del track_chunks
        del final_track
        gc.collect()

    # Final cleanup of the massive original file
    del full_audio
    gc.collect()

    return results[0], results[1]


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
