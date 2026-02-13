#!/usr/bin/env python3
"""
Automatic Label Noise Detection and Cleaning

Uses the trained model's high-confidence predictions to identify mislabeled samples.
Based on "confident learning" - if the model is very confident a sample is class X
but it's labeled as class Y, and X≠Y, it's likely a label error.

Usage:
    python clean_label_noise.py \
        --checkpoint runs/v5_phase2/best_drum_classifier_ema.pth \
        --dataset F:/datasets/prod_v5_cleaned \
        --feature-cache-dir F:/feature_cache \
        --output-dir label_corrections \
        --confidence-threshold 0.80 \
        --split val

This will:
1. Run inference on all samples
2. Identify high-confidence disagreements (model confident, but disagrees with label)
3. Export corrections file for relabeling
4. Generate statistics on label noise per class
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm

# Add ai-pipeline to path
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Detect and clean label noise")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("label_corrections"))
    parser.add_argument("--confidence-threshold", type=float, default=0.80,
                        help="Minimum confidence to flag as potential mislabel")
    parser.add_argument("--split", choices=["train", "val", "both"], default="both")
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--dry-run", action="store_true", help="Only report, don't save")
    args = parser.parse_args()
    
    device = torch.device(args.device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load class names
    components_file = args.dataset / "components.json"
    with open(components_file, 'r') as f:
        data = json.load(f)
    class_names = data.get("components", [])
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")
    
    # Load model
    print(f"\nLoading V5 {args.v5_size} model...")
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if args.v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes)
    elif args.v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes)
    else:
        model = cnn_v5_medium(num_classes=num_classes)
    
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    # Process each split
    splits = ["train", "val"] if args.split == "both" else [args.split]
    
    all_corrections = {}
    all_stats = {}
    
    for split in splits:
        print(f"\n{'='*60}")
        print(f"Processing {split.upper()} split")
        print('='*60)
        
        corrections, stats = process_split(
            model=model,
            dataset_path=args.dataset,
            feature_cache_dir=args.feature_cache_dir,
            split=split,
            class_names=class_names,
            confidence_threshold=args.confidence_threshold,
            batch_size=args.batch_size,
            device=device,
        )
        
        all_corrections[split] = corrections
        all_stats[split] = stats
        
        # Print summary
        print(f"\n{split.upper()} SUMMARY:")
        print(f"  Total samples: {stats['total_samples']:,}")
        print(f"  Potential mislabels: {stats['total_mislabels']:,} ({100*stats['total_mislabels']/stats['total_samples']:.2f}%)")
        print(f"\n  Top confusion pairs:")
        for (true_cls, pred_cls), count in sorted(stats['confusion_counts'].items(), 
                                                   key=lambda x: -x[1])[:10]:
            print(f"    {true_cls} → {pred_cls}: {count:,}")
    
    if args.dry_run:
        print("\n[DRY RUN] No files saved.")
        return
    
    # Save corrections
    for split, corrections in all_corrections.items():
        if not corrections:
            continue
            
        # Save as JSON for review
        corrections_file = args.output_dir / f"{split}_label_corrections.json"
        with open(corrections_file, 'w') as f:
            json.dump({
                'split': split,
                'confidence_threshold': args.confidence_threshold,
                'total_corrections': len(corrections),
                'corrections': corrections,
            }, f, indent=2)
        print(f"\nSaved: {corrections_file}")
        
        # Save as numpy for fast loading during training
        if corrections:
            indices = np.array([c['index'] for c in corrections], dtype=np.int64)
            old_labels = np.array([c['old_label_idx'] for c in corrections], dtype=np.int32)
            new_labels = np.array([c['new_label_idx'] for c in corrections], dtype=np.int32)
            confidences = np.array([c['confidence'] for c in corrections], dtype=np.float32)
            
            npz_file = args.output_dir / f"{split}_label_corrections.npz"
            np.savez_compressed(
                npz_file,
                indices=indices,
                old_labels=old_labels,
                new_labels=new_labels,
                confidences=confidences,
            )
            print(f"Saved: {npz_file}")
    
    # Save overall statistics
    stats_file = args.output_dir / "label_noise_stats.json"
    with open(stats_file, 'w') as f:
        # Convert tuple keys to strings for JSON
        json_stats = {}
        for split, stats in all_stats.items():
            json_stats[split] = {
                'total_samples': stats['total_samples'],
                'total_mislabels': stats['total_mislabels'],
                'mislabel_rate': stats['total_mislabels'] / stats['total_samples'],
                'confusion_counts': {f"{k[0]}_to_{k[1]}": v for k, v in stats['confusion_counts'].items()},
                'per_class_noise': stats['per_class_noise'],
            }
        json.dump(json_stats, f, indent=2)
    print(f"Saved: {stats_file}")
    
    # Print instructions
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("""
1. REVIEW the corrections (especially high-count pairs):
   - Open label_corrections/{split}_label_corrections.json
   - Spot-check samples to verify model is correct

