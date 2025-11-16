# 🚀 BeatSight - Linux Development Setup

**Welcome!** This guide will get you set up for BeatSight development on Ubuntu/Linux.

## ✅ Your Perfect Setup

Good news! **Everything you want to use is perfect for this project:**

- ✅ **Ubuntu/Linux** - Works great! Actually better than Windows for AI dev
- ✅ **VS Code** - Perfect choice! You don't need Visual Studio Community
- ✅ **Fish Shell** - All scripts are already fish-compatible

## 🎯 Quick Start (Automated)

### Option 1: Automated Setup (Recommended)

Run the setup script - it installs everything automatically:

```fish
cd ~/github/BeatSight
./setup-linux.fish
```

This will install:
- .NET 8.0 SDK (for desktop app)
- Python 3 + dependencies (for AI)
- FFmpeg (audio processing)
- Audio libraries (OpenAL, ALSA)
- Graphics libraries (OpenGL/Mesa)
- Python virtual environment
- Demucs AI model (~300MB)

**Time**: About 5-10 minutes depending on internet speed.

---

### Option 2: Manual Setup

If you prefer to install step-by-step:

#### 1. Install .NET 8.0 SDK

```fish
# Add Microsoft repository
wget https://packages.microsoft.com/config/ubuntu/24.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
sudo dpkg -i /tmp/packages-microsoft-prod.deb
rm /tmp/packages-microsoft-prod.deb

# Install .NET SDK
sudo apt update
sudo apt install -y dotnet-sdk-8.0

# Verify
dotnet --version
```

#### 2. Install System Dependencies

```fish
# Python and tools
sudo apt install -y python3 python3-pip python3-venv python3-dev

# FFmpeg for audio
sudo apt install -y ffmpeg

# Audio libraries
sudo apt install -y libopenal-dev libasound2-dev pulseaudio

# Graphics libraries
sudo apt install -y libgl1-mesa-dev libglu1-mesa-dev

# Git (if needed)
sudo apt install -y git
```

#### 3. Setup Python Environment

```fish
cd ~/github/BeatSight/ai-pipeline

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate.fish

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download Demucs model (~300MB, one-time)
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"
```

#### 4. Setup .NET Project

```fish
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet restore
```

#### 5. Load Shared Environment Defaults (Recommended)

Many training utilities expect a common set of paths. Source the fish helper before running exporters or training scripts:

```fish
cd ~/github/BeatSight
source ai-pipeline/training/tools/beatsight_env.fish
```

Override any variable (e.g. `BEATSIGHT_DATA_ROOT`) before sourcing if your datasets live on a different drive or mount.

---

## 🧪 Test Your Setup

### Test 1: Desktop App

```fish
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet run
```

**Expected**: A window should open with the BeatSight main menu.

**If it fails**:
- Check graphics drivers: `glxinfo | grep "OpenGL"`
- Install Mesa: `sudo apt install mesa-utils`

### Test 2: AI Pipeline

```fish
cd ~/github/BeatSight/ai-pipeline
source venv/bin/activate.fish

# Check help
python -m pipeline.process --help

# Test with sample (download any MP3 first)
python -m pipeline.process --input test.mp3 --output test.bsm
```

**Expected**: Processing completes and creates `test.bsm` file.

---

## 💻 VS Code Setup

### Install VS Code Extensions

Open VS Code and install these extensions:

1. **C# Dev Kit** (`ms-dotnettools.csdevkit`)
   - For C#/.NET development
   - Includes IntelliSense, debugging, testing

2. **Python** (`ms-python.python`)
   - For Python development
   - Includes linting, debugging

3. **Pylance** (`ms-python.vscode-pylance`)
   - Enhanced Python language server
   - Better autocomplete

4. **GitLens** (optional but recommended)
   - Git supercharged

### Configure VS Code

Create `.vscode/settings.json` in the project:

```json
{
  "editor.formatOnSave": true,
  "python.defaultInterpreterPath": "${workspaceFolder}/ai-pipeline/venv/bin/python",
  "python.terminal.activateEnvironment": true,
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "[csharp]": {
    "editor.defaultFormatter": "ms-dotnettools.csharp"
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  },
  "terminal.integrated.defaultProfile.linux": "fish",
  "files.exclude": {
    "**/bin": true,
    "**/obj": true,
    "**/__pycache__": true,
    "**/*.pyc": true
  }
}
```

### Open Project in VS Code

```fish
cd ~/github/BeatSight
code .
```

---

## 🎮 Development Workflow

### Desktop Development

```fish
# Navigate to desktop project
cd ~/github/BeatSight/desktop/BeatSight.Desktop

# Build
dotnet build

# Run
dotnet run

# Run with hot reload (for changes)
dotnet watch run

# Run in debug mode
dotnet run --configuration Debug
```

### AI Pipeline Development

