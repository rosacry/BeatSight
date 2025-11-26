#!/bin/bash
# Backend Tests - mirrors GitHub Actions ci.yml backend-test job EXACTLY
# Note: Requires PostgreSQL and Redis running locally
#   PostgreSQL: postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight_test
#   Redis: redis://localhost:6379/0
set -e

echo "=== Backend Tests ==="
cd "$(dirname "$0")/../backend"

echo "Installing dependencies..."
pip install -e ".[dev]" --quiet

echo ""
echo "--- Running pytest with coverage ---"
# Set test environment variables (same as GitHub Actions)
export DATABASE_DSN="postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight_test"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT=testing

pytest tests/ -v --cov=app --cov-report=xml --cov-report=term-missing

echo ""
echo "✅ Backend tests passed!"
