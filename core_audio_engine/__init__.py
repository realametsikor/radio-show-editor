"""core_audio_engine — Radio Show Editor Core Audio Engine
=======================================================
Modular audio processing pipeline for AI-generated podcast post-production.
"""
from core_audio_engine.diarize import diarize_speakers
from core_audio_engine.sfx import apply_sfx, generate_intro, generate_outro
from core_audio_engine.mixer import mix_with_ducking
from core_audio_engine.engine import run_pipeline
from core_audio_engine.enhance import enhance_voice, master_audio
from core_audio_engine.music_fetch import fetch_music_for_mood

__all__ = [
    "diarize_speakers",
    "apply_sfx",
    "generate_intro",
    "generate_outro",
    "mix_with_ducking",
    "run_pipeline",
    "enhance_voice",
    "master_audio",
    "fetch_music_for_mood",
]
