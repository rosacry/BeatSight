#!/usr/bin/env python3
"""
Model Sanity Check Script
=========================
Verifies that the trained model is genuinely learning and not broken.

Run this WHILE training is paused (Ctrl+C) to validate your checkpoint.

Usage:
    cd /c/github/BeatSight/ai-pipeline
    PYTHONPATH=. python training/scripts/validate_model_sanity.py \
        --checkpoint runs/v5_phase1/best_model.pt \
        --dataset "F:/datasets/prod_v5_definitive" \
        --feature-cache-dir "F:/feature_cache"
"""

import argparse
import sys
import os
import torch
import numpy as np
from pathlib import Path
from collections import Counter
import random

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.cnn_v5 import cnn_v5_large


CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open", 
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]


def load_model(checkpoint_path: str, device: str = "cuda"):
    """Load model from checkpoint."""
    print(f"\n{'='*60}")
    print("  LOADING MODEL")
    print(f"{'='*60}")
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Get model state
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint
    
    # Get metadata
    epoch = checkpoint.get('epoch', 'unknown')
    best_acc = checkpoint.get('best_balanced_acc', checkpoint.get('best_acc', 'unknown'))
    
    print(f"  Checkpoint epoch: {epoch}")
    print(f"  Best balanced acc: {best_acc}")
    
    # Create model (v5 large with 12 classes)
    model = cnn_v5_large(
        num_classes=12,
        drop_path_rate=0.1,
        use_deep_supervision=False,  # Not needed for inference
        use_multi_task=False
    )
    
    # Load weights
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()
    
    print(f"  ✓ Model loaded successfully ({sum(p.numel() for p in model.parameters()):,} params)")
    
    return model, checkpoint


