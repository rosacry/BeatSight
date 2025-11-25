# 🍎 BeatSight - macOS Development Setup

**Welcome!** This guide will get you set up for BeatSight development on macOS.

## ✅ Compatibility

- ✅ **macOS 12+ (Monterey or later)** - Fully supported
- ✅ **Apple Silicon (M1/M2/M3)** - Native ARM64 builds work great
- ✅ **Intel Macs** - x64 builds supported
- ✅ **VS Code** - Recommended IDE with C#/Python extensions
- ✅ **zsh/bash/fish** - All shells supported

## 🎯 Quick Start

### Option 1: Automated Setup (Recommended)

```bash
# Clone repository
cd ~/Documents/github  # or any workspace without spaces
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight

# Run setup
./setup-macos.sh
```

### Option 2: Manual Setup

#### 1. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the post-install instructions to add Homebrew to your PATH.

#### 2. Install Core Dependencies

```bash
# Install .NET 8.0 SDK
brew install --cask dotnet-sdk

# Install Python 3.12
brew install python@3.12

# Install FFmpeg
brew install ffmpeg

# Install audio/video libraries
brew install openal-soft portaudio libsndfile

# Install pipx and Poetry
brew install pipx
pipx ensurepath
pipx install poetry
```

#### 3. Verify Installations

```bash
dotnet --version     # Should show 8.0.x
python3 --version    # Should show 3.10+
ffmpeg -version      # Should show recent build
poetry --version     # Should show 1.7+
```

## 🖥️ Desktop Client (osu-framework)

### Build and Run

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```

### Development Mode

```bash
# Hot reload during UI development
dotnet watch run
```

### Apple Silicon Notes

On Apple Silicon Macs, the .NET runtime and osu-framework use native ARM64 binaries. You may see Rosetta 2 translation warnings for some third-party libraries - these are usually harmless.

If you encounter issues:

```bash
# Force x64 mode (slower but more compatible)
arch -x86_64 dotnet run

# Check current architecture
file $(which dotnet)
```

### Graphics Requirements

macOS uses Metal for graphics rendering. The osu-framework abstracts this via the Veldrid backend. Ensure:

- macOS 12+ (Metal 2 support required)
- GPU drivers are up-to-date (System Settings → Software Update)

## 🐍 AI Pipeline (Python)

### Create Virtual Environment

```bash
cd ai-pipeline

# Create venv with Python 3.12
python3.12 -m venv .venv

# Activate (bash/zsh)
source .venv/bin/activate

# Or for fish shell
source .venv/bin/activate.fish
```

### Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### GPU Acceleration (Apple Silicon)

PyTorch supports Metal Performance Shaders (MPS) for GPU acceleration on Apple Silicon:

```python
import torch
print(torch.backends.mps.is_available())  # Should print True
```

The AI pipeline automatically detects MPS and uses it when available. For explicit control:

```bash
# Force MPS (Apple GPU)
export PYTORCH_ENABLE_MPS_FALLBACK=1

# Force CPU only
export CUDA_VISIBLE_DEVICES=""
```

### Demucs Model Download

The first beatmap generation will download the Demucs model (~300MB):

```bash
# Pre-download to avoid delay during first generation
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"
```

## 🌐 Backend (FastAPI)

### Setup with Poetry

```bash
cd backend

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment Configuration

```bash
# Copy template
cp .env.example .env

# Edit with your settings
nano .env  # or use your preferred editor
```

Key settings to configure:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis for job queue
- `JWT_SECRET_KEY` - Generate with `openssl rand -hex 32`

## 🗄️ Database (PostgreSQL)

### Install PostgreSQL

```bash
brew install postgresql@16
brew services start postgresql@16
```

### Create Database

```bash
createdb beatsight_dev
createuser -s beatsight
```

### Verify Connection

```bash
psql -d beatsight_dev -c "SELECT version();"
```

## 📦 Redis (Job Queue)

### Install Redis

```bash
brew install redis
brew services start redis
```

### Verify Connection

```bash
redis-cli ping  # Should return "PONG"
```

## 🔧 VS Code Extensions

Recommended extensions for macOS development:

```json
{
  "recommendations": [
    "ms-dotnettools.csharp",
    "ms-dotnettools.csdevkit",
    "ms-python.python",
    "ms-python.vscode-pylance",
    "bradlc.vscode-tailwindcss",
    "EditorConfig.EditorConfig"
  ]
}
```

Install all at once:

```bash
code --install-extension ms-dotnettools.csharp
code --install-extension ms-dotnettools.csdevkit
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
```

## 🐛 Troubleshooting

### "Unable to load shared library 'libdl'" Error

This can occur on Apple Silicon. Fix:

```bash
# Ensure Rosetta 2 is installed
softwareupdate --install-rosetta --agree-to-license
```

### Audio Output Issues

If no audio output:

1. Check System Settings → Sound → Output
2. Ensure the app has microphone permissions (for live input features)

```bash
# Test audio with FFmpeg
ffplay -nodisp -autoexit /path/to/audio.mp3
```

### OpenGL/Metal Warnings

osu-framework uses Veldrid for cross-platform graphics. Some Metal validation warnings are expected and harmless:

```
[Metal Validation] ...
```

To suppress verbose logging:

```bash
export METAL_DEVICE_WRAPPER_TYPE=0
```

### Python "SSL Certificate Verify Failed"

Common on fresh macOS installs:

```bash
# Install certificates
/Applications/Python\ 3.12/Install\ Certificates.command

# Or via pip
pip install --upgrade certifi
```

### Slow First Build

The first `dotnet restore` downloads NuGet packages. Subsequent builds are much faster.

```bash
# Pre-warm cache
dotnet restore BeatSight.sln
```

## 📁 Project Structure

After setup, your workspace should look like:

```
BeatSight/
├── ai-pipeline/          # Python AI processing
│   └── .venv/            # Python virtual environment
├── backend/              # FastAPI web backend
├── desktop/              # C# desktop client
│   ├── BeatSight.Desktop/
│   ├── BeatSight.Game/
│   └── BeatSight.Tests/
├── data/                 # Training data (gitignored)
└── docs/                 # Documentation
```

## 🚀 Next Steps

1. **Run the desktop client**: `cd desktop/BeatSight.Desktop && dotnet run`
2. **Test AI pipeline**: `cd ai-pipeline && python -m pipeline.server`
3. **Start backend**: `cd backend && poetry run uvicorn app.main:app --reload`
4. **Read the docs**: See `docs/ARCHITECTURE.md` for system overview

## 📚 Additional Resources

- [.NET on macOS](https://docs.microsoft.com/en-us/dotnet/core/install/macos)
- [osu-framework](https://github.com/ppy/osu-framework)
- [PyTorch MPS Backend](https://pytorch.org/docs/stable/notes/mps.html)
- [Homebrew](https://brew.sh)

---

**Having issues?** Check `docs/SETUP.md` for general troubleshooting or open an issue on GitHub.
