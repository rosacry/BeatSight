# Development Setup Guide

## Prerequisites

### Required Software

1. **.NET 8.0 SDK**
   ```bash
   # Ubuntu/Debian
   wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
   sudo dpkg -i packages-microsoft-prod.deb
   sudo apt update
   sudo apt install -y dotnet-sdk-8.0
   
   # Verify
   dotnet --version
   ```

2. **Python 3.10+**
   ```bash
   # Ubuntu/Debian
   sudo apt install python3.10 python3.10-venv python3-pip
   
   # Verify
   python3 --version
   ```

3. **FFmpeg** (for audio processing)
   ```bash
   sudo apt install ffmpeg
   ```

4. **Git**
   ```bash
   sudo apt install git
   ```

## Project Setup

### 1. Clone Repository

```bash
cd ~/github
git clone https://github.com/yourusername/beatsight.git
cd beatsight
```

### 2. Desktop App Setup

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet build

# Run the app
dotnet run
```

**Troubleshooting:**
- If osu-framework fails to restore, ensure you have internet connection
- On Linux, you may need additional libraries:
  ```bash
  sudo apt install libopenal-dev libgl1-mesa-dev libglu1-mesa-dev
  ```

### 3. AI Pipeline Setup

```bash
cd ../../ai-pipeline

# Create virtual environment
python3 -m venv venv

# Activate (bash/zsh)
source venv/bin/activate

# Activate (fish shell)
source venv/bin/activate.fish

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download Demucs model (first time only, ~300MB)
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"

# Test the pipeline
python -m pipeline.process --help
```

**GPU Support (Optional but Recommended):**
```bash
# If you have NVIDIA GPU with CUDA 11.8+
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 4. Backend API Setup (Future)

```bash
cd ../backend
npm install
npm run dev
```

## IDE Setup

### Visual Studio Code (Recommended)

1. **Install VS Code**
   ```bash
   sudo snap install code --classic
   ```

2. **Install Extensions**
   - C# Dev Kit (Microsoft)
   - Python (Microsoft)
   - Pylance
   - GitLens
   - Thunder Client (API testing)

3. **Open Workspace**
   ```bash
   code ~/github/beatsight
   ```

4. **Configure Python Interpreter**
   - Press `Ctrl+Shift+P`
   - Type "Python: Select Interpreter"
   - Choose `./ai-pipeline/venv/bin/python`

### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "python.defaultInterpreterPath": "${workspaceFolder}/ai-pipeline/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["ai-pipeline/tests"],
  "[csharp]": {
    "editor.defaultFormatter": "ms-dotnettools.csharp"
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.python"
  }
}
```

## Testing Your Setup

### Test Desktop App

```bash
cd desktop/BeatSight.Desktop
dotnet run
```

You should see a window with the BeatSight main menu.

### Test AI Pipeline

```bash
cd ai-pipeline

# Create a test directory
mkdir -p test_data
cd test_data

# Download a Creative Commons test audio file
wget https://freepd.com/music/Example.mp3 -O test.mp3

# Process it
cd ..
python -m pipeline.process --input test_data/test.mp3 --output test_data/test.bsm --confidence 0.6

# Check the output
cat test_data/test.bsm
```

## Development Workflow

### Typical Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make Changes**
   - Edit code in your IDE
   - Test frequently
   - Commit incrementally

3. **Run Tests**
   ```bash
   # C# tests
   cd desktop
   dotnet test
   
   # Python tests
   cd ai-pipeline
   pytest tests/
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add amazing feature"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/my-new-feature
   ```

### Hot Reload

**Desktop App:**
- osu-framework supports hot reload for some changes
- For major changes, stop and restart with `dotnet run`

**AI Pipeline:**
- Python modules reload automatically in most cases
- Restart the server for server.py changes:
  ```bash
  # Stop with Ctrl+C, then:
  python -m pipeline.server
  ```

## Debugging

### Desktop App

**VS Code:**
1. Open `desktop/BeatSight.Desktop`
2. Press `F5` or go to Run > Start Debugging
3. Set breakpoints by clicking left of line numbers

**Command Line:**
```bash
cd desktop/BeatSight.Desktop
dotnet run --configuration Debug
```

### AI Pipeline

**VS Code:**
1. Set breakpoints in Python files
2. Press `F5` or Run > Start Debugging
3. Or use the Python debugger:
   ```bash
   python -m pdb pipeline/process.py --input test.mp3 --output test.bsm
   ```

**Print Debugging:**
```python
print(f"Debug: {variable}")
import pdb; pdb.set_trace()  # Breakpoint
```

## Common Issues

### Linux-Specific Issues

**Audio Playback Issues:**
```bash
# Install ALSA
sudo apt install libasound2-dev

# Or use PulseAudio
sudo apt install pulseaudio
```

**Graphics Issues:**
```bash
# Install Mesa drivers
sudo apt install mesa-utils
glxinfo | grep "OpenGL"
```

### Python Issues

**ImportError: No module named 'torch':**
```bash
pip install torch torchvision torchaudio
```

**CUDA out of memory:**
- Reduce batch size in config
- Use CPU mode: Set `device = "cpu"` in code
- Close other GPU applications

### .NET Issues

**Package restore fails:**
```bash
dotnet nuget locals all --clear
dotnet restore --force
```

**"Unable to find osu.Framework":**
- Check internet connection
- Try updating: `dotnet nuget update`

## Performance Tips

### AI Pipeline Optimization

1. **Use GPU** if available (10-50x faster for Demucs)
2. **Reduce sample rate** for faster testing (16kHz instead of 44.1kHz)
3. **Cache Demucs model** (downloaded automatically on first run)
4. **Parallel processing** for batch jobs

### Desktop App Optimization

1. **Release builds** for performance testing:
   ```bash
   dotnet build -c Release
   dotnet run -c Release
   ```

2. **Profile with dotTrace** or VS profiler
3. **Check frame rate** in osu-framework stats overlay (Ctrl+F2)

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
- Check [BEATMAP_FORMAT.md](BEATMAP_FORMAT.md) for file format details
- See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- Join our [Discord](https://discord.gg/beatsight) for help

Happy coding! 🥁