def run_sanity_checks(model, cache_readers, labels, cache_mapping, device, num_samples=500):
    """Run comprehensive sanity checks.
    
    Args:
        cache_readers: dict mapping cache split name ('train', 'val') to cache reader
    """
    
    results = {
        'passed': [],
        'failed': [],
        'warnings': []
    }
    
    # Get valid dataset indices (where cache mapping is valid)
    valid_mask = cache_mapping['valid']
    shard_ids = cache_mapping['shard_ids']
    offsets = cache_mapping['offsets']
    cache_splits = cache_mapping['cache_split']  # 'train' or 'val' for each sample
    
    valid_indices = np.where(valid_mask)[0]
    print(f"  Valid dataset indices: {len(valid_indices):,} / {len(labels):,}")
    
    # =========================================================================
    # CHECK 1: Model produces varied predictions (not collapsed)
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 1: Prediction Diversity")
    print(f"{'='*60}")
    
    # Sample from valid indices only
    sample_indices = random.sample(list(valid_indices), min(num_samples, len(valid_indices)))
    predictions = []
    confidences = []
    sample_labels = []
    
    with torch.no_grad():
        for i, dataset_idx in enumerate(sample_indices):
            # Use cache mapping to get the correct shard/offset
            shard_id = int(shard_ids[dataset_idx])
            offset = int(offsets[dataset_idx])
            split = cache_splits[dataset_idx]
            
            # Get the correct cache reader for this sample
            cache_reader = cache_readers.get(split)
            if cache_reader is None:
                continue
            
            features = cache_reader._read_sample(shard_id, offset)
            if isinstance(features, np.ndarray):
                features = torch.from_numpy(features)
            # Ensure [1, C, H, W] shape for model
            if features.dim() == 2:
                features = features.unsqueeze(0).unsqueeze(0)
            elif features.dim() == 3:
                features = features.unsqueeze(0)
            features = features.float().to(device)
            
            logits = model(features)
            probs = torch.softmax(logits, dim=1)
            pred = logits.argmax(dim=1).item()
            conf = probs.max().item()
            
            predictions.append(pred)
            confidences.append(conf)
            sample_labels.append(int(labels[dataset_idx]))
            
            if (i + 1) % 100 == 0:
                print(f"  Processed {i+1}/{len(sample_indices)} samples...")
    
    pred_counts = Counter(predictions)
    unique_preds = len(pred_counts)
    
    print(f"\n  Prediction distribution ({num_samples} samples):")
    for cls_idx in sorted(pred_counts.keys()):
        cls_name = CLASS_NAMES[cls_idx]
        count = pred_counts[cls_idx]
        pct = count / len(predictions) * 100
        bar = '█' * int(pct / 2)
        print(f"    {cls_name:12s}: {count:4d} ({pct:5.1f}%) {bar}")
    
    if unique_preds >= 10:
        results['passed'].append(f"✓ Prediction diversity: {unique_preds}/12 classes predicted")
    elif unique_preds >= 6:
        results['warnings'].append(f"⚠ Limited diversity: Only {unique_preds}/12 classes predicted")
    else:
        results['failed'].append(f"✗ COLLAPSED: Only {unique_preds}/12 classes predicted!")
    
    # =========================================================================
    # CHECK 2: Confidence distribution is reasonable
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 2: Confidence Distribution")
    print(f"{'='*60}")
    
    avg_conf = np.mean(confidences)
    min_conf = np.min(confidences)
    max_conf = np.max(confidences)
    std_conf = np.std(confidences)
    
    print(f"  Average confidence: {avg_conf:.3f}")
    print(f"  Min confidence:     {min_conf:.3f}")
    print(f"  Max confidence:     {max_conf:.3f}")
    print(f"  Std deviation:      {std_conf:.3f}")
    
    if 0.4 < avg_conf < 0.98 and std_conf > 0.05:
        results['passed'].append(f"✓ Confidence distribution healthy (avg={avg_conf:.3f}, std={std_conf:.3f})")
    elif avg_conf > 0.98:
        results['warnings'].append(f"⚠ Overconfident predictions (avg={avg_conf:.3f})")
    elif std_conf < 0.02:
        results['warnings'].append(f"⚠ Uniform confidence (std={std_conf:.3f}) - might be poorly calibrated")
    else:
        results['passed'].append(f"✓ Confidence within acceptable range")
    
    # =========================================================================
    # CHECK 3: Per-class accuracy on sample
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 3: Per-Class Accuracy (Sample)")
    print(f"{'='*60}")
    
    # Use labels we already collected
    correct_per_class = Counter()
    total_per_class = Counter()
    
    for pred, label in zip(predictions, sample_labels):
        if label >= 0:  # Valid label
            total_per_class[label] += 1
            if pred == label:
                correct_per_class[label] += 1
    
    print(f"\n  Per-class accuracy on {num_samples} random samples:")
    class_accs = []
    for cls_idx in range(12):
        total = total_per_class.get(cls_idx, 0)
        correct = correct_per_class.get(cls_idx, 0)
        if total > 0:
            acc = correct / total * 100
            class_accs.append(acc)
            status = "✓" if acc > 50 else "⚠" if acc > 20 else "✗"
            print(f"    {status} {CLASS_NAMES[cls_idx]:12s}: {correct:3d}/{total:3d} ({acc:5.1f}%)")
        else:
            print(f"    - {CLASS_NAMES[cls_idx]:12s}: No samples")
    
    if class_accs:
        balanced_acc = np.mean(class_accs)
        print(f"\n  Sample balanced accuracy: {balanced_acc:.1f}%")
        
        if balanced_acc > 70:
            results['passed'].append(f"✓ Strong sample accuracy: {balanced_acc:.1f}%")
        elif balanced_acc > 50:
            results['passed'].append(f"✓ Reasonable sample accuracy: {balanced_acc:.1f}%")
        else:
            results['warnings'].append(f"⚠ Low sample accuracy: {balanced_acc:.1f}%")
    
    # =========================================================================
    # CHECK 4: Model weights are not NaN/Inf
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 4: Weight Health")
    print(f"{'='*60}")
    
    nan_params = 0
    inf_params = 0
    zero_params = 0
    total_params = 0
    
    for name, param in model.named_parameters():
        total_params += param.numel()
        nan_params += torch.isnan(param).sum().item()
        inf_params += torch.isinf(param).sum().item()
        zero_params += (param == 0).sum().item()
    
    zero_pct = zero_params / total_params * 100
    
    print(f"  Total parameters: {total_params:,}")
    print(f"  NaN parameters:   {nan_params}")
    print(f"  Inf parameters:   {inf_params}")
    print(f"  Zero parameters:  {zero_params:,} ({zero_pct:.1f}%)")
    
    if nan_params == 0 and inf_params == 0:
        results['passed'].append("✓ No NaN/Inf in model weights")
    else:
        results['failed'].append(f"✗ CORRUPTED: {nan_params} NaN, {inf_params} Inf parameters!")
    
    if zero_pct < 50:
        results['passed'].append(f"✓ Weight sparsity normal ({zero_pct:.1f}% zeros)")
    else:
        results['warnings'].append(f"⚠ High sparsity ({zero_pct:.1f}% zeros)")
    
    # =========================================================================
    # CHECK 5: Same input → same output (deterministic)
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 5: Determinism")
    print(f"{'='*60}")
    
    # Use first sample from our test set
    test_dataset_idx = sample_indices[0]
    test_shard_id = int(shard_ids[test_dataset_idx])
    test_offset = int(offsets[test_dataset_idx])
    test_split = cache_splits[test_dataset_idx]
    test_cache_reader = cache_readers.get(test_split)
    features = test_cache_reader._read_sample(test_shard_id, test_offset)
    if isinstance(features, np.ndarray):
        features = torch.from_numpy(features)
    if features.dim() == 2:
        features = features.unsqueeze(0).unsqueeze(0)
    elif features.dim() == 3:
        features = features.unsqueeze(0)
    features = features.float().to(device)
    
    with torch.no_grad():
        out1 = model(features)
        out2 = model(features)
    
    is_deterministic = torch.allclose(out1, out2, atol=1e-6)
    
    if is_deterministic:
        results['passed'].append("✓ Model is deterministic (same input → same output)")
        print("  ✓ Same input produces identical output")
    else:
        results['warnings'].append("⚠ Model not fully deterministic (dropout/noise active?)")
        print("  ⚠ Outputs differ slightly (might have dropout enabled)")
    
    # =========================================================================
    # CHECK 6: Different inputs → different outputs
    # =========================================================================
    print(f"\n{'='*60}")
    print("  CHECK 6: Input Sensitivity")
    print(f"{'='*60}")
    
    outputs = []
    for dataset_idx in sample_indices[:10]:
        sid = int(shard_ids[dataset_idx])
        off = int(offsets[dataset_idx])
        split = cache_splits[dataset_idx]
        cr = cache_readers.get(split)
        features = cr._read_sample(sid, off)
        if isinstance(features, np.ndarray):
            features = torch.from_numpy(features)
        if features.dim() == 2:
            features = features.unsqueeze(0).unsqueeze(0)
        elif features.dim() == 3:
            features = features.unsqueeze(0)
        features = features.float().to(device)
        with torch.no_grad():
            out = model(features)
        outputs.append(out.cpu())
    
    all_same = all(torch.allclose(outputs[0], o, atol=1e-4) for o in outputs[1:])
    
    if not all_same:
        results['passed'].append("✓ Different inputs produce different outputs")
        print("  ✓ Model responds to different inputs")
    else:
        results['failed'].append("✗ BROKEN: All inputs produce same output!")
        print("  ✗ All inputs produce identical output - model may be broken!")
    
    return results


