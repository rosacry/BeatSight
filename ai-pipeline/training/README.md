# AI Training System

This directory contains tools for training and improving the drum classification model.

## Overview

The training system now includes:

1. **Data Collection** (`collect_training_data.py`) – Collect and label drum samples.
2. **QA & Evaluation Utilities** (`align_qc.py`, `boundary_eval.py`, `openset_eval.py`, `bootstrap_eval.py`) – Enforce dataset readiness gates (alignment, streaming boundaries, open-set robustness, statistical significance).
3. **ML Classifier** (`../transcription/ml_drum_classifier.py`) – PyTorch CNN model.
4. **Training Script** (`train_classifier.py`) – Train the model once the dataset passes QA.

### Technique Taxonomy

Curated drummer techniques and timing feels live in `training/configs/technique_taxonomy.json`, sourced from the root `additionaldrummertech.txt`. Ingestion helpers (`ingest_utils.load_techniques`) now prefer this machine-readable catalog, falling back to the legacy text file if the JSON is missing. Keep the catalog updated whenever the text file grows so readiness gates (`health_required_techniques_prod.txt`) and sampling profiles can enforce coverage for high-priority techniques like hi-hat barking, metric modulation, variable meter feels, and layered cymbal hits from the same class.

## Quick Start

### 1. Collect Training Data

```bash
# Add a single sample
python collect_training_data.py --add-sample audio.mp3 1.234 kick

# Extract from a beatmap (best method!)
python collect_training_data.py --extract-beatmap beatmap.bsm audio.mp3

# Check statistics
python collect_training_data.py --stats

# Export dataset for training
python collect_training_data.py --export dataset
```

### 2. Train the Model

```bash
# Train with default settings
python train_classifier.py --dataset ./dataset --epochs 50

# Train with GPU
python train_classifier.py --dataset ./dataset --epochs 100 --batch-size 64 --device cuda

# Custom learning rate
python train_classifier.py --dataset ./dataset --lr 0.0001 --epochs 75

# Log a run to Weights & Biases (optional)
pip install wandb
wandb login
python train_classifier.py --dataset ./dataset --epochs 50 --wandb-project beatsight-classifier --wandb-tags prod retrain
```

`--wandb-project` activates logging; add `--wandb-entity` for team workspaces or `--wandb-mode offline` when running air-gapped. Metrics stream per epoch, and best/final checkpoints upload automatically when the dependency is available.

## Production Training Commands (12-Class v5 Model)

These commands are the **verified production configuration** that achieved **94.55% balanced validation accuracy** on the 12-class drum classifier. Use these exact hyperparameters for reproducible results.

> **Last Updated:** January 2026  
> **Current Best:** 94.55% balanced accuracy (Phase 2, Epoch 63)  
> **Theoretical Ceiling:** 94.93% (99.6% achieved)

### Prerequisites

**Dataset:** `prod_v5_final` (16.9M total samples, with 1.17M label corrections)
- Training samples: **15,217,976** (90% split)
- Validation samples: **1,690,880** (10% split)
- Class distribution: **47.5:1 ratio** (snare:splash)
- STAR Drums samples integrated: 40,733 real-world recordings
- Lakh MIDI synthetic samples: 166,664 for rare classes
- **Label corrections applied:** 1,172,486 (692,161 model confidence + 480,325 hi-hat force corrections)
- All 12 classes: china, crash, cross_stick, hihat_closed, hihat_open, hihat_pedal, kick, ride_bell, ride_bow, snare, splash, tom

**Feature Cache:** Precompute mel-spectrograms for faster training:

```bash
# Precompute feature cache for ~15M samples (run once)
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/tools/precompute_feature_cache_fast.py \
  --dataset "F:/datasets/prod_v5_cleaned" \
  --cache-dir "F:/feature_cache" \
  --splits train val \
  --num-workers 4 \
  --batch-size 64
```

### Phase 1: Initial Training ✅ COMPLETE (90.06% achieved)

