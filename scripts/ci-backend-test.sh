#!/bin/bash
# Backend Tests - mirrors GitHub Actions backend-test job
# Note: Requires PostgreSQL and Redis running locally or skips DB tests
set -e

echo "=== Backend Tests ==="
cd "$(dirname "$0")/../backend"

echo "Installing dependencies..."
pip install --quiet -e ".[dev,test]" 2>/dev/null || pip install --quiet -e ".[dev]"

echo ""
echo "--- Running pytest ---"
# Set test environment variables
export ENVIRONMENT=testing
export TESTING=true

pytest tests/ -v --tb=short

echo ""
echo "✅ Backend tests passed!"
