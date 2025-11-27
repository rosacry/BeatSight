# BeatSight Drum Classifier Training Runbook

_Last updated: 2025-11-24_

This runbook captures the end-to-end workflow for refreshing the drum classifier after a new manifest export. It builds on the tooling in `ai-pipeline/training/tools/` and the post-export checklist.

---

## 0. Hardware Profile (Reference System)

| Component | Specification | Training Impact |
|-----------|---------------|-----------------|
| GPU | RTX 3080 Ti FE (12GB VRAM) | AMP float16, batch_size=32-48 |
| CPU | AMD Ryzen 9800X3D (8-core, 104MB L3) | 2-4 DataLoader workers optimal |
| RAM | 32GB DDR5-6000 MT/s | Sufficient for full dataset |
| Storage | Samsung 990 Pro 2TB NVMe | Eliminates I/O bottlenecks |

**Key Optimizations:**
- `channels_last` memory format for tensor core utilization
- `torch.compile(mode="reduce-overhead")` for reduced graph overhead
- `float16` feature cache cuts storage by 50%
- Gradient accumulation for effective batch_size=128 without VRAM increase

## 1. Prerequisites
- Verified manifest (`prod_combined_events.jsonl`) with health report ✅.
- All audio roots mounted (`data/raw`, `data/raw/cambridge`, etc.); run `check_cambridge_presence.py` to confirm.
- GPU node provisioned (RTX 3080 Ti+ locally or cloud A100/A40 equivalent) with CUDA 12 environment.
- Python virtualenv activated (`source ai-pipeline/venv/bin/activate`).
- Weights & Biases logged in (`wandb login`), or W&B offline mode configured.
- Storage budget: ≥1 TB free for dataset export + cache + checkpoints.
- Source `ai-pipeline/training/tools/beatsight_env.sh` (or export the same variables manually) so `BEATSIGHT_DATA_ROOT`, `BEATSIGHT_DATASET_DIR`, `BEATSIGHT_CACHE_DIR`, etc. point at your chosen storage layout.

### 1.1 Quick Environment Setup
```bash
# Source the environment hook (creates all BEATSIGHT_* variables)
source ai-pipeline/training/tools/beatsight_env.sh

# Verify CUDA availability
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"

# Verify storage paths exist
ls -la "${BEATSIGHT_DATA_ROOT}"
ls -la "${BEATSIGHT_DATASET_DIR}" 2>/dev/null || echo "Dataset not yet exported"
```

## 2. Export Dataset
1. Verify manifest resolution (optional smoke):
   ```bash
   source ai-pipeline/training/tools/beatsight_env.sh
   export BEATSIGHT_SECONDARY_ROOT="${BEATSIGHT_SECONDARY_ROOT:-$BEATSIGHT_DATA_ROOT}"

   PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/build_training_dataset.py \
      ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
      "$BEATSIGHT_DATA_ROOT/prod_combined_profile_run_smoke" \
      --audio-root "$BEATSIGHT_DATA_ROOT/raw" \
      --audio-root-map slakh2100=$BEATSIGHT_DATA_ROOT/raw/slakh2100 \
      --audio-root-map groove_mididataset=$BEATSIGHT_DATA_ROOT/raw/groove_midi \
      --audio-root-map cambridge_multitrack=$BEATSIGHT_DATA_ROOT/raw/cambridge \
   --audio-root-map cambridge_multitrack=$BEATSIGHT_SECONDARY_ROOT/raw/cambridge \
      --limit 1000 --verify-only
   ```
2. Full export (monitor Rich dashboard):
   ```bash
   source ai-pipeline/training/tools/beatsight_env.sh
   export BEATSIGHT_SECONDARY_ROOT="${BEATSIGHT_SECONDARY_ROOT:-$BEATSIGHT_DATA_ROOT}"

   PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/build_training_dataset.py \
      ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
      "$BEATSIGHT_DATA_ROOT/prod_combined_profile_run" \
      --audio-root "$BEATSIGHT_DATA_ROOT/raw" \
      --audio-root-map slakh2100=$BEATSIGHT_DATA_ROOT/raw/slakh2100 \
      --audio-root-map groove_mididataset=$BEATSIGHT_DATA_ROOT/raw/groove_midi \
      --audio-root-map cambridge_multitrack=$BEATSIGHT_DATA_ROOT/raw/cambridge \
      --audio-root-map cambridge_multitrack=$BEATSIGHT_SECONDARY_ROOT/raw/cambridge \
      --manifest-total 3010770 \
      --write-workers 8 \
      --force-rich \
      --overwrite
   ```

