#!/usr/bin/env python3
"""
Force-correct specific confusion pairs regardless of confidence.

Based on manual review showing >90% of kick→hihat_closed and snare→hihat_closed
predictions are actually mislabeled hi-hats, this tool corrects ALL such predictions
regardless of model confidence.

Usage:
    python training/tools/force_correct_hihat_pairs.py \
        --checkpoint runs/v5_phase2/best_drum_classifier_ema.pth \
        --input-dataset F:/datasets/prod_v5_fixed_60pct \
        --output-dataset F:/datasets/prod_v5_final \
        --feature-cache-dir F:/feature_cache
"""

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm

# Add ai-pipeline to path
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))


# Pairs to force-correct: (original_label, predicted_label)
# If model predicts hihat_closed for a sample labeled kick/snare, correct it
FORCE_CORRECT_PAIRS = [
    ("kick", "hihat_closed"),
    ("snare", "hihat_closed"),
]


def main():
    parser = argparse.ArgumentParser(description="Force-correct hi-hat confusion pairs")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--input-dataset", type=Path, required=True)
    parser.add_argument("--output-dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--v5-size", default="large", choices=["small", "medium", "large"])
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--min-confidence", type=float, default=0.0,
                        help="Minimum confidence for correction (default 0 = correct all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't save, just report")
    args = parser.parse_args()
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load class names
    components_file = args.input_dataset / "components.json"
    with open(components_file, 'r') as f:
        data = json.load(f)
    class_names = data.get("components", [])
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")
    
    # Build correction pair indices
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    correction_pairs = set()
    for orig_label, pred_label in FORCE_CORRECT_PAIRS:
        if orig_label in class_to_idx and pred_label in class_to_idx:
            correction_pairs.add((class_to_idx[orig_label], class_to_idx[pred_label]))
            print(f"Will correct: {orig_label} → {pred_label}")
    
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
    all_corrections = {}
    
    for split in ["train", "val"]:
        print(f"\n{'='*60}")
        print(f"Processing {split.upper()} split")
        print('='*60)
        
        corrections = process_split(
            model=model,
            dataset_path=args.input_dataset,
            feature_cache_dir=args.feature_cache_dir,
            split=split,
            class_names=class_names,
            correction_pairs=correction_pairs,
            min_confidence=args.min_confidence,
            batch_size=args.batch_size,
            device=device,
        )
        
        all_corrections[split] = corrections
        
        print(f"\n{split.upper()} CORRECTIONS:")
        print(f"  Total corrections: {len(corrections):,}")
        
        # Breakdown by pair
        pair_counts = defaultdict(int)
        for c in corrections:
            pair_counts[(c['old_label'], c['new_label'])] += 1
        
        for (old, new), count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            print(f"    {old} → {new}: {count:,}")
    
    if args.dry_run:
        print("\n[DRY RUN] No files saved.")
        total = sum(len(c) for c in all_corrections.values())
        print(f"\nWould apply {total:,} force corrections")
        return
    
    # Create output dataset
    print(f"\n{'='*60}")
    print("APPLYING CORRECTIONS")
    print('='*60)
    
    args.output_dataset.mkdir(parents=True, exist_ok=True)
    
    # Copy components.json
    shutil.copy(components_file, args.output_dataset / "components.json")
    print("Copied components.json")
    
    total_corrections = 0
    
    for split in ["train", "val"]:
        corrections = all_corrections[split]
        if not corrections:
            continue
        
        print(f"\nProcessing {split}...")
        print(f"  Corrections to apply: {len(corrections):,}")
        
        # Create output directory
        out_split_dir = args.output_dataset / split
        out_split_dir.mkdir(parents=True, exist_ok=True)
        
        # Load original labels
        in_split_dir = args.input_dataset / split
        labels_file = in_split_dir / f"{split}_labels_labels.npy"
        labels = np.load(labels_file)
        print(f"  Loaded {len(labels):,} labels")
        
        # Apply corrections
        correction_map = {c['index']: c['new_label_idx'] for c in corrections}
        corrected = 0
        for idx, new_label in correction_map.items():
            if idx < len(labels):
                labels[idx] = new_label
                corrected += 1
        
        print(f"  Applied {corrected:,} corrections")
        total_corrections += corrected
        
        # Save corrected labels
        np.save(out_split_dir / f"{split}_labels_labels.npy", labels)
        print(f"  Saved: {out_split_dir / f'{split}_labels_labels.npy'}")
        
        # Copy other files
        files_npy = in_split_dir / f"{split}_labels_files.npy"
        if files_npy.exists():
            shutil.copy(files_npy, out_split_dir / f"{split}_labels_files.npy")
            print(f"  Copied files array")
        
        cache_mapping = in_split_dir / "cache_mapping.npz"
        if cache_mapping.exists():
            shutil.copy(cache_mapping, out_split_dir / "cache_mapping.npz")
            print(f"  Copied cache mapping")
    
    # Save correction stats
    stats = {
        "total_corrections": total_corrections,
        "min_confidence": args.min_confidence,
        "pairs_corrected": [f"{p[0]}→{p[1]}" for p in FORCE_CORRECT_PAIRS],
        "per_split": {split: len(corr) for split, corr in all_corrections.items()},
    }
    
    with open(args.output_dataset / "force_correction_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n{'='*60}")
    print("COMPLETE")
    print('='*60)
    print(f"Total force corrections applied: {total_corrections:,}")
    print(f"Output dataset: {args.output_dataset}")
    
    print("\nNext: Re-evaluate the confusion ceiling:")
    print(f"  python training/tools/analyze_confusion_ceiling.py \\")
    print(f"      --checkpoint {args.checkpoint} \\")
    print(f"      --dataset {args.output_dataset} \\")
    print(f"      --feature-cache-dir {args.feature_cache_dir}")


def process_split(
    model: torch.nn.Module,
    dataset_path: Path,
    feature_cache_dir: Path,
    split: str,
    class_names: list,
    correction_pairs: set,
    min_confidence: float,
    batch_size: int,
    device: torch.device,
):
    """Process a split and find all samples matching correction pairs."""
    
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
    
    # Get valid indices
    if cache_mapping is not None:
        mapping_data = np.load(cache_mapping, allow_pickle=True)
        valid_mask = mapping_data['valid']
        valid_indices = np.where(valid_mask)[0]
        print(f"Valid cached samples: {len(valid_indices):,}")
    else:
        valid_indices = np.arange(total_samples)
    
    # Create dataloader
    subset = Subset(dataset, valid_indices.tolist())
    loader = DataLoader(
        subset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )
    
    # Find all samples to correct
    corrections = []
    sample_offset = 0
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(loader, desc=f"Scanning {split}"):
            features, labels = batch
            features = features.to(device)
            labels_np = labels.numpy()
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            probs = F.softmax(outputs, dim=1).cpu().numpy()
            preds = probs.argmax(axis=1)
            max_probs = probs.max(axis=1)
            
            for i, (label, pred, max_prob) in enumerate(zip(labels_np, preds, max_probs)):
                global_idx = int(valid_indices[sample_offset + i])
                
                # Check if this matches a correction pair
                if (label, pred) in correction_pairs and max_prob >= min_confidence:
                    corrections.append({
                        'index': global_idx,
                        'old_label': class_names[label],
                        'old_label_idx': int(label),
                        'new_label': class_names[pred],
                        'new_label_idx': int(pred),
                        'confidence': float(max_prob),
                    })
            
            sample_offset += len(labels_np)
    
    return corrections


if __name__ == "__main__":
    main()
