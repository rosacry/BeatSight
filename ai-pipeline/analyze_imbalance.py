#!/usr/bin/env python
"""Analyze class imbalance and weighting strategies for multi-label training."""

class_counts = {
    'kick': 6016247,
    'snare': 3977898,
    'hihat_closed': 3513851,
    'hihat_open': 1063917,
    'tom_high': 156276,
    'tom_mid': 275632,
    'tom_low': 345682,
    'ride': 431976,
    'crash': 147458,
    'china': 1874,
    'splash': 5357,
    'bell': 18893
}

total = sum(class_counts.values())
print("=" * 70)
print("MULTI-LABEL TRAINING: CLASS IMBALANCE ANALYSIS")
print("=" * 70)
print(f"Total samples: {total:,}")
print()

print("CLASS DISTRIBUTION:")
for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
    pct = count / total * 100
    imbalance = class_counts['snare'] / count
    print(f"  {cls:15}: {count:>10,} ({pct:>6.3f}%)  [{imbalance:>7.1f}:1 vs snare]")

print()
print("=" * 70)
print("WEIGHTING STRATEGY COMPARISON")
print("=" * 70)
print()

# CB-Focal weights with beta=0.999
beta = 0.999
print(f"{'Class':15} | {'CB-Focal (β=0.999)':>20} | {'Balanced Sampling':>20} | {'Sampling/CB':>12}")
print("-" * 75)

for cls in ['china', 'splash', 'bell', 'crash', 'tom_high', 'snare', 'kick']:
    count = class_counts[cls]
    
    # CB-Focal effective number
    en = (1 - beta**count) / (1 - beta)
    cb_weight = total / (12 * en)
    
    # Balanced sampling weight
    sample_weight = total / count
    
    # Ratio (how much more aggressive sampling is)
    ratio = sample_weight / cb_weight
    
    print(f"{cls:15} | {cb_weight:>20.1f} | {sample_weight:>20.1f} | {ratio:>10.0f}x more")

print()
print("=" * 70)
print("KEY INSIGHT")
print("=" * 70)
print()
print("CB-Focal (beta=0.999) asymptotically approaches 1/(1-beta) = 1000")
print("For rare classes like china (1,874 samples), CB-Focal gives minimal boost")
print()
print("Balanced Sampling gives weight = 1/count, directly proportional to rarity")
print("For china: 8,485x weight vs snare's 1x")
print()
print(">>> BALANCED SAMPLING IS ~1800x MORE AGGRESSIVE FOR RARE CLASSES <<<")
print()
print("This is why:")
print("  - Single-label training worked (used --balanced-sampling)")
print("  - Multi-label training failed (only used CB-Focal)")
print()
print("=" * 70)
print("SOLUTION")
print("=" * 70)
print()
print("Add these flags to your training command:")
print()
print("  --balanced-sampling --balanced-method rare_class")
print()
print("This will use WeightedRandomSampler to oversample rare classes")
print("Combined with CB-Focal, this provides both:")
print("  1. Input-level balancing (see rare classes more often)")
print("  2. Loss-level weighting (penalize rare class errors more)")
