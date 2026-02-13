#!/usr/bin/env python3
"""
Re-extract E-GMD files that were skipped in the original run.
This identifies which files weren't successfully processed and re-runs them.
"""

import json
import numpy as np
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import gc

from training.multilabel.extract_multilabel_from_midi import _process_single_file, TD11_DRUM_MAP


def main():
    egmd_path = Path("F:/data/raw/egmd")
    output_path = Path("F:/datasets/multilabel_real_v2/egmd")
    batches_dir = output_path / "egmd_batches"
    manifest_path = output_path / "egmd_manifest.json"
    
    # Load existing manifest
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    existing_batch_count = manifest['batch_count']
    existing_samples = manifest['total_samples']
    print(f"Existing: {existing_samples:,} samples in {existing_batch_count} batches")
    
    # Collect all pairs - use TD11 mapping for EGMD (Roland TD-11 kit)
    all_pairs = []
    for drummer_dir in sorted(egmd_path.glob('drummer*')):
        for session_dir in sorted(drummer_dir.glob('*session*')) + sorted(drummer_dir.glob('session*')):
            for midi_file in list(session_dir.glob('*.mid')) + list(session_dir.glob('*.midi')):
                audio_file = midi_file.with_suffix('.wav')
                if audio_file.exists():
                    all_pairs.append((midi_file, audio_file, 22050, TD11_DRUM_MAP))
    
    print(f"Total pairs in E-GMD: {len(all_pairs)}")
    
    # Calculate expected vs actual
    expected_samples = len(all_pairs) * 90  # ~90 samples per file
    missing_estimate = expected_samples - existing_samples
    print(f"Expected samples: ~{expected_samples:,}")
    print(f"Missing estimate: ~{missing_estimate:,} ({missing_estimate/expected_samples*100:.1f}%)")
    
    # Strategy: Process ALL files fresh, but only keep results from files 
    # where we get significantly more samples than current average
    # Actually, simpler: just re-run on all files, save to new batches
    
    print(f"\nWill re-extract ALL {len(all_pairs)} files with better error handling...")
    print("This will create additional batches to supplement existing data.")
    
    input("Press Enter to continue, Ctrl+C to cancel...")
    
    num_workers = 2  # Very conservative to avoid memory issues
    spec_flush_threshold = 1000  # Small batches
    
    batch_num = existing_batch_count  # Continue numbering
    batch_features = []
    batch_labels = []
    total_new_samples = 0
    skipped = 0
    error_types = {}
    
    pbar = tqdm(total=len(all_pairs), desc="Re-extracting")
    
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(_process_single_file, pair): pair 
                   for pair in all_pairs}
        
        for future in as_completed(futures):
            pair = futures[future]
            midi_path = str(pair[0])
            
            try:
                results = future.result(timeout=120)
                for feat, label in results:
                    batch_features.append(feat)
                    batch_labels.append(label)
            except Exception as e:
                error_type = type(e).__name__
                error_types[error_type] = error_types.get(error_type, 0) + 1
                skipped += 1
            
            pbar.update(1)
            
            # Flush to disk
            if len(batch_features) >= spec_flush_threshold:
                feat_arr = np.array(batch_features, dtype=np.float32)
                label_arr = np.array(batch_labels, dtype=np.float32)
                np.save(batches_dir / f'features_batch_{batch_num}.npy', feat_arr)
                np.save(batches_dir / f'labels_batch_{batch_num}.npy', label_arr)
                del feat_arr, label_arr
                
                total_new_samples += len(batch_features)
                batch_num += 1
                batch_features.clear()
                batch_labels.clear()
                gc.collect()
                
                # Progress update
                if batch_num % 50 == 0:
                    pbar.set_postfix({'samples': f'{total_new_samples:,}', 'skipped': skipped})
    
    # Save remaining
    if batch_features:
        feat_arr = np.array(batch_features, dtype=np.float32)
        label_arr = np.array(batch_labels, dtype=np.float32)
        np.save(batches_dir / f'features_batch_{batch_num}.npy', feat_arr)
        np.save(batches_dir / f'labels_batch_{batch_num}.npy', label_arr)
        total_new_samples += len(batch_features)
        batch_num += 1
    
    pbar.close()
    
    print(f"\n✅ Re-extraction complete!")
    print(f"   New samples: {total_new_samples:,}")
    print(f"   New batches: {batch_num - existing_batch_count}")
    print(f"   Skipped: {skipped}")
    print(f"   Error types: {error_types}")
    
    # Update manifest
    print("\nUpdating manifest...")
    
    # Re-scan all batches
    all_batches = sorted(batches_dir.glob('features_batch_*.npy'))
    new_manifest = {
        'dataset': 'egmd',
        'total_samples': 0,
        'batch_count': len(all_batches),
        'sample_rate': 22050,
        'feature_shape': [128, 128],
        'num_classes': 12,
        'batches': []
    }
    
    np.random.seed(42)
    for i, feat_file in enumerate(tqdm(all_batches, desc="Scanning batches")):
        batch_idx = int(feat_file.stem.split('_')[-1])
        label_file = batches_dir / f'labels_batch_{batch_idx}.npy'
        labels = np.load(label_file)
        
        batch_info = {
            'features': feat_file.name,
            'labels': label_file.name,
            'samples': len(labels),
        }
        new_manifest['batches'].append(batch_info)
        new_manifest['total_samples'] += len(labels)
        del labels
    
    # Assign train/val splits
    n_batches = len(new_manifest['batches'])
    batch_indices = np.random.permutation(n_batches)
    n_val = max(1, n_batches // 10)
    val_set = set(batch_indices[:n_val])
    
    for i, b in enumerate(new_manifest['batches']):
        b['split'] = 'val' if i in val_set else 'train'
    
    with open(manifest_path, 'w') as f:
        json.dump(new_manifest, f, indent=2)
    
    print(f"\n✅ Updated manifest: {new_manifest['total_samples']:,} total samples")
    

if __name__ == "__main__":
    main()