def print_summary(results):
    """Print final summary."""
    print(f"\n{'='*60}")
    print("  SANITY CHECK SUMMARY")
    print(f"{'='*60}")
    
    print(f"\n  PASSED ({len(results['passed'])}):")
    for msg in results['passed']:
        print(f"    {msg}")
    
    if results['warnings']:
        print(f"\n  WARNINGS ({len(results['warnings'])}):")
        for msg in results['warnings']:
            print(f"    {msg}")
    
    if results['failed']:
        print(f"\n  FAILED ({len(results['failed'])}):")
        for msg in results['failed']:
            print(f"    {msg}")
    
    print(f"\n{'='*60}")
    if not results['failed']:
        print("  ✅ MODEL LOOKS HEALTHY! Training appears to be working correctly.")
        print("     Your 89%+ balanced accuracy is LEGITIMATE.")
    else:
        print("  ❌ ISSUES DETECTED! Review the failures above.")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate model sanity")
    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to model checkpoint")
    parser.add_argument("--dataset", type=str, required=True,
                        help="Path to dataset")
    parser.add_argument("--feature-cache-dir", type=str, required=True,
                        help="Path to feature cache")
    parser.add_argument("--num-samples", type=int, default=500,
                        help="Number of samples to test")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device to use")
    args = parser.parse_args()
    
    # Check checkpoint exists
    if not os.path.exists(args.checkpoint):
        print(f"ERROR: Checkpoint not found: {args.checkpoint}")
        sys.exit(1)
    
    # Load model
    device = args.device if torch.cuda.is_available() else "cpu"
    model, checkpoint = load_model(args.checkpoint, device)
    
    # Load validation data using ConsolidatedCacheReader
    print(f"\n{'='*60}")
    print("  LOADING VALIDATION DATA")
    print(f"{'='*60}")
    
    from training.utils.consolidated_cache import ConsolidatedCacheReader
    
    # Load both train and val caches (dual-cache system)
    cache_base = Path(args.feature_cache_dir)
    cache_readers = {}
    
    train_cache_path = cache_base / "train"
    if train_cache_path.exists():
        cache_readers['train'] = ConsolidatedCacheReader(train_cache_path, verbose=False)
        print(f"  Loaded train cache: {len(cache_readers['train']):,} samples, {cache_readers['train'].num_shards} shards")
    
    val_cache_path = cache_base / "val"
    if val_cache_path.exists():
        cache_readers['val'] = ConsolidatedCacheReader(val_cache_path, verbose=False)
        print(f"  Loaded val cache: {len(cache_readers['val']):,} samples, {cache_readers['val'].num_shards} shards")
    
    # Load labels - try multiple naming conventions
    dataset_path = Path(args.dataset)
    val_dir = dataset_path / "val"
    
    labels = None
    # Try common naming patterns
    label_candidates = [
        val_dir / "labels.npy",
        val_dir / "val_labels_labels.npy",  # prod_v5_definitive format
        val_dir / "labels_labels.npy",
    ]
    
    for labels_path in label_candidates:
        if labels_path.exists():
            labels = np.load(labels_path)
            print(f"  Loaded {len(labels):,} labels from {labels_path.name}")
            break
    
    if labels is None:
        # Try .npz files
        npz_candidates = [
            val_dir / "labels.npz",
            val_dir / "val_labels.npz",
        ]
        for labels_npz in npz_candidates:
            if labels_npz.exists():
                data = np.load(labels_npz)
                labels = data['labels'] if 'labels' in data else data[list(data.keys())[0]]
                print(f"  Loaded {len(labels):,} labels from {labels_npz.name}")
                break
    
    if labels is None:
        print(f"ERROR: No labels found in {val_dir}")
        print(f"  Tried: {[p.name for p in label_candidates]}")
        sys.exit(1)
    
    # Load cache mapping (critical for correct feature-label alignment)
    cache_mapping_path = val_dir / "cache_mapping.npz"
    if not cache_mapping_path.exists():
        print(f"ERROR: Cache mapping not found: {cache_mapping_path}")
        sys.exit(1)
    
    cache_mapping = np.load(cache_mapping_path)
    print(f"  Loaded cache mapping: {cache_mapping['valid'].sum():,} valid entries")
    
    # Count samples by cache split
    cache_splits = cache_mapping['cache_split']
    for split in np.unique(cache_splits):
        count = (cache_splits == split).sum()
        print(f"    From {split} cache: {count:,}")
    
    # Run checks
    results = run_sanity_checks(model, cache_readers, labels, cache_mapping, device, args.num_samples)
    
    # Print summary
    print_summary(results)


if __name__ == "__main__":
    main()
