#!/bin/bash
# Run GitHub Actions locally using 'act'
# This runs your actual .github/workflows/*.yml files in Docker containers
#
# Prerequisites:
#   - Docker Desktop must be running
#   - act CLI installed (winget install nektos.act)
#
# Usage:
#   ./scripts/act-local.sh                    # List all available jobs
#   ./scripts/act-local.sh backend-test       # Run the backend-test job from ci.yml
#   ./scripts/act-local.sh backend-lint       # Run the backend-lint job from ci.yml
#   ./scripts/act-local.sh desktop-build      # Run the desktop-build job from ci.yml
#   ./scripts/act-local.sh -W .github/workflows/ci.yml   # Run entire ci.yml workflow
#
# Common jobs from ci.yml:
#   backend-lint     - Ruff linting and formatting check
#   backend-test     - Pytest with coverage (needs Postgres & Redis in Docker)
#   desktop-build    - .NET build and test
#   ai-pipeline-test - AI pipeline tests
#   security-scan    - Trivy vulnerability scanner
#   ci-success       - Final check (depends on backend-test and desktop-build)

set -e

# Add Docker and act to PATH (winget installs to dynamic paths)
export PATH="$PATH:/c/Program Files/Docker/Docker/resources/bin"
ACT_PATH=$(find /c/Users/*/AppData/Local/Microsoft/WinGet/Packages -name "act.exe" 2>/dev/null | head -1)

if [[ -z "$ACT_PATH" ]]; then
    # Try if act is already in PATH
    if command -v act &> /dev/null; then
        ACT_PATH="act"
    else
        echo "❌ 'act' not found. Install with: winget install nektos.act"
        echo "   Then restart your terminal."
        exit 1
    fi
fi

cd "$(dirname "$0")/.."

# Check Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

if [[ $# -eq 0 ]]; then
    echo "=== Available GitHub Actions Jobs ==="
    echo ""
    "$ACT_PATH" -l
    echo ""
    echo "Usage: ./scripts/act-local.sh <job-name>"
    echo "Example: ./scripts/act-local.sh backend-test"
else
    JOB_NAME="$1"
    shift
    echo "=== Running GitHub Actions Job: $JOB_NAME ==="
    echo ""
    # Use medium-sized Ubuntu image for better compatibility
    # -W specifies the workflow file to avoid conflicts with duplicate job names
    "$ACT_PATH" -j "$JOB_NAME" -W .github/workflows/ci.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest "$@"
fi
