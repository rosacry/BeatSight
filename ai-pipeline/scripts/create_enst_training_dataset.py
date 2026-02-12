#!/usr/bin/env python3
"""
Create ENST Training Dataset

This script processes the ENST-Drums dataset (real acoustic drum recordings)
and creates batched .npy files compatible with the multilabel_real_v3 format.

Adding real acoustic drums to training helps the model generalize beyond
synthesized/electronic drums.

Usage:
    python scripts/create_enst_training_dataset.py \
        --enst-root D:/data/raw/ENST-Drums \
        --output-dir F:/datasets/multilabel_real_v3/enst_real \
        --train-ratio 0.8

Note: We use 80% for training, keeping 20% as validation for domain adaptation.
"""

from __future__ import annotations

import argparse
import json
import numpy as np
from pathlib import Path
from collections import Counter
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    import librosa
except ImportError:
    print("ERROR: librosa required. Install with: pip install librosa")
    exit(1)


# 12-class mapping (must match DEFAULT_DRUM_COMPONENTS)
CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]

# Map ENST manifest labels to 12-class indices
LABEL_TO_IDX = {name: i for i, name in enumerate(CLASS_NAMES)}

# Additional mappings for ENST-specific labels
LABEL_REMAP = {
    "tom_high": "tom",
    "tom_mid": "tom", 
    "tom_low": "tom",
    "hihat": "hihat_closed",
    "ride": "ride_bow",
}

# Feature extraction parameters (must match training exactly)
SAMPLE_RATE = 22050
N_MELS = 128
N_FFT = 2048
FMAX = 8000
TARGET_FRAMES = 128
BATCH_SIZE = 2500


def extract_spectrogram(audio: np.ndarray, sr: int) -> np.ndarray:
    """Extract mel spectrogram matching production pipeline exactly."""
    # Dynamic hop_length to always get ~128 frames
    n_samples = len(audio)
    hop_length = max(1, n_samples // TARGET_FRAMES)
    
    mel_spec = librosa.feature.melspectrogram(
        y=audio,
        sr=sr,
        n_fft=N_FFT,
        hop_length=hop_length,
        n_mels=N_MELS,
        fmax=FMAX,
        power=2.0,
    )
    
    # Convert to dB
    mel_db = librosa.power_to_db(mel_spec, ref=np.max, top_db=80)
    
    # Ensure exactly 128 frames
    if mel_db.shape[1] < TARGET_FRAMES:
        pad_width = TARGET_FRAMES - mel_db.shape[1]
        mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='edge')
    elif mel_db.shape[1] > TARGET_FRAMES:
        mel_db = mel_db[:, :TARGET_FRAMES]
    
    # Min-Max normalization to [0, 1]
    mel_min = mel_db.min()
    mel_max = mel_db.max()
    if mel_max > mel_min:
        mel_db = (mel_db - mel_min) / (mel_max - mel_min)
    else:
        mel_db = np.zeros_like(mel_db)
    
    return mel_db.astype(np.float32)


