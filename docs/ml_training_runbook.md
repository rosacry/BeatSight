# BeatSight Drum Classifier Training Runbook

_Last updated: 2025-11-13_

This runbook captures the end-to-end workflow for refreshing the drum classifier after a new manifest export. It builds on the tooling in `ai-pipeline/training/tools/` and the post-export checklist.

---

## 0. Logistics (current)
- Replacement HDD arrival (Nov 13) is required before moving forward; hold exports until the new drive is installed.
- Once the drive is online, migrate `prod_combined_profile_run`, `feature_cache`, checkpoints, W&B offline runs, and other heavy assets from WSL storage back to `C:`.
- Confirm the final data layout (e.g., `C:\BeatSightData\prod_combined_profile_run`, `...\feature_cache`, `...\checkpoints`). This layout will inform the new environment hook described below.

## 1. Prerequisites
- Verified manifest (`prod_combined_events.jsonl`) with health report ✅.
- All audio roots mounted (`data/raw`, `data/raw/cambridge`, etc.); run `check_cambridge_presence.py` to confirm.
- GPU node provisioned (RTX 3080 Ti+ locally or cloud A100/A40 equivalent) with CUDA 12 environment.
- Python virtualenv activated (`source ai-pipeline/venv/bin/activate`).
- Weights & Biases logged in (`wandb login`), or W&B offline mode configured.
- Storage budget: ≥1 TB free for dataset export + cache + checkpoints.
- **Pending update:** Introduce a centralized `BEATSIGHT_DATA_ROOT` env/config hook so datasets, caches, checkpoints, and W&B paths derive from one source. Until it is wired in, keep path overrides consistent across scripts.

## 2. Export Dataset
1. Verify manifest resolution (optional smoke):
   ```bash
   PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/build_training_dataset.py \
      ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
      /tmp/prod_combined_profile_run \
      --audio-root /mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw \
      --audio-root-map slakh2100=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/slakh2100 \
      --audio-root-map groove_mididataset=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/groove_midi \
      --audio-root-map cambridge_multitrack=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/cambridge \
      --audio-root-map cambridge_multitrack=/mnt/d/data/raw/cambridge \
      --limit 1000 --verify-only
   ```
2. Full export (monitor Rich dashboard):
   ```bash
   PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/build_training_dataset.py \
      ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
      /home/chrig/prod_combined_profile_run \
      --audio-root /mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw \
      --audio-root-map slakh2100=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/slakh2100 \
      --audio-root-map groove_mididataset=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/groove_midi \
      --audio-root-map cambridge_multitrack=/mnt/c/Users/10ros/OneDrive/Documents/github/BeatSight/data/raw/cambridge \
      --audio-root-map cambridge_multitrack=/mnt/d/data/raw/cambridge \
      --manifest-total 3010770 \
      --write-workers 8 \
      --force-rich \
      --overwrite
   ```

> Adjust output paths (`/home/chrig/...`) if running on a different machine; keep metadata relative for downstream scripts.

## 3. Post-Export Checklist
Run the predefined script to validate the dataset and prep for training:
```bash
bash ai-pipeline/training/tools/post_export_commands.sh
```
Key actions performed:
- Sync offline W&B runs.
- `dataset_health.py` validation (JSON + HTML reports).
- Snapshot of metadata totals vs manifest.
- Pytest regression targets (`test_dataset_health.py`, `test_drum_classifier.py`).
- Optional feature-cache warm-up.
- Training presets (warmup, quick, long-run).
- Post-run analysis entry point (`analyze_classifier.py`).

Ensure reports land in `ai-pipeline/training/reports/health/` and `reports/metrics/` for archival.

> Tip: `post_export_commands.sh` now targets `BEATSIGHT_*` environment variables. Export `BEATSIGHT_DATA_ROOT` (and friends) once after you finalize the new layout and the checklist commands will follow automatically.

## 4. Training Presets
Choose a preset based on available compute:

### 4.1 Warm-up Probe (8 epochs)
- Validates pipeline end-to-end (~75 min with warm cache).
- Confirms accuracy jumps from baseline; use before longer runs.

