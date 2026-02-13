#!/usr/bin/env python3
"""
Extract Confused Samples for Manual Verification
=================================================
Saves spectrograms of the most confused samples as images for visual inspection.

Usage:
    cd /c/github/BeatSight/ai-pipeline
    PYTHONPATH=. python training/scripts/extract_confused_samples.py \
        --checkpoint runs/v5_phase1/best_drum_classifier.pth \
        --dataset "F:/datasets/prod_v5_definitive" \
        --feature-cache-dir "F:/feature_cache" \
        --output-dir runs/v5_phase1/confusion_analysis \
        --num-samples 50
"""

import argparse
import sys
import torch
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import json
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.utils.consolidated_cache import ConsolidatedCacheReader

CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open", 
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]

# Focus on the problematic pairs
CONFUSION_PAIRS = [
    ("kick", "hihat_closed"),
    ("snare", "hihat_closed"),
    ("snare", "hihat_pedal"),
    ("kick", "crash"),
    ("hihat_closed", "kick"),
    ("hihat_closed", "snare"),
    ("kick", "hihat_open"),
    ("snare", "ride_bow"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--feature-cache-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--num-samples", type=int, default=50, help="Samples per confusion pair")
    parser.add_argument("--num-val-samples", type=int, default=20000, help="Val samples to scan")
    args = parser.parse_args()
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load model
    print("\n" + "="*70)
    print("  LOADING MODEL")
    print("="*70)
    
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    state = ckpt.get('model_state_dict', ckpt.get('state_dict', ckpt))
    model = cnn_v5_large(12, drop_path_rate=0.1, use_deep_supervision=False, use_multi_task=False)
    model.load_state_dict(state)
    model.eval().to(device)
    print(f"  [OK] Model loaded")
    
    # Load data
    print("\n" + "="*70)
    print("  LOADING VALIDATION DATA")
    print("="*70)
    
    dataset_path = Path(args.dataset)
    cache_path = Path(args.feature_cache_dir)
    
    labels = np.load(dataset_path / "val" / "val_labels_labels.npy")
    mapping = np.load(dataset_path / "val" / "cache_mapping.npz")
    
    # Try to load file paths for context
    try:
        files = np.load(dataset_path / "val" / "val_labels_files.npy", allow_pickle=True)
        has_files = True
    except:
        files = None
        has_files = False
    
    train_cache = ConsolidatedCacheReader(cache_path / "train")
    val_cache = ConsolidatedCacheReader(cache_path / "val")
    
    valid_indices = np.where(mapping['valid'])[0]
    print(f"  [OK] {len(valid_indices):,} valid samples")
    
    # Scan validation set for confused samples
    print("\n" + "="*70)
    print(f"  SCANNING {args.num_val_samples:,} SAMPLES FOR CONFUSIONS")
    print("="*70)
    
    np.random.seed(42)
    scan_indices = np.random.choice(valid_indices, min(args.num_val_samples, len(valid_indices)), replace=False)
    
    # Store confused samples by pair
    confused_samples = defaultdict(list)
    
    with torch.no_grad():
        for i, idx in enumerate(scan_indices):
            if (i + 1) % 5000 == 0:
                print(f"  Scanned {i+1}/{len(scan_indices)}...")
            
            cache_split = str(mapping['cache_split'][idx])
            cache = val_cache if cache_split == 'val' else train_cache
            
            shard_id = int(mapping['shard_ids'][idx])
            offset = int(mapping['offsets'][idx])
            
            feat = cache._read_sample(shard_id, offset)
            if isinstance(feat, np.ndarray):
                feat_tensor = torch.from_numpy(feat)
            else:
                feat_tensor = feat
            
            feat_input = feat_tensor.unsqueeze(0).float().to(device)
            
            logits = model(feat_input)
            probs = torch.softmax(logits, dim=1)
            conf = probs.max().item()
            pred = logits.argmax(1).item()
            gt = int(labels[idx])
            
            if pred != gt:
                gt_name = CLASS_NAMES[gt]
                pred_name = CLASS_NAMES[pred]
                pair = (gt_name, pred_name)
                
                if pair in CONFUSION_PAIRS:
                    # Store the raw feature data
                    if isinstance(feat, torch.Tensor):
                        feat_np = feat.cpu().numpy()
                    else:
                        feat_np = feat
                    
                    confused_samples[pair].append({
                        'idx': int(idx),
                        'gt': gt_name,
                        'pred': pred_name,
                        'conf': conf,
                        'gt_conf': probs[0, gt].item(),
                        'feat': feat_np,
                        'file': str(files[idx]) if has_files else f"idx_{idx}",
                        'shard_id': shard_id,
                        'offset': offset,
                    })
    
    # Save spectrograms for each confusion pair
    print("\n" + "="*70)
    print("  SAVING CONFUSED SAMPLE SPECTROGRAMS")
    print("="*70)
    
    summary = {}
    
    for pair in CONFUSION_PAIRS:
        samples = confused_samples[pair]
        if not samples:
            print(f"  {pair[0]} → {pair[1]}: No samples found")
            continue
        
        # Sort by confidence (model was most sure about wrong answer)
        samples.sort(key=lambda x: x['conf'], reverse=True)
        samples = samples[:args.num_samples]
        
        pair_dir = output_dir / f"{pair[0]}_to_{pair[1]}"
        pair_dir.mkdir(exist_ok=True)
        
        print(f"  {pair[0]} → {pair[1]}: Saving {len(samples)} samples")
        
        pair_summary = []
        
        for j, sample in enumerate(samples):
            # Create figure with spectrogram
            fig, ax = plt.subplots(figsize=(10, 4))
            
            # Get spectrogram data (squeeze to 2D)
            spec = sample['feat'].squeeze()
            
            # Plot mel spectrogram
            im = ax.imshow(spec, aspect='auto', origin='lower', cmap='magma',
                          vmin=-80, vmax=0)
            
            ax.set_xlabel('Time frames')
            ax.set_ylabel('Mel bins')
            ax.set_title(
                f"GT: {sample['gt'].upper()} | Pred: {sample['pred'].upper()} "
                f"(conf: {sample['conf']:.2f}, gt_conf: {sample['gt_conf']:.2f})\n"
                f"File: {Path(sample['file']).name[:60]}",
                fontsize=10
            )
            
            plt.colorbar(im, ax=ax, label='dB')
            plt.tight_layout()
            
            # Save
            filename = f"{j:02d}_{sample['gt']}_pred_{sample['pred']}_{sample['conf']:.2f}.png"
            plt.savefig(pair_dir / filename, dpi=100, bbox_inches='tight')
            plt.close()
            
            pair_summary.append({
                'filename': filename,
                'gt': sample['gt'],
                'pred': sample['pred'],
                'confidence': sample['conf'],
                'gt_confidence': sample['gt_conf'],
                'source_file': sample['file'],
                'dataset_idx': sample['idx'],
            })
        
        summary[f"{pair[0]}_to_{pair[1]}"] = pair_summary
        
        # Also create a grid view for quick scanning
        n_samples = len(samples)
        if n_samples >= 4:
            n_cols = 4
            n_rows = min(4, (n_samples + n_cols - 1) // n_cols)
            
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 4 * n_rows))
            axes = axes.flatten() if n_rows > 1 else [axes] if n_cols == 1 else axes.flatten()
            
            for k, sample in enumerate(samples[:n_rows * n_cols]):
                ax = axes[k]
                spec = sample['feat'].squeeze()
                ax.imshow(spec, aspect='auto', origin='lower', cmap='magma', vmin=-80, vmax=0)
                ax.set_title(f"GT:{sample['gt']} P:{sample['pred']} c:{sample['conf']:.2f}", fontsize=8)
                ax.axis('off')
            
            # Hide unused subplots
            for k in range(len(samples), len(axes)):
                axes[k].axis('off')
            
            plt.suptitle(f"Confusion: {pair[0].upper()} → {pair[1].upper()}", fontsize=14)
            plt.tight_layout()
            plt.savefig(pair_dir / "GRID_OVERVIEW.png", dpi=120, bbox_inches='tight')
            plt.close()
    
    # Save summary JSON
    with open(output_dir / "confusion_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\n" + "="*70)
    print("  EXTRACTION COMPLETE")
    print("="*70)
    print(f"\n  Output directory: {output_dir}")
    print(f"\n  Confusion pairs extracted:")
    for pair in CONFUSION_PAIRS:
        count = len(confused_samples[pair])
        saved = min(count, args.num_samples)
        print(f"    {pair[0]:12s} → {pair[1]:12s}: {saved:3d} samples saved (found {count})")
    
    print(f"\n  Files created:")
    print(f"    - Individual spectrograms in subdirectories")
    print(f"    - GRID_OVERVIEW.png in each subdirectory (quick scan)")
    print(f"    - confusion_summary.json (metadata)")
    
    print("\n" + "="*70)
    print("  WHAT TO LOOK FOR IN THE SPECTROGRAMS")
    print("="*70)
    print("""
  KICK should show:
    - Strong low-frequency energy (bottom of spectrogram)
    - Sharp vertical attack line
    - Short duration, quick decay
  
  SNARE should show:
    - Broadband noise (vertical stripe across all frequencies)  
    - Strong attack with snare wire "buzz"
    - Mid-high frequency emphasis
  
  HIHAT_CLOSED should show:
    - High-frequency content only (top of spectrogram)
    - Very short duration
    - No low-frequency energy
  
  HIHAT_PEDAL should show:
    - Similar to closed but slightly longer
    - May have more "body"
  
  If you see LOW frequencies in a sample labeled as HIHAT → MISLABELED
  If you see HIGH-only frequencies in a sample labeled as KICK → MISLABELED
""")


if __name__ == "__main__":
    main()
