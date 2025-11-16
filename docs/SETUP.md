# Development Setup Guide

This document captures the common pieces of the BeatSight developer environment and points to the platform-specific playbooks. Skim this page first, then follow the detailed guides for your operating system.

## Platform Checklists

- **Windows (Git Bash preferred):** see `SETUP_WINDOWS.md`
- **Linux (fish/kitty or bash/zsh):** see `SETUP_LINUX.md`

Both guides land you in the same project layout with .NET for the desktop client, Python for the AI pipeline, and Poetry for the backend. Use whichever shell is native to your machine; Git Bash on Windows and fish on Linux are both fully supported.

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

## Troubleshooting Cross-Platform Issues

- **File paths & casing:** Keep the repository on a case-preserving filesystem (Windows with NTFS, Linux ext4). Avoid case-only renames when collaborating across OSes.
- **Line endings:** Prefer LF (`git config core.autocrlf input`).
- **OneDrive sync delays:** Store large datasets outside your synced folder and point `BEATSIGHT_DATA_ROOT` to the alternate location.
- **Audio/graphics packages:** Linux requirements are captured in `SETUP_LINUX.md`; Windows uses bundled dependencies from the .NET runtime.
- **Poetry not found:** Re-open your shell after installing via `pipx` (Windows) or add `$HOME/.local/bin` to PATH (Linux).

Refer back to `SETUP_WINDOWS.md` and `SETUP_LINUX.md` for deeper troubleshooting, recommended shell aliases, and optional productivity tooling.
