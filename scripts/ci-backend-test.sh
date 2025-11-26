#!/bin/bash
# Backend Tests - mirrors GitHub Actions ci.yml backend-test job EXACTLY
#
# Usage:
#   ./ci-backend-test.sh          # Normal run (uses current venv)
#   ./ci-backend-test.sh --clean  # Clean run (creates fresh venv like GitHub Actions)
#
# Prerequisites (same as GitHub Actions services):
#   PostgreSQL 15:
#     - Host: localhost:5432
#     - User: beatsight
#     - Password: beatsight
#     - Database: beatsight_test
#
#   Redis 7:
#     - Host: localhost:6379
#
# Quick start with Docker:
#   docker run -d --name pg-test -p 5432:5432 \
#     -e POSTGRES_USER=beatsight \
#     -e POSTGRES_PASSWORD=beatsight \
#     -e POSTGRES_DB=beatsight_test \
#     postgres:15
#
#   docker run -d --name redis-test -p 6379:6379 redis:7
#
set -e

echo "=== Backend Tests ==="
echo "Mirrors: ci.yml -> backend-test job"
echo ""
cd "$(dirname "$0")/../backend"

# Check for --clean flag to simulate fresh GitHub Actions environment
CLEAN_MODE=false
if [[ "$1" == "--clean" ]]; then
    CLEAN_MODE=true
    echo "🧹 CLEAN MODE: Creating fresh virtual environment (like GitHub Actions)"
    echo ""
    
    # Remove and recreate a test-specific venv
    rm -rf .venv-ci-test
    python -m venv .venv-ci-test
    
    # Activate the clean venv
    if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        source .venv-ci-test/Scripts/activate
    else
        source .venv-ci-test/bin/activate
    fi
    
    echo "Using clean venv: $(which python)"
fi

echo "Installing dependencies (pip install -e \".[dev]\")..."
python -m pip install --upgrade pip --quiet 2>/dev/null || true
python -m pip install -e ".[dev]" --quiet

echo ""
echo "--- Running pytest with coverage ---"
echo "Command: pytest tests/ -v --cov=app --cov-report=xml --cov-report=term-missing"
echo ""

# Environment variables (same as GitHub Actions)
export DATABASE_DSN="postgresql+asyncpg://beatsight:beatsight@localhost:5432/beatsight_test"
export REDIS_URL="redis://localhost:6379/0"
export ENVIRONMENT="testing"

pytest tests/ -v --cov=app --cov-report=xml --cov-report=term-missing

echo ""
echo "✅ Backend tests passed!"

# Cleanup message for clean mode
if [[ "$CLEAN_MODE" == "true" ]]; then
    echo ""
    echo "ℹ️  Clean venv at backend/.venv-ci-test can be deleted with: rm -rf backend/.venv-ci-test"
fi
