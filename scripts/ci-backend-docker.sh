#!/bin/bash
# Backend Docker Build - mirrors GitHub Actions backend.yml docker job EXACTLY
set -e

echo "=== Backend Docker Build ==="
cd "$(dirname "$0")/../backend"

echo "Building Docker image (docker build -t beatsight-backend:test .)..."
docker build -t beatsight-backend:test .

echo ""
echo "--- Verifying image ---"
docker run --rm beatsight-backend:test python -c "from app.main import app; print('✅ App imports successfully')"

echo ""
echo "✅ Docker build passed!"
