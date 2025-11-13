# Training Dataset Export Workflow

This guide walks through the recommended process for validating a manifest, exporting a dataset bundle, and resuming an interrupted run with `build_training_dataset.py`.

## 0. Dataset integrity baseline

Before touching the manifest, confirm that the raw assets you expect are
available. The tool below checks that each dataset root in
`configs/dataset_integrity.json` exists and, when requested, walks the checksum
manifests to ensure the referenced files are still present.

```bash
python ai-pipeline/training/tools/check_dataset_integrity.py \
  --verify-manifests --max-checks 2000
```

Integrate this step into CI so a missing external drive (or a deleted pack)
fails fast instead of surfacing halfway through a long export.

## 1. Pre-flight verification (`--verify-only`)

Run the tool in verification mode to confirm audio coverage and label integrity before writing any files:

```bash
python ai-pipeline/training/tools/build_training_dataset.py \
  ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
  /tmp/no-op \
  --verify-only \
  --audio-root data/raw \
  --audio-root-map slakh2100=data/raw/slakh2100 \
  --audio-root-map groove_mididataset=data/raw/groove_midi \
  --summary-json logs/verify_prod_combined.json
```

- **No files are created**; the tool streams the manifest and renders a rich summary.
- Missing audio/components are surfaced with counts and example event IDs.
- The verification report summarizes label distribution, making it easy to spot taxonomy gaps.
- The summary includes an estimated total clip duration (based on context windows) for quick sizing.
- A per-source duration table highlights which collections will contribute the most audio once exported.
- Pass `--expected-duration-csv reports/verify_duration.csv` to export the per-source table as structured data for planning large runs (the same flag during export writes the actual totals).

## 1b. Limited export smoke test (optional but recommended)

Run a short export before committing to the full dataset. The helper script
below executes a `--limit` run (default 50k events), records throughput, runs
`dataset_health.py` on the temporary bundle, and then removes the smoke
directory.

```bash
bash ai-pipeline/training/tools/pre_export_checklist.sh
```

Override `EXPORT_LIMIT`, `RAW_PRIMARY`, or `RAW_SECONDARY` in the environment if
you need a different sample size or storage roots. Pass `KEEP_SMOKE_OUTPUT=1`
when you want to inspect the clips manually.

## 2. First export
- Duration tables break down clip seconds by source_set for the aggregate dataset and just this run.
- When you provide `--expected-duration-csv`, the export step writes the per-source totals (aggregate + current run) for downstream readiness dashboards.
- After ingestion finishes, snapshot the class/technique distribution so you
  have concrete numbers for drift comparisons:

  ```bash
  python ai-pipeline/training/tools/summarize_manifest_metrics.py \
    --manifest ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
    --output ai-pipeline/training/reports/metrics/prod_combined_ingest_snapshot.json
  ```

After verification, perform the full export:

```bash
python ai-pipeline/training/tools/build_training_dataset.py \
  ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
  ai-pipeline/training/datasets/prod_combined_20251109 \
  --audio-root data/raw \
  --audio-root-map slakh2100=data/raw/slakh2100 \
  --audio-root-map groove_mididataset=data/raw/groove_midi \
  --sample-rate 44100 \
  --val-ratio 0.1 \
  --log-file logs/dataset_prod_combined_20251109.log \
  --summary-json logs/dataset_prod_combined_20251109.summary.json
```

Highlights:

- Rich progress with clips/train/val counters updates live.
- Outputs include:
  - `train/train_labels.json`, `val/val_labels.json`
  - `components.json`
  - `metadata.json` (aggregate + per-run statistics, including split duration totals)
- The plain-text summary mirrors to the optional log file for provenance.
  - Rich and plain summaries now surface total/train/val audio duration with human-friendly formatting.
  - Duration tables break down clip seconds by source_set for the aggregate dataset and just this run.
- When you provide `--expected-duration-csv`, the export step writes the per-source totals (aggregate + current run) for downstream readiness dashboards.

## 3. Resuming a run (`--resume`)

If the job stops midway (e.g., storage hiccup), rerun with `--resume`:

```bash
python ai-pipeline/training/tools/build_training_dataset.py \
  ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
  ai-pipeline/training/datasets/prod_combined_20251109 \
  --resume \
  --audio-root data/raw
```

Key behaviors:

- Existing clips remain intact; missing audio files listed in label JSONs are regenerated automatically.
- New labels are appended without duplicating existing entries.
- `metadata.json` tracks:
  - **`statistics.*`**: lifetime totals (e.g., all clips after multiple runs)
  - **`run_statistics.*`**: what the current invocation contributed
  - **`run_label_counts.*`**: labels added on this run only
  - **`split_durations_seconds` / `run_split_durations_seconds`**: per-split audio seconds retained across runs and emitted for the current invocation
- The CLI renders a *Run Contribution* table so you can confirm progress was made during the resume.

## 4. Suggested checklist

1. `--verify-only` and review missing audio table.
2. Run full export with logging enabled.
3. If interrupted, rerun with `--resume` until no clips remain in `run_statistics`.
4. Archive `metadata.json`, the summary JSON, and the log file alongside the dataset bundle for provenance.

## 5. Troubleshooting tips

- **Persistent missing audio**: ensure `--audio-root` and `--audio-root-map` targets exist and have read permissions.
- **Unexpected new labels on resume**: inspect the manifest for newly ingested components since the last run; update taxonomy config if needed.
- **Performance**: use `--manifest-total` when known to improve progress ETA accuracy; `--limit` can smoke-test new manifests.

By following this workflow, each dataset export yields reproducible artifacts with clear audit trails and fast recovery from interruptions.
