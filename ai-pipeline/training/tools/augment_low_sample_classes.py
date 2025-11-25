#!/usr/bin/env python3
"""
Data Augmentation for Low-Sample Classes

Generates augmented versions of audio samples for classes with insufficient
training data. This is critical for multi-cymbal support (crash_1, crash_2, etc.)
where real-world kits have multiple cymbals but labeled data is scarce.

Augmentation techniques:
1. Pitch shifting (±2 semitones) - simulates different cymbal sizes
2. Time stretching (0.9x-1.1x) - varies decay characteristics  
3. Gain variation (±3dB) - simulates different hit intensities
4. Noise injection - improves robustness
5. Room reverb simulation - simulates different recording environments

Usage:
    python augment_low_sample_classes.py --dataset E:/data/prod_combined_profile_run \
        --min-samples 1000 --augment-factor 5 --dry-run
        
    python augment_low_sample_classes.py --dataset E:/data/prod_combined_profile_run \
        --min-samples 1000 --augment-factor 5 --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

try:
    import librosa
    import soundfile as sf
    HAS_AUDIO_LIBS = True
except ImportError:
    HAS_AUDIO_LIBS = False


@dataclass
class AugmentationConfig:
    """Configuration for audio augmentation."""
    pitch_shift_semitones: Tuple[float, float] = (-2.0, 2.0)
    time_stretch_range: Tuple[float, float] = (0.9, 1.1)
    gain_db_range: Tuple[float, float] = (-3.0, 3.0)
    noise_factor_range: Tuple[float, float] = (0.0, 0.005)
    sample_rate: int = 44100


def load_audio(path: Path, sr: int = 44100) -> np.ndarray:
    """Load audio file."""
    audio, _ = librosa.load(str(path), sr=sr, mono=True)
    return audio


def save_audio(path: Path, audio: np.ndarray, sr: int = 44100) -> None:
    """Save audio file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr)


def augment_audio(
    audio: np.ndarray,
    sr: int,
    config: AugmentationConfig,
    rng: random.Random,
) -> np.ndarray:
    """Apply random augmentations to audio."""
    augmented = audio.copy()
    
    # 1. Pitch shift (simulates different cymbal sizes/tunings)
    if rng.random() < 0.7:
        semitones = rng.uniform(*config.pitch_shift_semitones)
        augmented = librosa.effects.pitch_shift(augmented, sr=sr, n_steps=semitones)
    
    # 2. Time stretch (varies attack/decay characteristics)
    if rng.random() < 0.5:
        rate = rng.uniform(*config.time_stretch_range)
        augmented = librosa.effects.time_stretch(augmented, rate=rate)
    
    # 3. Gain variation (different hit intensities)
    gain_db = rng.uniform(*config.gain_db_range)
    gain_linear = 10 ** (gain_db / 20)
    augmented = augmented * gain_linear
    
    # 4. Add subtle noise (improves robustness)
    if rng.random() < 0.3:
        noise_factor = rng.uniform(*config.noise_factor_range)
        noise = np.random.randn(len(augmented)) * noise_factor
        augmented = augmented + noise
    
    # Normalize to prevent clipping
    max_val = np.abs(augmented).max()
    if max_val > 0.99:
        augmented = augmented * 0.99 / max_val
    
    return augmented


def get_class_counts(labels: List[Dict[str, Any]]) -> Dict[str, int]:
    """Count samples per class."""
    return Counter(item.get("label", "") for item in labels)


def find_samples_for_class(
    labels: List[Dict[str, Any]],
    target_class: str,
) -> List[Dict[str, Any]]:
    """Find all samples belonging to a class."""
    return [item for item in labels if item.get("label") == target_class]


