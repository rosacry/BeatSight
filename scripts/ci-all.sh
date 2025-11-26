#!/bin/bash
# Run all CI checks locally - mirrors the full GitHub Actions CI workflow
set -e

SCRIPT_DIR="$(dirname "$0")"
FAILED=0

echo "========================================"
echo "  BeatSight Local CI Runner"
echo "  (Mirrors GitHub Actions ci.yml)"
echo "========================================"
echo ""
echo "Required jobs (must pass for CI to succeed):"
echo "  - backend-lint  -> backend-test -> ci-success"
echo "  - desktop-build -> ci-success"
echo ""
echo "Optional jobs (non-blocking):"
echo "  - ai-pipeline-test (continue-on-error: true)"
echo "  - security-scan (exit-code: '0')"
echo ""

# Backend Lint (required - matches ci.yml backend-lint job)
echo "🔍 [1/6] Backend Lint..."
if bash "$SCRIPT_DIR/ci-backend-lint.sh"; then
    echo "✅ Backend Lint PASSED"
else
    echo "❌ Backend Lint FAILED"
    FAILED=1
fi
echo ""

# Backend Tests (required - matches ci.yml backend-test job)
# Note: Requires PostgreSQL and Redis running locally
echo "🧪 [2/6] Backend Tests..."
if bash "$SCRIPT_DIR/ci-backend-test.sh"; then
    echo "✅ Backend Tests PASSED"
else
    echo "❌ Backend Tests FAILED"
    FAILED=1
fi
echo ""

# Desktop Build (required - matches ci.yml desktop-build job)
echo "🖥️  [3/6] Desktop Build..."
if command -v dotnet &> /dev/null; then
    if bash "$SCRIPT_DIR/ci-desktop-build.sh"; then
        echo "✅ Desktop Build PASSED"
    else
        echo "❌ Desktop Build FAILED"
        FAILED=1
    fi
else
    echo "⏭️  Desktop Build SKIPPED (dotnet not installed)"
    echo "   Install .NET 8 SDK to run this check locally"
fi
echo ""

# AI Pipeline (optional - matches ci.yml ai-pipeline-test job with continue-on-error)
echo "🤖 [4/6] AI Pipeline Tests..."
if bash "$SCRIPT_DIR/ci-ai-pipeline.sh"; then
    echo "✅ AI Pipeline PASSED"
else
    echo "⚠️ AI Pipeline had issues (non-blocking, continue-on-error: true in CI)"
fi
echo ""

# Security Scan (optional - matches ci.yml security-scan job with exit-code: '0')
echo "🔒 [5/6] Security Scan..."
if bash "$SCRIPT_DIR/ci-backend-security.sh"; then
    echo "✅ Security Scan PASSED"
else
    echo "⚠️ Security Scan had issues (non-blocking, exit-code: '0' in CI)"
fi
echo ""

# Backend Docker Build (optional - only runs after lint+test pass in CI)
echo "🐳 [6/6] Backend Docker Build..."
if command -v docker &> /dev/null; then
    if bash "$SCRIPT_DIR/ci-backend-docker.sh"; then
        echo "✅ Backend Docker PASSED"
    else
        echo "⚠️ Backend Docker failed (non-blocking for local dev)"
    fi
else
    echo "⏭️  Backend Docker SKIPPED (docker not installed)"
fi
echo ""

echo ""
echo "========================================"
echo "  CI SUCCESS CHECK"
echo "  (Mirrors ci.yml ci-success job)"
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo "  ✅ ALL REQUIRED CI CHECKS PASSED!"
    echo "  backend-test: passed"
    echo "  desktop-build: passed (or skipped)"
    echo ""
    echo "  Safe to push to GitHub"
else
    echo "  ❌ SOME REQUIRED CI CHECKS FAILED"
    echo ""
    echo "  This mirrors the ci-success job in ci.yml:"
    echo "    if backend-test == failure OR desktop-build == failure:"
    echo "      exit 1"
    echo ""
    echo "  Fix issues before pushing"
    exit 1
fi
echo "========================================"
