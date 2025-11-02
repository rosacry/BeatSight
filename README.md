# BeatSight 🥁

**Transform any song into an interactive drum learning experience**

BeatSight is an AI-powered rhythm learning application that automatically transcribes drum parts from any song into a Guitar Hero-style visual gameplay experience. Whether you're a beginner drummer tired of losing interest in songs from endless repetition, or an experienced player looking for a new way to learn, BeatSight bridges the gap between gaming and music education.

## 🎯 Core Concept

Inspired by the sight-reading skills developed in rhythm games like osu!, BeatSight helps drummers:
- Learn songs without burning out from repetitive listening
- Develop sight-reading abilities for drum notation
- Practice with visual feedback and real-time accuracy scoring
- Share and discover community-created beatmaps

## ✨ Features

### 🤖 AI-Powered Processing
- **Automatic Instrument Separation**: Isolates drums from any audio file
- **Intelligent Transcription**: Detects drum hits and identifies specific drum parts (kick, snare, hi-hat, crash, ride, china, toms, etc.)
- **Smart Mapping**: Converts audio into playable beatmaps with optimal note placement

### 🎮 Gameplay
- **Guitar Hero-Style Visualization**: Falling notes with customizable approach rate
- **Real-Time Feedback**: Microphone input detection with accuracy scoring (300/100/50)
- **Flexible Playback**: 
  - Toggle between full song or isolated drum track
  - Adjustable playback speed for practice
  - Metronome overlay with BPM sync
- **Scoring System**: osu!-inspired accuracy metrics and combo tracking

### 🎼 Beatmap Editor
- **Full Editor Mode**: Create or modify beatmaps manually
- **Visual Timeline**: Waveform display with precise note placement
- **Correction Tools**: Fix AI mistakes or customize existing maps
- **Sample Extraction**: Extract drum samples from favorite songs to build custom kits

### 🌐 Community Features
- **Beatmap Sharing**: Upload and download community-created maps
- **Open Format**: Human-readable `.bsm` (BeatSight Map) files
- **Search & Browse**: Discover maps by song, artist, difficulty, or rating
- **Quality Control**: Community ratings and feedback

### 🛠️ Advanced Features
- **Multi-format Support**: Process various audio file types (MP3, WAV, FLAC, OGG, etc.)
- **Drum Kit Detection**: Automatically identifies available drum components in recordings
- **Custom Kits**: Build personalized drum sample libraries
- **Distributed Training**: (Optional) Contribute computing power to improve AI models

## 🏗️ Architecture

### Desktop Application (Windows/macOS/Linux)
- Built on **osu-framework** for high-performance, cross-platform gameplay
- Native C# application with direct audio/graphics acceleration
- Full-featured beatmap editor and gameplay engine

### Mobile Apps (iOS/Android)
- Flutter-based applications for touch-optimized gameplay
- Beatmap playback and community browsing
- Shared file format with desktop version

### AI Processing Pipeline
- Python-based service using **Demucs** for source separation
- Custom transformer model for drum transcription
- Onset detection and drum part classification

### Backend Services
- RESTful API for beatmap storage and retrieval
- User accounts and authentication
- CDN for audio file distribution
- Donation processing

## 📁 Project Structure

```
beatsight/
├── desktop/              # osu-framework C# application
│   ├── BeatSight.Game/   # Core game logic
│   ├── BeatSight.Desktop/ # Desktop launcher
│   └── BeatSight.Resources/ # Assets and resources
├── mobile/               # Flutter mobile apps
│   ├── ios/
│   └── android/
├── ai-pipeline/          # Python AI processing
│   ├── separation/       # Demucs integration
│   ├── transcription/    # Drum transcription model
│   ├── classification/   # Drum part identification
│   └── training/         # Model training infrastructure
├── backend/              # API server
│   ├── api/              # REST endpoints
│   ├── database/         # Models and migrations
│   └── storage/          # File handling
├── shared/               # Shared resources
│   ├── formats/          # .bsm format specification
│   ├── protocols/        # API contracts
│   └── samples/          # Example beatmaps
├── tools/                # Development utilities
│   └── training-client/  # Distributed training app
└── docs/                 # Documentation
    ├── ARCHITECTURE.md
    ├── BEATMAP_FORMAT.md
    ├── API_REFERENCE.md
    └── CONTRIBUTING.md
```

## 🚀 Getting Started

### Prerequisites
- **.NET 8.0 SDK** (for desktop app)
- **Python 3.10+** (for AI pipeline)
- **Node.js 18+** (for backend)
- **Flutter 3.16+** (for mobile apps)

### Desktop Development
```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```

### AI Pipeline Setup
```bash
cd ai-pipeline
python -m venv venv
source venv/bin/activate  # or `venv/bin/activate.fish` for fish shell
pip install -r requirements.txt
python -m pipeline.server
```

### Backend Development
```bash
cd backend
npm install
npm run dev
```

## 🤝 Contributing

BeatSight is open-source and community-driven! Contributions are welcome in:
- AI model improvements
- Beatmap creation
- Code contributions
- Documentation
- Bug reports and feature requests

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

## 💖 Support the Project

BeatSight is completely free with no ads. If you'd like to support development and server costs, you can donate via:
- [Ko-fi](https://ko-fi.com/beatsight) _(placeholder)_
- [GitHub Sponsors](https://github.com/sponsors/beatsight) _(placeholder)_

**100% of donations go toward:**
- Server hosting and bandwidth
- AI model training compute
- Development tools and services

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- **osu!** and **ppy** for the incredible osu-framework
- **Meta AI** for Demucs source separation
- The rhythm game community for inspiration
- All contributors and supporters

## 📞 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/beatsight/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/beatsight/discussions)
- **Discord**: [Join our community](https://discord.gg/beatsight) _(placeholder)_

---

**Made with ❤️ by drummers, for drummers**
