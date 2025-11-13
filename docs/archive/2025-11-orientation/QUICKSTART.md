# BeatSight Quick Start Guide

Welcome to BeatSight development! This guide will get you up and running quickly.

## 🚀 Quick Start (5 minutes)

### For Desktop Development

```fish
# Navigate to project
cd ~/github/BeatSight

# Build and run desktop app (from repository root)
dotnet restore
dotnet run --project desktop/BeatSight.Desktop/BeatSight.Desktop.csproj
```

That's it! The BeatSight window should open.

> Tip: A sample beatmap (`shared/formats/simple_beat.bsm`) ships with the repo so Song Select always has something to load. Its audio file is intentionally missing; BeatSight will fall back to a silent timing track for quick testing.

### For AI Pipeline Development

```bash
cd ~/github/drumify/ai-pipeline

# Setup Python environment
python3 -m venv venv
source venv/bin/activate.fish  # or activate for bash/zsh

# Install dependencies
pip install -r requirements.txt

# Download AI model (one-time, ~300MB)
python -c "import demucs.pretrained; demucs.pretrained.get_model('htdemucs')"

# Test with sample audio
# (Download any audio file first to test_audio.mp3)
python -m pipeline.process --input test_audio.mp3 --output output.bsm
```

## 📚 What You Have Now

### Complete Project Structure

```
beatsight/
├── desktop/              ← C# desktop app (osu-framework)
├── ai-pipeline/          ← Python AI processing
├── docs/                 ← Comprehensive documentation
├── shared/               ← Shared formats/protocols
└── README.md             ← Main project documentation
```

### Key Files to Explore

**Desktop App:**
- `desktop/BeatSight.Game/BeatSightGame.cs` - Main game class
- `desktop/BeatSight.Game/Screens/MainMenuScreen.cs` - UI example
- `desktop/BeatSight.Game/Beatmaps/Beatmap.cs` - Data structures

**AI Pipeline:**
- `ai-pipeline/pipeline/process.py` - Main processing orchestrator
- `ai-pipeline/separation/demucs_separator.py` - Source separation
- `ai-pipeline/transcription/onset_detector.py` - Drum hit detection
- `ai-pipeline/transcription/drum_classifier.py` - Drum type classifier
- `ai-pipeline/pipeline/beatmap_generator.py` - Beatmap file creator

**Documentation:**
- `docs/ARCHITECTURE.md` - System design overview
- `docs/BEATMAP_FORMAT.md` - File format specification
- `docs/SETUP.md` - Detailed development setup
- `docs/CONTRIBUTING.md` - Contribution guidelines

## 🎯 Next Steps

### Choose Your Path

#### Path 1: Desktop App Development
1. **Learn osu-framework basics**
   - Read: https://github.com/ppy/osu-framework/wiki
   - Explore: `desktop/BeatSight.Game/Screens/`
   
2. **Create a gameplay screen**
   - Add a new screen in `Screens/GameplayScreen.cs`
   - Implement falling notes visualization
   - Add hit detection logic

3. **Build the editor**
   - Timeline view with waveform
   - Note placement and editing
   - Audio playback controls

#### Path 2: AI Pipeline Development
1. **Understand the pipeline**
   - Read: `ai-pipeline/README.md`
   - Trace through: `pipeline/process.py`
   
2. **Improve classification**
   - Current: Heuristic-based (placeholder)
   - Goal: Train a neural network
   - See: `transcription/drum_classifier.py` TODO section

3. **Optimize performance**
   - GPU acceleration
   - Batch processing
   - Caching strategies

#### Path 3: Full-Stack Development
1. **Backend API** (future phase)
   - FastAPI server for community features
   - Database for beatmap storage
   - User authentication

2. **Mobile apps** (future phase)
   - Flutter cross-platform development
   - Touch-optimized gameplay
   - Beatmap browser

## 🔥 Quick Wins (Start Here!)

### Easy First Contributions

