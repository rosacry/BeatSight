#!/usr/bin/env python3
"""
Check the actual training progress of a checkpoint.

This script analyzes a checkpoint file and reports:
- Epoch counter (may be inflated from multiple mid-epoch resumes)
- Actual cumulative batches trained
- Estimated full epochs of actual training

Usage:
    python training/scripts/check_checkpoint_progress.py runs/v5_phase1/checkpoints/latest_checkpoint.pth
"""

import argparse
import sys
from pathlib import Path

import torch


def analyze_checkpoint(checkpoint_path: str) -> None:
    """Analyze a checkpoint and report training progress."""
    path = Path(checkpoint_path)
    if not path.exists():
        print(f"ERROR: Checkpoint not found: {path}")
        sys.exit(1)
    
    print(f"Analyzing checkpoint: {path}")
    print("=" * 60)
    
    # Load checkpoint
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    
    # Extract info
    epoch = checkpoint.get('epoch', 'unknown')
    total_epochs = checkpoint.get('total_epochs', 'unknown')
    batch_index = checkpoint.get('batch_index')
    total_batches = checkpoint.get('total_batches')
    cumulative_batches = checkpoint.get('cumulative_batches_trained', 0)
    batches_per_epoch = checkpoint.get('batches_per_epoch', 0)
    best_val_acc = checkpoint.get('best_val_acc', 0)
    best_epoch = checkpoint.get('best_epoch', -1)
    
    # Checkpoint type
    is_mid_epoch = batch_index is not None and total_batches is not None
    
    print(f"\n📊 CHECKPOINT INFO:")
    print(f"   Epoch counter:      {epoch}/{total_epochs}")
    print(f"   Best val accuracy:  {best_val_acc:.2f}% (epoch {best_epoch})")
    
    if is_mid_epoch:
        pct = 100 * batch_index / total_batches if total_batches else 0
        print(f"   Type:               Mid-epoch ({batch_index:,}/{total_batches:,} = {pct:.1f}%)")
    else:
        print(f"   Type:               End-of-epoch")
    
    print(f"\n📈 ACTUAL TRAINING PROGRESS:")
    
    if cumulative_batches > 0 and batches_per_epoch > 0:
        actual_epochs = cumulative_batches / batches_per_epoch
        print(f"   Cumulative batches: {cumulative_batches:,}")
        print(f"   Batches per epoch:  {batches_per_epoch:,}")
        print(f"   Actual full epochs: {actual_epochs:.2f}")
        
        if epoch > 0:
            inflation = epoch - actual_epochs
            if inflation > 1:
                print(f"\n⚠️  EPOCH INFLATION DETECTED:")
                print(f"   Epoch counter says {epoch}, but only {actual_epochs:.1f} full epochs trained")
                print(f"   Inflation: +{inflation:.1f} phantom epochs")
                print(f"\n   This happens when you resume mid-epoch multiple times.")
                print(f"   The model has seen less data than the epoch counter suggests.")
                
                # Recommendation
                target_epochs = 50  # Assuming this is the goal
                remaining_actual = target_epochs - actual_epochs
                recommended_total = epoch + remaining_actual
                print(f"\n💡 RECOMMENDATION:")
                print(f"   To reach {target_epochs} actual epochs of training,")
                print(f"   set --epochs {int(recommended_total) + 5} (adding buffer for more interrupts)")
    else:
        print(f"   ⚠️  No cumulative progress tracking in this checkpoint")
        print(f"   This is a legacy checkpoint before the tracking was added.")
        
        # Estimate from available info
        if batches_per_epoch > 0 or total_batches:
            est_batches = total_batches or 118891  # Default
            if is_mid_epoch:
                estimated = ((epoch - 1) * est_batches) + batch_index
            else:
                estimated = epoch * est_batches
            actual_est = estimated / est_batches
            print(f"\n   Estimated cumulative batches: ~{estimated:,}")
            print(f"   Estimated actual epochs: ~{actual_est:.1f}")
            print(f"\n   Note: This is just an estimate. After resuming with the")
            print(f"   updated code, accurate tracking will begin.")
    
    # Show args if available
    args = checkpoint.get('args', {})
    if args:
        print(f"\n⚙️  TRAINING CONFIG:")
        print(f"   Dataset:        {args.get('dataset', 'unknown')}")
        print(f"   Batch size:     {args.get('batch_size', 'unknown')}")
        print(f"   Learning rate:  {args.get('lr', 'unknown')}")
        print(f"   Scheduler:      {args.get('scheduler', 'unknown')}")
        if args.get('balanced_sampling'):
            print(f"   Sampling:       {args.get('sampling_strategy', 'unknown')} balanced")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Check checkpoint training progress")
    parser.add_argument('checkpoint', help='Path to checkpoint file')
    args = parser.parse_args()
    
    analyze_checkpoint(args.checkpoint)


if __name__ == '__main__':
    main()
