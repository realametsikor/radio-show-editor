"""mixer.py — Intelligent audio ducking and pacing."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from pydub import AudioSegment

logger = logging.getLogger(__name__)

def add_natural_pauses(voice_audio: AudioSegment) -> AudioSegment:
    """Adds a slight breathable padding to the raw voice track."""
    logger.info("Padding voice track with natural breath room...")
    pad = AudioSegment.silent(duration=800)
    return pad + voice_audio + pad

def mix_with_ducking(
    voice_path: str | Path, 
    music_path: str | Path, 
    output_path: str | Path, 
    music_curve: list = None
) -> Path:
    """
    Enterprise-Grade FFmpeg Sidechain Auto-Ducker.
    Uses a mathematically perfect channel-merge to prevent the 'volume halving' 
    bug. The music will dynamically breathe with the conversation!
    """
    logger.info("Executing Broadcast-Grade FFmpeg Sidechain Ducker...")
    
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)
    
    # 1. First ensure music is looped to be long enough using Pydub
    voice_seg = AudioSegment.from_wav(str(voice_path))
    music_seg = AudioSegment.from_file(str(music_path))
    
    if len(music_seg) < len(voice_seg):
        loops = (len(voice_seg) // len(music_seg)) + 1
        music_seg = music_seg * loops
        
    # Add a gentle fade out to the very end of the music tail
    music_seg = music_seg[:len(voice_seg)].fade_out(3000)
    
    # Save the looped music to a temp file for FFmpeg
    temp_music_path = music_path.parent / "temp_music_looped.wav"
    music_seg.export(str(temp_music_path), format="wav")

    # =========================================================================
    # 🎛️ THE "NO-VOLUME-DROP" SIDECHAIN GRAPH
    # We split the voice. One copy triggers the compressor, the other is 
    # merged flawlessly with the ducked music using a 4-channel stereo pan.
    # =========================================================================
    
    # threshold=0.03 (-30dB) reacts to quiet speech
    # ratio=6.0 provides aggressive ducking so voices are crystal clear
    # release=800 creates a beautiful 0.8s swell during conversational pauses
    filter_complex = (
        "[0:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.85[music];"
        "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.10[voice];"
        "[voice]asplit=2[voice_sc][voice_mix];"
        "[music][voice_sc]sidechaincompress=threshold=0.03:ratio=6.0:attack=10:release=800[ducked_music];"
        "[ducked_music][voice_mix]amerge=inputs=2[merged];"
        "[merged]pan=stereo|c0<c0+c2|c1<c1+c3[out]"
    )
    
    try:
        subprocess.run([
            "ffmpeg", 
            "-i", str(temp_music_path),
            "-i", str(voice_path),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-y", str(output_path)
        ], check=True, capture_output=True)
        
        temp_music_path.unlink(missing_ok=True)
        logger.info("✅ Perfect FFmpeg Sidechain Mix Complete!")
        return output_path
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"FFmpeg ducking failed: {error_msg}")
        
        # Failsafe in case of catastrophic FFmpeg failure
        logger.info("Falling back to static PyDub mix...")
        mixed = (music_seg - 18).overlay(voice_seg)
        mixed.export(str(output_path), format="wav")
        return output_path
