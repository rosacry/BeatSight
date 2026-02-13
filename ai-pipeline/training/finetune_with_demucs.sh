#!/bin/bash
# =============================================================================
# Fine-tune V5 Model with Demucs-Augmented Data
# =============================================================================
#
# This script fine-tunes the best v5 multilabel model from the clean-data
# checkpoint, incorporating Demucs-processed training data to eliminate
# the domain gap between training (clean audio) and inference (Demucs output).
#
# PREREQUISITES:
#   1. Run Demucs augmentation first:
#      python scripts/create_demucs_augmented_dataset.py --source enst
#      python scripts/create_demucs_augmented_dataset.py --source groove
#      python scripts/create_demucs_augmented_dataset.py --source egmd --max-files 5000
#
#   2. Ensure best checkpoint exists:
#      runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt
#
# KEY DIFFERENCES FROM ORIGINAL TRAINING:
#   - Start from best checkpoint (not random init)
#   - Lower learning rate: 2e-5 (vs 1e-4 original)
#   - Fewer epochs: 20 (model is already well-trained)
#   - Warmup epochs: 2 (stable start from pretrained)
#   - Demucs datasets weighted 15-20x for emphasis
#   - Same dataset path (new manifests auto-discovered)
#
# WHAT THE TRAINING SCRIPT AUTO-DISCOVERS:
#   The training script globs for *_manifest.json in the dataset directory.
#   After running the Demucs augmentation script, these new datasets appear:
#   - enst_drums_demucs_manifest.json   (~45K samples)
#   - egmd_demucs_manifest.json         (~100-500K samples)
#   - groove_midi_demucs_manifest.json  (~20K samples)
#   These are loaded alongside the existing 11 datasets automatically.

# === CUDA MEMORY OPTIMIZATION ===
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True,garbage_collection_threshold:0.8"

cd "$(dirname "$0")/.." || exit 1

echo "========================================================================"
echo "FINE-TUNING V5 MODEL WITH DEMUCS-AUGMENTED DATA"
echo "========================================================================"

# Checkpoint to fine-tune from
CHECKPOINT="runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt"

if [ ! -f "$CHECKPOINT" ]; then
    echo "ERROR: Checkpoint not found: $CHECKPOINT"
    exit 1
fi

# Output directory
OUTPUT_DIR="runs/v5_demucs_finetuned_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo ""
echo "Checkpoint: $CHECKPOINT"
echo "Output:     $OUTPUT_DIR"
echo "Dataset:    F:/datasets/multilabel_real_v3"
echo ""

# List discovered Demucs datasets
echo "Checking for Demucs-augmented datasets..."
for ds in enst_drums_demucs egmd_demucs groove_midi_demucs; do
    manifest="F:/datasets/multilabel_real_v3/$ds/${ds}_manifest.json"
    if [ -f "$manifest" ]; then
        echo "  ✓ $ds found"
    else
        echo "  ⚠ $ds not found (run create_demucs_augmented_dataset.py --source ...)"
    fi
done
echo ""

PYTHONPATH=. python training/multilabel/train_multilabel.py \
  --dataset F:/datasets/multilabel_real_v3 \
  --pretrained-checkpoint "$CHECKPOINT" \
  --model-version v5 \
  --v5-size large \
  --output "$OUTPUT_DIR" \
  --epochs 20 \
  --batch-size 128 \
  --grad-accum-steps 5 \
  --lr 2e-5 \
  --min-lr 2e-7 \
  --warmup-epochs 2 \
  --amp-dtype bfloat16 \
  --loss-type cb_focal \
  --cb-beta 0.999 \
  --gamma 2.0 \
  --balanced-sampling \
  --balanced-method rare_class \
  --acoustic-oversample 10 \
  --dataset-weight enst_drums_demucs=20 \
  --dataset-weight egmd_demucs=15 \
  --dataset-weight groove_midi_demucs=15 \
  --specaugment drum \
  --use-ema \
  --ema-decay 0.9995 \
  --gradient-checkpointing \
  --channels-last \
  --num-workers 4 \
  --persistent-workers \
  --checkpoint-every 1 \
  "$@"

echo ""
echo "========================================================================"
echo "Fine-tuning complete!"
echo "Model saved to: $OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Re-tune thresholds on Demucs-augmented validation data:"
echo "     python tools/tune_thresholds_batched.py \\"
echo "       --model $OUTPUT_DIR/best_multilabel_model_ema.pt \\"
echo "       --manifests F:/datasets/multilabel_real_v3/enst_drums_demucs/enst_drums_demucs_manifest.json"
echo ""
echo "  2. Test on a real song:"
echo "     python -m pipeline.process --input '../test_songs/your_song.flac' \\"
echo "       --model-path $OUTPUT_DIR/best_multilabel_model_ema.pt"
echo "========================================================================"
