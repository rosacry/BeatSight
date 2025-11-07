#!/usr/bin/env bash

# BeatSight Development Environment Setup for Linux (Ubuntu/Debian)
# This script installs all required dependencies for development.

set -euo pipefail

echo "🥁 BeatSight Development Setup"
echo "=============================="
echo

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "❌ Error: This script is for Linux only"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

echo "📦 Installing system dependencies..."
echo

echo "Updating package lists..."
sudo apt update

echo
echo "📥 Installing .NET 8.0 SDK..."
if ! command -v dotnet >/dev/null 2>&1; then
    wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
    sudo dpkg -i /tmp/packages-microsoft-prod.deb
    rm /tmp/packages-microsoft-prod.deb

    sudo apt update
    sudo apt install -y dotnet-sdk-8.0
    echo "✅ .NET 8.0 SDK installed"
else
    echo "✅ .NET already installed: $(dotnet --version)"
fi

echo
echo "🐍 Installing Python 3..."
sudo apt install -y python3 python3-pip python3-venv python3-dev

echo
echo "🎵 Installing FFmpeg..."
sudo apt install -y ffmpeg

echo
echo "🔊 Installing audio libraries..."
sudo apt install -y libopenal-dev libasound2-dev pulseaudio

echo
echo "🎮 Installing graphics libraries..."
sudo apt install -y libgl1-mesa-dev libglu1-mesa-dev

echo
echo "📚 Checking Git installation..."
if ! command -v git >/dev/null 2>&1; then
    sudo apt install -y git
    echo "✅ Git installed"
else
    echo "✅ Git already installed: $(git --version)"
fi

echo
echo "💻 VS Code Extensions (install manually):"
echo "  - C# Dev Kit (ms-dotnettools.csdevkit)"
echo "  - Python (ms-python.python)"
echo "  - Pylance (ms-python.vscode-pylance)"
echo

echo "🤖 Setting up Python environment for AI pipeline..."
cd "${REPO_ROOT}/ai-pipeline"

if [[ -d venv ]]; then
    echo "✅ Python virtual environment already exists"
else
    python3 -m venv venv
    echo "✅ Python virtual environment created"
fi

echo
echo "📥 Installing Python dependencies..."
"${REPO_ROOT}/ai-pipeline/venv/bin/pip" install --upgrade pip
"${REPO_ROOT}/ai-pipeline/venv/bin/pip" install -r requirements.txt

echo
echo "🎵 Downloading Demucs model (this may take a few minutes, ~300MB)..."
"${REPO_ROOT}/ai-pipeline/venv/bin/python" -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"

echo
echo "✅ Python environment setup complete"

echo
echo "🧪 Testing .NET installation..."
cd "${REPO_ROOT}/desktop/BeatSight.Desktop"
if dotnet restore; then
    echo "✅ .NET project restored successfully"
else
    echo "⚠️  .NET restore had issues, but may still work"
fi

echo
echo "=============================="
echo "✅ Setup Complete!"
echo "=============================="
echo
echo "📚 Next steps:"
echo
echo "1. Run the desktop app:"
echo "   cd ${REPO_ROOT}/desktop/BeatSight.Desktop"
echo "   dotnet run"
echo
echo "2. Test the AI pipeline:"
echo "   cd ${REPO_ROOT}/ai-pipeline"
echo "   source venv/bin/activate        # bash/zsh"
echo "   source venv/bin/activate.fish    # fish"
echo "   python -m pipeline.process --help"
echo
echo "3. Read the documentation:"
echo "   cat ${REPO_ROOT}/QUICKSTART.md"
echo
echo "🥁 Happy coding! Let's build BeatSight! ✨"