The verified training run that achieved **90.06% balanced accuracy at epoch 53** (on `prod_v5_cleaned` before label cleaning):

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \
  --dataset "F:/datasets/prod_v5_cleaned" \
  --feature-cache-dir "F:/feature_cache" \
  --model-version v5 --v5-size large \
  --epochs 53 --batch-size 160 --grad-accum-steps 4 \
  --lr 1e-4 \
  --amp-dtype bfloat16 \
  --balanced-sampling --sampling-strategy uniform \
  --cb-loss --cb-beta 0.999 \
  --specaugment drum \
  --use-ema --ema-decay 0.999 \
  --scheduler cosine --warmup-epochs 5 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 \
  --channels-last --output runs/v5_phase1
```

**Phase 1 hyperparameters (verified 90.06% run):**
- `--lr 1e-4` – Initial learning rate with cosine decay
- `--batch-size 160` with `--grad-accum-steps 4` – Effective batch size 640
- `--cb-loss --cb-beta 0.999` – Class-balanced loss (note: at this scale, effectively uniform weights)
- `--ema-decay 0.999` – EMA model averaging
- **Result:** 90.06% balanced validation accuracy at epoch 53

### Phase 2: Label Cleaning + Fine-Tuning ✅ COMPLETE (94.55% achieved)

After label cleaning (1.17M corrections applied to create `prod_v5_final`), training achieved **94.55% balanced accuracy**:

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \
  --dataset "F:/datasets/prod_v5_final" \
  --feature-cache-dir "F:/feature_cache" \
  --model-version v5 --v5-size large \
  --epochs 84 --batch-size 160 --grad-accum-steps 4 \
  --lr 1e-5 \
  --amp-dtype bfloat16 \
  --balanced-sampling --sampling-strategy uniform \
  --specaugment drum \
  --label-smoothing 0.1 \
  --use-ema --ema-decay 0.999 \
  --use-swa --swa-start-pct 0.5 --swa-lr 5e-6 \
  --scheduler cosine --warmup-epochs 0 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 \
  --channels-last \
  --output runs/v5_phase2 \
  --resume-from runs/v5_phase1/checkpoints/best_checkpoint.pth \
  --reset-scheduler
```

**Phase 2 changes:**
- Dataset changed from `prod_v5_cleaned` → `prod_v5_final` (with label corrections)
- `--lr 1e-5` – 10x lower learning rate for fine-tuning
- `--label-smoothing 0.1` – Regularization to prevent overconfidence
- `--use-swa --swa-start-pct 0.5 --swa-lr 5e-6` – Stochastic Weight Averaging
- **Result:** 94.55% balanced validation accuracy at epoch 63

### Phase 3: Final Fine-Tuning (Optional - minimal gains expected)

```bash
cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python training/train_classifier.py \
  --dataset "F:/datasets/prod_v5_cleaned" \
  --feature-cache-dir "F:/feature_cache" \
  --model-version v5 --v5-size large \
  --epochs 104 --batch-size 160 --grad-accum-steps 4 \
  --lr 1e-6 \
  --amp-dtype bfloat16 \
  --balanced-sampling --sampling-strategy uniform \
  --specaugment drum \
  --label-smoothing 0.1 \
  --use-ema --ema-decay 0.9995 \
  --use-swa --swa-start-pct 0.5 --swa-lr 5e-7 \
  --scheduler cosine --warmup-epochs 0 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 --prefetch-factor 2 --persistent-workers --pin-memory \
  --checkpoint-every 1 --checkpoint-every-batches 5000 \
  --channels-last \
  --output runs/v5_phase3 \
  --resume-from runs/v5_phase2/checkpoints/best_checkpoint.pth \
  --reset-scheduler
```

**Phase 3 changes:**
- `--lr 1e-6` – Very low LR for final polish
- `--ema-decay 0.9995` – Higher EMA decay for stability
- `--swa-lr 5e-7` – Lower SWA learning rate

### ⚠️ Important: Phase Transition and Resume Behavior

