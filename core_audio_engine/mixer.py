"""
mixer.py — Audio Ducking Mixer
===============================
Takes a voice audio file and a background music file, applies sidechain-style
audio ducking (lowers music volume whenever voice is present) via an
ffmpeg-python filter graph, and exports the mixed result as a .wav file.

Usage:
    from core_audio_engine.mixer import mix_with_ducking

    mix_with_ducking(
        voice_path="voice.wav",
        music_path="background_music.wav",
        output_path="mixed_output.wav",
    )
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import ffmpeg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ducking parameters — tweak these to taste
# ---------------------------------------------------------------------------
DEFAULT_DUCKING_PARAMS = {
    # Silence-detection threshold (dB).  Frames whose RMS is below this
    # value are treated as "voice is silent" → music returns to full volume.
    "silence_threshold_db": -30,
    # How much (in dB) to lower the music when voice is detected.
    "duck_amount_db": 14,
    # Attack / release in seconds — controls how quickly ducking kicks in
    # and how smoothly the music fades back.
    "attack_s": 0.3,
    "release_s": 0.8,
}


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    *,
    silence_threshold_db: float = DEFAULT_DUCKING_PARAMS["silence_threshold_db"],
    duck_amount_db: float = DEFAULT_DUCKING_PARAMS["duck_amount_db"],
    attack_s: float = DEFAULT_DUCKING_PARAMS["attack_s"],
    release_s: float = DEFAULT_DUCKING_PARAMS["release_s"],
) -> Path:
    """Mix *voice_path* over *music_path* with sidechain-style audio ducking.

    The ffmpeg ``sidechaincompress`` filter is applied so that the music track
    is compressed (ducked) whenever energy is detected in the voice track.

    Parameters
    ----------
    voice_path : str | Path
        Path to the voice / dialogue .wav file.
    music_path : str | Path
        Path to the background music .wav file.
    output_path : str | Path, optional
        Destination for the final mixed .wav file.
    silence_threshold_db : float
        dB threshold below which voice is considered silent.
    duck_amount_db : float
        How many dB to attenuate the music when voice is active.
    attack_s : float
        Seconds for the compressor to reach full ducking.
    release_s : float
        Seconds for the music to return to full volume after voice stops.

    Returns
    -------
    Path
        The resolved path to the exported mixed .wav file.

    Raises
    ------
    FileNotFoundError
        If either input file does not exist.
    RuntimeError
        If the ffmpeg process exits with a non-zero return code.
    """
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)

    # --- Validate inputs ---------------------------------------------------
    if not voice_path.is_file():
        raise FileNotFoundError(f"Voice file not found: {voice_path}")
    if not music_path.is_file():
        raise FileNotFoundError(f"Music file not found: {music_path}")

    # Ensure the output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Mixing voice '%s' with music '%s' → '%s'", voice_path, music_path, output_path)

    # --- Build the ffmpeg filter graph ------------------------------------
    # Two inputs: voice (sidechain signal) and music (target to duck).
    voice_input = ffmpeg.input(str(voice_path))
    music_input = ffmpeg.input(str(music_path))

    # Convert duck_amount_db into a ratio for the compressor.
    # sidechaincompress "ratio" controls how aggressively signal is reduced.
    # A ratio of ~6:1 paired with a low threshold gives a solid ducking feel.
    ratio = max(2.0, duck_amount_db / 3.0)

    # The sidechaincompress filter:
    #   - input 0 = music (the signal being compressed)
    #   - input 1 = voice (the sidechain / detector signal)
    ducked_music = ffmpeg.filter(
        [music_input, voice_input],
        "sidechaincompress",
        level_in=1,
        threshold=f"{_db_to_amplitude(silence_threshold_db):.6f}",
        ratio=ratio,
        attack=attack_s * 1000,   # ffmpeg expects milliseconds
        release=release_s * 1000,
    )

    # Re-read voice_input for the overlay mix (ffmpeg streams are consumed once)
    voice_for_mix = ffmpeg.input(str(voice_path))

    # Merge ducked music + original voice into a single stereo output.
    mixed = ffmpeg.filter([ducked_music, voice_for_mix], "amix", inputs=2, duration="longest")

    # --- Run ffmpeg --------------------------------------------------------
    try:
        (
            mixed
            .output(str(output_path), acodec="pcm_s16le", ar=44100, ac=2)
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as exc:
        stderr_output = exc.stderr.decode() if exc.stderr else "no stderr captured"
        raise RuntimeError(
            f"ffmpeg failed while mixing audio.\nstderr:\n{stderr_output}"
        ) from exc

    logger.info("Mix complete: %s (%.1f MB)", output_path, output_path.stat().st_size / 1_048_576)
    return output_path.resolve()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_to_amplitude(db: float) -> float:
    """Convert a decibel value to a linear amplitude (0.0–1.0 range)."""
    return 10 ** (db / 20.0)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Mix voice + music with audio ducking.")
    parser.add_argument("voice", help="Path to voice .wav file")
    parser.add_argument("music", help="Path to background music .wav file")
    parser.add_argument("-o", "--output", default="mixed_output.wav", help="Output .wav path")
    parser.add_argument("--duck-db", type=float, default=DEFAULT_DUCKING_PARAMS["duck_amount_db"])
    parser.add_argument("--attack", type=float, default=DEFAULT_DUCKING_PARAMS["attack_s"])
    parser.add_argument("--release", type=float, default=DEFAULT_DUCKING_PARAMS["release_s"])
    args = parser.parse_args()

    result = mix_with_ducking(
        args.voice,
        args.music,
        args.output,
        duck_amount_db=args.duck_db,
        attack_s=args.attack,
        release_s=args.release,
    )
    print(f"Done → {result}")
