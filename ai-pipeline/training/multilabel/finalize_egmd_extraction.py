#!/usr/bin/env python3
"""
Finalize the E-GMD extraction by creating a manifest from existing batch files.
Run this after extraction completed but merge failed due to memory.
"""

import json
import numpy as np
from pathlib import Path
import shutil

def main():
    output_path = Path("F:/datasets/multilabel_real_v2/egmd")
    temp_dir = output_path / "temp_batches"
    
    if not temp_dir.exists():
        print(f"Error: {temp_dir} does not exist")
        return
    
    # Count batches
    batch_files = sorted(temp_dir.glob("features_batch_*.npy"))
    batch_num = len(batch_files)
    print(f"Found {batch_num} feature batch files")
    
    # Read checkpoint for total samples
    checkpoint_file = temp_dir / "checkpoint.json"
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            checkpoint = json.load(f)
        total_samples = checkpoint.get('total_samples', 0)
        print(f"Checkpoint says: {total_samples:,} samples")
    else:
        total_samples = 0
    
    # Create manifest
    manifest = {
        'dataset': 'egmd',
        'total_samples': total_samples,
        'batch_count': batch_num,
        'sample_rate': 22050,
        'feature_shape': [128, 128],
        'num_classes': 12,
        'batches': []
    }
    
    # Scan batches
    print("Scanning batches...")
    np.random.seed(42)
    actual_total = 0
    
    for i in range(batch_num):
        label_file = temp_dir / f'labels_batch_{i}.npy'
        if not label_file.exists():
            print(f"  Warning: {label_file} missing, skipping")
            continue
            
        labels = np.load(label_file)
        n_samples = len(labels)
        actual_total += n_samples
        
        batch_info = {
            'features': f'features_batch_{i}.npy',
            'labels': f'labels_batch_{i}.npy',
            'samples': n_samples,
        }
        
        # Compute multi-label ratio for first 20 batches
        if i < 20:
            multi_count = np.sum(labels.sum(axis=1) > 1)
            batch_info['multi_label_ratio'] = float(multi_count / n_samples)
        
        manifest['batches'].append(batch_info)
        del labels
        
        if (i + 1) % 100 == 0:
            print(f"  Scanned {i+1}/{batch_num} batches, {actual_total:,} samples so far")
    
    manifest['total_samples'] = actual_total
    print(f"\nActual total: {actual_total:,} samples")
    
    # Assign train/val splits by batch (90/10)
    batch_indices = np.random.permutation(batch_num)
    n_val_batches = max(1, batch_num // 10)
    val_batch_set = set(batch_indices[:n_val_batches])
    
    for i, batch_info in enumerate(manifest['batches']):
        batch_info['split'] = 'val' if i in val_batch_set else 'train'
    
    # Compute multi-label ratio
    sampled_ratios = [b.get('multi_label_ratio', 0) for b in manifest['batches'][:20] if 'multi_label_ratio' in b]
    manifest['estimated_multi_label_ratio'] = float(np.mean(sampled_ratios)) if sampled_ratios else 0
    
    # Save manifest
    manifest_path = output_path / 'egmd_manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"\nSaved manifest: {manifest_path}")
    
    # Move batches to organized directory
    egmd_batches_dir = output_path / 'egmd_batches'
    egmd_batches_dir.mkdir(exist_ok=True)
    
    print(f"\nMoving {batch_num * 2} files to {egmd_batches_dir}...")
    moved = 0
    for i in range(batch_num):
        src_feat = temp_dir / f'features_batch_{i}.npy'
        src_label = temp_dir / f'labels_batch_{i}.npy'
        
        if src_feat.exists():
            shutil.move(str(src_feat), str(egmd_batches_dir / f'features_batch_{i}.npy'))
            moved += 1
        if src_label.exists():
            shutil.move(str(src_label), str(egmd_batches_dir / f'labels_batch_{i}.npy'))
            moved += 1
        
        if (i + 1) % 200 == 0:
            print(f"  Moved {moved} files...")
    
    print(f"  Moved {moved} files total")
    
    # Remove temp dir
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(f"Removed {temp_dir}")
    
    # Summary
    train_samples = sum(b['samples'] for i, b in enumerate(manifest['batches']) if i not in val_batch_set)
    val_samples = sum(b['samples'] for i, b in enumerate(manifest['batches']) if i in val_batch_set)
    
    print(f"\n✅ Finalization complete!")
    print(f"   Total samples: {actual_total:,}")
    print(f"   Train batches: {batch_num - n_val_batches}, Val batches: {n_val_batches}")
    print(f"   Train samples: ~{train_samples:,}, Val samples: ~{val_samples:,}")
    print(f"   Estimated multi-label: {manifest['estimated_multi_label_ratio']*100:.1f}%")
    print(f"   Batches dir: {egmd_batches_dir}")
    print(f"   Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