> Adjust `BEATSIGHT_DATA_ROOT` (and optionally `BEATSIGHT_SECONDARY_ROOT`) if your heavy data lives elsewhere. All downstream scripts will respect these exports.

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

### 4.4 Advanced Training Paths (2024)
For cutting-edge features beyond baseline CNN, see `docs/CUTTING_EDGE_TRAINING_FEATURES.md`:

| Mode | Description | Duration | Expected Gain |
|------|-------------|----------|---------------|
| **17a-17d** | **V5 Ultimate ⭐ RECOMMENDED** | 2-24hr | +3-6% over v4 |
| 15a-15d | Temporal Mamba (NOVEL/patentable) | 3-24hr | +3-8% on edge cases |
| 16a-16d | Ultimate (Wav2Vec2 + Mamba + Beat) | 5-40hr | +9-20% |
| 18a-18c | BEATs (Microsoft audio foundation) | 1-12hr | +2-3% |
| 12a-12c | Enhanced v4 (superseded by V5) | 2-18hr | +5-10% |

> **⭐ RECOMMENDED DEFAULT**: Path G (17a → 17d) provides the best single-model quality with all 2024 innovations in ~14-26 hours total. Start here.
>
> **For novel IP/patents**: Path E (15a-15d) or Path F (16a-16d) contain publishable research that can be patented.

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

### 5.1 Real-time Monitoring
```bash
# GPU utilization (run in separate terminal)
watch -n 1 nvidia-smi

# Expected values for RTX 3080 Ti:
# - GPU Util: 85-98%
# - Memory: 6-9 GB depending on batch size
# - Power: 300-350W during training
```

### 5.2 Common Issues & Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| GPU util <50% | DataLoader bottleneck | Increase `--num-workers` to 4 |
| GPU util fluctuating | Prefetch too low | Set `--prefetch-factor 2-4` |
| OOM errors | Batch too large | Reduce batch, increase `--grad-accum-steps` |
| Training loss stuck | LR too low/high | Try LR in range 1e-4 to 5e-4 |
| Val loss rising | Overfitting | Enable early stopping, increase weight decay |
| NaN loss | Gradient explosion | Enable `--grad-clip-norm 1.0` |
| Slow first epoch | Cache miss | Run precompute_feature_cache.py first |

### 5.3 Recovery from Interruption
```bash
# Resume from last checkpoint (automatic save on interrupt)
PYTHONPATH=ai-pipeline python ai-pipeline/training/train_classifier.py \
  --resume-from "${BEATSIGHT_RUN_WARMUP}/checkpoints/latest_checkpoint.pth" \
  [... same args as original run ...]
```

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

## 8. Performance Benchmarks (RTX 3080 Ti Reference)

| Preset | Effective Batch | Samples/sec | VRAM Peak | Time/Epoch |
|--------|-----------------|-------------|-----------|------------|
| Warmup | 128 | 1200-1500 | 6.5 GB | 3.5 min |
| Quick | 144 | 1400-1700 | 8.5 GB | 2.8 min |
| Long | 128 | 1300-1600 | 7.0 GB | 3.2 min |

## 9. Open Items
- ✅ Created `beatsight_env.sh` environment hook
- ✅ Added hardware-optimized configs in `configs/hardware_profiles.json`
- Evaluate migrating to Modal/AWS Batch for bursty training needs.
- Document exact CUDA/cuDNN versions used during successful runs for reproducibility.
- Consider implementing class weighting for imbalanced classes.

---

For rapid checklists, refer to `post_export_commands.sh`. Update this runbook whenever the training workflow changes.

