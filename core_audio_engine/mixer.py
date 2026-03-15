"""
Professional radio mixer using ffmpeg sidechaincompress.
Optimized for NotebookLM audio with dynamic mid-roll music breaks!
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pydub import AudioSegment, effects
from pydub.silence import detect_silence

logger = logging.getLogger(__name__)


def create_radio_breaks(voice: AudioSegment) -> AudioSegment:
    """
    Finds natural pauses in the speech and inserts longer silences (breaks).
    Because of the ducking compressor, these silences will cause the background
    music to automatically swell up, creating a professional radio transition!
    """
    duration_sec = len(voice) / 1000.0
    
    # Decide how many breaks based on length (1 break every ~2.5 minutes)
    num_breaks = int(duration_sec // 150)
    if num_breaks == 0 and duration_sec > 45:
        num_breaks = 1  # At least 1 break if the clip is over 45 seconds

    if num_breaks == 0:
        return voice

    logger.info(f"Attempting to insert {num_breaks} music break(s)...")
    
    # Look for natural breaths/pauses > 400ms to avoid cutting off words
    silences = detect_silence(voice, min_silence_len=400, silence_thresh=voice.dBFS-16)
    
    if not silences:
        logger.warning("No natural pauses found. Skipping breaks.")
        return voice

    target_times = [len(voice) * (i + 1) / (num_breaks + 1) for i in range(num_breaks)]
    break_points = []
    
    for target in target_times:
        # Find the closest natural pause to our ideal target time
        best_silence = min(silences, key=lambda s: abs(s[0] - target))
        break_points.append(best_silence[0])
        
    # Sort descending so we insert from back to front (prevents shifting audio)
    break_points.sort(reverse=True)
    
    result = voice
    for bp in break_points:
        # Insert 4 seconds of pure silence! 
        # The compressor will release, and music will swell to full volume.
        break_silence = AudioSegment.silent(duration=4000, frame_rate=voice.frame_rate)
        result = result[:bp] + break_silence + result[bp:]
        
    logger.info(f"Successfully added {len(break_points)} music break(s).")
    return result


def _loop_music(music: AudioSegment, target_ms: int) -> AudioSegment:
    """Loop music with crossfades to avoid hard-cut transitions."""
    if len(music) >= target_ms:
        return music[:target_ms]

    xfade  = min(3000, len(music) // 4)
    result = music
    while len(result) < target_ms:
        result = result.append(music, crossfade=xfade) if xfade > 100 else result + music
    return result[:target_ms]


def mix_with_ducking(
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path = "mixed_output.wav",
    music_curve: list[dict] | None = None,
    *,
    music_volume_db: float = -15.0,  
    duck_ratio: float      = 8.0,    
    attack_ms: int         = 80,     
    release_ms: int        = 800,    
    voice_boost_db: float  = 0.0,    
) -> Path:
    """
    Professional radio mix tailored for high-quality NotebookLM audio.
    """
    voice_path  = Path(voice_path)
    music_path  = Path(music_path)
    output_path = Path(output_path)

    if not voice_path.is_file():
        raise FileNotFoundError("Voice not found: " + str(voice_path))
    if not music_path.is_file():
        raise FileNotFoundError("Music not found: " + str(music_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_voice = output_path.parent / "_tmp_voice_prepared.wav"
    tmp_music = output_path.parent / "_tmp_music_prepared.wav"

    try:
        # 1. Prepare Voice (Inject the Radio Breaks!)
        logger.info("Preparing voice track (adding breaks)...")
        voice_audio = AudioSegment.from_wav(str(voice_path))
        if voice_audio.channels == 1:
            voice_audio = voice_audio.set_channels(2)
        if voice_audio.frame_rate != 44100:
            voice_audio = voice_audio.set_frame_rate(44100)
            
        voice_audio = create_radio_breaks(voice_audio)
        voice_audio.export(str(tmp_voice), format="wav")
        voice_duration_ms = len(voice_audio)

        # 2. Prepare music
        logger.info("Preparing music...")
        music = AudioSegment.from_file(str(music_path))
        if music.channels == 1:
            music = music.set_channels(2)
        if music.frame_rate != 44100:
            music = music.set_frame_rate(44100)

        music = _loop_music(music, voice_duration_ms + 12000)
        music = music.fade_in(2000).fade_out(5000)
        music.export(str(tmp_music), format="wav")

        # 3. Build ffmpeg filter chain tailored for NotebookLM
        filter_str = (
            f"[0:a]aformat=channel_layouts=stereo,"
            f"volume={music_volume_db}dB,"
            f"equalizer=f=120:width_type=o:width=1:g=2,"
            f"equalizer=f=8000:width_type=o:width=1:g=1.5"
            f"[mp];"
            f"[1:a]aformat=channel_layouts=stereo,"
            f"highpass=f=80," 
            f"acompressor=threshold=0.1:ratio=2:attack=5:release=50:makeup=1," 
            f"volume={voice_boost_db}dB"
            f"[vp];"
            f"[vp]asplit=2[sc][vm];"
            f"[mp][sc]sidechaincompress="
            f"threshold=0.015:"
            f"ratio={duck_ratio:.1f}:"
            f"attack={attack_ms}:"
            f"release={release_ms}:"
            f"makeup=1.5"
            f"[ducked];"
            f"[ducked][vm]amix=inputs=2:duration=longest:weights=1 4[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_music),
            "-i", str(tmp_voice),
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]

        logger.info("Running ffmpeg sidechain mix...")
        result = subprocess.run(cmd, capture_output=True, timeout=1800)
        if result.returncode == 0:
            logger.info("✅ NotebookLM Mix complete!")
        else:
            error = result.stderr.decode()
            raise RuntimeError("ffmpeg mix failed: " + error[-200:])

    except Exception as exc:
        logger.warning("ffmpeg mix failed (%s) — pydub fallback", exc)
        _pydub_fallback_mix(
            voice_path=tmp_voice if tmp_voice.exists() else voice_path,
            music_path=tmp_music if tmp_music.exists() else music_path,
            output_path=output_path,
            music_volume_db=music_volume_db,
        )
    finally:
        try:
            tmp_music.unlink()
            tmp_voice.unlink()
        except Exception:
            pass

    return output_path.resolve()


def _pydub_fallback_mix(
    voice_path: Path,
    music_path: Path,
    output_path: Path,
    music_volume_db: float = -15.0,
) -> None:
    """Simple pydub fallback if ffmpeg sidechain fails."""
    try:
        logger.info("Using pydub fallback mixer...")
        voice = AudioSegment.from_wav(str(voice_path))
        music = AudioSegment.from_file(str(music_path))

        if voice.channels == 1:
            voice = voice.set_channels(2)
        if music.channels == 1:
            music = music.set_channels(2)

        voice = effects.normalize(voice)
        music = effects.normalize(music) + music_volume_db

        while len(music) < len(voice):
            music = music + music
        music = music[:len(voice) + 3000]

        mixed = music.overlay(voice, position=0)
        mixed = effects.normalize(mixed)
        mixed.export(str(output_path), format="wav")
        logger.info("✅ pydub fallback mix complete")

    except Exception as exc:
        logger.warning("pydub fallback also failed: %s — voice only", exc)
        shutil.copy(str(voice_path), str(output_path))
