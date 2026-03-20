"""engine.py — Full radio show production pipeline."""
from __future__ import annotations

import logging
import shutil
import random
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
    from core_audio_engine.sfx      import apply_sfx
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

    # ── Step 1: Diarize (DYNAMIC SPEAKER COUNT) ───────────────────────
    logger.info("STEP 1/7 — Diarizing speakers (Dynamic Count)")
    diarize_result = diarize_speakers(
        audio_path=raw_audio,
        output_dir=output_dir,
        hf_token=hf_token,
    )
    
    if isinstance(diarize_result, (tuple, list)):
        raw_speakers = list(diarize_result)
    else:
        raw_speakers = [diarize_result]
        
    logger.info(f"✅ Diarizer returned {len(raw_speakers)} track(s).")

    # ── Step 2: Enhance voices in parallel ────────────────────────────
    logger.info("STEP 2/7 — Enhancing voices")
    enhanced_speakers = []
    
    if audio_len_s > 1200:
        logger.info("Long file — skipping enhancement")
        enhanced_speakers = raw_speakers
    else:
        with ThreadPoolExecutor(max_workers=max(1, len(raw_speakers))) as ex:
            futures = []
            for i, spk_path in enumerate(raw_speakers):
                enh_path = output_dir / f"host_{i}_enhanced.wav"
                futures.append((enh_path, ex.submit(enhance_voice, spk_path, enh_path)))
            
            for enh_path, f in futures:
                try:
                    f.result(timeout=180)
                    enhanced_speakers.append(enh_path)
                except Exception as exc:
                    logger.warning(f"Enhancement failed for {enh_path}: {exc}")
                    enhanced_speakers.append(raw_speakers[len(enhanced_speakers)])

    # ── Step 3: Combine speakers (SMART SPATIAL PANNING) ──────────────
    logger.info("STEP 3/7 — Combining speakers (Smart Spatial Panning)")
    combined_path = output_dir / "combined.wav"
    try:
        valid_audio_tracks = []
        
        for spk_path in enhanced_speakers:
            try:
                track = AudioSegment.from_wav(str(spk_path))
                if len(track) > 100 and track.max_dBFS > -75.0: 
                    if track.channels == 1:
                        track = track.set_channels(2)
                    valid_audio_tracks.append(track)
            except Exception:
                pass
                
        # THE ULTIMATE INDESTRUCTIBLE FAILSAFE
        if len(valid_audio_tracks) == 0:
            logger.warning("Failsafe triggered! Engine lost the voices. Restoring original audio.")
            fallback = AudioSegment.from_wav(str(raw_audio))
            if fallback.channels == 1: 
                fallback = fallback.set_channels(2)
            valid_audio_tracks.append(fallback)
        
        num_speakers = len(valid_audio_tracks)
        logger.info(f"✅ Detected {num_speakers} active speaker(s) for final mix.")
        
        combined = None
        
        for i, track in enumerate(valid_audio_tracks):
            if num_speakers == 1:
                pan_val = 0.0 
            elif num_speakers == 2:
                pan_val = -0.30 if i == 0 else 0.30 
            elif num_speakers == 3:
                pan_val = [-0.30, 0.0, 0.30][i] 
            else:
                pan_val = random.choice([-0.25, 0.25, -0.15, 0.15, 0])
                
            track = track.pan(pan_val)
            track = effects.normalize(track) - 3
            
            if combined is None:
                combined = track
            else:
                combined = combined.overlay(track)
                
        if combined is None:
            combined = AudioSegment.silent(duration=60000)
            
        combined = effects.normalize(combined)
        combined.export(str(combined_path), format="wav")
        logger.info(f"✅ Combined (Smart Stereo): {len(combined)/1000:.1f}s dBFS={combined.dBFS:.1f}")
        
    except Exception as exc:
        logger.exception("Combine failed: %s", exc)
        shutil.copy(str(raw_audio), str(combined_path))

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

    # ── Step 8: Finalizing Mix ────────────────────────────────────────
    # Removed the legacy generate_intro/generate_outro calls to prevent 
    # clashing with the cinematic Sidechain Swell generated in main.py.
    logger.info("STEP 8/8 — Final safety limiter")
    master_audio(mixed_path, output_path)

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

    return output_path