When using `--reset-scheduler`:
- The scheduler state from checkpoint is **ignored** (T_max, eta_min recalculated from new args)
- The optimizer's `initial_lr` is **reset** to match `--lr` argument
- This prevents LR schedule corruption when transitioning between phases with different LR

When resuming **within the same phase** (e.g., after a crash):
- Do **NOT** use `--reset-scheduler`
- The scheduler will continue from where it left off
- Example: `--resume-from runs/v5_phase2/checkpoints/latest_checkpoint.pth` (no --reset-scheduler)

### Dataset Class Distribution (prod_v5_final)

| Class | Count | Ratio to Min |
|-------|-------|--------------|
| snare | 3,726,478 | 47.5:1 |
| hihat_closed | 3,078,654 | 39.2:1 |
| kick | 2,966,716 | 37.8:1 |
| hihat_pedal | 1,470,232 | 18.7:1 |
| ride_bow | 1,448,023 | 18.4:1 |
| tom | 1,101,824 | 14.0:1 |
| hihat_open | 535,178 | 6.8:1 |
| cross_stick | 414,432 | 5.3:1 |
| crash | 301,208 | 3.8:1 |
| ride_bell | 282,856 | 3.6:1 |
| china | 90,524 | 1.2:1 |
| splash | 78,347 | 1.0:1 (min) |

**Total Training:** 15,217,976 samples  
**Total Validation:** 1,690,880 samples  
**Class Imbalance:** 47.5:1 (snare:splash) - handled by `--balanced-sampling --sampling-strategy uniform`
**Label Corrections Applied:** 1,172,486 (692,161 model confidence + 480,325 hi-hat force corrections)

> **Note:** The class imbalance is handled by uniform balanced sampling, which ensures each class is sampled equally during training. Combined with label cleaning, this achieved **94.55% balanced accuracy**.

### 3. Run QA & Evaluation Checks

Before exporting a release candidate, run the new readiness checks:

```bash
# Multi-mic alignment (fails with exit code 1 when --strict)
python align_qc.py --manifest sessions/session_001.json --report reports/session_001_alignment.json --strict

# Streaming boundary recall (macro recall gate 0.95 by default)
python boundary_eval.py --ground-truth boundary_pack/labels.jsonl --predictions outputs/boundary_predictions.jsonl --strict

# Open-set rejection (AUROC gate 0.90, FPR@95 gate 0.10)
python openset_eval.py --ground-truth test_ood_unknown/labels.jsonl --predictions outputs/test_ood_unknown_preds.jsonl --strict

# Bootstrap confidence intervals (1,000 resamples)
python bootstrap_eval.py --ground-truth splits/test.jsonl --predictions outputs/test_preds.jsonl \
    --report reports/test_bootstrap.json --iterations 1000

# Or run all checks together
python run_readiness_checks.py \
    --alignment-manifest sessions/session_001.json \
    --alignment-report reports/session_001_alignment.json \
    --boundary-ground-truth boundary_pack/labels.jsonl \
    --boundary-predictions outputs/boundary_predictions.jsonl \
    --boundary-report reports/boundary_metrics.json \
    --openset-ground-truth test_ood_unknown/labels.jsonl \
    --openset-predictions outputs/test_ood_unknown_preds.jsonl \
    --openset-report reports/openset_metrics.json \
    --bootstrap-ground-truth splits/test.jsonl \
    --bootstrap-predictions outputs/test_preds.jsonl \
    --bootstrap-report reports/test_bootstrap.json \
    --health-events training/data/manifests/prod_combined_events.jsonl \
    --health-require-techniques-file configs/health_required_techniques_prod.txt \
    --halt-on-first-failure
```

Wire the `--strict` options into CI so releases block when gates fail. Pair the readiness wrapper with `--health-require-techniques-file` to ensure bark (and future technique) coverage holds steady. Reports in `reports/` feed directly into the dataset readiness documentation.

See `examples/session_manifest_example.json` for the manifest format consumed by
`align_qc.py`, and `boundary_pack/README.md` for guidance on building the
streaming boundary dataset.

