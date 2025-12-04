# BeatSight Tools

This directory contains utility scripts and tools for BeatSight development and data processing.

## Directory Structure

```
tools/
├── BmFontGenerator/        # Bitmap font generation (placeholder)
├── FontStoreInspector/     # osu!framework font API inspection
├── convert_labels_to_numpy.py
├── convert_labels_to_pickle.py
└── generate_cache_index_mapping.py
```

## Data Processing Tools

### convert_labels_to_numpy.py

Converts large label JSON files to memory-efficient numpy format, reducing memory usage by ~10x.

```bash
# Basic usage
python tools/convert_labels_to_numpy.py data/dataset_index/train_labels.json

# For velocity-enriched labels
python tools/convert_labels_to_numpy.py data/dataset_index/train_labels_with_velocity.json
```

**Output:** `.npy` file with same name (e.g., `train_labels.npy`)

**Dependencies:** `numpy`, `ijson` (optional, for streaming large files)

---

### convert_labels_to_pickle.py

Converts large JSON label files to sharded pickle format for datasets with 14M+ samples.
Creates multiple shards (~1M items each) to keep memory under 2GB per shard.

```bash
python tools/convert_labels_to_pickle.py data/dataset_index/train_labels.json
python tools/convert_labels_to_pickle.py data/dataset_index/val_labels.json
```

**Output:** Directory of pickle shards (e.g., `train_labels_shards/`)

---

### generate_cache_index_mapping.py

Creates O(1) direct index mapping for consolidated feature cache, eliminating binary search overhead during training.

**Performance impact:**
- Without mapping: ~1-5 iterations/second (binary search over 14M entries)
- With mapping: ~30-60 iterations/second (direct array lookup)

```bash
# Generate mapping for training data
python tools/generate_cache_index_mapping.py \
    --labels data/dataset_index/train_labels_with_velocity_files.npy \
    --cache data/feature_cache/prod_combined_warmup_consolidated/train \
    --output data/dataset_index/train_cache_mapping.npz

# Generate mapping for validation data
python tools/generate_cache_index_mapping.py \
    --labels data/dataset_index/val_labels_with_velocity_files.npy \
    --cache data/feature_cache/prod_combined_warmup_consolidated/val \
    --output data/dataset_index/val_cache_mapping.npz
```

**Output:** `.npz` file containing:
- `shard_ids`: uint16 array of shard IDs
- `offsets`: uint32 array of offsets within shards
- `valid`: bool array indicating if sample was found

---

## .NET Tools

### FontStoreInspector/

Diagnostic utility for inspecting osu!framework's `FontStore.AddFont` method overloads.
See [FontStoreInspector/README.md](FontStoreInspector/README.md) for details.

```bash
cd tools/FontStoreInspector
dotnet run
```

### BmFontGenerator/

Placeholder for bitmap font generation tool. Not yet implemented.
See [BmFontGenerator/README.md](BmFontGenerator/README.md) for planned features.

---

## Requirements

- **Python tools:** Python 3.10+, numpy
- **.NET tools:** .NET 8.0 SDK

## Contributing

When adding new tools:
1. Include a docstring at the top with usage examples
2. Update this README with a description
3. Add appropriate error handling and help text
