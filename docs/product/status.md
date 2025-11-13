# BeatSight Status (November 13, 2025)

## Snapshot
- Desktop reference build: ✅ shipping-quality gameplay, editor skeleton, and live-input calibration remain green.
- AI pipeline: 🟠 dual-crash relabel complete; GPU retrain still pending while we wait for the replacement hard drive and repatriate datasets/checkpoints to `C:`.
- Web pivot: 🟡 planning artifacts published (PRD, schema, UX, costs); backend FastAPI scaffold alive but workstreams not yet staffed.
- Documentation: 🟢 consolidated under `docs/Guidebook.md`; historical logs preserved in `docs/archive/`.

## Critical Actions
1. **Hardware unblock** – wait for the replacement HDD (due today), then migrate `prod_combined_profile_run`, `feature_cache`, checkpoints, W&B offline runs, and any other heavyweight assets from WSL back to `C:`.
2. **Centralise data paths** – once the target layout is confirmed (e.g., `C:\BeatSightData\...`), introduce `BEATSIGHT_DATA_ROOT` across exporters, training scripts, and helper tooling so Windows/WSL moves stay painless.
3. **Script refresh** – after the hook exists, rewire `ai-pipeline/training/tools/post_export_commands.sh` (and related helpers) to consume the new variables instead of hard-coded `/home/chrig` paths; keep CLI overrides for ad-hoc usage.
4. **Dataset export (runbook step 4)** – execute `build_training_dataset.py` for `prod_combined_events.jsonl`, run the checklist, and log outputs per `docs/ml_training_runbook.md`.
5. **Warm-up probe (runbook step 5a)** – run the cached probe, then evaluate it immediately using the criteria in the runbook (per-class recall >0.25, confusion shrinkage, W&B F1 trend, loss curve behaviour, misclassified audit).
6. **Long run gate** – only launch step 5c after the probe passes the checks; monitor W&B confusion matrices during the long run and re-evaluate with `--fraction 0.3` before promoting.
7. **Web MVP staffing** – pick a kick-off focus (queue infrastructure, fingerprint service, or UX shell) and translate `docs/web_mvp_task_breakdown.md` into issues.

## Active Initiatives
- **AI Readiness:** Cambridge ingest restored, weights refreshed, all gates green; awaiting drive delivery, data migration, and the `BEATSIGHT_DATA_ROOT` refactor before exporter + retrain resume.
- **Web MVP Planning:** Architecture, schema, UX, and cost models are ready. Needs engineering tickets and service spikes.
- **Practice Mode Polish:** Stage 0.2 hygiene landed; waveform view, blur shader, and hit-lighting are the next desktop polish tasks.

## Reference Map
- Deep status log (Nov 2025): [`docs/archive/current_status_2025-11-12.md`](../archive/current_status_2025-11-12.md)
- Action backlog & option matrix: [`docs/archive/next_steps_2025-11-12.md`](../archive/next_steps_2025-11-12.md)
- Roadmap detail (pre-restructure): [`docs/archive/roadmap_2025-11-12.md`](../archive/roadmap_2025-11-12.md)
- Live input regression checklist: [`docs/LIVE_INPUT_REGRESSION_CHECKLIST.md`](../LIVE_INPUT_REGRESSION_CHECKLIST.md)
- ML training SOP: [`docs/ml_training_runbook.md`](../ml_training_runbook.md)

_Update cadence: refresh this summary when a blocker clears or a focus area changes; archive the older snapshot under `docs/archive/` when you roll a new dated entry._
