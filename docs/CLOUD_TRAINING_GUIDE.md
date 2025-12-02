# BeatSight Cloud Training Guide

## Overview

This guide covers running the full V5 training pipeline on **Lambda Labs** with an A100 40GB GPU.

> **Important Architecture Decision:**
> - **Training:** Lambda Labs (A100 GPUs, hourly billing, persistent instances)
> - **Production Inference:** Modal.com (serverless, pay-per-second, auto-scaling)
> 
> Lambda Labs is for training because it offers persistent instances for long training runs.
> Modal is for production because it scales to zero and has sub-second billing.
> See `docs/MODEL_SECURITY.md` for how models are securely deployed to Modal.

**Pipeline:** `14 → 17a → 17d → 17e → 19 (local) → 19c`

| Step | Name | Where | Time | Description |
|------|------|-------|------|-------------|
| **14** | Label Audit | Local | ~30 min | Confident learning noise detection to find mislabeled samples |
| **17a** | V5 Warmup | Cloud | ~1.5 hr | Validate all innovations work |
| **17d** | V5 Full | Cloud | ~22 hr | 300 epochs, **V5-Large** for maximum quality |
| **17e** | V5 Self-Distill | Cloud | ~22 hr | Born-Again Networks (+1-2%) |
| **19** | Multilabel Generate | **Local** | ~30 min | Generate multilabel dataset (CPU only) |
| **19c** | Multilabel Finetune | Cloud | ~5 hr | Fine-tune for simultaneous detection |

**Single-Tier Strategy (NEW):**
> We use **V5-Large + INT8 quantization** for production. This gives:
> - Maximum accuracy from V5-Large model
> - Fast inference from INT8 quantization (3-4x speedup)
> - No quality/speed tradeoffs - best of both worlds!

**Key Training Features:**
- **V5-Large model** (single-tier, maximum quality)
- **300 epochs** (17d/17e) for maximum convergence
- **K-fold label audit** (step 14) for +0.5-1% more noise detection
- **Technique heads** enabled for flam/roll/choke/ghost detection
- **Warm restarts** with T0=40 for optimal learning rate cycling
- **23 SOTA techniques** including SAM, SWA, EMA, FMix, R-Drop, Curriculum
- **TTA validation** enabled for accurate training progress

**Estimated Cost:** ~$68-72 total
- Upload: ~$2.84
- Training: ~$65-68

---

## 🎯 Recommended Instance

Based on current Lambda Labs availability (Dec 2025):

| Instance | Price | VRAM | Recommendation |
|----------|-------|------|----------------|
| **1x A100 40GB PCIe** | **$1.29/hr** | 40GB | ✅ **BEST VALUE** |
| 1x A10 24GB | $0.75/hr | 24GB | ⚠️ May need smaller batch |
| 1x H100 80GB PCIe | $2.49/hr | 80GB | Overkill for single-GPU training |
| 1x GH200 96GB | $1.49/hr | 96GB | ARM64 - compatibility unknown |

---

## 🎉 GPU Auto-Detection

The `auto_train.sh` script **automatically detects your GPU** and configures optimal settings:

```
🖥️  GPU Detected: NVIDIA A100 80GB (80GB VRAM)
⚙️  Auto-configured: batch=512, workers=8/4, amp=bfloat16
📊 Expected speed: ~18-22 it/s
```

### Supported GPUs

| GPU | Batch Size | Workers | AMP | Expected it/s |
|-----|------------|---------|-----|---------------|
| H100 | 640 | 8/4 | bfloat16 | 25-35 |
| A100 80GB | 512 | 8/4 | bfloat16 | 18-22 |
| A100 40GB | 448 | 8/4 | bfloat16 | 15-18 |
| V100 32GB | 384 | 8/4 | float16 | 8-12 |
| RTX 4090 | 512 | 4/2 | float16 | 10-15 |
| RTX 3090 | 448 | 3/2 | float16 | 3-5 |
| RTX 3080 Ti | 384 | 2/1 | float16 | 1.5-2 |

Override with environment variables:
```bash
export BEATSIGHT_BATCH_SIZE=512
export BEATSIGHT_NUM_WORKERS=8
```

---

## ⚠️ Critical: Reserve Holdout Test Set

**Before training, ensure holdout sources are reserved for final evaluation.**

