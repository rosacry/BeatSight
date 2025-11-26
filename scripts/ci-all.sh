#!/bin/bash
# Run all CI checks locally - mirrors the full GitHub Actions CI workflow
set -e

SCRIPT_DIR="$(dirname "$0")"
FAILED=0

echo "========================================"
echo "  BeatSight Local CI Runner"
echo "========================================"
echo ""

# Backend Lint
echo "🔍 [1/5] Backend Lint..."
if bash "$SCRIPT_DIR/ci-backend-lint.sh"; then
    echo "✅ Backend Lint PASSED"
else
    echo "❌ Backend Lint FAILED"
    FAILED=1
fi
echo ""

# Backend Docker Build
echo "🐳 [2/5] Backend Docker Build..."
if bash "$SCRIPT_DIR/ci-backend-docker.sh"; then
    echo "✅ Backend Docker PASSED"
else
    echo "❌ Backend Docker FAILED"
    FAILED=1
fi
echo ""

# Desktop Build (optional - requires .NET)
echo "🖥️  [3/5] Desktop Build..."
if command -v dotnet &> /dev/null; then
    if bash "$SCRIPT_DIR/ci-desktop-build.sh"; then
        echo "✅ Desktop Build PASSED"
    else
        echo "❌ Desktop Build FAILED"
        FAILED=1
    fi
else
    echo "⏭️  Desktop Build SKIPPED (dotnet not installed)"
fi
echo ""

# AI Pipeline (optional - may need GPU)
echo "🤖 [4/5] AI Pipeline Tests..."
if bash "$SCRIPT_DIR/ci-ai-pipeline.sh"; then
    echo "✅ AI Pipeline PASSED"
else
    echo "⚠️ AI Pipeline had issues (non-blocking)"
fi
echo ""

# Backend Security
echo "🔒 [5/5] Backend Security..."
if bash "$SCRIPT_DIR/ci-backend-security.sh"; then
    echo "✅ Backend Security PASSED"
else
    echo "⚠️ Backend Security had issues (non-blocking)"
fi
echo ""

echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo "  ✅ ALL CI CHECKS PASSED!"
    echo "  Safe to push to GitHub"
else
    echo "  ❌ SOME CI CHECKS FAILED"
    echo "  Fix issues before pushing"
    exit 1
fi
echo "========================================"
