#!/usr/bin/env python3
"""Check where val cache samples came from vs current val dataset."""
import numpy as np

# Load val cache keys
print("Loading val cache...")
index = np.load('F:/feature_cache/val/index.npz', allow_pickle=True)
cache_keys = set()
for k in index['keys']:
    k_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
    cache_keys.add(k_str)

print(f"Val cache has {len(cache_keys):,} unique keys")
print("\nSample cache keys:")
for i, k in enumerate(list(cache_keys)[:5]):
    print(f"  {k}")

# Load current val dataset
print("\nLoading current val dataset...")
files = np.load('F:/datasets/prod_v5_definitive/val/val_labels_files.npy', allow_pickle=True)
print(f"Val dataset has {len(files):,} samples")
print("\nSample dataset files:")
for f in files[:5]:
    f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
    print(f"  {f_str}")

# Check key format compatibility
print("\n" + "="*60)
print("KEY FORMAT ANALYSIS")
print("="*60)

# Try to understand the format
cache_key_sample = list(cache_keys)[0]
dataset_file_sample = files[0].decode('utf-8') if isinstance(files[0], bytes) else str(files[0])

print(f"\nCache key format: {cache_key_sample}")
print(f"Dataset file format: {dataset_file_sample}")

# Check if it's a path separator / extension issue
# Dataset: audio/xxx.wav
# Cache might be: audio\xxx.pt or audio/xxx.pt

# Try various transformations
def try_match(dataset_file):
    f_str = dataset_file.decode('utf-8') if isinstance(dataset_file, bytes) else str(dataset_file)
    variants = [
        f_str,  # as-is
        f_str.replace('/', '\\'),  # forward to back
        f_str.replace('.wav', '.pt'),  # wav to pt
        f_str.replace('/', '\\').replace('.wav', '.pt'),  # both
        f_str.replace('.wav', '.pt').replace('/', '\\'),  # both other order
    ]
    for v in variants:
        if v in cache_keys:
            return v
    return None

print("\nTrying to match first 10 dataset files:")
matches = 0
for f in files[:10]:
    match = try_match(f)
    f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
    if match:
        print(f"  ✓ {f_str} -> {match}")
        matches += 1
    else:
        print(f"  ✗ {f_str} -> NO MATCH")

print(f"\nMatched {matches}/10")

# Check if UUIDs in cache exist in dataset at all
print("\n" + "="*60)
print("UUID OVERLAP CHECK")
print("="*60)

import re
def extract_uuid(s):
    # Match UUID pattern
    match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', s.lower())
    return match.group(1) if match else None

# Get UUIDs from cache
cache_uuids = set()
for k in list(cache_keys)[:100000]:  # Sample
    uuid = extract_uuid(k)
    if uuid:
        cache_uuids.add(uuid)

# Get UUIDs from dataset
dataset_uuids = set()
for f in files[:100000]:  # Sample
    f_str = f.decode('utf-8') if isinstance(f, bytes) else str(f)
    uuid = extract_uuid(f_str)
    if uuid:
        dataset_uuids.add(uuid)

overlap = cache_uuids & dataset_uuids
print(f"Cache UUIDs (sample): {len(cache_uuids):,}")
print(f"Dataset UUIDs (sample): {len(dataset_uuids):,}")
print(f"Overlap: {len(overlap):,} ({100*len(overlap)/len(dataset_uuids):.1f}%)")

if len(overlap) < len(dataset_uuids) * 0.5:
    print("\n⚠️  LOW OVERLAP - Cache and dataset are from DIFFERENT sources!")
