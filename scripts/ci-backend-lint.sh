#!/bin/bash
# Backend Lint - mirrors GitHub Actions backend-lint and lint jobs
set -e

echo "=== Backend Lint Check ==="
cd "$(dirname "$0")/../backend"

echo "Installing ruff..."
pip install --quiet ruff

echo ""
echo "--- Ruff Linter (ruff check) ---"
ruff check .

echo ""
echo "--- Ruff Formatter (ruff format --check) ---"
ruff format --check .

echo ""
echo "✅ Backend lint checks passed!"
