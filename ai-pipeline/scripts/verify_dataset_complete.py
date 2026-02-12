#!/usr/bin/env python
"""Complete verification of multilabel_real_v3 dataset."""

import json
import numpy as np
from pathlib import Path

DATASET = Path('F:/datasets/multilabel_real_v3')
SOURCES = {
    'egmd': 'egmd_manifest.json',
    'groove_midi': 'groove_manifest.json',
    'slakh': 'slakh_manifest.json',
    'lakh_synth': 'lakh_manifest.json',
}
CLASS_NAMES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open',
               'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']

def find_batch_dir(manifest_path: Path) -> Path:
    """Find the batch directory, handling nested structures like egmd/egmd_batches."""
    batch_dir = manifest_path.parent
    
    # Check if features are directly in the parent
    if any(batch_dir.glob('features_batch_*.npy')):
        return batch_dir
    
    # Look for subdirectory containing batch files
    for subdir in batch_dir.iterdir():
        if subdir.is_dir() and any(subdir.glob('features_batch_*.npy')):
            return subdir
    
    # Fallback to parent
    return batch_dir


def main():
    grand_totals = np.zeros(12, dtype=np.int64)
    source_stats = {}

    print('=' * 70)
    print('COMPLETE DATASET VERIFICATION')
    print('=' * 70)
    print()

    for source, manifest_file in SOURCES.items():
        manifest_path = DATASET / source / manifest_file
        if not manifest_path.exists():
            print(f'{source}: MANIFEST NOT FOUND at {manifest_path}')
            continue
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Find the actual batch directory (handles egmd/egmd_batches pattern)
        batch_dir = find_batch_dir(manifest_path)
        
        batches = manifest['batches']
        source_class_totals = np.zeros(12, dtype=np.int64)
        n_samples = 0
        n_batches_read = 0
        
        batch_items = batches.items() if isinstance(batches, dict) else enumerate(batches)
        
        for batch_idx, batch_info in batch_items:
            # Normalize key names
            labels_key = batch_info.get('labels_file') or batch_info.get('labels')
            if not labels_key:
                continue
            
            # Get just the filename (in case path includes directory)
            labels_filename = Path(labels_key).name
            labels_path = batch_dir / labels_filename
            
            if not labels_path.exists():
                continue
            
            labels = np.load(labels_path)
            n_samples += len(labels)
            n_batches_read += 1
            for c in range(12):
                source_class_totals[c] += np.sum(labels[:, c] > 0.5)
        
        grand_totals += source_class_totals
        source_stats[source] = {
            'samples': n_samples, 
            'batches': n_batches_read,
            'classes': source_class_totals
        }
        
        print(f'[SOURCE] {source.upper()}')
        print(f'   Samples: {n_samples:,}  |  Batches: {n_batches_read}')
        
        # Show classes with > 0 samples
        active = [(c, source_class_totals[c]) for c in range(12) if source_class_totals[c] > 0]
        active.sort(key=lambda x: -x[1])
        for c, count in active[:6]:
            print(f'     {c:2}: {CLASS_NAMES[c]:15} = {count:>10,}')
        if len(active) > 6:
            print(f'     ... and {len(active)-6} more classes')
        print()

    print()
    print('=' * 70)
    print('GRAND TOTALS - ALL SOURCES COMBINED')
    print('=' * 70)
    total_samples = sum(s['samples'] for s in source_stats.values())
    print(f'Total samples: {total_samples:,}')
    print(f'Total hit count: {grand_totals.sum():,}')
    print()

    for c in range(12):
        count = grand_totals[c]
        pct = 100.0 * count / grand_totals.sum() if grand_totals.sum() > 0 else 0
        bar_len = int(pct / 2)
        bar = '#' * bar_len + '.' * (50 - bar_len)
        marker = ' ** TARGET **' if CLASS_NAMES[c] in ['china', 'splash'] else ''
        print(f'{c:2}: {CLASS_NAMES[c]:15} {bar} {count:>10,} ({pct:5.2f}%){marker}')

    print()
    print('=' * 70)
    print('CHINA & SPLASH VERIFICATION')
    print('=' * 70)
    for source in source_stats:
        china = source_stats[source]['classes'][0]
        splash = source_stats[source]['classes'][10]
        if china > 0 or splash > 0:
            print(f'{source:12}: china = {china:>10,}  |  splash = {splash:>10,}')

    print()
    print(f'TOTAL:        china = {grand_totals[0]:>10,}  |  splash = {grand_totals[10]:>10,}')
    
    # Final verdict
    print()
    print('=' * 70)
    print('VERIFICATION VERDICT')
    print('=' * 70)
    
    lakh = source_stats.get('lakh_synth', {})
    lakh_china = lakh.get('classes', np.zeros(12))[0] if lakh else 0
    lakh_splash = lakh.get('classes', np.zeros(12))[10] if lakh else 0
    
    checks = []
    
    # Check 1: lakh_synth has china at index 0
    if lakh_china > 200000:
        checks.append(('lakh_synth china count > 200K', True, lakh_china))
    else:
        checks.append(('lakh_synth china count > 200K', False, lakh_china))
    
    # Check 2: lakh_synth has splash at index 10
    if lakh_splash > 600000:
        checks.append(('lakh_synth splash count > 600K', True, lakh_splash))
    else:
        checks.append(('lakh_synth splash count > 600K', False, lakh_splash))
    
    # Check 3: lakh_synth has NO other classes
    other_classes = sum(lakh.get('classes', np.zeros(12))[c] for c in range(12) if c not in [0, 10])
    if other_classes == 0:
        checks.append(('lakh_synth has ONLY china+splash', True, other_classes))
    else:
        checks.append(('lakh_synth has ONLY china+splash', False, other_classes))
    
    # Check 4: Total dataset size
    if total_samples > 10_000_000:
        checks.append(('Total samples > 10M', True, total_samples))
    else:
        checks.append(('Total samples > 10M', False, total_samples))
    
    all_pass = True
    for name, passed, value in checks:
        status = 'PASS' if passed else 'FAIL'
        print(f'  [{status}] {name}: {value:,}')
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        print('>>> ALL CHECKS PASSED - DATASET IS READY FOR TRAINING <<<')
    else:
        print('>>> SOME CHECKS FAILED - INVESTIGATE BEFORE TRAINING <<<')

if __name__ == '__main__':
    main()
