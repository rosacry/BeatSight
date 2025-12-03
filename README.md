<!-- prettier-ignore -->
<div align="center">

# 🥁 BeatSight

**AI-powered drum transcription and practice environment**

[![CI](https://img.shields.io/github/actions/workflow/status/rosacry/BeatSight/ci.yml?style=flat-square&label=CI)](https://github.com/rosacry/BeatSight/actions)
[![codecov](https://img.shields.io/codecov/c/gh/rosacry/BeatSight?style=flat-square)](https://codecov.io/gh/rosacry/BeatSight)
![.NET](https://img.shields.io/badge/.NET-8.0-512BD4?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Features](#features) • [Getting Started](#getting-started) • [Usage](#usage) • [Architecture](#architecture) • [Contributing](#contributing)

</div>

---

BeatSight transforms any song into a visual, scrolling drum score that drummers can follow in real time. The AI pipeline automatically transcribes drum performances, detects techniques (flams, ghost notes, rolls), and generates practice-ready beatmaps. No scoring or input latency to chase—just accurate playback surfaces tuned for deliberate practice.

## Features

- **AI-Powered Transcription** — Automatic drum detection using a trained ML classifier with ~96% accuracy, technique recognition (flams, rolls, ghost notes, accents), and velocity/dynamics analysis
- **Multiple View Modes** — 2D lane view (StepMania-style), 3D highway (Guitar Hero-inspired), and manuscript notation for traditional drummers
- **Practice-Focused** — Stem isolation (drums vs. full mix), tempo adjustment without pitch shift, section looping, and metronome overlay
- **Cross-Platform Desktop** — Built on the osu!-framework with OpenGL rendering, runs on Windows, macOS, and Linux
- **Web Interface** — React + TypeScript SPA for library management, upload, and AI job tracking
- **Extensible Format** — Human-readable `.bsm` (BeatSight Map) JSON format, version-control friendly

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| .NET SDK | 8.0+ | Desktop client |
| Python | 3.10+ | AI pipeline |
| Poetry | 1.7+ | Backend dependencies |
| Node.js | 18+ | Web frontend |
| FFmpeg | Latest | Audio processing |

> [!TIP]
> See [`docs/SETUP.md`](docs/SETUP.md) for detailed platform-specific installation guides.

### Quick Start

<details open>
<summary><strong>Desktop Client</strong></summary>

```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```

Use `dotnet watch run` for hot-reload during development.

</details>

<details>
<summary><strong>AI Pipeline</strong></summary>

```bash
cd ai-pipeline
python -m venv .venv
source .venv/bin/activate  # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt

# Process a song
python -m pipeline.process --input song.mp3 --output beatmap.bsm
```

</details>

<details>
<summary><strong>Backend API</strong></summary>

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```

API available at `http://localhost:8000`. Health check: `GET /health/live`

</details>

<details>
<summary><strong>Web Frontend</strong></summary>

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` with hot module replacement.

</details>

## Usage

### Generate a Beatmap

```bash
cd ai-pipeline
python -m pipeline.process --input path/to/song.mp3 --output output.bsm
```

Enable the ML classifier for better accuracy:

```bash
python -m pipeline.process --input song.mp3 --output output.bsm \
    --ml-model models/best_drum_classifier.pth
```

### Desktop Application

1. Launch the desktop client
2. Drag and drop an audio file to start generation
3. Configure sensitivity, quantization, and lane presets in the generation UI
4. Practice with the playback screen: scrub the timeline, toggle stems, adjust speed

### Logging Controls

```bash
dotnet run -- --log-level debug    # debug|verbose|important|error
dotnet run -- --quiet              # minimal output
dotnet run -- --raw-framework-logs # show all framework messages
```

## Architecture

```
BeatSight/
├── desktop/              # osu-framework desktop client (C#/.NET 8)
│   ├── BeatSight.Desktop/    # Platform host
│   ├── BeatSight.Game/       # UI, playback, editor
│   └── BeatSight.Tests/      # Unit tests
├── ai-pipeline/          # ML transcription pipeline (Python)
│   ├── pipeline/             # CLI and server orchestration
│   ├── training/             # Dataset tools, training scripts
│   ├── transcription/        # Onset detection, drum classification
│   └── separation/           # Demucs integration
├── backend/              # FastAPI web services (Python)
│   └── app/                  # Routers, models, services
├── frontend/             # React + TypeScript SPA
│   └── src/                  # Components, hooks, state
├── data/                 # Dataset storage (gitignored)
├── docs/                 # Architecture, guides, specifications
└── shared/               # Format specs, shared assets
```

### Key Components

| Component | Technology | Description |
|-----------|------------|-------------|
| Desktop Client | osu-framework, .NET 8 | Visual playback with 2D/3D/manuscript views |
| AI Pipeline | Python, PyTorch, Demucs | Source separation and drum transcription |
| Backend | FastAPI, SQLAlchemy, PostgreSQL | REST API, job orchestration, user management |
| Frontend | React, TypeScript, TailwindCSS | Web UI for library and job management |

### Beatmap Format

BeatSight uses `.bsm` (BeatSight Map), a JSON-based format:

```json
{
  "version": "1.0.0",
  "metadata": { "title": "Song Name", "artist": "Artist", "difficulty": 7.5 },
  "timing": { "bpm": 120.0, "offset": 0, "timeSignature": "4/4" },
  "hitObjects": [
    { "time": 1000, "component": "kick", "velocity": 0.85 },
    { "time": 1500, "component": "snare", "velocity": 0.92 }
  ]
}
```

See [`docs/BEATMAP_FORMAT.md`](docs/BEATMAP_FORMAT.md) for the full specification.

## Documentation

| Document | Description |
|----------|-------------|
| [`START_HERE.md`](START_HERE.md) | Quick orientation and launch commands |
| [`docs/SETUP.md`](docs/SETUP.md) | Platform-specific installation guides |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and component details |
| [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) | Contribution guidelines |
| [`docs/BEATMAP_FORMAT.md`](docs/BEATMAP_FORMAT.md) | `.bsm` file format specification |
| [`docs/ml_training_runbook.md`](docs/ml_training_runbook.md) | ML training procedures |

## Contributing

Contributions are welcome! Please read [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) before submitting a PR.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run CI locally: `dotnet test BeatSight.sln` and `cd backend && poetry run pytest`
5. Submit a pull request

## License

This project is licensed under the [MIT License](LICENSE).

## Support

- **Issues**: [GitHub Issues](https://github.com/rosacry/BeatSight/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rosacry/BeatSight/discussions)
