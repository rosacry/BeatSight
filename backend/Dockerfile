# BeatSight Backend Dockerfile
# Multi-stage build for production deployment

# =============================================================================
# Build Stage
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files (README.md is required by pyproject.toml)
COPY pyproject.toml README.md ./

# Copy application source code (required for package building)
COPY app/ ./app/

# Install dependencies using pip
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# =============================================================================
# Production Stage
# =============================================================================
FROM python:3.12-slim AS production

LABEL maintainer="BeatSight Team" \
    version="1.0.0" \
    description="BeatSight API Backend"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    # Default to production settings
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    LOGGING_JSON=true

# Health check (Railway handles this via railway.toml)
# For local Docker, we use the /health/live endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health/live || exit 1

# Expose API port (Railway dynamically assigns via $PORT)
EXPOSE ${PORT:-8000}

# Default port (Railway overrides with $PORT via startCommand)
ENV PORT=8000

# Run with uvicorn (production settings)
# Note: Railway overrides CMD with startCommand in railway.toml
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1

# =============================================================================
# Development Stage (optional, for local development)
# =============================================================================
FROM production AS development

USER root

# Install dev dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    httpx

USER appuser

# Override CMD for development (single worker, reload enabled)
CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--reload"]
