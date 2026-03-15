def add_natural_pauses(audio: AudioSegment) -> AudioSegment:
    """
    Bypassed for NotebookLM: 
    Google's AI already has perfect pacing, breathing, and interruptions. 
    Adding artificial pauses will only ruin the natural flow.
    """
    logger.info("Skipping artificial pauses — optimized for NotebookLM.")
    return audio


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
    music_volume_db: float = -15.0,  # Raised for a true "Radio Show" energy bed
    duck_ratio: float      = 8.0,    # Smoother ducking (was 12.0)
    attack_ms: int         = 80,     # Slightly faster duck to catch them speaking
    release_ms: int        = 800,    # Faster recovery so music swells nicely during pauses
    voice_boost_db: float  = 0.0,    # NotebookLM is already perfectly leveled, no boost needed
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

    # Prepare music
    logger.info("Preparing music...")
    try:
        music = AudioSegment.from_file(str(music_path))
        if music.channels == 1:
            music = music.set_channels(2)
        if music.frame_rate != 44100:
            music = music.set_frame_rate(44100)

        voice_duration_ms = len(AudioSegment.from_wav(str(voice_path)))
        music = _loop_music(music, voice_duration_ms + 12000)
        music = music.fade_in(2000).fade_out(5000)

        tmp_music = output_path.parent / "_tmp_music_prepared.wav"
        music.export(str(tmp_music), format="wav")
    except Exception as exc:
        logger.warning("Music preparation failed: %s — voice only", exc)
        shutil.copy(str(voice_path), str(output_path))
        return output_path.resolve()

    # Build ffmpeg filter chain tailored for NotebookLM:
    # 1. Music: stereo → volume setting → warm EQ
    # 2. Voice: stereo → clean rumble (no harsh EQ) → gentle compression
    # 3. Sidechain: smooth, musical ducking
    # 4. Mix: Balanced 1 to 4 ratio
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
        "-i", str(voice_path),
        "-filter_complex", filter_str,
        "-map", "[out]",
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        "-ac", "2",
        str(output_path),
    ]

    logger.info("Running ffmpeg sidechain mix...")
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=1800)
        if result.returncode == 0:
            logger.info("✅ NotebookLM Mix complete!")
        else:
            error = result.stderr.decode()
            raise RuntimeError("ffmpeg mix failed: " + error[-200:])

    except Exception as exc:
        logger.warning("ffmpeg mix failed (%s) — pydub fallback", exc)
        _pydub_fallback_mix(
            voice_path=voice_path,
            music_path=tmp_music,
            output_path=output_path,
            music_volume_db=music_volume_db,
        )
    finally:
        try:
            tmp_music.unlink()
        except Exception:
            pass

    return output_path.resolve()
