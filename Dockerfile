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

# ── Python dependencies (OPTIMIZED FOR SPEED) ───────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip 

# Force the tiny CPU-only version of PyTorch first to save 3GB of downloading!
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Then install the rest of your app
RUN pip install --no-cache-dir -r requirements.txt

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
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# ── Hugging Face Port Configuration ─────────────────────────────────────────
ENV PORT=7860
EXPOSE 7860

# ── Start Uvicorn ──────────────────────────────────────────────────────────
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 7860"]
