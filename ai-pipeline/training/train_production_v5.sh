#!/bin/bash
# Production training script for v5 model
# Includes memory optimization to prevent CUDA OOM on long runs

# === CUDA MEMORY OPTIMIZATION ===
# Prevents memory fragmentation that causes OOM after many epochs
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"

# Optional: Force synchronous CUDA operations for debugging OOM issues
# export CUDA_LAUNCH_BLOCKING=1

cd "$(dirname "$0")/.." || exit 1

PYTHONPATH=. python training/train_classifier.py \
  --dataset C:/temp_dataset/prod_v5_fixed_20251212 \
  --feature-cache-dir C:/temp_dataset/feature_cache_v5 \
  --model-version v5 \
  --v5-size large \
  --epochs 100 \
  --batch-size 160 \
  --grad-accum-steps 4 \
  --lr 2e-4 \
  --amp-dtype bfloat16 \
  --balanced-sampling \
  --sampling-strategy uniform \
  --class-weights none \
  --mixup-alpha 0.0 \
  --cutmix-alpha 0.0 \
  --specaugment none \
  --use-ema \
  --ema-decay 0.9995 \
  --scheduler cosine_warm_restarts \
  --warm-restart-t0 20 \
  --warmup-epochs 2 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 \
  --prefetch-factor 2 \
  --persistent-workers \
  --pin-memory \
  --checkpoint-every 1 \
  --checkpoint-every-batches 5000 \
  --channels-last \
  "$@"
