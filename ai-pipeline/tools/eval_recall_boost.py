#!/usr/bin/env python3
"""Quick evaluation of recall_boost model."""
import torch
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from training.multilabel.train_multilabel import create_model
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score, precision_recall_fscore_support


def main():
    device = torch.device('cuda')
    model = create_model(model_version='v5', num_classes=12, v5_size='large', drop_path_rate=0.1)
    ckpt = torch.load('runs/v5_multilabel_recall_boost/best_checkpoint.pt', map_location=device, weights_only=False)
    model.load_state_dict(ckpt['model_state_dict'])
    model = model.to(device).eval()
    print(f'Recall Boost Model - Epoch {ckpt["epoch"]}, F1: {ckpt["best_val_f1"]:.4f}')

    val_dataset = CachedMultiLabelDataset(
        data_dir='F:/datasets/prod_v5_multilabel/val', num_classes=12,
        class_names=DEFAULT_DRUM_COMPONENTS[:12],
        feature_cache_dir='F:/feature_cache/train',
        cache_mapping_path='F:/datasets/prod_v5_final/train/cache_mapping.npz')
    np.random.seed(42)
    indices = np.random.choice(len(val_dataset), 20000, replace=False)
    # num_workers=0 to avoid Windows multiprocessing issues
    loader = DataLoader(torch.utils.data.Subset(val_dataset, indices), batch_size=512, num_workers=0, pin_memory=True)

    print('Evaluating on 20k samples...')
    all_preds, all_labels = [], []
    with torch.no_grad():
        for specs, labels in loader:
            probs = torch.sigmoid(model(specs.to(device)))
            all_preds.append((probs > 0.5).float().cpu().numpy())
            all_labels.append(labels.numpy())
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)

    print()
    print('Per-Class Performance (threshold=0.5)')
    print(f'{"Class":<15} {"Prec":>8} {"Recall":>8} {"F1":>8} {"Support":>8}')
    print('-' * 55)
    for i, cls in enumerate(DEFAULT_DRUM_COMPONENTS[:12]):
        p, r, f, _ = precision_recall_fscore_support(all_labels[:,i], all_preds[:,i], average='binary', zero_division=0)
        support = int(all_labels[:,i].sum())
        marker = '  <<<' if f < 0.75 else ''
        print(f'{cls:<15} {p:>8.3f} {r:>8.3f} {f:>8.3f} {support:>8}{marker}')
    print()
    print(f'Macro F1: {f1_score(all_labels, all_preds, average="macro"):.4f}')
    print(f'Micro F1: {f1_score(all_labels, all_preds, average="micro"):.4f}')


if __name__ == '__main__':
    main()
