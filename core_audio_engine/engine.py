"""engine.py — Full radio show production pipeline.

Steps:
1. Diarize — separate speakers
2. Enhance — EQ + compress each voice
3. Combine — merge speakers with individual normalization
4. Transcribe + Claude — AI production plan
5. SFX — apply AI-directed sound effects
6. Mix — professional ducking mixer
7. Intro/Outro + Master — broadcast-ready output
"""
from __future__ import annotations

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Model cache ────────────────────────────────────────────────────────────
_PIPELINE_CACHE: dict = {}
_WHISPER_CACHE:  dict = {}


def _get_pipeline(hf_token: str):
    if "p" not in _PIPELINE_CACHE:
        from pyannote.audio import Pipeline
        import torch
        logger.info("Loading pyannote pipeline (first time)...")
        p = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )
        p.to(torch.device("cpu"))
        _PIPELINE_CACHE["p"] = p
        logger.info("Pyannote cached ✅")
    return _PIPELINE_CACHE["p"]


def _get_whisper(size: str):
    if size not in _WHISPER_CACHE:
        import whisper
        logger.info("Loading Whisper '%s' (first time)...", size)
        _WHISPER_CACHE[size] = whisper.load_model(size)
        logger.info("Whisper '%s' cached ✅", size)
    return _WHISPER_CACHE[size]


