#!/usr/bin/env python3
"""Analyze confusion patterns - what classes get confused with what."""
import torch
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from training.multilabel.train_multilabel import create_model
from torch.utils.data import DataLoader

def main():
    device = torch.device('cuda')
    
    model = create_model(model_version='v5', num_classes=12, v5_size='large', drop_path_rate=0.1)
    ckpt = torch.load('runs/v5_multilabel/best_checkpoint.pt', map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])
    model = model.to(device).eval()
    print(f'Model: Epoch {ckpt["epoch"]}, F1: {ckpt["best_val_f1"]:.4f}')

    val_dataset = CachedMultiLabelDataset(
        data_dir='F:/datasets/prod_v5_multilabel/val', num_classes=12,
        class_names=DEFAULT_DRUM_COMPONENTS[:12],
        feature_cache_dir='F:/feature_cache/train',
        cache_mapping_path='F:/datasets/prod_v5_final/train/cache_mapping.npz')
    
    np.random.seed(42)
    indices = np.random.choice(len(val_dataset), 50000, replace=False)
    loader = DataLoader(torch.utils.data.Subset(val_dataset, indices), 
                       batch_size=512, num_workers=0, pin_memory=True)

    print('Getting predictions...')
    all_probs, all_labels = [], []
    with torch.no_grad():
        for specs, labels in loader:
            probs = torch.sigmoid(model(specs.to(device)))
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    all_probs = np.vstack(all_probs)
    all_labels = np.vstack(all_labels)
    all_preds = (all_probs >= 0.5).astype(float)

    class_names = DEFAULT_DRUM_COMPONENTS[:12]
    
    # Focus on the problem classes
    problem_classes = [
        (5, 'hihat_pedal'),
        (2, 'cross_stick'),
        (8, 'ride_bow'),
        (3, 'hihat_closed'),
        (4, 'hihat_open'),
        (7, 'ride_bell'),
    ]
    
    print('\n' + '='*80)
    print('ERROR ANALYSIS FOR PROBLEM CLASSES')
    print('='*80)
    
    for cls_idx, cls_name in problem_classes:
        print(f'\n{"="*80}')
        print(f'{cls_name.upper()} (idx={cls_idx})')
        print(f'{"="*80}')
        
        # Get samples where this class is positive
        pos_mask = all_labels[:, cls_idx] == 1
        neg_mask = all_labels[:, cls_idx] == 0
        
        # False negatives: label=1, pred=0 (MISSED - hurts recall)
        fn_mask = pos_mask & (all_preds[:, cls_idx] == 0)
        # False positives: label=0, pred=1 (FALSE ALARM - hurts precision)
        fp_mask = neg_mask & (all_preds[:, cls_idx] == 1)
        # True positives
        tp_mask = pos_mask & (all_preds[:, cls_idx] == 1)
        
        n_pos = pos_mask.sum()
        n_tp = tp_mask.sum()
        n_fn = fn_mask.sum()
        n_fp = fp_mask.sum()
        
        recall = n_tp / n_pos if n_pos > 0 else 0
        precision = n_tp / (n_tp + n_fp) if (n_tp + n_fp) > 0 else 0
        
        print(f'\nBasic stats:')
        print(f'  Total positive samples: {n_pos}')
        print(f'  True positives: {n_tp} ({100*n_tp/n_pos:.1f}%)')
        print(f'  False negatives (MISSED): {n_fn} ({100*n_fn/n_pos:.1f}%)')
        print(f'  False positives: {n_fp}')
        print(f'  Recall: {recall:.3f}, Precision: {precision:.3f}')
        
        # For FALSE NEGATIVES: What other classes are predicted?
        print(f'\n  When {cls_name} is MISSED (FN={n_fn}), what IS predicted?')
        fn_preds = all_preds[fn_mask]
        if len(fn_preds) > 0:
            for i, name in enumerate(class_names):
                if i == cls_idx:
                    continue
                count = fn_preds[:, i].sum()
                pct = 100 * count / len(fn_preds)
                if pct > 10:  # Only show significant
                    print(f'    {name}: {count:.0f} ({pct:.1f}%)')
        
        # For FALSE NEGATIVES: What's the probability distribution?
        fn_probs = all_probs[fn_mask, cls_idx]
        if len(fn_probs) > 0:
            print(f'\n  Probability distribution for MISSED samples:')
            for thresh in [0.1, 0.2, 0.3, 0.4, 0.5]:
                above = (fn_probs >= thresh).sum()
                pct = 100 * above / len(fn_probs)
                print(f'    p >= {thresh}: {above} ({pct:.1f}%)')
        
        # For FALSE NEGATIVES: What other classes are in the ground truth?
        print(f'\n  What classes co-occur in MISSED samples (ground truth)?')
        fn_labels = all_labels[fn_mask]
        if len(fn_labels) > 0:
            for i, name in enumerate(class_names):
                if i == cls_idx:
                    continue
                count = fn_labels[:, i].sum()
                pct = 100 * count / len(fn_labels)
                if pct > 5:
                    print(f'    + {name}: {count:.0f} ({pct:.1f}%)')
        
        # For FALSE POSITIVES: What's the actual class?
        print(f'\n  When {cls_name} is FALSE POSITIVE (FP={n_fp}), actual labels:')
        fp_labels = all_labels[fp_mask]
        if len(fp_labels) > 0:
            for i, name in enumerate(class_names):
                count = fp_labels[:, i].sum()
                pct = 100 * count / len(fp_labels)
                if pct > 10:
                    print(f'    Actually {name}: {count:.0f} ({pct:.1f}%)')

    print('\n' + '='*80)
    print('SUMMARY: Key Confusion Patterns')
    print('='*80)


if __name__ == '__main__':
    main()
