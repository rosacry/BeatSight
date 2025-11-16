# Data Inventory and Layout

## Storage Topology
- Primary workspace: `C:\Users\10ros\OneDrive\Documents\github\BeatSight` (Git Bash path `/c/Users/10ros/OneDrive/Documents/github/BeatSight`).
- External bulk storage: `D:\data\raw` (Git Bash path `/d/data/raw`).
- NVMe cache budget: 2 TB total, allocate <1 TB for preprocessed features under `data/cache/` when normalization scripts land.

## Dataset Inventory
| Dataset | Size (approx.) | Location (Windows) | Notes |
|---------|----------------|--------------------|-------|
| Cambridge Multitrack Collection (800 projects) | ~1 TB | `data/raw/cambridge` (~200 projects) + `D:\data\raw\cambridge` (~600 projects) | `ingest_cambridge.py` inventories both primary and external volumes |
| Slakh2100 | ~100 GB | `data/raw/slakh` | verify instrument stems mapping to drum taxonomy |
| Groove MIDI Dataset | ~6 GB | `data/raw/groove` | pair with audio where available |
| Extended Groove MIDI Dataset (E-GMD) | ~131 GB | `data/raw/egmd` | includes velocity + kit metadata |
| IDMT-SMT-Drums V2 | ~1 GB | `data/raw/idmt_smt_drums` | labeled single hits + grooves |
| MUSDB18 (compressed) | ~6 GB | `data/raw/musdb18` | keep original archives under `data/archives/` |
| MUSDB18 HQ | ~29 GB | `data/raw/musdb18_hq` | high-resolution stems, align sample rate |
| Telefunken Multitracks (23 projects) | ~26 GB | `data/raw/telefunken` | capture mic layouts in provenance |
| ENST-Drums | ~10 GB | `data/raw/enst` | new access credentials on 2025-11-07 |
| SignatureSounds Packs (15) | ~1 GB | `data/raw/signaturesounds` | percussion loops + one-shots |
| MedleyDB | Pending | - | awaiting access response |

## Lifecycle Checkpoints
- **Checksums:** capture SHA256 manifests per dataset under `data/archives/checksums/<dataset>.sha256`. Pending for newly transferred Cambridge split and ENST drop.
- **Licenses:** record summaries in `ai-pipeline/training/data/licenses/<dataset>.md` as ingestion scripts are authored.
- **Provenance:** store ingestion metadata in `ai-pipeline/training/data/provenance/<dataset>.jsonl` (one entry per source file, include path, sample rate, mic config, license, tags).

## Ingestion Roadmap
1. Build converters in `ai-pipeline/training/tools/` (`ingest_cambridge.py`, `ingest_slakh.py`, etc.) emitting unified `events.jsonl` with drummer technique annotations informed by `additionaldrummertech.txt`.
2. Normalize audio to 44.1 kHz (or project standard) with loudness alignment; cache under `data/cache/<dataset>/`.
3. Aggregate exports into tiered manifests in `ai-pipeline/training/data/manifests/` (`dev_small.jsonl`, `full_audio.jsonl`, `full_synthetic.jsonl`, `full_live.jsonl`).
4. Re-run readiness gates (`run_readiness_checks.py`) on each new manifest and archive reports inside `ai-pipeline/training/reports/health/`.
5. Kick off reference training runs (hyperparameter sweep + full corpus baseline) once manifests settle; log metrics to `ai-pipeline/training/reports/` and stage checkpoints in `ai-pipeline/training/models/`.

## Open Tasks
- [ ] Enumerate directory listing for each dataset and confirm counts vs. expected totals.
- [ ] Verify Git Bash paths (`/c/Users/...`, `/d/data/...`) and document in scripts.
- [ ] Generate initial checksum manifests and store under `data/archives/checksums/`.
  Use `python ai-pipeline/training/tools/write_checksums.py <root> data/archives/checksums/<dataset>.sha256` per corpus.
- [ ] Draft baseline provenance templates for each dataset (fields: `source_set`, `session_id`, `mic_config`, `tempo_map`, `techniques`).
- [x] Define cymbal taxonomy (high/mid/low crash/china, cowbell, stick position) in classifier label map prior to ingestion. See `ai-pipeline/training/configs/technique_taxonomy.json` for the curated list consumed by ingestion scripts.
