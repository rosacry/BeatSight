#!/usr/bin/env python3
"""
Diagnose why class_18 (splash) has 0% validation accuracy.

This script investigates potential causes:
1. Train vs Val distribution mismatch
2. Confusion matrix - what is class_18 being predicted as?
3. Logit/probability distributions for class_18 samples
4. Feature similarity to other classes

Usage:
    python diagnose_class_18.py --checkpoint runs/v5_production_*/checkpoints/latest_checkpoint.pth
"""

import argparse
import sys
from pathlib import Path
from collections import Counter

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

# Add ai-pipeline to path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRUM_CLASSES = [
    "aux_percussion", "china", "crash", "cross_stick", "cymbal_choke",
    "hihat_closed", "hihat_foot_splash", "hihat_open", "hihat_pedal", "hihat_splash",
    "kick", "ride_bell", "ride_bow", "rimshot", "snare",
    "snare_center", "snare_cross_stick", "snare_rimshot", "splash", "tom_high", "tom_low"
]

TARGET_CLASS = 18  # splash
TARGET_NAME = DRUM_CLASSES[TARGET_CLASS]


def load_model(checkpoint_path: Path, device: torch.device):
    """Load model from checkpoint."""
    from training.models.cnn_v5 import cnn_v5_large
    
    num_classes = len(DRUM_CLASSES)
    model = cnn_v5_large(num_classes=num_classes, drop_path_rate=0.0)
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    if isinstance(checkpoint, dict):
        if "model_state" in checkpoint:
            state_dict = checkpoint["model_state"]
        elif "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint
    else:
        state_dict = checkpoint
    
    # Remove _orig_mod. prefix if present
    state_dict = {k.replace("_orig_mod.", ""): v for k, v in state_dict.items()}
    
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()
    return model


class SimpleNumpyDataset(Dataset):
    """Simple dataset that loads from numpy labels and consolidated cache."""
    
    def __init__(self, labels_dir: Path, cache_dir: Path, split: str = "val"):
        self.labels_dir = labels_dir
        self.cache_dir = cache_dir
        self.split = split
        
        # Load labels
        labels_file = labels_dir / f"{split}_labels_with_velocity_labels.npy"
        if not labels_file.exists():
            # Try alternate naming
            labels_file = labels_dir / f"{split}_labels.npy"
        
        print(f"  Loading labels from: {labels_file}")
        self.labels = np.load(labels_file, mmap_mode='r')
        print(f"  Loaded {len(self.labels):,} labels")
        
        # Load consolidated cache
        self.shards = []
        self.shard_offsets = [0]
        
        shard_idx = 0
        while True:
            shard_path = cache_dir / f"{split}_shard_{shard_idx:04d}.pt"
            if not shard_path.exists():
                break
            self.shards.append(shard_path)
            # We'll load lazily
            shard_idx += 1
        
        if not self.shards:
            raise FileNotFoundError(f"No shards found in {cache_dir} for split {split}")
        
        print(f"  Found {len(self.shards)} cache shards")
        
        # Load shard info to get offsets
        self._loaded_shards = {}
        self._build_shard_index()
    
    def _build_shard_index(self):
        """Build index mapping sample idx -> (shard_idx, offset_in_shard)."""
        # Load cache mapping if available
        mapping_file = self.labels_dir / f"{self.split}_cache_mapping.npz"
        if mapping_file.exists():
            mapping = np.load(mapping_file)
            self.shard_indices = mapping['shard_indices']
            self.offsets_in_shard = mapping['offsets_in_shard']
            print(f"  Loaded cache mapping for {len(self.shard_indices):,} samples")
        else:
            # Fallback: assume sequential
            print(f"  [WARN] No cache mapping found, assuming sequential order")
            self.shard_indices = None
            self.offsets_in_shard = None
    
    def _load_shard(self, shard_idx: int) -> torch.Tensor:
        """Load a shard into memory (cached)."""
        if shard_idx not in self._loaded_shards:
            shard_path = self.shards[shard_idx]
            self._loaded_shards[shard_idx] = torch.load(shard_path, weights_only=True)
            # Keep only last 3 shards in memory
            if len(self._loaded_shards) > 3:
                oldest = min(self._loaded_shards.keys())
                del self._loaded_shards[oldest]
        return self._loaded_shards[shard_idx]
    
    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        label = int(self.labels[idx])
        
        if self.shard_indices is not None:
            shard_idx = int(self.shard_indices[idx])
            offset = int(self.offsets_in_shard[idx])
        else:
            # Fallback: compute from idx (assumes ~65536 samples per shard)
            samples_per_shard = 65536
            shard_idx = idx // samples_per_shard
            offset = idx % samples_per_shard
        
        try:
            shard_data = self._load_shard(shard_idx)
            features = shard_data[offset]
        except Exception as e:
            # Return zeros if loading fails
            features = torch.zeros(1, 128, 44)
        
        return features, label


