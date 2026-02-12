#!/usr/bin/env python3
"""Verify multi-label extraction completeness."""
import json
from pathlib import Path

def verify_extraction(output_dir: str = "F:/datasets/multilabel_real_v3"):
    output_dir = Path(output_dir)
    
    print("=" * 60)
    print("EXTRACTION VERIFICATION")
    print("=" * 60)
    
    total_samples = 0
    total_train = 0
    total_val = 0
    total_batches = 0
    
    for dataset in ['egmd', 'groove_midi', 'slakh']:
        dataset_dir = output_dir / dataset
        manifest_patterns = [
            f'{dataset}_manifest.json',
            'egmd_manifest.json',
            'groove_manifest.json', 
            'slakh_manifest.json',
            'manifest.json'
        ]
        
        manifest_file = None
        for pattern in manifest_patterns:
            f = dataset_dir / pattern
            if f.exists():
                manifest_file = f
                break
        
        print(f"\n[{dataset.upper()}]:")
        
        if manifest_file and manifest_file.exists():
            with open(manifest_file) as f:
                m = json.load(f)
            samples = m.get('total_samples', 0)
            batches = m.get('batch_count', 0)
            
            # Calculate train/val
            train = m.get('train_samples', 0)
            val = m.get('val_samples', 0)
            if train == 0 and 'batches' in m:
                batch_data = m['batches']
                items = batch_data.values() if isinstance(batch_data, dict) else batch_data
                for b in items:
                    if isinstance(b, dict):
                        if b.get('split') == 'train':
                            train += b.get('samples', 0)
                        else:
                            val += b.get('samples', 0)
            
            # Verify batch files exist
            batch_dirs_to_check = [
                dataset_dir / f'{dataset}_batches',
                dataset_dir / 'egmd_batches',
                dataset_dir / 'groove_batches',
                dataset_dir / 'slakh_batches',
            ]
            
            batch_dir = None
            for bd in batch_dirs_to_check:
                if bd.exists():
                    batch_dir = bd
                    break
            
            actual_batches = len(list(batch_dir.glob('features_batch_*.npy'))) if batch_dir else 0
            
            print(f"   Manifest: {manifest_file.name}")
            print(f"   Total samples: {samples:,}")
            print(f"   Train: {train:,}, Val: {val:,}")
            print(f"   Batches in manifest: {batches}")
            print(f"   Actual batch files: {actual_batches}")
            
            if batches != actual_batches:
                print(f"   WARNING: manifest says {batches}, found {actual_batches}")
            else:
                print(f"   OK: Batch count verified")
            
            total_samples += samples
            total_train += train
            total_val += val
            total_batches += batches
        else:
            print(f"   ERROR: No manifest found in {dataset_dir}")
            # Check for temp_batches (partial extraction)
            temp_dirs = [
                dataset_dir / 'temp_batches',
                dataset_dir / f'temp_batches_{dataset}',
                dataset_dir / 'temp_batches_slakh',
                dataset_dir / 'temp_batches_groove',
            ]
            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    checkpoint = temp_dir / 'checkpoint.json'
                    if checkpoint.exists():
                        with open(checkpoint) as f:
                            cp = json.load(f)
                        files = len(cp.get("processed_files", []))
                        samps = cp.get("total_samples", 0)
                        print(f"   PARTIAL: {files:,} files processed, {samps:,} samples so far")
                        break
    
    print(f"\n" + "=" * 60)
    print(f"TOTALS")
    print("=" * 60)
    print(f"Total samples: {total_samples:,}")
    print(f"Total train: {total_train:,}")
    print(f"Total val: {total_val:,}")
    print(f"Total batches: {total_batches}")
    
    # Expected counts
    print(f"\n" + "=" * 60)
    print("EXPECTED vs ACTUAL")
    print("=" * 60)
    print(f"EGMD: Expected ~45,537 files -> ~9.7M samples")
    print(f"Groove: Expected ~1,090 files -> ~240K samples")
    print(f"Slakh: Expected ~1,710 files -> ~300-500K samples")
    print(f"Total Expected: ~10-11M samples")

if __name__ == "__main__":
    verify_extraction()
