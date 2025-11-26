#!/bin/bash
# Backend Lint - mirrors GitHub Actions ci.yml backend-lint job EXACTLY
set -e

echo "=== Backend Lint Check ==="
echo "Mirrors: ci.yml -> backend-lint job"
echo ""
cd "$(dirname "$0")/../backend"

echo "Installing dependencies (pip install ruff mypy)..."
python -m pip install --upgrade pip --quiet 2>/dev/null || true
python -m pip install ruff mypy --quiet

echo ""
echo "--- Ruff Linter (ruff check .) ---"
ruff check .

echo ""
echo "--- Ruff Formatter (ruff format --check .) ---"
ruff format --check .

echo ""
echo "✅ Backend lint checks passed!"
