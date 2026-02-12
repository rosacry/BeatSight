# BeatSight Data Location Update

**Migration Status:** ✅ Complete (January 6, 2026)  
**All codebase docs updated to reflect new paths**

The project data has been migrated across drives for optimal performance:
- **F: drive** (Samsung 990 EVO Plus 2TB SSD) - Hot data for active training
- **D: drive** (Seagate 2TB HDD) - Cold storage for archived/source datasets

## Current Data Locations

| Data Type | Location | Drive Type |
|-----------|----------|------------|
| Feature Cache | `F:\feature_cache\` | SSD (hot) |
| Training Dataset | `F:\datasets\prod_v5_fixed_20251212\` | SSD (hot) |
| Augmented Rare Classes | `F:\datasets\augmented_rare_classes\` | SSD (hot) |
| Lakh MIDI Dataset | `D:\cold_storage\datasets\lakh_midi\` | HDD (cold) |
| **STAR Drums (506 GB)** | `D:\cold_storage\datasets\star_drums\` | HDD (cold) |
| FSD50K | `D:\cold_storage\datasets\fsd50k\` | HDD (cold) |
| Manifests/Labels | `F:\manifests\dataset_index\` | SSD (hot) |
| Cold Raw Data | `D:\data\raw\` | HDD (cold) |
| Project Code | `C:\github\BeatSight\` | System drive |

## Migration History

| Date | Change |
|------|--------|
| Dec 30, 2025 | Initial migration from C: to F: (SSD) |
| Jan 1, 2026 | Moved cold datasets from F: to D: (HDD) to free SSD space |

## Directory Structure

### F: Drive (Samsung 990 EVO Plus SSD) - Hot Data
```
F:\
├── feature_cache\                    # ~512GB feature cache for training
│   └── train\                        # 233 shards + index.npz + manifest.json
├── datasets\
│   └── prod_v5_fixed_20251212\       # Active training dataset
│       ├── train\
│       ├── val\
│       ├── components.json
│       └── metadata.json
└── manifests\
    └── dataset_index\
```

### D: Drive (Seagate 2TB HDD) - Cold Storage
```
D:\
├── cold_storage\
│   └── datasets\
│       ├── star_drums\               # 506 GB (moved Jan 1, 2026)
│       ├── lakh_midi\                # 8 GB
│       ├── fsd50k\                   # 5 GB
│       ├── star_drums_extracted\     # 1 GB
│       └── augmented_rare_classes\   # 10 MB
└── data\
    └── raw\                          # Original raw audio files
```

## Notes

- **Hot data** on F: (SSD) - actively used during training
- **Cold data** on D: (HDD) - source datasets, not needed during training
- **Project code** stays at `C:\github\BeatSight\`
- The F: drive is a Samsung 990 EVO Plus 2TB NVMe (7000/6000 MB/s read/write)
- The D: drive is a Seagate 2TB HDD (external, slower but high capacity)
