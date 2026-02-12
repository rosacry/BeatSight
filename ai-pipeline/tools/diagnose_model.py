#!/usr/bin/env python3
"""
Deep diagnostic analysis of multi-label model performance.
Identifies class confusion patterns and bottlenecks.
"""

import sys
from pathlib import Path

# Add both ai-pipeline and training directory to path
ai_pipeline = Path(__file__).parent.parent
sys.path.insert(0, str(ai_pipeline))
sys.path.insert(0, str(ai_pipeline / "training"))

import torch
import torch.nn as nn
import numpy as np
from tqdm import tqdm

from models.cnn_v5 import cnn_v5_large
from utils.consolidated_cache import ConsolidatedCacheReader


class MultiLabelDrumClassifier(nn.Module):
    """Wrapper to use single-label backbone for multi-label classification."""
    
    def __init__(self, backbone: nn.Module, num_classes: int = 12):
        super().__init__()
        self.backbone = backbone
        self.num_classes = num_classes
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.backbone(x)


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # Load model
    print("Loading model...")
    backbone = cnn_v5_large(num_classes=12)
    ckpt = torch.load('runs/v5_multilabel_ohem/best_checkpoint.pt', map_location='cpu', weights_only=False)
    
    # Handle state dict key prefixes - checkpoint has 'backbone.' prefix
    state = {}
    for k, v in ckpt['model_state_dict'].items():
        # Remove 'backbone.' prefix to match the raw model structure
        new_key = k.replace('backbone.', '')
        state[new_key] = v
    
    # Load into backbone directly
    result = backbone.load_state_dict(state, strict=False)
    print(f"  Loaded weights: {len(state) - len(result.unexpected_keys)} matched, {len(result.missing_keys)} missing")
    
    # Wrap and move to device
    model = MultiLabelDrumClassifier(backbone, num_classes=12)
    model = model.to(device).eval()
    print(f"  Checkpoint from epoch {ckpt.get('epoch', '?')}")
    
    # Load validation data
    val_labels = np.load('F:/datasets/prod_v5_multilabel/val/train_labels_labels.npy')
    source_indices = np.load('F:/datasets/prod_v5_multilabel/val/source_indices.npy', allow_pickle=True)
    
    # Sample for speed (10k instead of 50k for faster results)
    np.random.seed(42)
    sample_idx = np.random.choice(len(val_labels), 10000, replace=False)
    
    # Load cache with cache mapping
    cache = ConsolidatedCacheReader(Path('F:/feature_cache/train'))
    cache_mapping = np.load('F:/datasets/prod_v5_final/train/cache_mapping.npz', mmap_mode='r')
    cache_shards = cache_mapping['shard_ids']
    cache_offsets = cache_mapping['offsets']
    cache_valid = cache_mapping['valid']
    
    all_preds = []
    all_labels_list = []
    
    print('Running inference on 10k val samples...')
    with torch.no_grad():
        for i, idx in enumerate(tqdm(sample_idx)):
            src_idxs = source_indices[idx]
            specs = []
            for src_idx in src_idxs:
                # Use cache mapping to get shard/offset
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
            
            # Blend using max (same as training default)
            stacked = np.stack(specs, axis=0)
            blended = np.max(stacked, axis=0)  # Max blending
            
            # Ensure correct shape: (C, H, W) -> (1, C, H, W)
            if blended.ndim == 2:
                blended = blended[np.newaxis, ...]  # (1, H, W)
            x = torch.from_numpy(blended).unsqueeze(0).to(device)  # (1, C, H, W)
            probs = torch.sigmoid(model(x)).cpu().numpy()[0]
            all_preds.append(probs)
            all_labels_list.append(val_labels[idx])
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels_list)
    print(f'Analyzed {len(all_preds)} samples')
    
    classes = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 'hihat_pedal',
               'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
    
    print()
    print('='*90)
    print('PER-CLASS DIAGNOSTIC (threshold=0.5)')
    print('='*90)
    print(f'{"Class":<15} {"F1":>6} {"Prec":>6} {"Rec":>6} {"TP":>7} {"FP":>7} {"FN":>7} | P(pos) | P(neg) | Gap')
    print('-'*90)
    
    class_f1s = []
    for i, cls in enumerate(classes):
        y_true = all_labels[:, i]
        y_pred = (all_preds[:, i] >= 0.5).astype(int)
        y_prob = all_preds[:, i]
        
        tp = np.sum((y_true == 1) & (y_pred == 1))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        class_f1s.append(f1)
        
        pos_mask = y_true == 1
        neg_mask = y_true == 0
        avg_p_pos = np.mean(y_prob[pos_mask]) if pos_mask.sum() > 0 else 0
        avg_p_neg = np.mean(y_prob[neg_mask]) if neg_mask.sum() > 0 else 0
        gap = avg_p_pos - avg_p_neg
        
        flag = "⚠️" if f1 < 0.7 else ""
        print(f'{cls:<15} {f1:>6.3f} {prec:>6.3f} {rec:>6.3f} {tp:>7} {fp:>7} {fn:>7} | {avg_p_pos:>6.3f} | {avg_p_neg:>6.3f} | {gap:>5.3f} {flag}')
    
    macro_f1 = np.mean(class_f1s)
    print('-'*90)
    print(f'{"MACRO F1":<15} {macro_f1:>6.3f}')
    
    # Calculate micro F1
    total_tp = sum(np.sum((all_labels[:, i] == 1) & (all_preds[:, i] >= 0.5)) for i in range(12))
    total_fp = sum(np.sum((all_labels[:, i] == 0) & (all_preds[:, i] >= 0.5)) for i in range(12))
    total_fn = sum(np.sum((all_labels[:, i] == 1) & (all_preds[:, i] < 0.5)) for i in range(12))
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    micro_f1 = 2 * micro_prec * micro_rec / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0
    print(f'{"MICRO F1":<15} {micro_f1:>6.3f}')
    
    print()
    print('='*90)
    print('CONFUSION ANALYSIS: When FN occurs, what other classes are predicted?')
    print('='*90)
    
    for i, cls in enumerate(classes):
        fn_mask = (all_labels[:, i] == 1) & (all_preds[:, i] < 0.5)
        if fn_mask.sum() < 100:
            continue
        
        fn_preds = all_preds[fn_mask]
        confused = []
        for j, other_cls in enumerate(classes):
            if i == j:
                continue
            pred_rate = (fn_preds[:, j] >= 0.5).mean()
            if pred_rate > 0.1:
                confused.append((other_cls, pred_rate))
        
        if confused:
            confused_str = ', '.join([f'{c}:{r:.0%}' for c, r in sorted(confused, key=lambda x: -x[1])[:3]])
            print(f'{cls:<15} FN={fn_mask.sum():>5} | Often predicts: {confused_str}')
    
    # Probability distribution analysis for weak classes
    print()
    print('='*90)
    print('WEAK CLASS PROBABILITY ANALYSIS')
    print('='*90)
    
    weak_classes = [i for i, f1 in enumerate(class_f1s) if f1 < 0.7]
    for i in weak_classes:
        cls = classes[i]
        y_true = all_labels[:, i]
        y_prob = all_preds[:, i]
        
        pos_probs = y_prob[y_true == 1]
        neg_probs = y_prob[y_true == 0]
        
        print(f'\n{cls.upper()} (F1={class_f1s[i]:.3f}):')
        print(f'  Positives: {len(pos_probs):,} samples')
        print(f'    P < 0.3: {(pos_probs < 0.3).sum():,} ({100*(pos_probs < 0.3).mean():.1f}%) - HARD, model cant see')
        print(f'    P 0.3-0.5: {((pos_probs >= 0.3) & (pos_probs < 0.5)).sum():,} ({100*((pos_probs >= 0.3) & (pos_probs < 0.5)).mean():.1f}%) - threshold fixable')
        print(f'    P >= 0.5: {(pos_probs >= 0.5).sum():,} ({100*(pos_probs >= 0.5).mean():.1f}%) - correctly detected')
        
        print(f'  Negatives: {len(neg_probs):,} samples')
        print(f'    P >= 0.5: {(neg_probs >= 0.5).sum():,} ({100*(neg_probs >= 0.5).mean():.1f}%) - false positives')
    
    print()
    print('='*90)
    print('RECOMMENDATIONS')
    print('='*90)
    
    # Identify main blockers
    blockers = [(classes[i], class_f1s[i]) for i in range(12) if class_f1s[i] < 0.75]
    if blockers:
        print('\n🚨 MAIN BLOCKERS (F1 < 0.75):')
        for cls, f1 in sorted(blockers, key=lambda x: x[1]):
            improvement_needed = 0.90 - f1
            print(f'   {cls}: F1={f1:.3f} (needs +{improvement_needed:.3f} to reach 0.90)')
    
    # Calculate how much each weak class is dragging down micro F1
    print('\n📊 CONTRIBUTION TO MICRO F1 GAP:')
    target_f1 = 0.90
    current_gap = target_f1 - micro_f1
    print(f'   Current: {micro_f1:.3f}, Target: {target_f1}, Gap: {current_gap:.3f}')


if __name__ == '__main__':
    main()
