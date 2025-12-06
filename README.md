<!-- prettier-ignore -->
<div align="center">

<img src="assets/logo.png" alt="BeatSight Logo" width="120" />

# BeatSight

**See the music before you play it.**

[![CI/CD Pipeline](https://img.shields.io/github/actions/workflow/status/rosacry/BeatSight/ci-cd.yml?style=flat-square&label=CI/CD)](https://github.com/rosacry/BeatSight/actions)
[![Deploy](https://img.shields.io/github/actions/workflow/status/rosacry/BeatSight/deploy-production.yml?style=flat-square&label=Deploy)](https://github.com/rosacry/BeatSight/actions)
[![Backend Coverage](https://img.shields.io/badge/backend-84%25-brightgreen?style=flat-square)](https://codecov.io/gh/rosacry/BeatSight)
![.NET](https://img.shields.io/badge/.NET-8.0-512BD4?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6?style=flat-square)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Why BeatSight](#why-beatsight) • [Features](#features) • [Getting Started](#getting-started) • [Architecture](#architecture) • [Contributing](#contributing)

��� **Live at [beatsight.io](https://beatsight.io)** | ��� **[API Docs](https://api.beatsight.io/docs)**

</div>

---

## Why BeatSight?

Rhythm games like Guitar Hero, Rock Band, Dance Dance Revolution, and osu! all share one key mechanic: notes scroll toward a timing line *before* you need to hit them. This visual lookahead is what enables rapid skill acquisition—you see what's coming and your brain pre-plans the movement. But when drummers want to learn *real songs on real drums*, they're stuck memorizing by ear, rewinding the same 4-bar section dozens of times, or squinting at static sheet music that offers no timing guidance.

**This matters more than you might think.** Research on rhythm and motor learning demonstrates that visual anticipation dramatically accelerates motor skill acquisition. When you can *see* what's coming, your brain pre-plans the movement instead of reacting after the fact. Drummers have never had this advantage—until now.

BeatSight brings the rhythm game paradigm to drum practice:

- **Visual lookahead** — Notes scroll toward a timing line, giving you time to prepare each hit
- **AI transcription** — Drop in any song and get a playable beatmap in minutes, not hours of manual transcription  
- **Tempo control** — Slow sections down to 50% without pitch shift, then gradually speed up as you learn
- **Stem isolation** — Practice with just the drum track, or hear how your part fits the full mix

## Features

### AI-Powered Transcription
- **~96% validation accuracy** on drum classification using a production-trained ML model
- Technique detection: flams, ghost notes, rolls, accents, rimshots
- Velocity and dynamics analysis for expressive playback
- Automatic tempo and time signature detection

### Multiple Practice Views
- **2D Lane View** — DDR/StepMania-style vertical scrolling with color-coded drum components
- **3D Highway** — Guitar Hero-inspired perspective with depth and scanline effects
- **Manuscript View** — Traditional drum notation with a sweeping playhead highlighter

### Practice Tools
- Stem isolation (drums vs. full mix) via Demucs source separation
- Pitch-independent tempo adjustment (50%–200%)
- Section looping with visual loop markers
- Metronome overlay with configurable accents
- Progress tracking: favorites, tags, notes, and difficult section marking

### Production Status

| Service | URL | Status |
|---------|-----|--------|
| **Web App** | [beatsight.io](https://beatsight.io) | ✅ Live |
| **API** | [api.beatsight.io](https://api.beatsight.io/docs) | ✅ Live |
| **Desktop** | osu!-framework client | ✅ Available |
| **Mobile** | iOS/Android | ���️ Planned |

> [!NOTE]
> The AI transcription model runs on secure cloud infrastructure (Modal). Users access it through the desktop app or web interface with their account credits.

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| .NET SDK | 8.0+ | Desktop client |
| Python | 3.12+ | Backend services |
| Node.js | 20+ | Web frontend |
| PostgreSQL | 15+ | Database |
| Redis | 7+ | Caching |

> [!TIP]
> See [`docs/SETUP.md`](docs/SETUP.md) for detailed platform-specific installation guides.

### Desktop Client

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```

The desktop app connects to beatsight.io for AI transcription. Sign in with your account to use your credits.

<details>
<summary><strong>Backend API (for developers)</strong></summary>

```bash
cd backend
pip install -e ".[dev]"

# Start dependencies
docker compose up -d  # PostgreSQL + Redis

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `/docs`.

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

| Tier | Price | Monthly Quota | Best For |
|------|-------|---------------|----------|
| **Free** | $0 | 3 songs | Trying it out |
| **Pro** | $12/mo | 50 songs | Regular practice |
| **Credits** | $0.35/song | Pay-as-you-go | Occasional use |

## Architecture

```
BeatSight/
├── desktop/                  # osu-framework desktop client (C#/.NET 8)
│   ├── BeatSight.Desktop/    # Platform host & window management
│   ├── BeatSight.Game/       # Playback screens, editor, UI components
│   └── BeatSight.Tests/      # Unit tests
├── ai-pipeline/              # ML training & inference pipeline (Python)
│   ├── pipeline/             # Audio processing orchestration
│   ├── training/             # Model training scripts & configs
│   ├── transcription/        # Onset detection, drum classification
│   └── separation/           # Demucs source separation
├── backend/                  # FastAPI web services (Python 3.12)
│   └── app/                  # API routes, services, models
├── frontend/                 # React + TypeScript SPA
│   └── src/                  # Components, hooks, state management
├── docs/                     # All documentation
├── data/                     # Dataset storage (gitignored)
└── shared/                   # Format specs, shared assets
```

### Tech Stack

| Component | Stack | Tests |
|-----------|-------|-------|
| Desktop | osu-framework, .NET 8, OpenGL | 75 tests |
| Backend | FastAPI, SQLAlchemy, PostgreSQL, Redis | 2895 tests (84% cov) |
| Frontend | React 18, TypeScript, TailwindCSS, Vite | 283 tests |
| AI Pipeline | PyTorch, Demucs, librosa | 195 tests |

### Infrastructure

| Service | Provider |
|---------|----------|
| Frontend Hosting | Cloudflare Pages |
| Backend Hosting | Railway |
| Database | Railway PostgreSQL |
| Cache | Railway Redis |
| AI Compute | Modal (GPU) |
| Storage | S3-compatible |
| Payments | Stripe |
| DNS/CDN | Cloudflare |

### Beatmap Format

BeatSight uses `.bsm` (BeatSight Map), a JSON-based format:

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

All documentation lives in the [`docs/`](docs/) folder:

| Document | Description |
|----------|-------------|
| [`docs/START_HERE.md`](docs/START_HERE.md) | Quick orientation and launch commands |
| [`docs/SETUP.md`](docs/SETUP.md) | Platform-specific installation |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design deep-dive |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Contribution guidelines |
| [`docs/BEATMAP_FORMAT.md`](docs/BEATMAP_FORMAT.md) | `.bsm` file format spec |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | Backend API documentation |
| [`docs/ENGINEERING_ROADMAP.md`](docs/ENGINEERING_ROADMAP.md) | Development roadmap |

## Contributing

Contributions are welcome! Please read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) before submitting a PR.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `cd backend && pytest` and `cd frontend && npm test`
5. Submit a pull request

> [!IMPORTANT]
> The AI model training code in `ai-pipeline/training/` is provided for transparency but trained weights are proprietary.

## License

This project is licensed under the [MIT License](LICENSE).

## Support

- **Discord**: [Join our community](https://discord.gg/T57fDWcHDQ)
- **Issues**: [GitHub Issues](https://github.com/rosacry/BeatSight/issues)
- **Email**: [support@beatsight.io](mailto:support@beatsight.io)
