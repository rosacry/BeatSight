# Training Tool Examples

This folder provides small JSON/JSONL snippets that demonstrate the expected
format for the readiness tooling:

- `session_manifest_example.json` – input for `align_qc.py`.
- `boundary_labels_example.jsonl` & `boundary_predictions_example.jsonl` – inputs for `boundary_eval.py`.
- `openset_ground_truth_example.jsonl` & `openset_predictions_example.jsonl` – inputs for `openset_eval.py`.
- `bootstrap_ground_truth_example.jsonl` & `bootstrap_predictions_example.jsonl` – inputs for `bootstrap_eval.py`.
- `events_health_example.jsonl` – sample events for `dataset_health.py`.
- `metadata_health_example.json` – companion `metadata.json` emitted by
	`build_training_dataset.py`; pass to `dataset_health.py --dataset-metadata`
	to surface duration tables in the report outputs.
- `hard_negative_events_example.jsonl` & `hard_negative_predictions_example.jsonl` – inputs for `hard_negative_miner.py`.
- `../configs/health_min_counts_example.json` – baseline label thresholds for
	`dataset_health.py` when using bespoke minimum counts.
- `../configs/health_require_labels_example.txt` – newline-separated labels for
	`dataset_health.py --require-labels-file`.
- Health report baselines live under `reports/health/`; diff them with
	`compare_health_reports.py` to enforce non-regression gates in CI.

These files are tiny and synthetic; replace them with real manifests/packs in
your environment before running the scripts on production data.
