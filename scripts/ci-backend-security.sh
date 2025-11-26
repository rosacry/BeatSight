#!/bin/bash
# Backend Security Scan - mirrors GitHub Actions backend.yml security job EXACTLY
set -e

echo "=== Backend Security Scan ==="
cd "$(dirname "$0")/../backend"

echo "Installing security tools..."
pip install bandit safety --quiet

echo ""
echo "--- Bandit Security Linter (bandit -r app/ -ll) ---"
bandit -r app/ -ll

echo ""
echo "--- Safety Vulnerability Check (safety check --ignore 70612) ---"
safety check --ignore 70612 || echo "⚠️ Safety check found issues (continue-on-error: true in CI)"

echo ""
echo "✅ Security scan completed!"
