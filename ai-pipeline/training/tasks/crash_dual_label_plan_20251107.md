# Crash Dual-Layer Annotation Plan — 7 Nov 2025

## Goal
Introduce explicit `crash2` (and future `crash3+`) component labels so multi-cymbal kits expose individual crash timbres to downstream models and sampling profiles. This replaces the temporary reliance on the `multi_cymbal_same_class` technique tag and allows class-balanced training, gating, and evaluation for distinct crash voices.

## Scope
- Source corpora: Slakh2100, Groove MIDI (rendered stems), ENST-Drums, Telefunken sessions, SignatureSounds one-shots.
- Label focus: events whose `components` currently contain only `crash` but whose metadata/techniques indicate more than one active crash cymbal in the kit.
- Deliverables: updated manifests, taxonomy note, provenance diffs, regression tests, and re-enabled readiness gate (`crash2` min-count + presence).

## Progress — 7 Nov 2025
- Implemented metadata-driven mapping via `training/tools/crash_variant_clustering.py`, yielding 16,258 `crash2` assignments archived in `training/reports/health/crash_dual_label_mapping_20251107.json`.
- Promoted the relabelled manifest (`training/data/manifests/prod_combined_events.jsonl`) using the enhanced `alias_events.py` pipeline; preserved the prior baseline as `prod_combined_events_pre_crashdual_20251107.jsonl`.
- Restored production readiness gates (`health_min_counts_prod.json`, `health_required_labels_prod.txt`) and published the passing report `training/reports/health/prod_combined_health_20251107_crash_dual.json` alongside diff artifact `training/reports/health/diffs/prod_combined_health_delta_crash_dual_20251107.json`.
- Added unit coverage (`tests/test_crash_dual_label.py`) verifying crash mapping ingestion and relabel application.
- Captured crash event descriptors with the new `training/tools/extract_crash_embeddings.py` CLI, creating per-event spectral summaries ahead of the clustering upgrade.
- Enabled centroid-gap spectral clustering fallback inside `training/tools/crash_variant_clustering.py`, with regression coverage to validate the crash2 assignments.

## Pipeline Overview
1. **Candidate Detection**
   - Use existing `multi_cymbal_same_class` technique tags plus per-session kit metadata to flag sessions with >=2 crash cymbals.
   - Inspect audio metadata (when available) for manufacturer/diameter cues; fallback to per-event spectral clustering.

2. **Spectral Clustering & Assignment**
   - Extract log-mel spectra + spectral centroid/bandwidth from crash events.
   - Cluster crash hits per session with Gaussian Mixture Models (GMM, k=2..3) or agglomerative clustering seeded by frequency peaks.
   - Label clusters deterministically by sorted centroid (e.g., `crash_low`, `crash_high`). Map `crash_low -> crash`, `crash_high -> crash2` for backwards compatibility. Support optional `crash3` when clusters >2.
   - Confidence fallback: when clustering confidence < configurable threshold (e.g., silhouette score <0.2), keep legacy single `crash` label and log for manual review.

3. **Metadata-Aware Overrides**
   - Telefunken/SignatureSounds provide per-mic/per-cymbal notes. Parse ingest provenance (YAML/CSV) to assign explicit cymbal IDs where present, overriding spectral inference.
   - Allow ingest overrides via `training/tools/ingest_*` CLI flags (`--cymbal-map path/to/map.json`).

4. **Manifest Rewriting**
   - Implement `training/tools/alias_events.py --add-crash-variants` to read manifests and duplicate crash components into `crash`/`crash2` based on cluster assignment, updating `components`, `techniques`, and `provenance`.
   - Record provenance entries: `annotation_stage: crash_dual_label`, `method: spectral_cluster|metadata_override`, `confidence` value.

5. **Validation & Gating**
   - Extend `dataset_health.py` to surface new labels (`crash2`, optional `crash3`) in per-class counts and allow gating via `--min-counts-json`.
   - Add regression tests covering cluster assignment + provenance injection.
   - Re-enable readiness gate: restore `crash2` entries in `health_required_labels_prod.txt` and `health_min_counts_prod.json` once manifests refreshed.

6. **Sampling & Training Integration**
   - Update `sampling_profiles.json` to include min/max weights for `crash2` once counts verified.
   - Adjust model training configs to treat `crash` and `crash2` as distinct outputs; add evaluation metrics for each.

## Task Breakdown
| Task | Owner | Notes |
| --- | --- | --- |
| Extract crash feature embeddings per session | Pipeline | 🚧 `extract_crash_embeddings.py` generates per-event spectral stats; pending batch run over full audio corpus and integration with clustering step. |
| Build clustering module (`training/tools/crash_variant_clustering.py`) | Pipeline | ✅ Metadata heuristic pass in place (16,258 assignments on 2025-11-07); centroid-gap spectral fallback now wired via embeddings export (threshold tuning pending full-scale run). |
| Integrate metadata overrides from Telefunken/SignatureSounds ingest | Data | Parse existing provenance, fallback to manual mapping tables |
| Implement manifest mutation CLI (`alias_events.py --add-crash-variants`) | Pipeline | ✅ Live; applies crash mapping + annotation history tagging. |
| Extend dataset health & tests for `crash2` gating | QA | ✅ Counts surfaced in `dataset_health.py`; coverage tracked via new unit tests. |
| Regenerate manifests & reports, re-enable gates | Pipeline | ✅ `prod_combined_events.jsonl` rewritten, health report + diff refreshed 2025-11-07. |
| Update documentation (Readiness Plan, Technique Gap Plan, Sampling Plan) | Docs | In progress — readiness plan + technique gap updated; sampling plan refresh pending post-training. |

## Risks & Mitigations
- **False split of single crash**: Use conservative confidence thresholds; keep manual queue for low-confidence sessions.
- **Metadata inconsistency**: Validate ingest-provided cymbal IDs against event counts; log mismatches for manual review.
- **Model regression**: Retrain classifier with new label, run full evaluation (bootstrap CI + open-set tests) before deploying.

## Timeline (Estimate)
1. Feature extraction & clustering prototype — 3 days.
2. Ingest + manifest integration — 2 days.
3. Validation, tests, documentation — 2 days.
4. Full readiness rerun + training dry run — 2 days.

_Total_: ~9 focused days (can overlap with training experiments).

## Exit Criteria
- `crash2` present with ≥100 examples (per gating requirement) across merged manifests.
- `dataset_health.py` gates for `crash2` pass with zero manual overrides.
- Sampling weights regenerated with distinct crash distributions.
- CUDA training run validates metrics parity or improvement for crash-related classes.

---
Document owner: GitHub Copilot (AI data lead).
