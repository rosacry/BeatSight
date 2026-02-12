#!/usr/bin/env python3
"""Diagnose loss function with realistic class distributions."""
import torch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.loss import RecallBoostFocalLoss, FocalBCELoss, DEFAULT_PER_CLASS_GAMMA

# Realistic class positive rates from the training logs
CLASS_POSITIVE_RATES = {
    0: 0.154,  # china
    1: 0.276,  # crash
    2: 0.062,  # cross_stick (6.2% - very low!)
    3: 0.245,  # hihat_closed
    4: 0.154,  # hihat_open
    5: 0.093,  # hihat_pedal (9.3% - very low!)
    6: 0.428,  # kick
    7: 0.093,  # ride_bell (9.3%)
    8: 0.214,  # ride_bow
    9: 0.367,  # snare
    10: 0.093, # splash (9.3%)
    11: 0.154, # tom
}

class_names = ['china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open', 'hihat_pedal', 
               'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom']

# Create realistic test data
torch.manual_seed(42)
batch_size = 1000

# Create targets with realistic distributions
targets = torch.zeros(batch_size, 12)
for cls_idx, rate in CLASS_POSITIVE_RATES.items():
    n_positive = int(batch_size * rate)
    targets[:n_positive, cls_idx] = 1.0

# Simulate model outputs that have ~70% accuracy (realistic)
# For positive samples, model outputs logits around 0.5 (p=0.62)
# For negative samples, model outputs logits around -0.5 (p=0.38)
logits = torch.where(targets == 1, 
                     torch.randn(batch_size, 12) * 0.5 + 0.5,  # positives: mean=0.5
                     torch.randn(batch_size, 12) * 0.5 - 0.5)  # negatives: mean=-0.5

# Create losses
focal_loss = FocalBCELoss(gamma=2.0)
recall_boost_loss = RecallBoostFocalLoss(
    per_class_gamma=DEFAULT_PER_CLASS_GAMMA,
    recall_boost_weight=2.0,
    base_gamma=2.0,
    num_classes=12
)

# Forward pass
logits.requires_grad_(True)
focal_out = focal_loss(logits, targets)
focal_out.backward()
focal_grads = logits.grad.clone()

# Separate gradients for positive and negative samples
focal_pos_grads = []
focal_neg_grads = []
for cls_idx in range(12):
    pos_mask = targets[:, cls_idx] == 1
    neg_mask = targets[:, cls_idx] == 0
    focal_pos_grads.append(focal_grads[pos_mask, cls_idx].abs().mean().item())
    focal_neg_grads.append(focal_grads[neg_mask, cls_idx].abs().mean().item())

logits.grad.zero_()
recall_out = recall_boost_loss(logits, targets)
recall_out.backward()
rb_grads = logits.grad

rb_pos_grads = []
rb_neg_grads = []
for cls_idx in range(12):
    pos_mask = targets[:, cls_idx] == 1
    neg_mask = targets[:, cls_idx] == 0
    rb_pos_grads.append(rb_grads[pos_mask, cls_idx].abs().mean().item())
    rb_neg_grads.append(rb_grads[neg_mask, cls_idx].abs().mean().item())

print('=== POSITIVE SAMPLE GRADIENTS (what matters for recall!) ===')
header = f"{'Class':<15} {'Focal':>10} {'RB':>10} {'Ratio':>8} {'Gamma':>6} {'PosRate':>8}"
print(header)
print('-' * 65)
for i, name in enumerate(class_names):
    gamma = DEFAULT_PER_CLASS_GAMMA.get(i, 2.0)
    ratio = rb_pos_grads[i] / (focal_pos_grads[i] + 1e-8)
    print(f'{name:<15} {focal_pos_grads[i]:>10.6f} {rb_pos_grads[i]:>10.6f} {ratio:>8.2f} {gamma:>6.1f} {CLASS_POSITIVE_RATES[i]:>8.1%}')

print()
print('=== NEGATIVE SAMPLE GRADIENTS ===')
header = f"{'Class':<15} {'Focal':>10} {'RB':>10} {'Ratio':>8}"
print(header)
print('-' * 50)
for i, name in enumerate(class_names):
    ratio = rb_neg_grads[i] / (focal_neg_grads[i] + 1e-8)
    print(f'{name:<15} {focal_neg_grads[i]:>10.6f} {rb_neg_grads[i]:>10.6f} {ratio:>8.2f}')

print()
print('=== ANALYSIS ===')
print('For recall boost to work, POSITIVE gradients should be HIGHER for low-recall classes')
print('We want to see ratios > 1.0 for hihat_pedal, cross_stick, ride_bow')
