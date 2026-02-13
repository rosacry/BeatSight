#!/usr/bin/env python3
"""
Generate Multi-Label Dataset from Single-Label Production Data

This script creates multi-label training data from the single-label prod_v5_final
dataset. There are two main approaches:

1. SYNTHETIC OVERLAYS (Recommended for training):
   - Randomly combine 2-3 isolated drum hits from different classes
   - Mix their spectrograms with realistic blending
   - Creates controlled multi-label ground truth
   - Can generate millions of diverse combinations

2. ONSET MERGING (For validation/testing):
   - Group nearby onsets from source MIDI/annotations within 30ms
   - Requires original onset timing metadata
   - More realistic but limited by source data quality

Usage:
    # Generate synthetic multi-label dataset
    python generate_multilabel_dataset.py \
        --input "F:/datasets/prod_v5_final" \
        --output "F:/datasets/prod_v5_multilabel" \
        --feature-cache-dir "F:/feature_cache" \
        --mode synthetic \
        --num-samples 5000000 \
        --max-labels 3

    # Analyze existing single-label dataset for potential merging
    python generate_multilabel_dataset.py \
        --input "F:/datasets/prod_v5_final" \
        --mode analyze

Author: BeatSight Team
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from tqdm import tqdm


# =============================================================================
# 12-Class Drum Component Mapping
# =============================================================================

DRUM_COMPONENTS = [
    "china",         # 0
    "crash",         # 1
    "cross_stick",   # 2
    "hihat_closed",  # 3
    "hihat_open",    # 4
    "hihat_pedal",   # 5
    "kick",          # 6
    "ride_bell",     # 7
    "ride_bow",      # 8
    "snare",         # 9
    "splash",        # 10
    "tom",           # 11
]

# Common simultaneous hit patterns in drumming
# These represent realistic multi-label combinations
# Class indices: china=0, crash=1, cross_stick=2, hihat_closed=3, hihat_open=4,
#                hihat_pedal=5, kick=6, ride_bell=7, ride_bow=8, snare=9, splash=10, tom=11
COMMON_PATTERNS = [
    # =========================================================================
    # 2-LABEL PATTERNS (basic combos)
    # =========================================================================
    # Beat 1 patterns (kick + hi-hat variations)
    [6, 3],          # kick + hihat_closed (most common)
    [6, 4],          # kick + hihat_open
    [6, 5],          # kick + hihat_pedal
    [6, 1],          # kick + crash (downbeat with crash)
    [6, 0],          # kick + china
    [6, 8],          # kick + ride_bow
    
    # Beat 2/4 patterns (snare + hi-hat variations)  
    [9, 3],          # snare + hihat_closed (most common)
    [9, 4],          # snare + hihat_open
    [9, 1],          # snare + crash (accents)
    [9, 0],          # snare + china
    [9, 10],         # snare + splash
    
    # Fills and transitions
    [11, 1],         # tom + crash
    [11, 3],         # tom + hihat_closed
    [6, 9],          # kick + snare (simultaneous)
    
    # Cymbal combinations
    [1, 8],          # crash + ride_bow
    [7, 8],          # ride_bell + ride_bow (grace note)
    [0, 1],          # china + crash
    
    # Cross-stick patterns (jazz, ballads) - ADDED for better cross_stick representation
    [2, 6],          # cross_stick + kick
    [2, 8],          # cross_stick + ride_bow
    [2, 3],          # cross_stick + hihat_closed
    [2, 5],          # cross_stick + hihat_pedal
    
    # =========================================================================
    # 3-LABEL PATTERNS (common)
    # =========================================================================
    [6, 9, 3],       # kick + snare + hihat_closed
    [6, 9, 1],       # kick + snare + crash
    [6, 3, 8],       # kick + hihat_closed + ride_bow
    [9, 3, 8],       # snare + hihat_closed + ride_bow
    [6, 11, 1],      # kick + tom + crash
    [6, 9, 4],       # kick + snare + hihat_open
    [6, 11, 3],      # kick + tom + hihat_closed
    [9, 11, 1],      # snare + tom + crash
    [6, 5, 8],       # kick + hihat_pedal + ride_bow
    [9, 5, 8],       # snare + hihat_pedal + ride_bow
    
    # Cross-stick 3-label patterns (jazz) - ADDED for better cross_stick representation
    [2, 3, 6],       # cross_stick + hihat_closed + kick
    [2, 8, 6],       # cross_stick + ride_bow + kick
    [2, 5, 6],       # cross_stick + hihat_pedal + kick
    [2, 8, 5],       # cross_stick + ride_bow + hihat_pedal
    
    # =========================================================================
    # 4-LABEL PATTERNS (4-limb independence)
    # These are CRITICAL for detecting when drummer uses all 4 limbs:
    # Left foot (hihat_pedal) + Right hand (cymbal/tom) + Left hand (snare) + Right foot (kick)
    # =========================================================================
    # Hihat pedal + cymbal + snare + kick (all 4 limbs)
    [5, 1, 9, 6],    # hihat_pedal + crash + snare + kick
    [5, 0, 9, 6],    # hihat_pedal + china + snare + kick
    [5, 8, 9, 6],    # hihat_pedal + ride_bow + snare + kick
    [5, 7, 9, 6],    # hihat_pedal + ride_bell + snare + kick
    [5, 10, 9, 6],   # hihat_pedal + splash + snare + kick
    [5, 11, 9, 6],   # hihat_pedal + tom + snare + kick
    
    # Hihat pedal + cymbal + tom + kick (4 limbs, tom instead of snare)
    [5, 1, 11, 6],   # hihat_pedal + crash + tom + kick
    [5, 0, 11, 6],   # hihat_pedal + china + tom + kick
    [5, 8, 11, 6],   # hihat_pedal + ride_bow + tom + kick
    
    # Hihat closed/open + tom + snare + kick (right foot on hihat, left foot on kick - less common)
    [3, 11, 9, 6],   # hihat_closed + tom + snare + kick (fast fill)
    [4, 11, 9, 6],   # hihat_open + tom + snare + kick
    [3, 1, 9, 6],    # hihat_closed + crash + snare + kick
    [4, 1, 9, 6],    # hihat_open + crash + snare + kick
    
    # Cross stick variations (jazz patterns)
    [5, 8, 2, 6],    # hihat_pedal + ride_bow + cross_stick + kick
    [5, 7, 2, 6],    # hihat_pedal + ride_bell + cross_stick + kick
]


def load_components_json(dataset_dir: Path) -> List[str]:
    """Load component names from components.json."""
    components_path = dataset_dir / "components.json"
    if components_path.exists():
        with open(components_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'components' in data:
                return data['components']
            elif isinstance(data, list):
                return data
    return DRUM_COMPONENTS


def analyze_single_label_dataset(dataset_dir: Path, split: str = "train") -> Dict[str, Any]:
    """Analyze single-label dataset for class distribution and potential patterns."""
    split_dir = dataset_dir / split
    
    # Support both train_labels_*.npy and val_labels_*.npy naming conventions
    labels_npy = split_dir / f"{split}_labels_labels.npy"
    if not labels_npy.exists():
        labels_npy = split_dir / "train_labels_labels.npy"  # Fallback
    
    if not labels_npy.exists():
        print(f"Skipping {split}: Labels file not found: {labels_npy}")
        return {}
    
    labels = np.load(labels_npy)
    print(f"Loaded {len(labels):,} labels from {split}")
    
    # Class distribution
    unique, counts = np.unique(labels, return_counts=True)
    class_counts = dict(zip(unique.tolist(), counts.tolist()))
    
    component_names = load_components_json(dataset_dir)
    
    stats = {
        "total_samples": len(labels),
        "num_classes": len(component_names),
        "class_distribution": {},
    }
    
    print(f"\n{'='*60}")
    print(f"Single-Label Dataset Analysis: {dataset_dir.name}/{split}")
    print(f"{'='*60}")
    print(f"Total samples: {len(labels):,}")
    print(f"Number of classes: {len(component_names)}")
    
    print("\nClass Distribution:")
    print(f"{'Class':<20} {'Index':>5} {'Count':>12} {'%':>8}")
    print("-" * 50)
    
    for idx in range(len(component_names)):
        name = component_names[idx]
        count = class_counts.get(idx, 0)
        pct = 100 * count / len(labels) if len(labels) > 0 else 0
        print(f"{name:<20} {idx:>5} {count:>12,} {pct:>7.1f}%")
        stats["class_distribution"][name] = count
    
    print(f"{'='*60}\n")
    
    return stats


def generate_synthetic_multilabel_sample(
    single_label_samples: Dict[int, List[int]],
    labels_array: np.ndarray,
    num_classes: int,
    max_labels: int = 4,
    pattern_based: bool = True,
    solo_ratio: float = 0.0,
) -> Tuple[List[int], np.ndarray]:
    """
    Generate a synthetic multi-label sample by combining indices.
    
    Args:
        single_label_samples: Dict mapping class_idx -> list of sample indices
        labels_array: Original single-label labels
        num_classes: Number of classes
        max_labels: Maximum number of labels per sample
        pattern_based: If True, use realistic drumming patterns
        solo_ratio: Fraction of samples that should be solo (1 label only)
    
    Returns:
        Tuple of (list of source indices to combine, multi-hot label array)
    """
    # Check if this should be a solo sample
    if solo_ratio > 0 and random.random() < solo_ratio:
        # Generate solo sample - pick one random class
        valid_classes = [c for c in single_label_samples if len(single_label_samples[c]) > 0]
        selected_class = random.choice(valid_classes)
        idx = random.choice(single_label_samples[selected_class])
        
        # Create multi-hot label with single class
        multi_hot = np.zeros(num_classes, dtype=np.float32)
        multi_hot[selected_class] = 1.0
        return [idx], multi_hot
    
    if pattern_based and random.random() < 0.7:
        # Use a predefined realistic pattern
        pattern = random.choice(COMMON_PATTERNS)
        # Filter to classes that have samples
        valid_pattern = [c for c in pattern if c in single_label_samples and len(single_label_samples[c]) > 0]
        if len(valid_pattern) >= 2:
            selected_classes = valid_pattern
        else:
            # Fall back to random selection
            valid_classes = [c for c in single_label_samples if len(single_label_samples[c]) > 0]
            num_labels = random.randint(2, min(max_labels, len(valid_classes)))
            selected_classes = random.sample(valid_classes, num_labels)
    else:
        # Random combination
        valid_classes = [c for c in single_label_samples if len(single_label_samples[c]) > 0]
        num_labels = random.randint(2, min(max_labels, len(valid_classes)))
        selected_classes = random.sample(valid_classes, num_labels)
    
    # Select one sample index from each class
    source_indices = []
    for cls in selected_classes:
        idx = random.choice(single_label_samples[cls])
        source_indices.append(idx)
    
    # Create multi-hot label
    multi_hot = np.zeros(num_classes, dtype=np.float32)
    for cls in selected_classes:
        multi_hot[cls] = 1.0
    
    return source_indices, multi_hot


def generate_synthetic_multilabel_dataset(
    input_dir: Path,
    output_dir: Path,
    feature_cache_dir: Optional[Path],
    num_samples: int,
    max_labels: int = 3,
    solo_ratio: float = 0.0,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> None:
    """
    Generate a synthetic multi-label dataset from single-label data.
    
    This creates new samples by:
    1. Randomly selecting 2-3 single-label samples from different classes
    2. Blending their cached spectrograms
    3. Creating multi-hot labels
    
    The blending is done in feature space (spectrograms) which approximates
    how multiple drum hits sound when they overlap.
    """
    random.seed(seed)
    np.random.seed(seed)
    
    # Load single-label data
    train_dir = input_dir / "train"
    labels_npy = train_dir / "train_labels_labels.npy"
    files_npy = train_dir / "train_labels_files.npy"
    
    if not labels_npy.exists():
        raise FileNotFoundError(f"Labels not found: {labels_npy}")
    
    labels = np.load(labels_npy)
    
    # Try to load files array
    files = None
    if files_npy.exists():
        try:
            files = np.load(files_npy, allow_pickle=True)
        except Exception:
            pass
    
    component_names = load_components_json(input_dir)
    num_classes = len(component_names)
    
    print(f"Source dataset: {len(labels):,} single-label samples")
    print(f"Target: {num_samples:,} multi-label samples")
    print(f"Max labels per sample: {max_labels}")
    print(f"Solo sample ratio: {solo_ratio:.0%}")
    
    # Build index of samples per class
    samples_by_class = defaultdict(list)
    for idx, label in enumerate(labels):
        samples_by_class[int(label)].append(idx)
    
    print("\nSamples per class:")
    for cls in range(num_classes):
        print(f"  {component_names[cls]}: {len(samples_by_class[cls]):,}")
    
    # Try to load consolidated cache for spectrogram blending
    cache_reader = None
    cache_mapping = None
    
    if feature_cache_dir is not None:
        feature_cache_dir = Path(feature_cache_dir)
        
        # Load cache mapping
        cache_mapping_path = train_dir / "cache_mapping.npz"
        if cache_mapping_path.exists():
            try:
                mapping_data = np.load(cache_mapping_path, allow_pickle=True)
                cache_mapping = {
                    'shard_ids': mapping_data['shard_ids'],
                    'offsets': mapping_data['offsets'],
                    'valid': mapping_data['valid'],
                }
                print(f"Loaded cache mapping: {np.sum(cache_mapping['valid']):,} valid entries")
            except Exception as e:
                print(f"Failed to load cache mapping: {e}")
        
        # Load consolidated cache reader
        train_cache = feature_cache_dir / "train"
        if (train_cache / "manifest.json").exists():
            try:
                from training.utils.consolidated_cache import ConsolidatedCacheReader
                cache_reader = ConsolidatedCacheReader(train_cache)
                print(f"Loaded consolidated cache: {len(cache_reader):,} samples")
            except Exception as e:
                print(f"Failed to load cache reader: {e}")
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy components.json
    shutil.copy(input_dir / "components.json", output_dir / "components.json")
    
    # Generate samples
    train_size = int(num_samples * (1 - val_ratio))
    val_size = num_samples - train_size
    
    print(f"\nGenerating {train_size:,} train + {val_size:,} val samples...")
    
    for split, size in [("train", train_size), ("val", val_size)]:
        split_dir = output_dir / split
        split_dir.mkdir(exist_ok=True)
        
        # We'll store:
        # - Multi-hot labels as 2D numpy array (N, num_classes)
        # - Source indices for each component (for cache lookup)
        # - Blended spectrograms in new consolidated cache
        
        multilabel_labels = np.zeros((size, num_classes), dtype=np.float32)
        source_indices_list = []  # List of (idx1, idx2, ...) tuples
        
        print(f"\n{split.upper()}: Generating {size:,} samples...")
        for i in tqdm(range(size)):
            source_indices, multi_hot = generate_synthetic_multilabel_sample(
                samples_by_class,
                labels,
                num_classes,
                max_labels=max_labels,
                pattern_based=True,
                solo_ratio=solo_ratio,
            )
            multilabel_labels[i] = multi_hot
            source_indices_list.append(source_indices)
        
        # Save multi-label labels (2D multi-hot format)
        np.save(split_dir / "train_labels_labels.npy", multilabel_labels)
        
        # Save source indices for reference
        np.save(split_dir / "source_indices.npy", np.array(source_indices_list, dtype=object), allow_pickle=True)
        
        # Analyze generated data
        labels_per_sample = np.sum(multilabel_labels, axis=1)
        class_counts = np.sum(multilabel_labels, axis=0)
        
        print(f"\n{split.upper()} Statistics:")
        print(f"  Total samples: {size:,}")
        print(f"  Avg labels per sample: {np.mean(labels_per_sample):.2f}")
        print(f"  1-label (solo) samples: {np.sum(labels_per_sample == 1):,} ({100*np.mean(labels_per_sample == 1):.1f}%)")
        print(f"  2-label samples: {np.sum(labels_per_sample == 2):,}")
        print(f"  3-label samples: {np.sum(labels_per_sample == 3):,}")
        print(f"  4-label samples: {np.sum(labels_per_sample == 4):,}")
        
        print("\n  Per-class counts:")
        for idx, name in enumerate(component_names):
            print(f"    {name}: {int(class_counts[idx]):,}")
    
    print(f"\n{'='*60}")
    print(f"Multi-label dataset generated at: {output_dir}")
    print(f"{'='*60}")
    print("\nNOTE: This dataset stores source indices for spectrogram blending.")
    print("The training script will blend spectrograms on-the-fly from the cache.")
    print(f"\nTo train: python training/multilabel/train_multilabel.py \\")
    print(f"    --dataset \"{output_dir}\" \\")
    print(f"    --feature-cache-dir \"{feature_cache_dir}\" \\")
    print(f"    --pretrained-checkpoint runs/v5_phase2/best_drum_classifier.pth")


def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-label drum dataset from single-label data"
    )
    
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Input single-label dataset directory (e.g., F:/datasets/prod_v5_final)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output multi-label dataset directory')
    parser.add_argument('--feature-cache-dir', type=str, default=None,
                        help='Feature cache directory (e.g., F:/feature_cache)')
    parser.add_argument('--mode', type=str, choices=['synthetic', 'analyze'], default='analyze',
                        help='Mode: synthetic (generate data) or analyze (just analyze input)')
    parser.add_argument('--num-samples', type=int, default=5000000,
                        help='Number of multi-label samples to generate')
    parser.add_argument('--max-labels', type=int, default=4,
                        help='Maximum number of labels per sample (default: 4 for full 4-limb independence)')
    parser.add_argument('--solo-ratio', type=float, default=0.0,
                        help='Fraction of samples that are solo (1 label only). Set to 0.25-0.30 for better single-class learning.')
    parser.add_argument('--val-ratio', type=float, default=0.1,
                        help='Validation split ratio')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    
    if not input_dir.exists():
        print(f"ERROR: Input directory not found: {input_dir}")
        return
    
    if args.mode == 'analyze':
        # Just analyze the single-label dataset
        analyze_single_label_dataset(input_dir, "train")
        if (input_dir / "val").exists():
            analyze_single_label_dataset(input_dir, "val")
    
    elif args.mode == 'synthetic':
        if args.output is None:
            args.output = str(input_dir) + "_multilabel"
        
        output_dir = Path(args.output)
        feature_cache_dir = Path(args.feature_cache_dir) if args.feature_cache_dir else None
        
        generate_synthetic_multilabel_dataset(
            input_dir=input_dir,
            output_dir=output_dir,
            feature_cache_dir=feature_cache_dir,
            num_samples=args.num_samples,
            max_labels=args.max_labels,
            solo_ratio=args.solo_ratio,
            val_ratio=args.val_ratio,
            seed=args.seed,
        )


if __name__ == '__main__':
    main()
