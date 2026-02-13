#!/usr/bin/env python3
"""
Enrich existing training labels with velocity information from source manifests.

This script reads the source manifests (egmd, groove_midi, slakh, etc.) which contain
velocity and dynamic_bucket information, and adds this data to the existing training
labels using the event_id as the join key.

Usage:
    python enrich_velocity.py --labels-path /path/to/train_labels.json --output /path/to/enriched_labels.json

For datasets where velocity is not available (e.g., medleydb which has no MIDI),
a default velocity of 0.7 (medium) is used.
"""

import argparse
import json
from pathlib import Path
from collections import defaultdict
import sys


def bucket_velocity(velocity: float) -> str:
    """Convert velocity (0.0-1.0) to dynamic bucket."""
    if velocity <= 0.25:
        return "ghost"
    elif velocity <= 0.5:
        return "light"
    elif velocity <= 0.8:
        return "medium"
    else:
        return "accent"


def load_manifests(manifest_dir: Path) -> dict:
    """
    Load all manifests and build event_id -> velocity lookup.
    
    Returns dict: event_id -> {velocity: float, dynamic_bucket: str, label_velocities: {label: velocity}}
    """
    velocity_lookup = {}
    
    manifest_files = list(manifest_dir.glob("*_events.jsonl"))
    print(f"Found {len(manifest_files)} manifest files in {manifest_dir}")
    
    for manifest_file in manifest_files:
        source = manifest_file.stem.replace("_events", "")
        count = 0
        velocity_count = 0
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    event_id = event.get('event_id')
                    if not event_id:
                        continue
                    
                    count += 1
                    
                    # Extract velocity per component label
                    label_velocities = {}
                    components = event.get('components', [])
                    
                    for comp in components:
                        label = comp.get('label')
                        velocity = comp.get('velocity')
                        dyn_bucket = comp.get('dynamic_bucket')
                        
                        if label and velocity is not None:
                            label_velocities[label] = {
                                'velocity': velocity,
                                'dynamic_bucket': dyn_bucket or bucket_velocity(velocity)
                            }
                            velocity_count += 1
                    
                    if label_velocities:
                        velocity_lookup[event_id] = {
                            'source': source,
                            'label_velocities': label_velocities
                        }
                        
                except json.JSONDecodeError:
                    continue
        
        print(f"  {source}: {count} events, {velocity_count} components with velocity")
    
    print(f"\nTotal events with velocity data: {len(velocity_lookup)}")
    return velocity_lookup


def enrich_labels(labels_path: Path, velocity_lookup: dict, output_path: Path):
    """
    Add velocity and dynamic_bucket to training labels.
    """
    print(f"\nLoading training labels from {labels_path}")
    
    with open(labels_path, 'r', encoding='utf-8') as f:
        labels = json.load(f)
    
    print(f"Total training entries: {len(labels)}")
    
    # Stats
    stats = {
        'total': len(labels),
        'enriched': 0,
        'missing_event': 0,
        'missing_label': 0,
        'default_velocity': 0,
        'by_source': defaultdict(lambda: {'total': 0, 'enriched': 0}),
        'by_bucket': defaultdict(int)
    }
    
    enriched_labels = []
    
    for entry in labels:
        event_id = entry.get('event_id')
        label = entry.get('label')
        source_set = entry.get('source_set', 'unknown')
        
        stats['by_source'][source_set]['total'] += 1
        
        # Create new entry with velocity
        new_entry = entry.copy()
        
        if event_id and event_id in velocity_lookup:
            event_data = velocity_lookup[event_id]
            label_velocities = event_data.get('label_velocities', {})
            
            if label in label_velocities:
                vel_data = label_velocities[label]
                new_entry['velocity'] = vel_data['velocity']
                new_entry['dynamic_bucket'] = vel_data['dynamic_bucket']
                stats['enriched'] += 1
                stats['by_source'][source_set]['enriched'] += 1
                stats['by_bucket'][vel_data['dynamic_bucket']] += 1
            else:
                # Event exists but label not found (shouldn't happen normally)
                new_entry['velocity'] = 0.7
                new_entry['dynamic_bucket'] = 'medium'
                stats['missing_label'] += 1
                stats['default_velocity'] += 1
                stats['by_bucket']['medium'] += 1
        else:
            # No velocity data available - use default (medium)
            new_entry['velocity'] = 0.7
            new_entry['dynamic_bucket'] = 'medium'
            stats['missing_event'] += 1
            stats['default_velocity'] += 1
            stats['by_bucket']['medium'] += 1
        
        enriched_labels.append(new_entry)
    
    # Write enriched labels
    print(f"\nWriting enriched labels to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_labels, f)
    
    # Print stats
    print("\n" + "="*60)
    print("ENRICHMENT SUMMARY")
    print("="*60)
    print(f"Total entries:           {stats['total']}")
    print(f"Enriched with velocity:  {stats['enriched']} ({100*stats['enriched']/stats['total']:.1f}%)")
    print(f"Default velocity used:   {stats['default_velocity']} ({100*stats['default_velocity']/stats['total']:.1f}%)")
    print(f"  - Missing event_id:    {stats['missing_event']}")
    print(f"  - Missing label:       {stats['missing_label']}")
    
    print("\nBy source set:")
    for source, data in sorted(stats['by_source'].items()):
        pct = 100 * data['enriched'] / data['total'] if data['total'] > 0 else 0
        print(f"  {source}: {data['enriched']}/{data['total']} enriched ({pct:.1f}%)")
    
    print("\nBy dynamic bucket:")
    for bucket in ['ghost', 'light', 'medium', 'accent']:
        count = stats['by_bucket'].get(bucket, 0)
        pct = 100 * count / stats['total'] if stats['total'] > 0 else 0
        print(f"  {bucket}: {count} ({pct:.1f}%)")
    
    return enriched_labels


def main():
    parser = argparse.ArgumentParser(description='Enrich training labels with velocity data')
    parser.add_argument('--labels-path', type=Path, required=True,
                       help='Path to train_labels.json')
    parser.add_argument('--manifests-dir', type=Path, 
                       default=Path(__file__).parent.parent / 'data' / 'manifests',
                       help='Path to manifests directory')
    parser.add_argument('--output', type=Path, required=True,
                       help='Output path for enriched labels')
    parser.add_argument('--in-place', action='store_true',
                       help='Modify labels file in place (creates .bak backup)')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.labels_path.exists():
        print(f"ERROR: Labels file not found: {args.labels_path}")
        sys.exit(1)
    
    if not args.manifests_dir.exists():
        print(f"ERROR: Manifests directory not found: {args.manifests_dir}")
        sys.exit(1)
    
    # Handle in-place mode
    if args.in_place:
        import shutil
        backup_path = args.labels_path.with_suffix('.json.bak_velocity')
        shutil.copy2(args.labels_path, backup_path)
        print(f"Created backup: {backup_path}")
        args.output = args.labels_path
    
    # Load manifests
    print("Loading velocity data from manifests...")
    velocity_lookup = load_manifests(args.manifests_dir)
    
    # Enrich labels
    enrich_labels(args.labels_path, velocity_lookup, args.output)
    
    print(f"\nDone! Enriched labels saved to: {args.output}")


if __name__ == '__main__':
    main()
