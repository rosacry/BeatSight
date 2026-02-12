#!/usr/bin/env python3
"""Quick script to check china/splash in manifests."""
import json
from pathlib import Path
from collections import defaultdict

manifest_dir = Path('c:/github/BeatSight/ai-pipeline/training/data/manifests')
output_file = Path('c:/github/BeatSight/ai-pipeline/rare_class_report.txt')

results = []

for manifest in sorted(manifest_dir.glob('*.jsonl')):
    label_counts = defaultdict(int)
    total = 0
    
    with open(manifest, 'r') as f:
        for line in f:
            try:
                item = json.loads(line)
                total += 1
                for comp in item.get('components', []):
                    label = comp.get('label', 'unknown')
                    label_counts[label] += 1
            except:
                pass
    
    china = label_counts.get('china', 0)
    splash = label_counts.get('splash', 0)
    
    if total > 0:
        results.append(f"\n{manifest.name}:")
        results.append(f"  Total events: {total:,}")
        results.append(f"  China: {china:,}")
        results.append(f"  Splash: {splash:,}")
        
        # List all labels
        results.append(f"  All labels: {dict(sorted(label_counts.items(), key=lambda x: -x[1]))}")

# Write to file
with open(output_file, 'w') as f:
    f.write('\n'.join(results))

print(f"Report written to {output_file}")
