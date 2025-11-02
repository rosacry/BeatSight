#!/usr/bin/env fish

# BeatSight Development Environment Setup for Linux (Ubuntu/Debian)
# This script installs all required dependencies for development

echo "🥁 BeatSight Development Setup"
echo "=============================="
echo ""

# Check if running on Linux
if not test (uname) = "Linux"
    echo "❌ Error: This script is for Linux only"
    exit 1
end

echo "📦 Installing system dependencies..."
echo ""

# Update package lists
echo "Updating package lists..."
sudo apt update

# Install .NET 8.0 SDK
echo ""
echo "📥 Installing .NET 8.0 SDK..."
if not command -v dotnet &> /dev/null
    # Add Microsoft package repository
    wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
    sudo dpkg -i /tmp/packages-microsoft-prod.deb
    rm /tmp/packages-microsoft-prod.deb
    
    # Install .NET SDK
    sudo apt update
    sudo apt install -y dotnet-sdk-8.0
    
    echo "✅ .NET 8.0 SDK installed"
else
    echo "✅ .NET already installed: "(dotnet --version)
end

# Install Python 3 and pip
echo ""
echo "🐍 Installing Python 3..."
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Install FFmpeg (required for audio processing)
echo ""
echo "🎵 Installing FFmpeg..."
sudo apt install -y ffmpeg

# Install audio libraries for osu-framework
echo ""
echo "🔊 Installing audio libraries..."
sudo apt install -y libopenal-dev libasound2-dev pulseaudio

# Install OpenGL libraries
echo ""
echo "🎮 Installing graphics libraries..."
sudo apt install -y libgl1-mesa-dev libglu1-mesa-dev

# Install Git (if not already installed)
echo ""
echo "📚 Checking Git installation..."
if not command -v git &> /dev/null
    sudo apt install -y git
    echo "✅ Git installed"
else
    echo "✅ Git already installed: "(git --version)
end

# Install VS Code extensions helper
echo ""
echo "💻 VS Code Extensions (install manually):"
echo "  - C# Dev Kit (ms-dotnettools.csdevkit)"
echo "  - Python (ms-python.python)"
echo "  - Pylance (ms-python.vscode-pylance)"
echo ""

# Setup Python virtual environment for AI pipeline
echo "🤖 Setting up Python environment for AI pipeline..."
cd ~/github/BeatSight/ai-pipeline

if test -d venv
    echo "✅ Python virtual environment already exists"
else
    python3 -m venv venv
    echo "✅ Python virtual environment created"
end

echo ""
echo "📥 Installing Python dependencies..."
source venv/bin/activate.fish
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "🎵 Downloading Demucs model (this may take a few minutes, ~300MB)..."
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"

echo ""
echo "✅ Python environment setup complete"
deactivate

# Test .NET installation
echo ""
echo "🧪 Testing .NET installation..."
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet restore
if test $status -eq 0
    echo "✅ .NET project restored successfully"
else
    echo "⚠️  .NET restore had issues, but may still work"
end

echo ""
echo "=============================="
echo "✅ Setup Complete!"
echo "=============================="
echo ""
echo "📚 Next steps:"
echo ""
echo "1. Run the desktop app:"
echo "   cd ~/github/BeatSight/desktop/BeatSight.Desktop"
echo "   dotnet run"
echo ""
echo "2. Test the AI pipeline:"
echo "   cd ~/github/BeatSight/ai-pipeline"
echo "   source venv/bin/activate.fish"
echo "   python -m pipeline.process --help"
echo ""
echo "3. Read the documentation:"
echo "   cat ~/github/BeatSight/QUICKSTART.md"
echo ""
echo "🥁 Happy coding! Let's build BeatSight! ✨"
