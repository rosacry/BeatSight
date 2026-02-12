#!/usr/bin/env python3
"""Compare two checkpoints to verify which is better."""

import torch
import sys
sys.path.insert(0, '.')

# Load both checkpoints
print("Loading checkpoints...")
old = torch.load('runs/v5_multilabel/best_checkpoint.pt', map_location='cpu', weights_only=False)
new = torch.load('runs/v5_multilabel_balanced/best_checkpoint.pt', map_location='cpu', weights_only=False)

print()
print('=' * 60)
print('OLD CHECKPOINT (v5_multilabel)')
print('=' * 60)
print(f"  Epoch: {old.get('epoch', 'N/A')}")
print(f"  Best F1: {old.get('best_val_f1', 'N/A')}")
print(f"  Val Loss: {old.get('val_loss', 'N/A')}")
print(f"  Cumulative batches: {old.get('cumulative_batches_trained', 'N/A')}")

print()
print('=' * 60)
print('NEW CHECKPOINT (v5_multilabel_balanced)')
print('=' * 60)
print(f"  Epoch: {new.get('epoch', 'N/A')}")
print(f"  Best F1: {new.get('best_val_f1', 'N/A')}")
print(f"  Val Loss: {new.get('val_loss', 'N/A')}")
print(f"  Cumulative batches: {new.get('cumulative_batches_trained', 'N/A')}")

print()
print('=' * 60)
print('COMPARISON')
print('=' * 60)
old_f1 = old.get('best_val_f1', 0)
new_f1 = new.get('best_val_f1', 0)
diff = new_f1 - old_f1
print(f"  F1 Difference: {diff:+.4f} ({'NEW is better' if diff > 0 else 'OLD is better' if diff < 0 else 'Same'})")
