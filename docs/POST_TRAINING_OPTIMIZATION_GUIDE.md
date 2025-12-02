# BeatSight Post-Training Optimization Guide

## Overview

This guide covers **everything you need to do AFTER training completes** to achieve maximum production performance. Run these steps after completing the training pipeline (`14 → 17a → 17d → 17e → 19 → 19c`).

> **Goal:** Transform your trained V5-Large model into a **2-3ms/sample** production beast
> while maintaining maximum accuracy.

**What You'll Achieve:**

| Metric | Before Optimization | After Optimization |
|--------|--------------------|--------------------|
| Inference Speed | ~50ms/sample | **~2-3ms/sample** |
| Cold Start | 30-60 seconds | **<2 seconds** |
| Model Size | ~12MB (FP32) | **~3MB (INT8)** |
| Compute Cost | $0.02-0.03/song | **$0.006-0.01/song** |

---

## 📋 Post-Training Checklist

After training completes, follow this checklist in order:

```
□ Step 1: Download checkpoints from S3
□ Step 2: Evaluate on holdout test set (CRITICAL!)
□ Step 3: Export Static INT8 ONNX (base production model)
□ Step 4: Export FP8 TensorRT (2x faster on L40S/H100)
□ Step 5: Export EPContext (instant cold starts)
□ Step 6: (Optional) Train 2:4 Sparsity variant
□ Step 7: (Optional) Export Early Exit variant
□ Step 8: Upload to Modal and deploy
□ Step 9: Benchmark production performance
```

---

## Step 1: Download Checkpoints from S3

After cloud training auto-shuts down, your checkpoints are in S3:

```bash
# From your local machine
aws s3 sync s3://beatsight-checkpoints/ ./checkpoints/

# Verify the key files exist:
ls -la checkpoints/v5/self-distill/
# Expected:
#   best_drum_classifier.pth      (~12 MB)
#   best_drum_classifier_ema.pth  (~12 MB)
#   metrics.json
#   training_log.jsonl
```

**Best checkpoint to use:** `best_drum_classifier_ema.pth` (EMA typically has +0.2-0.5% better accuracy)

---

## Step 2: Evaluate on Holdout Test Set (CRITICAL!)

**This gives TRUE generalization metrics on never-seen data.**

Your validation accuracy during training is optimistic. The holdout test set (ENST-Drums + MDB-Drums) was **never used** during training or validation.

```bash
# Set up environment
cd /path/to/BeatSight
export PYTHONPATH=ai-pipeline

# Run holdout evaluation with TTA
python ai-pipeline/training/tools/evaluate_holdout.py \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --holdout-cache data/feature_cache_holdout \
    --output results/holdout_evaluation \
    --tta \
    --tta-augmentations 5 \
    --compare-validation checkpoints/v5/self-distill/metrics.json \
    --technique-heads \
    --velocity-labels
```

**Expected Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GENERALIZATION COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Validation accuracy (training): 96.5%
Holdout accuracy (test):        94.2%
Generalization gap:             2.3%
Interpretation:                 GOOD (<2% is excellent, 2-5% is good)

Per-Class Performance:
  Kick:        96.8%
  Snare:       95.2%
  Hi-Hat:      93.1%
  Tom:         91.5%
  Crash:       94.7%
  Ride:        92.3%
  ...

Technique Detection:
  Flam:        88.2%
  Roll:        85.6%
  Ghost:       82.1%
  Choke:       91.3%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If generalization gap is >5%:** Your model may be overfitting. Consider:
- More aggressive augmentation in next training run
- Reducing model size
- Adding more regularization

---

## Step 3: Export Static INT8 ONNX (Base Production Model)

This is your **required** base production model. All other optimizations build on this.

### 3.1: Generate Calibration Data

Static INT8 quantization needs representative samples to compute optimal scale factors:

```bash
python -m training.inference.production_optimizations \
    --mode calibrate \
    --cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --output checkpoints/v5/calibration_data.npy \
    --n-samples 1000
```

### 3.2: Export with Static INT8 Quantization

```bash
python -m training.inference.production_optimizations \
    --mode export \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --cache-dir checkpoints/v5/calibration_data.npy \
    --output models/production/drum_classifier_static_int8.onnx
```

### 3.3: Verify the Export

