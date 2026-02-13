#!/usr/bin/env python3
"""
Discover Multi-Label Data Sources

Scans drives for existing datasets that may contain multi-label drum annotations:
- MIDI files with simultaneous drum hits
- Annotations with overlapping timestamps
- Multi-track drum recordings

Usage:
    python discover_multilabel_sources.py --drives D: F:
    python discover_multilabel_sources.py --drives "D:/Cold_Raw_Data" "F:/ML_Data"
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re

# Known dataset patterns that typically contain multi-label data
KNOWN_MULTILABEL_DATASETS = {
    "e-gmd": {
        "description": "Expanded Groove MIDI Dataset - MIDI with full drum kit",
        "patterns": ["e-gmd", "expanded_groove", "groove_midi"],
        "midi_based": True,
    },
    "groove_midi": {
        "description": "Groove MIDI Dataset - Professional drummer MIDI",
        "patterns": ["groove-midi", "groove_midi", "magenta-groove"],
        "midi_based": True,
    },
    "mdb_drums": {
        "description": "MDB Drums - Multi-track isolated drums",
        "patterns": ["mdb_drums", "mdb-drums", "medleydb"],
        "midi_based": False,
    },
    "enst_drums": {
        "description": "ENST Drums - Isolated + mix recordings",
        "patterns": ["enst", "enst_drums", "enst-drums"],
        "midi_based": False,
    },
    "idmt_smt_drums": {
        "description": "IDMT-SMT-Drums - Annotated drum loops",
        "patterns": ["idmt", "idmt_smt", "idmt-smt"],
        "midi_based": False,
    },
    "rbma_13": {
        "description": "RBMA 13 - Annotated drum breaks",
        "patterns": ["rbma", "rbma_13", "rbma-13"],
        "midi_based": False,
    },
    "slakh": {
        "description": "Slakh2100 - Synthesized multi-track with MIDI",
        "patterns": ["slakh", "slakh2100"],
        "midi_based": True,
    },
}

# File patterns that indicate multi-label annotations
ANNOTATION_PATTERNS = {
    "midi": [".mid", ".midi"],
    "json": [".json"],
    "csv": [".csv"],
    "txt": [".txt"],
    "xml": [".xml"],
    "lab": [".lab"],
    "jams": [".jams"],
}


def scan_directory_structure(root_path: Path, max_depth: int = 4) -> Dict:
    """Scan directory structure for dataset-like folders."""
    results = {
        "datasets_found": [],
        "midi_locations": [],
        "annotation_locations": [],
        "audio_locations": [],
        "potential_multilabel": [],
    }
    
    if not root_path.exists():
        print(f"  ⚠️  Path does not exist: {root_path}")
        return results
    
    def scan_recursive(path: Path, depth: int = 0):
        if depth > max_depth:
            return
        
        try:
            items = list(path.iterdir())
        except PermissionError:
            return
        except Exception as e:
            return
        
        dir_name_lower = path.name.lower()
        
        # Check for known dataset names
        for dataset_id, info in KNOWN_MULTILABEL_DATASETS.items():
            for pattern in info["patterns"]:
                if pattern.lower() in dir_name_lower:
                    results["datasets_found"].append({
                        "path": str(path),
                        "dataset_id": dataset_id,
                        "description": info["description"],
                        "midi_based": info["midi_based"],
                    })
                    results["potential_multilabel"].append(str(path))
        
        # Count file types in this directory
        midi_count = 0
        json_count = 0
        audio_count = 0
        csv_count = 0
        
        for item in items:
            if item.is_file():
                suffix = item.suffix.lower()
                if suffix in [".mid", ".midi"]:
                    midi_count += 1
                elif suffix == ".json":
                    json_count += 1
                elif suffix == ".csv":
                    csv_count += 1
                elif suffix in [".wav", ".mp3", ".flac", ".ogg"]:
                    audio_count += 1
            elif item.is_dir():
                scan_recursive(item, depth + 1)
        
        # Report significant findings
        if midi_count > 10:
            results["midi_locations"].append({
                "path": str(path),
                "count": midi_count,
            })
        
        if json_count > 10 or csv_count > 10:
            results["annotation_locations"].append({
                "path": str(path),
                "json_count": json_count,
                "csv_count": csv_count,
            })
    
    scan_recursive(root_path)
    return results


def analyze_midi_for_multilabel(midi_path: Path, sample_limit: int = 100) -> Dict:
    """Analyze MIDI files to detect multi-label events (simultaneous drum hits)."""
    try:
        import mido
    except ImportError:
        return {"error": "mido not installed - run: pip install mido"}
    
    stats = {
        "files_analyzed": 0,
        "total_events": 0,
        "simultaneous_hits": 0,
        "max_simultaneous": 0,
        "simultaneous_by_count": defaultdict(int),
        "example_combinations": [],
    }
    
    midi_files = list(midi_path.glob("**/*.mid")) + list(midi_path.glob("**/*.midi"))
    midi_files = midi_files[:sample_limit]
    
    # Standard GM drum mapping
    GM_DRUM_MAP = {
        35: "kick", 36: "kick",
        38: "snare", 40: "snare",
        37: "cross_stick",
        42: "hihat_closed", 44: "hihat_pedal", 46: "hihat_open",
        49: "crash", 57: "crash",
        51: "ride_bow", 59: "ride_bow", 53: "ride_bell",
        41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom",
        52: "china", 55: "splash",
    }
    
    for midi_file in midi_files:
        try:
            mid = mido.MidiFile(midi_file)
            
            # Collect all note-on events with their absolute times
            events_by_time = defaultdict(list)
            abs_time = 0
            
            for track in mid.tracks:
                abs_time = 0
                for msg in track:
                    abs_time += msg.time
                    if msg.type == 'note_on' and msg.velocity > 0:
                        # Check if it's a drum note (channel 10 or in GM drum range)
                        if msg.channel == 9 or 35 <= msg.note <= 81:
                            drum_name = GM_DRUM_MAP.get(msg.note, f"drum_{msg.note}")
                            events_by_time[abs_time].append(drum_name)
            
            # Count simultaneous events
            for time, drums in events_by_time.items():
                stats["total_events"] += 1
                if len(drums) > 1:
                    stats["simultaneous_hits"] += 1
                    stats["simultaneous_by_count"][len(drums)] += 1
                    stats["max_simultaneous"] = max(stats["max_simultaneous"], len(drums))
                    
                    # Record example combinations
                    combo = tuple(sorted(set(drums)))
                    if len(stats["example_combinations"]) < 20 and combo not in [tuple(c) for c in stats["example_combinations"]]:
                        stats["example_combinations"].append(list(combo))
            
            stats["files_analyzed"] += 1
            
        except Exception as e:
            continue
    
    return stats


def analyze_json_annotations(json_path: Path, sample_limit: int = 50) -> Dict:
    """Analyze JSON annotation files for multi-label events."""
    stats = {
        "files_analyzed": 0,
        "multilabel_events": 0,
        "total_events": 0,
        "example_structures": [],
        "potential_multilabel": False,
    }
    
    json_files = list(json_path.glob("**/*.json"))[:sample_limit]
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stats["files_analyzed"] += 1
            
            # Try to detect annotation structure
            if isinstance(data, list):
                # List of events
                for event in data[:100]:
                    if isinstance(event, dict):
                        # Check for multi-label indicators
                        if "labels" in event and isinstance(event["labels"], list):
                            if len(event["labels"]) > 1:
                                stats["multilabel_events"] += 1
                                stats["potential_multilabel"] = True
                            stats["total_events"] += 1
                        elif "instruments" in event and isinstance(event["instruments"], list):
                            if len(event["instruments"]) > 1:
                                stats["multilabel_events"] += 1
                                stats["potential_multilabel"] = True
                            stats["total_events"] += 1
                        elif "components" in event and isinstance(event["components"], list):
                            if len(event["components"]) > 1:
                                stats["multilabel_events"] += 1
                                stats["potential_multilabel"] = True
                            stats["total_events"] += 1
            
            # Record example structure
            if len(stats["example_structures"]) < 3:
                if isinstance(data, list) and len(data) > 0:
                    stats["example_structures"].append({
                        "file": json_file.name,
                        "sample": data[0] if isinstance(data[0], dict) else str(data[0])[:200],
                    })
                elif isinstance(data, dict):
                    stats["example_structures"].append({
                        "file": json_file.name,
                        "keys": list(data.keys())[:10],
                    })
                    
        except Exception as e:
            continue
    
    return stats


def check_existing_beatsight_data(drives: List[Path]) -> Dict:
    """Check for existing BeatSight processed data that might have multi-label info."""
    results = {
        "prod_datasets": [],
        "raw_datasets": [],
        "cached_features": [],
    }
    
    patterns_to_find = [
        "prod_v*",
        "prod_combined*", 
        "raw_*",
        "dataset_*",
        "*_multilabel*",
        "*_events*",
    ]
    
    for drive in drives:
        if not drive.exists():
            continue
            
        for pattern in patterns_to_find:
            matches = list(drive.glob(f"**/{pattern}"))[:20]  # Limit to avoid slowness
            for match in matches:
                if match.is_dir():
                    # Check for BeatSight dataset indicators
                    has_components = (match / "components.json").exists()
                    has_labels = any(match.glob("*labels*.json")) or any(match.glob("*labels*.npy"))
                    has_cache = (match / "cache_mapping.npz").exists()
                    
                    if has_components or has_labels:
                        info = {
                            "path": str(match),
                            "has_components": has_components,
                            "has_labels": has_labels,
                            "has_cache": has_cache,
                        }
                        
                        # Try to read components.json
                        if has_components:
                            try:
                                with open(match / "components.json", 'r') as f:
                                    comp_data = json.load(f)
                                    if isinstance(comp_data, dict):
                                        info["num_classes"] = comp_data.get("num_classes")
                                        info["components"] = comp_data.get("components", [])[:5]
                            except:
                                pass
                        
                        results["prod_datasets"].append(info)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Discover multi-label data sources")
    parser.add_argument("--drives", nargs="+", default=["D:/", "F:/"],
                        help="Drives or paths to scan")
    parser.add_argument("--deep-scan", action="store_true",
                        help="Perform deep analysis of MIDI/JSON files")
    parser.add_argument("--max-depth", type=int, default=5,
                        help="Maximum directory depth to scan")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("Multi-Label Data Source Discovery")
    print("=" * 70)
    
    all_results = {
        "drives_scanned": args.drives,
        "known_datasets": [],
        "midi_sources": [],
        "annotation_sources": [],
        "beatsight_datasets": [],
        "recommendations": [],
    }
    
    # Scan each drive/path
    for drive in args.drives:
        drive_path = Path(drive)
        print(f"\n📂 Scanning: {drive_path}")
        
        if not drive_path.exists():
            print(f"   ⚠️  Path does not exist, skipping...")
            continue
        
        # Basic structure scan
        results = scan_directory_structure(drive_path, max_depth=args.max_depth)
        
        # Report known datasets found
        if results["datasets_found"]:
            print(f"\n   ✅ Known Multi-Label Datasets Found:")
            for ds in results["datasets_found"]:
                print(f"      • {ds['dataset_id']}: {ds['path']}")
                print(f"        {ds['description']}")
                all_results["known_datasets"].append(ds)
        
        # Report MIDI locations
        if results["midi_locations"]:
            print(f"\n   🎵 MIDI File Locations:")
            for loc in results["midi_locations"][:10]:
                print(f"      • {loc['path']} ({loc['count']} files)")
                all_results["midi_sources"].append(loc)
                
                # Deep analysis if requested
                if args.deep_scan:
                    print(f"        Analyzing MIDI files...")
                    midi_stats = analyze_midi_for_multilabel(Path(loc["path"]))
                    if "error" not in midi_stats:
                        pct = (midi_stats["simultaneous_hits"] / max(1, midi_stats["total_events"])) * 100
                        print(f"        → {midi_stats['simultaneous_hits']:,} simultaneous hits ({pct:.1f}%)")
                        print(f"        → Max simultaneous: {midi_stats['max_simultaneous']} drums")
                        if midi_stats["example_combinations"]:
                            print(f"        → Examples: {midi_stats['example_combinations'][:5]}")
                        loc["midi_analysis"] = midi_stats
        
        # Report annotation locations
        if results["annotation_locations"]:
            print(f"\n   📋 Annotation File Locations:")
            for loc in results["annotation_locations"][:10]:
                print(f"      • {loc['path']} (json:{loc['json_count']}, csv:{loc['csv_count']})")
                all_results["annotation_sources"].append(loc)
    
    # Check for existing BeatSight data
    print(f"\n📊 Checking for existing BeatSight datasets...")
    beatsight_data = check_existing_beatsight_data([Path(d) for d in args.drives])
    
    if beatsight_data["prod_datasets"]:
        print(f"\n   ✅ BeatSight Datasets Found:")
        for ds in beatsight_data["prod_datasets"][:10]:
            print(f"      • {ds['path']}")
            if ds.get("num_classes"):
                print(f"        Classes: {ds['num_classes']}")
            all_results["beatsight_datasets"].append(ds)
    
    # Generate recommendations
    print(f"\n" + "=" * 70)
    print("📋 RECOMMENDATIONS")
    print("=" * 70)
    
    recommendations = []
    
    if all_results["known_datasets"]:
        midi_datasets = [d for d in all_results["known_datasets"] if d.get("midi_based")]
        if midi_datasets:
            rec = {
                "priority": "HIGH",
                "action": "Extract multi-label from MIDI",
                "datasets": [d["path"] for d in midi_datasets],
                "reason": "MIDI files contain exact timing of all simultaneous drum hits",
            }
            recommendations.append(rec)
            print(f"\n🔴 HIGH PRIORITY: Extract multi-label data from MIDI datasets")
            for d in midi_datasets:
                print(f"   • {d['path']}")
            print(f"   Reason: MIDI has precise timing of all simultaneous drum hits")
    
    if all_results["midi_sources"]:
        rec = {
            "priority": "MEDIUM",
            "action": "Analyze MIDI files for multi-label extraction",
            "locations": [s["path"] for s in all_results["midi_sources"][:5]],
            "reason": "MIDI files may contain multi-label drum data",
        }
        recommendations.append(rec)
        print(f"\n🟡 MEDIUM PRIORITY: Analyze other MIDI sources")
        for s in all_results["midi_sources"][:5]:
            print(f"   • {s['path']} ({s['count']} files)")
    
    all_results["recommendations"] = recommendations
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {output_path}")
    
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Known datasets found: {len(all_results['known_datasets'])}")
    print(f"MIDI sources found: {len(all_results['midi_sources'])}")
    print(f"BeatSight datasets found: {len(all_results['beatsight_datasets'])}")
    
    if not all_results["known_datasets"] and not all_results["midi_sources"]:
        print(f"\n⚠️  No obvious multi-label sources found.")
        print(f"   The synthetic generation approach may be the best option.")
        print(f"   Alternatively, you could download E-GMD or Groove MIDI datasets.")
    
    return all_results


if __name__ == "__main__":
    main()
