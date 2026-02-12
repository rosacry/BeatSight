import json
from collections import defaultdict

rare_classes = ['china', 'splash', 'rimshot']
rare_by_source = defaultdict(lambda: defaultdict(int))
total_rare = defaultdict(int)

print("Scanning manifest...")
with open('training/data/manifests/prod_combined_events.jsonl', 'r') as f:
    for i, line in enumerate(f):
        if i % 1000000 == 0:
            print(f"  {i:,} lines...")
        try:
            d = json.loads(line)
            label = d.get('label', '')
            if label in rare_classes:
                src = d.get('source_set', 'unknown')
                rare_by_source[label][src] += 1
                total_rare[label] += 1
        except: 
            pass

print('\n=== RARE CLASS SOURCES ===')
for label in rare_classes:
    print(f'\n{label.upper()} ({total_rare[label]:,} total):')
    for src, count in sorted(rare_by_source[label].items(), key=lambda x: -x[1]):
        print(f'  {src}: {count:,}')
