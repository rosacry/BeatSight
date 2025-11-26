#!/bin/bash
# Backend Lint - mirrors GitHub Actions ci.yml backend-lint job EXACTLY
set -e

echo "=== Backend Lint Check ==="
cd "$(dirname "$0")/../backend"

echo "Installing dependencies..."
pip install ruff mypy --quiet

echo ""
echo "--- Ruff Linter (ruff check .) ---"
ruff check .

echo ""
echo "--- Ruff Formatter (ruff format --check .) ---"
ruff format --check .

echo ""
echo "✅ Backend lint checks passed!"
