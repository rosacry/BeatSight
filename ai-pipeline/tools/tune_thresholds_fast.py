#!/usr/bin/env python3
"""
Fast Per-Class Threshold Tuning

Uses direct cache access (like diagnose_model.py) to efficiently tune thresholds.
Outputs optimal per-class thresholds for multi-label drum classification.
"""

import sys
from pathlib import Path
import json
import numpy as np
import torch
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.utils.consolidated_cache import ConsolidatedCacheReader
import torch.nn as nn

class MultiLabelDrumClassifier(nn.Module):
    """Simple wrapper for multi-label classification."""
    def __init__(self, backbone, num_classes=12):
        super().__init__()
        self.backbone = backbone
        self.num_classes = num_classes
    
    def forward(self, x):
        return self.backbone(x)

CLASSES = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 'hihat_pedal',
           'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']


def load_model(checkpoint_path: str, device: str = 'cuda'):
    """Load model with proper weight handling."""
    backbone = cnn_v5_large(num_classes=12)
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Strip 'backbone.' prefix from state dict
    state = {}
    for k, v in ckpt['model_state_dict'].items():
        if k.startswith('backbone.'):
            state[k[9:]] = v  # Remove 'backbone.'
        else:
            state[k] = v
    
    backbone.load_state_dict(state, strict=False)
    model = MultiLabelDrumClassifier(backbone, num_classes=12)
    return model.to(device).eval()


def collect_predictions(model, val_labels, source_indices, cache, cache_mapping, device='cuda', n_samples=50000):
    """Collect predictions on validation samples."""
    cache_shards = cache_mapping['shard_ids']
    cache_offsets = cache_mapping['offsets']
    cache_valid = cache_mapping['valid']
    
    np.random.seed(42)
    sample_idx = np.random.choice(len(val_labels), min(n_samples, len(val_labels)), replace=False)
    
    all_preds = []
    all_labels = []
    
    print(f'Collecting predictions on {len(sample_idx)} samples...')
    with torch.no_grad():
        for idx in tqdm(sample_idx):
            src_idxs = source_indices[idx]
            specs = []
            for src_idx in src_idxs:
                src_idx = int(src_idx)
                if src_idx < len(cache_valid) and cache_valid[src_idx]:
                    shard_id = int(cache_shards[src_idx])
                    offset = int(cache_offsets[src_idx])
                    try:
                        spec = cache._read_sample(shard_id, offset)
                        if spec is not None:
                            specs.append(spec.numpy() if isinstance(spec, torch.Tensor) else spec)
                    except Exception:
                        pass
            
            if not specs:
                continue
            
            # Max blending
            stacked = np.stack(specs, axis=0)
            blended = np.max(stacked, axis=0)
            
            if blended.ndim == 2:
                blended = blended[np.newaxis, ...]
            
            x = torch.from_numpy(blended).unsqueeze(0).to(device)
            probs = torch.sigmoid(model(x)).cpu().numpy()[0]
            all_preds.append(probs)
            all_labels.append(val_labels[idx])
    
    return np.array(all_preds), np.array(all_labels)


