#!/usr/bin/env python3
"""Check what china/splash samples look like in the original dataset."""
import numpy as np

files = np.load('F:/datasets/prod_v5_definitive/train/backup_original/train_labels_files.npy', allow_pickle=True)
labels = np.load('F:/datasets/prod_v5_definitive/train/backup_original/train_labels_labels.npy')

# china = 0, splash = 10
for class_idx, class_name in [(0, 'china'), (10, 'splash')]:
    mask = labels == class_idx
    class_files = files[mask]
    print(f"\n{class_name.upper()} samples ({len(class_files):,} total):")
    for f in class_files[:10]:
        print(f"  {f}")
