"""diarize.py — Speaker separation using Pyannote AI."""
from __future__ import annotations

import logging
import torch
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# Cache the pipeline locally so we don't redownload it on every run
_PIPELINE_CACHE = None

def diarize_speakers(audio_path: str | Path, output_dir: str | Path, hf_token: str = None) -> list[Path]:
    """
    Analyzes the audio file and slices it into separate tracks for each speaker.
    Gracefully handles 1 to N speakers without crashing.
    """
    global _PIPELINE_CACHE
    
    logger.info("Starting Pyannote Speaker Diarization...")
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    
    if _PIPELINE_CACHE is None:
        from pyannote.audio import Pipeline
        logger.info("Loading Pyannote AI model into memory...")
        _PIPELINE_CACHE = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )
        # Force CPU to ensure compatibility across all Hugging Face tiers
        _PIPELINE_CACHE.to(torch.device("cpu"))
        
    # 1. Run the AI Inference
    diarization = _PIPELINE_CACHE(str(audio_path))
    
    # 2. Group timestamps by speaker
    speaker_segments = {}
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if speaker not in speaker_segments:
            speaker_segments[speaker] = []
        speaker_segments[speaker].append((turn.start, turn.end))
        
    logger.info(f"Pyannote identified {len(speaker_segments)} unique speaker(s).")
    
    # 3. Slice and Export the audio
    full_audio = AudioSegment.from_wav(str(audio_path))
    output_paths = []
    
    for i, (speaker_label, segments) in enumerate(speaker_segments.items()):
        spk_audio = AudioSegment.empty()
        
        # Stitch all of this speaker's talking parts together
        for start, end in segments:
            # PyDub works in milliseconds
            spk_audio += full_audio[int(start * 1000):int(end * 1000)]
            
        out_file = output_dir / f"host_{i}_raw.wav"
        spk_audio.export(str(out_file), format="wav")
        output_paths.append(out_file)
        logger.info(f"Exported {speaker_label} track to {out_file.name}")
        
    # =========================================================================
    # 🛡️ THE FAILSAFE (Removed the old "ValueError: at least 2 needed" crash)
    # If the AI completely fails and finds 0 speakers, we just return the raw
    # audio as a single "host" so the podcast mix can still finish.
    # =========================================================================
    if len(output_paths) == 0:
        logger.warning("Pyannote found 0 speakers. Triggering failsafe to pass raw audio.")
        out_file = output_dir / "host_0_raw.wav"
        full_audio.export(str(out_file), format="wav")
        return [out_file]
        
    return output_paths
