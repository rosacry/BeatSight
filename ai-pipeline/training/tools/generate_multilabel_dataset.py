#!/usr/bin/env python3
"""
Generate Multi-Label Training Dataset from MIDI-Aligned Sources

This script creates a proper multi-label dataset by grouping drum hits that
occur within a configurable time window (default: 30ms). This enables training
models that can detect simultaneous drum hits (kick + hi-hat, snare + crash, etc.)

The script:
1. Reads events from MIDI-aligned manifest files (Groove MIDI, E-GMD, Slakh, etc.)
2. Groups events by audio file and session
3. Merges events within the time window into single multi-label samples
4. Generates comprehensive statistics on simultaneous hit patterns
5. Outputs a new manifest ready for multi-label training

Usage:
    # Basic usage with defaults (30ms window)
    python generate_multilabel_dataset.py

    # Custom window size and output
    python generate_multilabel_dataset.py \
        --merge-window-ms 25 \
        --output manifests/multilabel_combined.jsonl

    # Process only specific sources
    python generate_multilabel_dataset.py \
        --sources groove_mididataset egmd slakh2100

    # Verbose mode with detailed statistics
    python generate_multilabel_dataset.py --verbose --stats-only

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

import argparse
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, **kwargs):
        return iterable


# ============================================================================
# Configuration
# ============================================================================

# MIDI-aligned sources that have precise onset times
MIDI_ALIGNED_SOURCES = {
    "groove_mididataset": {
        "file": "groove_mididataset_events.jsonl",
        "description": "Groove MIDI Dataset - professional drummers with MIDI",
        "has_velocity": True,
        "has_midi": True,
        "priority": 1,  # Highest quality
    },
    "egmd": {
        "file": "egmd_events.jsonl",
        "description": "E-GMD - Expanded Groove MIDI Dataset",
        "has_velocity": True,
        "has_midi": True,
        "priority": 1,
    },
    "slakh2100": {
        "file": "slakh2100_events.jsonl",
        "description": "Slakh2100 - Synthesized multi-track with MIDI",
        "has_velocity": True,
        "has_midi": True,
        "priority": 2,  # Synthetic, slightly lower priority
    },
    "enst_drums": {
        "file": "enst_drums_events.jsonl",
        "description": "ENST Drums - Annotated drum recordings",
        "has_velocity": False,  # Annotations, not MIDI velocity
        "has_midi": False,
        "priority": 2,
    },
    "idmt_smt_drums_v2": {
        "file": "idmt_smt_drums_v2_events.jsonl",
        "description": "IDMT-SMT-Drums - Drum sample dataset",
        "has_velocity": False,
        "has_midi": False,
        "priority": 3,
    },
}

# Default drum components (should match components.json)
DEFAULT_DRUM_COMPONENTS = [
    "aux_percussion", "china", "crash", "cross_stick",
    "hihat_closed", "hihat_foot_splash", "hihat_open", "hihat_pedal", "hihat_splash",
    "kick", "ride_bell", "ride_bow", "rimshot",
    "snare", "snare_center", "snare_cross_stick", "snare_rimshot",
    "splash", "tom_high", "tom_low", "tom_mid",
]


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class DrumEvent:
    """Single drum hit event from the manifest."""
    event_id: str
    session_id: str
    source_set: str
    audio_path: str
    onset_time: float
    components: List[Dict[str, Any]]
    velocity: Optional[float] = None
    dynamic_bucket: Optional[str] = None
    techniques: List[str] = field(default_factory=list)
    midi_path: Optional[str] = None
    tempo_bpm: Optional[float] = None
    meter: Optional[str] = None
    context_ms: Dict[str, int] = field(default_factory=lambda: {"pre": 80, "post": 200})
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrumEvent":
        components = data.get("components", [])
        
        # Extract velocity from first component if available
        velocity = None
        dynamic_bucket = None
        if components:
            velocity = components[0].get("velocity")
            dynamic_bucket = components[0].get("dynamic_bucket")
        
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            session_id=data.get("session_id", "unknown"),
            source_set=data.get("source_set", "unknown"),
            audio_path=data.get("audio_path", ""),
            onset_time=float(data.get("onset_time", 0.0)),
            components=components,
            velocity=velocity,
            dynamic_bucket=dynamic_bucket,
            techniques=data.get("techniques", []),
            midi_path=data.get("midi_path"),
            tempo_bpm=data.get("tempo_bpm"),
            meter=data.get("meter"),
            context_ms=data.get("context_ms", {"pre": 80, "post": 200}),
        )


@dataclass
class MultiLabelEvent:
    """Merged multi-label event with potentially multiple drum components."""
    event_id: str
    session_id: str
    source_set: str
    audio_path: str
    onset_time: float  # Time of first component
    components: List[Dict[str, Any]]  # All components merged
    techniques: List[str]
    midi_path: Optional[str]
    tempo_bpm: Optional[float]
    meter: Optional[str]
    context_ms: Dict[str, int]
    original_event_ids: List[str]  # Track which events were merged
    is_multilabel: bool  # True if 2+ components
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "source_set": self.source_set,
            "audio_path": self.audio_path,
            "onset_time": self.onset_time,
            "offset_time": None,
            "tempo_bpm": self.tempo_bpm,
            "meter": self.meter,
            "components": self.components,
            "techniques": list(set(self.techniques)),
            "context_ms": self.context_ms,
            "midi_path": self.midi_path,
            "metadata_ref": f"multilabel_merged:{len(self.original_event_ids)}",
            "negative_example": False,
            "is_multilabel": self.is_multilabel,
            "merged_count": len(self.original_event_ids),
        }


@dataclass
class DatasetStatistics:
    """Statistics about the generated multi-label dataset."""
    total_events: int = 0
    single_label_events: int = 0
    multi_label_events: int = 0
    
    # Component counts
    component_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Co-occurrence matrix (which drums play together)
    cooccurrence: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    
    # Distribution of simultaneous hit counts
    simultaneous_count_dist: Dict[int, int] = field(default_factory=lambda: defaultdict(int))
    
    # Velocity distributions
    velocity_by_component: Dict[str, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    
    # Source set breakdown
    by_source: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"single": 0, "multi": 0, "total": 0})
    )
    
    # Common patterns (most frequent multi-label combinations)
    pattern_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def add_event(self, event: MultiLabelEvent):
        self.total_events += 1
        
        labels = [c["label"] for c in event.components]
        num_labels = len(labels)
        
        if num_labels == 1:
            self.single_label_events += 1
            self.by_source[event.source_set]["single"] += 1
        else:
            self.multi_label_events += 1
            self.by_source[event.source_set]["multi"] += 1
        
        self.by_source[event.source_set]["total"] += 1
        self.simultaneous_count_dist[num_labels] += 1
        
        # Count components
        for comp in event.components:
            label = comp["label"]
            self.component_counts[label] += 1
            if comp.get("velocity") is not None:
                self.velocity_by_component[label].append(comp["velocity"])
        
        # Track co-occurrences
        if num_labels > 1:
            # Sort for consistent pattern key
            pattern_key = "+".join(sorted(labels))
            self.pattern_counts[pattern_key] += 1
            
            for i, label1 in enumerate(labels):
                for label2 in labels[i+1:]:
                    self.cooccurrence[label1][label2] += 1
                    self.cooccurrence[label2][label1] += 1
    
    def print_summary(self, top_patterns: int = 20):
        print("\n" + "="*70)
        print("MULTI-LABEL DATASET STATISTICS")
        print("="*70)
        
        print("\n📊 OVERALL:")
        print(f"   Total events:        {self.total_events:,}")
        print(f"   Single-label:        {self.single_label_events:,} ({100*self.single_label_events/max(1,self.total_events):.1f}%)")
        print(f"   Multi-label:         {self.multi_label_events:,} ({100*self.multi_label_events/max(1,self.total_events):.1f}%)")
        
        print("\n📁 BY SOURCE:")
        for source, counts in sorted(self.by_source.items()):
            total = counts["total"]
            multi = counts["multi"]
            pct = 100 * multi / max(1, total)
            print(f"   {source:30s}: {total:>8,} total, {multi:>6,} multi-label ({pct:.1f}%)")
        
        print("\n🎯 SIMULTANEOUS HIT DISTRIBUTION:")
        for count in sorted(self.simultaneous_count_dist.keys()):
            num = self.simultaneous_count_dist[count]
            pct = 100 * num / max(1, self.total_events)
            bar = "█" * int(pct / 2)
            print(f"   {count} drum(s): {num:>8,} ({pct:>5.1f}%) {bar}")
        
        print(f"\n🥁 TOP {top_patterns} MULTI-LABEL PATTERNS:")
        sorted_patterns = sorted(self.pattern_counts.items(), key=lambda x: -x[1])[:top_patterns]
        for pattern, count in sorted_patterns:
            pct = 100 * count / max(1, self.multi_label_events)
            print(f"   {pattern:40s}: {count:>6,} ({pct:>5.1f}% of multi-label)")
        
        print("\n🔊 COMPONENT FREQUENCIES:")
        sorted_comps = sorted(self.component_counts.items(), key=lambda x: -x[1])
        for comp, count in sorted_comps[:15]:
            pct = 100 * count / max(1, self.total_events)
            print(f"   {comp:25s}: {count:>8,} ({pct:>5.1f}%)")
        
        # Most common co-occurrences
        print("\n🤝 TOP CO-OCCURRENCES (which drums play together):")
        cooc_pairs = []
        seen = set()
        for d1, partners in self.cooccurrence.items():
            for d2, count in partners.items():
                key = tuple(sorted([d1, d2]))
                if key not in seen:
                    cooc_pairs.append((d1, d2, count))
                    seen.add(key)
        
        for d1, d2, count in sorted(cooc_pairs, key=lambda x: -x[2])[:15]:
            print(f"   {d1} + {d2}: {count:,}")
        
        print("\n" + "="*70)


# ============================================================================
# Core Processing Functions
# ============================================================================

def load_manifest(filepath: Path, max_events: Optional[int] = None) -> List[DrumEvent]:
    """Load events from a JSONL manifest file."""
    events = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if max_events and i >= max_events:
                break
            
            line = line.strip()
            if not line:
                continue
            
            try:
                if HAS_ORJSON and orjson is not None:
                    data = orjson.loads(line)
                else:
                    data = json.loads(line)
                
                # Skip non-drum events or negative examples
                if data.get("negative_example", False):
                    continue
                
                # Skip events without valid onset time
                if data.get("onset_time") is None:
                    continue
                
                events.append(DrumEvent.from_dict(data))
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Skipping malformed line {i}: {e}")
                continue
    
    return events


def group_events_by_session(events: List[DrumEvent]) -> Dict[str, List[DrumEvent]]:
    """Group events by session and audio file for proper merging."""
    groups = defaultdict(list)
    
    for event in events:
        # Key by audio file to ensure we only merge within same recording
        key = (event.session_id, event.audio_path)
        groups[key].append(event)
    
    # Sort each group by onset time
    for key in groups:
        groups[key].sort(key=lambda e: e.onset_time)
    
    return groups


def merge_simultaneous_events(
    events: List[DrumEvent],
    window_ms: float = 30.0,
) -> List[MultiLabelEvent]:
    """
    Merge events that occur within the time window into multi-label events.
    
    This is the core algorithm that creates multi-label training data.
    Events within `window_ms` milliseconds of each other are considered
    simultaneous and merged into a single multi-label sample.
    """
    if not events:
        return []
    
    window_sec = window_ms / 1000.0
    merged_events = []
    
    i = 0
    while i < len(events):
        current = events[i]
        current_time = current.onset_time
        
        # Find all events within the window
        to_merge = [current]
        j = i + 1
        
        while j < len(events):
            next_event = events[j]
            time_diff = next_event.onset_time - current_time
            
            if time_diff <= window_sec:
                to_merge.append(next_event)
                j += 1
            else:
                break
        
        # Create merged event
        merged = create_merged_event(to_merge)
        merged_events.append(merged)
        
        # Skip past all merged events
        i = j
    
    return merged_events


def create_merged_event(events: List[DrumEvent]) -> MultiLabelEvent:
    """Create a single multi-label event from multiple simultaneous events."""
    first = events[0]
    
    # Collect all unique components
    all_components = []
    seen_labels = set()
    all_techniques = []
    original_ids = []
    
    for event in events:
        original_ids.append(event.event_id)
        all_techniques.extend(event.techniques)
        
        for comp in event.components:
            label = comp.get("label", "unknown")
            # Avoid duplicate labels (e.g., two kicks merged)
            if label not in seen_labels:
                all_components.append(comp)
                seen_labels.add(label)
    
    # Use earliest onset time
    onset_time = min(e.onset_time for e in events)
    
    return MultiLabelEvent(
        event_id=str(uuid.uuid4()),
        session_id=first.session_id,
        source_set=first.source_set,
        audio_path=first.audio_path,
        onset_time=onset_time,
        components=all_components,
        techniques=list(set(all_techniques)),
        midi_path=first.midi_path,
        tempo_bpm=first.tempo_bpm,
        meter=first.meter,
        context_ms=first.context_ms,
        original_event_ids=original_ids,
        is_multilabel=len(all_components) > 1,
    )


def process_source(
    manifest_path: Path,
    window_ms: float,
    max_events: Optional[int] = None,
    verbose: bool = False,
) -> Tuple[List[MultiLabelEvent], DatasetStatistics]:
    """Process a single source manifest and return multi-label events."""
    
    if verbose:
        print(f"\n📂 Loading {manifest_path.name}...")
    
    events = load_manifest(manifest_path, max_events)
    
    if verbose:
        print(f"   Loaded {len(events):,} events")
    
    if not events:
        return [], DatasetStatistics()
    
    # Group by session/audio
    groups = group_events_by_session(events)
    
    if verbose:
        print(f"   Found {len(groups):,} unique sessions/recordings")
    
    # Merge simultaneous events within each group
    all_merged = []
    stats = DatasetStatistics()
    
    iterator = tqdm(groups.items(), desc="Merging", disable=not verbose)
    for (session_id, audio_path), session_events in iterator:
        merged = merge_simultaneous_events(session_events, window_ms)
        all_merged.extend(merged)
        
        for event in merged:
            stats.add_event(event)
    
    return all_merged, stats


def save_manifest(events: List[MultiLabelEvent], output_path: Path):
    """Save multi-label events to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for event in events:
            line = json.dumps(event.to_dict(), ensure_ascii=False)
            f.write(line + '\n')
    
    print(f"\n✅ Saved {len(events):,} multi-label events to {output_path}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate multi-label training dataset from MIDI-aligned sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all MIDI sources with 30ms window (recommended)
  python generate_multilabel_dataset.py

  # Tighter window for more conservative merging
  python generate_multilabel_dataset.py --merge-window-ms 20

  # Process specific sources only
  python generate_multilabel_dataset.py --sources groove_mididataset egmd

  # Just show statistics without generating output
  python generate_multilabel_dataset.py --stats-only --verbose
        """
    )
    
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "manifests",
        help="Directory containing manifest JSONL files",
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSONL file path (default: manifests/multilabel_combined_events.jsonl)",
    )
    
    parser.add_argument(
        "--merge-window-ms",
        type=float,
        default=30.0,
        help="Time window in milliseconds for merging simultaneous hits (default: 30)",
    )
    
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(MIDI_ALIGNED_SOURCES.keys()),
        default=None,
        help="Specific sources to process (default: all MIDI-aligned sources)",
    )
    
    parser.add_argument(
        "--max-events-per-source",
        type=int,
        default=None,
        help="Maximum events to load per source (for testing)",
    )
    
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only compute statistics, don't write output file",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output with progress bars",
    )
    
    args = parser.parse_args()
    
    # Determine which sources to process
    sources = args.sources or list(MIDI_ALIGNED_SOURCES.keys())
    
    # Set default output path
    if args.output is None:
        args.output = args.manifests_dir / "multilabel_combined_events.jsonl"
    
    print("="*70)
    print("🥁 BeatSight Multi-Label Dataset Generator")
    print("="*70)
    print(f"   Merge window:     {args.merge_window_ms}ms")
    print(f"   Sources:          {', '.join(sources)}")
    print(f"   Output:           {args.output}")
    print(f"   Stats only:       {args.stats_only}")
    print("="*70)
    
    # Process each source
    all_events = []
    total_stats = DatasetStatistics()
    
    for source_name in sources:
        source_config = MIDI_ALIGNED_SOURCES[source_name]
        manifest_path = args.manifests_dir / source_config["file"]
        
        if not manifest_path.exists():
            print(f"\n⚠️  Skipping {source_name}: {manifest_path} not found")
            continue
        
        print(f"\n{'─'*70}")
        print(f"📀 Processing: {source_name}")
        print(f"   {source_config['description']}")
        print(f"   File: {manifest_path.name} ({manifest_path.stat().st_size / 1024 / 1024:.1f} MB)")
        
        events, stats = process_source(
            manifest_path,
            window_ms=args.merge_window_ms,
            max_events=args.max_events_per_source,
            verbose=args.verbose,
        )
        
        all_events.extend(events)
        
        # Merge statistics
        total_stats.total_events += stats.total_events
        total_stats.single_label_events += stats.single_label_events
        total_stats.multi_label_events += stats.multi_label_events
        
        for label, count in stats.component_counts.items():
            total_stats.component_counts[label] += count
        
        for d1, partners in stats.cooccurrence.items():
            for d2, count in partners.items():
                total_stats.cooccurrence[d1][d2] += count
        
        for count, num in stats.simultaneous_count_dist.items():
            total_stats.simultaneous_count_dist[count] += num
        
        for pattern, count in stats.pattern_counts.items():
            total_stats.pattern_counts[pattern] += count
        
        for source, counts in stats.by_source.items():
            for key, val in counts.items():
                total_stats.by_source[source][key] += val
        
        for label, velocities in stats.velocity_by_component.items():
            total_stats.velocity_by_component[label].extend(velocities)
        
        print(f"   ✅ Generated {len(events):,} multi-label events")
        print(f"      Single-label: {stats.single_label_events:,}")
        print(f"      Multi-label:  {stats.multi_label_events:,} ({100*stats.multi_label_events/max(1,stats.total_events):.1f}%)")
    
    # Print combined statistics
    total_stats.print_summary()
    
    # Save output
    if not args.stats_only and all_events:
        save_manifest(all_events, args.output)
        
        # Save components.json for the dataset
        components_path = args.output.parent / "components.json"
        with open(components_path, 'w') as f:
            json.dump(DRUM_COMPONENTS, f, indent=2)
        print(f"📋 Components saved to {components_path}")
        
        # Also create a summary JSON
        summary_path = args.output.with_suffix('.summary.json')
        summary = {
            "generated_at": datetime.now().isoformat(),
            "merge_window_ms": args.merge_window_ms,
            "sources": sources,
            "total_events": total_stats.total_events,
            "single_label_events": total_stats.single_label_events,
            "multi_label_events": total_stats.multi_label_events,
            "multi_label_percentage": 100 * total_stats.multi_label_events / max(1, total_stats.total_events),
            "simultaneous_count_distribution": dict(total_stats.simultaneous_count_dist),
            "component_counts": dict(total_stats.component_counts),
            "top_patterns": dict(sorted(total_stats.pattern_counts.items(), key=lambda x: -x[1])[:50]),
        }
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"📊 Summary saved to {summary_path}")
    
    print("\n🎉 Done!")
    
    if total_stats.multi_label_events > 0:
        print("\n💡 Next steps:")
        print("   1. Your V5 training should complete first")
        print("   2. Then run multi-label training with this dataset:")
        print("      bash ai-pipeline/training/tools/post_export_commands.sh")
        print("      Select: 19c (Multi-Label Finetune)")
        print("")
        print("   The multi-label model will detect simultaneous drums!")


if __name__ == "__main__":
    main()
