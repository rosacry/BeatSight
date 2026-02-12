#!/usr/bin/env python3
"""Restore dataset from backup."""
import shutil
from pathlib import Path

dataset = Path("F:/datasets/prod_v5_definitive")

for split in ['train', 'val']:
    backup = dataset / split / "backup_original"
    target = dataset / split
    
    if backup.exists():
        for f in backup.glob("*.npy"):
            dest = target / f.name
            shutil.copy(f, dest)
            print(f"Restored {dest}")
    else:
        print(f"No backup found for {split}")

print("\nDone - dataset restored from backup")
