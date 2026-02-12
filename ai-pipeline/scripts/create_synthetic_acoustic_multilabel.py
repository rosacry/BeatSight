#!/usr/bin/env python3
"""
Create Synthetic Acoustic Multi-Label Dataset

This script addresses the critical gap in acoustic multi-label training data:
- China cymbal only has ~68 acoustic samples in ENST
- Splash cymbal only has ~28 acoustic samples  
- Commercial tracks (Bleed by Meshuggah, etc.) need the model to recognize
  acoustic china/splash played simultaneously with other drums

The approach:
1. Load all batched acoustic spectrograms from ENST, IDMT, Cambridge, etc.
2. Index samples by their primary class (single-label acoustic samples)
3. Generate synthetic multi-label combinations by blending spectrograms
4. Focus heavily on rare classes: china, splash, cross_stick, hihat_pedal, ride_bell
5. Output in the same batched format for seamless integration

Key patterns to generate (metal/rock focus for china):
- china + kick (Meshuggah-style accents)
- china + snare (blast beats with china)
- china + kick + snare (full pattern)
- splash + snare (jazz/pop accents)
- splash + kick (intro accents)

Usage:
    python scripts/create_synthetic_acoustic_multilabel.py \
        --dataset F:/datasets/multilabel_real_v3 \
        --output F:/datasets/multilabel_real_v3/acoustic_synth \
        --num-samples 100000 \
        --oversample-rare 10
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from tqdm import tqdm

# 12-Class drum components
CLASS_NAMES = [
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

# Rare classes that need heavy oversampling in combinations
RARE_CLASSES = {0, 2, 5, 7, 10}  # china, cross_stick, hihat_pedal, ride_bell, splash

# Acoustic sources to load from
ACOUSTIC_SOURCES = [
    'enst_drums',
    'idmt_smt_drums_v2', 
    'cambridge_multitrack',
    'telefunken',
    'signaturesounds',
    'medleydb',
]

# Realistic multi-label patterns for acoustic drums
# Focus on combinations involving rare classes
ACOUSTIC_PATTERNS = [
    # =========================================================================
    # CHINA PATTERNS (most important for metal)
    # =========================================================================
    [0, 6],          # china + kick (Meshuggah, Gojira style)
    [0, 9],          # china + snare
    [0, 6, 9],       # china + kick + snare (blast with china)
    [0, 3],          # china + hihat_closed
    [0, 11],         # china + tom
    [0, 6, 11],      # china + kick + tom
    [0, 9, 11],      # china + snare + tom
    [0, 6, 3],       # china + kick + hihat_closed
    [0, 9, 3],       # china + snare + hihat_closed
    
    # =========================================================================
    # SPLASH PATTERNS
    # =========================================================================
    [10, 6],         # splash + kick
    [10, 9],         # splash + snare  
    [10, 6, 9],      # splash + kick + snare
    [10, 3],         # splash + hihat_closed
    [10, 11],        # splash + tom
    [10, 6, 3],      # splash + kick + hihat_closed
    
    # =========================================================================
    # CROSS_STICK PATTERNS (jazz, ballads)
    # =========================================================================
    [2, 6],          # cross_stick + kick
    [2, 8],          # cross_stick + ride_bow
    [2, 3],          # cross_stick + hihat_closed
    [2, 5],          # cross_stick + hihat_pedal
    [2, 6, 8],       # cross_stick + kick + ride_bow
    [2, 6, 5],       # cross_stick + kick + hihat_pedal
    
    # =========================================================================
    # HIHAT_PEDAL PATTERNS (4-limb independence)
    # =========================================================================
    [5, 8, 6],       # hihat_pedal + ride_bow + kick
    [5, 8, 9],       # hihat_pedal + ride_bow + snare
    [5, 1, 6],       # hihat_pedal + crash + kick
    [5, 1, 9],       # hihat_pedal + crash + snare
    [5, 8, 9, 6],    # hihat_pedal + ride_bow + snare + kick (4 limbs)
    [5, 0, 6],       # hihat_pedal + china + kick
    [5, 0, 9],       # hihat_pedal + china + snare
    
    # =========================================================================
    # RIDE_BELL PATTERNS
    # =========================================================================
    [7, 6],          # ride_bell + kick
    [7, 9],          # ride_bell + snare
    [7, 6, 9],       # ride_bell + kick + snare
    [7, 5],          # ride_bell + hihat_pedal
    [7, 6, 5],       # ride_bell + kick + hihat_pedal
    
    # =========================================================================
    # STANDARD ACOUSTIC PATTERNS (for balance)
    # =========================================================================
    [6, 3],          # kick + hihat_closed
    [6, 4],          # kick + hihat_open
    [6, 9],          # kick + snare
    [9, 3],          # snare + hihat_closed
    [9, 4],          # snare + hihat_open
    [6, 1],          # kick + crash
    [9, 1],          # snare + crash
    [6, 9, 3],       # kick + snare + hihat_closed
    [6, 9, 1],       # kick + snare + crash
    [6, 11],         # kick + tom
    [9, 11],         # snare + tom
    [6, 9, 11],      # kick + snare + tom
]


def load_acoustic_samples(
    dataset_path: Path,
    acoustic_sources: List[str],
) -> Tuple[Dict[int, List[Tuple[np.ndarray, int]]], Dict[str, int]]:
    """
    Load all acoustic samples and index by class.
    
    Returns:
        samples_by_class: Dict mapping class_idx -> list of (spectrogram, source_idx)
        source_stats: Dict mapping source_name -> sample_count
    """
    samples_by_class: Dict[int, List[Tuple[np.ndarray, int]]] = {i: [] for i in range(12)}
    source_stats: Dict[str, int] = {}
    
    for source in acoustic_sources:
        source_dir = dataset_path / source
        manifest_path = source_dir / f"{source}_manifest.json"
        
        if not manifest_path.exists():
            print(f"  Skipping {source}: manifest not found")
            continue
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        batches = manifest.get('batches', [])
        if isinstance(batches, dict):
            batches = list(batches.values())
        
        # Find batch directory
        batch_dir = source_dir
        for subdir in source_dir.iterdir():
            if subdir.is_dir() and 'batches' in subdir.name:
                batch_dir = subdir
                break
        
        source_count = 0
        for batch_info in tqdm(batches, desc=f"Loading {source}", leave=False):
            feat_file = batch_info.get('features') or batch_info.get('features_file')
            label_file = batch_info.get('labels') or batch_info.get('labels_file')
            
            feat_path = batch_dir / feat_file
            label_path = batch_dir / label_file
            
            if not feat_path.exists() or not label_path.exists():
                continue
            
            features = np.load(feat_path)
            labels = np.load(label_path)
            
            # Index samples by their active classes
            # For multi-label samples, we find the "primary" class for indexing
            # but also index under all active classes
            for i in range(len(labels)):
                active_classes = np.where(labels[i] > 0.5)[0]
                
                if len(active_classes) == 0:
                    continue
                
                # Store under each active class (allows finding samples with specific class)
                for cls_idx in active_classes:
                    samples_by_class[cls_idx].append((features[i], len(active_classes)))
                    source_count += 1
        
        source_stats[source] = source_count
        print(f"  {source}: {source_count:,} class instances")
    
    return samples_by_class, source_stats


def blend_spectrograms(
    specs: List[np.ndarray],
    method: str = 'max',
) -> np.ndarray:
    """
    Blend multiple spectrograms into one.
    
    Args:
        specs: List of spectrograms, each (H, W) or (C, H, W)
        method: Blending method - 'max', 'mean', or 'softmax'
    
    Returns:
        Blended spectrogram
    """
    # Ensure all have same shape
    stacked = np.stack(specs, axis=0)  # (N, H, W) or (N, C, H, W)
    
    if method == 'max':
        return np.max(stacked, axis=0)
    elif method == 'mean':
        return np.mean(stacked, axis=0)
    elif method == 'softmax':
        # Soft-max blending (smoother than max)
        temp = 2.0
        weights = np.exp(stacked / temp)
        weights = weights / weights.sum(axis=0, keepdims=True)
        return (weights * stacked).sum(axis=0)
    else:
        return np.max(stacked, axis=0)


def generate_synthetic_sample(
    samples_by_class: Dict[int, List[Tuple[np.ndarray, int]]],
    pattern: List[int],
    blend_method: str = 'max',
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate a synthetic multi-label sample from a pattern.
    
    Args:
        samples_by_class: Dict mapping class_idx -> list of (spectrogram, num_labels)
        pattern: List of class indices to combine
        blend_method: Spectrogram blending method
    
    Returns:
        Tuple of (blended_spectrogram, multi_hot_label)
    """
    specs = []
    valid_classes = []
    
    for cls_idx in pattern:
        if len(samples_by_class[cls_idx]) > 0:
            # Prefer samples that are solo (num_labels == 1) for cleaner blending
            candidates = samples_by_class[cls_idx]
            solo_candidates = [s for s, n in candidates if n == 1]
            
            if solo_candidates:
                spec = random.choice(solo_candidates)
            else:
                spec, _ = random.choice(candidates)
            
            specs.append(spec)
            valid_classes.append(cls_idx)
    
    if len(specs) == 0:
        return None, None
    
    # Blend spectrograms
    blended = blend_spectrograms(specs, method=blend_method)
    
    # Create multi-hot label
    label = np.zeros(12, dtype=np.float32)
    for cls_idx in valid_classes:
        label[cls_idx] = 1.0
    
    return blended.astype(np.float32), label


