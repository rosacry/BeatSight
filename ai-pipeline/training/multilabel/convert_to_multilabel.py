#!/usr/bin/env python3
"""
Convert Single-Label Dataset to Multi-Label Format

This script converts existing single-label drum classification datasets
to the multi-label format that supports simultaneous drum hits.

The key change is converting:
    {"file": "audio.wav", "component_idx": 9}
To:
    {"file": "audio.wav", "components": [{"label": "kick", "velocity": 1.0}]}

For datasets that already have components arrays (from MIDI sources like
Groove MIDI or Slakh), this script validates and enriches the data.

Usage:
    python convert_to_multilabel.py --input labels.json --output labels_multilabel.json
    
    # Also merge nearby onsets that should be simultaneous
    python convert_to_multilabel.py --input labels.json --output labels_merged.json \
        --merge-threshold 0.03  # 30ms
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False


# Default drum components (should match components.json)
DEFAULT_COMPONENTS = [
    "aux_percussion",
    "china",
    "crash",
    "cross_stick",
    "hihat_closed",
    "hihat_foot_splash",
    "hihat_open",
    "hihat_pedal",
    "hihat_splash",
    "kick",
    "ride_bell",
    "ride_bow",
    "rimshot",
    "snare",
    "snare_center",
    "snare_cross_stick",
    "snare_rimshot",
    "splash",
    "tom_high",
    "tom_low",
    "tom_mid",
]


def load_json(path: Path) -> Any:
    """Load JSON file with optional orjson acceleration."""
    if HAS_ORJSON and orjson is not None:
        with open(path, 'rb') as f:
            return orjson.loads(f.read())
    else:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)


def save_json(data: Any, path: Path, indent: bool = True) -> None:
    """Save data as JSON."""
    with open(path, 'w', encoding='utf-8') as f:
        if indent:
            json.dump(data, f, indent=2)
        else:
            json.dump(data, f)


def load_components_mapping(dataset_dir: Path) -> List[str]:
    """Load component names from components.json if it exists."""
    components_path = dataset_dir / "components.json"
    if components_path.exists():
        return load_json(components_path)
    return DEFAULT_COMPONENTS


def convert_single_to_multilabel(
    item: Dict[str, Any],
    component_names: List[str]
) -> Dict[str, Any]:
    """
    Convert a single-label item to multi-label format.
    
    Single-label:
        {"file": "audio.wav", "component_idx": 9}
    
    Multi-label:
        {"file": "audio.wav", "components": [{"label": "kick", "velocity": 1.0}]}
    """
    result = {}
    
    # Copy file path (support both 'file' and 'audio_path' keys)
    if 'audio_path' in item:
        result['audio_path'] = item['audio_path']
    elif 'file' in item:
        result['audio_path'] = item['file']
    else:
        raise ValueError(f"No file path found in item: {item}")
    
    # Check if already has components array
    if 'components' in item and isinstance(item['components'], list):
        # Already multi-label format, just validate/copy
        components = []
        for comp in item['components']:
            if isinstance(comp, dict):
                components.append({
                    'label': comp.get('label', 'unknown'),
                    'velocity': comp.get('velocity', 1.0),
                })
            elif isinstance(comp, str):
                components.append({'label': comp, 'velocity': 1.0})
        result['components'] = components
    elif 'component_idx' in item:
        # Single-label format - convert
        idx = int(item['component_idx'])
        label = component_names[idx] if idx < len(component_names) else f"class_{idx}"
        result['components'] = [{
            'label': label,
            'velocity': item.get('velocity', 1.0)
        }]
    elif 'component' in item:
        # Has component name directly
        result['components'] = [{
            'label': item['component'],
            'velocity': item.get('velocity', 1.0)
        }]
    else:
        raise ValueError(f"No label information found in item: {item}")
    
    # Copy metadata
    for key in ['onset_time', 'session_id', 'drummer_id', 'kit_id',
                'source_set', 'techniques', 'bleed_level', 'sample_id']:
        if key in item:
            result[key] = item[key]
    
    return result


def merge_nearby_onsets(
    items: List[Dict[str, Any]],
    threshold_seconds: float = 0.03
) -> List[Dict[str, Any]]:
    """
    Merge items with nearby onset times into single multi-label samples.
    
    This handles cases where kick and hi-hat are labeled as separate samples
    but occur at nearly the same time and should be a single hit.
    
    Args:
        items: List of labeled items
        threshold_seconds: Maximum time difference to consider simultaneous
    
    Returns:
        Merged list with fewer items (simultaneous hits combined)
    """
    if not items:
        return items
    
    # Sort by onset time (if available)
    has_onset = all('onset_time' in item for item in items)
    if not has_onset:
        print("Warning: No onset_time in items, cannot merge nearby onsets")
        return items
    
    sorted_items = sorted(items, key=lambda x: x['onset_time'])
    
    # Group by audio file and session
    def get_group_key(item: Dict) -> str:
        session = item.get('session_id', 'default')
        audio = item.get('audio_path', '')
        # Group by session - onsets near each other in same session get merged
        return session
    
    groups = defaultdict(list)
    for item in sorted_items:
        groups[get_group_key(item)].append(item)
    
    merged_items = []
    
    for group_key, group_items in groups.items():
        i = 0
        while i < len(group_items):
            current = group_items[i]
            current_time = current['onset_time']
            
            # Find all items within threshold
            to_merge = [current]
            j = i + 1
            
            while j < len(group_items):
                next_item = group_items[j]
                if next_item['onset_time'] - current_time <= threshold_seconds:
                    to_merge.append(next_item)
                    j += 1
                else:
                    break
            
            if len(to_merge) == 1:
                # No merge needed
                merged_items.append(current)
            else:
                # Merge components from all items
                merged = {
                    'audio_path': current['audio_path'],
                    'onset_time': current_time,
                    'components': [],
                }
                
                # Collect unique components
                seen_labels = set()
                for item in to_merge:
                    for comp in item.get('components', []):
                        label = comp.get('label')
                        if label and label not in seen_labels:
                            merged['components'].append(comp)
                            seen_labels.add(label)
                
                # Copy metadata from first item
                for key in ['session_id', 'drummer_id', 'kit_id', 'source_set']:
                    if key in current:
                        merged[key] = current[key]
                
                # Combine techniques
                all_techniques = set()
                for item in to_merge:
                    for tech in item.get('techniques', []):
                        all_techniques.add(tech)
                if all_techniques:
                    merged['techniques'] = list(all_techniques)
                
                merged_items.append(merged)
            
            i = j
    
    return merged_items


def analyze_dataset(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze multi-label dataset and return statistics."""
    stats = {
        'total_samples': len(items),
        'single_label': 0,
        'multi_label': 0,
        'class_counts': defaultdict(int),
        'label_count_distribution': defaultdict(int),
        'cooccurrence': defaultdict(lambda: defaultdict(int)),
    }
    
    for item in items:
        components = item.get('components', [])
        labels = [c.get('label') for c in components if c.get('label')]
        
        num_labels = len(labels)
        stats['label_count_distribution'][num_labels] += 1
        
        if num_labels == 1:
            stats['single_label'] += 1
        else:
            stats['multi_label'] += 1
        
        for label in labels:
            stats['class_counts'][label] += 1
        
        # Track co-occurrences
        for i, label1 in enumerate(labels):
            for label2 in labels[i+1:]:
                key = tuple(sorted([label1, label2]))
                stats['cooccurrence'][key[0]][key[1]] += 1
    
    # Convert defaultdicts to regular dicts
    stats['class_counts'] = dict(stats['class_counts'])
    stats['label_count_distribution'] = dict(stats['label_count_distribution'])
    stats['cooccurrence'] = {k: dict(v) for k, v in stats['cooccurrence'].items()}
    
    return stats


