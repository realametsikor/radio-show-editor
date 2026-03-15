"""engine.py — Full radio show production pipeline."""
from __future__ import annotations

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PIPELINE_CACHE: dict = {}
_WHISPER_CACHE:  dict = {}


def _get_pipeline(hf_token: str):
    if "p" not in _PIPELINE_CACHE:
        from pyannote.audio import Pipeline
        import torch
        logger.info("Loading pyannote pipeline...")
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
        logger.info("Loading Whisper '%s'...", size)
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
    from core_audio_engine.mixer    import mix_with_ducking, add_natural_pauses

    raw_audio   = Path(raw_audio)
    music_path  = Path(music_path)
    output_path = Path(output_path)
    output_dir  = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio_len_s = len(AudioSegment.from_file(str(raw_audio))) / 1000
    except Exception:
        audio_len_s = 120
    logger.info("Audio: %.0fs (%.1f mins)", audio_len_s, audio_len_s / 60)

    # Whisper model selection — skip for very long files
    if audio_len_s > 1800:       # 30+ mins
        whisper_size = None
        logger.info("Long audio — skipping transcription to save time")
    elif audio_len_s > 600:      # 10-30 mins
        whisper_size = "tiny"
    elif audio_len_s > 180:      # 3-10 mins
        whisper_size = "base"
    else:
        whisper_size = "small"

    # Pre-warm models
    if hf_token:
        try:
            _get_pipeline(hf_token)
        except Exception as exc:
            logger.warning("Pipeline pre-warm failed: %s", exc)
    if whisper_size:
        try:
            _get_whisper(whisper_size)
        except Exception as exc:
            logger.warning("Whisper pre-warm failed: %s", exc)

    # ── Step 1: Diarize ────────────────────────────────────────────────
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
        logger.info("Long file — skipping enhancement")
        shutil.copy(str(host_a), str(ha_enh))
        shutil.copy(str(host_b), str(hb_enh))
    else:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(enhance_voice, host_a, ha_enh)
            fb = ex.submit(enhance_voice, host_b, hb_enh)
            try:
                fa.result(timeout=180)
                fb.result(timeout=180)
                logger.info("✅ Both voices enhanced")
            except Exception as exc:
                logger.warning("Enhancement failed: %s", exc)
                shutil.copy(str(host_a), str(ha_enh))
                shutil.copy(str(host_b), str(hb_enh))

    # ── Step 3: Combine speakers ───────────────────────────────────────
    logger.info("STEP 3/7 — Combining speakers")
    combined_path = output_dir / "combined.wav"
    try:
        a = AudioSegment.from_wav(str(ha_enh))
        b = AudioSegment.from_wav(str(hb_enh))
        a = effects.normalize(a) - 3
        b = effects.normalize(b) - 3
        combined = a.overlay(b)
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
        logger.info(
            "✅ Combined: %.1fs dBFS=%.1f",
            len(combined) / 1000,
            combined.dBFS,
        )
    except Exception as exc:
        logger.warning("Combine failed: %s", exc)
        shutil.copy(str(ha_enh), str(combined_path))

    # ── Step 4: Natural pauses ─────────────────────────────────────────
    logger.info("STEP 4/7 — Adding natural pauses")
    paused_path = output_dir / "combined_paused.wav"
    try:
        combined_audio = AudioSegment.from_wav(str(combined_path))
        paused_audio   = add_natural_pauses(combined_audio)
        paused_audio.export(str(paused_path), format="wav")
        voice_source = paused_path
        logger.info("✅ Pauses added")
    except Exception as exc:
        logger.warning("Pause injection failed: %s", exc)
        voice_source = combined_path

    # ── Step 5: Transcribe + Claude production ─────────────────────────
    logger.info("STEP 5/7 — Claude AI analysis")
    words      = []
    transcript = ""

    if whisper_size:
        try:
            model  = _get_whisper(whisper_size)
            result = model.transcribe(
                str(voice_source),
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
            logger.info("✅ Transcribed %d words", len(words))
        except Exception as exc:
            logger.warning("Transcription failed: %s", exc)

    audio_duration = len(AudioSegment.from_wav(str(voice_source))) / 1000.0

    production_plan = analyze_with_claude(
        transcript=transcript,
        words=words,
        audio_duration=audio_duration,
        available_sfx=[
            "applause", "laugh", "dramatic", "cash", "shock",
            "success", "fail", "transition", "crowd_wow",
            "rimshot", "news_sting",
        ],
        mood=mood,
    )
    logger.info(
        "✅ Plan: '%s' — %d SFX",
        production_plan.get("show_title", ""),
        len(production_plan.get("sfx_cues", [])),
    )

    # ── Step 6: Apply SFX ─────────────────────────────────────────────
    logger.info("STEP 6/7 — Applying SFX")
    sfx_path = output_dir / "voice_with_sfx.wav"
    try:
        apply_sfx(
            audio_path=voice_source,
            output_path=sfx_path,
            sfx_cues=production_plan.get("sfx_cues", []),
        )
        voice_to_mix = sfx_path
        logger.info("✅ SFX applied")
    except Exception as exc:
        logger.warning("SFX failed: %s", exc)
        voice_to_mix = voice_source

    # ── Step 7: Mix with music ─────────────────────────────────────────
    logger.info("STEP 7/7 — Professional mixing")
    mixed_path = output_dir / "mixed.wav"
    mix_with_ducking(
        voice_path=voice_to_mix,
        music_path=music_path,
        output_path=mixed_path,
        music_curve=production_plan.get("music_curve"),
    )
    logger.info("✅ Mix complete")

    # ── Step 8: Intro + Outro + Master ────────────────────────────────
    logger.info("STEP 8 — Intro, outro, mastering")
    pre_master = output_dir / "pre_master.wav"
    try:
        mixed = AudioSegment.from_wav(str(mixed_path))
        intro = generate_intro(duration_ms=3000, mood=mood)
        outro = generate_outro(duration_ms=2500, mood=mood)
        gap   = AudioSegment.silent(duration=300)

        for seg in [intro, mixed, outro]:
            pass  # type check

        if intro.channels == 1:
            intro = intro.set_channels(2)
        if mixed.channels == 1:
            mixed = mixed.set_channels(2)
        if outro.channels == 1:
            outro = outro.set_channels(2)

        full = intro + gap + mixed + gap + outro
        full.export(str(pre_master), format="wav")
        logger.info("✅ Full show: %.1f mins", len(full) / 60000)
    except Exception as exc:
        logger.warning("Intro/outro failed: %s", exc)
        shutil.copy(str(mixed_path), str(pre_master))

    master_audio(pre_master, output_path)

    try:
        final = AudioSegment.from_wav(str(output_path))
        logger.info(
            "🎙️ DONE: %.1f mins | dBFS=%.1f | max=%.1f",
            len(final) / 60000,
            final.dBFS,
            final.max_dBFS,
        )
    except Exception:
        logger.info("🎙️ Done → %s", output_path)

    return output_path.resolve()
