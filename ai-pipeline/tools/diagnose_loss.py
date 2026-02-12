#!/usr/bin/env python3
"""Diagnose loss function behavior."""
import torch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.loss import RecallBoostFocalLoss, FocalBCELoss, DEFAULT_PER_CLASS_GAMMA

# Create test data
torch.manual_seed(42)
logits = torch.randn(32, 12)  # (batch, classes)
targets = torch.zeros(32, 12)
targets[:, 0] = 1  # class 0 is all positive
targets[::2, 5] = 1  # class 5 (hihat_pedal) is 50% positive

# Create losses
focal_loss = FocalBCELoss(gamma=2.0)
recall_boost_loss = RecallBoostFocalLoss(
    per_class_gamma=DEFAULT_PER_CLASS_GAMMA,
    recall_boost_weight=2.0,
    base_gamma=2.0,
    num_classes=12
)

# Test forward
focal_out = focal_loss(logits, targets)
recall_out = recall_boost_loss(logits, targets)

print('=== Loss Function Test ===')
print(f'Focal Loss: {focal_out.item():.6f}')
print(f'RecallBoost Loss: {recall_out.item():.6f}')
print(f'Ratio (RB/Focal): {recall_out.item() / focal_out.item():.3f}')
print()

# Test gradient magnitude per class
logits.requires_grad_(True)

# Get gradients for focal loss
focal_out = focal_loss(logits, targets)
focal_out.backward()
focal_grads = logits.grad.abs().mean(dim=0).clone()
logits.grad.zero_()

# Get gradients for recall boost
recall_out = recall_boost_loss(logits, targets)
recall_out.backward()
rb_grads = logits.grad.abs().mean(dim=0)

print('=== Gradient Magnitudes per Class ===')
header = f"{'Class':<15} {'Focal':>10} {'RecallBoost':>12} {'Ratio':>8} {'Gamma':>8}"
print(header)
print('-' * 55)
class_names = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 'hihat_pedal', 
               'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']
for i, name in enumerate(class_names):
    gamma = DEFAULT_PER_CLASS_GAMMA.get(i, 2.0)
    ratio = rb_grads[i].item() / (focal_grads[i].item() + 1e-8)
    print(f'{name:<15} {focal_grads[i].item():>10.6f} {rb_grads[i].item():>12.6f} {ratio:>8.2f} {gamma:>8.1f}')

print()
print('=== KEY INSIGHT ===')
print('If RecallBoost is working, classes with higher gamma should have HIGHER gradient ratios')
print('hihat_pedal (gamma=5.0), cross_stick (gamma=4.0), ride_bow (gamma=4.0) should stand out')
