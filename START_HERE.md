# Start Here

These are the minimum steps to get productive in the BeatSight workspace. Skim this page, then follow the linked docs for deeper context.

## 1. TL;DR

- Launch the desktop client from your shell of choice:
	- **Windows (Git Bash):** `cd ~/OneDrive/Documents/github/BeatSight/desktop/BeatSight.Desktop && dotnet run`
	- **Linux/macOS:** `cd ~/github/BeatSight/desktop/BeatSight.Desktop && dotnet run`
- Review the live backlog in `docs/product/status.md` (updates happen here, not in this file)
- Use `docs/Guidebook.md` as the table of contents for orientation, onboarding, and archives
- Need a fresh environment? Follow `docs/SETUP.md` and the platform guides it links (`SETUP_WINDOWS.md`, `SETUP_LINUX.md`)

## 2. Run the Core Apps

### Desktop Client

Use the command pair that matches your platform:

- **Windows (Git Bash):**
	```bash
	cd ~/OneDrive/Documents/github/BeatSight/desktop/BeatSight.Desktop
	dotnet run
	```
- **Linux/macOS:**
	```bash
	cd ~/github/BeatSight/desktop/BeatSight.Desktop
	dotnet run
	```

- `dotnet watch run` is handy for UI iteration
- Builds expect .NET 8 (see `docs/Guidebook.md#prereqs` for setup notes)

### Backend API (optional while prototyping)

```bash
cd ~/OneDrive/Documents/github/BeatSight/backend
poetry install
poetry run uvicorn app.main:app --reload
```

See `backend/README.md` for routes and health checks if you need the service.

## 3. Documentation Map

- **Guidebook** → `docs/Guidebook.md` is the master index (orientation, engineering playbooks, archive pointers)
- **Current status / next steps** → `docs/product/status.md`
- **Implementation status** → `IMPLEMENTATION_STATUS.md` (comprehensive codebase analysis with all gaps and priorities)
- **Roadmap** → `docs/product/roadmap.md`
- **Training SOP** → `docs/ml_training_runbook.md`
- **Recent archives** → `docs/archive/2025-11-02-phase12/` and `docs/archive/2025-11-orientation/`

If you update any of the above, keep cross-links consistent. The root `NEXT_STEPS.md` and `CURRENT_STATUS.md` files simply redirect to the live status doc.

## 4. Environment & Data Checklist

- Configure dataset paths before running training or export tools. The quickest route is to source the helper hook from your shell:

```bash
cd ~/OneDrive/Documents/github/BeatSight
source ai-pipeline/training/tools/beatsight_env.sh
```

	- fish users: `source ai-pipeline/training/tools/beatsight_env.fish`

- Override any of the exported variables (`BEATSIGHT_DATA_ROOT`, `BEATSIGHT_DATASET_DIR`, `BEATSIGHT_CACHE_DIR`, etc.) before sourcing if you keep data on a different volume.
- `ai-pipeline/training/tools/post_export_commands.sh` and the training scripts consume these variables directly, so once the hook is sourced every command in the checklist runs against the same layout.
- Logs and large artifacts live in `data/` (see `docs/Guidebook.md#data` for naming conventions)

## 5. Active Workstreams (sync with status doc)

- **⭐ AI Training:** Run Path G (V5 Ultimate, modes 17a-17d) via `post_export_commands.sh` - this is the recommended default for production
- **Storage migration:** move the production dataset to the new HDD mount; verify permissions so the training pipeline can stream directly
- **Probe evaluation:** follow the warm-up probe notes in `docs/ml_training_runbook.md` before kicking off long trainings
- **Desktop polishing:** see the "Critical Actions" section in `docs/product/status.md` for the UI backlog

Always record progress in `docs/product/status.md`; we archive completed milestones from there into `docs/product/roadmap.md`.

## 6. Useful Commands

```bash
# Solution-wide build (desktop + tests)
cd ~/OneDrive/Documents/github/BeatSight   # adjust the root for your clone path
dotnet build BeatSight.sln

# Run C# tests
dotnet test BeatSight.sln

# Lint backend Python
cd backend
poetry run ruff check
```

### Local CI with `act` (run before every push!)

We use [`act`](https://github.com/nektos/act) to run the **actual GitHub Actions workflows** locally in Docker containers. This ensures 100% parity with CI.

**Prerequisites:**
- Docker Desktop running
- `act` CLI installed: `winget install nektos.act`

```bash
# List all available CI jobs
./scripts/act-local.sh

# Run specific jobs:
./scripts/act-local.sh backend-lint       # Ruff lint + format
./scripts/act-local.sh backend-test       # pytest with Postgres/Redis
./scripts/act-local.sh desktop-build      # .NET build + test
./scripts/act-local.sh ai-pipeline-test   # AI pipeline tests
./scripts/act-local.sh security-scan      # Trivy vulnerability scan
```

**⚠️ All checks must pass before pushing.** Since `act` runs the real `.github/workflows/*.yml` files, you get exact CI parity—no more "works locally but fails in CI" surprises.

## 7. Need More Context?

- Check `docs/Guidebook.md#orientation` for the narrative walkthrough of the project
- For historical decisions, read `docs/product/roadmap.md` milestones and the archives referenced there
- If something seems missing, add an entry to `docs/product/status.md` and link or create the supporting doc so future readers land in the right place
