# 🎯 BeatSight Quick Reference

**Your Linux + VS Code Setup - PERFECT for this project!** ✅

---

## 📋 Quick Answers

### Q: Can I use Linux (Ubuntu)?
**A: YES!** Linux is actually BETTER for this project. Better GPU drivers for AI, easier package management, and osu-framework works great on Linux.

### Q: Can I use VS Code?
**A: YES!** VS Code is perfect. You do NOT need Visual Studio Community. Install these extensions:
- C# Dev Kit
- Python
- Pylance

### Q: Do I need Windows?
**A: NO!** Only for final Windows builds (can use CI). For iOS, you'll need macOS later (or CI runners).

---

## 🚀 Getting Started (3 Steps)

### 1. Run Setup Script
```fish
cd ~/github/BeatSight
./setup-linux.fish
```
**Wait**: 5-10 minutes (downloads .NET + Python + AI models)

### 2. Test Desktop App
```fish
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet run
```
**Expected**: Window opens with BeatSight menu

### 3. Test AI Pipeline
```fish
cd ~/github/BeatSight/ai-pipeline
source venv/bin/activate.fish
python -m pipeline.process --help
```

---

## 💻 Daily Commands

### Desktop Development
```fish
# Run app
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet run

# Build
dotnet build

# Hot reload (auto-restart on changes)
dotnet watch run
```

### AI Development
```fish
# Activate Python env (ALWAYS DO THIS FIRST!)
cd ~/github/BeatSight/ai-pipeline
source venv/bin/activate.fish

# Process audio
python -m pipeline.process --input song.mp3 --output map.bsm

# Run API server
python -m pipeline.server

# Deactivate when done
deactivate
```

### VS Code
```fish
# Open project
cd ~/github/BeatSight
code .
```

---

## 📁 Project Structure

```
~/github/BeatSight/
├── desktop/              ← C# app (dotnet run here)
│   ├── BeatSight.Game/   ← Game logic
│   └── BeatSight.Desktop/← Entry point
├── ai-pipeline/          ← Python AI (activate venv here)
│   ├── pipeline/         ← Main code
│   └── venv/            ← Python environment
├── docs/                 ← Documentation
├── SETUP_LINUX.md       ← This guide (detailed)
├── QUICKSTART.md        ← Fast start guide
└── OVERVIEW.md          ← Visual summary
```

---

## 🎮 What Works Right Now

✅ Desktop app skeleton (menu screen)  
✅ Beatmap format (.bsm files)  
✅ AI processing (Demucs + onset detection)  
✅ Audio file support (MP3, WAV, FLAC, etc.)  
✅ FastAPI server  
✅ Complete documentation  

---

## 🔧 Next to Build

🚧 Gameplay screen (falling notes)  
🚧 Input handling & scoring  
🚧 Beatmap editor  
🚧 AI model training  
🚧 Real-time microphone input  
🚧 Mobile apps  

---

## 🐛 Common Issues

### Desktop app crashes
```fish
# Check graphics
glxinfo | grep "OpenGL"

# Install/update drivers
sudo apt install mesa-utils
```

### Python imports fail
```fish
# Did you activate venv?
source ~/github/BeatSight/ai-pipeline/venv/bin/activate.fish

# Reinstall
pip install -r requirements.txt
```

### Demucs is slow
```fish
# Check for GPU
nvidia-smi

# Install CUDA PyTorch
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

---

## 📖 Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Project overview |
| `SETUP_LINUX.md` | Detailed Linux setup |
| `QUICKSTART.md` | Fast getting started |
| `OVERVIEW.md` | Visual project summary |
| `ROADMAP.md` | Development timeline |
| `docs/ARCHITECTURE.md` | Technical deep dive |
| `docs/BEATMAP_FORMAT.md` | .bsm file spec |

---

## 🎯 Your Next Steps

1. ✅ **Setup**: Run `./setup-linux.fish`
2. ✅ **Test**: Run desktop app + AI pipeline
3. ✅ **Explore**: Read `OVERVIEW.md`
4. 🚧 **Code**: Build gameplay screen (see `ROADMAP.md`)

---

## 💡 Pro Tips

- **Use fish aliases**: Add to `~/.config/fish/config.fish`
  ```fish
  alias bs-run='cd ~/github/BeatSight/desktop/BeatSight.Desktop && dotnet run'
  alias bs-ai='cd ~/github/BeatSight/ai-pipeline && source venv/bin/activate.fish'
  ```

- **VS Code tasks**: Press `Ctrl+Shift+B` to build

- **Git workflow**: 
  ```fish
  git checkout -b feature/gameplay
  # Make changes
  git commit -m "feat: add gameplay screen"
  ```

---

## 🎉 Summary

| Aspect | Your Choice | Status |
|--------|-------------|--------|
| OS | Ubuntu/Linux | ✅ Perfect! |
| IDE | VS Code | ✅ Perfect! |
| Shell | Fish | ✅ Supported! |
| Desktop | .NET + osu-framework | ✅ Cross-platform |
| AI | Python + PyTorch | ✅ Works great |
| License | MIT (open source) | ✅ Free forever |

**You have everything you need. Start coding!** 🚀

---

**Questions?** Check `SETUP_LINUX.md` for detailed help.

**Ready?** Run `./setup-linux.fish` and let's go! 🥁✨
