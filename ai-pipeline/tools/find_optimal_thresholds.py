#!/usr/bin/env python3
"""Find optimal per-class thresholds to maximize F1 for each class.

Updated for BatchedMultiLabelDataset format with EMA weight loading.
"""
import torch
import numpy as np
import json
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import BatchedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from training.models.cnn_v5 import cnn_v5_large
from torch.utils.data import DataLoader, ConcatDataset
from sklearn.metrics import precision_recall_fscore_support, f1_score
from tqdm import tqdm


def find_optimal_threshold(y_true, y_prob, thresholds=None):
    """Find threshold that maximizes F1 for a single class."""
    if thresholds is None:
        # Search range 0.15 to 0.85 with fine granularity
        thresholds = np.arange(0.15, 0.85, 0.025)
    
    best_f1 = 0
    best_thresh = 0.5
    best_prec = 0
    best_recall = 0
    
    for thresh in thresholds:
        y_pred = (y_prob >= thresh).astype(float)
        p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average='binary', zero_division=0)
        if f > best_f1:
            best_f1 = f
            best_thresh = thresh
            best_prec = p
            best_recall = r
    
    return best_thresh, best_f1, best_prec, best_recall


def load_model_with_ema(checkpoint_path: str, device: torch.device, num_classes: int = 12):
    """Load model from checkpoint, preferring EMA weights if available."""
    print(f"Loading checkpoint: {checkpoint_path}")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Create model
    model = cnn_v5_large(num_classes=num_classes)
    
    # Extract weights - prefer EMA
    if 'ema_state_dict' in ckpt:
        print("Using EMA weights")
        ema_state = ckpt['ema_state_dict']
        # EMA weights are nested: {'ema_model': state_dict, 'decay': ..., ...}
        if isinstance(ema_state, dict) and 'ema_model' in ema_state:
            state_dict = ema_state['ema_model']
        else:
            state_dict = ema_state
    else:
        print("Using main model weights (no EMA found)")
        state_dict = ckpt.get('model_state_dict', ckpt.get('state_dict', ckpt))
    
    # Strip 'backbone.' prefix if present (from MultiLabelDrumClassifier wrapper)
    cleaned_state_dict = {}
    for k, v in state_dict.items():
        new_key = k.replace('backbone.', '') if k.startswith('backbone.') else k
        cleaned_state_dict[new_key] = v
    
    # Load weights
    result = model.load_state_dict(cleaned_state_dict, strict=False)
    if result.missing_keys:
        print(f"  Missing keys: {result.missing_keys[:5]}...")
    if result.unexpected_keys:
        print(f"  Unexpected keys: {result.unexpected_keys[:5]}...")
    
    model.to(device)
    model.eval()
    
    # Print checkpoint info
    epoch = ckpt.get('epoch', 'unknown')
    best_f1 = ckpt.get('best_val_f1', ckpt.get('best_f1', 'unknown'))
    print(f"Model loaded - Epoch {epoch}, Best F1: {best_f1}")
    
    return model


