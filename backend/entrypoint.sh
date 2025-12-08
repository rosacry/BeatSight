#!/bin/sh
# Entrypoint script for BeatSight backend
set -e

# Default port if not set
PORT="${PORT:-8000}"

echo "Starting uvicorn on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 1
