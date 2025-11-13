# Training Tools

| Script | Purpose |
|--------|---------|
| alias_events.py | Normalize component labels (aliasing duplicates). |
| export_events.py | Export events to CSV or JSON for analysis. |
| generate_dev_dataset.py | Produce the tiny dev dataset for CI. |
| derive_sampling_weights.py | Compute per-group sampling weights with technique boosts, dedupe keys, and profile presets. |
| crash_variant_clustering.py | Promote crash dual-label assignments using metadata heuristics plus optional spectral clustering. |
| extract_crash_embeddings.py | Slice crash events and compute spectral descriptors ahead of dual-label clustering. |
| check_dataset_integrity.py | Validate dataset roots and checksum manifests before running exports (ideal for CI preflight). |
| hparam_sweep.py | Grid search for `train_classifier.py` hyperparameters. |
| summarize_manifest_metrics.py | Snapshot label/technique/source counts from a manifest right after ingestion for drift tracking. |
| ingest_utils.py | Shared helpers (checksums, JSONL writing) for ingestion scripts. |
| ingest_groove.py | Convert Groove MIDI dataset into BeatSight `events.jsonl` and provenance records. |
| ingest_egmd.py | Convert Extended Groove MIDI dataset into the unified schema with velocity layers captured. |
| ingest_cambridge.py | Inventory Cambridge multitracks across primary and external storage roots. |
| ingest_slakh.py | Parse Slakh2100 MIDI renders into unified events and provenance. |
| ingest_enst.py | Import ENST-Drums audio annotations as timestamped events. |
| ingest_idmt.py | Convert IDMT-SMT-Drums V2 annotations to events. |
| ingest_musdb.py | Summarize MUSDB18 HQ drum stems and provenance. |
| ingest_telefunken.py | Index Telefunken multitrack drum captures with heuristically labeled components. |
| ingest_signaturesounds.py | Catalog SignatureSounds percussion one-shots into events. |
| annotate_techniques.py | Backfill taxonomy-derived techniques (metric modulation, variable meter, layered cymbals) into existing manifests without a full reingest. |
| build_training_dataset.py | Slice manifest events into train/val audio bundles with optional rich progress, resumable exports, and summary reporting. |
| merge_manifests.py | Stream multiple event manifests into a single JSONL for readiness checks or ad-hoc analysis. |
| compare_manifests.py | Compare two manifests by session, component, and technique coverage to spot regressions. |
| analyze_hihat_transitions.py | Inspect hi-hat open→close windows (uses `training.event_loader` streaming). |
| post_ingest_checklist.py | Run dataset health, pytest, and sampling-weight refresh after any ingest completes. |
| pre_export_checklist.sh | Perform a limited export smoke test plus dataset health before the full production run. |
| write_checksums.py | Emit SHA256 manifests for dataset directories. |

Run ingestion scripts from the repository root so they can locate `additionaldrummertech.txt` and write outputs into `ai-pipeline/training/data/`.

## `build_training_dataset.py`

- Use `--verify-only` to dry-run a manifest and surface missing audio/components before writing any clips.
- Verification summaries estimate total clip duration and break it down by source so you can gauge dataset footprint; use `--expected-duration-csv` (in verify or export modes) to persist those tables for scheduling.
- `--resume` continues an interrupted export without duplicating labels; missing audio files are healed automatically.
- `metadata.json` now tracks lifetime totals (`statistics.*`) and the most recent run (`run_statistics.*`), plus per-split audio seconds (`split_durations_seconds` / `run_split_durations_seconds`) and per-source audio seconds (`duration_seconds_by_source` / `run_duration_seconds_by_source`), which render in the CLI summary as separate tables when rich is available.
- `--summary-json` writes the verification/export report to a separate JSON file for sharing in readiness reviews.
- See `BUILD_DATASET_WORKFLOW.md` for an end-to-end operator checklist covering verification, export, and resume flows.
