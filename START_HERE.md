# Start Here

These are the minimum steps to get productive in the BeatSight workspace. Skim this page, then follow the linked docs for deeper context.

## 1. TL;DR

- Launch the desktop client: `cd ~/github/BeatSight/desktop/BeatSight.Desktop && dotnet run`
- Review the live backlog in `docs/product/status.md` (updates happen here, not in this file)
- Use `docs/Guidebook.md` as the table of contents for orientation, onboarding, and archives

## 2. Run the Core Apps

### Desktop Client

```bash
cd ~/github/BeatSight/desktop/BeatSight.Desktop
dotnet run
```

- `dotnet watch run` is handy for UI iteration
- Builds expect .NET 8 (see `docs/Guidebook.md#prereqs` for setup notes)

### Backend API (optional while prototyping)

```bash
cd ~/github/BeatSight/backend
poetry install
poetry run uvicorn app.main:app --reload
```

See `backend/README.md` for routes and health checks if you need the service.

## 3. Documentation Map

- **Guidebook** → `docs/Guidebook.md` is the master index (orientation, engineering playbooks, archive pointers)
- **Current status / next steps** → `docs/product/status.md`
- **Roadmap** → `docs/product/roadmap.md`
- **Training SOP** → `docs/ml_training_runbook.md`
- **Recent archives** → `docs/archive/2025-11-02-phase12/` and `docs/archive/2025-11-orientation/`

If you update any of the above, keep cross-links consistent. The root `NEXT_STEPS.md` and `CURRENT_STATUS.md` files simply redirect to the live status doc.

## 4. Environment & Data Checklist

- Configure dataset paths before running training or export tools:

```bash
export BEATSIGHT_DATA_ROOT="/mnt/data/beatsight"
export BEATSIGHT_CACHE_ROOT="${BEATSIGHT_DATA_ROOT}/cache"
export BEATSIGHT_RUN_ROOT="${BEATSIGHT_DATA_ROOT}/runs"
```

- `ai-pipeline/training/tools/post_export_commands.sh` reads the variables above; set them in your shell profile if you run exports often
- Logs and large artifacts live in `data/` (see `docs/Guidebook.md#data` for naming conventions)

## 5. Active Workstreams (sync with status doc)

- **Storage migration:** move the production dataset to the new HDD mount; verify permissions so the training pipeline can stream directly
- **Probe evaluation:** follow the warm-up probe notes in `docs/ml_training_runbook.md` before kicking off long trainings
- **Desktop polishing:** see the “Critical Actions” section in `docs/product/status.md` for the UI backlog

Always record progress in `docs/product/status.md`; we archive completed milestones from there into `docs/product/roadmap.md`.

## 6. Useful Commands

```bash
# Solution-wide build (desktop + tests)
cd ~/github/BeatSight
dotnet build BeatSight.sln

# Run C# tests
dotnet test BeatSight.sln

# Lint backend Python
cd backend
poetry run ruff check
```

## 7. Need More Context?

- Check `docs/Guidebook.md#orientation` for the narrative walkthrough of the project
- For historical decisions, read `docs/product/roadmap.md` milestones and the archives referenced there
- If something seems missing, add an entry to `docs/product/status.md` and link or create the supporting doc so future readers land in the right place
