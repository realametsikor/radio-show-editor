# =============================================================================
# Dockerfile — Radio Show Editor Backend (FastAPI + Celery)
# =============================================================================
# Build:   docker build -t radio-show-backend .
# Run:     docker run -p 8000:8000 --env-file .env radio-show-backend
# =============================================================================

FROM python:3.11-slim

# ── System dependencies ─────────────────────────────────────────────────────
# ffmpeg is required by both ffmpeg-python and pydub for audio processing.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ─────────────────────────────────────────────────────
# Install requirements first to leverage Docker layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────────────────
COPY main.py tasks.py start.sh ./
COPY core_audio_engine/ ./core_audio_engine/

# Copy assets if they exist (background music, SFX files, etc.)
COPY assets/ ./assets/

# ── Prepare entrypoint ──────────────────────────────────────────────────────
RUN chmod +x start.sh

# ── Create uploads directory & non-root user ────────────────────────────────
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser && \
    mkdir -p /app/uploads && \
    chown -R appuser:appuser /app

USER appuser

# ── Health check ────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Expose API port ─────────────────────────────────────────────────────────
EXPOSE 8000

# ── Default entrypoint ──────────────────────────────────────────────────────
CMD ["./start.sh"]
