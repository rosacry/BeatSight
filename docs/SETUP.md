# Development Setup Guide

Complete setup instructions for BeatSight development on all platforms.

## Platform Quick Start

<details open>
<summary><strong>Windows (Git Bash / PowerShell)</strong></summary>

```powershell
# Install prerequisites (PowerShell as Admin)
winget install Git.Git Microsoft.DotNet.SDK.8 Python.Python.3.12 Gyan.FFmpeg

# Clone and run
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight/desktop/BeatSight.Desktop
dotnet restore && dotnet run
```
</details>

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# Install prerequisites
sudo apt update
sudo apt install -y dotnet-sdk-8.0 python3.10 python3-venv python3-pip ffmpeg \
                    libopenal-dev libasound2-dev libgl1-mesa-dev

# Clone and run
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight/desktop/BeatSight.Desktop
dotnet restore && dotnet run
```
</details>

<details>
<summary><strong>macOS (Intel / Apple Silicon)</strong></summary>

```bash
# Install prerequisites via Homebrew
brew install --cask dotnet-sdk
brew install python@3.12 ffmpeg openal-soft

# Clone and run
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight/desktop/BeatSight.Desktop
dotnet restore && dotnet run
```
</details>

## Core Prerequisites (All Platforms)

| Tool | Minimum Version | Notes |
|------|-----------------|-------|
| .NET SDK | 8.0.x | Required for `BeatSight.Desktop` and tests |
| Python | 3.10+ | Used by `ai-pipeline` and training scripts |
| Poetry | 1.7+ | Dependency manager for the FastAPI backend |
| FFmpeg | Latest stable | Audio processing and previews |
| Git | Latest stable | Recommended: enable long path support |

### Quick Install Snippets

- **Windows (PowerShell as Administrator):**
   ```powershell
   winget install --id Git.Git --source winget
   winget install --id Microsoft.DotNet.SDK.8 --source winget
   winget install --id Python.Python.3.12 --source winget
   winget install --id Gyan.FFmpeg --source winget
   winget install --id Python.Pipx --source winget
   pipx install poetry
   pipx ensurepath
   ```

- **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install -y dotnet-sdk-8.0 python3.10 python3.10-venv python3-pip python3-dev \
                                 ffmpeg git libopenal-dev libasound2-dev libgl1-mesa-dev libglu1-mesa-dev
   python3 -m pip install --upgrade pip
   python3 -m pip install --user poetry
   ```
   Add Poetry to your PATH: `export PATH="$HOME/.local/bin:$PATH"` (place in shell config).

## Repository Bootstrap

```bash
cd ~/OneDrive/Documents/github     # or any workspace path without spaces
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight
git config core.longpaths true
```

When collaborating across Windows and Linux machines, set `git config core.autocrlf input` to keep line endings consistent.

## Desktop Client (osu-framework)

| Platform | Commands |
|----------|----------|
| Windows (Git Bash) | `cd desktop/BeatSight.Desktop && dotnet restore && dotnet run` |
| Linux/macOS | `cd desktop/BeatSight.Desktop && dotnet restore && dotnet run` |

Use `dotnet watch run` during UI iteration. The client requires a GPU capable of OpenGL 3.0+. Windows relies on ANGLE; keep GPU drivers current. Linux users should confirm Mesa/OpenGL packages (see `SETUP_LINUX.md`).

## AI Pipeline (Python)

Create a virtual environment per platform and install requirements:

- **Windows (Git Bash):**
   ```bash
   cd ai-pipeline
   python -m venv .venv
   source .venv/Scripts/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

- **Linux (fish):**
   ```fish
   cd ai-pipeline
   python3 -m venv venv
   source venv/bin/activate.fish
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

Run `python -m pipeline.process --help` to confirm the CLI is wired up. Install GPU-enabled PyTorch if you have CUDA hardware (see platform guides for version-specific commands).

## Environment Variable Hook

Source the helper script before running training tools so shared paths are in sync. Override any variable beforehand if your datasets live on a different drive.

- **Bash/Zsh/Git Bash:**
  ```bash
  source ai-pipeline/training/tools/beatsight_env.sh
  ```

- **fish:**
  ```fish
  source ai-pipeline/training/tools/beatsight_env.fish
  ```

The script prints the resolved directories for quick verification.

## Smoke Tests

Run these checks after a fresh setup (activate your Python virtualenv first):

```bash
# Solution build + tests
cd <repo>

# AI pipeline
cd ai-pipeline
python -m pipeline.process --help

# Backend
cd ../backend
poetry run uvicorn app.main:app --reload --port 9000
```

Visit `http://localhost:9000/health/live` to confirm the backend responds.

## Troubleshooting

### Common Issues (All Platforms)

- **File paths & casing:** Keep the repository on a case-preserving filesystem. Avoid case-only renames when collaborating across OSes.
- **Line endings:** Use `git config core.autocrlf input` for LF endings.
- **Poetry not found:** Re-open your shell after installing via `pipx` (Windows) or add `$HOME/.local/bin` to PATH (Linux/macOS).

### Windows-Specific

| Issue | Solution |
|-------|----------|
| `dotnet: command not found` | Add to PATH: `$env:PATH += ";C:\Program Files\dotnet"` |
| pip install fails with "Visual C++ required" | `winget install Microsoft.VisualStudio.2022.BuildTools` (select C++ workload) |
| Docker Desktop won't start | Enable Hyper-V and WSL2 in Windows Features |
| Port already in use | `netstat -ano \| findstr :8000` then `taskkill /PID <PID> /F` |

### Linux-Specific

| Issue | Solution |
|-------|----------|
| Desktop app won't start | Check OpenGL: `glxinfo \| grep "OpenGL version"` (needs 3.0+) |
| Graphics errors | Install Mesa: `sudo apt install mesa-utils mesa-vulkan-drivers` |
| Audio not working | Check PulseAudio: `pactl info` |
| .NET command not found | Reinstall: `sudo apt install --reinstall dotnet-sdk-8.0` |

### macOS-Specific

| Issue | Solution |
|-------|----------|
| "Unable to load shared library 'libdl'" | Install Rosetta 2: `softwareupdate --install-rosetta --agree-to-license` |
| SSL Certificate errors | Run `/Applications/Python\ 3.12/Install\ Certificates.command` |
| Metal validation warnings | Safe to ignore; suppress with `export METAL_DEVICE_WRAPPER_TYPE=0` |
| Slow first build | Pre-warm: `dotnet restore BeatSight.sln` |

---

## GPU Acceleration

### NVIDIA (CUDA) - Windows/Linux

```bash
# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Apple Silicon (MPS) - macOS

PyTorch automatically detects MPS. Verify:
```python
import torch
print(torch.backends.mps.is_available())  # Should print True
```

### CPU-Only Fallback

The AI pipeline works on CPU (slower, ~10x) if no GPU is available.

---

## Running Tests

```bash
# Desktop (NUnit)
dotnet test BeatSight.sln

# Backend (pytest)
cd backend && poetry run pytest tests/ -v

# Frontend (Vitest)
cd frontend && npm run test

# AI Pipeline (pytest)
cd ai-pipeline && pytest tests/ -v
```

---

## Next Steps

- [Architecture Guide](ARCHITECTURE.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Current Status](product/status.md)
- [ML Training Runbook](ml_training_runbook.md)
