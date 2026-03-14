"""
tasks.py — Celery Task Definitions for the Radio Show Editor API
================================================================
Configures a Celery application backed by Redis and defines the
long-running ``process_audio_task`` that wraps the Phase 2 pipeline.

Usage:
    Start a worker:
        celery -A tasks worker --loglevel=info

    Trigger from Python:
        from tasks import process_audio_task
        result = process_audio_task.delay("/path/to/uploaded.wav")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from celery import Celery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery Configuration
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "radio_show_editor",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="process_audio_task")
def process_audio_task(self, file_path: str) -> str:
    """Run the full Radio Show Editor pipeline on *file_path*.

    This task is meant to be dispatched asynchronously via ``.delay()``
    so the API can return a task ID immediately.

    Parameters
    ----------
    file_path : str
        Absolute path to the uploaded .wav file saved on disk.

    Returns
    -------
    str
        Absolute path to the final mixed ``radio_show_final.wav``.
    """
    from core_audio_engine.engine import run_pipeline

    self.update_state(state="PROCESSING", meta={"status": "Processing audio"})

    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Uploaded file not found: {file_path}")

    # Place output alongside the uploaded file so each job is isolated.
    output_dir = file_path.parent / "output"
    output_file = file_path.parent / "radio_show_final.wav"

    # The pipeline requires a background music file.  Default to a
    # bundled file or an environment-variable override.
    music_path = os.environ.get(
        "BACKGROUND_MUSIC_PATH",
        str(Path(__file__).resolve().parent / "assets" / "background_music.wav"),
    )

    logger.info("Starting pipeline for %s", file_path)

    try:
        final_path = run_pipeline(
            raw_audio=str(file_path),
            music_path=music_path,
            output_path=str(output_file),
            output_dir=str(output_dir),
            hf_token=os.environ.get("HF_AUTH_TOKEN"),
        )
    except Exception as exc:
        logger.exception("Pipeline failed for %s", file_path)
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise

    logger.info("Pipeline complete → %s", final_path)
    return str(final_path)
