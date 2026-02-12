#!/usr/bin/env python3
"""
Analyze which samples are missing from the feature cache and why.
This helps diagnose data pipeline issues.
"""

import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict
import re


def load_cache_index(cache_dir: Path) -> set:
    """Load all sample IDs from the cache index."""
    # Try index.npz (main format)
    index_path = cache_dir / "index.npz"
    if index_path.exists():
        print(f"  Loading from index.npz...")
        data = np.load(index_path, allow_pickle=True)
        # Check for various key names
        if 'sample_ids' in data.files:
            return set(data['sample_ids'])
        elif 'ids' in data.files:
            return set(data['ids'])
        elif 'arr_0' in data.files:
            return set(data['arr_0'])
        else:
            print(f"  Available keys: {data.files}")
            raise KeyError("Cannot find sample IDs in index.npz")
    
    # Try consolidated_index.npy
    npy_path = cache_dir / "consolidated_index.npy"
    if npy_path.exists():
        ids = np.load(npy_path)
        return set(ids)
    
    # Try binary index
    bin_path = cache_dir / "consolidated_index.bin"
    if bin_path.exists():
        ids = np.fromfile(bin_path, dtype=np.int64)
        return set(ids)
    
    raise FileNotFoundError(f"No index found in {cache_dir}")


def load_labels(labels_dir: Path, split: str) -> tuple:
    """Load labels and files arrays."""
    labels_path = labels_dir / f"{split}_labels_files.npy"
    if labels_path.exists():
        data = np.load(labels_path, allow_pickle=True)
        labels = data['labels'] if 'labels' in data.files else data['arr_0']
        files = data['files'] if 'files' in data.files else data['arr_1']
        return labels, files
    
    # Try separate files
    labels = np.load(labels_dir / f"{split}_labels.npy")
    files = np.load(labels_dir / f"{split}_files.npy", allow_pickle=True)
    return labels, files


def extract_source_from_path(path: str) -> str:
    """Extract the data source from a file path."""
    path_lower = path.lower()
    
    # Common source patterns
    if 'lakh' in path_lower or 'midi' in path_lower:
        return 'lakh_midi'
    if 'idmt' in path_lower:
        return 'idmt'
    if 'enst' in path_lower:
        return 'enst'
    if 'e-gmd' in path_lower or 'egmd' in path_lower:
        return 'e-gmd'
    if 'mdb' in path_lower or 'medleydb' in path_lower:
        return 'medleydb'
    if 'rbma' in path_lower:
        return 'rbma'
    if 'slakh' in path_lower:
        return 'slakh'
    if 'groove' in path_lower:
        return 'groove_midi'
    if 'synthesized' in path_lower or 'synth' in path_lower:
        return 'synthesized'
    if 'augmented' in path_lower:
        return 'augmented'
    
    # Try to extract from directory structure
    parts = path.replace('\\', '/').split('/')
    for part in parts:
        if part and not part.startswith('.') and len(part) > 2:
            # Skip common non-source parts
            if part.lower() not in ['audio', 'features', 'data', 'drums', 'hits', 'samples']:
                return part[:30]  # Truncate long names
    
    return 'unknown'


def analyze_missing(dataset_dir: str, cache_dir: str, split: str = 'train'):
    """Analyze which samples are missing from cache."""
    dataset_path = Path(dataset_dir) / split
    cache_path = Path(cache_dir) / split
    
    print(f"\n{'='*70}")
    print(f"  ANALYZING MISSING SAMPLES: {split.upper()}")
    print(f"{'='*70}")
    
    # Load cache index
    print(f"\nLoading cache index from {cache_path}...")
    cached_ids = load_cache_index(cache_path)
    print(f"  Cache has {len(cached_ids):,} unique sample IDs")
    
    # Load dataset labels
    print(f"\nLoading labels from {dataset_path}...")
    labels, files = load_labels(dataset_path, split)
    print(f"  Dataset has {len(labels):,} samples")
    
    # Find missing samples
    print("\nAnalyzing missing samples...")
    missing_indices = []
    missing_by_source = defaultdict(list)
    missing_by_class = defaultdict(int)
    
    CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
                   'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
    
    for idx in range(len(labels)):
        sample_id = hash(str(files[idx])) & 0x7FFFFFFFFFFFFFFF
        if sample_id not in cached_ids:
            missing_indices.append(idx)
            
            # Track by source
            path = str(files[idx])
            source = extract_source_from_path(path)
            missing_by_source[source].append((idx, path, labels[idx]))
            
            # Track by class
            missing_by_class[labels[idx]] += 1
    
    # Report
    total = len(labels)
    missing = len(missing_indices)
    cached = total - missing
    
    print(f"\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}")
    print(f"\n  Total samples in dataset: {total:,}")
    print(f"  Samples in cache:         {cached:,} ({100*cached/total:.2f}%)")
    print(f"  Samples MISSING:          {missing:,} ({100*missing/total:.2f}%)")
    
    print(f"\n  Missing by SOURCE:")
    print(f"  {'-'*50}")
    for source, samples in sorted(missing_by_source.items(), key=lambda x: -len(x[1])):
        pct = 100 * len(samples) / missing
        print(f"    {source:30s}: {len(samples):>10,} ({pct:5.1f}%)")
    
    print(f"\n  Missing by CLASS:")
    print(f"  {'-'*50}")
    for class_idx in range(len(CLASS_NAMES)):
        count = missing_by_class.get(class_idx, 0)
        class_total = np.sum(labels == class_idx)
        pct_of_class = 100 * count / class_total if class_total > 0 else 0
        print(f"    {CLASS_NAMES[class_idx]:15s}: {count:>10,} / {class_total:>10,} ({pct_of_class:5.1f}% of class missing)")
    
    # Show example missing paths
    print(f"\n  Example MISSING file paths:")
    print(f"  {'-'*50}")
    shown_sources = set()
    for source, samples in sorted(missing_by_source.items(), key=lambda x: -len(x[1])):
        if source not in shown_sources and len(samples) > 0:
            idx, path, label = samples[0]
            print(f"    [{CLASS_NAMES[label]}] {path[:80]}...")
            shown_sources.add(source)
            if len(shown_sources) >= 10:
                break
    
    # Save missing indices for later use
    output_file = dataset_path / f"{split}_missing_indices.npy"
    np.save(output_file, np.array(missing_indices, dtype=np.int64))
    print(f"\n  Saved {missing:,} missing indices to: {output_file}")
    
    return missing_indices, missing_by_source


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze missing cache samples")
    parser.add_argument("--dataset", required=True, help="Dataset directory")
    parser.add_argument("--cache", required=True, help="Feature cache directory")
    parser.add_argument("--split", default="train", choices=["train", "val"], help="Split to analyze")
    
    args = parser.parse_args()
    analyze_missing(args.dataset, args.cache, args.split)
