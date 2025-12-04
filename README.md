<!-- prettier-ignore -->
<div align="center">

# 🥁 BeatSight

**See the music before you play it.**

[![CI](https://img.shields.io/github/actions/workflow/status/rosacry/BeatSight/ci.yml?style=flat-square&label=CI)](https://github.com/rosacry/BeatSight/actions)
[![Backend Coverage](https://img.shields.io/badge/backend-84%25-brightgreen?style=flat-square)](https://codecov.io/gh/rosacry/BeatSight)
[![AI Pipeline Coverage](https://img.shields.io/badge/ai--pipeline-21%25-yellow?style=flat-square)](https://codecov.io/gh/rosacry/BeatSight)
![.NET](https://img.shields.io/badge/.NET-8.0-512BD4?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Why BeatSight](#why-beatsight) • [Features](#features) • [Getting Started](#getting-started) • [Architecture](#architecture) • [Contributing](#contributing)

**🌐 [beatsight.io](https://beatsight.io)** *(coming soon)*

</div>

---

## Why BeatSight?

Rhythm games like Guitar Hero, Rock Band, Dance Dance Revolution, and osu! all share one key mechanic: notes scroll toward a timing line *before* you need to hit them. This visual lookahead is what enables rapid skill acquisition—you see what's coming and your brain pre-plans the movement. But when drummers want to learn *real songs on real drums*, they're stuck memorizing by ear, rewinding the same 4-bar section dozens of times, or squinting at static sheet music that offers no timing guidance.

**This matters more than you might think.** Research on rhythm and motor learning ([Rhythm and Music-Based Interventions in Motor Rehabilitation](https://www.frontiersin.org/articles/10.3389/fnhum.2021.789467/full)) demonstrates that visual anticipation dramatically accelerates motor skill acquisition. When you can *see* what's coming, your brain pre-plans the movement instead of reacting after the fact. Drummers have never had this advantage—until now.

BeatSight brings the rhythm game paradigm to drum practice:

- **Visual lookahead** — Notes scroll toward a timing line, giving you time to prepare each hit
- **AI transcription** — Drop in any song and get a playable beatmap in minutes, not hours of manual transcription  
- **Tempo control** — Slow sections down to 50% without pitch shift, then gradually speed up as you learn
- **Stem isolation** — Practice with just the drum track, or hear how your part fits the full mix

The goal isn't gamification for its own sake—it's giving drummers the same visual-motor advantage that rhythm games have proven works, but applied to learning *actual songs* on *real drums*.

## Features

### AI-Powered Transcription
- **~96% validation accuracy** on drum classification using a production-trained ML model
- Technique detection: flams, ghost notes, rolls, accents, rimshots
- Velocity and dynamics analysis for expressive playback
- Automatic tempo and time signature detection

### Multiple Practice Views
- **2D Lane View** — DDR/StepMania-style vertical scrolling with color-coded drum components
- **3D Highway** — Guitar Hero-inspired perspective with depth and scanline effects
- **Manuscript View** — Traditional drum notation with a **sweeping playhead highlighter** that glides left-to-right across the staff, its leading edge marking exactly when each note should be played

### Practice Tools
- Stem isolation (drums vs. full mix) via Demucs source separation
- Pitch-independent tempo adjustment (50%–200%)
- Section looping with visual loop markers
- Metronome overlay with configurable accents
- Progress tracking: favorites, tags, notes, and difficult section marking

### Platforms

| Platform | Description | Status |
|----------|-------------|--------|
| **Desktop** | Full-featured practice environment built on osu!-framework | ✅ Available |
| **Web** | Library management, uploads, AI job tracking at [beatsight.io](https://beatsight.io) | 🚧 In development |
| **Mobile** | Flutter-based iOS/Android clients | 📋 Planned |

> [!NOTE]
> The AI transcription model runs on secure cloud infrastructure (Modal). Users access it through the desktop app or web interface with their account credits—the model is not distributed for local execution.

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| .NET SDK | 8.0+ | Desktop client |
| Python | 3.10+ | Backend services |
| Poetry | 1.7+ | Backend dependencies |
| Node.js | 18+ | Web frontend |
| FFmpeg | Latest | Audio processing |

> [!TIP]
> See [`docs/SETUP.md`](docs/SETUP.md) for detailed platform-specific installation guides (Windows, macOS, Linux).

### Desktop Client

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```

The desktop app connects to beatsight.io for AI transcription. Sign in with your account to use your credits or free tier quota.

<details>
<summary><strong>Backend API (for developers)</strong></summary>

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Health check: `GET /health/live`

</details>

<details>
<summary><strong>Web Frontend (for developers)</strong></summary>

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` with hot module replacement.

</details>

## Pricing

BeatSight uses a simple 2-tier model with optional credit packs:

| Tier | Price | Monthly Quota | Best For |
|------|-------|---------------|----------|
| **Free** | $0 | 3 songs | Trying it out |
| **Pro** | $12/mo | 50 songs | Regular practice |
| **Credits** | $0.35/song | Pay-as-you-go | Occasional use |

Credits work for everyone—buy a pack if you just need a few extra transcriptions without committing to Pro.

## Architecture

```
BeatSight/
├── desktop/              # osu-framework desktop client (C#/.NET 8)
│   ├── BeatSight.Desktop/    # Platform host & window management
│   ├── BeatSight.Game/       # Playback screens, editor, UI components
│   └── BeatSight.Tests/      # Unit tests (75 tests)
├── ai-pipeline/          # ML training & inference pipeline (Python)
│   ├── pipeline/             # Audio processing orchestration
│   ├── training/             # Model training scripts & configs
│   ├── transcription/        # Onset detection, drum classification
│   └── separation/           # Demucs source separation
├── backend/              # FastAPI web services (Python)
│   └── app/                  # API routes, services, models (1147 tests, 84% coverage)
├── frontend/             # React + TypeScript SPA (223 tests)
│   └── src/                  # Components, hooks, state management
├── data/                 # Dataset storage (gitignored)
├── docs/                 # Architecture, guides, specifications
└── shared/               # Format specs, shared assets
```

### Key Technologies

| Component | Stack | Coverage |
|-----------|-------|----------|
| Desktop | osu-framework, .NET 8, OpenGL | 75 tests |
| Backend | FastAPI, SQLAlchemy, PostgreSQL, Redis | 84% |
| Frontend | React 18, TypeScript, TailwindCSS, Vite | 223 tests |
| AI Pipeline | PyTorch, Demucs, librosa | 21%* |
| Infrastructure | Modal (GPU), S3, Stripe | — |

*AI pipeline coverage is lower because full model integration tests require the trained production model, which is still in active training.

### Beatmap Format

BeatSight uses `.bsm` (BeatSight Map), a JSON-based format designed for version control and human readability:

```json
{
  "version": "1.0.0",
  "metadata": { "title": "Song Name", "artist": "Artist", "difficulty": 7.5 },
  "timing": { "bpm": 120.0, "offset": 0, "timeSignature": "4/4" },
  "hitObjects": [
    { "time": 1000, "component": "kick", "velocity": 0.85 },
    { "time": 1500, "component": "snare", "velocity": 0.92, "articulation": "ghost" }
  ]
}
```

See [`docs/BEATMAP_FORMAT.md`](docs/BEATMAP_FORMAT.md) for the full specification.

## Documentation

| Document | Description |
|----------|-------------|
| [`START_HERE.md`](START_HERE.md) | Quick orientation and launch commands |
| [`docs/SETUP.md`](docs/SETUP.md) | Platform-specific installation |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design deep-dive |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Contribution guidelines |
| [`docs/BEATMAP_FORMAT.md`](docs/BEATMAP_FORMAT.md) | `.bsm` file format spec |

## Contributing

Contributions are welcome! Please read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) before submitting a PR.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run CI locally: `dotnet test BeatSight.sln` and `cd backend && poetry run pytest`
5. Submit a pull request

> [!IMPORTANT]
> The AI model and training code in `ai-pipeline/training/` is provided for transparency but the trained weights are proprietary. Contributions to the training pipeline are welcome; model weights are not redistributed.

## License

This project is licensed under the [MIT License](LICENSE).

## Support

- **Issues**: [GitHub Issues](https://github.com/rosacry/BeatSight/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rosacry/BeatSight/discussions)
