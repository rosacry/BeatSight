# Ingestion & Readiness Schedule — 8 Nov 2025

This playbook captures the remaining dataset ingestion work now that the production crash dual-label manifest is stable.

## 1. Cambridge Multitrack Collection

**Preflight**
- [ ] Confirm licensing notes in `training/data/licenses/cambridge.md` and log any downstream usage constraints.
- [ ] Generate missing SHA256 manifests under `data/archives/checksums/cambridge.sha256` (include both primary `data/raw/cambridge` and external drive roots).
- [ ] Run a dry inventory:
  ```bash
  python ai-pipeline/training/tools/ingest_cambridge.py --allow-empty --output ai-pipeline/training/data/manifests/cambridge_sessions_dryrun.jsonl
  ```
  Review counts, storage tiers, and missing audio warnings.

**Ingestion Pass**
- [ ] Extend `ingest_cambridge.py` (or add a companion converter) to emit `cambridge_events.jsonl` with technique metadata aligned to `configs/technique_taxonomy.json`.
- [ ] Record provenance rows in `training/data/provenance/cambridge_provenance.jsonl` (session id, storage tier, source files, ingest commit).
- [ ] Publish inventory plus events:
  ```bash
  python ai-pipeline/training/tools/ingest_cambridge.py --output ai-pipeline/training/data/manifests/cambridge_sessions.jsonl
  # TODO: run converter once implemented
  ```

**Readiness & Weights**
- [ ] `python ai-pipeline/training/dataset_health.py --events ai-pipeline/training/data/manifests/cambridge_events.jsonl --html-output ai-pipeline/training/reports/health/cambridge_20251108.html` (add required gates/techniques as needed).
- [ ] Regenerate sampling weights (likely per `session_id`) and publish to `training/reports/sampling/cambridge_weights_20251108.json`.
- [ ] Update documentation (`DATASET_READINESS_PLAN.md`, `reports/health/2025-11-08-health-summary.md`) with Cambridge metrics and attach diff artifacts.

## 2. MUSDB Cross-Validation (post-Cambridge)

- [ ] Re-run `training/tools/ingest_musdb.py` to align manifests with any Cambridge-specific taxonomy additions.
- [ ] Produce refreshed health report `training/reports/health/musdb_hq_20251108.json` and diff it against the existing 2025-11-07 baseline.
- [ ] Compare class/technique deltas between Cambridge and MUSDB to sanity-check cymbal/aux coverage before blending datasets.

## 3. E-GMD Ingestion (after MUSDB)

**Preparation**
- [ ] Verify data availability under `data/raw/egmd` and confirm licensing in `training/data/licenses/egmd.md`.
- [ ] Ensure `mido` and other dependencies exist in the environment (see `requirements.txt`).

**Execution**
- [ ] Run the MIDI ingestion pipeline:
  ```bash
  python ai-pipeline/training/tools/ingest_egmd.py \
    --output ai-pipeline/training/data/manifests/egmd_events.jsonl \
    --provenance ai-pipeline/training/data/provenance/egmd_provenance.jsonl
  ```
- [ ] Validate taxonomy alignment: confirm inferred techniques appear in `configs/technique_taxonomy.json`; patch taxonomy if new gestures surface.
- [ ] Generate readiness report `training/reports/health/egmd_20251108.json` and HTML summary.
- [ ] Decide whether to create a standalone sampling profile or merge select sessions into the production combined manifest.

## 4. Post-Ingestion Consolidation

- [ ] Re-run crash dual-label mapping if Cambridge or E-GMD introduce new crash variants before merging into production.
- [ ] Update `training/reports/health/2025-11-08-health-summary.md` (or successor) with ingestion outcomes and link to new diff artifacts.
- [ ] Consider a fresh combined health gate once Cambridge/E-GMD join (`prod_combined_events.jsonl` → `prod_combined_health_2025XXXX.json`).
- [ ] Stage and commit manifests, provenance, health reports, sampling weights, and documentation together (include `reports/sampling/prod_combined_weights.json` + `training/sampling/weights_prod_combined_20251108.json`).
