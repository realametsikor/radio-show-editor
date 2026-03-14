#!/usr/bin/env bash
# =============================================================================
# start.sh — Entrypoint for the Radio Show Editor Docker container
# =============================================================================
# Starts the FastAPI server and the Celery worker in a single container.
# Use this when running with `docker run` (standalone mode).
# When using docker-compose, each service overrides CMD with its own command.
# =============================================================================

set -e

echo "Starting Celery worker in the background..."
celery -A tasks worker --loglevel=info --concurrency=2 &

echo "Starting FastAPI server on port 8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
