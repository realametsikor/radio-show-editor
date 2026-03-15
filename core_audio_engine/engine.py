from __future__ import annotations

import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model cache — keeps pyannote + whisper in memory between requests
# ---------------------------------------------------------------------------
_PIPELINE_CACHE: dict = {}
_WHISPER_CACHE: dict = {}


def _get_diarization_pipeline(hf_token: str):
    """Load and cache the pyannote pipeline."""
    if "pipeline" not in _PIPELINE_CACHE:
        from pyannote.audio import Pipeline
        logger.info("Loading pyannote pipeline (first time — caching)...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )
        _PIPELINE_CACHE["pipeline"] = pipeline
        logger.info("Pyannote pipeline cached ✅")
    else:
        logger.info("Using cached pyannote pipeline ✅")
    return _PIPELINE_CACHE["pipeline"]


def _get_whisper_model(model_size: str = "base"):
    """Load and cache the Whisper model."""
    if model_size not in _WHISPER_CACHE:
        import whisper
        logger.info("Loading Whisper '%s' model (first time — caching)...", model_size)
        model = whisper.load_model(model_size)
        _WHISPER_CACHE[model_size] = model
        logger.info("Whisper '%s' model cached ✅", model_size)
    else:
        logger.info("Using cached Whisper '%s' model ✅", model_size)
    return _WHISPER_CACHE[model_size]


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

    from core_audio_engine.diarize import diarize_speakers
    from core_audio_engine.enhance import enhance_voice, master_audio
    from core_audio_engine.producer import analyze_with_claude
    from core_audio_engine.sfx import apply_sfx, generate_intro, generate_outro
    from core_audio_engine.mixer import mix_with_ducking

    raw_audio   = Path(raw_audio)
    music_path  = Path(music_path)
    output_path = Path(output_path)
    output_dir  = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-warm models before pipeline starts
    logger.info("Pre-warming models...")
    if hf_token:
        try:
            _get_diarization_pipeline(hf_token)
        except Exception as exc:
            logger.warning("Could not pre-warm diarization pipeline: %s", exc)

    # Decide whisper model size based on audio length
    try:
        audio_len_s = len(AudioSegment.from_wav(str(raw_audio))) / 1000
    except Exception:
        audio_len_s = 0

    # Use tiny for long files to save time, small for short files
    whisper_model_size = "tiny" if audio_len_s > 600 else "base"
    logger.info(
        "Audio length: %.0fs — using Whisper '%s'",
        audio_len_s, whisper_model_size
    )

    try:
        _get_whisper_model(whisper_model_size)
    except Exception as exc:
        logger.warning("Could not pre-warm Whisper: %s", exc)

    # ── Step 1: Diarize ────────────────────────────────────────────────
    logger.info("Step 1/7 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )
    logger.info("Diarization complete: %s, %s", host_a, host_b)

    # ── Step 2: Enhance speakers in parallel ───────────────────────────
    logger.info("Step 2/7 — Enhancing voices in parallel …")
    host_a_enhanced = output_dir / "host_A_enhanced.wav"
    host_b_enhanced = output_dir / "host_B_enhanced.wav"

    # Skip enhancement for very long files to save time
    if audio_len_s > 1200:  # 20+ mins
        logger.info("Long file detected — skipping enhancement to save time")
        shutil.copy(str(host_a), str(host_a_enhanced))
        shutil.copy(str(host_b), str(host_b_enhanced))
    else:
        # Run both enhancements in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(enhance_voice, host_a, host_a_enhanced)
            future_b = executor.submit(enhance_voice, host_b, host_b_enhanced)
            try:
                future_a.result()
                future_b.result()
                logger.info("Both speakers enhanced in parallel ✅")
            except Exception as exc:
                logger.warning("Parallel enhancement failed: %s", exc)
                shutil.copy(str(host_a), str(host_a_enhanced))
                shutil.copy(str(host_b), str(host_b_enhanced))

    # ── Step 3: Combine both speakers ──────────────────────────────────
    logger.info("Step 3/7 — Combining speaker tracks …")
    combined_path = output_dir / "combined_voices.wav"
    try:
        audio_a = AudioSegment.from_wav(str(host_a_enhanced))
        audio_b = AudioSegment.from_wav(str(host_b_enhanced))
        combined = audio_a.overlay(audio_b)
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
        logger.info("Combined both speakers → %s", combined_path)
    except Exception as exc:
        logger.warning("Combine failed: %s", exc)
        shutil.copy(str(host_a_enhanced), str(combined_path))

    # ── Step 4: Transcribe + Claude production plan ─────────────────────
    logger.info("Step 4/7 — Transcribing + Claude AI production analysis …")
    words = []
    transcript = ""
    try:
        model = _get_whisper_model(whisper_model_size)
        result = model.transcribe(
            str(combined_path),
            word_timestamps=True,
            language="en",
            # Speed optimizations
            fp16=False,
            condition_on_previous_text=False,
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
            "Transcribed %d words — preview: %s",
            len(words), transcript[:150]
        )
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)

    available_sfx = [
        "applause", "laugh", "dramatic", "cash", "shock",
        "success", "fail", "transition", "crowd_wow", "rimshot",
    ]

    audio_duration = len(AudioSegment.from_wav(str(combined_path))) / 1000.0

    production_plan = analyze_with_claude(
        transcript=transcript,
        words=words,
        audio_duration=audio_duration,
        available_sfx=available_sfx,
        mood=mood,
    )

    logger.info("Show: %s — %s",
                production_plan.get("show_title"),
                production_plan.get("show_tagline"))

    # ── Step 5: Apply SFX ──────────────────────────────────────────────
    logger.info("Step 5/7 — Applying AI-directed sound effects …")
    combined_sfx_path = output_dir / "combined_with_sfx.wav"
    try:
        apply_sfx(
            audio_path=combined_path,
            output_path=combined_sfx_path,
            sfx_cues=production_plan.get("sfx_cues", []),
        )
        voice_to_mix = combined_sfx_path
        logger.info("SFX applied ✅")
    except Exception as exc:
        logger.warning("SFX failed: %s", exc)
        voice_to_mix = combined_path

    # ── Step 6: Mix with music ─────────────────────────────────────────
    logger.info("Step 6/7 — Professional audio mixing …")
    mixed_path = output_dir / "mixed.wav"
    mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=mixed_path,
        music_curve=production_plan.get("music_curve"),
    )
    logger.info("Mixing complete ✅")

    # ── Step 7: Intro + Outro + Master ────────────────────────────────
    logger.info("Step 7/7 — Adding intro/outro and mastering …")
    pre_master_path = output_dir / "pre_master.wav"
    try:
        mixed    = AudioSegment.from_wav(str(mixed_path))
        intro    = generate_intro(duration_ms=3500)
        outro    = generate_outro(duration_ms=3000)
        gap      = AudioSegment.silent(duration=600)
        full     = intro + gap + mixed + gap + outro
        full.export(str(pre_master_path), format="wav")
        logger.info(
            "Intro/outro added → total: %.1fs",
            len(full) / 1000
        )
    except Exception as exc:
        logger.warning("Intro/outro failed: %s", exc)
        shutil.copy(str(mixed_path), str(pre_master_path))

    master_audio(pre_master_path, output_path)
    logger.info("🎙️ Pipeline complete → %s", output_path)

    return output_path.resolve()