### 4.2 Baseline Refresh (60 epochs)
- Target for the November 2025 refresh; expect ~3.5h on 3080 Ti with cached features.
- Achieve ≥93% validation accuracy and ≤0.45 validation loss before promotion.

### 4.3 Long Run (220 epochs)
- Extended fine-tuning pass (~12h) when chasing incremental gains.
- Group runs via `WANDB_RUN_GROUP` for ensemble management.

> Update `--wandb-tags` and `--wandb-run-name` for traceability (e.g., `prod_combined_20251109`).

## 5. Probe Evaluation Checklist (steps 4 → 5a)
Use this sequence before committing to the long run:
1. **Run step 4** (warm-up probe).
2. **Run step 5a** and evaluate immediately:
   - Re-run step 6 with `--fraction 0.3` right after the probe. Expect overall validation accuracy ≥0.72 and per-class recall >0.25 across cymbal/tom buckets; zeros indicate the subset is still too sparse.
   - Load `reports/metrics/prod_combined_warmup_confusion` (`.npy`/`.json`) and verify kick↔ride_bow and hihat_*↔snare confusions shrink relative to the previous run (use the notebook helpers in `training/tools/`).
   - Inspect the W&B run tagged `richer_subset warmup`; class F1 panels should trend upward without post-warmup oscillation once LR anneals.
   - Confirm training vs validation loss: training loss should decline smoothly, validation loss should only flatten after ~epoch 15. Early flattening or rising val loss points to an overly aggressive LR or inconsistent subset.
   - Spot-audit `prod_combined_warmup_misclassified.json`; high-confidence mistakes should skew toward edge cymbals or aux hits rather than core kick/snare swaps.
3. **If probe looks healthy**, proceed with step 5c (longer run). Monitor W&B confusion matrices to ensure hi-hat vs snare separation continues to improve as LR ramps down.
4. **After step 5c**, repeat the validation slice with `--fraction 0.3` to stress rare cymbal classes before promotion.
5. Consider enabling class weighting or sampling adjustments in `train_classifier.py` if the evaluation reveals persistent imbalance; hooks can be added quickly once the probe results are captured.

## 5. Monitoring & Troubleshooting
- Watch W&B dashboards for loss, accuracy, learning-rate scheduling.
- Check GPU utilization (`nvidia-smi`) and I/O throughput; adjust `--num-workers`/`--prefetch-factor` if stalled.
- If training crashes, resume with `--resume-from <run_dir>/checkpoints/latest_checkpoint.pth`.
- For data-related issues, revisit `dataset_health.json/html` before re-running training.

## 6. Promotion Criteria
1. Validation accuracy ≥93% and F1 per class >0.90 (kick/snare/crash). Use `analyze_classifier.py --topk-misclassified` to spot drifts.
2. Compare metrics against previous baseline stored in `ai-pipeline/training/reports/metrics/*.json`.
3. Document summary in `CURRENT_STATUS.md` and `NEXT_STEPS.md` with links to artifacts.
4. Promote model by copying `best_drum_classifier.pth` into production path (`ai-pipeline/models/current_drum_classifier.pth`).
5. Update pipeline configs to reference new checkpoint.

## 7. Post-Run Archival
- Upload W&B summary to project workspace; export CSV metrics for long-term storage.
- Archive dataset metadata, health reports, and top misclassifications in `ai-pipeline/training/reports/archive/YYYYMMDD/`.
- Clean up temporary datasets if disk usage becomes an issue; retain canonical export under `ai-pipeline/training/datasets/`.

## 8. Open Items
- Automate feature-cache warming on GPU nodes with systemd/tmux service.
- Evaluate migrating to Modal/AWS Batch for bursty training needs.
- Document exact CUDA/cuDNN versions used during successful runs for reproducibility.
- Implement repository-wide support for `BEATSIGHT_DATA_ROOT`, refactor existing absolute paths, and update helper scripts (including `post_export_commands.sh`).

---

For rapid checklists, refer to `post_export_commands.sh`. Update this runbook whenever the training workflow changes.