def print_statistics(stats: Dict[str, Any]) -> None:
    """Print dataset statistics in a readable format."""
    print(f"\n{'='*60}")
    print("Multi-Label Dataset Statistics")
    print(f"{'='*60}")
    print(f"Total samples: {stats['total_samples']:,}")
    print(f"Single-label:  {stats['single_label']:,} ({100*stats['single_label']/stats['total_samples']:.1f}%)")
    print(f"Multi-label:   {stats['multi_label']:,} ({100*stats['multi_label']/stats['total_samples']:.1f}%)")
    
    print(f"\nLabels per sample distribution:")
    for num_labels, count in sorted(stats['label_count_distribution'].items()):
        pct = 100 * count / stats['total_samples']
        print(f"  {num_labels} labels: {count:,} ({pct:.1f}%)")
    
    print(f"\nPer-class counts:")
    print(f"{'Class':<25} {'Count':>8} {'%':>8}")
    print(f"{'-'*45}")
    for label, count in sorted(stats['class_counts'].items(), key=lambda x: -x[1]):
        pct = 100 * count / stats['total_samples']
        print(f"{label:<25} {count:>8,} {pct:>7.1f}%")
    
    if stats['cooccurrence']:
        print(f"\nTop 10 co-occurring pairs:")
        pairs = []
        for label1, label2_counts in stats['cooccurrence'].items():
            for label2, count in label2_counts.items():
                pairs.append((label1, label2, count))
        pairs.sort(key=lambda x: -x[2])
        for label1, label2, count in pairs[:10]:
            print(f"  {label1} + {label2}: {count:,}")
    
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert single-label dataset to multi-label format"
    )
    
    parser.add_argument('--input', '-i', type=str, required=True,
                        help='Input labels file (JSON or JSONL)')
    parser.add_argument('--output', '-o', type=str, required=True,
                        help='Output labels file')
    parser.add_argument('--dataset-dir', type=str, default=None,
                        help='Dataset directory (for components.json)')
    parser.add_argument('--merge-threshold', type=float, default=None,
                        help='Merge onsets within this many seconds (e.g., 0.03 for 30ms)')
    parser.add_argument('--format', type=str, choices=['json', 'jsonl'], default='json',
                        help='Output format')
    parser.add_argument('--stats-only', action='store_true',
                        help='Only print statistics, do not save')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    # Load component names
    if args.dataset_dir:
        dataset_dir = Path(args.dataset_dir)
    else:
        dataset_dir = input_path.parent
    component_names = load_components_mapping(dataset_dir)
    print(f"Using {len(component_names)} component names")
    
    # Load input data
    print(f"Loading {input_path}...")
    if input_path.suffix == '.jsonl':
        items = []
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
    else:
        items = load_json(input_path)
    
    print(f"Loaded {len(items):,} items")
    
    # Convert to multi-label format
    print("Converting to multi-label format...")
    converted = []
    for item in items:
        try:
            converted.append(convert_single_to_multilabel(item, component_names))
        except ValueError as e:
            print(f"Warning: Skipping invalid item: {e}")
    
    print(f"Converted {len(converted):,} items")
    
    # Optionally merge nearby onsets
    if args.merge_threshold is not None:
        print(f"Merging onsets within {args.merge_threshold*1000:.0f}ms...")
        before_count = len(converted)
        converted = merge_nearby_onsets(converted, args.merge_threshold)
        after_count = len(converted)
        print(f"Merged {before_count - after_count:,} samples")
        print(f"Final count: {after_count:,}")
    
    # Analyze and print statistics
    stats = analyze_dataset(converted)
    print_statistics(stats)
    
    # Save output
    if not args.stats_only:
        print(f"Saving to {output_path}...")
        
        if args.format == 'jsonl':
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in converted:
                    f.write(json.dumps(item) + '\n')
        else:
            save_json(converted, output_path)
        
        # Also save statistics
        stats_path = output_path.with_suffix('.stats.json')
        save_json(stats, stats_path)
        
        print(f"Output saved to: {output_path}")
        print(f"Statistics saved to: {stats_path}")
    
    print("Done!")


if __name__ == '__main__':
    main()