def load_labels_only(data_root: Path):
    """Load just the label arrays for distribution analysis."""
    labels_dir = data_root / "dataset_index"
    
    train_labels_file = labels_dir / "train_labels_with_velocity_labels.npy"
    val_labels_file = labels_dir / "val_labels_with_velocity_labels.npy"
    
    if not train_labels_file.exists():
        train_labels_file = labels_dir / "train_labels.npy"
    if not val_labels_file.exists():
        val_labels_file = labels_dir / "val_labels.npy"
    
    print(f"  Loading train labels: {train_labels_file}")
    train_labels = np.load(train_labels_file, mmap_mode='r')
    
    print(f"  Loading val labels: {val_labels_file}")
    val_labels = np.load(val_labels_file, mmap_mode='r')
    
    return train_labels, val_labels


def analyze_class_distribution(train_labels, val_labels):
    """Compare class distribution between train and val."""
    print("\n" + "=" * 70)
    print(f"  1. CLASS DISTRIBUTION ANALYSIS")
    print("=" * 70)
    
    train_counts = Counter(train_labels.tolist() if isinstance(train_labels, np.ndarray) else train_labels)
    val_counts = Counter(val_labels.tolist() if isinstance(val_labels, np.ndarray) else val_labels)
    
    print(f"\n  Class {TARGET_CLASS} ({TARGET_NAME}):")
    print(f"    Train samples: {train_counts.get(TARGET_CLASS, 0):,}")
    print(f"    Val samples:   {val_counts.get(TARGET_CLASS, 0):,}")
    
    train_total = sum(train_counts.values())
    val_total = sum(val_counts.values())
    
    train_pct = 100 * train_counts.get(TARGET_CLASS, 0) / train_total
    val_pct = 100 * val_counts.get(TARGET_CLASS, 0) / val_total
    
    print(f"    Train %: {train_pct:.4f}%")
    print(f"    Val %:   {val_pct:.4f}%")
    
    # Check for severe imbalance
    if abs(train_pct - val_pct) > 0.5:
        print(f"\n  [WARNING] Significant train/val distribution mismatch!")
        print(f"    Difference: {abs(train_pct - val_pct):.4f}%")
    else:
        print(f"\n  [OK] Train/val distribution similar (diff: {abs(train_pct - val_pct):.4f}%)")
    
    # Show similar classes (cymbals)
    print(f"\n  Related cymbal classes for comparison:")
    cymbal_classes = [1, 2, 4, 18]  # china, crash, cymbal_choke, splash
    for idx in cymbal_classes:
        print(f"    {DRUM_CLASSES[idx]:20s}: train={train_counts.get(idx, 0):>8,}, val={val_counts.get(idx, 0):>6,}")
    
    # Show all classes
    print(f"\n  All classes distribution:")
    for idx in range(len(DRUM_CLASSES)):
        marker = ">>>" if idx == TARGET_CLASS else "   "
        print(f"  {marker} {DRUM_CLASSES[idx]:20s} (class {idx:2d}): train={train_counts.get(idx, 0):>8,}, val={val_counts.get(idx, 0):>6,}")