```bash
# Check file size (should be ~3MB for INT8)
ls -lh models/production/drum_classifier_static_int8.onnx

# Quick inference test
python -c "
import onnxruntime as ort
import numpy as np

session = ort.InferenceSession('models/production/drum_classifier_static_int8.onnx')
dummy = np.random.randn(1, 1, 128, 128).astype(np.float32)
output = session.run(None, {'input': dummy})
print(f'Output shape: {output[0].shape}')
print(f'Model loaded successfully!')
"
```

**Result:** `drum_classifier_static_int8.onnx` (~3MB, ~7-10ms/sample)

---

## Step 4: Export FP8 TensorRT (2x Faster on L40S/H100)

FP8 provides **2x speedup** over INT8 on NVIDIA Ada/Hopper GPUs (L40S, H100).

> **Note:** This step requires running on a machine with L40S/H100 GPU and TensorRT installed.
> You can do this on Lambda Labs or Modal.

### 4.1: Check FP8 Support

```bash
python -m training.inference.revolutionary_optimizations check
```

**Expected Output (on L40S):**
```
══════════════════════════════════════════════════════════════
Revolutionary Optimization Support Report
══════════════════════════════════════════════════════════════
GPU: NVIDIA L40S (48.0 GB)
Compute Capability: sm_89

Optimization Availability:
  FP8 Quantization:    ✓ Ada Lovelace (sm_89) supports FP8
  Flash Attention v2:  ✓ sm_80+ detected
  Fused CUDA Kernels:  ✓ Triton available
  GPU Spectrograms:    ✓ CUDA available
══════════════════════════════════════════════════════════════
```

### 4.2: Export FP8 TensorRT Engine

```bash
# On Lambda Labs or Modal with L40S/H100
python -m training.inference.revolutionary_optimizations export \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --output-dir models/production/ \
    --enable-fp8 \
    --calibration-data checkpoints/v5/calibration_data.npy
```

**Result:** `drum_classifier_fp8.trt` (~3MB, ~2-3ms/sample on L40S)

---

## Step 5: Export EPContext (Instant Cold Starts)

EPContext embeds a pre-compiled TensorRT engine in the ONNX file, eliminating the 30-60 second engine build time on cold starts.

> **Note:** This step also requires running on a Linux machine with TensorRT.

```bash
# On Lambda Labs or Modal
python -m training.inference.advanced_optimizations export-embedded \
    --onnx models/production/drum_classifier_static_int8.onnx \
    --output models/production/drum_classifier_epcontext.onnx \
    --precision int8 \
    --batch-sizes 1,8,16,32,64
```

**Result:** `drum_classifier_epcontext.onnx` (~15-20MB with embedded engine, <2s cold start)

---

## Step 6: Train 2:4 Sparsity Variant (RECOMMENDED)

2:4 structured sparsity provides **2x compute speedup** on Ampere+ GPUs with minimal accuracy loss.

> **Time:** ~30 minutes for fine-tuning on H100
> **Cost:** ~$1.25 on Lambda Labs  
> **Accuracy Loss:** <0.5%
> **Speed Gain:** 2x faster compute → ~4-6ms/sample (or ~1-1.5ms combined with FP8!)

### 6.1: Apply Sparsity with Integrated Export

The simplest way is to use the export script with `--with-sparsity`:

```bash
python -m training.scripts.export_production \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --output-dir models/production/ \
    --cache-dir "${BEATSIGHT_DATA_ROOT}/feature_cache" \
    --with-sparsity \
    --finetune-sparse 5 \
    --with-fp8
```

This automatically:
1. Applies 2:4 structured sparsity pattern
2. Fine-tunes for 5 epochs to recover accuracy
3. Exports sparse ONNX + sparse TensorRT
4. If `--with-fp8` is also enabled, creates combined FP8+Sparse model (MAXIMUM SPEED!)

### 6.2: Alternative - Manual Sparsity Application

For more control, use the advanced_optimizations module directly:

```bash
python -m training.inference.advanced_optimizations apply-sparsity \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --output checkpoints/v5/sparse/best_drum_classifier_sparse.pth \
    --finetune-epochs 5 \
    --finetune-lr 1e-5 \
    --dataset "${BEATSIGHT_DATASET_DIR}" \
    --labels-cache-dir "${BEATSIGHT_DATA_ROOT}/dataset_index"

# Then export
python -m training.inference.advanced_optimizations export-sparse \
    --checkpoint checkpoints/v5/sparse/best_drum_classifier_sparse.pth \
    --output models/production/drum_classifier_sparse_trt.onnx \
    --precision int8
```

