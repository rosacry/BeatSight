#!/usr/bin/env python3
"""
Confusion Ceiling Analysis for Drum Classifier

This script analyzes the confusion matrix to identify:
1. Which class pairs are limiting balanced accuracy
2. The theoretical ceiling based on acoustic ambiguity
3. Specific recommendations for breaking the plateau

Usage:
    python analyze_confusion_ceiling.py \
        --checkpoint runs/v5_phase2/checkpoints/best_checkpoint.pth \
        --dataset F:/datasets/prod_v5_cleaned \
        --feature-cache-dir F:/feature_cache
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
from sklearn.metrics import confusion_matrix, balanced_accuracy_score

# Add ai-pipeline to path for proper module resolution
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))


# Known acoustic confusions (expected based on physics)
EXPECTED_CONFUSIONS = {
    ("china", "splash"): "Both are short accent cymbals with similar attack",
    ("china", "crash"): "Both are effect cymbals with loud attack",
    ("splash", "crash"): "Splash is like a short crash",
    ("ride_bow", "crash"): "Ride crashes can sound like crash cymbals",
    ("ride_bell", "ride_bow"): "Same cymbal, different strike location",
    ("hihat_closed", "hihat_pedal"): "Similar timbre, different mechanism",
    ("hihat_open", "crash"): "Open hats can ring like crashes",
    ("cross_stick", "snare"): "Ghost snares can sound like cross-sticks",
    ("tom", "kick"): "Low toms can sound like kicks",
}

# Default class order (will be overridden by components.json)
DEFAULT_CLASSES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", 
    "splash", "tom"
]


def load_components(dataset_path: Path) -> List[str]:
    """Load class names from components.json."""
    components_file = dataset_path / "components.json"
    if components_file.exists():
        with open(components_file, 'r') as f:
            data = json.load(f)
        return data.get("components", DEFAULT_CLASSES)
    return DEFAULT_CLASSES


def compute_confusion_matrix_full(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    num_classes: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute full confusion matrix with probabilities."""
    model.eval()
    
    all_preds = []
    all_labels = []
    all_probs = []
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(dataloader, desc="Computing confusion"):
            features, labels = batch
            features = features.to(device)
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            probs = F.softmax(outputs, dim=1)
            preds = outputs.argmax(dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())
            all_probs.extend(probs.cpu().numpy())
    
    return np.array(all_labels), np.array(all_preds), np.array(all_probs)


def analyze_confusion_pairs(
    cm: np.ndarray,
    class_names: List[str],
    threshold: float = 0.05,
) -> List[Dict]:
    """Identify the most confusing class pairs."""
    pairs = []
    
    for i, cls_a in enumerate(class_names):
        row_total = cm[i].sum()
        if row_total == 0:
            continue
        
        for j, cls_b in enumerate(class_names):
            if i == j:
                continue
            
            confusion_rate = cm[i, j] / row_total
            if confusion_rate >= threshold:
                pair_key = tuple(sorted([cls_a, cls_b]))
                expected = EXPECTED_CONFUSIONS.get(pair_key, "Unexpected - investigate")
                
                pairs.append({
                    "true_class": cls_a,
                    "predicted_class": cls_b,
                    "confusion_rate": float(confusion_rate),
                    "count": int(cm[i, j]),
                    "total": int(row_total),
                    "explanation": expected,
                    "is_expected": pair_key in EXPECTED_CONFUSIONS,
                })
    
    return sorted(pairs, key=lambda x: -x["confusion_rate"])


def estimate_ceiling(
    cm: np.ndarray,
    class_names: List[str],
    expected_pairs: Dict[Tuple[str, str], str],
) -> float:
    """Estimate theoretical ceiling based on expected confusions."""
    n_classes = len(class_names)
    per_class_ceiling = []
    
    for i, cls_name in enumerate(class_names):
        row_total = cm[i].sum()
        if row_total == 0:
            per_class_ceiling.append(1.0)
            continue
        
        # Correct predictions
        correct = cm[i, i]
        
        # Expected confusions (we can't fix these without better data)
        expected_confusion_count = 0
        for j, other_cls in enumerate(class_names):
            if i == j:
                continue
            pair_key = tuple(sorted([cls_name, other_cls]))
            if pair_key in expected_pairs:
                expected_confusion_count += cm[i, j]
        
        # Ceiling = (correct + expected_confusions) / total
        # This represents the best we could do if we fixed all unexpected confusions
        ceiling = (correct + expected_confusion_count) / row_total
        per_class_ceiling.append(min(1.0, ceiling))
    
    # Balanced accuracy ceiling
    return float(np.mean(per_class_ceiling))


