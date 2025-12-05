#!/usr/bin/env python3
"""
Quick Class Health Check During Training

Run this periodically during training to verify all 21 classes are learning.
This catches class collapse EARLY (unlike post-training analysis).

Usage:
    python ai-pipeline/training/tools/quick_class_check.py \
        --checkpoint ai-pipeline/training/runs/cutting_edge/v5/local-balanced/checkpoints/latest_checkpoint.pth

Expected Output (HEALTHY):
    ✅ All 21 classes have >0% accuracy - no class collapse!
    
Warning Output (PROBLEM):
    ⚠️ CLASS COLLAPSE DETECTED! 15 classes have 0% accuracy
"""

import argparse
import sys
from pathlib import Path
from collections import Counter
from typing import List

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm

# Add ai-pipeline to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DRUM_CLASSES = [
    "aux_percussion", "china", "crash", "cross_stick", "cymbal_choke",
    "hihat_closed", "hihat_foot_splash", "hihat_open", "hihat_pedal", "hihat_splash",
    "kick", "ride_bell", "ride_bow", "rimshot", "snare",
    "snare_center", "snare_cross_stick", "snare_rimshot", "splash", "tom_high", "tom_low"
]


def main():
    parser = argparse.ArgumentParser(description="Quick class health check during training")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Checkpoint path")
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--samples", type=int, default=50000, help="Number of samples to check")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    
    device = torch.device(args.device)
    num_classes = len(DRUM_CLASSES)
    
    print("=" * 60)
    print("  QUICK CLASS HEALTH CHECK")
    print("=" * 60)
    print(f"Checkpoint: {args.checkpoint}")
    print()
    
    # Load model
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if args.v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes, drop_path_rate=0.1)
    elif args.v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes, drop_path_rate=0.15)
    else:
        model = cnn_v5_medium(num_classes=num_classes, drop_path_rate=0.12)
    
    # Load checkpoint
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    
    # Handle different checkpoint formats
    if isinstance(checkpoint, dict):
        if "model_state" in checkpoint:
            state_dict = checkpoint["model_state"]
        elif "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint
        
        # Print training progress if available
        if "epoch" in checkpoint:
            print(f"Checkpoint epoch: {checkpoint['epoch']}")
        if "best_val_acc" in checkpoint:
            print(f"Best val accuracy: {checkpoint['best_val_acc']:.2f}%")
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    print(f"Model loaded ({sum(p.numel() for p in model.parameters()):,} params)")
    print()
    
    # Load a quick sample of validation data
    print("Loading validation data sample...")
    from training.train_classifier import DrumSampleDataset
    
    labels_dir = Path("data/dataset_index")
    cache_dir = Path("data/feature_cache/prod_combined_warmup_consolidated/val")
    cache_mapping_path = labels_dir / "val_cache_mapping.npz"
    
    val_dataset = DrumSampleDataset(
        data_dir=labels_dir,
        labels_file=labels_dir / "val_labels.json",
        cache_dir=cache_dir,
        cache_mapping=cache_mapping_path if cache_mapping_path.exists() else None,
    )
    
    # Sample subset
    total_samples = len(val_dataset)
    sample_size = min(args.samples, total_samples)
    indices = np.random.RandomState(42).choice(total_samples, sample_size, replace=False)
    val_subset = Subset(val_dataset, indices)
    
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False,
    )
    
    print(f"Evaluating on {sample_size:,} samples...")
    print()
    
    # Per-class counters
    correct_per_class = Counter()
    total_per_class = Counter()
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for features, labels in tqdm(val_loader, desc="Checking"):
            features = features.to(device)
            labels = labels.to(device)
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            _, predicted = torch.max(outputs, 1)
            
            for pred, label in zip(predicted.cpu().numpy(), labels.cpu().numpy()):
                total_per_class[int(label)] += 1
                if pred == label:
                    correct_per_class[int(label)] += 1
    
    # Calculate per-class accuracy
    print()
    print("=" * 60)
    print("  PER-CLASS ACCURACY")
    print("=" * 60)
    print()
    print(f"{'Class':<25} {'Accuracy':>10} {'Correct':>10} {'Total':>10}")
    print("-" * 60)
    
    zero_accuracy_classes = []
    low_accuracy_classes = []
    
    for class_idx, class_name in enumerate(DRUM_CLASSES):
        total = total_per_class[class_idx]
        correct = correct_per_class[class_idx]
        
        if total > 0:
            acc = 100 * correct / total
            status = "✅" if acc > 10 else "⚠️" if acc > 0 else "❌"
            print(f"{status} {class_name:<23} {acc:>9.1f}% {correct:>10} {total:>10}")
            
            if acc == 0:
                zero_accuracy_classes.append(class_name)
            elif acc < 5:
                low_accuracy_classes.append((class_name, acc))
        else:
            print(f"⚪ {class_name:<23} {'N/A':>10} {0:>10} {0:>10}")
    
    # Summary
    print()
    print("=" * 60)
    print("  DIAGNOSIS")
    print("=" * 60)
    
    overall_correct = sum(correct_per_class.values())
    overall_total = sum(total_per_class.values())
    overall_acc = 100 * overall_correct / overall_total if overall_total > 0 else 0
    
    print(f"\nOverall accuracy: {overall_acc:.2f}%")
    
    if len(zero_accuracy_classes) > 0:
        print()
        print(f"🚨 CLASS COLLAPSE DETECTED!")
        print(f"   {len(zero_accuracy_classes)}/21 classes have 0% accuracy:")
        for cls in zero_accuracy_classes[:10]:
            print(f"      - {cls}")
        if len(zero_accuracy_classes) > 10:
            print(f"      ... and {len(zero_accuracy_classes) - 10} more")
        print()
        print("   ⚠️  This model is NOT learning all classes!")
        print("   ⚠️  Check if balanced sampling is working correctly.")
    elif len(low_accuracy_classes) > 0:
        print()
        print(f"⚠️  Some classes have very low accuracy (<5%):")
        for cls, acc in low_accuracy_classes:
            print(f"      - {cls}: {acc:.1f}%")
        print()
        print("   This is EXPECTED early in training with balanced sampling.")
        print("   Check again after a few more epochs.")
    else:
        print()
        print("✅ All 21 classes have >0% accuracy - NO CLASS COLLAPSE!")
        print("   Training appears healthy. Continue monitoring.")
    
    # Random guess baseline
    random_baseline = 100 / num_classes
    print(f"\n   Random baseline: {random_baseline:.2f}%")
    print(f"   Current overall: {overall_acc:.2f}%")
    
    if overall_acc > random_baseline * 2:
        print("   ✅ Model is learning (>2x random baseline)")
    elif overall_acc > random_baseline:
        print("   ⚠️  Model is slightly above random - early training or issues")
    else:
        print("   ❌ Model is at or below random - check training!")


if __name__ == "__main__":
    main()
