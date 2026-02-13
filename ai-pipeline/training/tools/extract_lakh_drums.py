#!/usr/bin/env python3
"""
Extract drum events from Lakh MIDI Dataset.

This script parses MIDI files and extracts drum events, particularly focusing
on rare classes (china, splash, rimshot/sidestick) that are underrepresented
in the current training data.

Usage:
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --output drum_events.jsonl
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --output drum_events.jsonl --stats-only
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib

try:
    import mido
except ImportError:
    print("ERROR: mido not installed. Run: pip install mido")
    sys.exit(1)

# General MIDI Drum Map (Channel 10, notes 35-81)
# Reference: https://www.midi.org/specifications-old/item/gm-level-1-sound-set
GM_DRUM_MAP = {
    # Bass Drums
    35: "kick",           # Acoustic Bass Drum
    36: "kick",           # Bass Drum 1
    
    # Snare & Variants
    38: "snare",          # Acoustic Snare
    40: "snare",          # Electric Snare
    37: "cross_stick",    # Side Stick / Rimshot (cross-stick)
    
    # Hi-Hat
    42: "hihat_closed",   # Closed Hi-Hat
    44: "hihat_pedal",    # Pedal Hi-Hat
    46: "hihat_open",     # Open Hi-Hat
    
    # Toms
    41: "tom",            # Low Floor Tom
    43: "tom",            # High Floor Tom
    45: "tom",            # Low Tom
    47: "tom",            # Low-Mid Tom
    48: "tom",            # Hi-Mid Tom
    50: "tom",            # High Tom
    
    # Cymbals - Crash
    49: "crash",          # Crash Cymbal 1
    57: "crash",          # Crash Cymbal 2
    
    # Cymbals - Ride
    51: "ride_bow",       # Ride Cymbal 1 (bow)
    59: "ride_bow",       # Ride Cymbal 2
    53: "ride_bell",      # Ride Bell
    
    # RARE CLASSES - What we need most!
    52: "china",          # Chinese Cymbal - RARE!
    55: "splash",         # Splash Cymbal - RARE!
    
    # Other percussion (less relevant but included for completeness)
    39: "clap",           # Hand Clap
    54: "cowbell",        # Tambourine (mapped to cowbell for our purposes)
    56: "cowbell",        # Cowbell
    
    # Additional variations
    58: "crash",          # Vibraslap (sometimes used as effect)
}

# Our target classes (matching components.json) - 12 classes (rimshot merged into snare)
TARGET_CLASSES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare",
    "splash", "tom"
]

# Priority classes (rare in current dataset) - rimshot now handled via post-processing
RARE_CLASSES = ["china", "splash", "cross_stick"]


def parse_midi_file(midi_path: Path) -> Optional[Dict]:
    """Parse a single MIDI file and extract drum events."""
    try:
        mid = mido.MidiFile(midi_path)
    except Exception as e:
        return None
    
    drum_events = []
    tempo = 500000  # Default: 120 BPM
    ticks_per_beat = mid.ticks_per_beat or 480
    
    # Find drum track(s) - Channel 9 (0-indexed) = Channel 10 in MIDI convention
    for track_idx, track in enumerate(mid.tracks):
        absolute_time = 0
        current_tempo = tempo
        
        for msg in track:
            absolute_time += msg.time
            
            # Track tempo changes
            if msg.type == 'set_tempo':
                current_tempo = msg.tempo
            
            # Drum notes are on channel 9 (0-indexed)
            if msg.type == 'note_on' and msg.channel == 9 and msg.velocity > 0:
                note = msg.note
                if note in GM_DRUM_MAP:
                    # Convert ticks to seconds
                    time_seconds = mido.tick2second(
                        absolute_time, ticks_per_beat, current_tempo
                    )
                    
                    drum_class = GM_DRUM_MAP[note]
                    drum_events.append({
                        "time": round(time_seconds, 4),
                        "note": note,
                        "velocity": msg.velocity,
                        "class": drum_class,
                        "track": track_idx,
                    })
    
    if not drum_events:
        return None
    
    # Sort by time
    drum_events.sort(key=lambda x: x["time"])
    
    # Get file duration
    duration = 0
    try:
        duration = mid.length
    except:
        if drum_events:
            duration = drum_events[-1]["time"] + 0.5
    
    return {
        "file": str(midi_path),
        "file_hash": hashlib.md5(midi_path.name.encode()).hexdigest()[:12],
        "duration": round(duration, 2),
        "ticks_per_beat": ticks_per_beat,
        "num_tracks": len(mid.tracks),
        "events": drum_events,
        "event_count": len(drum_events),
    }


def count_classes(midi_data: Dict) -> Counter:
    """Count drum classes in parsed MIDI data."""
    return Counter(e["class"] for e in midi_data["events"])


def scan_directory(midi_dir: Path, max_files: Optional[int] = None, 
                   verbose: bool = True) -> Tuple[List[Dict], Counter]:
    """Scan directory for MIDI files and extract drum events."""
    
    all_midi_data = []
    total_counts = Counter()
    files_with_drums = 0
    files_processed = 0
    files_failed = 0
    
    # Find all MIDI files
    midi_files = list(midi_dir.rglob("*.mid")) + list(midi_dir.rglob("*.midi"))
    
    if max_files:
        midi_files = midi_files[:max_files]
    
    total_files = len(midi_files)
    print(f"Found {total_files:,} MIDI files to process")
    
    for i, midi_path in enumerate(midi_files):
        if verbose and (i + 1) % 1000 == 0:
            print(f"  Processed {i+1:,}/{total_files:,} files "
                  f"({files_with_drums:,} with drums, {files_failed:,} failed)")
        
        result = parse_midi_file(midi_path)
        files_processed += 1
        
        if result is None:
            files_failed += 1
            continue
        
        if result["events"]:
            files_with_drums += 1
            all_midi_data.append(result)
            total_counts.update(count_classes(result))
    
    print(f"\nProcessing complete:")
    print(f"  Total files: {files_processed:,}")
    print(f"  Files with drums: {files_with_drums:,}")
    print(f"  Files failed/no drums: {files_failed + (files_processed - files_with_drums):,}")
    
    return all_midi_data, total_counts


def print_statistics(counts: Counter, title: str = "Drum Event Statistics"):
    """Print formatted statistics."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")
    
    total = sum(counts.values())
    print(f"Total drum events: {total:,}\n")
    
    # Sort by count
    sorted_counts = sorted(counts.items(), key=lambda x: -x[1])
    
    print(f"{'Class':<20} {'Count':>12} {'Percentage':>10} {'Status':<15}")
    print("-" * 60)
    
    for class_name, count in sorted_counts:
        pct = 100.0 * count / total if total > 0 else 0
        status = "[RARE!]" if class_name in RARE_CLASSES else ""
        if class_name in RARE_CLASSES and count > 10000:
            status = "[Good!]"
        print(f"{class_name:<20} {count:>12,} {pct:>9.2f}% {status:<15}")
    
    # Highlight rare classes
    print(f"\n{'='*60}")
    print(" RARE CLASS SUMMARY (china, splash, cross_stick, rimshot)")
    print(f"{'='*60}")
    
    for rare_class in RARE_CLASSES:
        count = counts.get(rare_class, 0)
        print(f"  {rare_class}: {count:,} events")
    
    rare_total = sum(counts.get(c, 0) for c in RARE_CLASSES)
    print(f"\n  Total rare class events: {rare_total:,}")
    print(f"  Percentage of total: {100.0 * rare_total / total if total else 0:.2f}%")


