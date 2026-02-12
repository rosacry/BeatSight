#!/usr/bin/env python3
"""
Hard Example Mining - Extract samples where model is uncertain.

These are the most valuable training samples because:
1. Model is at decision boundary (p=0.3-0.5 for true positives)
2. Training on these will push the boundary in the right direction
3. Focuses compute on samples that matter most

Usage:
    python tools/extract_hard_examples.py \
        --checkpoint runs/v5_multilabel/best_checkpoint.pt \
        --train-dir F:/datasets/prod_v5_multilabel/train \
        --source-dataset F:/datasets/prod_v5_final \
        --feature-cache-dir F:/feature_cache \
        --output-dir F:/datasets/prod_v5_multilabel_hard \
        --p-low 0.2 --p-high 0.6 \
        --max-samples 500000
"""

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm
import json


def main():
    parser = argparse.ArgumentParser(description="Extract hard examples for mining")
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to model checkpoint')
    parser.add_argument('--train-dir', type=str, required=True,
                        help='Training data directory')
    parser.add_argument('--source-dataset', type=str, required=True,
                        help='Source dataset directory')
    parser.add_argument('--feature-cache-dir', type=str, required=True,
                        help='Feature cache directory')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for hard examples')
    parser.add_argument('--p-low', type=float, default=0.2,
                        help='Lower probability threshold for hard examples')
    parser.add_argument('--p-high', type=float, default=0.6,
                        help='Upper probability threshold for hard examples')
    parser.add_argument('--max-samples', type=int, default=500000,
                        help='Maximum number of hard examples to extract')
    parser.add_argument('--batch-size', type=int, default=512,
                        help='Batch size for inference')
    parser.add_argument('--num-workers', type=int, default=4,
                        help='DataLoader workers')
    args = parser.parse_args()
    
    from training.multilabel.dataset import CachedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
    from training.multilabel.train_multilabel import create_model
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load model
    print(f"\nLoading model from {args.checkpoint}...")
    model = create_model(
        model_version='v5',
        num_classes=12,
        pretrained_checkpoint=args.checkpoint,
        v5_size='large',
    )
    model = model.to(device)
    model.eval()
    
    # Load training dataset
    print(f"\nLoading training dataset from {args.train_dir}...")
    train_dir = Path(args.train_dir)
    source_dir = Path(args.source_dataset)
    cache_dir = Path(args.feature_cache_dir)
    
    train_dataset = CachedMultiLabelDataset(
        data_dir=train_dir,
        num_classes=12,
        class_names=DEFAULT_DRUM_COMPONENTS[:12],
        feature_cache_dir=cache_dir / "train" if (cache_dir / "train").exists() else cache_dir,
        cache_mapping_path=source_dir / "train" / "cache_mapping.npz",
        is_multilabel=True,
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True,
    )
    
    print(f"Training samples: {len(train_dataset):,}")
    
    # Run inference and collect hard example indices
    print(f"\nScanning for hard examples (p in [{args.p_low}, {args.p_high}])...")
    
    hard_indices = []
    hard_scores = []  # Track how "hard" each sample is
    
    sample_idx = 0
    with torch.no_grad():
        for features, labels in tqdm(train_loader, desc="Scanning"):
            features = features.to(device)
            labels = labels.numpy()
            
            logits = model(features)
            probs = torch.sigmoid(logits).cpu().numpy()
            
            batch_size = len(features)
            
            for i in range(batch_size):
                global_idx = sample_idx + i
                
                # Find classes where label=1 (true positive expected)
                positive_classes = np.where(labels[i] > 0.5)[0]
                
                if len(positive_classes) == 0:
                    continue
                
                # Check if any positive class has probability in the hard range
                positive_probs = probs[i, positive_classes]
                
                # Hard example: at least one positive class has p in [p_low, p_high]
                hard_mask = (positive_probs >= args.p_low) & (positive_probs <= args.p_high)
                
                if np.any(hard_mask):
                    # Score by how many classes are in hard range and how uncertain
                    # Lower probability = harder = higher priority
                    uncertainty = 0.5 - np.abs(positive_probs - 0.5)  # Max at p=0.5
                    hard_score = np.sum(uncertainty[hard_mask])
                    
                    hard_indices.append(global_idx)
                    hard_scores.append(hard_score)
            
            sample_idx += batch_size
            
            # Early stopping if we have enough candidates
            if len(hard_indices) >= args.max_samples * 2:
                print(f"\nFound enough candidates ({len(hard_indices):,}), stopping scan...")
                break
    
    print(f"\nFound {len(hard_indices):,} hard examples")
    
    # Sort by hardness score (higher = harder = more valuable)
    sorted_indices = np.argsort(hard_scores)[::-1]
    selected_indices = [hard_indices[i] for i in sorted_indices[:args.max_samples]]
    
    print(f"Selected top {len(selected_indices):,} hardest examples")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load original labels and source indices
    train_labels = np.load(train_dir / "train_labels_labels.npy", mmap_mode='r')
    train_source_indices = np.load(train_dir / "source_indices.npy", allow_pickle=True)
    
    # Extract hard examples
    hard_labels = train_labels[selected_indices].copy()
    hard_source_indices = train_source_indices[selected_indices].copy()
    
    # Save hard examples
    print(f"\nSaving hard examples to {output_dir}...")
    
    # Create train subdirectory
    hard_train_dir = output_dir / "train"
    hard_train_dir.mkdir(parents=True, exist_ok=True)
    
    np.save(hard_train_dir / "train_labels_labels.npy", hard_labels)
    np.save(hard_train_dir / "source_indices.npy", hard_source_indices)
    
    # Copy cache mapping (same as original)
    import shutil
    src_mapping = source_dir / "train" / "cache_mapping.npz"
    if src_mapping.exists():
        shutil.copy(src_mapping, hard_train_dir / "cache_mapping.npz")
    
    # Analyze class distribution in hard examples
    print("\n" + "=" * 60)
    print("HARD EXAMPLES CLASS DISTRIBUTION")
    print("=" * 60)
    
    class_counts = np.sum(hard_labels, axis=0)
    total = len(hard_labels)
    
    print(f"\nTotal hard examples: {total:,}")
    print(f"\n{'Class':<20} {'Count':>10} {'%':>8}")
    print("-" * 40)
    
    for i, name in enumerate(DEFAULT_DRUM_COMPONENTS[:12]):
        count = int(class_counts[i])
        pct = 100 * count / total
        print(f"{name:<20} {count:>10,} {pct:>7.1f}%")
    
    # Save metadata
    metadata = {
        "source_checkpoint": str(args.checkpoint),
        "source_train_dir": str(args.train_dir),
        "p_low": args.p_low,
        "p_high": args.p_high,
        "total_hard_examples": len(selected_indices),
        "class_counts": {name: int(class_counts[i]) for i, name in enumerate(DEFAULT_DRUM_COMPONENTS[:12])},
    }
    
    with open(output_dir / "hard_examples_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Hard examples saved to {output_dir}")
    print(f"\nNext step: Fine-tune on hard examples:")
    print(f"""
    python training/multilabel/train_multilabel.py \\
        --train-dir "{hard_train_dir}" \\
        --val-dir "F:/datasets/prod_v5_multilabel/val" \\
        --source-dataset "{source_dir}" \\
        --feature-cache-dir "{cache_dir}" \\
        --pretrained-checkpoint {args.checkpoint} \\
        --model-version v5 --v5-size large \\
        --epochs 10 --batch-size 128 --grad-accum-steps 2 \\
        --lr 1e-5 \\
        --amp-dtype bfloat16 \\
        --loss-type focal --gamma 2.0 \\
        --scheduler cosine --warmup-epochs 1 \\
        --num-workers 4 --pin-memory \\
        --output-dir runs/v5_multilabel_hard_mining
    """)


if __name__ == '__main__':
    main()
