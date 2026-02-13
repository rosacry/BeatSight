#!/usr/bin/env python3
"""
Investigate uncertain kick/snare → hihat_closed confusions.

These are samples where the model is genuinely uncertain (45-60% confidence),
which the standard cleaning approach can't catch. This tool exports them
for manual review to determine if they're:
1. True mislabels (should be hihat_closed)
2. Ambiguous samples (recording artifacts, should be removed)
3. Correct labels (model limitation)

Usage:
    python training/tools/investigate_hihat_confusion.py \
        --checkpoint runs/v5_phase2/best_drum_classifier_ema.pth \
        --dataset F:/datasets/prod_v5_cleaned \
        --feature-cache-dir F:/feature_cache \
        --output-dir hihat_investigation \
        --max-samples 500
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.cnn_v5 import DrumClassifierCNNv5
from training.train_classifier import DrumSampleDataset


# Target confusion pairs (label → predicted)
TARGET_PAIRS = [
    ("kick", "hihat_closed"),
    ("snare", "hihat_closed"),
    ("hihat_closed", "kick"),  # Reverse direction too
    ("hihat_closed", "snare"),
]


def load_model(checkpoint_path: str, device: torch.device, v5_size: str = "large"):
    """Load model from checkpoint."""
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if v5_size == "small":
        model = cnn_v5_small(num_classes=12)
    elif v5_size == "large":
        model = cnn_v5_large(num_classes=12)
    else:
        model = cnn_v5_medium(num_classes=12)
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    return model


def get_class_names():
    """Get class names in order."""
    return ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 
            'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']


def investigate_confusions(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    class_names: list,
    min_confidence: float = 0.45,
    max_confidence: float = 0.65,
    max_per_pair: int = 200,
):
    """
    Find samples where model is uncertain between target pairs.
    
    Returns dict mapping (true_label, pred_label) -> list of sample info
    """
    # Build class index mapping
    class_to_idx = {name: i for i, name in enumerate(class_names)}
    
    # Target pair indices
    target_pair_indices = set()
    for true_name, pred_name in TARGET_PAIRS:
        if true_name in class_to_idx and pred_name in class_to_idx:
            target_pair_indices.add((class_to_idx[true_name], class_to_idx[pred_name]))
    
    # Results storage
    results = defaultdict(list)
    pair_counts = defaultdict(int)
    
    total_scanned = 0
    total_found = 0
    sample_offset = 0
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(dataloader, desc="Investigating"):
            features, labels = batch
            features = features.to(device)
            labels = labels.numpy()
            
            # Get predictions
            logits = model(features)
            if isinstance(logits, tuple):
                logits = logits[0]
            probs = torch.softmax(logits, dim=1)
            
            # Get top-2 predictions
            top2_probs, top2_preds = torch.topk(probs, k=2, dim=1)
            top2_probs = top2_probs.cpu().numpy()
            top2_preds = top2_preds.cpu().numpy()
            
            for i in range(len(labels)):
                total_scanned += 1
                true_label = labels[i]
                pred_label = top2_preds[i, 0]  # Top prediction
                alt_label = top2_preds[i, 1]   # Second prediction
                
                top_conf = top2_probs[i, 0]
                alt_conf = top2_probs[i, 1]
                
                # Current global index (accounting for subset)
                global_idx = sample_offset + i
                
                # Check if this matches any target pair
                pair_key = None
                confused_with = None
                
                # Case 1: Model predicts different class with moderate confidence
                if (true_label, pred_label) in target_pair_indices:
                    if min_confidence <= top_conf <= max_confidence:
                        pair_key = (true_label, pred_label)
                        confused_with = pred_label
                
                # Case 2: Model predicts correct but second choice is target
                elif (true_label, alt_label) in target_pair_indices:
                    if alt_conf >= 0.25:  # Alt prediction is significant
                        pair_key = (true_label, alt_label)
                        confused_with = alt_label
                
                if pair_key and pair_counts[pair_key] < max_per_pair:
                    pair_counts[pair_key] += 1
                    total_found += 1
                    
                    results[pair_key].append({
                        "index": global_idx,
                        "file": "",
                        "true_label": class_names[true_label],
                        "pred_label": class_names[pred_label],
                        "confused_with": class_names[confused_with],
                        "confidence": float(top_conf),
                        "alt_confidence": float(alt_conf),
                        "margin": float(top_conf - alt_conf),
                    })
                
                # Check if we have enough for all pairs
                if all(pair_counts[p] >= max_per_pair for p in target_pair_indices):
                    break
            
            sample_offset += len(labels)
            
            # Early exit if we have enough
            if all(pair_counts[p] >= max_per_pair for p in target_pair_indices):
                break
    
    print(f"\nScanned {total_scanned:,} samples, found {total_found:,} uncertain target confusions")
    
    return results


def save_results(results: dict, output_dir: Path, class_names: list):
    """Save investigation results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Summary stats
    summary = {
        "total_samples": sum(len(v) for v in results.values()),
        "pairs": {},
    }
    
    all_samples = []
    
    for (true_idx, pred_idx), samples in results.items():
        true_name = class_names[true_idx]
        pred_name = class_names[pred_idx]
        pair_name = f"{true_name}_to_{pred_name}"
        
        summary["pairs"][pair_name] = {
            "count": len(samples),
            "avg_confidence": np.mean([s["confidence"] for s in samples]) if samples else 0,
            "avg_margin": np.mean([s["margin"] for s in samples]) if samples else 0,
        }
        
        # Add pair info to samples
        for s in samples:
            s["pair"] = pair_name
            all_samples.append(s)
    
    # Save summary
    with open(output_dir / "investigation_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # Save all samples as NPZ for spectrogram generation
    if all_samples:
        indices = np.array([s["index"] for s in all_samples], dtype=np.int64)
        np.savez(
            output_dir / "uncertain_samples.npz",
            indices=indices,
            samples=json.dumps(all_samples),
        )
        
        # Also save as JSON for easy reading
        with open(output_dir / "uncertain_samples.json", "w") as f:
            json.dump(all_samples, f, indent=2)
    
    print(f"\nSaved results to {output_dir}")
    print(f"  - investigation_summary.json")
    print(f"  - uncertain_samples.npz ({len(all_samples)} samples)")
    print(f"  - uncertain_samples.json")
    
    return summary


def generate_review_command(output_dir: Path, feature_cache_dir: str):
    """Generate command to create spectrogram grid."""
    npz_path = output_dir / "uncertain_samples.npz"
    
    print("\n" + "=" * 60)
    print("NEXT STEP: Generate spectrogram grid for review")
    print("=" * 60)
    print(f"""
Run this command to generate spectrograms:

python training/tools/generate_spectrogram_grid.py \\
    --npz {npz_path} \\
    --feature-cache-dir {feature_cache_dir} \\
    --output {output_dir / "spectrogram_grid.png"} \\
    --max-samples 100 \\
    --cols 10

Then review the grid and note which samples are:
  - Mislabeled (should be hihat_closed)
  - Ambiguous (unclear, consider removing)
  - Correct (model limitation)
""")


def main():
    parser = argparse.ArgumentParser(description="Investigate hi-hat confusions")
    parser.add_argument("--checkpoint", required=True, help="Model checkpoint path")
    parser.add_argument("--dataset", required=True, help="Dataset path")
    parser.add_argument("--feature-cache-dir", required=True, help="Feature cache directory")
    parser.add_argument("--output-dir", default="hihat_investigation", help="Output directory")
    parser.add_argument("--split", default="val", choices=["train", "val"], help="Which split to investigate")
    parser.add_argument("--min-confidence", type=float, default=0.45, help="Min confidence threshold")
    parser.add_argument("--max-confidence", type=float, default=0.65, help="Max confidence threshold")
    parser.add_argument("--max-samples", type=int, default=200, help="Max samples per confusion pair")
    parser.add_argument("--batch-size", type=int, default=256, help="Batch size")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers")
    
    args = parser.parse_args()
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    class_names = get_class_names()
    print(f"Classes ({len(class_names)}): {class_names}")
    
    print(f"\nTarget confusion pairs to investigate:")
    for true_name, pred_name in TARGET_PAIRS:
        print(f"  {true_name} → {pred_name}")
    
    print(f"\nConfidence range: {args.min_confidence:.0%} - {args.max_confidence:.0%}")
    print(f"Max samples per pair: {args.max_samples}")
    
    # Load model
    print(f"\nLoading model from {args.checkpoint}...")
    model = load_model(args.checkpoint, device)
    
    # Load dataset
    print(f"\nLoading {args.split} split...")
    split_dir = Path(args.dataset) / args.split
    
    # Find labels file
    labels_file = None
    if (split_dir / f"{args.split}_labels_files.npy").exists():
        labels_file = split_dir / f"{args.split}_labels.npy"
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
        cache_dir=Path(args.feature_cache_dir) / args.split,
        cache_mapping=cache_mapping,
    )
    print(f"Loaded {len(dataset):,} samples")
    
    # Get valid indices
    if cache_mapping is not None:
        mapping_data = np.load(cache_mapping, allow_pickle=True)
        valid_mask = mapping_data['valid']
        valid_indices = np.where(valid_mask)[0]
        print(f"Valid cached samples: {len(valid_indices):,}")
        from torch.utils.data import Subset
        dataset = Subset(dataset, valid_indices.tolist())
    
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,  # Avoid multiprocessing issues
        pin_memory=True,
    )
    
    # Investigate
    results = investigate_confusions(
        model=model,
        dataloader=dataloader,
        device=device,
        class_names=class_names,
        min_confidence=args.min_confidence,
        max_confidence=args.max_confidence,
        max_per_pair=args.max_samples,
    )
    
    # Print summary
    print("\n" + "=" * 60)
    print("INVESTIGATION RESULTS")
    print("=" * 60)
    
    for (true_idx, pred_idx), samples in sorted(results.items(), key=lambda x: -len(x[1])):
        true_name = class_names[true_idx]
        pred_name = class_names[pred_idx]
        
        if samples:
            avg_conf = np.mean([s["confidence"] for s in samples])
            avg_margin = np.mean([s["margin"] for s in samples])
            print(f"\n{true_name} → {pred_name}: {len(samples)} samples")
            print(f"  Avg confidence: {avg_conf:.1%}")
            print(f"  Avg margin (top - 2nd): {avg_margin:.1%}")
    
    # Save results
    output_dir = Path(args.output_dir)
    summary = save_results(results, output_dir, class_names)
    
    # Generate review command
    generate_review_command(output_dir, args.feature_cache_dir)
    
    print("\n" + "=" * 60)
    print("INTERPRETATION GUIDE")
    print("=" * 60)
    print("""
When reviewing spectrograms, look for:

KICK vs HIHAT_CLOSED:
  - Kick: Strong low-frequency energy, short decay, 50-150 Hz fundamental
  - Hihat closed: High-frequency content (6-12 kHz), very short, no low end
  - Ambiguous: Muted/dampened kick can look like closed hihat

SNARE vs HIHAT_CLOSED:
  - Snare: Broad spectrum, snare wire buzz (2-5 kHz), longer decay
  - Hihat closed: Concentrated high freq, shorter, no snare buzz
  - Ambiguous: Ghost notes, very soft snare hits

If >70% look mislabeled, we should force-correct these pairs.
If >50% look ambiguous, we should consider removing them from training.
""")


if __name__ == "__main__":
    main()