1. **Add UI polish**
   - Improve menu button hover effects
   - Add transitions between screens
   - Create a loading spinner

2. **Enhance beatmap format**
   - Add new metadata fields
   - Improve JSON validation
   - Create example beatmaps

3. **Documentation**
   - Add code comments
   - Create tutorials
   - Write API documentation

4. **Testing**
   - Write unit tests
   - Create test beatmaps
   - Add integration tests

## 🛠️ Development Commands

### Desktop App

```bash
# Build
cd desktop/BeatSight.Desktop
dotnet build

# Run
dotnet run

# Run tests (when added)
dotnet test

# Create release build
dotnet publish -c Release -r linux-x64 --self-contained
```

### AI Pipeline

```bash
cd ai-pipeline

# Activate environment
source venv/bin/activate.fish

# Process audio file
python -m pipeline.process --input audio.mp3 --output beatmap.bsm

# Run API server
python -m pipeline.server

# Run tests (when added)
pytest tests/

# Check code style
pylint pipeline/
black pipeline/ --check
```

## 🐛 Troubleshooting

### Desktop App Won't Start

```bash
# Clear and restore packages
dotnet clean
dotnet nuget locals all --clear
dotnet restore --force
```

### Python Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate.fish

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Demucs Download Fails

```bash
# Manual download and cache
python -c "
import demucs.pretrained
demucs.pretrained.get_model('htdemucs', device='cpu')
"
```

### Audio Playback Issues (Linux)

```bash
# Install audio libraries
sudo apt install libopenal-dev libasound2-dev pulseaudio
```

## 📖 Learning Resources

### osu-framework
- Wiki: https://github.com/ppy/osu-framework/wiki
- Source: https://github.com/ppy/osu-framework
- Example: osu!lazer source code

### Audio Processing
- Librosa docs: https://librosa.org/doc/latest/
- Demucs: https://github.com/facebookresearch/demucs
- Music Information Retrieval: https://musicinformationretrieval.com/

### .NET/C#
- Microsoft docs: https://learn.microsoft.com/en-us/dotnet/
- C# guide: https://learn.microsoft.com/en-us/dotnet/csharp/

## 🎵 Project Vision

**Goal**: Make drum learning accessible, engaging, and fun by combining gaming principles with music education.

**Inspiration**: 
- osu! for sight-reading skills
- Guitar Hero for visual learning
- Demucs for AI-powered separation

**Target Users**:
- Beginner drummers frustrated with traditional learning
- Intermediate drummers wanting to expand repertoire
- Rhythm game players interested in real instruments

## 💡 Ideas to Explore

- **Real-time mode**: Play along and get instant feedback
- **Practice mode**: Loop sections, slow down audio
- **Challenge mode**: Random patterns, sight-reading tests
- **Multiplayer**: Compete on scores, share beatmaps
- **VR mode**: Immersive drum learning experience
- **MIDI support**: Use electronic drum kits as input

## 🤝 Getting Help

- **Documentation**: Check `docs/` folder first
- **Issues**: https://github.com/yourusername/beatsight/issues
- **Discussions**: https://github.com/yourusername/beatsight/discussions
- **Discord**: (placeholder - create community server)

## ✅ Current Status

### ✅ Completed
- Project structure and architecture
- Beatmap format specification (.bsm)
- Basic desktop app skeleton (osu-framework)
- AI pipeline foundation (Demucs integration)
- Onset detection implementation
- Beatmap generation logic
- API server structure
- Comprehensive documentation

### 🚧 In Progress
- Desktop gameplay implementation
- Editor UI development
- AI model training

### 📋 TODO
- Real-time microphone input
- Mobile app development
- Backend API deployment
- Community features
- Advanced AI models
- Performance optimizations

## 🎉 Start Building!

Pick a task from the TODO list or create your own feature. Don't hesitate to experiment and have fun!

**Remember**: This is a learning project. Mistakes are encouraged. Break things, fix them, and learn along the way.

Happy coding! 🥁✨
