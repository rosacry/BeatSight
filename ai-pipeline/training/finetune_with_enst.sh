#!/bin/bash
# Fine-tune v5 model with ENST real drum data for domain adaptation
#
# Strategy: Take existing v5 large model and fine-tune with:
# 1. ENST real drums added to training mix
# 2. Lower learning rate (10x reduction)
# 3. Aggressive augmentation to bridge synthetic->real gap
# 4. Class-weighted loss to handle ENST's smaller size

# === CUDA MEMORY OPTIMIZATION ===
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"

cd "$(dirname "$0")/.." || exit 1

echo "========================================================================"
echo "FINE-TUNING V5 MODEL WITH ENST REAL DRUM DATA"
echo "========================================================================"
echo ""
echo "Strategy:"
echo "  - Start from pre-trained v5_large checkpoint"
echo "  - Add ENST (45K real drum samples) to training mix"
echo "  - Lower LR (2e-5 vs original 2e-4)"
echo "  - Use cosine schedule with warm restarts"
echo "  - Strong SpecAugment for domain adaptation"
echo ""

# Find the best checkpoint
CHECKPOINT_DIR="runs/v5_multilabel_final_v2"
if [ -f "$CHECKPOINT_DIR/best_model.pt" ]; then
    RESUME_FROM="--resume $CHECKPOINT_DIR/best_model.pt"
    echo "Resuming from: $CHECKPOINT_DIR/best_model.pt"
elif [ -f "$CHECKPOINT_DIR/checkpoint_latest.pt" ]; then
    RESUME_FROM="--resume $CHECKPOINT_DIR/checkpoint_latest.pt"
    echo "Resuming from: $CHECKPOINT_DIR/checkpoint_latest.pt"
else
    echo "ERROR: No checkpoint found in $CHECKPOINT_DIR"
    echo "Please provide a pre-trained model to fine-tune."
    exit 1
fi

# Create output directory for fine-tuned model
OUTPUT_DIR="runs/v5_finetuned_enst_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Output: $OUTPUT_DIR"
echo ""

PYTHONPATH=. python training/train_classifier.py \
  --dataset F:/datasets/multilabel_real_v3 \
  --feature-cache-dir F:/feature_cache/v5_finetune \
  --model-version v5 \
  --v5-size large \
  --output "$OUTPUT_DIR" \
  $RESUME_FROM \
  --reset-scheduler \
  --epochs 30 \
  --batch-size 128 \
  --grad-accum-steps 4 \
  --lr 2e-5 \
  --amp-dtype bfloat16 \
  --balanced-sampling \
  --sampling-strategy uniform \
  --class-weights none \
  --mixup-alpha 0.2 \
  --cutmix-alpha 0.0 \
  --specaugment strong \
  --use-ema \
  --ema-decay 0.9995 \
  --scheduler cosine_warm_restarts \
  --warm-restart-t0 10 \
  --warmup-epochs 1 \
  --gradient-checkpointing \
  --grad-clip-norm 1.0 \
  --num-workers 4 \
  --prefetch-factor 2 \
  --persistent-workers \
  --pin-memory \
  --checkpoint-every 1 \
  --channels-last \
  "$@"

echo ""
echo "========================================================================"
echo "Fine-tuning complete!"
echo "Model saved to: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Run threshold tuning on ENST-like data:"
echo "     python tools/tune_thresholds_batched.py \\"
echo "       --manifests F:/datasets/multilabel_real_v3/enst_real/enst_manifest.json \\"
echo "       --model $OUTPUT_DIR/best_model.pt"
echo ""
echo "  2. Re-run ENST benchmark:"
echo "     python tools/run_enst_benchmark.py --model $OUTPUT_DIR/best_model.pt"
echo "========================================================================"
