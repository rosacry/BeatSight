#!/usr/bin/env python3
"""
Export Confused Samples for Manual Review

Exports samples where the model prediction disagrees with labels,
allowing manual review to identify label noise.

Usage:
    python export_confused_samples.py \
        --checkpoint runs/v5_phase2/best_drum_classifier_ema.pth \
        --dataset F:/datasets/prod_v5_cleaned \
        --feature-cache-dir F:/feature_cache \
        --confusion-pair kick hihat_closed \
        --output-dir confused_samples \
        --max-samples 100
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple

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
    parser = argparse.ArgumentParser(description="Export confused samples for review")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--confusion-pair", nargs=2, required=True, 
                        help="e.g., --confusion-pair kick hihat_closed")
    parser.add_argument("--output-dir", type=Path, default=Path("confused_samples"))
    parser.add_argument("--max-samples", type=int, default=100)
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    
    device = torch.device(args.device)
    true_class, pred_class = args.confusion_pair
    
    # Load class names
    components_file = args.dataset / "components.json"
    if components_file.exists():
        with open(components_file, 'r') as f:
            data = json.load(f)
        class_names = data.get("components", [])
    else:
        raise FileNotFoundError(f"components.json not found in {args.dataset}")
    
    if true_class not in class_names:
        raise ValueError(f"Class '{true_class}' not in {class_names}")
    if pred_class not in class_names:
        raise ValueError(f"Class '{pred_class}' not in {class_names}")
    
    true_idx = class_names.index(true_class)
    pred_idx = class_names.index(pred_class)
    num_classes = len(class_names)
    
    print(f"Looking for: {true_class} (label) → {pred_class} (prediction)")
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
    
    # Load dataset
    print("\nLoading validation dataset...")
    from training.train_classifier import DrumSampleDataset
    
    val_dir = args.dataset / "val"
    
    # Find labels file
    labels_file = None
    if (val_dir / "labels.json").exists():
        labels_file = val_dir / "labels.json"
    elif (val_dir / "val_labels_files.npy").exists():
        labels_file = val_dir / "val_labels.npy"
    else:
        raise FileNotFoundError(f"No labels file found in {val_dir}")
    
    cache_mapping = val_dir / "cache_mapping.npz"
    if not cache_mapping.exists():
        cache_mapping = None
    
    val_dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=labels_file,
        cache_dir=args.feature_cache_dir / "val",
        cache_mapping=cache_mapping,
    )
    
    # Filter to only the true class
    print(f"\nFiltering to class '{true_class}'...")
    
    # Get all labels
    if hasattr(val_dataset, '_numpy_labels') and val_dataset._numpy_labels is not None:
        all_labels = val_dataset._numpy_labels[:]
    else:
        all_labels = np.array([val_dataset.labels[i].get('label', -1) for i in range(len(val_dataset))])
    
    # Find indices of true class
    true_class_indices = np.where(all_labels == true_idx)[0]
    print(f"Found {len(true_class_indices):,} samples with label '{true_class}'")
    
    # Filter by valid cache if needed
    if cache_mapping is not None:
        mapping_data = np.load(cache_mapping, allow_pickle=True)
        valid_mask = mapping_data['valid']
        true_class_indices = true_class_indices[valid_mask[true_class_indices]]
        print(f"After cache filter: {len(true_class_indices):,} samples")
    
    # Create subset
    val_subset = Subset(val_dataset, true_class_indices.tolist())
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )
    
    # Find confused samples
    print(f"\nFinding samples predicted as '{pred_class}'...")
    confused_indices = []
    confused_confidences = []
    
    sample_offset = 0
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(val_loader, desc="Scanning"):
            features, labels = batch
            features = features.to(device)
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            probs = F.softmax(outputs, dim=1)
            preds = outputs.argmax(dim=1)
            
            # Find where prediction == pred_class
            for i, (pred, prob) in enumerate(zip(preds, probs)):
                if pred.item() == pred_idx:
                    global_idx = true_class_indices[sample_offset + i]
                    confidence = prob[pred_idx].item()
                    confused_indices.append(int(global_idx))
                    confused_confidences.append(confidence)
            
            sample_offset += len(labels)
    
    print(f"\nFound {len(confused_indices):,} confused samples")
    
    if len(confused_indices) == 0:
        print("No confused samples found!")
        return
    
    # Sort by confidence (highest first = model is most sure it's wrong)
    sorted_pairs = sorted(zip(confused_indices, confused_confidences), 
                          key=lambda x: x[1], reverse=True)
    
    # Export top N
    args.output_dir.mkdir(parents=True, exist_ok=True)
    export_count = min(args.max_samples, len(sorted_pairs))
    
    # Get file paths - need to load the files array directly since dataset may have skipped it
    print(f"\nExporting top {export_count} samples...")
    export_data = []
    
    # Load files array directly from numpy
    files_npy = val_dir / "val_labels_files.npy"
    if files_npy.exists():
        print(f"Loading file paths from {files_npy}...")
        numpy_files = np.load(files_npy, allow_pickle=True)
    else:
        numpy_files = None
    
    for i, (idx, conf) in enumerate(sorted_pairs[:export_count]):
        if numpy_files is not None:
            file_path = numpy_files[idx]
            if isinstance(file_path, bytes):
                file_path = file_path.decode('utf-8')
        elif hasattr(val_dataset, '_numpy_files') and val_dataset._numpy_files is not None:
            file_path = val_dataset._numpy_files[idx]
            if isinstance(file_path, bytes):
                file_path = file_path.decode('utf-8')
        else:
            file_path = f'sample_{idx}'
        
        export_data.append({
            'index': idx,
            'file': str(file_path),
            'label': true_class,
            'predicted': pred_class,
            'confidence': round(conf, 4),
        })
    
    # Save manifest
    manifest_path = args.output_dir / f"{true_class}_to_{pred_class}_confused.json"
    with open(manifest_path, 'w') as f:
        json.dump({
            'confusion_pair': [true_class, pred_class],
            'total_confused': len(confused_indices),
            'exported': export_count,
            'samples': export_data,
        }, f, indent=2)
    
    print(f"\nExported to: {manifest_path}")
    print(f"\nTop 10 most confident confusions:")
    print("-" * 80)
    for item in export_data[:10]:
        print(f"  [{item['confidence']*100:.1f}%] {item['file']}")
    
    print(f"\n💡 Review these samples - if many are mislabeled, consider:")
    print(f"   1. Relabeling in your dataset")
    print(f"   2. Adding them to a 'noisy' exclusion list")
    print(f"   3. Using label smoothing or noise-robust loss")


if __name__ == "__main__":
    main()
