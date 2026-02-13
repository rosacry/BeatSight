#!/usr/bin/env python3
"""
Generate a grid of spectrograms for visual review.

Creates a single image with all confused samples arranged in a grid,
making it easy to share for batch classification.

Usage:
    python generate_spectrogram_grid.py \
        --confusion-json confused_samples/kick_to_hihat_closed_confused.json \
        --feature-cache-dir F:/feature_cache \
        --dataset F:/datasets/prod_v5_cleaned \
        --output confused_samples/grid_kick_hihat.png \
        --max-samples 50
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Add ai-pipeline to path
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Generate spectrogram grid")
    parser.add_argument("--confusion-json", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--cols", type=int, default=10)
    args = parser.parse_args()
    
    # Load confusion data
    with open(args.confusion_json, 'r') as f:
        data = json.load(f)
    
    # Handle both old format (dict with confusion_pair) and new format (list of samples)
    if isinstance(data, list):
        # New format from investigate_hihat_confusion.py
        samples = data[:args.max_samples]
        # Group by pair for title
        pairs = set(s.get('pair', f"{s['true_label']}_to_{s['confused_with']}") for s in samples)
        title = f"Confused Samples: {', '.join(pairs)}"
    else:
        # Old format from export_confused_samples.py
        true_class, pred_class = data['confusion_pair']
        samples = data['samples'][:args.max_samples]
        title = f'Confused Samples: Label={true_class}, Predicted={pred_class}'
    
    print(f"Generating grid: {title}")
    print(f"Samples: {len(samples)}")
    
    # Load dataset
    print("\nLoading dataset...")
    from training.train_classifier import DrumSampleDataset
    
    val_dir = args.dataset / "val"
    labels_file = None
    if (val_dir / "val_labels_files.npy").exists():
        labels_file = val_dir / "val_labels.npy"
    elif (val_dir / "labels.json").exists():
        labels_file = val_dir / "labels.json"
    
    cache_mapping = val_dir / "cache_mapping.npz"
    if not cache_mapping.exists():
        cache_mapping = None
    
    val_dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=labels_file,
        cache_dir=args.feature_cache_dir / "val",
        cache_mapping=cache_mapping,
    )
    
    # Extract spectrograms
    print("Extracting spectrograms...")
    spectrograms = []
    confidences = []
    
    for i, sample in enumerate(samples):
        idx = sample['index']
        try:
            spec_tensor, label = val_dataset[idx]
            spec = spec_tensor.squeeze().numpy()
            spectrograms.append(spec)
            confidences.append(sample['confidence'])
            print(f"  [{i+1}/{len(samples)}] ✓")
        except Exception as e:
            print(f"  [{i+1}/{len(samples)}] ✗ {e}")
            spectrograms.append(np.zeros((128, 128)))
            confidences.append(0)
    
    # Create grid
    n_samples = len(spectrograms)
    cols = args.cols
    rows = (n_samples + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2, rows * 2.2))
    fig.suptitle(f'{title}\nKICK = low freq (bottom bright) | HIHAT = high freq (top bright)',
                 fontsize=14, fontweight='bold')
    
    axes = axes.flatten() if n_samples > 1 else [axes]
    
    for i, (spec, conf, sample) in enumerate(zip(spectrograms, confidences, samples)):
        ax = axes[i]
        ax.imshow(spec, aspect='auto', origin='lower', cmap='magma')
        # Show sample number, true label, and confidence
        true_lbl = sample.get('true_label', '?')[:4]  # Abbreviated
        ax.set_title(f'#{i+1} {true_lbl} ({conf*100:.0f}%)', fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        
        # Add frequency labels on first column
        if i % cols == 0:
            ax.set_ylabel('Freq↑', fontsize=8)
    
    # Hide unused subplots
    for i in range(n_samples, len(axes)):
        axes[i].axis('off')
    
    plt.tight_layout()
    
    # Save
    if args.output is None:
        args.output = args.confusion_json.parent / f"grid_{true_class}_{pred_class}.png"
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"\n✓ Saved: {args.output}")
    print(f"\nShare this image for batch classification!")
    print(f"  - KICK: Low frequency energy (bright at BOTTOM)")
    print(f"  - HIHAT: High frequency energy (bright at TOP)")


if __name__ == "__main__":
    main()