`generate_boundary_pack.py` produces the streaming boundary JSONL from annotated
events:

```bash
python generate_boundary_pack.py \
    --events annotations/events.jsonl \
    --output boundary_pack/labels.jsonl \
    --window-ms 2048 \
    --hop-ms 512 \
    --margin-ms 40
```

Tune the window and hop sizes to mirror your streaming inference configuration.

Example JSONL inputs for the readiness utilities are stored in `examples/` and
can be used to sanity-check CLI invocation before wiring up real data.

### CI Integration

The repository ships with `.github/workflows/dataset-readiness.yml`, which
invokes `run_readiness_checks.py` on pushes and pull requests that touch the
`training/` directory. Update the workflow arguments (manifest paths, boundary
pack locations, etc.) to match your production data layout before enabling it.

### Hard Negative Mining

Use `hard_negative_miner.py` to capture high-confidence false positives for
labeling:

```bash
python hard_negative_miner.py \
    --predictions outputs/full_mix_predictions.jsonl \
    --ground-truth annotations/events.jsonl \
    --output negatives/negatives_manifest.jsonl \
    --min-confidence 0.7 \
    --max-per-label 150
```

See `examples/hard_negative_predictions_example.jsonl` and
`examples/hard_negative_events_example.jsonl` for expected schemas.

### Dataset Health Reports

Use `dataset_health.py` to inspect coverage, duplication, dynamics, and openness
distributions before promoting a release:

```bash
python dataset_health.py \
    --events annotations/events.jsonl \
    --components components.json \
    --output reports/health/latest_health.json \
    --html-output reports/health/latest_health.html \
    --dataset-metadata training/datasets/prod_combined_20251109/metadata.json \
    --max-duplication-rate 0.005 \
    --min-class-count 200 \
    --max-unknown-labels 0 \
    --require-technique hihat_bark \
    --require-techniques-file configs/health_required_techniques_prod.txt \
    --require-label hihat_open \
    --require-labels-file configs/health_require_labels_example.txt \
    --min-counts-json configs/health_min_counts_example.json
```

For the production dataset we first stitch the source manifests together so
technique gates evaluate the union (Groove alone never hits
`metric_modulation` or `variable_meter`). Generate the aggregated manifest and
feed it into `dataset_health.py` during release prep:

```bash
python tools/merge_manifests.py \
    --input training/data/manifests/groove_events.jsonl \
    --input training/data/manifests/slakh_events.jsonl \
    --output training/data/manifests/prod_combined_events.jsonl

python dataset_health.py \
    --events training/data/manifests/prod_combined_events.jsonl \
    --require-techniques-file training/configs/health_required_techniques_prod.txt
```

This keeps per-source manifests intact for ingestion while giving the health
gate the combined technique coverage it expects.

Sample inputs live in `examples/events_health_example.jsonl`. The report is JSON,
ready to drop into `training_data/health_reports/` or to feed CI gates.

`--min-class-count` enforces a uniform floor across the taxonomy (or all
observed labels); `--min-counts-json` lets you specify bespoke thresholds per
label, and `--require-label` (repeatable) guarantees at least one example for
critical classes. `--require-labels-file` imports newline-separated labels so you
can manage the list in version control, `--max-unknown-labels` guards against
taxonomy drift, and `--require-technique` mirrors the label gate for coverage of
specific playing techniques. Prefer `--require-techniques-file` when the
required set lives in version control (for example,
`configs/health_required_techniques_prod.txt`, which currently enforces
`hihat_bark`, `metric_modulation`, `variable_meter`, and
`multi_cymbal_same_class`). `--html-output` writes a
lightweight summary, and `configs/health_min_counts_example.json` illustrates a
starter threshold map. When you have already materialised clips with
`build_training_dataset.py`, pass the generated `metadata.json` via
`--dataset-metadata` to surface per-split and per-source duration totals in both
the JSON and HTML health summaries.