def analyze_confidence_distribution(
    probs: np.ndarray,
    labels: np.ndarray,
    preds: np.ndarray,
    class_names: List[str],
) -> Dict:
    """Analyze confidence distribution for correct/incorrect predictions."""
    results = {}
    
    for i, cls_name in enumerate(class_names):
        mask = labels == i
        if mask.sum() == 0:
            continue
        
        cls_probs = probs[mask]
        cls_preds = preds[mask]
        cls_correct = cls_preds == i
        
        correct_conf = cls_probs[cls_correct, i] if cls_correct.sum() > 0 else np.array([])
        incorrect_conf = cls_probs[~cls_correct, cls_preds[~cls_correct]] if (~cls_correct).sum() > 0 else np.array([])
        
        results[cls_name] = {
            "correct_mean_conf": float(correct_conf.mean()) if len(correct_conf) > 0 else 0,
            "incorrect_mean_conf": float(incorrect_conf.mean()) if len(incorrect_conf) > 0 else 0,
            "accuracy": float(cls_correct.mean()),
            "samples": int(mask.sum()),
        }
    
    return results


def generate_recommendations(
    confusion_pairs: List[Dict],
    conf_distribution: Dict,
    current_accuracy: float,
    ceiling: float,
) -> List[str]:
    """Generate actionable recommendations based on analysis."""
    recommendations = []
    
    # Check gap to ceiling
    gap = ceiling - current_accuracy
    if gap < 0.02:
        recommendations.append(
            f"🎯 You are within 2% of the theoretical ceiling ({ceiling*100:.1f}%). "
            "Consider ensemble methods or foundation models for further gains."
        )
    else:
        recommendations.append(
            f"📊 Gap to ceiling: {gap*100:.1f}% ({current_accuracy*100:.1f}% vs {ceiling*100:.1f}%). "
            "There's room for improvement with targeted training."
        )
    
    # Check for unexpected confusions
    unexpected = [p for p in confusion_pairs if not p["is_expected"] and p["confusion_rate"] > 0.05]
    if unexpected:
        recommendations.append(
            f"⚠️ {len(unexpected)} unexpected confusion pairs detected. "
            "These may indicate label noise or data issues."
        )
        for p in unexpected[:3]:
            recommendations.append(
                f"   - {p['true_class']} → {p['predicted_class']}: {p['confusion_rate']*100:.1f}%"
            )
    
    # Check for low confidence correct predictions
    low_conf_correct = [
        (k, v) for k, v in conf_distribution.items()
        if v["correct_mean_conf"] < 0.6 and v["accuracy"] > 0.5
    ]
    if low_conf_correct:
        recommendations.append(
            "📉 Some classes have low confidence even when correct. "
            "Consider temperature scaling or label smoothing adjustments."
        )
    
    # Specific training recommendations
    high_confusion_cymbal = any(
        p["confusion_rate"] > 0.1 and 
        any(c in p["true_class"] or c in p["predicted_class"] 
            for c in ["china", "crash", "splash", "ride"])
        for p in confusion_pairs
    )
    if high_confusion_cymbal:
        recommendations.append(
            "🥁 High cymbal confusion detected. Consider:\n"
            "   1. Contrastive loss to push cymbal embeddings apart\n"
            "   2. Longer audio context windows for cymbals (decay differences)\n"
            "   3. Multi-scale spectrogram features"
        )
    
    return recommendations


