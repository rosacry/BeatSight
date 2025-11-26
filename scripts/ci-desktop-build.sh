#!/bin/bash
# Desktop Build - mirrors GitHub Actions ci.yml desktop-build job EXACTLY
set -e

echo "=== Desktop Build (.NET) ==="
cd "$(dirname "$0")/.."

echo "--- Restoring dependencies (dotnet restore) ---"
dotnet restore

echo ""
echo "--- Building (dotnet build --configuration Release --no-restore) ---"
dotnet build --configuration Release --no-restore

echo ""
echo "--- Running tests (dotnet test --no-build --configuration Release --verbosity normal) ---"
dotnet test --no-build --configuration Release --verbosity normal

echo ""
echo "✅ Desktop build passed!"