def create_synthetic_dataset(
    dataset_path: Path,
    output_path: Path,
    num_samples: int = 100000,
    oversample_rare: int = 10,
    batch_size: int = 2500,
    blend_method: str = 'max',
    seed: int = 42,
):
    """
    Create synthetic acoustic multi-label dataset.
    
    Args:
        dataset_path: Path to multilabel_real_v3 dataset
        output_path: Output directory for synthetic dataset
        num_samples: Total number of samples to generate
        oversample_rare: How many times more to sample patterns with rare classes
        batch_size: Samples per batch file
        blend_method: Spectrogram blending method
        seed: Random seed
    """
    random.seed(seed)
    np.random.seed(seed)
    
    print(f"\n{'='*60}")
    print("Creating Synthetic Acoustic Multi-Label Dataset")
    print(f"{'='*60}")
    print(f"Output: {output_path}")
    print(f"Target samples: {num_samples:,}")
    print(f"Rare class oversample: {oversample_rare}x")
    print(f"Blend method: {blend_method}")
    print()
    
    # Load acoustic samples
    print("Loading acoustic source data...")
    samples_by_class, source_stats = load_acoustic_samples(dataset_path, ACOUSTIC_SOURCES)
    
    # Print class availability
    print("\nClass availability:")
    for i, name in enumerate(CLASS_NAMES):
        count = len(samples_by_class[i])
        marker = " ⚠️ RARE" if i in RARE_CLASSES else ""
        print(f"  {name:<15} {count:>6,} samples{marker}")
    
    # Filter patterns to only those we can actually generate
    valid_patterns = []
    for pattern in ACOUSTIC_PATTERNS:
        can_generate = all(len(samples_by_class[c]) > 0 for c in pattern)
        if can_generate:
            # Check if pattern contains rare classes
            has_rare = any(c in RARE_CLASSES for c in pattern)
            weight = oversample_rare if has_rare else 1
            valid_patterns.extend([pattern] * weight)
    
    if not valid_patterns:
        print("\n❌ ERROR: No valid patterns can be generated (missing class samples)")
        return
    
    print(f"\nValid patterns: {len(set(tuple(p) for p in valid_patterns))} unique")
    print(f"Pattern pool size: {len(valid_patterns)} (with oversampling)")
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    batch_dir = output_path / "acoustic_synth_batches"
    batch_dir.mkdir(exist_ok=True)
    
    # Generate samples
    print(f"\nGenerating {num_samples:,} synthetic samples...")
    
    all_features = []
    all_labels = []
    batch_idx = 0
    batches_info = []
    
    for i in tqdm(range(num_samples)):
        # Pick a random pattern
        pattern = random.choice(valid_patterns)
        
        # Generate sample
        spec, label = generate_synthetic_sample(samples_by_class, pattern, blend_method)
        
        if spec is None:
            continue
        
        all_features.append(spec)
        all_labels.append(label)
        
        # Save batch when full
        if len(all_features) >= batch_size:
            feat_arr = np.stack(all_features, axis=0)
            label_arr = np.stack(all_labels, axis=0)
            
            feat_file = f"features_batch_{batch_idx}.npy"
            label_file = f"labels_batch_{batch_idx}.npy"
            
            np.save(batch_dir / feat_file, feat_arr)
            np.save(batch_dir / label_file, label_arr)
            
            batches_info.append({
                "features": f"acoustic_synth_batches/{feat_file}",
                "labels": f"acoustic_synth_batches/{label_file}",
                "samples": len(all_features),
            })
            
            all_features = []
            all_labels = []
            batch_idx += 1
    
    # Save remaining samples
    if all_features:
        feat_arr = np.stack(all_features, axis=0)
        label_arr = np.stack(all_labels, axis=0)
        
        feat_file = f"features_batch_{batch_idx}.npy"
        label_file = f"labels_batch_{batch_idx}.npy"
        
        np.save(batch_dir / feat_file, feat_arr)
        np.save(batch_dir / label_file, label_arr)
        
        batches_info.append({
            "features": f"acoustic_synth_batches/{feat_file}",
            "labels": f"acoustic_synth_batches/{label_file}",
            "samples": len(all_features),
        })
    
    # Calculate total samples and class distribution
    total_samples = sum(b["samples"] for b in batches_info)
    
    # Create manifest
    manifest = {
        "dataset": "acoustic_synth",
        "description": "Synthetic acoustic multi-label combinations (china, splash, cross_stick focus)",
        "total_samples": total_samples,
        "batch_count": len(batches_info),
        "batches": batches_info,
        "generation_params": {
            "num_samples_requested": num_samples,
            "oversample_rare": oversample_rare,
            "blend_method": blend_method,
            "seed": seed,
            "sources": ACOUSTIC_SOURCES,
        }
    }
    
    manifest_path = output_path / "acoustic_synth_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'='*60}")
    print("Generation Complete!")
    print(f"{'='*60}")
    print(f"Total samples generated: {total_samples:,}")
    print(f"Batches: {len(batches_info)}")
    print(f"Manifest: {manifest_path}")
    print(f"\nTo include in training, the script will auto-discover this manifest")
    print(f"from: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Create synthetic acoustic multi-label dataset"
    )
    
    parser.add_argument('--dataset', type=str, default="F:/datasets/multilabel_real_v3",
                        help='Path to multilabel_real_v3 dataset with acoustic sources')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory (default: {dataset}/acoustic_synth)')
    parser.add_argument('--num-samples', type=int, default=100000,
                        help='Number of synthetic samples to generate')
    parser.add_argument('--oversample-rare', type=int, default=10,
                        help='How many times more to sample patterns with rare classes')
    parser.add_argument('--batch-size', type=int, default=2500,
                        help='Samples per batch file')
    parser.add_argument('--blend-method', type=str, default='max',
                        choices=['max', 'mean', 'softmax'],
                        help='Spectrogram blending method')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed')
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    output_path = Path(args.output) if args.output else dataset_path / "acoustic_synth"
    
    if not dataset_path.exists():
        print(f"ERROR: Dataset path not found: {dataset_path}")
        return
    
    create_synthetic_dataset(
        dataset_path=dataset_path,
        output_path=output_path,
        num_samples=args.num_samples,
        oversample_rare=args.oversample_rare,
        batch_size=args.batch_size,
        blend_method=args.blend_method,
        seed=args.seed,
    )


if __name__ == '__main__':
    main()
