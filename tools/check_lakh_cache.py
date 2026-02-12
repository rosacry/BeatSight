#!/usr/bin/env python3
"""Check if any lakh samples exist in cache."""
import numpy as np

index = np.load('F:/feature_cache/train/index.npz', allow_pickle=True)
keys = index['keys']

lakh_count = 0
lakh_examples = []
for k in keys:
    k_str = k.decode('utf-8') if isinstance(k, bytes) else str(k)
    if 'lakh' in k_str.lower():
        lakh_count += 1
        if len(lakh_examples) < 10:
            lakh_examples.append(k_str)

print(f"Lakh samples in cache: {lakh_count:,}")
if lakh_examples:
    print("Examples:")
    for ex in lakh_examples:
        print(f"  {ex}")
