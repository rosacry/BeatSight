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
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
from sklearn.metrics import classification_report, confusion_matrix

# Add ai-pipeline to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Default drum classes - will be overridden by components.json if available
DEFAULT_DRUM_CLASSES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "rimshot",
    "snare", "splash", "tom"
]


def load_components(dataset_path: Path) -> List[str]:
    """Load class names from components.json, falling back to defaults."""
    components_file = dataset_path / "components.json"
    if components_file.exists():
        with open(components_file, 'r') as f:
            data = json.load(f)
        return data.get("components", DEFAULT_DRUM_CLASSES)
    return DEFAULT_DRUM_CLASSES


def parse_args():
    parser = argparse.ArgumentParser(description="Per-class accuracy analysis for V5 models")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Model checkpoint path")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset root with components.json")
    parser.add_argument("--feature-cache-dir", type=Path, required=True, help="Feature cache directory")
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--num-workers", type=int, default=0)  # 0 = main process, safer on Windows
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of val set to evaluate")
    return parser.parse_args()


def main():
    args = parse_args()
    device = torch.device(args.device)
    
    # Load class names from dataset
    DRUM_CLASSES = load_components(args.dataset)
    num_classes = len(DRUM_CLASSES)
    
    print(f"Loaded {num_classes} classes from {args.dataset / 'components.json'}")
    print(f"Classes: {DRUM_CLASSES}")
    
    print(f"\nLoading V5 {args.v5_size} model...")
    
    # Import and create V5 model
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if args.v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes, drop_path_rate=0.1)
    elif args.v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes, drop_path_rate=0.1)
    else:
        model = cnn_v5_medium(num_classes=num_classes, drop_path_rate=0.12)
    
    # Load weights
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    elif isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    print(f"Model loaded: {sum(p.numel() for p in model.parameters()):,} parameters")
    
    # Load dataset using consolidated cache
    print("\nLoading validation dataset...")
    from training.datasets.consolidated_cache_dataset import ConsolidatedCacheDataset
    
    val_dataset = ConsolidatedCacheDataset(
        cache_dir=args.feature_cache_dir / "val",
        labels_dir=args.dataset / "val",
    )
    
    total_samples = len(val_dataset)
    subset_size = int(total_samples * args.fraction)
    
    print(f"Evaluating on {subset_size:,} / {total_samples:,} samples ({args.fraction*100:.0f}%)")
    
    # Create subset if needed
    if args.fraction < 1.0:
        indices = np.random.RandomState(42).choice(total_samples, subset_size, replace=False)
        val_subset = Subset(val_dataset, indices)
    else:
        val_subset = val_dataset
    
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
    
    print("Running inference...")
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(val_loader, desc="Evaluating"):
            # Dataset returns (features, labels) tuple
            features, labels = batch
            features = features.to(device)
            labels = labels.to(device)
            
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
    
    # Calculate per-class metrics
    print("\n" + "="*80)
    print("PER-CLASS ACCURACY ANALYSIS")
    print("="*80)
    
    # Classification report
    report = classification_report(
        all_labels, all_preds,
        labels=list(range(num_classes)),
        target_names=DRUM_CLASSES,
        output_dict=True,
        zero_division=0
    )
    
    # Calculate per-class accuracy
    per_class_correct = Counter()
    per_class_total = Counter()
    
    for pred, label in zip(all_preds, all_labels):
        per_class_total[label] += 1
        if pred == label:
            per_class_correct[label] += 1
    
    # Build results sorted by accuracy (worst first)
    results = []
    for i, cls_name in enumerate(DRUM_CLASSES):
        total = per_class_total.get(i, 0)
        correct = per_class_correct.get(i, 0)
        accuracy = correct / total if total > 0 else 0
        
        cls_report = report.get(cls_name, {})
        results.append({
            "class_id": i,
            "class_name": cls_name,
            "accuracy": accuracy,
            "precision": cls_report.get("precision", 0),
            "recall": cls_report.get("recall", 0),
            "f1": cls_report.get("f1-score", 0),
            "support": total,
            "correct": correct,
        })
    
    # Sort by accuracy (worst first)
    results_sorted = sorted(results, key=lambda x: x["accuracy"])
    
    # Print results
    print(f"\n{'Class':<20} {'Acc':<8} {'Prec':<8} {'Recall':<8} {'F1':<8} {'Support':<10} {'Correct':<10}")
    print("-" * 80)
    
    for r in results_sorted:
        acc_color = "🔴" if r["accuracy"] < 0.3 else ("🟡" if r["accuracy"] < 0.6 else "🟢")
        print(f"{r['class_name']:<20} {acc_color}{r['accuracy']*100:>5.1f}%  {r['precision']*100:>5.1f}%  "
              f"{r['recall']*100:>5.1f}%  {r['f1']*100:>5.1f}%  {r['support']:<10,} {r['correct']:<10,}")
    
    # Overall metrics
    overall_accuracy = np.mean(all_preds == all_labels)
    macro_f1 = report.get("macro avg", {}).get("f1-score", 0)
    weighted_f1 = report.get("weighted avg", {}).get("f1-score", 0)
    
    print("-" * 80)
    print(f"\n{'OVERALL':<20} {overall_accuracy*100:>5.1f}%")
    print(f"{'Macro F1':<20} {macro_f1*100:>5.1f}%")
    print(f"{'Weighted F1':<20} {weighted_f1*100:>5.1f}%")
    
    # Analysis summary
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)
    
    # Identify failing classes (< 30% accuracy)
    failing = [r for r in results if r["accuracy"] < 0.30]
    struggling = [r for r in results if 0.30 <= r["accuracy"] < 0.60]
    good = [r for r in results if r["accuracy"] >= 0.60]
    
    print(f"\n🔴 FAILING (<30% accuracy): {len(failing)} classes")
    for r in failing:
        print(f"   - {r['class_name']}: {r['accuracy']*100:.1f}% ({r['support']:,} samples)")
    
    print(f"\n🟡 STRUGGLING (30-60% accuracy): {len(struggling)} classes")
    for r in struggling:
        print(f"   - {r['class_name']}: {r['accuracy']*100:.1f}% ({r['support']:,} samples)")
    
    print(f"\n🟢 GOOD (>60% accuracy): {len(good)} classes")
    for r in good:
        print(f"   - {r['class_name']}: {r['accuracy']*100:.1f}% ({r['support']:,} samples)")
    
    # Confusion analysis for worst classes
    if len(failing) > 0:
        print("\n" + "="*80)
        print("CONFUSION ANALYSIS FOR FAILING CLASSES")
        print("="*80)
        
        cm = confusion_matrix(all_labels, all_preds, labels=list(range(num_classes)))
        
        for r in failing[:5]:  # Top 5 failing
            cls_id = r["class_id"]
            cls_name = r["class_name"]
            
            # What does this class get confused with?
            row = cm[cls_id]
            total = row.sum()
            if total == 0:
                continue
            
            print(f"\n{cls_name} ({r['accuracy']*100:.1f}% accuracy) - TOP CONFUSIONS:")
            
            # Sort by confusion count
            confusions = [(DRUM_CLASSES[i], count, count/total*100) 
                          for i, count in enumerate(row) if i != cls_id and count > 0]
            confusions.sort(key=lambda x: -x[1])
            
            for conf_class, count, pct in confusions[:5]:
                print(f"   → {conf_class}: {count:,} ({pct:.1f}%)")
    
    # Save results
    if args.output:
        output_data = {
            "overall_accuracy": float(overall_accuracy),
            "macro_f1": float(macro_f1),
            "weighted_f1": float(weighted_f1),
            "samples_evaluated": int(subset_size),
            "samples_total": int(total_samples),
            "fraction": float(args.fraction),
            "per_class": results,
        }
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    return overall_accuracy


if __name__ == "__main__":
    main()
