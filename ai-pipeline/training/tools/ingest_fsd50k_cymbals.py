#!/usr/bin/env python3
"""
Ingest FSD50K cymbal samples into the training dataset.

This script:
1. Reads FSD50K ground truth to identify cymbal samples
2. Computes mel spectrograms for each sample
3. Saves features to the feature cache
4. Appends file IDs to the dataset numpy arrays

Usage:
    python ingest_fsd50k_cymbals.py --fsd50k-dir F:/datasets/fsd50k --dataset-dir F:/datasets/prod_v5_fixed_20251212 --feature-cache F:/feature_cache
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import numpy as np
import torch

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import librosa
    import soundfile as sf
except ImportError:
    logger.error("Required packages not installed. Run: pip install librosa soundfile")
    sys.exit(1)


# Mapping from FSD50K labels to our drum classes
# FSD50K uses AudioSet ontology labels
FSD50K_TO_DRUM_CLASS = {
    # Cymbal mappings
    "Cymbal": "crash",           # Generic cymbal -> crash
    "Crash_cymbal": "crash",     # Crash cymbal -> crash  
    "Hi-hat": "hihat_closed",    # Hi-hat -> closed (default)
    "Splash_cymbal": "splash",   # Splash! RARE CLASS!
    "China_cymbal": "china",     # China! RARE CLASS! (if exists)
    "Ride_cymbal": "ride_bow",   # Ride -> bow (default)
    
    # Drum mappings (bonus)
    "Drum": None,                # Too generic, skip
    "Drum_kit": None,            # Too generic, skip
    "Bass_drum": "kick",
    "Snare_drum": "snare",
    "Percussion": None,          # Too generic, skip
    "Timpani": "tom",            # Close enough
    "Gong": None,                # Not a standard kit component
    "Tambourine": None,          # Not in our classes
}


def load_fsd50k_labels(ground_truth_dir: Path) -> Dict[str, List[str]]:
    """Load FSD50K labels from dev.csv and eval.csv."""
    labels = {}
    
    for csv_file in ["dev.csv", "eval.csv"]:
        csv_path = ground_truth_dir / csv_file
        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            continue
            
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = row['fname'].replace('.wav', '')
                file_labels = row['labels'].split(',')
                labels[fname] = file_labels
    
    logger.info(f"Loaded {len(labels):,} samples from FSD50K ground truth")
    return labels


def filter_drum_samples(labels: Dict[str, List[str]]) -> Dict[str, str]:
    """Filter samples that contain drum/cymbal classes and map to our classes."""
    drum_samples = {}
    class_counts = Counter()
    
    for fname, file_labels in labels.items():
        # Find the first matching drum class
        for label in file_labels:
            if label in FSD50K_TO_DRUM_CLASS:
                drum_class = FSD50K_TO_DRUM_CLASS[label]
                if drum_class is not None:
                    drum_samples[fname] = drum_class
                    class_counts[drum_class] += 1
                    break
    
    logger.info(f"Found {len(drum_samples):,} drum/cymbal samples:")
    for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        rare_marker = " [RARE!]" if cls in ["china", "splash"] else ""
        logger.info(f"  {cls}: {count:,}{rare_marker}")
    
    return drum_samples


def compute_mel_spectrogram(
    audio_path: Path,
    sr: int = 22050,
    n_mels: int = 128,
    hop_length: int = 512,
    n_fft: int = 2048,
    target_frames: int = 128
) -> Optional[np.ndarray]:
    """Compute mel spectrogram for an audio file."""
    try:
        # Load audio
        y, file_sr = librosa.load(audio_path, sr=sr, mono=True)
        
        if len(y) == 0:
            return None
        
        # Compute mel spectrogram
        mel = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_mels=n_mels,
            hop_length=hop_length,
            n_fft=n_fft,
            fmin=20,
            fmax=8000
        )
        
        # Convert to dB scale
        mel_db = librosa.power_to_db(mel, ref=np.max)
        
        # Normalize to 0-1 range
        mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
        
        # Pad or truncate to target frames
        if mel_db.shape[1] < target_frames:
            # Pad with zeros
            pad_width = target_frames - mel_db.shape[1]
            mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
        else:
            # Truncate
            mel_db = mel_db[:, :target_frames]
        
        return mel_db.astype(np.float32)
        
    except Exception as e:
        logger.debug(f"Error processing {audio_path}: {e}")
        return None


def process_fsd50k_samples(
    drum_samples: Dict[str, str],
    audio_dir: Path,
    feature_cache: Path,
    class_to_idx: Dict[str, int],
    existing_ids: Set[str],
    dry_run: bool = False
) -> Tuple[List[str], List[int]]:
    """Process FSD50K samples and save features."""
    
    new_file_ids = []
    new_labels = []
    processed = 0
    skipped_exists = 0
    skipped_no_audio = 0
    skipped_error = 0
    
    total = len(drum_samples)
    
    for i, (fname, drum_class) in enumerate(drum_samples.items()):
        if (i + 1) % 100 == 0:
            logger.info(f"Processing {i+1}/{total} ({processed} new, {skipped_exists} exist)")
        
        # Create feature ID
        feature_id = f"fsd50k_{drum_class}_{fname}"
        
        # Skip if already in dataset
        if feature_id in existing_ids:
            skipped_exists += 1
            continue
        
        # Find audio file
        audio_path = audio_dir / f"{fname}.wav"
        if not audio_path.exists():
            skipped_no_audio += 1
            continue
        
        if dry_run:
            new_file_ids.append(feature_id)
            new_labels.append(class_to_idx[drum_class])
            processed += 1
            continue
        
        # Compute mel spectrogram
        mel = compute_mel_spectrogram(audio_path)
        if mel is None:
            skipped_error += 1
            continue
        
        # Save feature
        feature_path = feature_cache / f"{feature_id}.pt"
        torch.save(torch.from_numpy(mel), feature_path)
        
        new_file_ids.append(feature_id)
        new_labels.append(class_to_idx[drum_class])
        processed += 1
    
    logger.info(f"\nProcessing complete:")
    logger.info(f"  New features: {processed:,}")
    logger.info(f"  Skipped (already exist): {skipped_exists:,}")
    logger.info(f"  Skipped (no audio): {skipped_no_audio:,}")
    logger.info(f"  Skipped (error): {skipped_error:,}")
    
    return new_file_ids, new_labels


def append_to_dataset(
    dataset_dir: Path,
    new_file_ids: List[str],
    new_labels: List[int],
    dry_run: bool = False
):
    """Append new samples to dataset numpy arrays."""
    
    # Check for both naming conventions
    train_dir = dataset_dir / "train"
    if train_dir.exists():
        file_ids_path = train_dir / "train_labels_files.npy"
        labels_path = train_dir / "train_labels_labels.npy"
    else:
        file_ids_path = dataset_dir / "file_ids.npy"
        labels_path = dataset_dir / "labels.npy"
    
    if not file_ids_path.exists() or not labels_path.exists():
        logger.error(f"Dataset files not found in {dataset_dir}")
        return False
    
    # Load existing
    existing_ids = np.load(file_ids_path)
    existing_labels = np.load(labels_path)
    
    logger.info(f"Existing dataset: {len(existing_ids):,} samples")
    
    if dry_run:
        logger.info(f"[DRY RUN] Would append {len(new_file_ids):,} samples")
        return True
    
    # Append
    new_ids_array = np.array(new_file_ids, dtype=object)
    new_labels_array = np.array(new_labels, dtype=existing_labels.dtype)
    
    updated_ids = np.concatenate([existing_ids, new_ids_array])
    updated_labels = np.concatenate([existing_labels, new_labels_array])
    
    # Backup existing
    file_ids_path.rename(file_ids_path.with_suffix('.npy.bak'))
    labels_path.rename(labels_path.with_suffix('.npy.bak'))
    
    # Save updated
    np.save(file_ids_path, updated_ids)
    np.save(labels_path, updated_labels)
    
    logger.info(f"Updated dataset: {len(updated_ids):,} samples (+{len(new_file_ids):,})")
    
    # Count by class
    class_counts = Counter(new_labels)
    logger.info("New samples by class:")
    for cls_idx, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  Class {cls_idx}: {count:,}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Ingest FSD50K cymbal samples")
    parser.add_argument("--fsd50k-dir", type=str, required=True,
                        help="Path to FSD50K directory")
    parser.add_argument("--dataset-dir", type=str, required=True,
                        help="Path to training dataset directory")
    parser.add_argument("--feature-cache", type=str, required=True,
                        help="Path to feature cache directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    fsd50k_dir = Path(args.fsd50k_dir)
    dataset_dir = Path(args.dataset_dir)
    feature_cache = Path(args.feature_cache)
    
    # Validate paths
    if not fsd50k_dir.exists():
        logger.error(f"FSD50K directory not found: {fsd50k_dir}")
        return
    
    ground_truth_dir = fsd50k_dir / "FSD50K.ground_truth"
    if not ground_truth_dir.exists():
        logger.error(f"Ground truth directory not found: {ground_truth_dir}")
        return
    
    audio_dir = fsd50k_dir / "FSD50K.dev_audio"
    if not audio_dir.exists():
        logger.error(f"Audio directory not found: {audio_dir}")
        return
    
    if not dataset_dir.exists():
        logger.error(f"Dataset directory not found: {dataset_dir}")
        return
    
    feature_cache.mkdir(parents=True, exist_ok=True)
    
    # Load class mapping from components.json
    components_path = Path(__file__).parent.parent / "components.json"
    if components_path.exists():
        import json
        with open(components_path) as f:
            components = json.load(f)
        class_to_idx = {name: idx for idx, name in enumerate(components)}
    else:
        # Default 12-class mapping (rimshot merged into snare)
        class_to_idx = {
            "china": 0, "crash": 1, "cross_stick": 2, "hihat_closed": 3,
            "hihat_open": 4, "hihat_pedal": 5, "kick": 6, "ride_bell": 7,
            "ride_bow": 8, "snare": 9, "splash": 10, "tom": 11
        }
    
    logger.info(f"Class mapping: {class_to_idx}")
    
    # Get existing file IDs - check both naming conventions
    train_dir = dataset_dir / "train"
    if train_dir.exists():
        file_ids_path = train_dir / "train_labels_files.npy"
    else:
        file_ids_path = dataset_dir / "file_ids.npy"
    
    existing_ids = set()
    if file_ids_path.exists():
        existing_ids = set(np.load(file_ids_path, allow_pickle=True).tolist())
    logger.info(f"Existing dataset has {len(existing_ids):,} samples")
    
    # Load FSD50K labels
    labels = load_fsd50k_labels(ground_truth_dir)
    
    # Filter to drum/cymbal samples
    drum_samples = filter_drum_samples(labels)
    
    if not drum_samples:
        logger.warning("No drum/cymbal samples found!")
        return
    
    # Process samples
    new_file_ids, new_labels = process_fsd50k_samples(
        drum_samples,
        audio_dir,
        feature_cache,
        class_to_idx,
        existing_ids,
        dry_run=args.dry_run
    )
    
    if not new_file_ids:
        logger.info("No new samples to add")
        return
    
    # Append to dataset
    if not args.dry_run:
        append_to_dataset(dataset_dir, new_file_ids, new_labels, dry_run=False)
    else:
        logger.info(f"[DRY RUN] Would append {len(new_file_ids):,} samples")


if __name__ == "__main__":
    main()