def filter_files_with_rare_classes(midi_data: List[Dict], 
                                   min_rare_events: int = 5) -> List[Dict]:
    """Filter to files that contain rare class events."""
    filtered = []
    for data in midi_data:
        counts = count_classes(data)
        rare_count = sum(counts.get(c, 0) for c in RARE_CLASSES)
        if rare_count >= min_rare_events:
            data["rare_class_count"] = rare_count
            data["rare_classes_present"] = [c for c in RARE_CLASSES if counts.get(c, 0) > 0]
            filtered.append(data)
    return filtered


def export_events(midi_data: List[Dict], output_path: Path, 
                  classes_filter: Optional[List[str]] = None):
    """Export drum events to JSONL format."""
    
    total_events = 0
    with open(output_path, 'w') as f:
        for data in midi_data:
            for event in data["events"]:
                if classes_filter and event["class"] not in classes_filter:
                    continue
                
                record = {
                    "midi_file": data["file"],
                    "file_hash": data["file_hash"],
                    "time": event["time"],
                    "note": event["note"],
                    "velocity": event["velocity"],
                    "class": event["class"],
                }
                f.write(json.dumps(record) + "\n")
                total_events += 1
    
    print(f"Exported {total_events:,} events to {output_path}")


def export_synthesis_list(midi_data: List[Dict], output_path: Path,
                          target_classes: Optional[List[str]] = None):
    """Export list of files suitable for synthesis, grouped by rare classes."""
    
    # Group files by which rare classes they contain
    by_rare_class = defaultdict(list)
    
    for data in midi_data:
        counts = count_classes(data)
        for rare_class in (target_classes or RARE_CLASSES):
            if counts.get(rare_class, 0) > 0:
                by_rare_class[rare_class].append({
                    "file": data["file"],
                    "event_count": counts[rare_class],
                    "total_events": data["event_count"],
                    "duration": data["duration"],
                })
    
    # Sort each list by event count (most events first)
    for rare_class in by_rare_class:
        by_rare_class[rare_class].sort(key=lambda x: -x["event_count"])
    
    output = {
        "summary": {
            "total_files": len(midi_data),
            "files_per_class": {k: len(v) for k, v in by_rare_class.items()},
            "events_per_class": {k: sum(f["event_count"] for f in v) 
                                 for k, v in by_rare_class.items()},
        },
        "files_by_class": dict(by_rare_class),
    }
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Exported synthesis list to {output_path}")
    print("\nFiles per rare class:")
    for cls, files in by_rare_class.items():
        total_events = sum(f["event_count"] for f in files)
        print(f"  {cls}: {len(files):,} files, {total_events:,} events")


