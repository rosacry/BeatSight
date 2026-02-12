#!/usr/bin/env python3
"""
Create batched datasets from ALL acoustic drum sources for multi-label training.

This script processes:
- ENST Drums (already done - will skip if exists)
- IDMT-SMT-Drums
- MedleyDB
- Cambridge Multitrack
- Telefunken
- SignatureSounds
- MUSDB-HQ

Each source is processed into batched .npy files compatible with multilabel_real_v3.

Usage:
    python scripts/create_full_acoustic_dataset.py --analyze-only
    python scripts/create_full_acoustic_dataset.py --process-all
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import after path setup
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("WARNING: librosa not installed, cannot process audio")

from tqdm import tqdm

# ============================================================================
# Configuration
# ============================================================================

MANIFESTS_DIR = Path("training/data/manifests")
OUTPUT_BASE = Path("F:/datasets/multilabel_real_v3")

# Audio root directories for each source
AUDIO_ROOTS = {
    "enst_drums": Path("D:/data/raw/ENST-Drums"),
    "idmt_smt_drums_v2": Path("D:/data/raw/idmt_smt_drums_v2"),
    "medleydb": Path("D:/data/raw/MedleyDB"),
    "cambridge_multitrack": Path("D:/data/raw"),  # Manifest paths include 'cambridge/' prefix
    "telefunken": Path("D:/data/raw/Telefunken"),
    "signaturesounds": Path("D:/data/raw/SignatureSounds"),
}

# Manifest files for each source  
MANIFEST_FILES = {
    "enst_drums": "enst_drums_events.jsonl",
    "idmt_smt_drums_v2": "idmt_smt_drums_v2_events.jsonl",
    "medleydb": "medleydb_events.jsonl",
    "cambridge_multitrack": "cambridge_multitrack_events.jsonl",
    "telefunken": "telefunken_sessions_events.jsonl",
    "signaturesounds": "signaturesounds_events.jsonl",
}

# Standard class mapping (must match training pipeline)
DEFAULT_DRUM_COMPONENTS = [
    'china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open',
    'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom'
]

# Label normalization (map variations to standard labels)
LABEL_MAP = {
    # Toms
    'tom_high': 'tom', 'tom_mid': 'tom', 'tom_low': 'tom',
    'tom_floor': 'tom', 'tom1': 'tom', 'tom2': 'tom', 'tom3': 'tom',
    # Snare variations
    'snare_center': 'snare', 'snare_edge': 'snare', 'snare_rimshot': 'snare',
    'snare_cross_stick': 'cross_stick', 'rimshot': 'snare',
    # Hi-hat variations
    'hihat_foot_splash': 'hihat_pedal', 'hihat_splash': 'hihat_open',
    'hihat_foot': 'hihat_pedal', 'hihat_half_open': 'hihat_open',
    # Ride variations
    'ride': 'ride_bow', 'ride_edge': 'ride_bow', 'ride_crash': 'crash',
    # Crash variations
    'crash1': 'crash', 'crash2': 'crash',
}

# Feature extraction parameters (must match training pipeline!)
SAMPLE_RATE = 22050
N_MELS = 128
N_FFT = 2048
FMAX = 8000
TARGET_FRAMES = 128

BATCH_SIZE = 2500  # Samples per batch file


def normalize_label(label: str) -> Optional[str]:
    """Normalize label to standard 12-class vocabulary."""
    label = label.lower().strip()
    
    # Direct match
    if label in DEFAULT_DRUM_COMPONENTS:
        return label
    
    # Mapped match
    if label in LABEL_MAP:
        return LABEL_MAP[label]
    
    # Unknown
    return None


def extract_mel_spectrogram(
    audio_path: Path,
    onset_time: float,
    duration: float = 0.3,
) -> Optional[np.ndarray]:
    """Extract mel spectrogram for a single event."""
    if not HAS_LIBROSA:
        return None
    
    try:
        # Calculate start time with some pre-onset context
        pre_context = 0.02  # 20ms before onset
        start_time = max(0, onset_time - pre_context)
        
        # Load audio segment
        y, sr = librosa.load(
            audio_path,
            sr=SAMPLE_RATE,
            offset=start_time,
            duration=duration + pre_context,
        )
        
        if len(y) < 512:  # Too short
            return None
        
        # Calculate hop length for target frames
        hop_length = max(1, len(y) // TARGET_FRAMES)
        
        # Extract mel spectrogram
        mel = librosa.feature.melspectrogram(
            y=y,
            sr=SAMPLE_RATE,
            n_mels=N_MELS,
            n_fft=N_FFT,
            hop_length=hop_length,
            fmax=FMAX,
        )
        
        # Convert to dB
        mel_db = librosa.power_to_db(mel, ref=np.max)
        
        # Normalize to 0-1
        mel_norm = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
        
        # Pad or truncate to target frames
        if mel_norm.shape[1] < TARGET_FRAMES:
            pad_width = TARGET_FRAMES - mel_norm.shape[1]
            mel_norm = np.pad(mel_norm, ((0, 0), (0, pad_width)), mode='constant')
        else:
            mel_norm = mel_norm[:, :TARGET_FRAMES]
        
        return mel_norm.astype(np.float32)
        
    except Exception as e:
        return None


def analyze_manifests():
    """Analyze all available manifests and report statistics."""
    print("=" * 70)
    print("ANALYZING ALL ACOUSTIC DRUM MANIFESTS")
    print("=" * 70)
    print()
    
    results = {}
    
    for source_name, manifest_file in MANIFEST_FILES.items():
        manifest_path = MANIFESTS_DIR / manifest_file
        
        if not manifest_path.exists():
            print(f"❌ {source_name}: Manifest not found at {manifest_path}")
            continue
        
        # Count events and analyze labels
        event_count = 0
        label_counts = Counter()
        has_onset_time = 0
        sample_audio_paths = []
        
        with open(manifest_path) as f:
            for line in f:
                event_count += 1
                try:
                    data = json.loads(line)
                    
                    # Check onset time
                    if data.get('onset_time') is not None:
                        has_onset_time += 1
                    
                    # Count labels
                    for comp in data.get('components', []):
                        label = comp.get('label', '')
                        normalized = normalize_label(label)
                        if normalized:
                            label_counts[normalized] += 1
                    
                    # Sample some audio paths
                    if len(sample_audio_paths) < 3:
                        sample_audio_paths.append(data.get('audio_path', ''))
                        
                except json.JSONDecodeError:
                    pass
        
        # Check if audio root exists
        audio_root = AUDIO_ROOTS.get(source_name)
        audio_exists = audio_root and audio_root.exists()
        
        # Check if already processed
        output_dir = OUTPUT_BASE / source_name
        already_processed = (output_dir / f"{source_name}_manifest.json").exists()
        
        results[source_name] = {
            'events': event_count,
            'with_onset': has_onset_time,
            'labels': dict(label_counts.most_common()),
            'audio_root': str(audio_root) if audio_root else 'NOT CONFIGURED',
            'audio_exists': audio_exists,
            'already_processed': already_processed,
        }
        
        # Print summary
        status = "✓ READY" if audio_exists else "❌ AUDIO NOT FOUND"
        if already_processed:
            status = "⏭ ALREADY PROCESSED"
        
        print(f"{source_name}:")
        print(f"  Events: {event_count:,}")
        print(f"  With onset time: {has_onset_time:,} ({100*has_onset_time/max(1,event_count):.1f}%)")
        print(f"  Audio root: {audio_root}")
        print(f"  Status: {status}")
        print(f"  Top labels: {dict(list(label_counts.most_common(5)))}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    ready = [k for k, v in results.items() if v['audio_exists'] and not v['already_processed']]
    processed = [k for k, v in results.items() if v['already_processed']]
    missing = [k for k, v in results.items() if not v['audio_exists']]
    
    print(f"Ready to process: {len(ready)} sources")
    for s in ready:
        print(f"  - {s}: {results[s]['events']:,} events")
    
    print(f"\nAlready processed: {len(processed)} sources")
    for s in processed:
        print(f"  - {s}")
    
    print(f"\nMissing audio: {len(missing)} sources")
    for s in missing:
        print(f"  - {s}: need {results[s]['audio_root']}")
    
    return results


def process_source(
    source_name: str,
    audio_root: Path,
    manifest_path: Path,
    output_dir: Path,
    max_samples: Optional[int] = None,
    train_ratio: float = 0.8,
):
    """Process a single source into batched .npy files."""
    print(f"\n{'='*70}")
    print(f"PROCESSING: {source_name}")
    print(f"{'='*70}")
    print(f"Audio root: {audio_root}")
    print(f"Manifest: {manifest_path}")
    print(f"Output: {output_dir}")
    print()
    
    # Load manifest
    events = []
    with open(manifest_path) as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    print(f"Loaded {len(events):,} events")
    
    if max_samples and len(events) > max_samples:
        import random
        random.seed(42)
        events = random.sample(events, max_samples)
        print(f"Limited to {len(events):,} samples")
    
    # Process events
    features_list = []
    labels_list = []
    skipped = 0
    
    for event in tqdm(events, desc="Extracting features"):
        # Get audio path
        audio_path_rel = event.get('audio_path', '')
        if not audio_path_rel:
            skipped += 1
            continue
        
        # Handle path separators
        audio_path_rel = audio_path_rel.replace('\\', '/')
        audio_path = audio_root / audio_path_rel
        
        if not audio_path.exists():
            # Try alternative paths
            alternatives = [
                audio_root / audio_path_rel.lstrip('/'),
                audio_root / Path(audio_path_rel).name,
            ]
            found = False
            for alt in alternatives:
                if alt.exists():
                    audio_path = alt
                    found = True
                    break
            if not found:
                skipped += 1
                continue
        
        # Get onset time
        onset_time = event.get('onset_time', 0.0)
        if onset_time is None:
            onset_time = 0.0
        
        # Extract features
        mel = extract_mel_spectrogram(audio_path, onset_time)
        if mel is None:
            skipped += 1
            continue
        
        # Create multi-hot label
        label_vec = np.zeros(len(DEFAULT_DRUM_COMPONENTS), dtype=np.float32)
        for comp in event.get('components', []):
            raw_label = comp.get('label', '')
            normalized = normalize_label(raw_label)
            if normalized and normalized in DEFAULT_DRUM_COMPONENTS:
                idx = DEFAULT_DRUM_COMPONENTS.index(normalized)
                label_vec[idx] = 1.0
        
        if label_vec.sum() == 0:
            skipped += 1
            continue
        
        features_list.append(mel)
        labels_list.append(label_vec)
    
    print(f"\nProcessed: {len(features_list):,} samples")
    print(f"Skipped: {skipped:,}")
    
    if len(features_list) == 0:
        print("ERROR: No samples extracted!")
        return None
    
    # Convert to arrays
    features = np.array(features_list)
    labels = np.array(labels_list)
    
    # Print label distribution
    print("\nLabel distribution:")
    for i, name in enumerate(DEFAULT_DRUM_COMPONENTS):
        count = int(labels[:, i].sum())
        pct = 100 * count / len(labels)
        print(f"  {name:<15}: {count:>6} ({pct:>5.1f}%)")
    
    # Shuffle and split
    np.random.seed(42)
    indices = np.random.permutation(len(features))
    features = features[indices]
    labels = labels[indices]
    
    split_idx = int(len(features) * train_ratio)
    train_features, val_features = features[:split_idx], features[split_idx:]
    train_labels, val_labels = labels[:split_idx], labels[split_idx:]
    
    print(f"\nTrain: {len(train_features):,} samples")
    print(f"Val: {len(val_features):,} samples")
    
    # Create output directory
    batch_dir = output_dir / f"{source_name}_batches"
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    # Save batches
    manifest_batches = []
    
    def save_batches(feats, labs, split_name):
        batches = []
        for i in range(0, len(feats), BATCH_SIZE):
            batch_features = feats[i:i+BATCH_SIZE]
            batch_labels = labs[i:i+BATCH_SIZE]
            
            batch_idx = len(manifest_batches) + len(batches)
            feat_file = f"features_batch_{batch_idx}.npy"
            label_file = f"labels_batch_{batch_idx}.npy"
            
            np.save(batch_dir / feat_file, batch_features)
            np.save(batch_dir / label_file, batch_labels)
            
            # Calculate multi-label ratio
            multi_label = (batch_labels.sum(axis=1) > 1).mean()
            
            batches.append({
                'features': feat_file,
                'labels': label_file,
                'samples': len(batch_features),
                'multi_label_ratio': float(multi_label),
                'split': split_name,
            })
        return batches
    
    print("\nSaving train batches...")
    manifest_batches.extend(save_batches(train_features, train_labels, 'train'))
    
    print("Saving val batches...")
    manifest_batches.extend(save_batches(val_features, val_labels, 'val'))
    
    # Create manifest
    manifest = {
        'dataset': source_name,
        'total_samples': len(features),
        'train_samples': len(train_features),
        'val_samples': len(val_features),
        'batch_count': len(manifest_batches),
        'sample_rate': SAMPLE_RATE,
        'feature_shape': [N_MELS, TARGET_FRAMES],
        'num_classes': len(DEFAULT_DRUM_COMPONENTS),
        'class_names': DEFAULT_DRUM_COMPONENTS,
        'batches': manifest_batches,
    }
    
    manifest_path = output_dir / f"{source_name}_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✓ Saved {len(manifest_batches)} batches to {batch_dir}")
    print(f"✓ Manifest: {manifest_path}")
    
    return manifest


def process_all_sources(skip_existing: bool = True):
    """Process all available sources."""
    print("=" * 70)
    print("PROCESSING ALL ACOUSTIC SOURCES")
    print("=" * 70)
    print()
    
    processed = []
    skipped = []
    failed = []
    
    for source_name, manifest_file in MANIFEST_FILES.items():
        manifest_path = MANIFESTS_DIR / manifest_file
        audio_root = AUDIO_ROOTS.get(source_name)
        output_dir = OUTPUT_BASE / source_name
        
        # Check if already exists
        if skip_existing and (output_dir / f"{source_name}_manifest.json").exists():
            print(f"⏭ Skipping {source_name} (already processed)")
            skipped.append(source_name)
            continue
        
        # Check prerequisites
        if not manifest_path.exists():
            print(f"❌ Skipping {source_name} (manifest not found)")
            failed.append((source_name, "manifest not found"))
            continue
        
        if not audio_root or not audio_root.exists():
            print(f"❌ Skipping {source_name} (audio root not found: {audio_root})")
            failed.append((source_name, f"audio not found at {audio_root}"))
            continue
        
        # Process
        try:
            result = process_source(
                source_name=source_name,
                audio_root=audio_root,
                manifest_path=manifest_path,
                output_dir=output_dir,
            )
            if result:
                processed.append(source_name)
            else:
                failed.append((source_name, "no samples extracted"))
        except Exception as e:
            print(f"ERROR processing {source_name}: {e}")
            failed.append((source_name, str(e)))
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Processed: {len(processed)}")
    for s in processed:
        print(f"  ✓ {s}")
    print(f"Skipped (already done): {len(skipped)}")
    for s in skipped:
        print(f"  ⏭ {s}")
    print(f"Failed: {len(failed)}")
    for s, reason in failed:
        print(f"  ❌ {s}: {reason}")
    
    # List all manifests now available
    print("\n" + "=" * 70)
    print("AVAILABLE MANIFESTS FOR TRAINING")
    print("=" * 70)
    for manifest in OUTPUT_BASE.glob("*/*_manifest.json"):
        print(f"  {manifest}")


def main():
    parser = argparse.ArgumentParser(description="Create full acoustic dataset")
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze manifests, don't process",
    )
    parser.add_argument(
        "--process-all",
        action="store_true",
        help="Process all available sources",
    )
    parser.add_argument(
        "--source",
        type=str,
        help="Process a specific source only",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if already exists",
    )
    args = parser.parse_args()
    
    if args.analyze_only:
        analyze_manifests()
    elif args.process_all:
        process_all_sources(skip_existing=not args.force)
    elif args.source:
        source_name = args.source
        manifest_path = MANIFESTS_DIR / MANIFEST_FILES.get(source_name, f"{source_name}_events.jsonl")
        audio_root = AUDIO_ROOTS.get(source_name)
        output_dir = OUTPUT_BASE / source_name
        
        if not audio_root:
            print(f"ERROR: No audio root configured for {source_name}")
            print(f"Add it to AUDIO_ROOTS in this script")
            sys.exit(1)
        
        process_source(
            source_name=source_name,
            audio_root=audio_root,
            manifest_path=manifest_path,
            output_dir=output_dir,
        )
    else:
        print("Usage:")
        print("  python scripts/create_full_acoustic_dataset.py --analyze-only")
        print("  python scripts/create_full_acoustic_dataset.py --process-all")
        print("  python scripts/create_full_acoustic_dataset.py --source enst_drums")


if __name__ == "__main__":
    main()