def analyze_predictions_simple(model, val_labels, data_root: Path, device, max_samples=2000):
    """Analyze model predictions for class_18 samples using simple loading."""
    print("\n" + "=" * 70)
    print(f"  2. PREDICTION ANALYSIS FOR CLASS {TARGET_CLASS} ({TARGET_NAME})")
    print("=" * 70)
    
    # Find class_18 sample indices
    target_indices = np.where(val_labels == TARGET_CLASS)[0]
    
    if len(target_indices) == 0:
        print(f"  [ERROR] No samples of class {TARGET_CLASS} found in validation set!")
        return
    
    print(f"\n  Found {len(target_indices):,} validation samples of class {TARGET_CLASS}")
    
    # Try to load the dataset
    try:
        labels_dir = data_root / "dataset_index"
        cache_dir = data_root / "feature_cache" / "prod_combined_warmup_consolidated"
        
        dataset = SimpleNumpyDataset(labels_dir, cache_dir, split="val")
    except Exception as e:
        print(f"  [ERROR] Could not load dataset: {e}")
        print("  Skipping prediction analysis (labels-only mode)")
        return
    
    # Subsample
    if len(target_indices) > max_samples:
        target_indices = np.random.choice(target_indices, max_samples, replace=False)
        print(f"  Analyzing {len(target_indices):,} samples (subsampled)")
    
    # Create subset loader
    from torch.utils.data import Subset
    target_subset = Subset(dataset, target_indices.tolist())
    loader = DataLoader(target_subset, batch_size=128, shuffle=False, num_workers=0)
    
    all_preds = []
    all_probs = []
    all_logits = []
    
    with torch.no_grad():
        for batch in tqdm(loader, desc="Analyzing class_18", leave=False):
            inputs = batch[0].to(device)
            
            logits = model(inputs)
            probs = F.softmax(logits, dim=1)
            preds = logits.argmax(dim=1)
            
            all_preds.extend(preds.cpu().numpy())
            all_probs.append(probs.cpu().numpy())
            all_logits.append(logits.cpu().numpy())
    
    all_preds = np.array(all_preds)
    all_probs = np.concatenate(all_probs, axis=0)
    all_logits = np.concatenate(all_logits, axis=0)
    
    # Accuracy for this class
    accuracy = 100 * (all_preds == TARGET_CLASS).mean()
    print(f"\n  Accuracy on class {TARGET_CLASS} ({TARGET_NAME}): {accuracy:.2f}%")
    
    # Confusion: What does the model predict instead?
    print(f"\n  What is class {TARGET_CLASS} ({TARGET_NAME}) being confused with?")
    pred_counts = Counter(all_preds)
    for pred_class, count in pred_counts.most_common(10):
        pct = 100 * count / len(all_preds)
        marker = "✓" if pred_class == TARGET_CLASS else "✗"
        print(f"    {marker} {DRUM_CLASSES[pred_class]:20s} (class {pred_class:2d}): {count:5d} ({pct:5.1f}%)")
    
    # Probability analysis
    print(f"\n  Probability statistics for class {TARGET_CLASS} on its own samples:")
    target_probs = all_probs[:, TARGET_CLASS]
    print(f"    Mean prob:   {target_probs.mean():.4f}")
    print(f"    Median prob: {np.median(target_probs):.4f}")
    print(f"    Max prob:    {target_probs.max():.4f}")
    print(f"    Min prob:    {target_probs.min():.6f}")
    print(f"    Std prob:    {target_probs.std():.4f}")
    
    # How often is class_18 in top-3?
    top3_preds = np.argsort(all_probs, axis=1)[:, -3:]
    in_top3 = np.any(top3_preds == TARGET_CLASS, axis=1).mean()
    print(f"    In top-3:    {100*in_top3:.1f}%")
    
    # Logit analysis
    print(f"\n  Logit statistics for class {TARGET_CLASS} on its own samples:")
    target_logits = all_logits[:, TARGET_CLASS]
    print(f"    Mean logit:  {target_logits.mean():.4f}")
    print(f"    Max logit:   {target_logits.max():.4f}")
    print(f"    Min logit:   {target_logits.min():.4f}")
    
    # Compare to top confused class
    if pred_counts.most_common(1)[0][0] != TARGET_CLASS:
        top_confused = pred_counts.most_common(1)[0][0]
        confused_logits = all_logits[:, top_confused]
        print(f"\n  Logit comparison: {TARGET_NAME} vs {DRUM_CLASSES[top_confused]}")
        print(f"    {TARGET_NAME:20s}: mean={target_logits.mean():.4f}")
        print(f"    {DRUM_CLASSES[top_confused]:20s}: mean={confused_logits.mean():.4f}")
        print(f"    Difference: {target_logits.mean() - confused_logits.mean():.4f}")


def main():
    parser = argparse.ArgumentParser(description="Diagnose class_18 (splash) issues")
    parser.add_argument("--checkpoint", type=Path, required=True, help="Path to checkpoint")
    parser.add_argument("--data-root", type=Path, default=Path("C:/github/BeatSight/data"))
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--skip-predictions", action="store_true", help="Only analyze label distribution")
    args = parser.parse_args()
    
    device = torch.device(args.device)
    
    print("=" * 70)
    print(f"  DIAGNOSING CLASS {TARGET_CLASS} ({TARGET_NAME}) - 0% VAL ACCURACY")
    print("=" * 70)
    print(f"\n  Checkpoint: {args.checkpoint}")
    print(f"  Device: {device}")
    
    # Load labels for distribution analysis
    print("\n  Loading labels...")
    train_labels, val_labels = load_labels_only(args.data_root)
    
    # Run distribution analysis (always works)
    analyze_class_distribution(train_labels, val_labels)
    
    if not args.skip_predictions:
        # Load model
        print("\n  Loading model...")
        model = load_model(args.checkpoint, device)
        
        # Run prediction analysis
        analyze_predictions_simple(model, val_labels, args.data_root, device)
    
    # Summary
    print("\n" + "=" * 70)
    print("  RECOMMENDATIONS")
    print("=" * 70)
    print("""
  If class_18 (splash) is consistently confused with crash/china:
    1. LET IT CONTINUE - the model may learn to distinguish them with more epochs
    2. Class_18 samples might have label noise (mislabeled as crash)
    3. Consider label audit: python train_classifier.py --clean-labels
    
  If class_18 probability is always near zero:
    1. Check for data issues (corrupted/missing splash samples)
    2. May need sqrt sampling instead of uniform (less aggressive rebalancing)
    3. Could try focal loss with low gamma (0.5-1.0)
    
  To monitor during training:
    - Class_18 should start recovering by epoch 10-15
    - If still at 0% by epoch 20, consider stopping and adjusting config
""")


if __name__ == "__main__":
    main()