def load_manifest(manifest_path: Path) -> list:
    """Load ENST events manifest."""
    events = []
    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def process_event(event: dict, enst_root: Path, window_ms: float = 100.0) -> tuple:
    """Process a single event and return (features, labels) or None if failed."""
    try:
        # Get audio path
        audio_rel = event.get('audio_path', '')
        if not audio_rel:
            return None
        
        audio_path = enst_root / audio_rel
        if not audio_path.exists():
            # Try with forward slashes
            audio_path = enst_root / audio_rel.replace('\\', '/')
            if not audio_path.exists():
                return None
        
        # Load audio
        audio, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE, mono=True)
        
        # Get onset time
        onset_time = event.get('onset_time', 0.0)
        
        # Extract window around onset (asymmetric: 1/4 before, 3/4 after)
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)
        
        if end - start < 100:
            return None
        
        segment = audio[start:end]
        
        # Pad if too short
        if len(segment) < window_samples:
            segment = np.pad(segment, (0, window_samples - len(segment)), mode='constant')
        
        # Extract spectrogram
        spec = extract_spectrogram(segment, sr)
        
        # Build multi-hot label vector
        labels = np.zeros(12, dtype=np.float32)
        components = event.get('components', [])
        
        for comp in components:
            raw_label = comp.get('label', '')
            label = LABEL_REMAP.get(raw_label, raw_label)
            
            if label in LABEL_TO_IDX:
                labels[LABEL_TO_IDX[label]] = 1.0
        
        # Skip if no valid labels
        if labels.sum() == 0:
            return None
        
        return spec, labels
    
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser(description="Create ENST training dataset")
    parser.add_argument('--enst-root', type=str, default='D:/data/raw/ENST-Drums',
                        help='Root directory of ENST-Drums dataset')
    parser.add_argument('--manifest', type=str, 
                        default='training/data/manifests/enst_drums_events.jsonl',
                        help='Path to ENST events manifest')
    parser.add_argument('--output-dir', type=str,
                        default='F:/datasets/multilabel_real_v3/enst_real',
                        help='Output directory for batched dataset')
    parser.add_argument('--train-ratio', type=float, default=0.8,
                        help='Ratio of data to use for training (rest for validation)')
    parser.add_argument('--window-ms', type=float, default=100.0,
                        help='Window size in milliseconds')
    parser.add_argument('--max-samples', type=int, default=None,
                        help='Maximum samples to process (for testing)')
    args = parser.parse_args()
    
    enst_root = Path(args.enst_root)
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest)
    
    print("=" * 70)
    print("CREATE ENST TRAINING DATASET")
    print("=" * 70)
    print(f"ENST root: {enst_root}")
    print(f"Output: {output_dir}")
    print(f"Train ratio: {args.train_ratio}")
    
    # Load manifest
    print(f"\nLoading manifest from {manifest_path}...")
    events = load_manifest(manifest_path)
    print(f"  Loaded {len(events):,} events")
    
    if args.max_samples:
        events = events[:args.max_samples]
        print(f"  Limited to {len(events):,} samples for testing")
    
    # Process all events
    print("\nExtracting features...")
    features_list = []
    labels_list = []
    label_counts = Counter()
    
    for event in tqdm(events, desc="Processing"):
        result = process_event(event, enst_root, args.window_ms)
        if result is not None:
            spec, labels = result
            features_list.append(spec)
            labels_list.append(labels)
            
            # Track label distribution
            for i in range(12):
                if labels[i] == 1:
                    label_counts[CLASS_NAMES[i]] += 1
    
    print(f"\nSuccessfully processed {len(features_list):,} samples")
    
    # Print label distribution
    print("\nLabel distribution:")
    total = len(features_list)
    for name in CLASS_NAMES:
        count = label_counts[name]
        pct = 100 * count / total if total > 0 else 0
        print(f"  {name:15s}: {count:>6,} ({pct:>5.1f}%)")
    
    # Convert to numpy arrays
    features = np.array(features_list, dtype=np.float32)
    labels = np.array(labels_list, dtype=np.float32)
    
    print(f"\nFeatures shape: {features.shape}")
    print(f"Labels shape: {labels.shape}")
    
    # Shuffle deterministically
    np.random.seed(42)
    indices = np.random.permutation(len(features))
    features = features[indices]
    labels = labels[indices]
    
    # Split into train/val
    split_idx = int(len(features) * args.train_ratio)
    train_features = features[:split_idx]
    train_labels = labels[:split_idx]
    val_features = features[split_idx:]
    val_labels = labels[split_idx:]
    
    print(f"\nTrain samples: {len(train_features):,}")
    print(f"Val samples: {len(val_features):,}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    batch_dir = output_dir / "enst_batches"
    batch_dir.mkdir(exist_ok=True)
    
    # Save batches
    manifest = {
        "dataset": "enst_real",
        "total_samples": len(features),
        "batch_count": 0,
        "sample_rate": SAMPLE_RATE,
        "feature_shape": [N_MELS, TARGET_FRAMES],
        "num_classes": 12,
        "batches": [],
        "train_samples": len(train_features),
        "val_samples": len(val_features),
        "class_distribution": {name: label_counts[name] for name in CLASS_NAMES},
    }
    
    batch_id = 0
    
    for split_name, split_features, split_labels in [
        ("train", train_features, train_labels),
        ("val", val_features, val_labels)
    ]:
        print(f"\nSaving {split_name} batches...")
        
        for start_idx in tqdm(range(0, len(split_features), BATCH_SIZE), desc=f"{split_name}"):
            end_idx = min(start_idx + BATCH_SIZE, len(split_features))
            batch_feats = split_features[start_idx:end_idx]
            batch_labs = split_labels[start_idx:end_idx]
            
            # Save batch files
            feat_file = f"features_batch_{batch_id}.npy"
            label_file = f"labels_batch_{batch_id}.npy"
            
            np.save(batch_dir / feat_file, batch_feats)
            np.save(batch_dir / label_file, batch_labs)
            
            # Multi-label ratio
            multi_count = (batch_labs.sum(axis=1) > 1).sum()
            multi_ratio = multi_count / len(batch_labs)
            
            manifest["batches"].append({
                "features": feat_file,
                "labels": label_file,
                "samples": len(batch_feats),
                "multi_label_ratio": float(multi_ratio),
                "split": split_name,
            })
            
            batch_id += 1
    
    manifest["batch_count"] = batch_id
    
    # Save manifest
    manifest_path = output_dir / "enst_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'=' * 70}")
    print("COMPLETE!")
    print(f"{'=' * 70}")
    print(f"Created {batch_id} batches in {batch_dir}")
    print(f"Manifest saved to {manifest_path}")
    print(f"\nTo add to training, include this manifest in your training config:")
    print(f"  F:/datasets/multilabel_real_v3/enst_real/enst_manifest.json")


if __name__ == "__main__":
    main()