### Sampling Weights

Per-session weighting artifacts live under `training/sampling/`. After the 11 Nov
2025 crash dual-label refresh, the production pipeline uses
`training/sampling/weights_prod_combined_20251111.json`, which mirrors the JSON
generated by `reports/sampling/prod_combined_weights.json` (49,967 session groups,
7,391,699 counted events, weights clamped to `[0.05, 0.5]`, and 13,079
`crash_dual_label` events). When preparing a training run, feed this file (or the
manifest-specific weights in `reports/sampling/`) into your sampler so batch
probabilities respect the latest distribution. Re-run
`training/tools/derive_sampling_weights.py` and replace the artifact whenever the
manifest or taxonomy changes, then rebuild any cached dataloaders to pick up the
new weights. The post-ingest checklist now defaults weights into
`ai-pipeline/training/reports/sampling/`, keeping refreshed artifacts alongside
other QA outputs.

Use `training/tools/compare_manifests.py` to sanity-check new manifests before
committing them:

```bash
python training/tools/compare_manifests.py \
    ai-pipeline/training/data/manifests/prod_combined_events_pre_crashdual_20251107.jsonl \
    ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
    --json-output reports/health/prod_combined_manifest_diff.json
```

The console summary highlights session/component/technique deltas, and the JSON
payload captures the complete diff for CI review or documentation.

Legacy manifests that predate the taxonomy inference helpers can be patched in
place with `training/tools/annotate_techniques.py`. The script walks existing
events, applies `ingest_utils.apply_taxonomy_inference`, and overwrites (or
writes a new) manifest so readiness gates see the expected techniques without a
full reingestion pass.
The JSON report now embeds `gating_results` and the HTML output lists pass/fail
status for each gate.

After generating reports, compare them against a blessed baseline before
cutting a release:

```bash
python compare_health_reports.py \
    --baseline reports/health/baseline.json \
    --candidate reports/health/latest_health.json \
    --max-drop 25 \
    --ignore-label aux_percussion \
    --json-output reports/health/diff_latest_vs_baseline.json
```

The comparator fails when per-class totals drop beyond `--max-drop`, when the
candidate triggers new gate failures, or when unknown labels increase relative
to the baseline. Use the JSON diff to surface regressions directly in pull
requests or CI dashboards. The `dataset-readiness` workflow publishes the
latest JSON/HTML outputs and diff as artifacts so reviewers can inspect the
changes without rerunning the tooling locally.

### Hyperparameter Sweeps

Use the lightweight grid-search driver to evaluate multiple training settings:

```bash
python training/tools/hparam_sweep.py \
    --dataset training/dev_dataset \
    --batch-sizes 8 16 \
    --epochs 3 5 \
    --learning-rates 0.001 0.0005 \
    --device cuda \
    --output-root training/hparam_runs \
    --report training/reports/hparam_sweep.json
```

Each run invokes `train_classifier.py` with `--metrics-json`, stores models in a
dedicated subdirectory under `training/hparam_runs/`, and aggregates results
into the optional report file. Re-run specific combinations with `--rerun` or
skip completed ones (default).

### 4. Normalize Hi-hat Openness

Calibrate e-drum CC4 values before modeling:

```bash
python normalize_openness.py --events annotations/events.jsonl --output annotations/events_calibrated.jsonl --curves calibration/openness_curves.json
```

Use `--dry-run` to preview how many events are updated. The calibration file hosts vendor curves (`calibration/openness_curves.json`) and should grow as new devices are profiled.

### 5. Use the Trained Model

1. Copy the generated `best_drum_classifier.pth` into `ai-pipeline/models/`.
2. Run the processor; it will automatically pick up the model when present, or specify it explicitly:
   ```bash
   python -m pipeline.process --input song.mp3 --output beatmap.bsm \
       --ml-model models/best_drum_classifier.pth
   ```
3. Environment variables offer further control:
   - `BEATSIGHT_ML_MODEL_PATH` – custom absolute/relative path to the `.pth`
   - `BEATSIGHT_USE_ML_CLASSIFIER=0` – disable ML and fall back to heuristics

