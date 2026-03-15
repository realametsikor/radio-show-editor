# =============================================================================
# Dockerfile — Radio Show Editor Backend 
# =============================================================================
# Optimized for dynamic cloud deployment (Railway, RunPod, etc.)
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
COPY main.py ./
COPY core_audio_engine/ ./core_audio_engine/

# Copy assets if they exist (background music, SFX files, etc.)
COPY assets/ ./assets/

# ── Create uploads directory & non-root user ────────────────────────────────
RUN useradd -m -u 1000 user && \
    mkdir -p /app/uploads && \
    chown -R user:user /app

USER user

# ── Health check ────────────────────────────────────────────────────────────
# Uses the dynamic port so the health check doesn't fail on Railway
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# ── Dynamic Port Configuration ──────────────────────────────────────────────
# We set a default of 8000 for local testing, but Railway will override this.
ENV PORT=8000
EXPOSE $PORT

# ── Start Uvicorn ──────────────────────────────────────────────────────────
# This command dynamically binds to whatever port Railway assigns!
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