Holdout sources (NEVER use in training/validation):
- **ENST-Drums** - Real recordings with annotations
- **MDB-Drums** - Professional multi-track recordings

Training sources (OK to use):
- Groove MIDI, E-GMD, Slakh, IDMT, Cambridge

See: `ai-pipeline/training/configs/holdout_test_sources.json`

This gives you TRUE generalization metrics, not optimistic validation accuracy.

---

## Prerequisites (Run Locally BEFORE Cloud)

### 0. Pre-flight Check - ⭐ REQUIRED BEFORE RENTING INSTANCE

**Run this to catch ALL errors before spending money on cloud compute:**

```bash
# From project root with PYTHONPATH set
cd /path/to/BeatSight
source ai-pipeline/training/tools/post_export_commands.sh
# Then select 'pre' from menu

# Or run directly:
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/preflight_check.py
```

This validates:
- ✅ Python syntax in all 160+ training files
- ✅ All required dependencies are installed
- ✅ Training imports work correctly
- ✅ Model instantiation (V5 small/medium/large)
- ✅ auto_train.sh shell syntax

**If ANY check fails, fix it before renting a Lambda Labs instance!**

### 1. K-Fold Label Audit (Step 14) - RECOMMENDED

K-fold cross-validation finds +0.5-1% more noisy labels than single-fold:

```bash
# Option A: Enhanced K-fold audit (recommended, ~2.5 hours)
python ai-pipeline/training/tools/kfold_label_audit.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index" \
    --feature-cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --output ai-pipeline/training/runs/cutting_edge/audits \
    --k 5 \
    --epochs 15

# Option B: Standard single-fold audit (faster, ~30 minutes)
bash ai-pipeline/training/tools/auto_train.sh label-audit
```

The K-fold audit flags samples that multiple models agree are mislabeled = higher confidence.

### 2. Rotate AWS Credentials

If credentials were ever exposed, rotate them before cloud training.

### 3. Have Your S3 Bucket Ready

`s3://beatsight-checkpoints/`

### 4. Generate Multilabel Dataset (Step 19) - Do Before 19c

**This step runs locally (CPU only) and must complete before step 19c:**

```bash
# Generate multilabel dataset from MIDI-aligned sources (~30 min)
python ai-pipeline/training/tools/generate_multilabel_dataset.py \
    --merge-window-ms 30 \
    --output "${BEATSIGHT_OUTPUT_ROOT:-E:/data}/multilabel_dataset" \
    --verbose
```

This creates `multilabel_events.jsonl` needed for step 19c.

---

## Upload Time Estimate

Based on 520 Mbps upload speed:

| Data | Size | Time |
|------|------|------|
| `feature_cache/` | 501 GB | ~2.1 hours |
| `dataset_index/` | 15 GB | ~4 minutes |
| **Total** | 516 GB | **~2.2 hours** |

**Upload cost:** 2.2 hrs × $1.29/hr = **~$2.84**

> 💡 With 520 Mbps upload, don't bother compressing - the time to compress would be longer than you'd save on transfer.

---

## Full Lambda Labs Workflow

### Step 1: Launch Instance

