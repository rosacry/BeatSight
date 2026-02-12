#!/usr/bin/env python3
"""Add lakh synthesis entries to cache index with CORRECT local shard offsets."""

import json
import numpy as np
from pathlib import Path

CACHE_DIR = Path("F:/feature_cache/train")
LABELS_DIR = Path("F:/datasets/prod_v5_fixed_20251212/train")

# Load current index
print("Loading current index...")
with open(CACHE_DIR / "index.json", "r", encoding="utf-8") as f:
    index = json.load(f)
print(f"Current entries: {len(index):,}")

# Check if lakh entries already exist
lakh_keys = [k for k in index.keys() if k.startswith("lakh_")]
print(f"Existing lakh entries: {len(lakh_keys):,}")

# Load labels to get file IDs
print("Loading labels...")
files = np.load(LABELS_DIR / "train_labels_files.npy", allow_pickle=True)

# Find all lakh entries
lakh_files = [(i, f) for i, f in enumerate(files) if isinstance(f, str) and f.startswith("lakh_")]
print(f"Found {len(lakh_files):,} lakh entries in labels")

# Separate china and splash
china = [(i, f) for i, f in lakh_files if "china" in f]
splash = [(i, f) for i, f in lakh_files if "splash" in f]
print(f"  China: {len(china):,}, Splash: {len(splash):,}")

# Remove existing lakh entries (they have wrong offsets)
for k in lakh_keys:
    del index[k]
print(f"Removed {len(lakh_keys):,} existing lakh entries")

# Add entries with CORRECT local offsets
# Shard 231: first 65536 samples (offset 0-65535)
# Shard 232: remaining samples (offset 0 to N-65536-1)
SHARD_231_SIZE = 65536

added = 0
for i, (label_idx, file_id) in enumerate(lakh_files):
    # Determine shard and LOCAL offset
    if i < SHARD_231_SIZE:
        shard_id = 231
        local_offset = i
    else:
        shard_id = 232
        local_offset = i - SHARD_231_SIZE
    
    # Key format: filename.pt (matching how labels reference them)
    key = f"{file_id}.pt"
    index[key] = {
        "shard_id": shard_id,
        "offset": local_offset
    }
    added += 1

print(f"Added {added:,} lakh entries with correct local offsets")

# Verify - handle both list [shard, offset] and dict {"shard_id": x, "offset": y} formats
def get_shard_offset(v):
    if isinstance(v, dict):
        return v.get("shard_id"), v.get("offset")
    elif isinstance(v, list) and len(v) >= 2:
        return v[0], v[1]
    return None, None

s231 = [get_shard_offset(v)[1] for v in index.values() if get_shard_offset(v)[0] == 231]
s232 = [get_shard_offset(v)[1] for v in index.values() if get_shard_offset(v)[0] == 232]
print(f"Shard 231: {len(s231):,} entries, offsets {min(s231)}-{max(s231)}")
print(f"Shard 232: {len(s232):,} entries, offsets {min(s232)}-{max(s232)}")

# Save
print("Saving index...")
with open(CACHE_DIR / "index.json", "w", encoding="utf-8") as f:
    json.dump(index, f)
print(f"Saved {len(index):,} entries")

# Regenerate binary index
print("\nRegenerating binary index...")
import subprocess
subprocess.run([
    "python", "tools/convert_cache_index_to_binary.py",
    "--cache-dir", str(CACHE_DIR),
    "--force"
], check=True)

print("\nDone!")