## Data Collection Tips

### From Beatmaps
The easiest way to collect data is to use existing beatmaps:

```bash
# Process multiple beatmaps
for file in ../shared/formats/*.bsm; do
    python collect_training_data.py --extract-beatmap "$file" "${file%.bsm}.mp3"
done
```

### Manual Labeling
For precise labeling:

1. Open audio file in Audacity or similar
2. Find drum hit timestamps
3. Add each sample:
   ```bash
   python collect_training_data.py --add-sample audio.mp3 <time> <component>
   ```

### Recommended Data Distribution

For best results, aim for:
- Minimum 100 samples per component
- Balanced distribution across all components
- Variety of sources (different drummers, kits, rooms, recording styles)

| Component | Minimum Samples | Recommended |
|-----------|----------------|-------------|
| kick | 100 | 500+ |
| snare | 100 | 500+ |
| hihat_closed | 150 | 750+ |
| hihat_open | 50 | 250+ |
| crash | 75 | 300+ |
| ride | 75 | 300+ |
| tom_high | 50 | 200+ |
| tom_mid | 50 | 200+ |
| tom_low | 50 | 200+ |

## Model Architecture

The training system supports multiple model architectures, from baseline CNN to cutting-edge designs:

### Available Model Versions

| Version | Architecture | Parameters | Key Features | Recommended |
|---------|--------------|------------|--------------|-------------|
| **v5** 💎 | Ultimate | ~600K-4.5M | CoordAttn + DropPath + DeepSup + MultiScale | ⭐ **DEFAULT** |
| **v4** | CoordAttn | ~500K | Coordinate Attention + Multi-Task | Good fallback |
| **v3** | CBAM | ~450K | Channel + Spatial attention | Legacy |
| **v2** | SE Attention | ~406K | Squeeze-Excitation blocks | Legacy |
| **v1** | Baseline CNN | ~840K | Simple 4-layer CNN | Legacy |
| **beats** 🎵 | BEATs Foundation | ~90M | Microsoft's pretrained audio transformer | Research |

> **⭐ RECOMMENDED**: Use **v5** with balanced sampling for production.
> 
> **Training Paths:**
> - **Local GPU:** `17d-balanced` → `17e-local` → `19` → `19c` (uses UNIFORM balanced sampling)
> - **Cloud GPU:** `17d` → `17e` → `19` → `19c`
> 
> See `docs/PATH_TO_90_PERCENT.md` for current training status.

### V1 Baseline CNN
```
DrumClassifierCNN
├── Conv2D(1→32) + BatchNorm + ReLU + MaxPool
├── Conv2D(32→64) + BatchNorm + ReLU + MaxPool
├── Conv2D(64→128) + BatchNorm + ReLU + MaxPool
├── Conv2D(128→256) + BatchNorm + ReLU + AdaptiveAvgPool
├── Flatten
├── Dropout(0.3)
└── Linear(256→12)

Total Parameters: ~840K
Input: 128x128 mel-spectrogram
Output: 12-class probability distribution
```

### V5 Ultimate Model (⭐ RECOMMENDED DEFAULT)
```bash
# ⭐ This is the recommended training command for 2024
python train_classifier.py --dataset ./dataset \
    --model-version v5 \
    --v5-size medium \
    --drop-path-rate 0.1 \
    --use-deep-supervision \
    --use-gradient-centralization \
    --focal-loss --use-ema --use-sam
```

Features: Coordinate Attention, Stochastic Depth (DropPath), Deep Supervision, Multi-Scale Fusion, Gradient Centralization

**Why V5 is recommended:**
- Best single-model quality (+3-6% over v4)
- Fast inference (2-5ms, same as v4)
- Small model size (2-5MB)
- Your own IP (no external dependencies)
- Works on desktop, mobile, embedded

