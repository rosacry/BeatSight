#!/usr/bin/env python3
"""
Per-Class Accuracy Analysis for V5 Models

Evaluates a V5 drum classifier and provides detailed per-class metrics
to identify which classes are failing and need the most improvement.

Usage:
    python ai-pipeline/training/tools/evaluate_per_class_v5.py \
        --checkpoint ai-pipeline/training/runs/cutting_edge/v5/full-cached-simple/best_drum_classifier.pth \
        --v5-size large
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any, Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import tqdm
from sklearn.metrics import classification_report, confusion_matrix

# Add ai-pipeline to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="Per-class accuracy analysis for V5 models")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Model checkpoint path")
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--fraction", type=float, default=0.1, help="Fraction of val set to evaluate")
    return parser.parse_args()


def main():
    args = parse_args()
    device = torch.device(args.device)
    
    # Components (21 classes)
    components = [
        "aux_percussion", "china", "crash", "cross_stick", "cymbal_choke",
        "hihat_closed", "hihat_foot_splash", "hihat_open", "hihat_pedal", "hihat_splash",
        "kick", "ride_bell", "ride_bow", "rimshot", "snare",
        "snare_center", "snare_cross_stick", "snare_rimshot", "splash", "tom_high", "tom_low"
    ]
    num_classes = len(components)
    
    print(f"Loading V5 {args.v5_size} model...")
    
    # Import and create V5 model
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if args.v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes, drop_path_rate=0.1)
    elif args.v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes, drop_path_rate=0.15)
    else:
        model = cnn_v5_medium(num_classes=num_classes, drop_path_rate=0.12)
    
    # Load weights
    state_dict = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if isinstance(state_dict, dict) and "model_state_dict" in state_dict:
        state_dict = state_dict["model_state_dict"]
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    print(f"Model loaded: {sum(p.numel() for p in model.parameters()):,} parameters")
    
    # Load dataset
    print("Loading validation dataset...")
    from training.train_classifier import DrumSampleDataset
    
    labels_dir = Path("data/dataset_index")
    cache_dir = Path("data/feature_cache/prod_combined_warmup_consolidated")
    
    # Find labels file
    val_labels_path = labels_dir / "val_labels.json"
    if not val_labels_path.exists():
        # Try numpy labels
        val_labels_npy = labels_dir / "val_labels_labels.npy"
        val_files_npy = labels_dir / "val_labels_files.npy"
        if val_labels_npy.exists():
            print(f"Loading numpy labels from {val_labels_npy}")
            labels_arr = np.load(val_labels_npy)
            files_arr = np.load(val_files_npy) if val_files_npy.exists() else None
        else:
            raise FileNotFoundError("Could not find val labels")
    
    # Load cache mapping
    cache_mapping_path = labels_dir / "val_cache_mapping.npz"
    
    val_dataset = DrumSampleDataset(
        data_dir=labels_dir,  # Not used when cache is available
        labels_file=val_labels_path if val_labels_path.exists() else labels_dir / "val_labels.json",
        cache_dir=cache_dir,
        cache_mapping=cache_mapping_path if cache_mapping_path.exists() else None,
    )
    
    # Use subset for faster evaluation
    total_samples = len(val_dataset)
    subset_size = int(total_samples * args.fraction)
    indices = np.random.RandomState(42).choice(total_samples, subset_size, replace=False)
    
    from torch.utils.data import Subset
    val_subset = Subset(val_dataset, indices)
    
    print(f"Evaluating on {subset_size:,} / {total_samples:,} samples ({args.fraction*100:.0f}%)")
    
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,  # Use main process to avoid memory issues
        pin_memory=False,
    )
    
    # Evaluate
    all_preds = []
    all_labels = []
    all_probs = []
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(val_loader, desc="Evaluating"):
            features = batch["features"].to(device)
            labels = batch["label"].to(device)
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]  # Main classification output
            
            probs = F.softmax(outputs, dim=1)
            preds = outputs.argmax(dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    all_probs = np.array(all_probs)
    
    # Overall accuracy
    overall_acc = (all_preds == all_labels).mean() * 100
    print(f"\n{'='*70}")
    print(f"OVERALL ACCURACY: {overall_acc:.2f}%")
    print(f"{'='*70}")
    
    # Per-class metrics
    print(f"\n{'CLASS':<20} {'SUPPORT':>10} {'PREC':>8} {'RECALL':>8} {'F1':>8} {'STATUS'}")
    print("-" * 70)
    
    report = classification_report(
        all_labels, all_preds, 
        labels=list(range(num_classes)),
        target_names=components,
        output_dict=True,
        zero_division=0
    )
    
    # Sort by F1 score (worst first)
    class_metrics = []
    for i, name in enumerate(components):
        metrics = report.get(name, {})
        support = int(metrics.get("support", 0))
        precision = metrics.get("precision", 0)
        recall = metrics.get("recall", 0)
        f1 = metrics.get("f1-score", 0)
        
        # Status indicator
        if f1 < 0.3:
            status = "FAILING"
        elif f1 < 0.5:
            status = "POOR"
        elif f1 < 0.7:
            status = "OK"
        elif f1 < 0.85:
            status = "GOOD"
        else:
            status = "EXCELLENT"
        
        class_metrics.append({
            "class_idx": i,
            "name": name,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "status": status,
        })
    
    # Sort by F1 (worst first)
    class_metrics.sort(key=lambda x: x["f1"])
    
    for m in class_metrics:
        status_color = {
            "FAILING": "***",
            "POOR": "** ",
            "OK": "*  ",
            "GOOD": "   ",
            "EXCELLENT": "   ",
        }[m["status"]]
        print(f"{m['name']:<20} {m['support']:>10,} {m['precision']:>7.2%} {m['recall']:>7.2%} {m['f1']:>7.2%} {status_color}{m['status']}")
    
    print("-" * 70)
    
    # Summary statistics
    failing = [m for m in class_metrics if m["status"] == "FAILING"]
    poor = [m for m in class_metrics if m["status"] == "POOR"]
    
    print(f"\nSUMMARY:")
    print(f"  FAILING classes (F1 < 30%): {len(failing)}")
    for m in failing:
        print(f"    - {m['name']}: {m['f1']:.1%} F1, {m['support']:,} samples")
    
    print(f"  POOR classes (F1 30-50%): {len(poor)}")
    for m in poor:
        print(f"    - {m['name']}: {m['f1']:.1%} F1, {m['support']:,} samples")
    
    # Confusion analysis - most confused pairs
    cm = confusion_matrix(all_labels, all_preds, labels=list(range(num_classes)))
    
    print(f"\nMOST CONFUSED PAIRS (off-diagonal):")
    confusions = []
    for i in range(num_classes):
        for j in range(num_classes):
            if i != j and cm[i, j] > 0:
                confusions.append({
                    "true": components[i],
                    "pred": components[j],
                    "count": cm[i, j],
                    "rate": cm[i, j] / cm[i].sum() if cm[i].sum() > 0 else 0,
                })
    
    confusions.sort(key=lambda x: x["count"], reverse=True)
    for c in confusions[:15]:
        print(f"  {c['true']:>20} -> {c['pred']:<20} : {c['count']:>6,} ({c['rate']:.1%})")
    
    # Save results
    if args.output:
        results = {
            "overall_accuracy": overall_acc,
            "per_class": class_metrics,
            "confusion_pairs": confusions[:50],
            "checkpoint": str(args.checkpoint),
            "samples_evaluated": len(all_preds),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    return overall_acc


if __name__ == "__main__":
    main()
