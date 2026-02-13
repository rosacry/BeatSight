#!/usr/bin/env python3
"""
Debug script to understand the balanced accuracy discrepancy.

Compares training's balanced accuracy calculation vs analyze tool's calculation
on the same exact data.
"""

import argparse
import torch
import numpy as np
from pathlib import Path
from sklearn.metrics import balanced_accuracy_score
from tqdm import tqdm
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.train_classifier import DrumSampleDataset
from torch.utils.data import DataLoader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--max-batches", type=int, default=None, help="Limit batches for quick test")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load model
    print("\nLoading model...")
    model = cnn_v5_large(num_classes=12)
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model_state"], strict=False)
    model = model.to(device).eval()
    print(f"Loaded checkpoint from epoch {ckpt['epoch']}")

    # Print training's recorded balanced accuracy
    if ckpt["history"]:
        last = ckpt["history"][-1]
        print(f"Training recorded (epoch {int(last['epoch'])}): {last.get('val_balanced_accuracy', 'N/A'):.2f}%")

    # Load validation dataset
    print("\nLoading validation dataset...")
    val_dir = args.dataset / "val"
    cache_dir = args.feature_cache_dir / "val"
    
    dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=val_dir / "val_labels.npy",
        cache_dir=cache_dir,
        cache_mapping=val_dir / "cache_mapping.npz",
    )
    print(f"Dataset size: {len(dataset)}")

    loader = DataLoader(
        dataset, 
        batch_size=args.batch_size, 
        shuffle=False, 
        num_workers=0,
        pin_memory=True,
    )

    # Collect predictions
    all_preds = []
    all_labels = []

    print("\nCollecting predictions...")
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for i, (features, labels) in enumerate(tqdm(loader, desc="Predicting")):
            if args.max_batches and i >= args.max_batches:
                break
            
            features = features.to(device, non_blocking=True)
            outputs = model(features)
            
            # Handle tuple output (main output, velocity output)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            preds = outputs.argmax(dim=1)
            all_preds.append(preds.cpu())
            all_labels.append(labels)

    all_preds = torch.cat(all_preds)
    all_labels = torch.cat(all_labels)
    
    print(f"\nTotal samples evaluated: {len(all_labels)}")

    # Method 1: sklearn balanced_accuracy_score (used by analyze_confusion_ceiling.py)
    sklearn_bal = balanced_accuracy_score(all_labels.numpy(), all_preds.numpy()) * 100
    print(f"\n[sklearn balanced_accuracy_score]: {sklearn_bal:.4f}%")

    # Method 2: Training script's method (from train_classifier.py validate())
    n_classes = 12
    per_class_correct = torch.zeros(n_classes)
    per_class_total = torch.zeros(n_classes)

    for c in range(n_classes):
        mask = all_labels == c
        per_class_total[c] = mask.sum().item()
        if per_class_total[c] > 0:
            per_class_correct[c] = ((all_preds == c) & mask).sum().item()

    valid_classes = per_class_total > 0
    per_class_acc = per_class_correct[valid_classes] / per_class_total[valid_classes]
    training_bal = 100 * per_class_acc.mean().item()
    print(f"[Training script method]: {training_bal:.4f}%")

    # Show per-class breakdown
    print("\n" + "="*60)
    print("Per-class breakdown:")
    print("="*60)
    classes = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
    
    for c in range(n_classes):
        if per_class_total[c] > 0:
            acc = 100 * per_class_correct[c] / per_class_total[c]
            print(f"  {classes[c]:15s}: {acc:5.1f}% ({int(per_class_correct[c]):>7,} / {int(per_class_total[c]):>7,})")

    print("="*60)
    print(f"Mean per-class accuracy: {training_bal:.4f}%")
    
    # Check for discrepancy
    diff = abs(sklearn_bal - training_bal)
    if diff > 0.01:
        print(f"\n⚠️  DISCREPANCY DETECTED: {diff:.4f}%")
    else:
        print(f"\n✓ Methods agree within 0.01%")


if __name__ == "__main__":
    main()