def main():
    parser = argparse.ArgumentParser(description="Analyze confusion ceiling")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--fraction", type=float, default=0.25, help="Fraction of val set to use (for speed)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    
    device = torch.device(args.device)
    class_names = load_components(args.dataset)
    num_classes = len(class_names)
    
    print(f"Classes ({num_classes}): {class_names}")
    
    # Load model
    print(f"\nLoading V5 {args.v5_size} model...")
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if args.v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes)
    elif args.v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes)
    else:
        model = cnn_v5_medium(num_classes=num_classes)
    
    # Load weights
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    # Load dataset
    print("\nLoading validation dataset...")
    # Import the dataset class from train_classifier
    from training.train_classifier import DrumSampleDataset
    
    # Find labels file - check multiple formats
    val_dir = args.dataset / "val"
    labels_file = None
    
    # Format 1: labels.json
    if (val_dir / "labels.json").exists():
        labels_file = val_dir / "labels.json"
    # Format 2: labels.npy (combined format)
    elif (val_dir / "labels.npy").exists():
        labels_file = val_dir / "labels.npy"
    # Format 3: labels.pkl
    elif (val_dir / "labels.pkl").exists():
        labels_file = val_dir / "labels.pkl"
    # Format 4: {split}_labels_files.npy + {split}_labels_labels.npy (numpy split format)
    # In this case, we create a "fake" path that the dataset will derive the actual files from
    elif (val_dir / "val_labels_files.npy").exists() and (val_dir / "val_labels_labels.npy").exists():
        # DrumSampleDataset looks for {stem}_files.npy and {stem}_labels.npy
        # So we provide val_labels.npy as the path (even if it doesn't exist)
        labels_file = val_dir / "val_labels.npy"
    # Format 5: train_labels format in val folder
    elif (val_dir / "train_labels_files.npy").exists():
        labels_file = val_dir / "train_labels.npy"
    
    if labels_file is None:
        raise FileNotFoundError(
            f"Could not find labels file in {val_dir}\n"
            f"Expected one of: labels.json, labels.npy, labels.pkl, "
            f"or val_labels_files.npy + val_labels_labels.npy"
        )
    
    print(f"Using labels file: {labels_file}")
    
    # Check for cache mapping file
    cache_mapping = val_dir / "cache_mapping.npz"
    if not cache_mapping.exists():
        cache_mapping = None
        print("Warning: No cache_mapping.npz found, some samples may fail")
    else:
        print(f"Using cache mapping: {cache_mapping}")
    
    
    val_dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=labels_file,
        cache_dir=args.feature_cache_dir / "val",
        cache_mapping=cache_mapping,
    )
    
    # Filter to only samples that have valid cache entries
    if cache_mapping is not None:
        import numpy as np
        mapping_data = np.load(cache_mapping, allow_pickle=True)
        valid_mask = mapping_data['valid']
        valid_indices = np.where(valid_mask)[0]
        print(f"Cache coverage: {len(valid_indices):,} / {len(val_dataset):,} samples ({100*len(valid_indices)/len(val_dataset):.1f}%)")
        
        # Subset to only valid cached samples, then further subset by fraction
        subset_size = int(len(valid_indices) * args.fraction)
        subset_indices = np.random.RandomState(42).choice(valid_indices, subset_size, replace=False)
        val_subset = Subset(val_dataset, subset_indices.tolist())
        total = len(valid_indices)
    else:
        # Subset for speed
        total = len(val_dataset)
        subset_size = int(total * args.fraction)
        indices = np.random.RandomState(42).choice(total, subset_size, replace=False)
        val_subset = Subset(val_dataset, indices.tolist())
    
    print(f"Evaluating on {subset_size:,} / {total:,} samples ({args.fraction*100:.0f}%)")
    
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )
    
    # Compute confusion matrix
    labels, preds, probs = compute_confusion_matrix_full(model, val_loader, device, num_classes)
    cm = confusion_matrix(labels, preds, labels=list(range(num_classes)))
    
    # Current accuracy
    current_balanced_acc = balanced_accuracy_score(labels, preds)
    current_overall_acc = (labels == preds).mean()
    
    print("\n" + "=" * 80)
    print("CONFUSION CEILING ANALYSIS")
    print("=" * 80)
    
    print(f"\nCurrent Performance:")
    print(f"  Overall Accuracy: {current_overall_acc*100:.2f}%")
    print(f"  Balanced Accuracy: {current_balanced_acc*100:.2f}%")
    
    # Analyze confusions
    confusion_pairs = analyze_confusion_pairs(cm, class_names)
    
    # Estimate ceiling
    ceiling = estimate_ceiling(cm, class_names, EXPECTED_CONFUSIONS)
    print(f"\nTheoretical Ceiling: {ceiling*100:.2f}%")
    print(f"Gap to Ceiling: {(ceiling - current_balanced_acc)*100:.2f}%")
    
    # Top confusions
    print("\n" + "-" * 80)
    print("TOP CONFUSION PAIRS (>5% confusion rate)")
    print("-" * 80)
    
    for p in confusion_pairs[:10]:
        status = "🟡 Expected" if p["is_expected"] else "🔴 Unexpected"
        print(f"\n{p['true_class']} → {p['predicted_class']}: {p['confusion_rate']*100:.1f}%")
        print(f"  {status}: {p['explanation']}")
        print(f"  Count: {p['count']:,} / {p['total']:,}")
    
    # Confidence analysis
    conf_distribution = analyze_confidence_distribution(probs, labels, preds, class_names)
    
    print("\n" + "-" * 80)
    print("CONFIDENCE DISTRIBUTION BY CLASS")
    print("-" * 80)
    
    print(f"\n{'Class':<15} {'Accuracy':<10} {'Correct Conf':<15} {'Incorrect Conf':<15}")
    for cls_name in class_names:
        if cls_name not in conf_distribution:
            continue
        d = conf_distribution[cls_name]
        print(f"{cls_name:<15} {d['accuracy']*100:>6.1f}%    {d['correct_mean_conf']*100:>8.1f}%       "
              f"{d['incorrect_mean_conf']*100:>8.1f}%")
    
    # Recommendations
    recommendations = generate_recommendations(
        confusion_pairs, conf_distribution, current_balanced_acc, ceiling
    )
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    for rec in recommendations:
        print(f"\n{rec}")
    
    # Save results
    if args.output:
        results = {
            "current_balanced_accuracy": float(current_balanced_acc),
            "current_overall_accuracy": float(current_overall_acc),
            "theoretical_ceiling": float(ceiling),
            "gap_to_ceiling": float(ceiling - current_balanced_acc),
            "confusion_pairs": confusion_pairs[:20],
            "confidence_distribution": conf_distribution,
            "recommendations": recommendations,
            "confusion_matrix": cm.tolist(),
            "class_names": class_names,
        }
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    return current_balanced_acc, ceiling


if __name__ == "__main__":
    main()
