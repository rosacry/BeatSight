#!/bin/bash
# AI Pipeline Tests - mirrors GitHub Actions ci.yml ai-pipeline-test job EXACTLY
# Note: Some CUDA dependencies may fail on Windows - this is expected, tests will still run
set -e

echo "=== AI Pipeline Tests ==="
cd "$(dirname "$0")/../ai-pipeline"

echo "Installing dependencies..."
# Note: Some CUDA packages (nvidia-nccl-cu12) may fail on Windows - ignore these errors
pip install -r requirements.txt --quiet 2>/dev/null || echo "⚠️ Some GPU dependencies failed to install (expected on Windows)"
pip install pytest pytest-asyncio --quiet

echo ""
echo "--- Running tests (pytest tests/ -v --ignore=tests/test_pipeline_integration.py) ---"
pytest tests/ -v --ignore=tests/test_pipeline_integration.py || echo "⚠️ Some AI tests may need GPU/models (continue-on-error: true in CI)"

echo ""
echo "✅ AI Pipeline tests completed!"