2. APPLY corrections to your dataset:
   python training/tools/apply_label_corrections.py \\
       --corrections label_corrections/train_label_corrections.npz \\
       --dataset F:/datasets/prod_v5_cleaned \\
       --output F:/datasets/prod_v5_cleaned_fixed

3. RETRAIN with cleaned labels:
   - Expect +2-4% balanced accuracy improvement
   - The model was actually RIGHT on many "wrong" predictions
""")


def process_split(
    model: torch.nn.Module,
    dataset_path: Path,
    feature_cache_dir: Path,
    split: str,
    class_names: List[str],
    confidence_threshold: float,
    batch_size: int,
    device: torch.device,
) -> Tuple[List[Dict], Dict]:
    """Process a single split and return corrections and stats."""
    
    from training.train_classifier import DrumSampleDataset
    
    split_dir = dataset_path / split
    
    # Find labels file
    labels_file = None
    if (split_dir / f"{split}_labels_files.npy").exists():
        labels_file = split_dir / f"{split}_labels.npy"
    elif (split_dir / "labels.json").exists():
        labels_file = split_dir / "labels.json"
    else:
        raise FileNotFoundError(f"No labels file found in {split_dir}")
    
    cache_mapping = split_dir / "cache_mapping.npz"
    if not cache_mapping.exists():
        cache_mapping = None
    
    dataset = DrumSampleDataset(
        data_dir=split_dir,
        labels_file=labels_file,
        cache_dir=feature_cache_dir / split,
        cache_mapping=cache_mapping,
    )
    
    total_samples = len(dataset)
    print(f"Loaded {total_samples:,} samples")
    
    # Get valid indices (samples with cache entries)
    if cache_mapping is not None:
        mapping_data = np.load(cache_mapping, allow_pickle=True)
        valid_mask = mapping_data['valid']
        valid_indices = np.where(valid_mask)[0]
        print(f"Valid cached samples: {len(valid_indices):,}")
    else:
        valid_indices = np.arange(total_samples)
    
    # Load file paths for reporting
    files_npy = split_dir / f"{split}_labels_files.npy"
    if files_npy.exists():
        numpy_files = np.load(files_npy, allow_pickle=True)
    else:
        numpy_files = None
    
    # Create dataloader
    subset = Subset(dataset, valid_indices.tolist())
    loader = DataLoader(
        subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    
    # Run inference
    corrections = []
    confusion_counts = defaultdict(int)
    per_class_noise = defaultdict(lambda: {'total': 0, 'mislabeled': 0})
    
    sample_offset = 0
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(loader, desc=f"Scanning {split}"):
            features, labels = batch
            features = features.to(device)
            labels = labels.numpy()
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            probs = F.softmax(outputs, dim=1).cpu().numpy()
            preds = probs.argmax(axis=1)
            max_probs = probs.max(axis=1)
            
            for i, (label, pred, prob, max_prob) in enumerate(zip(labels, preds, probs, max_probs)):
                global_idx = int(valid_indices[sample_offset + i])
                true_class = class_names[label]
                pred_class = class_names[pred]
                
                per_class_noise[true_class]['total'] += 1
                
                # Check if high-confidence disagreement
                if pred != label and max_prob >= confidence_threshold:
                    per_class_noise[true_class]['mislabeled'] += 1
                    confusion_counts[(true_class, pred_class)] += 1
                    
                    # Get file path
                    if numpy_files is not None:
                        file_path = numpy_files[global_idx]
                        if isinstance(file_path, bytes):
                            file_path = file_path.decode('utf-8')
                    else:
                        file_path = f"sample_{global_idx}"
                    
                    corrections.append({
                        'index': global_idx,
                        'file': str(file_path),
                        'old_label': true_class,
                        'old_label_idx': int(label),
                        'new_label': pred_class,
                        'new_label_idx': int(pred),
                        'confidence': float(max_prob),
                    })
            
            sample_offset += len(labels)
    
    # Compute per-class noise rates
    per_class_noise_rates = {}
    for cls, data in per_class_noise.items():
        if data['total'] > 0:
            per_class_noise_rates[cls] = {
                'total': data['total'],
                'mislabeled': data['mislabeled'],
                'noise_rate': data['mislabeled'] / data['total'],
            }
    
    stats = {
        'total_samples': len(valid_indices),
        'total_mislabels': len(corrections),
        'confusion_counts': dict(confusion_counts),
        'per_class_noise': per_class_noise_rates,
    }
    
    return corrections, stats


if __name__ == "__main__":
    main()