def find_optimal_threshold(y_true, y_prob, thresholds=None):
    """Find threshold that maximizes F1 for a single class."""
    if thresholds is None:
        thresholds = np.arange(0.1, 0.9, 0.025)
    
    best_f1 = 0
    best_t = 0.5
    best_metrics = {}
    
    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        
        if f1 > best_f1:
            best_f1 = f1
            best_t = t
            best_metrics = {'precision': prec, 'recall': rec, 'f1': f1, 'tp': tp, 'fp': fp, 'fn': fn}
    
    return best_t, best_metrics


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='runs/v5_multilabel_ohem/best_checkpoint.pt')
    parser.add_argument('--val-dir', type=str, default='F:/datasets/prod_v5_multilabel/val')
    parser.add_argument('--cache-dir', type=str, default='F:/feature_cache/train')
    parser.add_argument('--cache-mapping', type=str, default='F:/datasets/prod_v5_final/train/cache_mapping.npz')
    parser.add_argument('--output', type=str, default='runs/v5_multilabel_ohem/optimal_thresholds.json')
    parser.add_argument('--n-samples', type=int, default=50000, help='Number of val samples to use')
    parser.add_argument('--device', type=str, default='cuda')
    args = parser.parse_args()
    
    # Load model
    print(f'Loading model: {args.model}')
    model = load_model(args.model, args.device)
    
    # Load data
    print(f'\nLoading validation data...')
    val_labels = np.load(f'{args.val_dir}/train_labels_labels.npy')
    source_indices = np.load(f'{args.val_dir}/source_indices.npy', allow_pickle=True)
    print(f'  Val samples: {len(val_labels)}')
    
    # Load cache
    print(f'\nLoading feature cache...')
    cache = ConsolidatedCacheReader(Path(args.cache_dir))
    cache_mapping = np.load(args.cache_mapping, mmap_mode='r')
    
    # Collect predictions
    all_preds, all_labels = collect_predictions(
        model, val_labels, source_indices, cache, cache_mapping, 
        device=args.device, n_samples=args.n_samples
    )
    print(f'Collected {len(all_preds)} predictions')
    
    # Tune thresholds per class
    print('\n' + '='*80)
    print('PER-CLASS THRESHOLD TUNING')
    print('='*80)
    print(f'{"Class":<15} {"Baseline F1":>12} {"Tuned F1":>12} {"Δ":>8} {"Threshold":>10}')
    print('-'*80)
    
    per_class_thresholds = {}
    per_class_metrics = {}
    baseline_f1s = []
    tuned_f1s = []
    
    for i, cls in enumerate(CLASSES):
        y_true = all_labels[:, i]
        y_prob = all_preds[:, i]
        
        # Baseline at 0.5
        y_pred_base = (y_prob >= 0.5).astype(int)
        tp_base = np.sum((y_true == 1) & (y_pred_base == 1))
        fp_base = np.sum((y_true == 0) & (y_pred_base == 1))
        fn_base = np.sum((y_true == 1) & (y_pred_base == 0))
        prec_base = tp_base / (tp_base + fp_base) if (tp_base + fp_base) > 0 else 0
        rec_base = tp_base / (tp_base + fn_base) if (tp_base + fn_base) > 0 else 0
        f1_base = 2 * prec_base * rec_base / (prec_base + rec_base) if (prec_base + rec_base) > 0 else 0
        baseline_f1s.append(f1_base)
        
        # Find optimal threshold
        best_t, best_metrics = find_optimal_threshold(y_true, y_prob)
        f1_tuned = best_metrics['f1']
        tuned_f1s.append(f1_tuned)
        
        delta = f1_tuned - f1_base
        delta_str = f'+{delta:.3f}' if delta > 0 else f'{delta:.3f}'
        
        per_class_thresholds[cls] = round(best_t, 3)
        per_class_metrics[cls] = {
            'threshold': round(best_t, 3),
            'f1': round(f1_tuned, 4),
            'precision': round(best_metrics['precision'], 4),
            'recall': round(best_metrics['recall'], 4),
            'baseline_f1': round(f1_base, 4),
            'improvement': round(delta, 4),
        }
        
        flag = '🔥' if delta > 0.05 else ('✅' if delta > 0.01 else '')
        print(f'{cls:<15} {f1_base:>12.4f} {f1_tuned:>12.4f} {delta_str:>8} {best_t:>10.3f} {flag}')
    
    print('-'*80)
    macro_f1_base = np.mean(baseline_f1s)
    macro_f1_tuned = np.mean(tuned_f1s)
    delta_macro = macro_f1_tuned - macro_f1_base
    print(f'{"MACRO F1":<15} {macro_f1_base:>12.4f} {macro_f1_tuned:>12.4f} {f"+{delta_macro:.3f}":>8}')
    
    # Calculate micro F1 with tuned thresholds
    all_tp, all_fp, all_fn = 0, 0, 0
    for i, cls in enumerate(CLASSES):
        t = per_class_thresholds[cls]
        y_pred = (all_preds[:, i] >= t).astype(int)
        y_true = all_labels[:, i]
        all_tp += np.sum((y_true == 1) & (y_pred == 1))
        all_fp += np.sum((y_true == 0) & (y_pred == 1))
        all_fn += np.sum((y_true == 1) & (y_pred == 0))
    
    micro_prec = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0
    micro_rec = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0
    micro_f1_tuned = 2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0
    
    # Baseline micro F1
    all_tp_b, all_fp_b, all_fn_b = 0, 0, 0
    for i in range(12):
        y_pred = (all_preds[:, i] >= 0.5).astype(int)
        y_true = all_labels[:, i]
        all_tp_b += np.sum((y_true == 1) & (y_pred == 1))
        all_fp_b += np.sum((y_true == 0) & (y_pred == 1))
        all_fn_b += np.sum((y_true == 1) & (y_pred == 0))
    micro_prec_b = all_tp_b / (all_tp_b + all_fp_b) if (all_tp_b + all_fp_b) > 0 else 0
    micro_rec_b = all_tp_b / (all_tp_b + all_fn_b) if (all_tp_b + all_fn_b) > 0 else 0
    micro_f1_base = 2 * micro_prec_b * micro_rec_b / (micro_prec_b + micro_rec_b) if (micro_prec_b + micro_rec_b) > 0 else 0
    
    delta_micro = micro_f1_tuned - micro_f1_base
    print(f'{"MICRO F1":<15} {micro_f1_base:>12.4f} {micro_f1_tuned:>12.4f} {f"+{delta_micro:.3f}":>8}')
    
    # Save results
    output = {
        'model_path': args.model,
        'val_samples_used': len(all_preds),
        'per_class_thresholds': per_class_thresholds,
        'per_class_metrics': per_class_metrics,
        'baseline_metrics': {
            'threshold': 0.5,
            'macro_f1': round(macro_f1_base, 4),
            'micro_f1': round(micro_f1_base, 4),
        },
        'tuned_metrics': {
            'macro_f1': round(macro_f1_tuned, 4),
            'micro_f1': round(micro_f1_tuned, 4),
        },
        'improvement': {
            'macro_f1': round(delta_macro, 4),
            'micro_f1': round(delta_micro, 4),
        },
    }
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f'\n✅ Saved thresholds to: {args.output}')
    print('\nKey improvements:')
    for cls, metrics in sorted(per_class_metrics.items(), key=lambda x: x[1]['improvement'], reverse=True)[:5]:
        if metrics['improvement'] > 0.01:
            print(f'  {cls}: {metrics["baseline_f1"]:.3f} → {metrics["f1"]:.3f} (+{metrics["improvement"]:.3f}) @ t={metrics["threshold"]:.3f}')


if __name__ == '__main__':
    main()
