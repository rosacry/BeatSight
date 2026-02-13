#!/usr/bin/env python3
"""
Audit all manifest files for class label consistency.
Checks for:
1. Missing expected drum classes (china, splash, rimshot, etc.)
2. Unexpected/misspelled class names
3. Class distribution per manifest
4. Possible label mappings/aliases
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import sys

# Expected 12-class taxonomy (rimshot merged into snare)
EXPECTED_CLASSES = {
    'kick', 'snare', 'hihat', 'tom', 'crash', 'ride',
    'china', 'splash', 'cross_stick', 'clap', 'cowbell', 
    'shaker', 'tambourine'
}

# Common aliases/variations to check
KNOWN_ALIASES = {
    # China cymbal variations
    'china_cymbal': 'china',
    'chinese_cymbal': 'china',
    'chinese': 'china',
    'china-type': 'china',
    
    # Splash cymbal variations
    'splash_cymbal': 'splash',
    'splash-cymbal': 'splash',
    
    # Rimshot variations (now mapped to snare, rimshot detection via post-processing)
    'rim_shot': 'snare',
    'rim-shot': 'snare',
    'rim': 'snare',
    'snare_rim': 'snare',
    'snare-rim': 'snare',
    'rimshot': 'snare',
    # Cross-stick remains separate (distinct woody sound)
    'cross_stick': 'cross_stick',
    'cross-stick': 'cross_stick',
    'sidestick': 'cross_stick',
    'side_stick': 'cross_stick',
    'side-stick': 'cross_stick',
    'xstick': 'cross_stick',
    
    # Hihat variations
    'hi-hat': 'hihat',
    'hi_hat': 'hihat',
    'closed_hihat': 'hihat',
    'open_hihat': 'hihat',
    'pedal_hihat': 'hihat',
    'hihat_closed': 'hihat',
    'hihat_open': 'hihat',
    'hihat_pedal': 'hihat',
    'hh': 'hihat',
    'hhc': 'hihat',
    'hho': 'hihat',
    'hhp': 'hihat',
    
    # Tom variations
    'tom_high': 'tom',
    'tom_mid': 'tom',
    'tom_low': 'tom',
    'tom_floor': 'tom',
    'high_tom': 'tom',
    'mid_tom': 'tom',
    'low_tom': 'tom',
    'floor_tom': 'tom',
    'tom1': 'tom',
    'tom2': 'tom',
    'tom3': 'tom',
    'tom4': 'tom',
    
    # Kick variations
    'bass_drum': 'kick',
    'bass-drum': 'kick',
    'bassdrum': 'kick',
    'bd': 'kick',
    
    # Snare variations
    'sd': 'snare',
    'snare_drum': 'snare',
    
    # Crash variations
    'crash_cymbal': 'crash',
    'crash-cymbal': 'crash',
    
    # Ride variations
    'ride_cymbal': 'ride',
    'ride_bell': 'ride',
    'ride-cymbal': 'ride',
    'ride-bell': 'ride',
    
    # Other cymbals that might be china/splash
    'effects_cymbal': 'china',  # Often china-type
    'fx_cymbal': 'china',
    'trash_cymbal': 'china',
    'bell': 'ride',  # ride bell
    'cymbal': None,  # Ambiguous - needs manual check
    
    # Percussion
    'handclap': 'clap',
    'hand_clap': 'clap',
    'claps': 'clap',
}


def load_jsonl(filepath: Path, max_records: int = 100000) -> tuple:
    """Load JSONL file and return (records, total_count). Samples very large files."""
    import os
    
    # Estimate file size - if > 100MB, sample
    file_size = os.path.getsize(filepath)
    sample_mode = file_size > 100 * 1024 * 1024  # 100MB
    
    records = []
    total_count = 0
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            total_count += 1
            # For large files, only read first N records + sample
            if sample_mode and total_count > max_records:
                # Just count remaining lines
                continue
            
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    if sample_mode:
        print(f"  [Large file: read {len(records):,} of {total_count:,} records]")
    
    return records, total_count


def extract_labels(records: list) -> Counter:
    """Extract all unique labels from records."""
    labels = Counter()
    for rec in records:
        # Try common label field names
        label = rec.get('label') or rec.get('instrument') or rec.get('class') or rec.get('drum_type')
        
        # Also check components array (BeatSight manifest format)
        if not label and 'components' in rec:
            components = rec.get('components', [])
            if components and isinstance(components, list):
                for comp in components:
                    if isinstance(comp, dict):
                        comp_label = comp.get('label')
                        if comp_label:
                            labels[comp_label.lower().strip()] += 1
                continue  # Already counted from components
        
        if label:
            labels[label.lower().strip()] += 1
    return labels


def audit_manifest(filepath: Path) -> dict:
    """Audit a single manifest file."""
    print(f"\n{'='*60}")
    print(f"Auditing: {filepath.name}")
    print(f"{'='*60}")
    
    records, total_count = load_jsonl(filepath)
    if not records:
        print("  [EMPTY] No records found!")
        return {'file': filepath.name, 'total': 0, 'labels': {}, 'issues': ['Empty file']}
    
    print(f"  Total records: {len(records):,}")
    
    labels = extract_labels(records)
    print(f"  Unique labels: {len(labels)}")
    
    results = {
        'file': filepath.name,
        'total': len(records),
        'labels': dict(labels),
        'issues': [],
        'missing_classes': [],
        'unknown_labels': [],
        'potential_aliases': {}
    }
    
    # Check for expected classes
    found_classes = set()
    for label in labels:
        normalized = label.lower().replace('-', '_').replace(' ', '_')
        if normalized in EXPECTED_CLASSES:
            found_classes.add(normalized)
        elif normalized in KNOWN_ALIASES:
            target = KNOWN_ALIASES[normalized]
            if target:
                found_classes.add(target)
                results['potential_aliases'][label] = target
    
    # Check what's missing
    missing = EXPECTED_CLASSES - found_classes
    if missing:
        results['missing_classes'] = list(missing)
    
    # Check for unknown labels
    for label in labels:
        normalized = label.lower().replace('-', '_').replace(' ', '_')
        if normalized not in EXPECTED_CLASSES and normalized not in KNOWN_ALIASES:
            results['unknown_labels'].append(label)
    
    # Print distribution
    print("\n  Class Distribution:")
    for label, count in sorted(labels.items(), key=lambda x: -x[1])[:20]:
        pct = 100 * count / len(records)
        bar = '#' * int(pct / 5)  # ASCII-safe bar
        mapped = KNOWN_ALIASES.get(label, label)
        mapping_note = f" -> {mapped}" if mapped != label and mapped else ""
        print(f"    {label:20s}: {count:>10,} ({pct:5.1f}%) {bar}{mapping_note}")
    
    if len(labels) > 20:
        print(f"    ... and {len(labels) - 20} more labels")
    
    # Report issues
    if results['missing_classes']:
        print(f"\n  [!] MISSING expected classes: {', '.join(sorted(results['missing_classes']))}")
    
    if results['unknown_labels']:
        print(f"\n  [?] Unknown labels: {', '.join(results['unknown_labels'][:10])}")
        if len(results['unknown_labels']) > 10:
            print(f"     ... and {len(results['unknown_labels']) - 10} more")
    
    if results['potential_aliases']:
        print(f"\n  [>] Potential remapping needed:")
        for orig, target in results['potential_aliases'].items():
            print(f"     '{orig}' -> '{target}'")
    
    return results


def main():
    manifest_dir = Path(__file__).parent.parent / 'data' / 'manifests'
    
    if not manifest_dir.exists():
        print(f"ERROR: Manifest directory not found: {manifest_dir}")
        sys.exit(1)
    
    manifest_files = list(manifest_dir.glob('*_events.jsonl'))
    
    print(f"Found {len(manifest_files)} manifest files")
    print("="*60)
    
    all_results = []
    global_labels = Counter()
    global_by_source = defaultdict(Counter)
    
    for mf in sorted(manifest_files):
        result = audit_manifest(mf)
        all_results.append(result)
        
        # Aggregate
        for label, count in result['labels'].items():
            global_labels[label] += count
            source = mf.stem.replace('_events', '')
            global_by_source[source][label] = count
    
    # Global summary
    print("\n" + "="*60)
    print("GLOBAL SUMMARY")
    print("="*60)
    
    total_samples = sum(r['total'] for r in all_results)
    print(f"\nTotal samples across all manifests: {total_samples:,}")
    print(f"Total unique labels: {len(global_labels)}")
    
    # Check rare classes specifically
    print("\n[TARGET] RARE CLASS STATUS (china, splash):")
    for target_class in ['china', 'splash']:
        count = 0
        sources = []
        for label, c in global_labels.items():
            normalized = label.lower().replace('-', '_').replace(' ', '_')
            if normalized == target_class or KNOWN_ALIASES.get(normalized) == target_class:
                count += c
                # Find which sources have it
                for source, labels in global_by_source.items():
                    if label in labels:
                        sources.append(f"{source}({labels[label]:,})")
        
        if count > 0:
            print(f"  [OK] {target_class}: {count:,} samples from {', '.join(sources)}")
        else:
            print(f"  [MISSING] {target_class}: NOT FOUND in any manifest!")
            # Check for potential aliases
            potential = []
            for label in global_labels:
                if target_class[:4] in label.lower():
                    potential.append(f"'{label}' ({global_labels[label]:,})")
            if potential:
                print(f"      Potential matches: {', '.join(potential)}")
    
    # All labels sorted by count
    print("\n[STATS] ALL LABELS (sorted by frequency):")
    for label, count in global_labels.most_common():
        pct = 100 * count / total_samples
        in_expected = "[Y]" if label in EXPECTED_CLASSES else ""
        alias = KNOWN_ALIASES.get(label, "")
        alias_note = f" -> {alias}" if alias else ""
        print(f"  {label:25s}: {count:>10,} ({pct:6.2f}%) {in_expected}{alias_note}")
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    all_missing = set()
    for r in all_results:
        all_missing.update(r['missing_classes'])
    
    if all_missing:
        print(f"\n[RED] Classes missing from ALL manifests: {', '.join(sorted(all_missing))}")
        print("   -> Need to acquire data from external sources")
    
    aliases_to_apply = {}
    for r in all_results:
        aliases_to_apply.update(r['potential_aliases'])
    
    if aliases_to_apply:
        print(f"\n[YELLOW] Suggested label remappings:")
        for orig, target in aliases_to_apply.items():
            orig_count = global_labels.get(orig, 0)
            print(f"   '{orig}' ({orig_count:,}) -> '{target}'")


if __name__ == '__main__':
    main()
