# =============================================================================
# Dockerfile — Radio Show Editor Backend (Hugging Face Docker Space)
# =============================================================================
# Optimized for Hugging Face Spaces which provides 16 GB RAM on the free tier.
# HF Spaces require port 7860 and a non-root user.
#
# Build:   docker build -t radio-show-backend .
# Run:     docker run -p 7860:7860 --env-file .env radio-show-backend
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

# ── Create uploads directory & non-root user (required by HF Spaces) ───────
RUN useradd -m -u 1000 user && \
    mkdir -p /app/uploads && \
    chown -R user:user /app

USER user

# ── Health check ────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# ── Hugging Face Spaces requires port 7860 ─────────────────────────────────
EXPOSE 7860

# ── Start Uvicorn on port 7860 ──────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