### BEATs Foundation Model
```bash
python train_classifier.py --dataset ./dataset \
    --model-version beats \
    --beats-freeze-encoder \
    --beats-layer-decay 0.75
```

Uses Microsoft's pretrained BEATs audio transformer for superior feature extraction.

For detailed training paths, see `docs/CUTTING_EDGE_TRAINING_FEATURES.md`.

## Training Tips

### Hyperparameters

| Parameter | Default | Recommended Range | Notes |
|-----------|---------|-------------------|-------|
| Epochs | 50 | 30-100 | Monitor validation loss |
| Batch Size | 32 | 16-64 | Depends on GPU memory |
| Learning Rate | 0.001 | 0.0001-0.01 | Use scheduler |
| Dropout | 0.3 | 0.2-0.5 | Prevent overfitting |

### Preventing Overfitting

- Use data augmentation (time stretching, pitch shifting)
- Increase dropout rate
- Add more training data
- Use early stopping

### GPU Acceleration

Training on GPU is 10-50x faster:

```bash
# Check if CUDA is available
python -c "import torch; print(torch.cuda.is_available())"

# Train with GPU
python train_classifier.py --dataset ./dataset --device cuda --batch-size 64
```

## Advanced Usage

### Data Augmentation

Add augmentation to `DrumSampleDataset.__getitem__()`:

```python
# Time stretching
if random.random() > 0.5:
    audio = librosa.effects.time_stretch(audio, rate=random.uniform(0.9, 1.1))

# Pitch shifting
if random.random() > 0.5:
    audio = librosa.effects.pitch_shift(audio, sr=self.sr, n_steps=random.randint(-2, 2))

# Add noise
if random.random() > 0.5:
    noise = np.random.randn(len(audio)) * 0.005
    audio = audio + noise
```

### Transfer Learning

Start from a pre-trained model:

```python
model = DrumClassifierCNN(num_classes=12)
model.load_state_dict(torch.load("pretrained_model.pth"), strict=False)
```

### Fine-tuning

Freeze early layers and train only the final layers:

```python
# Freeze conv layers
for param in model.conv1.parameters():
    param.requires_grad = False
for param in model.conv2.parameters():
    param.requires_grad = False

# Train only later layers
optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=0.0001)
```

## Evaluation

### Per-class Accuracy

Add to validation function:

```python
from sklearn.metrics import classification_report

# After validation
print(classification_report(all_labels, all_predictions, target_names=component_names))
```

### Confusion Matrix
### Additional QA Reports

The dataset readiness plan defines acceptance gates that depend on the utilities above. Summaries from `align_qc.py`, `boundary_eval.py`, `openset_eval.py`, and `bootstrap_eval.py` should be stored under `training_data/health_reports/` or `reports/<version>/` and referenced when approving a release.


```python
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

cm = confusion_matrix(all_labels, all_predictions)
plt.figure(figsize=(12, 10))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=component_names, yticklabels=component_names)
plt.xlabel('Predicted')
plt.ylabel('True')
plt.title('Drum Classifier Confusion Matrix')
plt.savefig('confusion_matrix.png')
```

## Distributed Training (Future)

For community-driven model training:

1. Contributors run training client
2. Central server aggregates gradients
3. Improved model distributed to all

See `ROADMAP.md` Phase 4 for details.

## Troubleshooting

### Low Accuracy
- Check data distribution (balanced?)
- Increase training data
- Add data augmentation
- Tune hyperparameters

### Overfitting
- Validation accuracy much lower than training?
- Increase dropout
- Add L2 regularization
- Reduce model complexity

### Out of Memory
- Reduce batch size
- Use mixed precision training
- Reduce input size

## References

- [Drum transcription survey](https://arxiv.org/abs/1806.06676)
- [ENST-Drums database](http://www.telecom-paristech.fr/~grichard/ENST-drums/)
- [PyTorch audio tutorial](https://pytorch.org/audio/stable/tutorials/audio_classification_tutorial.html)

## Contributing

See `docs/CONTRIBUTING.md` for guidelines on contributing training data and model improvements.
