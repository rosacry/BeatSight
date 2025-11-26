# =============================================================================
# BeatSight AI Pipeline Worker
# GPU-accelerated container for beatmap generation
# =============================================================================

# Use NVIDIA CUDA base image with Python support
FROM nvidia/cuda:12.2-cudnn9-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# =============================================================================
# System Dependencies
# =============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-venv \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    libsox-dev \
    sox \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

# =============================================================================
# Working Directory
# =============================================================================
WORKDIR /app

# =============================================================================
# Python Dependencies
# =============================================================================
# Copy requirements first for better Docker layer caching
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install additional worker dependencies
RUN pip install --no-cache-dir \
    redis>=5.0.0 \
    httpx>=0.27.0 \
    structlog>=24.1.0

# =============================================================================
# Application Code
# =============================================================================
COPY . .

# =============================================================================
# Pre-download Models
# =============================================================================
# Download Demucs models during build to avoid runtime delays
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')" || true

# =============================================================================
# Environment Variables
# =============================================================================
# API endpoint for job coordination
ENV BEATSIGHT_API_URL=http://backend:8000/api

# Worker identification
ENV WORKER_ID=""

# GPU settings
ENV CUDA_VISIBLE_DEVICES=0
ENV TORCH_CUDA_ARCH_LIST="8.0 8.6 8.9 9.0"

# Processing settings
ENV MAX_AUDIO_DURATION_SECONDS=600
ENV HEARTBEAT_INTERVAL_SECONDS=30

# Logging
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# =============================================================================
# Health Check
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" || exit 1

# =============================================================================
# Entry Point
# =============================================================================
CMD ["python", "-m", "pipeline.worker"]