**Results:**
- `drum_classifier_sparse.onnx` — (~3MB, sparse ONNX)
- `drum_classifier_sparse_trt.onnx` — (~3MB, ~4-6ms with hardware sparsity)
- `drum_classifier_fp8_sparse.trt` — (~3MB, **~1-1.5ms** MAXIMUM SPEED!)

---

## Step 7: (Optional) Export Early Exit Variant

Early Exit provides **+20-50% speedup** by exiting early for "easy" samples (clear kick, snare, hi-hat).

> **Accuracy Loss:** 0% (uses conservative confidence thresholds)

```bash
python -m training.scripts.export_production \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --output-dir models/production/ \
    --with-early-exit \
    --early-exit-thresholds 0.95,0.93,0.90
```

**Result:** `drum_classifier_early_exit.onnx` (~4MB, ~4-6ms average)

---

## Step 8: Upload to Modal and Deploy

### 8.1: Upload All Production Models

```bash
# Upload all production model variants
modal volume put beatsight-models models/production/ /models/

# Verify upload
modal volume ls beatsight-models /models/
```

**Expected files on Modal volume:**
```
/models/
├── drum_classifier_static_int8.onnx    # Base production (required)
├── drum_classifier_fp8.trt             # FP8 variant (2x faster)
├── drum_classifier_epcontext.onnx      # Instant cold starts
├── drum_classifier_sparse_trt.onnx     # 2:4 sparse (optional)
└── drum_classifier_early_exit.onnx     # Early exit (optional)
```

### 8.2: Redeploy Modal App

```bash
cd ai-pipeline
modal deploy modal_app.py
```

### 8.3: Verify Deployment

```bash
# Check which model variant was loaded
modal logs beatsight-ai-pipeline --tail 50

# Look for:
# "FP8 TensorRT classifier loaded (2x faster): /models/drum_classifier_fp8.trt"
# or
# "EPContext classifier loaded (instant cold start): /models/drum_classifier_epcontext.onnx"
```

---

## Step 9: Benchmark Production Performance

### 9.1: Run Inference Benchmark

```bash
python -m training.inference.production_optimizations benchmark \
    --model models/production/drum_classifier_static_int8.onnx \
    --n-warmup 10 \
    --n-runs 100
```

**Expected Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BENCHMARK RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Model: drum_classifier_static_int8.onnx
Batch size: 32
Runs: 100

Latency:
  Mean:   7.23 ms
  Std:    0.45 ms
  P50:    7.15 ms
  P95:    8.12 ms
  P99:    8.89 ms

Throughput:
  Per sample:    0.226 ms
  Samples/sec:   4,428
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 9.2: Compare All Variants

```bash
# Benchmark all model variants
python -c "
from training.inference.production_optimizations import benchmark_inference, create_optimized_inference

models = [
    'models/production/drum_classifier_static_int8.onnx',
    'models/production/drum_classifier_fp8.trt',
    'models/production/drum_classifier_epcontext.onnx',
]

for model_path in models:
    try:
        inference = create_optimized_inference(model_path)
        results = benchmark_inference(inference)
        print(f'{model_path}:')
        print(f'  Mean: {results[\"mean_ms\"]:.2f}ms, P95: {results[\"p95_ms\"]:.2f}ms')
        print(f'  Throughput: {results[\"throughput_samples_per_sec\"]:.0f} samples/sec')
        print()
    except Exception as e:
        print(f'{model_path}: FAILED - {e}')
"
```

### 9.3: End-to-End Pipeline Benchmark

```bash
# Benchmark full pipeline (separation + classification)
python -m training.inference.optimized_pipeline \
    --audio test_songs/test_3min.mp3 \
    --benchmark \
    --model models/production/drum_classifier_static_int8.onnx
```

**Expected Output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END-TO-END PIPELINE BENCHMARK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Audio: test_3min.mp3 (3:00)
Model: drum_classifier_static_int8.onnx

Timing Breakdown:
  Audio loading:        0.3s
  Drum separation:      8.2s (Demucs htdemucs_ft)
  Feature extraction:   1.1s
  Classification:       2.4s (10,560 windows)
  Post-processing:      0.2s
  ────────────────────────────
  TOTAL:               12.2s

Performance:
  Real-time factor:    14.7x faster than real-time
  Classification:      0.23ms/window
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🏆 Final Production Configuration

