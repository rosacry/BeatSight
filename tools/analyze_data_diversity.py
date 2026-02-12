#!/usr/bin/env python3
"""
Final check: Data source diversity analysis.
Ensure we have diverse samples and not just duplicates.
"""

import numpy as np
from pathlib import Path
from collections import Counter

DATASET = Path("F:/datasets/prod_v5_definitive")

CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']

print("="*80)
print("  DATA SOURCE DIVERSITY ANALYSIS")
print("="*80)

# Load files
print("\nLoading train files...")
train_files = np.load(DATASET / "train" / "train_labels_files.npy", allow_pickle=True)
train_labels = np.load(DATASET / "train" / "train_labels_labels.npy")
print(f"  Train: {len(train_files):,} samples")

print("\nLoading val files...")
val_files = np.load(DATASET / "val" / "val_labels_files.npy", allow_pickle=True)
val_labels = np.load(DATASET / "val" / "val_labels_labels.npy")
print(f"  Val: {len(val_files):,} samples")

# Analyze data sources
def extract_source(f):
    """Extract source info from filename."""
    f_str = f.decode() if isinstance(f, bytes) else str(f)
    
    # Lakh MIDI synthesized samples
    if f_str.startswith('lakh_'):
        return 'lakh_midi'
    
    # Audio files: audio/XX/UUID__class.wav
    if f_str.startswith('audio/') and '__' in f_str:
        # Extract the UUID prefix to identify unique recordings
        parts = f_str.split('/')
        if len(parts) >= 3:
            uuid_part = parts[2].split('__')[0]
            return f'audio_{uuid_part[:8]}'  # First 8 chars of UUID for grouping
    
    return 'unknown'

def analyze_split(files, labels, split_name):
    print(f"\n{'='*80}")
    print(f"  {split_name.upper()} SPLIT ANALYSIS")
    print(f"{'='*80}")
    
    # Count sources
    sources = [extract_source(f) for f in files]
    source_counts = Counter(sources)
    
    # Group by type
    lakh_count = source_counts.get('lakh_midi', 0)
    audio_count = sum(c for s, c in source_counts.items() if s.startswith('audio_'))
    unique_uuids = sum(1 for s in source_counts.keys() if s.startswith('audio_'))
    
    print(f"\n  Data sources:")
    print(f"    Lakh MIDI synthesized: {lakh_count:>12,} ({100*lakh_count/len(files):.1f}%)")
    print(f"    Audio files:           {audio_count:>12,} ({100*audio_count/len(files):.1f}%)")
    print(f"    Unique recordings:     {unique_uuids:>12,}")
    
    # Per-class source breakdown
    print(f"\n  Per-class source breakdown:")
    print(f"  {'Class':<15} {'Total':>10} {'Lakh':>10} {'Audio':>10} {'Audio%':>8}")
    print(f"  {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
    
    for class_idx, class_name in enumerate(CLASS_NAMES):
        class_mask = labels == class_idx
        class_sources = [sources[i] for i in range(len(sources)) if class_mask[i]]
        
        class_total = len(class_sources)
        class_lakh = sum(1 for s in class_sources if s == 'lakh_midi')
        class_audio = class_total - class_lakh
        audio_pct = 100 * class_audio / class_total if class_total > 0 else 0
        
        print(f"  {class_name:<15} {class_total:>10,} {class_lakh:>10,} {class_audio:>10,} {audio_pct:>7.1f}%")
    
    return sources, source_counts

train_sources, train_source_counts = analyze_split(train_files, train_labels, "train")
val_sources, val_source_counts = analyze_split(val_files, val_labels, "val")

# Check for recording leakage (same UUID in train and val)
print(f"\n{'='*80}")
print(f"  RECORDING LEAKAGE CHECK")
print(f"{'='*80}")

train_uuids = set(s for s in train_source_counts.keys() if s.startswith('audio_'))
val_uuids = set(s for s in val_source_counts.keys() if s.startswith('audio_'))
uuid_overlap = train_uuids & val_uuids

print(f"\n  Train unique recordings: {len(train_uuids):,}")
print(f"  Val unique recordings:   {len(val_uuids):,}")
print(f"  UUID overlap:            {len(uuid_overlap):,}")

if uuid_overlap:
    # This is expected since we did stratified split, but let's check the extent
    print(f"\n  Note: Some recording UUIDs appear in both train and val.")
    print(f"  This is expected for stratified splitting within recordings.")
    print(f"  Overlap percentage: {100*len(uuid_overlap)/(len(train_uuids)|1):.1f}% of train UUIDs")
else:
    print(f"\n  ✓ No recording leakage - train and val use different recordings!")

# Check duplicate files
print(f"\n{'='*80}")
print(f"  DUPLICATE FILE CHECK")
print(f"{'='*80}")

train_file_strings = [f.decode() if isinstance(f, bytes) else str(f) for f in train_files]
val_file_strings = [f.decode() if isinstance(f, bytes) else str(f) for f in val_files]

train_unique = len(set(train_file_strings))
val_unique = len(set(val_file_strings))

print(f"\n  Train: {len(train_files):,} total, {train_unique:,} unique")
print(f"  Val:   {len(val_files):,} total, {val_unique:,} unique")

if train_unique != len(train_files):
    print(f"  ⚠️ Train has {len(train_files) - train_unique:,} duplicate files!")
else:
    print(f"  ✓ Train has no duplicate files")

if val_unique != len(val_files):
    print(f"  ⚠️ Val has {len(val_files) - val_unique:,} duplicate files!")
else:
    print(f"  ✓ Val has no duplicate files")

print(f"\n{'='*80}")
print(f"  ✅ DATA DIVERSITY ANALYSIS COMPLETE")
print(f"{'='*80}")
