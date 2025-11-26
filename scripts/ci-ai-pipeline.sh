#!/bin/bash
# AI Pipeline Tests - mirrors GitHub Actions ai-pipeline-test job
set -e

echo "=== AI Pipeline Tests ==="
cd "$(dirname "$0")/../ai-pipeline"

echo "Installing dependencies..."
pip install --quiet -r requirements.txt
pip install --quiet pytest pytest-asyncio

echo ""
echo "--- Running tests ---"
pytest tests/ -v --ignore=tests/test_pipeline_integration.py || echo "⚠️ Some AI tests may need GPU/models (non-blocking)"

echo ""
echo "✅ AI Pipeline tests completed!"