def main():
    parser = argparse.ArgumentParser(
        description="Extract drum events from Lakh MIDI Dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scan and show statistics only
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --stats-only

    # Extract all drum events
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --output drum_events.jsonl

    # Extract only rare classes (china, splash, cross_stick)
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --output rare_events.jsonl --rare-only

    # Quick test with limited files
    python extract_lakh_drums.py --midi-dir /path/to/lmd_full --max-files 1000 --stats-only
        """
    )
    
    parser.add_argument("--midi-dir", type=Path, required=True,
                        help="Directory containing MIDI files (Lakh MIDI Dataset)")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSONL file for drum events")
    parser.add_argument("--synthesis-list", type=Path, default=None,
                        help="Output JSON file listing files good for synthesis")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only show statistics, don't export")
    parser.add_argument("--rare-only", action="store_true",
                        help="Only export rare class events (china, splash, cross_stick, rimshot)")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Limit number of files to process (for testing)")
    parser.add_argument("--min-rare-events", type=int, default=3,
                        help="Minimum rare events for a file to be included in synthesis list")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress output")
    
    args = parser.parse_args()
    
    if not args.midi_dir.exists():
        print(f"ERROR: Directory not found: {args.midi_dir}")
        sys.exit(1)
    
    print(f"Scanning MIDI files in: {args.midi_dir}")
    
    # Scan directory
    midi_data, total_counts = scan_directory(
        args.midi_dir, 
        max_files=args.max_files,
        verbose=not args.quiet
    )
    
    # Print statistics
    print_statistics(total_counts)
    
    if args.stats_only:
        print("\n[Stats only mode - no files exported]")
        return
    
    # Export events
    if args.output:
        classes_filter = RARE_CLASSES if args.rare_only else None
        export_events(midi_data, args.output, classes_filter)
    
    # Export synthesis list (files with rare classes)
    if args.synthesis_list:
        filtered = filter_files_with_rare_classes(midi_data, args.min_rare_events)
        export_synthesis_list(filtered, args.synthesis_list)
    
    # If no output specified but not stats-only, suggest next steps
    if not args.output and not args.synthesis_list:
        print("\n" + "="*60)
        print(" NEXT STEPS")
        print("="*60)
        print("To export events, run with --output:")
        print(f"  python {sys.argv[0]} --midi-dir {args.midi_dir} --output drum_events.jsonl")
        print("\nTo export synthesis list (files with rare classes):")
        print(f"  python {sys.argv[0]} --midi-dir {args.midi_dir} --synthesis-list synthesis_files.json")


if __name__ == "__main__":
    main()