def main():
    parser = argparse.ArgumentParser(description="Find optimal per-class thresholds")
    parser.add_argument('--checkpoint', type=str, 
                        default='runs/v5_real_4.8M_cbfocal/best_checkpoint.pt',
                        help='Path to model checkpoint')
    parser.add_argument('--output', type=str,
                        default=None,
                        help='Output path for thresholds JSON (default: same dir as checkpoint)')
    parser.add_argument('--max-samples', type=int, default=100000,
                        help='Maximum validation samples to use')
    args = parser.parse_args()
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model with EMA weights
    model = load_model_with_ema(args.checkpoint, device, num_classes=12)
    
    # Load validation data from both manifests
    manifest_files = [
        'F:/datasets/multilabel_real_v2/egmd/egmd_manifest.json',
        'F:/datasets/multilabel_real_v2/groove/groove_midi/groove_manifest.json',
    ]
    
    val_datasets = []
    for manifest in manifest_files:
        if Path(manifest).exists():
            print(f"Loading validation split from: {manifest}")
            val_ds = BatchedMultiLabelDataset(
                manifest_path=manifest,
                is_train=False,
                num_classes=12,
                shuffle_before_split=True,
                split_seed=42,
            )
            val_datasets.append(val_ds)
            print(f"  -> {len(val_ds):,} validation samples")
        else:
            print(f"Warning: Manifest not found: {manifest}")
    
    if not val_datasets:
        print("ERROR: No validation datasets found!")
        sys.exit(1)
    
    val_dataset = ConcatDataset(val_datasets) if len(val_datasets) > 1 else val_datasets[0]
    total_samples = len(val_dataset)
    print(f"\nTotal validation samples: {total_samples:,}")
    
    # Limit samples if dataset is very large
    if total_samples > args.max_samples:
        np.random.seed(42)
        indices = np.random.choice(total_samples, args.max_samples, replace=False)
        val_dataset = torch.utils.data.Subset(val_dataset, indices)
        print(f"Using {args.max_samples:,} samples for threshold optimization")
    
    loader = DataLoader(val_dataset, batch_size=512, num_workers=0, pin_memory=True, shuffle=False)

    print('\nGetting predictions...')
    all_probs, all_labels = [], []
    with torch.no_grad():
        for specs, labels in tqdm(loader, desc="Inference"):
            probs = torch.sigmoid(model(specs.to(device)))
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    all_probs = np.vstack(all_probs)
    all_labels = np.vstack(all_labels)
    
    print(f"Collected {len(all_probs):,} samples")

    class_names = DEFAULT_DRUM_COMPONENTS[:12]
    
    # First show default threshold=0.5 performance
    print('\n' + '='*70)
    print('BASELINE: All classes at threshold=0.5')
    print('='*70)
    print(f"{'Class':<15} {'Prec':>8} {'Recall':>8} {'F1':>8}")
    print('-' * 45)
    
    default_preds = (all_probs >= 0.5).astype(float)
    for i, name in enumerate(class_names):
        p, r, f, _ = precision_recall_fscore_support(all_labels[:,i], default_preds[:,i], 
                                                      average='binary', zero_division=0)
        marker = ' <<<' if f < 0.85 else ''
        print(f'{name:<15} {p:>8.3f} {r:>8.3f} {f:>8.3f}{marker}')
    
    baseline_micro = f1_score(all_labels, default_preds, average='micro')
    baseline_macro = f1_score(all_labels, default_preds, average='macro')
    print(f'\nMicro F1: {baseline_micro:.4f}, Macro F1: {baseline_macro:.4f}')

    # Find optimal thresholds
    print('\n' + '='*70)
    print('OPTIMIZED: Per-class optimal thresholds')
    print('='*70)
    print(f"{'Class':<15} {'Thresh':>8} {'Prec':>8} {'Recall':>8} {'F1':>8} {'Δ F1':>8}")
    print('-' * 60)
    
    optimal_thresholds = {}
    optimized_preds = np.zeros_like(all_probs)
    
    for i, name in enumerate(class_names):
        # Get baseline F1
        p0, r0, f0, _ = precision_recall_fscore_support(all_labels[:,i], default_preds[:,i], 
                                                         average='binary', zero_division=0)
        
        # Find optimal threshold
        best_thresh, best_f1, best_prec, best_recall = find_optimal_threshold(
            all_labels[:,i], all_probs[:,i]
        )
        optimal_thresholds[name] = float(best_thresh)
        optimized_preds[:,i] = (all_probs[:,i] >= best_thresh).astype(float)
        
        delta = best_f1 - f0
        marker = ' ↑↑↑' if delta > 0.05 else (' ↑' if delta > 0.01 else '')
        print(f'{name:<15} {best_thresh:>8.2f} {best_prec:>8.3f} {best_recall:>8.3f} {best_f1:>8.3f} {delta:>+8.3f}{marker}')
    
    optimized_micro = f1_score(all_labels, optimized_preds, average='micro')
    optimized_macro = f1_score(all_labels, optimized_preds, average='macro')
    
    print(f'\nMicro F1: {optimized_micro:.4f} (was {baseline_micro:.4f}, Δ {optimized_micro-baseline_micro:+.4f})')
    print(f'Macro F1: {optimized_macro:.4f} (was {baseline_macro:.4f}, Δ {optimized_macro-baseline_macro:+.4f})')
    
    # Save thresholds to JSON
    output_path = args.output
    if output_path is None:
        checkpoint_dir = Path(args.checkpoint).parent
        output_path = checkpoint_dir / 'thresholds.json'
    else:
        output_path = Path(output_path)
    
    thresholds_data = {
        "thresholds": optimal_thresholds,
        "baseline_micro_f1": float(baseline_micro),
        "baseline_macro_f1": float(baseline_macro),
        "optimized_micro_f1": float(optimized_micro),
        "optimized_macro_f1": float(optimized_macro),
        "checkpoint": str(args.checkpoint),
        "num_samples": len(all_probs),
    }
    
    with open(output_path, 'w') as f:
        json.dump(thresholds_data, f, indent=2)
    
    print(f'\n✓ Thresholds saved to: {output_path}')
    
    print('\n' + '='*70)
    print('RECOMMENDED THRESHOLDS')
    print('='*70)
    print('OPTIMAL_THRESHOLDS = {')
    for name, thresh in optimal_thresholds.items():
        print(f'    "{name}": {thresh:.2f},')
    print('}')


if __name__ == '__main__':
    main()
