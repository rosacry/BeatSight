#!/bin/bash
# Backend Security Scan - mirrors GitHub Actions security job
set -e

echo "=== Backend Security Scan ==="
cd "$(dirname "$0")/../backend"

echo "Installing security tools..."
pip install --quiet bandit safety

echo ""
echo "--- Bandit Security Linter ---"
bandit -r app/ -ll

echo ""
echo "--- Safety Vulnerability Check ---"
safety check --ignore 70612 || echo "⚠️ Safety check found issues (non-blocking)"

echo ""
echo "✅ Security scan completed!"