def run_pipeline(
    raw_audio: str | Path,
    music_path: str | Path,
    output_path: str | Path = "radio_show_final.wav",
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
    mood: str = "",
) -> Path:
    from pydub import AudioSegment, effects

    from core_audio_engine.diarize  import diarize_speakers
    from core_audio_engine.enhance  import enhance_voice, master_audio
    from core_audio_engine.producer import analyze_with_claude
    from core_audio_engine.sfx      import apply_sfx, generate_intro, generate_outro
    from core_audio_engine.mixer    import mix_with_ducking

    raw_audio   = Path(raw_audio)
    music_path  = Path(music_path)
    output_path = Path(output_path)
    output_dir  = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get audio length for smart decisions
    try:
        audio_len_s = len(AudioSegment.from_file(str(raw_audio))) / 1000
    except Exception:
        audio_len_s = 120  # assume 2 mins
    logger.info("Audio length: %.0fs (%.1f mins)", audio_len_s, audio_len_s / 60)

    # Smart Whisper model selection
    # tiny = fast but less accurate
    # base = good balance
    # small = best accuracy but slower
    if audio_len_s > 1200:    # 20+ mins → speed priority
        whisper_size = "tiny"
    elif audio_len_s > 300:   # 5-20 mins → balance
        whisper_size = "base"
    else:                      # < 5 mins → accuracy
        whisper_size = "small"
    logger.info("Whisper model: '%s'", whisper_size)

    # Pre-warm models in background
    if hf_token:
        try:
            _get_pipeline(hf_token)
        except Exception as exc:
            logger.warning("Pipeline pre-warm failed: %s", exc)
    try:
        _get_whisper(whisper_size)
    except Exception as exc:
        logger.warning("Whisper pre-warm failed: %s", exc)

    # ── Step 1: Diarize speakers ───────────────────────────────────────
    logger.info("=" * 50)
    logger.info("STEP 1/7 — Diarizing speakers")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )
    logger.info("✅ Diarized: A=%s B=%s", host_a.name, host_b.name)

    # ── Step 2: Enhance voices in parallel ────────────────────────────
    logger.info("STEP 2/7 — Enhancing voices")
    ha_enh = output_dir / "host_A_enhanced.wav"
    hb_enh = output_dir / "host_B_enhanced.wav"

    if audio_len_s > 1200:
        # Skip for very long files — saves time
        logger.info("Long file — skipping voice enhancement")
        shutil.copy(str(host_a), str(ha_enh))
        shutil.copy(str(host_b), str(hb_enh))
    else:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(enhance_voice, host_a, ha_enh)
            fb = ex.submit(enhance_voice, host_b, hb_enh)
            try:
                fa.result(timeout=180)
                fb.result(timeout=180)
                logger.info("✅ Both voices enhanced in parallel")
            except Exception as exc:
                logger.warning("Enhancement failed: %s", exc)
                shutil.copy(str(host_a), str(ha_enh))
                shutil.copy(str(host_b), str(hb_enh))

    # ── Step 3: Combine both speakers ─────────────────────────────────
    logger.info("STEP 3/7 — Combining speakers")
    combined_path = output_dir / "combined.wav"
    try:
        a = AudioSegment.from_wav(str(ha_enh))
        b = AudioSegment.from_wav(str(hb_enh))

        # Normalize each speaker INDIVIDUALLY first
        # This ensures both speakers are at equal loudness
        a = effects.normalize(a)
        b = effects.normalize(b)

        # Reduce each by 4.5dB before combining to ensure headroom
        # (two normalized signals overlaid can peak at +6dB)
        a = a - 4.5
        b = b - 4.5

        combined = a.overlay(b)
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
        logger.info(
            "✅ Combined: %.1fs dBFS=%.1f",
            len(combined)/1000,
            combined.dBFS,
        )
    except Exception as exc:
        logger.warning("Combine failed: %s", exc)
        shutil.copy(str(ha_enh), str(combined_path))

    # ── Step 4: Transcribe + Claude production plan ────────────────────
    logger.info("STEP 4/7 — Transcribing + Claude AI analysis")
    words      = []
    transcript = ""
    try:
        model  = _get_whisper(whisper_size)
        result = model.transcribe(
            str(combined_path),
            word_timestamps=True,
            language="en",
            fp16=False,
            condition_on_previous_text=False,
            temperature=0,
            best_of=1,
            beam_size=1,
        )
        transcript = result.get("text", "")
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word":  w.get("word", "").strip(),
                    "start": w.get("start", 0),
                    "end":   w.get("end", 0),
                })
        logger.info(
            "✅ Transcribed %d words — preview: %s...",
            len(words),
            transcript[:80],
        )
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)

    available_sfx = [
        "applause", "laugh", "dramatic", "cash", "shock",
        "success", "fail", "transition", "crowd_wow",
        "rimshot", "news_sting",
    ]

    audio_duration = len(AudioSegment.from_wav(str(combined_path))) / 1000.0

    production_plan = analyze_with_claude(
        transcript=transcript,
        words=words,
        audio_duration=audio_duration,
        available_sfx=available_sfx,
        mood=mood,
    )
    logger.info(
        "✅ Production plan: '%s' — %d SFX | %d segments | %d highlights",
        production_plan.get("show_title", ""),
        len(production_plan.get("sfx_cues", [])),
        len(production_plan.get("segments", [])),
        len(production_plan.get("highlights", [])),
    )

    # ── Step 5: Apply SFX ─────────────────────────────────────────────
    logger.info("STEP 5/7 — Applying SFX")
    sfx_path = output_dir / "combined_sfx.wav"
    try:
        apply_sfx(
            audio_path=combined_path,
            output_path=sfx_path,
            sfx_cues=production_plan.get("sfx_cues", []),
        )
        voice_to_mix = sfx_path
        logger.info("✅ SFX applied")
    except Exception as exc:
        logger.warning("SFX failed: %s", exc)
        voice_to_mix = combined_path

    # ── Step 6: Mix voice with music ───────────────────────────────────
    logger.info("STEP 6/7 — Professional mixing")
    mixed_path = output_dir / "mixed.wav"
    mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=mixed_path,
        music_curve=production_plan.get("music_curve"),
    )
    logger.info("✅ Mix complete")

    # ── Step 7: Intro + Outro + Master ────────────────────────────────
    logger.info("STEP 7/7 — Intro, outro, mastering")
    pre_master = output_dir / "pre_master.wav"
    try:
        mixed = AudioSegment.from_wav(str(mixed_path))
        intro = generate_intro(duration_ms=4000, mood=mood)
        outro = generate_outro(duration_ms=3500, mood=mood)

        # Ensure all parts are stereo and same sample rate
        if intro.channels == 1:
            intro = intro.set_channels(2)
        if intro.frame_rate != 44100:
            intro = intro.set_frame_rate(44100)
        if mixed.channels == 1:
            mixed = mixed.set_channels(2)
        if mixed.frame_rate != 44100:
            mixed = mixed.set_frame_rate(44100)
        if outro.channels == 1:
            outro = outro.set_channels(2)
        if outro.frame_rate != 44100:
            outro = outro.set_frame_rate(44100)

        # Crossfade intro into main content for smooth transition
        # and crossfade main content into outro
        xfade_in = min(800, len(intro) // 3, len(mixed) // 10)
        xfade_out = min(1000, len(outro) // 3, len(mixed) // 10)

        full = intro.append(mixed, crossfade=xfade_in)
        full = full.append(outro, crossfade=xfade_out)

        full.export(str(pre_master), format="wav")
        logger.info(
            "✅ Full show assembled: %.1f mins (xfade in=%dms out=%dms)",
            len(full) / 60000,
            xfade_in,
            xfade_out,
        )
    except Exception as exc:
        logger.warning("Intro/outro failed: %s", exc)
        shutil.copy(str(mixed_path), str(pre_master))

    # Master to broadcast standard
    master_audio(pre_master, output_path)

    # Log final stats
    try:
        final = AudioSegment.from_wav(str(output_path))
        logger.info(
            "🎙️ DONE: %.1f mins | dBFS=%.1f | max=%.1f → %s",
            len(final)/60000,
            final.dBFS,
            final.max_dBFS,
            output_path.name,
        )
    except Exception:
        logger.info("🎙️ Pipeline complete → %s", output_path)

    return output_path.resolve()