```fish
# Navigate to AI pipeline
cd ~/github/BeatSight/ai-pipeline

# Activate environment (do this first!)
source venv/bin/activate.fish

# Run processing
python -m pipeline.process --input song.mp3 --output map.bsm

# Run API server
python -m pipeline.server

# Deactivate when done
deactivate
```

### Quick Commands

Add these aliases to your `~/.config/fish/config.fish`:

```fish
# BeatSight aliases
alias bs-desktop='cd ~/github/BeatSight/desktop/BeatSight.Desktop && dotnet run'
alias bs-ai='cd ~/github/BeatSight/ai-pipeline && source venv/bin/activate.fish'
alias bs-docs='cd ~/github/BeatSight && cat QUICKSTART.md'
```

---

## 🐛 Troubleshooting

### Issue: Desktop app won't start

**Symptom**: Window doesn't open or crashes immediately.

**Solutions**:

1. Check OpenGL support:
```fish
glxinfo | grep "OpenGL version"
# Should show OpenGL 3.0 or higher
```

2. Install/update graphics drivers:
```fish
# For NVIDIA
sudo ubuntu-drivers autoinstall

# For AMD
sudo apt install mesa-vulkan-drivers

# For Intel
sudo apt install mesa-utils
```

3. Check audio:
```fish
pactl info
# Should show PulseAudio running
```

### Issue: .NET command not found

**Solution**:
```fish
# Verify installation
which dotnet

# If not found, reinstall
sudo apt install --reinstall dotnet-sdk-8.0

# Add to PATH (if needed)
set -Ux DOTNET_ROOT /usr/share/dotnet
fish_add_path /usr/share/dotnet
```

### Issue: Python import errors

**Solution**:
```fish
# Ensure venv is activated
source ~/github/BeatSight/ai-pipeline/venv/bin/activate.fish

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt

# Check Python version (needs 3.10+)
python --version
```

### Issue: Demucs is slow

**Solution**:

1. Check if NVIDIA GPU is available:
```fish
nvidia-smi
```

2. Install CUDA support (for NVIDIA GPUs):
```fish
# Check CUDA version
nvcc --version

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

3. Use CPU mode (slower but works everywhere):
```fish
# In code, it already defaults to CPU if GPU unavailable
# Check in demucs_separator.py: self.device = "cuda" if torch.cuda.is_available() else "cpu"
```

---

## 📊 Performance Tips

### Desktop App

- **Release builds** are much faster:
```fish
dotnet run --configuration Release
```

- **Frame rate**: Check with Ctrl+F2 (osu-framework stats overlay)

### AI Pipeline

- **GPU acceleration**: 10-50x faster than CPU for Demucs
- **Batch processing**: Process multiple files at once (future feature)
- **Caching**: Demucs model is cached after first download

---

## 🎯 Next Steps

Now that you're set up:

1. **Explore the code**:
   - Desktop: `desktop/BeatSight.Game/`
   - AI: `ai-pipeline/pipeline/`

2. **Read documentation**:
   - `OVERVIEW.md` - Visual project summary
   - `docs/ARCHITECTURE.md` - Technical deep dive
   - `ROADMAP.md` - Development plan

3. **Start coding**:
   - Next task: Build gameplay screen
   - Check `QUICKSTART.md` for guidance

---

## 📚 Resources

### Linux-Specific

- .NET on Linux: https://learn.microsoft.com/en-us/dotnet/core/install/linux
- osu-framework Linux: https://github.com/ppy/osu-framework/wiki/Linux
- PulseAudio setup: https://wiki.archlinux.org/title/PulseAudio

### General

- VS Code docs: https://code.visualstudio.com/docs
- Fish shell: https://fishshell.com/docs/current/
- PyTorch CUDA: https://pytorch.org/get-started/locally/

---

## ✅ Checklist

Before starting development, ensure:

- [ ] .NET SDK installed (`dotnet --version`)
- [ ] Python 3.10+ installed (`python3 --version`)
- [ ] Virtual environment created (`~/github/BeatSight/ai-pipeline/venv/`)
- [ ] Desktop app builds (`cd desktop/BeatSight.Desktop && dotnet build`)
- [ ] AI pipeline works (`cd ai-pipeline && source venv/bin/activate.fish && python -m pipeline.process --help`)
- [ ] VS Code extensions installed (C# Dev Kit, Python)
- [ ] OpenGL working (`glxinfo | grep "OpenGL"`)
- [ ] Audio working (`pactl info`)

---

## 🆘 Getting Help

- **Documentation**: Check `docs/` folder
- **Issues**: Create GitHub issue (when repo is published)
- **Quick reference**: `cat QUICKSTART.md`

---

**You're all set! Start building! 🥁✨**

```fish
# Quick start command:
cd ~/github/BeatSight/desktop/BeatSight.Desktop && dotnet run
```
