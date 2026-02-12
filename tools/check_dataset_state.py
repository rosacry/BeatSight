#!/usr/bin/env python3
import numpy as np

print("CURRENT DATASET STATE:")
print("="*60)

for split in ['train', 'val']:
    print(f"\n{split.upper()}:")
    
    # Current
    try:
        labels = np.load(f'F:/datasets/prod_v5_definitive/{split}/{split}_labels_labels.npy')
        files = np.load(f'F:/datasets/prod_v5_definitive/{split}/{split}_labels_files.npy', allow_pickle=True)
        print(f"  Current: {len(labels):,} samples")
        
        class_names = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
                       'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
        for i, name in enumerate(class_names):
            count = np.sum(labels == i)
            print(f"    {name:15}: {count:>10,}")
    except Exception as e:
        print(f"  Error loading current: {e}")
    
    # Backup
    try:
        backup_labels = np.load(f'F:/datasets/prod_v5_definitive/{split}/backup_original/{split}_labels_labels.npy')
        print(f"\n  Backup:  {len(backup_labels):,} samples")
    except Exception as e:
        print(f"  No backup found: {e}")
