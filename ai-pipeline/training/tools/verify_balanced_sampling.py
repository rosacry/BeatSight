#!/usr/bin/env python3
"""
Standalone verification script for balanced sampling.

This script simulates the WeightedRandomSampler behavior with synthetic data
that matches the class imbalance of a typical drum dataset.

Run this to verify the sampling math is correct.

Usage:
    cd BeatSight
    python ai-pipeline/training/tools/verify_balanced_sampling.py
"""

import sys
import numpy as np
from collections import Counter

import torch
from torch.utils.data import WeightedRandomSampler


def main():
    print("=" * 70)
    print("  BALANCED SAMPLING VERIFICATION TEST")
    print("=" * 70)
    print()
    
    # Simulate a dataset with 21 classes and EXTREME imbalance
    # This matches the typical drum class distribution
    num_classes = 21
    
    # Class distribution similar to real data (rough approximation)
    # Classes 0-4: common (snare, kick, etc.) - 10,000-50,000 samples
    # Classes 5-10: medium - 2,000-10,000 samples
    # Classes 11-20: rare - 50-2,000 samples
    np.random.seed(42)
    
    class_sizes_full = [
        50000, 45000, 40000, 35000, 30000,  # Common classes
        10000, 8000, 6000, 5000, 4000, 3000,  # Medium classes
        2000, 1500, 1000, 800, 500, 300, 200, 150, 100, 50  # Rare classes
    ]
    
    print(f"Simulated full dataset:")
    print(f"  Classes: {num_classes}")
    print(f"  Total samples: {sum(class_sizes_full):,}")
    print(f"  Imbalance ratio: {max(class_sizes_full) / min(class_sizes_full):.0f}x")
    
    # Create labels array for full dataset
    labels_full = []
    for class_idx, count in enumerate(class_sizes_full):
        labels_full.extend([class_idx] * count)
    labels_full = np.array(labels_full)
    
    # Simulate --train-fraction 0.10 (random subset)
    train_fraction = 0.10
    subset_size = int(len(labels_full) * train_fraction)
    subset_indices = np.random.choice(len(labels_full), subset_size, replace=False)
    train_labels = labels_full[subset_indices]
    
    print(f"\n{'=' * 70}")
    print(f"  SUBSET ANALYSIS (train_fraction={train_fraction})")
    print(f"{'=' * 70}")
    print(f"Subset size: {len(train_labels):,}")
    
    # Show subset distribution
    subset_counts = np.bincount(train_labels, minlength=num_classes)
    print(f"\nSubset class distribution:")
    for i, count in enumerate(subset_counts):
        marker = ""
        if count < 20:
            marker = " [CRITICAL: <20 samples!]"
        elif count < 50:
            marker = " [WARNING: <50 samples]"
        print(f"  Class {i:2d}: {count:6,} samples{marker}")
    
    print(f"\n  Min class: {subset_counts.min():,} samples")
    print(f"  Max class: {subset_counts.max():,} samples")
    print(f"  Imbalance ratio: {subset_counts.max() / max(subset_counts.min(), 1):.0f}x")
    
    classes_under_20 = np.sum(subset_counts < 20)
    classes_under_50 = np.sum(subset_counts < 50)
    if classes_under_20 > 0:
        print(f"\n  [CRITICAL] {classes_under_20} classes have <20 samples!")
        print(f"             Balanced sampling will repeatedly pick same samples!")
    elif classes_under_50 > 0:
        print(f"\n  [WARNING] {classes_under_50} classes have <50 samples")
    
    # === CREATE BALANCED SAMPLER (EXACTLY as train_classifier.py does) ===
    print(f"\n{'=' * 70}")
    print(f"  BALANCED SAMPLER TEST (uniform strategy)")
    print(f"{'=' * 70}")
    
    # Compute weights (EXACT copy from train_classifier.py)
    class_counts = np.bincount(train_labels, minlength=num_classes)
    class_weights = 1.0 / (class_counts + 1e-6)  # uniform strategy
    class_weights = class_weights / class_weights.sum() * num_classes  # normalize
    sample_weights = class_weights[train_labels]
    sample_weights_tensor = torch.from_numpy(sample_weights.astype(np.float64))
    
    print(f"\nSample weights computed:")
    print(f"  Weight range: {sample_weights.min():.6f} to {sample_weights.max():.6f}")
    print(f"  Weight ratio (max/min): {sample_weights.max() / sample_weights.min():.1f}x")
    
    # Create sampler
    balanced_sampler = WeightedRandomSampler(
        weights=sample_weights_tensor,
        num_samples=len(train_labels),
        replacement=True,
    )
    
    # Sample from the sampler
    batch_size = 256
    num_batches = 30
    total_samples = batch_size * num_batches
    
    print(f"\nSampling {total_samples:,} indices ({num_batches} batches of {batch_size})...")
    
    sampled_indices = list(balanced_sampler)[:total_samples]
    sampled_labels = train_labels[sampled_indices]
    
    # Analyze sampled distribution
    sampled_counts = np.bincount(sampled_labels, minlength=num_classes)
    expected_per_class = total_samples / num_classes
    
    print(f"\nSampled class distribution (expected ~{expected_per_class:.0f} per class):")
    for i, count in enumerate(sampled_counts):
        ratio = count / expected_per_class if expected_per_class > 0 else 0
        bar = "#" * min(int(ratio * 10), 30)
        status = ""
        if count == 0:
            status = " [NOT SAMPLED!]"
        elif ratio < 0.5:
            status = " [UNDER-SAMPLED]"
        elif ratio > 2.0:
            status = " [OVER-SAMPLED]"
        print(f"  Class {i:2d}: {count:5,} ({ratio:5.2f}x expected) {bar}{status}")
    
    # Summary statistics
    print(f"\n{'=' * 70}")
    print(f"  SAMPLING VERIFICATION RESULTS")
    print(f"{'=' * 70}")
    
    classes_not_sampled = np.sum(sampled_counts == 0)
    min_sampled = sampled_counts.min()
    max_sampled = sampled_counts.max()
    actual_imbalance = max_sampled / max(min_sampled, 1)
    
    print(f"  Classes not sampled at all: {classes_not_sampled}/{num_classes}")
    print(f"  Min samples per class: {min_sampled}")
    print(f"  Max samples per class: {max_sampled}")
    print(f"  Actual imbalance ratio: {actual_imbalance:.1f}x")
    print(f"  Target (uniform): {expected_per_class:.0f} per class, 1.0x imbalance")
    
    # Verdict
    print(f"\n{'=' * 70}")
    if classes_not_sampled > 0:
        print("  [FAIL] FAIL: Some classes are never sampled!")
        print("          Balanced sampling is NOT working correctly.")
        verdict = False
    elif actual_imbalance > 5.0:
        print(f"  [FAIL] FAIL: Imbalance ratio {actual_imbalance:.1f}x is too high (target <5x)")
        print("          Balanced sampling is NOT working correctly.")
        verdict = False
    elif actual_imbalance > 2.0:
        print(f"  [WARN]  WARNING: Imbalance ratio {actual_imbalance:.1f}x is higher than expected")
        print("          Balanced sampling is working but not perfectly.")
        verdict = True
    else:
        print(f"  [PASS] PASS: Imbalance ratio {actual_imbalance:.1f}x is acceptable (<2x)")
        print("          Balanced sampling appears to be working correctly!")
        verdict = True
    print(f"{'=' * 70}")
    
    # Additional diagnostic: check unique samples per class
    print(f"\n{'=' * 70}")
    print(f"  UNIQUE SAMPLE CHECK (overfitting risk)")
    print(f"{'=' * 70}")
    print("  This shows how many UNIQUE samples were selected from each class.")
    print("  High repetition = same samples picked over and over = overfitting risk!")
    print()
    
    danger_classes = 0
    for i in range(num_classes):
        sampled_from_class = [idx for idx in sampled_indices if train_labels[idx] == i]
        unique_sampled = len(set(sampled_from_class))
        total_in_class = subset_counts[i]
        times_sampled = len(sampled_from_class)
        avg_repeats = times_sampled / max(unique_sampled, 1)
        
        if total_in_class < 20:
            print(f"  Class {i:2d}: {unique_sampled:4d} unique / {times_sampled:4d} sampled (from {total_in_class:4d} available, avg {avg_repeats:.1f}x repeats) [DANGER!]")
            danger_classes += 1
        elif avg_repeats > 10:
            print(f"  Class {i:2d}: {unique_sampled:4d} unique / {times_sampled:4d} sampled (from {total_in_class:4d} available, avg {avg_repeats:.1f}x repeats) [HIGH REPEAT]")
    
    if danger_classes > 0:
        print(f"\n  [WARN]  {danger_classes} classes have <20 samples and will be repeated heavily!")
        print("     This is the likely cause of class collapse - the model memorizes")
        print("     these few samples instead of learning generalizable features.")
        print()
        print("  SOLUTION: Increase --train-fraction to get more samples per class,")
        print("            or use stratified subset to ensure minimum samples.")
    
    # === TEST THE FIX: Stratified sampling with min_samples_per_class ===
    print(f"\n{'=' * 70}")
    print(f"  TESTING FIX: Stratified sampling with min_samples_per_class=50")
    print(f"{'=' * 70}")
    
    # Simulate stratified_sample_indices with min_samples_per_class
    min_samples_per_class = 50
    rng = np.random.default_rng(42)
    
    stratified_indices = []
    classes_boosted = 0
    for class_idx in range(num_classes):
        class_mask = labels_full == class_idx
        class_indices_full = np.where(class_mask)[0]
        
        # Compute target based on fraction
        take_by_fraction = max(1, int(round(len(class_indices_full) * train_fraction)))
        # Apply minimum floor
        take = max(take_by_fraction, min(min_samples_per_class, len(class_indices_full)))
        
        if take > take_by_fraction:
            classes_boosted += 1
            print(f"  Class {class_idx:2d}: Boosted from {take_by_fraction} to {take} samples (min={min_samples_per_class})")
        
        if take >= len(class_indices_full):
            stratified_indices.extend(class_indices_full.tolist())
        else:
            stratified_indices.extend(rng.choice(class_indices_full, take, replace=False).tolist())
    
    stratified_labels = labels_full[stratified_indices]
    stratified_counts = np.bincount(stratified_labels, minlength=num_classes)
    
    print(f"\n  Classes boosted to minimum: {classes_boosted}")
    print(f"  New subset size: {len(stratified_indices):,} (was {subset_size:,})")
    print(f"\n  New class distribution:")
    for i, count in enumerate(stratified_counts):
        marker = ""
        if count < 20:
            marker = " [STILL CRITICAL!]"
        elif count < 50:
            marker = " [STILL LOW]"
        print(f"    Class {i:2d}: {count:5,} samples{marker}")
    
    new_min = stratified_counts.min()
    print(f"\n  New min class: {new_min} samples (was {subset_counts.min()})")
    
    if new_min >= 50:
        print(f"\n  [PASS] FIX VERIFIED: All classes now have ≥50 samples!")
        print(f"     This should prevent class collapse from data scarcity.")
    elif new_min >= 20:
        print(f"\n  [WARN]  PARTIAL FIX: Min class has {new_min} samples (target was 50)")
        print(f"     Some rare classes may not have enough samples in the full dataset.")
    else:
        print(f"\n  [FAIL] FIX FAILED: Min class still has only {new_min} samples")
    
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
