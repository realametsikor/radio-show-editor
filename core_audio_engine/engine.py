from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def run_pipeline(
    raw_audio: str | Path,
    music_path: str | Path,
    output_path: str | Path = "radio_show_final.wav",
    output_dir: str | Path = "output",
    *,
    hf_token: Optional[str] = None,
    mood: str = "",
) -> Path:
    import whisper
    from pydub import AudioSegment, effects

    from core_audio_engine.diarize import diarize_speakers
    from core_audio_engine.enhance import enhance_voice, master_audio
    from core_audio_engine.producer import analyze_with_claude
    from core_audio_engine.sfx import apply_sfx, generate_intro, generate_outro
    from core_audio_engine.mixer import mix_with_ducking

    raw_audio = Path(raw_audio)
    music_path = Path(music_path)
    output_path = Path(output_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Diarize ────────────────────────────────────────────────
    logger.info("Step 1/7 — Diarizing speakers …")
    host_a, host_b = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )
    logger.info("Diarization complete: %s, %s", host_a, host_b)

    # ── Step 2: Enhance each speaker's voice ───────────────────────────
    logger.info("Step 2/7 — Enhancing voice quality …")
    host_a_enhanced = output_dir / "host_A_enhanced.wav"
    host_b_enhanced = output_dir / "host_B_enhanced.wav"
    enhance_voice(host_a, host_a_enhanced)
    enhance_voice(host_b, host_b_enhanced)

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
    logger.info("Step 4/7 — Claude AI production analysis …")
    words = []
    transcript = ""
    try:
        model = whisper.load_model("small")
        result = model.transcribe(
            str(combined_path),
            word_timestamps=True,
            language="en"
        )
        transcript = result.get("text", "")
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", "").strip(),
                    "start": w.get("start", 0),
                    "end": w.get("end", 0),
                })
        logger.info("Transcribed %d words", len(words))
        logger.info("Transcript preview: %s", transcript[:200])
    except Exception as exc:
        logger.warning("Transcription failed: %s", exc)

    available_sfx = [
        "applause", "laugh", "dramatic", "cash", "shock",
        "success", "fail", "transition", "crowd_wow", "rimshot"
    ]

    audio_duration = len(AudioSegment.from_wav(str(combined_path))) / 1000.0

    production_plan = analyze_with_claude(
        transcript=transcript,
        words=words,
        audio_duration=audio_duration,
        available_sfx=available_sfx,
        mood=mood,
    )

    logger.info("Show title: %s", production_plan.get("show_title", "Radio Show"))
    logger.info("Tagline: %s", production_plan.get("show_tagline", ""))
    logger.info("Summary: %s", production_plan.get("show_summary", ""))

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
        logger.info("SFX applied successfully")
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
    logger.info("Mixing complete")

    # ── Step 7: Intro + Outro + Master ────────────────────────────────
    logger.info("Step 7/7 — Adding intro/outro and mastering …")
    pre_master_path = output_dir / "pre_master.wav"
    try:
        mixed = AudioSegment.from_wav(str(mixed_path))
        intro = generate_intro(duration_ms=3500)
        outro = generate_outro(duration_ms=3000)
        gap = AudioSegment.silent(duration=600)
        full = intro + gap + mixed + gap + outro
        full.export(str(pre_master_path), format="wav")
        logger.info(
            "Added intro/outro → total duration: %.1fs",
            len(full) / 1000
        )
    except Exception as exc:
        logger.warning("Intro/outro failed: %s", exc)
        shutil.copy(str(mixed_path), str(pre_master_path))

    # Master to broadcast standard
    master_audio(pre_master_path, output_path)
    logger.info("🎙️ Pipeline complete → %s", output_path)

    return output_path.resolve()
