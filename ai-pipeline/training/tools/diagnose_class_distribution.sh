#!/bin/bash
# =============================================================================
# DIAGNOSTIC: Check class distribution and confusion patterns
# =============================================================================
# Run this BEFORE spending hours on training to understand the data!
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Source environment
if [ -f "$SCRIPT_DIR/beatsight_env.sh" ]; then
    source "$SCRIPT_DIR/beatsight_env.sh"
fi

BEATSIGHT_REPO_ROOT=${BEATSIGHT_REPO_ROOT:-$REPO_ROOT}
BEATSIGHT_DATA_ROOT=${BEATSIGHT_DATA_ROOT:-${BEATSIGHT_REPO_ROOT}/data}

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           CLASS DISTRIBUTION DIAGNOSTIC                          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

cd "$BEATSIGHT_REPO_ROOT"

# Run Python diagnostic
PYTHONPATH=ai-pipeline python -c "
import numpy as np
from pathlib import Path

LABELS_DIR = Path('${BEATSIGHT_DATA_ROOT}/dataset_index')
DRUM_CLASSES = [
    'aux_percussion', 'china', 'crash', 'cross_stick', 'cymbal_choke',
    'hihat_closed', 'hihat_foot_splash', 'hihat_open', 'hihat_pedal', 'hihat_splash',
    'kick', 'ride_bell', 'ride_bow', 'rimshot', 'snare',
    'snare_center', 'snare_cross_stick', 'snare_rimshot', 'splash', 'tom_high', 'tom_low'
]

print('Loading labels...')
train_labels = np.load(LABELS_DIR / 'train_labels.npy')
val_labels = np.load(LABELS_DIR / 'val_labels.npy')

print(f'Train samples: {len(train_labels):,}')
print(f'Val samples: {len(val_labels):,}')
print()

# Count per class
train_counts = np.bincount(train_labels, minlength=21)
val_counts = np.bincount(val_labels, minlength=21)

print('=' * 80)
print('CLASS DISTRIBUTION (Training Set)')
print('=' * 80)
print(f'{'Class':<25} {'Count':>12} {'%':>8} {'Ratio to Min':>14}')
print('-' * 80)

min_count = train_counts.min()
max_count = train_counts.max()
total = train_counts.sum()

sorted_indices = np.argsort(train_counts)[::-1]  # Descending

for idx in sorted_indices:
    name = DRUM_CLASSES[idx]
    count = train_counts[idx]
    pct = 100 * count / total
    ratio = count / min_count
    bar = '█' * int(50 * count / max_count)
    print(f'{idx:2d}. {name:<20} {count:>12,} {pct:>7.2f}% {ratio:>10.1f}x  {bar}')

print('-' * 80)
print(f'    TOTAL: {total:,}')
print(f'    Max/Min ratio: {max_count / min_count:.1f}x')
print()

# Identify problematic class groups (similar names)
print('=' * 80)
print('SIMILAR CLASS GROUPS (potential confusion)')
print('=' * 80)

groups = {
    'Snare variants': [13, 14, 15, 16, 17],  # rimshot, snare, snare_center, snare_cross_stick, snare_rimshot
    'Hi-hat variants': [5, 6, 7, 8, 9],      # hihat_*
    'Cymbal variants': [1, 2, 4, 18],        # china, crash, cymbal_choke, splash
    'Ride variants': [11, 12],               # ride_bell, ride_bow
    'Tom variants': [19, 20],                # tom_high, tom_low
}

for group_name, indices in groups.items():
    total_group = sum(train_counts[i] for i in indices)
    print(f'\n{group_name}:')
    for idx in indices:
        name = DRUM_CLASSES[idx]
        count = train_counts[idx]
        pct_of_group = 100 * count / total_group if total_group > 0 else 0
        print(f'  {idx:2d}. {name:<20} {count:>12,} ({pct_of_group:>5.1f}% of group)')
    print(f'      Group total: {total_group:,}')

print()
print('=' * 80)
print('VALIDATION SET CLASS BALANCE')
print('=' * 80)
val_total = val_counts.sum()
for idx in sorted_indices:
    name = DRUM_CLASSES[idx]
    train_pct = 100 * train_counts[idx] / total
    val_pct = 100 * val_counts[idx] / val_total
    diff = val_pct - train_pct
    warning = ' ⚠️' if abs(diff) > 2 else ''
    print(f'{idx:2d}. {name:<20} Train: {train_pct:>6.2f}%  Val: {val_pct:>6.2f}%  (diff: {diff:+.2f}%){warning}')

print()
print('=' * 80)
print('RECOMMENDATIONS')
print('=' * 80)

# Check for extreme imbalance
if max_count / min_count > 100:
    print('⚠️  EXTREME CLASS IMBALANCE (>100x)')
    print('   → Use sqrt or log sampling (not uniform!)')
    print('   → Add focal loss with γ=1.5-2.0')
    print('   → Consider class grouping or hierarchical classification')

# Check for tiny classes
tiny_classes = [(i, DRUM_CLASSES[i], train_counts[i]) for i in range(21) if train_counts[i] < 10000]
if tiny_classes:
    print()
    print('⚠️  TINY CLASSES (<10K samples):')
    for idx, name, count in tiny_classes:
        print(f'   → {name}: {count:,} samples - may need oversampling or data augmentation')

# Check for dominant class
dominant = [(i, DRUM_CLASSES[i], train_counts[i]) for i in range(21) if train_counts[i] > 0.2 * total]
if dominant:
    print()
    print('⚠️  DOMINANT CLASSES (>20% of data):')
    for idx, name, count in dominant:
        pct = 100 * count / total
        print(f'   → {name}: {pct:.1f}% of data - model may overfit to this class')
"

echo ""
echo "Run this diagnostic FIRST to understand your data before training!"
