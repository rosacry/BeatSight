# Training Manifest Guide

Manifests enumerate unified drum events for training and evaluation. Create JSONL files with one event per line, referencing audio slices produced by the ingestion tools.

Recommended naming:
- `dev_small.jsonl` – minimal subset for smoke tests and CI
- `full_audio.jsonl` – all real recordings (multitrack, live kits)
- `full_synthetic.jsonl` – rendered or augmented sources (Slakh, Groove synth)
- `full_live.jsonl` – live-only sessions for evaluation integrity
- `full_corpus.jsonl` – union manifest used for primary training runs

Each event row should include:
- `event_id`: globally unique identifier
- `session_id`: session or song reference
- `source_set`: origin dataset
- `audio_path`: relative path to normalized slice under `data/cache/`
- `onset_time` / `offset_time`: in seconds relative to source audio
- `tempo_bpm`, `meter`: local timing context
- `components`: array of drum components with velocity, dynamic bucket, openness, positional tags
- `techniques`: array of gesture labels sourced from `additionaldrummertech.txt`
- `is_synthetic`: boolean flag for rendered content
- `split`: optional field noting `train`, `val`, `test`, or specialized packs (`test_ood`, `boundary`)
- `metadata_ref`: link to the provenance JSONL entry for traceability

Before committing new manifests:
1. Run `python training/run_readiness_checks.py --dataset <manifest> --out-dir training/reports/health/<name>`.
2. Diff the new health report against the baseline with `python training/compare_health_reports.py`.
3. Document major changes in `training/reports/runbook.md` or a dated log entry in `training/reports/`.
