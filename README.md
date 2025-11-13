dotnet restore
dotnet run
# BeatSight

Transforming drum practice into a sight-readable, data-aware workflow across desktop, AI services, and the web.

## Vision

BeatSight pairs an osu!-framework desktop client with a Python processing stack and FastAPI services to deliver AI-assisted drum visualisations, precise playback tooling, and community workflows. The project is engineered as a full application suite: gameplay and editing happen on the desktop, audio understanding flows through the AI pipeline, and service infrastructure prepares the path toward web sharing and verification.

## Subsystems

- **Desktop client (`desktop/`)** – C#/.NET 8 application with osu-framework UI, mapping pipeline integration, practice tooling, and playback UIs.
- **AI pipeline (`ai-pipeline/`)** – Python orchestration around Demucs separation, onset analysis, heuristic/ML drum classification, beatmap drafting, and dataset QA tooling.
- **Backend services (`backend/`)** – FastAPI scaffolding with SQLAlchemy models, async services, and job queue primitives for map generation, song metadata, and future review flows.
- **Data and training ops (`data/`, `ai-pipeline/training/`)** – Manifests, readiness gates, export scripts, and training presets governed by the ML runbook.
- **Documentation (`docs/`, root *.md)* – Living knowledge base covering setup, architecture, product planning, training SOPs, and archives.

## Current Capabilities

### Desktop application
- Drag-and-drop audio import pipeline that hands jobs to the AI generator and surfaces advanced options (sensitivity, quantisation grid, overrides).
- Generation UI with weighted progress, debug overlay hooks, detection confidence banners, and lane statistics.
- Playback screen supporting beatmap metadata review, stem/full-mix toggles, timeline visualisation, and configurable lane presets.
- Practice overlays (looping, metronome, playback speed) and settings surfaces driven by `BeatSightConfigManager` persist user preferences.
- Editor entry point scaffolding that opens generated drafts and will host deeper authoring workflows.

### AI processing & tooling
- Command line entry-point (`python -m pipeline.process`) orchestrating preprocessing, Demucs-based separation, onset detection/refinement, drum classification (ML or heuristic), and `.bsm` generation with debug payloads.
- Metadata detection and injection to populate beatmap headers when tags or fingerprint services succeed.
- Training toolchain (`ai-pipeline/training/`) covering dataset exporters, health checks, readiness automation, hard-negative mining, and classifier training scripts with W&B integration.
- Dataset readiness gates (health reports, QC scripts, post-export checklist) tracked in `docs/ml_training_runbook.md` and supporting environment variables (`BEATSIGHT_DATA_ROOT`, etc.).

### Backend & services
- FastAPI project bootstrapped with Poetry, structured logging, and environment-driven configuration (`backend/app/config.py`).
- Domain models for songs, maps, AI jobs, and supporting tables aligned with `docs/web_backend_schema.md`.
- REST endpoints for health, song CRUD, and AI job enqueue/list flows; service layer abstractions isolate SQLAlchemy operations.
- Ready for asynchronous workers/queue integration to orchestrate pipeline jobs once infrastructure is wired up.

### Data management & QA
- `data/` hierarchy captures archival datasets, raw source mirrors, and production exports with gitignore rules that keep huge assets out of version control.
- Readiness and roadmap documents (`docs/product/status.md`, `docs/product/roadmap.md`) track operational blockers, dataset migration, and GPU training milestones.
- `ai-pipeline/training/reports/` retains health baselines; tooling scripts enforce replacement of synthetic baselines with production metrics.

### Documentation & governance
- `START_HERE.md` and `docs/Guidebook.md` orient contributors and link to detailed archives.
- Domain specifications (`docs/BEATMAP_FORMAT.md`, `docs/BS_FILE_FORMAT.md`, `shared/formats/`) define the BeatSight map schema.
- Product strategy, backend architecture, UX flows, and compute cost analyses live under `docs/` for quick reference and cross-team alignment.

## Repository Layout

```
BeatSight/
├── desktop/
│   ├── BeatSight.Desktop/        # platform host
│   ├── BeatSight.Game/           # game, mapping, playback, editor
│   └── BeatSight.Tests/          # detection stats + timebase tests
├── ai-pipeline/
│   ├── pipeline/                 # CLI/server orchestration modules
│   ├── training/                 # dataset, readiness, training scripts
│   └── models/                   # drop-in classifier weights
├── backend/
│   └── app/                      # FastAPI app, routers, services, models
├── data/                         # local dataset mirrors (ignored in git)
├── docs/                         # architecture, roadmap, archives
├── shared/                       # format specs, shared assets
├── personal_notes/               # context dumps retained for planning
└── README.md, START_HERE.md, etc.
```

## Getting Started

### Prerequisites
- **.NET 8 SDK** for the desktop solution (`BeatSight.sln`).
- **Python 3.10+** with virtualenv support for the AI pipeline and training tools.
- **Poetry 1.7+** (or `pipx install poetry`) for the backend service.
- **FFmpeg + Demucs model cache** for source separation (see `SETUP_LINUX.md`).
- Optional: CUDA-enabled GPU for accelerated separation and training.

### Desktop client
```bash
cd desktop/BeatSight.Desktop
dotnet restore
dotnet run
```
Use `dotnet watch run` for rapid UI iteration. The client stores configuration under the host storage path; see `SETTINGS_REFERENCE.md` for defaults.

### AI pipeline
```bash
cd ai-pipeline
python -m venv venv
source venv/bin/activate  # On Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pipeline.process --input path/to/song.mp3 --output draft.bsm
```
Set `BEATSIGHT_USE_ML_CLASSIFIER=1` and drop model weights into `ai-pipeline/models/` to enable ML inference. Run `python -m pipeline.server` for the FastAPI wrapper.

### Backend service
```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
```
Environment variables live in `backend/.env.example`. The service exposes health checks at `/health/live` and API routes under `/api/v1`.

## Workflow & Documentation
- Start with `START_HERE.md` for active tasks and launch commands.
- Use `docs/Guidebook.md` as the index for subsystem docs, archives, and SOPs.
- Operational status and immediate next actions are captured in `docs/product/status.md`; roadmap targets reside in `docs/product/roadmap.md`.
- Training guardrails and exporter instructions are maintained in `docs/ml_training_runbook.md` and `ai-pipeline/training/README.md`.

## Contributing
- Review `docs/CONTRIBUTING.md` for coding standards, PR expectations, and documentation etiquette.
- Prefer adding context to the Guidebook when introducing new Markdown references.
- Keep dataset artifacts out of git (see `.gitignore`); commit manifests, configs, and reports instead.

## License

Released under the [MIT License](LICENSE). Please attribute and respect third-party assets referenced in the documentation.

## Support & Contact

- Issues & feature requests: open tickets in this repository.
- Long-form discussion and planning: use `docs/product/status.md` or linked discussion threads.
- For roadmap alignment or architectural decisions, start with the docs under `docs/` and capture outcomes there for future contributors.
