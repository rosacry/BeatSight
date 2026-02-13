#!/usr/bin/env python3
"""
BeatSight Training Data Diagnostic Tool

Run this on your Lambda instance to diagnose potential issues with
training data, label distributions, and train/val splits.

Usage:
    python ai-pipeline/training/tools/diagnose_training_data.py \
        --labels-cache-dir /home/ubuntu/beatsight_data/dataset_index

This will output a detailed report of:
1. Class distribution in train vs val
2. Train/val distribution similarity (should be >0.95)
3. Any missing or problematic classes
4. Sample count per class
5. Recommendations for fixing issues
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np


def load_labels(labels_dir: Path, split: str, use_velocity: bool = True) -> List[Dict[str, Any]]:
    """Load labels from numpy or JSON files."""
    # Try numpy first (faster)
    npy_labels = labels_dir / f"{split}_labels.npy"
    if npy_labels.exists():
        labels_arr = np.load(npy_labels, mmap_mode='r')
        # Convert to list of dicts
        return [{"component_idx": int(label)} for label in labels_arr]
    
    # Fall back to JSON
    suffix = "_with_velocity" if use_velocity else ""
    json_path = labels_dir / f"{split}_labels{suffix}.json"
    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)
    
    # Try without suffix
    json_path = labels_dir / f"{split}_labels.json"
    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)
    
    raise FileNotFoundError(f"No labels found for {split} in {labels_dir}")


def load_components(labels_dir: Path) -> Optional[List[str]]:
    """Load component names if available."""
    components_path = labels_dir / "components.json"
    if components_path.exists():
        with open(components_path, "r") as f:
            data = json.load(f)
            return data.get("components", [])
    return None


def compute_distribution(labels: List[Dict[str, Any]]) -> Counter:
    """Compute class distribution from labels."""
    if isinstance(labels[0], dict):
        return Counter(int(item.get("component_idx", item.get("label", 0))) for item in labels)
    return Counter(int(label) for label in labels)


def distribution_similarity(dist1: Counter, dist2: Counter) -> float:
    """
    Compute cosine similarity between two distributions.
    Returns value between 0 and 1, where 1 = identical distributions.
    """
    all_keys = set(dist1.keys()) | set(dist2.keys())
    
    vec1 = np.array([dist1.get(k, 0) for k in sorted(all_keys)], dtype=float)
    vec2 = np.array([dist2.get(k, 0) for k in sorted(all_keys)], dtype=float)
    
    # Normalize to proportions
    vec1 = vec1 / vec1.sum() if vec1.sum() > 0 else vec1
    vec2 = vec2 / vec2.sum() if vec2.sum() > 0 else vec2
    
    # Cosine similarity
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot / (norm1 * norm2)


def analyze_class_balance(dist: Counter, name: str) -> Dict[str, Any]:
    """Analyze class balance and identify issues."""
    total = sum(dist.values())
    num_classes = len(dist)
    
    # Calculate stats
    counts = list(dist.values())
    min_count = min(counts)
    max_count = max(counts)
    mean_count = total / num_classes if num_classes > 0 else 0
    
    # Imbalance ratio (max/min)
    imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
    
    # Find problematic classes
    underrepresented = []
    for cls, count in dist.most_common()[::-1]:  # Least common first
        if count < mean_count * 0.1:  # Less than 10% of mean
            underrepresented.append((cls, count, count / total * 100))
        if len(underrepresented) >= 5:
            break
    
    return {
        "name": name,
        "total_samples": total,
        "num_classes": num_classes,
        "min_count": min_count,
        "max_count": max_count,
        "mean_count": mean_count,
        "imbalance_ratio": imbalance_ratio,
        "underrepresented": underrepresented,
    }


def print_distribution(dist: Counter, components: Optional[List[str]], name: str):
    """Print formatted distribution table."""
    print(f"\n{'='*60}")
    print(f"  {name} Distribution ({sum(dist.values()):,} samples)")
    print(f"{'='*60}")
    
    total = sum(dist.values())
    
    # Sort by class index
    for cls_idx in sorted(dist.keys()):
        count = dist[cls_idx]
        pct = count / total * 100
        bar_len = int(pct * 0.5)  # Scale for display
        bar = "█" * bar_len
        
        if components and cls_idx < len(components):
            cls_name = components[cls_idx]
        else:
            cls_name = f"class_{cls_idx}"
        
        print(f"  {cls_idx:2d} {cls_name:20s} {count:10,d} ({pct:5.2f}%) {bar}")


def diagnose(labels_dir: Path, verbose: bool = True):
    """Run full diagnostics on training data."""
    print("\n" + "="*70)
    print("  BeatSight Training Data Diagnostics")
    print("="*70)
    print(f"\nLabels directory: {labels_dir}")
    
    # Load data
    print("\n📂 Loading training labels...")
    try:
        train_labels = load_labels(labels_dir, "train")
        print(f"   ✓ Loaded {len(train_labels):,} training samples")
    except FileNotFoundError as e:
        print(f"   ✗ ERROR: {e}")
        return None
    
    print("📂 Loading validation labels...")
    try:
        val_labels = load_labels(labels_dir, "val")
        print(f"   ✓ Loaded {len(val_labels):,} validation samples")
    except FileNotFoundError as e:
        print(f"   ✗ ERROR: {e}")
        return None
    
    # Load component names
    components = load_components(labels_dir)
    if components:
        print(f"📂 Loaded {len(components)} component names")
    
    # Compute distributions
    train_dist = compute_distribution(train_labels)
    val_dist = compute_distribution(val_labels)
    
    # Print distributions
    if verbose:
        print_distribution(train_dist, components, "TRAINING")
        print_distribution(val_dist, components, "VALIDATION")
    
    # Analyze balance
    train_analysis = analyze_class_balance(train_dist, "Training")
    val_analysis = analyze_class_balance(val_dist, "Validation")
    
    # Compute similarity
    similarity = distribution_similarity(train_dist, val_dist)
    
    # Print analysis
    print("\n" + "="*70)
    print("  ANALYSIS")
    print("="*70)
    
    print(f"\n📊 Distribution Similarity: {similarity:.4f}")
    if similarity >= 0.98:
        print("   ✓ EXCELLENT - Train and val distributions are nearly identical")
    elif similarity >= 0.95:
        print("   ✓ GOOD - Train and val distributions are similar")
    elif similarity >= 0.90:
        print("   ⚠️ WARNING - Some distribution mismatch between train/val")
    else:
        print("   ❌ PROBLEM - Significant distribution mismatch!")
        print("      This can cause volatile validation accuracy.")
    
    print(f"\n📊 Training Set Imbalance Ratio: {train_analysis['imbalance_ratio']:.1f}x")
    if train_analysis['imbalance_ratio'] <= 10:
        print("   ✓ GOOD - Reasonable class balance")
    elif train_analysis['imbalance_ratio'] <= 50:
        print("   ⚠️ WARNING - Moderate imbalance, class weights recommended")
    else:
        print("   ❌ PROBLEM - Severe imbalance!")
        print("      Some classes may be undertrained.")
    
    print(f"\n📊 Validation Set Imbalance Ratio: {val_analysis['imbalance_ratio']:.1f}x")
    
    # Show underrepresented classes
    if train_analysis['underrepresented']:
        print(f"\n⚠️ Underrepresented Training Classes (<10% of mean):")
        for cls_idx, count, pct in train_analysis['underrepresented']:
            cls_name = components[cls_idx] if components and cls_idx < len(components) else f"class_{cls_idx}"
            print(f"   - {cls_name} ({cls_idx}): {count:,} samples ({pct:.3f}%)")
    
    # Check for missing classes
    train_classes = set(train_dist.keys())
    val_classes = set(val_dist.keys())
    
    missing_in_val = train_classes - val_classes
    missing_in_train = val_classes - train_classes
    
    if missing_in_val:
        print(f"\n❌ Classes in TRAIN but NOT in VAL:")
        for cls_idx in missing_in_val:
            cls_name = components[cls_idx] if components and cls_idx < len(components) else f"class_{cls_idx}"
            print(f"   - {cls_name} ({cls_idx})")
    
    if missing_in_train:
        print(f"\n❌ Classes in VAL but NOT in TRAIN:")
        for cls_idx in missing_in_train:
            cls_name = components[cls_idx] if components and cls_idx < len(components) else f"class_{cls_idx}"
            print(f"   - {cls_name} ({cls_idx})")
    
    # Expected accuracy analysis
    print("\n" + "="*70)
    print("  EXPECTED PERFORMANCE")
    print("="*70)
    
    num_classes = len(train_classes)
    random_baseline = 100.0 / num_classes
    
    print(f"\n   Random baseline (uniform guess): {random_baseline:.2f}%")
    print(f"   Number of classes: {num_classes}")
    print(f"   Training samples: {train_analysis['total_samples']:,}")
    print(f"   Validation samples: {val_analysis['total_samples']:,}")
    print(f"   Train/Val ratio: {train_analysis['total_samples'] / val_analysis['total_samples']:.1f}:1")
    
    # Recommendations
    print("\n" + "="*70)
    print("  RECOMMENDATIONS")
    print("="*70)
    
    issues_found = 0
    
    if similarity < 0.95:
        issues_found += 1
        print(f"\n{issues_found}. FIX TRAIN/VAL DISTRIBUTION MISMATCH")
        print("   The train and val sets have different class distributions.")
        print("   This causes volatile val accuracy because the model sees")
        print("   different proportions of classes during validation.")
        print("   → Regenerate splits with stratified sampling")
    
    if train_analysis['imbalance_ratio'] > 50:
        issues_found += 1
        print(f"\n{issues_found}. ADDRESS SEVERE CLASS IMBALANCE")
        print("   Some classes have 50x+ fewer samples than others.")
        print("   → Use class weights (already enabled)")
        print("   → Consider oversampling rare classes")
        print("   → Or undersample common classes")
    
    if missing_in_val or missing_in_train:
        issues_found += 1
        print(f"\n{issues_found}. FIX MISSING CLASSES")
        print("   Some classes exist in one split but not the other.")
        print("   → Regenerate splits to ensure all classes in both")
    
    if issues_found == 0:
        print("\n   ✓ No major issues detected!")
        print("   If accuracy is still low, the problem may be:")
        print("   - Too much regularization (reduce techniques)")
        print("   - Learning rate too high/low")
        print("   - Model architecture issues")
    
    return {
        "train_dist": dict(train_dist),
        "val_dist": dict(val_dist),
        "similarity": similarity,
        "train_analysis": train_analysis,
        "val_analysis": val_analysis,
        "components": components,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose BeatSight training data for issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--labels-cache-dir",
        type=Path,
        required=True,
        help="Path to labels cache directory (contains train_labels.npy, val_labels.npy)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Skip detailed distribution printout",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Save analysis to JSON file",
    )
    
    args = parser.parse_args()
    
    results = diagnose(args.labels_cache_dir, verbose=not args.quiet)
    
    if results and args.output_json:
        # Convert numpy types for JSON
        output = {
            "similarity": float(results["similarity"]),
            "train_total": results["train_analysis"]["total_samples"],
            "val_total": results["val_analysis"]["total_samples"],
            "num_classes": results["train_analysis"]["num_classes"],
            "train_imbalance": results["train_analysis"]["imbalance_ratio"],
            "val_imbalance": results["val_analysis"]["imbalance_ratio"],
            "components": results["components"],
        }
        with open(args.output_json, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n📄 Results saved to {args.output_json}")


if __name__ == "__main__":
    main()
