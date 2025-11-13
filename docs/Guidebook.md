# BeatSight Guidebook

This guidebook is the navigation hub for every Markdown reference inside the repo. Use it to jump to the right track quickly; deeper logs and historical notes now live under `docs/archive/`.

## Orientation
- `README.md` – public project overview, pitch, and quickstart.
- `START_HERE.md` – condensed onboarding checklist that bounces to current status, roadmap, and runbooks.
- `personal_notes/` – private context dumps (formerly loose `.txt` files in the repo root).
- Historical elevator pitches now live under `docs/archive/2025-11-orientation/`.

## Product & Delivery
- `docs/product/status.md` – current blockers, active initiatives, and quick actions.
- `docs/product/roadmap.md` – phase summaries and near-term targets.
- Web pivot packet:
  - `docs/web_mvp_prd.md`
  - `docs/web_backend_architecture.md`
  - `docs/web_backend_schema.md`
  - `docs/web_compute_costs.md`
  - `docs/web_ux_flows.md`
  - `docs/web_mvp_task_breakdown.md`
- Historical notes & session logs live in `docs/archive/` (see links below).

## Engineering Systems
- Environment & tooling:
  - `SETUP_LINUX.md`
  - `docs/SETUP.md`
  - `SETTINGS_REFERENCE.md`
- Desktop (osu-framework) specifics: `docs/ARCHITECTURE.md`; Phase 1.2 feature inventory and editor fix logs are archived in `docs/archive/2025-11-02-phase12/`.
- AI pipeline:
  - `ai-pipeline/README.md`
  - `ai-pipeline/training/README.md`
  - `ai-pipeline/training/DATASET_READINESS_PLAN.md`
  - `docs/ml_training_runbook.md`
- Backend & services: `backend/README.md`, `docs/web_backend_architecture.md` (architecture), `docs/web_backend_schema.md` (data model).

## Domain Specs & Research
- Formats: `docs/BS_FILE_FORMAT.md`, `docs/BEATMAP_FORMAT.md`, `shared/formats/` specs.
- Live input QA: `docs/LIVE_INPUT_REGRESSION_CHECKLIST.md`.
- Training governance: `docs/ml_training_runbook.md`, `ai-pipeline/training/DATASET_READINESS_PLAN.md`, readiness reports under `ai-pipeline/training/reports/`.
- Experiment archives: see `wandb/` runs, `ai-pipeline/training/examples/`, and `ai-pipeline/training/tools/` for utilities referenced by the plan.

- Latest snapshots moved from the root:
  - `docs/archive/current_status_2025-11-12.md`
  - `docs/archive/next_steps_2025-11-12.md`
  - `docs/archive/roadmap_2025-11-12.md`
- Phase 1.2 bundle: feature inventory, celebration, session logs, bugfix notes, and editor fixes relocated to `docs/archive/2025-11-02-phase12/`.
- Orientation packets predating the current README are under `docs/archive/2025-11-orientation/`.
- Use the archive for historical context; create new dated copies when you roll forward major status or roadmap updates.

_Maintenance note: whenever you add a new Markdown context doc, register it here so future tasks stay discoverable._