1. Go to [Lambda Labs Cloud](https://cloud.lambdalabs.com/)
2. Select **A100 40GB** ($1.29/hr)
3. Launch and note the IP address (`LAMBDA_IP`)

### Step 2: Upload Data (from Windows Git Bash)

```bash
# Replace LAMBDA_IP with your instance's IP

# Upload feature cache (~2 hours)
rsync -avP --progress /c/github/BeatSight/data/feature_cache/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/feature_cache/

# Upload dataset index (~4 min)
rsync -avP --progress /c/github/BeatSight/data/dataset_index/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/dataset_index/

# Upload multilabel dataset (if generated locally)
rsync -avP --progress /e/data/multilabel_dataset/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/multilabel_dataset/
```

### Step 3: SSH into Lambda Instance

```bash
ssh ubuntu@LAMBDA_IP
```

### Step 4: Clone Repo & Install Dependencies

```bash
git clone https://github.com/rosacry/BeatSight.git
cd BeatSight/ai-pipeline && pip install -r requirements.txt && cd ..
```

### Step 5: Set Environment Variables

```bash
export BEATSIGHT_DATA_ROOT=/home/ubuntu/beatsight_data
export BEATSIGHT_CACHE_DIR=/home/ubuntu/beatsight_data/feature_cache
export BEATSIGHT_DATASET_DIR=/home/ubuntu/beatsight_data/feature_cache
export BEATSIGHT_OUTPUT_ROOT=/home/ubuntu/beatsight_data
```

### Step 6: Configure AWS for Checkpoint Backup

```bash
aws configure
# Access Key ID: [YOUR_KEY]
# Secret Access Key: [YOUR_SECRET]
# Default region: us-east-1
# Default output: json

export REMOTE_BACKUP_PATH='s3://beatsight-checkpoints/'
```

### Step 7: Start Training!

```bash
./ai-pipeline/training/tools/cloud_training.sh start-session
```

This creates a tmux session with:
- **Window 0 (training):** Main training pipeline
- **Window 1 (watchdog):** GPU idle monitor (auto-shutdown if idle 30+ min)
- **Window 2 (sync):** Checkpoint sync to S3 every 30 min
- **Window 3 (gpu):** Live nvidia-smi
- **Window 4 (logs):** Training log tail

---

## tmux Commands

| Command | Action |
|---------|--------|
| `Ctrl+B, D` | Detach (training continues) |
| `Ctrl+B, N` | Next window |
| `Ctrl+B, P` | Previous window |
| `Ctrl+B, 0-4` | Jump to specific window |
| `tmux attach -t beatsight` | Reattach to session |

---

## After Training Completes

> **📖 Complete Guide:** See [POST_TRAINING_OPTIMIZATION_GUIDE.md](POST_TRAINING_OPTIMIZATION_GUIDE.md) for the full post-training workflow including FP8, EPContext, Sparsity, and Early Exit optimizations.

### 1. Download Checkpoints

```bash
# Instance auto-shuts down after training completes
# Checkpoints are in S3: s3://beatsight-checkpoints/
aws s3 sync s3://beatsight-checkpoints/ ./checkpoints/
```

### 2. Run Holdout Evaluation (Critical!)

**This gives TRUE generalization metrics on never-seen data:**

```bash
# Evaluate on holdout test set (ENST + MDB-Drums)
python ai-pipeline/training/tools/evaluate_holdout.py \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --holdout-cache data/feature_cache_holdout \
    --output results/holdout_evaluation \
    --tta --tta-augmentations 5 \
    --compare-validation checkpoints/v5/self-distill/metrics.json
```

Expected output:
```
GENERALIZATION COMPARISON
Validation accuracy: 96.5%
Holdout accuracy:    94.2%
Generalization gap:  2.3%
Interpretation:      good (<2% is excellent, 2-5% is good)
```

### 3. Export for Production (Static INT8)

Export with **Static INT8 Quantization** for maximum speed:

```bash
# Step 1: Generate calibration data from your training cache (~1000 samples)
python -m training.inference.production_optimizations \
    --mode calibrate \
    --cache-dir /home/ubuntu/beatsight_data/feature_cache \
    --output calibration_data.npy \
    --n-samples 1000

# Step 2: Export with static INT8 quantization
python -m training.inference.production_optimizations \
    --mode export \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --cache-dir calibration_data.npy \
    --output models/drum_classifier_static_int8.onnx
```

**Production Speed:**

| What You Get | Speed |
|--------------|-------|
| Static INT8 + IO Binding + torch.compile | **~7-10ms/sample** |

That's **5-7× faster** than baseline PyTorch (~50ms). This is your production model.

See `ai-pipeline/training/inference/production_optimizations.py` for details.

---

## 🚀 Production Model Export

After training completes, export optimized models for Modal deployment.

### Quick Export (Recommended)

```bash
# One command exports all optimized variants
python -m training.scripts.export_production \
    --checkpoint /workspace/outputs/best_model.pth \
    --output-dir /workspace/outputs/production \
    --cache-dir /workspace/feature_cache \
    --v5-size large \
    --with-sparsity \
    --with-fp8

# This creates:
# 1. drum_classifier_static_int8.onnx  - Base production (required)
# 2. drum_classifier_epcontext.onnx    - Instant cold starts (if TensorRT available)
# 3. drum_classifier_sparse_trt.onnx   - 2:4 sparse variant (2x faster compute)
# 4. drum_classifier_fp8.trt           - FP8 variant (2x faster than INT8 on H100/L40S)
```

### Upload to Modal

```bash
# Upload all production models
modal volume put beatsight-models /workspace/outputs/production /models/

# Redeploy to pick up new models
modal deploy modal_app.py
```

### Speed Comparison

| Model Variant | Inference Speed | Cold Start | When to Use |
|---------------|-----------------|------------|-------------|
| **Static INT8** | ~7-10ms | 30-60s | ✅ Default production |
| + EPContext | ~7-10ms | **<2s** | If cold starts matter |
| + 2:4 Sparsity | **~4-6ms** | <2s | Maximum throughput |
| + FP8 (NEW!) | **~2-3ms** | <2s | 🚀 **REVOLUTIONARY** - H100/L40S only |

> **💡 TIP:** Deploy on Modal's **L40S** ($1.95/hr) for FP8 support at half the H100 price!
> The L40S has native FP8 support and gives you ~2-3ms inference.

---

## 🔧 Advanced Optimizations (Optional)

> These are **additional layers** you can apply on top of your Static INT8 model.

```
Static INT8              ← Your production model (required)
       ↓
  + EPContext            ← Faster cold starts (optional add-on)
       ↓
  + 2:4 Sparsity         ← Faster compute (optional add-on)
```

### Add-on: EPContext (Instant Cold Starts)

Pre-compile TensorRT engine and embed it. Eliminates 30-60s engine build on Modal cold starts.

```bash
# Automatically included in export_production if TensorRT is available
# Or run manually:
python -m training.inference.advanced_optimizations export-embedded \
    --onnx models/drum_classifier_static_int8.onnx \
    --output models/drum_classifier_epcontext.onnx \
    --precision int8
```

| Metric | Static INT8 | + EPContext |
|--------|-------------|-------------|
| Cold start | 30-60 seconds | **<2 seconds** |
| Inference | ~7-10ms | ~7-10ms (same) |

### Add-on: 2:4 Sparsity (2x Faster Compute)

NVIDIA Ampere+ GPUs have hardware-accelerated sparse compute.

```bash
# Export with sparsity
python -m training.scripts.export_production \
    --checkpoint best_model.pth \
    --output-dir production/ \
    --with-sparsity

# Or apply sparsity manually
python -m training.inference.advanced_optimizations apply-sparsity \
    --checkpoint best_model.pth \
    --output sparse_model.pth \
    --export-onnx sparse_model.onnx
```

| Metric | Static INT8 | + 2:4 Sparsity |
|--------|-------------|----------------|
| Inference | ~7-10ms | **~4-6ms** |
| Accuracy loss | 0% | <0.5% |

### Benchmark All Configurations

```bash
# Test all optimization levels
python -m training.inference.advanced_optimizations benchmark \
    --onnx models/drum_classifier_static_int8.onnx
```

See `ai-pipeline/training/inference/advanced_optimizations.py` for full implementation.

---

## 🚀 Revolutionary Optimizations (Cutting-Edge)

> **NEW!** These are bleeding-edge optimizations that push beyond the standard stack.

The revolutionary optimizations module (`revolutionary_optimizations.py`) adds:

### 1. FP8 Quantization (Available Now on Modal!)

**2× faster than INT8** on NVIDIA Hopper/Ada GPUs:

```bash
# Check if FP8 is available on your hardware
python -m training.inference.revolutionary_optimizations check

# Export with FP8 (requires L40S, H100, H200, B200, or RTX 4090)
python -m training.inference.revolutionary_optimizations export \
    --checkpoint best_model.pth \
    --output-dir models/ \
    --enable-fp8
```

**Modal GPU Pricing (for production - Dec 2025):**

| GPU | Price/sec | Price/hr | FP8? | Inference | Recommendation |
|-----|-----------|----------|------|-----------|----------------|
| B200 | $0.001736 | $6.25 | ✅ Yes | ~2ms | Overkill |
| H200 | $0.001261 | $4.54 | ✅ Yes | ~2ms | Overkill (141GB VRAM) |
| H100 | $0.001097 | $3.95 | ✅ Yes | ~2-3ms | Max speed |
| **L40S** | **$0.000542** | **$1.95** | ✅ Yes | **~2-3ms** | ⭐ **BEST VALUE** |
| A100 | $0.000583 | $2.10 | ❌ No | ~5-7ms | Not recommended |
| A10 | $0.000306 | $1.10 | ❌ No | ~4-6ms | Budget option |
| L4 | $0.000222 | $0.80 | ❌ No | ~6-8ms | Cheapest viable |

**⭐ Recommendation: L40S** - FP8 support at half the H100 price! Ada Lovelace (sm_89) architecture.

### 2. Flash Attention v2 (Ampere+ GPUs)

**2-4× faster attention** with O(N) memory instead of O(N²):

```bash
# Install flash-attn
pip install flash-attn --no-build-isolation

# Flash Attention is auto-applied during export
python -m training.inference.revolutionary_optimizations export \
    --checkpoint best_model.pth \
    --output-dir models/
```

### 3. Fused CUDA Kernels

**20-40% additional speedup** by fusing Conv+BN+SiLU operations:

```bash
# Automatically applied during export (fuses BN into Conv weights)
python -m training.inference.revolutionary_optimizations export \
    --checkpoint best_model.pth \
    --output-dir models/
```

### 4. GPU-Native Spectrograms

**30% faster preprocessing** by computing mel-spectrograms on GPU:

```python
from training.inference.revolutionary_optimizations import GPUMelSpectrogram

# Replace librosa with GPU-native computation
gpu_mel = GPUMelSpectrogram(sample_rate=44100, n_mels=128)
mel_spec = gpu_mel(waveform.cuda())  # Entire computation on GPU
```

### Complete Speed Stack

```
Baseline PyTorch:           ~50ms/sample
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Static INT8:                ~7-10ms/sample   ← Current production (A10G)
+ 2:4 Sparsity:             ~4-6ms/sample    ← With hardware sparsity
+ Flash Attention:          ~3-5ms/sample    ← Available on Ampere+
+ FP8 (H100):               ~2-3ms/sample    ← Available NOW on Modal!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total potential speedup:    **17-25× faster** than baseline
```

See `ai-pipeline/training/inference/revolutionary_optimizations.py` for full implementation.

---

## Cost Breakdown

| Phase | Time (A100) | Cost |
|-------|-------------|------|
| Upload | ~2.2 hr | $2.84 |
| v5-warmup (17a) | ~1.5 hr | $1.94 |
| v5-full (17d, 300 epochs) | ~22 hr | $28.38 |
| v5-self-distill (17e, 300 epochs) | ~22 hr | $28.38 |
| multilabel-finetune (19c) | ~5 hr | $6.45 |
| **Total** | **~53 hr** | **~$68** |

> 💡 **Note:** Step 19 (multilabel-generate) runs locally and costs $0.

> 💡 **Note:** 300 epochs (up from 200) provides +0.3-0.5% accuracy improvement. The extra ~$17 cost is worthwhile for maximum quality.

---

## Training Pipeline Improvements

### TTA Validation (Enabled by Default)

During training, validation uses Test-Time Augmentation for accurate progress tracking:
- 3-5 augmented views per sample
- Averaged predictions in probability space
- More reliable accuracy estimates

### K-Fold Label Audit Benefits

| Method | Issues Found | Time | Confidence |
|--------|--------------|------|------------|
| Single-fold | ~2.5% of samples | ~30 min | Medium |
| K=5 fold | ~3.5% of samples | ~2.5 hr | High |

Samples flagged by multiple folds are high-confidence errors.

### INT8 Quantization for Production

After training, export with INT8 quantization:

| Format | Size | Speed | Accuracy |
|--------|------|-------|----------|
| FP32 | 100% | 1× | 100% |
| FP16 | 50% | 1.5× | 99.9% |
| **INT8** | **25%** | **3-4×** | **99.5%** |

INT8 is ideal for production with minimal accuracy loss.

---

## Troubleshooting

### Connection dropped during upload
```bash
# rsync automatically resumes - just run the same command again
rsync -avP --progress /c/github/BeatSight/data/feature_cache/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/feature_cache/
```

### Check training progress after detaching
```bash
ssh ubuntu@LAMBDA_IP
tmux attach -t beatsight
```

### Cancel auto-shutdown
```bash
sudo shutdown -c
```

### Manually sync checkpoints
```bash
./ai-pipeline/training/tools/cloud_training.sh sync-once
```

### Check current cost
```bash
./ai-pipeline/training/tools/cloud_training.sh cost-estimate
```

### Step 19c fails: "Multi-label dataset not found"

You need to run step 19 locally first:
```bash
# On your local machine (not cloud)
python ai-pipeline/training/tools/generate_multilabel_dataset.py \
    --output "${BEATSIGHT_OUTPUT_ROOT:-E:/data}/multilabel_dataset"

# Then upload to cloud
rsync -avP /e/data/multilabel_dataset/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/multilabel_dataset/
```

### OOM Errors
```bash
# Reduce batch size
--batch-size 384  # or even 256
```

### Slow Data Loading
```bash
# Check disk I/O
iostat -x 1

# If slow, data may be on network storage
# Move to local NVMe: /home/ubuntu/beatsight_data/
```

### Training Stalls
```bash
# Check for zombie processes
ps aux | grep python

# Kill and restart
pkill -9 python
bash ai-pipeline/training/tools/auto_train.sh v5-full
```

---

## Cloud vs Local Comparison

| Metric | Local (RTX 3080 Ti) | Cloud (A100 40GB) | Improvement |
|--------|---------------------|-------------------|-------------|
| v5-warmup | ~20 hr | ~1.5 hr | 13x faster |
| v5-full | ~200 hr | ~22 hr | 9x faster |
| v5-self-distill | ~200 hr | ~22 hr | 9x faster |
| multilabel-finetune | ~60 hr | ~5 hr | 12x faster |
| **TOTAL TIME** | **~480 hr** | **~53 hr** | **9x faster** |
| **Wall Clock** | ~20 days | ~2.5 days | 17 days saved |

**ROI**: ~$68 to save 17+ days of training time = **$4/day saved**

---

## 📊 Monitoring

### GPU Monitoring
```bash
# Watch GPU utilization
watch -n 1 nvidia-smi

# Should see:
# - GPU Util: 95-100%
# - Memory: ~35-38 GB used (A100 40GB)
# - Power: ~350-400W
```

### WandB Sync (after training)
```bash
# Sync offline runs to WandB
wandb sync /home/ubuntu/beatsight/wandb/
```

---

## 🎯 Expected Results

After completing all phases:

| Model | Location | Expected Accuracy |
|-------|----------|-------------------|
| V5 Full | `runs/cutting_edge/v5/full/best_drum_classifier.pth` | 94-96% |
| V5 EMA | `runs/cutting_edge/v5/full/best_drum_classifier_ema.pth` | 94.5-96.5% |
| Self-Distill | `runs/cutting_edge/v5/self-distill/best_drum_classifier.pth` | 95-97% |
| Multi-Label | `runs/cutting_edge/multilabel/finetune/best_multilabel_model.pt` | 90-93% (F1) |

---

## Quick Reference: Complete Workflow

```bash
# === LOCAL (Before cloud) ===

# 1. Pre-flight check (catch errors before renting!)
PYTHONPATH=ai-pipeline python ai-pipeline/training/tools/preflight_check.py

# 2. Label Audit (recommended, ~30 min)
python ai-pipeline/training/tools/label_audit.py \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --output ai-pipeline/training/runs/cutting_edge/audits

# 3. Generate multilabel dataset (~30 min)
python ai-pipeline/training/tools/generate_multilabel_dataset.py \
    --output E:/data/multilabel_dataset

# === CLOUD ===

# 4. Upload data + start training
rsync -avP /c/github/BeatSight/data/feature_cache/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/feature_cache/
rsync -avP /e/data/multilabel_dataset/ ubuntu@LAMBDA_IP:/home/ubuntu/beatsight_data/multilabel_dataset/
ssh ubuntu@LAMBDA_IP
./ai-pipeline/training/tools/cloud_training.sh start-session

# === LOCAL (After cloud) ===

# 5. Download checkpoints
aws s3 sync s3://beatsight-checkpoints/ ./checkpoints/

# 6. Evaluate on holdout test set
python ai-pipeline/training/tools/evaluate_holdout.py \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output results/holdout_evaluation

# 7. Export for production (INT8 quantization)
python -m training.export.onnx_export \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output models/drum_classifier_int8.onnx \
    --quantize int8

# 8. (Optional) Create distilled model variants for tiered deployment
python -m training.tools.distill_model \
    --teacher checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output models/weights/ \
    --variant all \
    --epochs 50
```

---

## 🚀 Production Optimization (Post-Training)

After training completes, apply these optimizations for production deployment:

### Inference Speed Targets

| Configuration | Time (3-min song) | Speedup |
|---------------|-------------------|---------|
| Baseline (PyTorch) | ~35s | 1x |
| + Hybrid Demucs | ~20s | 1.75x |
| + ONNX Runtime | ~12s | 2.9x |
| + TensorRT FP16 | ~10s | 3.5x |
| + Spectrogram Cache | ~8s | 4.4x (cached) |

### Export Commands

```bash
# 1. Export to ONNX with FP16
python -m training.export.onnx_export \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output models/v5_full.onnx \
    --quantize fp16

# 2. Create distilled variants
python -m training.tools.distill_model \
    --teacher checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output models/weights/ \
    --variant distilled \
    --epochs 50

python -m training.tools.distill_model \
    --teacher checkpoints/v5/self-distill/best_drum_classifier.pth \
    --output models/weights/ \
    --variant tiny \
    --epochs 30

# 3. Benchmark optimized pipeline
python -m training.inference.optimized_pipeline \
    --audio test_song.mp3 \
    --benchmark
```

> **📖 For complete post-training optimization steps, see: [POST_TRAINING_OPTIMIZATION_GUIDE.md](POST_TRAINING_OPTIMIZATION_GUIDE.md)**

### Model Variants for Deployment

| Variant | Params | Accuracy | Use Case |
|---------|--------|----------|----------|
| V5-Full | ~15M | 100% (baseline) | Pro/API tier |
| V5-Distilled | ~7.5M | ~95% | Basic tier |
| V5-Tiny | ~3.7M | ~90% | Free tier |

### Optimization Components (Implemented)

```
ai-pipeline/
├── separation/
│   └── demucs_separator.py       # Hybrid Demucs (htdemucs_ft) support
├── training/
│   ├── inference/
│   │   ├── tensorrt_inference.py # TensorRT/ONNX acceleration
│   │   └── optimized_pipeline.py # Combined optimized pipeline
│   └── tools/
│       ├── spectrogram_cache.py  # Spectrogram caching
│       └── distill_model.py      # Model distillation
```

---

## 📝 Cost Tracking Template

Keep a log of your sessions:

| Date | Instance | Duration | Cost | Phase Completed |
|------|----------|----------|------|-----------------|
| Dec 1 | A100 40GB | 2.2h | $2.84 | Upload |
| Dec 1 | A100 40GB | 23.5h | $30.32 | v5-warmup, v5-full |
| Dec 2 | A100 40GB | 27h | $34.83 | self-distill, multilabel |
| Dec 3 | A100 40GB | 12h | $15.48 | distillation (optional) |
| **TOTAL** | | **~53-65h** | **~$68-83** | ✅ All phases |

---

## 🔧 Optimization Summary

After completing training, your production deployment will support:

1. **Hybrid Demucs** (`htdemucs_ft`) - 2.5x faster drum separation
2. **TensorRT/ONNX Runtime** - 2-4x faster classification  
3. **Spectrogram Caching** - 30% speedup on repeated requests
4. **Skip Separation Detection** - 60% faster for isolated drum tracks
5. **Model Distillation** - V5-Tiny/Distilled for tiered offerings

**Target Processing Times:**
- Free tier (V5-Tiny): ~25s for 3-min song
- Basic tier (V5-Distilled): ~18s
- Pro tier (V5-Full): ~15s  
- API tier (V5-Full + TensorRT): ~12s

---

## 🚀 Next Steps: Post-Training Optimization

After training completes, follow the **[POST_TRAINING_OPTIMIZATION_GUIDE.md](POST_TRAINING_OPTIMIZATION_GUIDE.md)** for:

1. **Holdout evaluation** - Get TRUE generalization metrics
2. **Static INT8 export** - Base production model (~7-10ms)
3. **FP8 TensorRT export** - 2x faster on L40S/H100 (~2-3ms)
4. **EPContext export** - Instant cold starts (<2s)
5. **2:4 Sparsity training** - Additional 2x compute speedup
6. **Early Exit export** - +20-50% speedup on easy samples
7. **Modal deployment** - Upload and deploy to production

These optimizations can make your model **3-5x faster** with **no accuracy loss**!

---

*Last Updated: December 2025*