def generate_augmented_id(original_id: str, aug_index: int) -> str:
    """Generate unique ID for augmented sample."""
    combined = f"{original_id}_aug{aug_index}"
    return hashlib.sha1(combined.encode()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(
        description="Augment low-sample classes in BeatSight dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to dataset directory",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=1000,
        help="Minimum samples threshold - classes below this get augmented (default: 1000)",
    )
    parser.add_argument(
        "--augment-factor",
        type=int,
        default=5,
        help="How many augmented copies to create per original sample (default: 5)",
    )
    parser.add_argument(
        "--target-classes",
        nargs="+",
        help="Specific classes to augment (default: auto-detect low-sample classes)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply augmentation and write files",
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.apply:
        parser.error("Must specify either --dry-run or --apply")
    
    if not HAS_AUDIO_LIBS:
        parser.error("librosa and soundfile are required. Install with: pip install librosa soundfile")
    
    dataset_dir = args.dataset.resolve()
    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)
    config = AugmentationConfig()
    
    print("=" * 60)
    print("BeatSight Low-Sample Class Augmentation")
    print("=" * 60)
    print(f"Dataset: {dataset_dir}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY'}")
    print(f"Min samples threshold: {args.min_samples}")
    print(f"Augmentation factor: {args.augment_factor}x")
    print()
    
    # Load existing labels
    train_labels_path = dataset_dir / "train" / "train_labels.json"
    if not train_labels_path.exists():
        parser.error(f"Train labels not found: {train_labels_path}")
    
    with train_labels_path.open() as f:
        train_labels = json.load(f)
    
    # Analyze class distribution
    class_counts = get_class_counts(train_labels)
    
    # Determine which classes need augmentation
    if args.target_classes:
        target_classes = set(args.target_classes)
    else:
        target_classes = {
            cls for cls, count in class_counts.items()
            if count < args.min_samples and count > 0
        }
    
    print("Classes needing augmentation:")
    for cls in sorted(target_classes):
        count = class_counts.get(cls, 0)
        target = args.min_samples
        needed = max(0, target - count)
        aug_copies = min(args.augment_factor, (needed // max(count, 1)) + 1)
        print(f"  {cls}: {count} → ~{count + count * aug_copies} (need {needed} more)")
    
    if not target_classes:
        print("  (none - all classes have sufficient samples)")
        return
    
    print()
    
    # Process each target class
    total_augmented = 0
    new_labels = []
    
    for target_class in sorted(target_classes):
        samples = find_samples_for_class(train_labels, target_class)
        if not samples:
            continue
        
        print(f"Processing {target_class} ({len(samples)} samples)...")
        
        for sample in samples:
            audio_path = dataset_dir / "train" / sample["file"]
            
            if not audio_path.exists():
                print(f"  Warning: Audio not found: {audio_path}")
                continue
            
            if args.apply:
                try:
                    audio = load_audio(audio_path, config.sample_rate)
                except Exception as e:
                    print(f"  Warning: Failed to load {audio_path}: {e}")
                    continue
            
            for aug_idx in range(args.augment_factor):
                aug_id = generate_augmented_id(sample.get("event_id", ""), aug_idx)
                
                # Create augmented filename
                original_file = Path(sample["file"])
                aug_filename = original_file.with_stem(f"{original_file.stem}_aug{aug_idx}")
                aug_path = dataset_dir / "train" / aug_filename
                
                if args.apply:
                    # Generate augmented audio
                    aug_audio = augment_audio(audio, config.sample_rate, config, rng)
                    save_audio(aug_path, aug_audio, config.sample_rate)
                
                # Create label entry
                aug_label = dict(sample)
                aug_label["file"] = str(aug_filename)
                aug_label["event_id"] = aug_id
                aug_label["augmented_from"] = sample.get("event_id", "")
                aug_label["augmentation_index"] = aug_idx
                
                new_labels.append(aug_label)
                total_augmented += 1
        
        print(f"  Created {len(samples) * args.augment_factor} augmented samples")
    
    print()
    print(f"Total augmented samples: {total_augmented}")
    
    if args.apply and new_labels:
        # Update labels file
        all_labels = train_labels + new_labels
        
        # Backup original
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = train_labels_path.with_suffix(f".pre_augment_{timestamp}.json")
        
        import shutil
        shutil.copy2(train_labels_path, backup_path)
        print(f"Backed up labels to: {backup_path}")
        
        with train_labels_path.open("w") as f:
            json.dump(all_labels, f, indent=2)
        print(f"Updated: {train_labels_path}")
        
        # Update components.json counts
        components_path = dataset_dir / "components.json"
        if components_path.exists():
            with components_path.open() as f:
                components = json.load(f)
            
            # Recount
            new_counts = get_class_counts(all_labels)
            components["counts"] = dict(new_counts)
            
            with components_path.open("w") as f:
                json.dump(components, f, indent=2)
            print(f"Updated: {components_path}")
    
    print()
    print("=" * 60)
    if args.dry_run:
        print("DRY RUN COMPLETE - No files were modified")
        print("Run with --apply to generate augmented samples")
    else:
        print("AUGMENTATION COMPLETE")
        print()
        print("Next steps:")
        print("  1. Clear feature cache for augmented samples (or entire cache)")
        print("  2. Re-run training with the expanded dataset")
    print("=" * 60)


if __name__ == "__main__":
    main()