After completing all steps, your production deployment will have:

| Component | Configuration | Speed |
|-----------|--------------|-------|
| **GPU** | Modal L40S ($1.95/hr) | FP8 capable |
| **Model** | FP8 TensorRT | ~2-3ms/sample |
| **Cold Start** | EPContext | <2 seconds |
| **Fallback** | Static INT8 | ~7-10ms/sample |

**Cost per song (3 minutes):**
- Classification: ~$0.003
- Separation (Demucs): ~$0.02
- **Total: ~$0.023/song**

---

## 📁 File Reference

All optimization code is in `ai-pipeline/training/inference/`:

| File | Purpose |
|------|---------|
| `production_optimizations.py` | Static INT8, IO Binding, torch.compile |
| `advanced_optimizations.py` | EPContext, 2:4 Sparsity, Speculative Batching |
| `revolutionary_optimizations.py` | FP8, Flash Attention, Fused Kernels, GPU Spectrograms |
| `early_exit.py` | Early Exit (Adaptive Depth) inference |
| `tensorrt_inference.py` | TensorRT backend, CUDA Graphs |
| `optimized_pipeline.py` | End-to-end optimized pipeline |

---

## 🔧 Quick Reference Commands

### All-in-One Export (After Training)

```bash
# Export all optimized variants in one command
python -m training.scripts.export_production \
    --checkpoint checkpoints/v5/self-distill/best_drum_classifier_ema.pth \
    --output-dir models/production/ \
    --cache-dir "${BEATSIGHT_CACHE_DIR}" \
    --v5-size large \
    --with-fp8 \
    --with-sparsity \
    --with-early-exit
```

### Upload and Deploy

```bash
# Upload to Modal
modal volume put beatsight-models models/production/ /models/

# Deploy
modal deploy ai-pipeline/modal_app.py

# Verify
modal logs beatsight-ai-pipeline --tail 50
```

### Benchmark

```bash
# Quick benchmark
python -m training.inference.production_optimizations benchmark \
    --model models/production/drum_classifier_static_int8.onnx

# Full pipeline benchmark
python -m training.inference.optimized_pipeline \
    --audio test_songs/test_3min.mp3 \
    --benchmark
```

---

## ❓ Troubleshooting

### FP8 export fails: "FP8 not supported"

FP8 requires Ada Lovelace (sm_89) or Hopper (sm_90) GPUs:
- **Supported:** L40S, H100, H200, RTX 4090
- **Not supported:** A100, A10, V100, RTX 3090

Run FP8 export on Lambda Labs H100 or Modal L40S.

### EPContext export fails: "TensorRT not available"

EPContext requires TensorRT on Linux. Run on Lambda Labs or Modal:
```bash
# On Lambda Labs
ssh ubuntu@LAMBDA_IP
cd BeatSight
python -m training.inference.advanced_optimizations export-embedded ...
```

### Model not loading on Modal

Check model priority in `modal_app.py`:
```python
model_priority = [
    ("/models/v5_large_fp8.trt", "fp8"),           # 1st priority
    ("/models/drum_classifier_fp8.trt", "fp8"),   
    ("/models/v5_large_epcontext.onnx", "epcontext"),
    # ...
]
```

Ensure your model filenames match the priority list.

### Inference is slower than expected

1. Check GPU utilization: `nvidia-smi`
2. Ensure CUDA provider is being used:
   ```python
   session.get_providers()  # Should show 'CUDAExecutionProvider'
   ```
3. Run warmup before benchmarking (10+ iterations)

---

## 📊 Expected Results Summary

| Model Variant | File Size | Inference | Cold Start | When to Use |
|---------------|-----------|-----------|------------|-------------|
| Static INT8 | ~3MB | ~7-10ms | 30-60s | Base production |
| + EPContext | ~15-20MB | ~7-10ms | <2s | If cold starts matter |
| + FP8 | ~3MB | ~2-3ms | <2s | L40S/H100 deployment |
| + Sparsity | ~3MB | ~4-6ms | <2s | Maximum throughput |
| + Early Exit | ~4MB | ~4-6ms avg | <2s | Variable workloads |

**Recommended Production Stack:**
1. **Primary:** FP8 TensorRT on L40S (~2-3ms)
2. **Fallback:** Static INT8 on A10 (~7-10ms)

---

*Last Updated: December 2025*
