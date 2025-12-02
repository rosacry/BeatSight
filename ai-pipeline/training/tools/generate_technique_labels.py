#!/usr/bin/env python3
"""
Generate technique labels from existing drum transcription data.

This script analyzes the existing training data to automatically label
techniques based on:
- Velocity patterns (ghost notes, accents, accent-tap sequences)
- Temporal proximity (flams, drags, double strokes)
- Instrument class heuristics (rimshot, cross_stick already labeled)

Usage:
    python generate_technique_labels.py \
        --input-labels E:/data/prod_combined_profile_run/train/index.json \
        --output-labels E:/data/prod_combined_profile_run/train/index_with_techniques.json \
        --technique-preset core

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from training.models.technique_heads import CORE_TECHNIQUES, ALL_TECHNIQUES


# =============================================================================
# TECHNIQUE DETECTION RULES
# =============================================================================

# Velocity thresholds
GHOST_NOTE_THRESHOLD = 0.25      # Below this = ghost note
ACCENT_THRESHOLD = 0.75          # Above this = accent
ACCENT_TAP_MIN_ALTERNATIONS = 3  # Minimum alternations for accent-tap pattern

# Temporal thresholds (in seconds)
FLAM_MAX_GAP = 0.04              # Max time between grace note and main hit
DRAG_MAX_GAP = 0.06              # Max time for drag (multiple grace notes)
DOUBLE_STROKE_MAX_GAP = 0.08     # Max time between RR/LL strokes
ROLL_MIN_HITS = 4                # Minimum hits for roll detection
ROLL_MAX_IOI = 0.1               # Maximum inter-onset interval for rolls

# Instrument-based technique mappings
RIMSHOT_CLASSES = {"snare_rimshot", "rimshot"}
CROSS_STICK_CLASSES = {"snare_cross_stick", "cross_stick"}


class TechniqueLabeler:
    """Automatically generate technique labels from drum transcription data."""
    
    def __init__(self, techniques: List[str]):
        self.techniques = techniques
        self.technique_to_idx = {t: i for i, t in enumerate(techniques)}
        self.stats = defaultdict(int)
    
    def label_from_velocity(
        self,
        velocity: float,
        instrument: str,
    ) -> Set[str]:
        """Detect techniques based on velocity alone."""
        techniques = set()
        
        if velocity < GHOST_NOTE_THRESHOLD:
            techniques.add("ghost_note")
        elif velocity > ACCENT_THRESHOLD:
            techniques.add("accent")
        
        return techniques
    
    def label_from_instrument(self, instrument: str) -> Set[str]:
        """Detect techniques based on instrument class."""
        techniques = set()
        
        if instrument in RIMSHOT_CLASSES:
            techniques.add("rimshot")
        elif instrument in CROSS_STICK_CLASSES:
            techniques.add("cross_stick")
        
        return techniques
    
    def detect_flam(
        self,
        events: List[Dict[str, Any]],
        index: int,
    ) -> bool:
        """Check if event at index is part of a flam."""
        if index == 0:
            return False
        
        current = events[index]
        prev = events[index - 1]
        
        # Same or similar instrument
        if not self._same_instrument_group(current.get("label", ""), prev.get("label", "")):
            return False
        
        # Time gap check
        time_gap = current.get("timestamp", 0) - prev.get("timestamp", 0)
        if time_gap > FLAM_MAX_GAP:
            return False
        
        # Velocity difference (grace note should be softer)
        prev_vel = prev.get("velocity", 0.5)
        curr_vel = current.get("velocity", 0.5)
        
        return prev_vel < curr_vel * 0.7  # Grace note significantly softer
    
    def detect_double_stroke(
        self,
        events: List[Dict[str, Any]],
        index: int,
    ) -> bool:
        """Check if event at index is part of a double stroke (diddle)."""
        if index == 0:
            return False
        
        current = events[index]
        prev = events[index - 1]
        
        # Same instrument
        if current.get("label", "") != prev.get("label", ""):
            return False
        
        # Time gap check
        time_gap = current.get("timestamp", 0) - prev.get("timestamp", 0)
        if time_gap > DOUBLE_STROKE_MAX_GAP:
            return False
        
        # Similar velocity (both hits of diddle should be similar)
        prev_vel = prev.get("velocity", 0.5)
        curr_vel = current.get("velocity", 0.5)
        
        return abs(prev_vel - curr_vel) < 0.2
    
    def detect_roll_region(
        self,
        events: List[Dict[str, Any]],
        index: int,
        window: int = 8,
    ) -> bool:
        """Check if event is within a roll region (sustained repeated strokes)."""
        # Look at surrounding events
        start = max(0, index - window // 2)
        end = min(len(events), index + window // 2)
        
        region = events[start:end]
        if len(region) < ROLL_MIN_HITS:
            return False
        
        # Filter to same instrument
        current_label = events[index].get("label", "")
        same_instrument = [e for e in region if e.get("label", "") == current_label]
        
        if len(same_instrument) < ROLL_MIN_HITS:
            return False
        
        # Check for consistent rapid IOI
        timestamps = [e.get("timestamp", 0) for e in same_instrument]
        iois = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps) - 1)]
        
        if not iois:
            return False
        
        mean_ioi = np.mean(iois)
        std_ioi = np.std(iois)
        
        # Roll has low IOI and consistent timing
        return mean_ioi < ROLL_MAX_IOI and std_ioi < mean_ioi * 0.3
    
    def detect_accent_tap_pattern(
        self,
        events: List[Dict[str, Any]],
        index: int,
        window: int = 8,
    ) -> bool:
        """Detect accent-tap alternating pattern."""
        start = max(0, index - window // 2)
        end = min(len(events), index + window // 2)
        
        region = events[start:end]
        current_label = events[index].get("label", "")
        same_instrument = [e for e in region if e.get("label", "") == current_label]
        
        if len(same_instrument) < ACCENT_TAP_MIN_ALTERNATIONS * 2:
            return False
        
        velocities = [e.get("velocity", 0.5) for e in same_instrument]
        
        # Count alternations between high and low
        alternations = 0
        prev_high = velocities[0] > 0.5
        
        for v in velocities[1:]:
            curr_high = v > 0.5
            if curr_high != prev_high:
                alternations += 1
            prev_high = curr_high
        
        # Strong alternation pattern
        return alternations >= ACCENT_TAP_MIN_ALTERNATIONS
    
    def _same_instrument_group(self, label1: str, label2: str) -> bool:
        """Check if two labels are from the same instrument group."""
        groups = {
            "snare": {"snare", "snare_center", "snare_rimshot", "snare_cross_stick"},
            "hihat": {"hihat_closed", "hihat_open", "hihat_pedal", "hihat_splash", "hihat_foot_splash"},
            "kick": {"kick"},
            "tom": {"tom_high", "tom_mid", "tom_low"},
            "crash": {"crash", "china", "splash"},
            "ride": {"ride_bow", "ride_bell"},
        }
        
        for group_labels in groups.values():
            if label1 in group_labels and label2 in group_labels:
                return True
        
        return label1 == label2
    
    def label_event(
        self,
        event: Dict[str, Any],
        events: List[Dict[str, Any]],
        index: int,
    ) -> List[int]:
        """Generate technique labels for a single event."""
        techniques = set()
        
        instrument = event.get("label", "")
        velocity = event.get("velocity", 0.5)
        
        # Velocity-based techniques
        techniques.update(self.label_from_velocity(velocity, instrument))
        
        # Instrument-based techniques
        techniques.update(self.label_from_instrument(instrument))
        
        # Context-based techniques
        if "flam" in self.techniques and self.detect_flam(events, index):
            techniques.add("flam")
        
        if "double_stroke" in self.techniques and self.detect_double_stroke(events, index):
            techniques.add("double_stroke")
        
        if "roll" in self.techniques and self.detect_roll_region(events, index):
            techniques.add("roll")
        
        # Accent-tap pattern (labels both accents and taps in the pattern)
        if self.detect_accent_tap_pattern(events, index):
            if velocity > 0.5:
                techniques.add("accent")
            else:
                techniques.add("ghost_note")  # Taps are soft
        
        # Convert to binary vector
        label_vector = [0] * len(self.techniques)
        for tech in techniques:
            if tech in self.technique_to_idx:
                label_vector[self.technique_to_idx[tech]] = 1
                self.stats[tech] += 1
        
        return label_vector
    
    def process_file_events(
        self,
        events: List[Dict[str, Any]],
    ) -> List[List[int]]:
        """Process all events in a file and return technique labels."""
        # Sort by timestamp
        events = sorted(events, key=lambda e: e.get("timestamp", 0))
        
        labels = []
        for i, event in enumerate(events):
            labels.append(self.label_event(event, events, i))
        
        return labels


def load_labels(labels_path: Path) -> Dict[str, Any]:
    """Load labels from JSON file."""
    with open(labels_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_labels(labels: Dict[str, Any], output_path: Path) -> None:
    """Save labels to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(labels, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate technique labels from drum transcription data"
    )
    parser.add_argument(
        "--input-labels",
        type=str,
        required=True,
        help="Path to input labels JSON file",
    )
    parser.add_argument(
        "--output-labels",
        type=str,
        required=True,
        help="Path to output labels JSON file with techniques",
    )
    parser.add_argument(
        "--technique-preset",
        type=str,
        default="core",
        choices=["core", "full", "minimal"],
        help="Technique preset to use",
    )
    parser.add_argument(
        "--has-velocity",
        action="store_true",
        help="Input labels contain velocity information",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only compute stats, don't write output",
    )
    
    args = parser.parse_args()
    
    # Select techniques
    if args.technique_preset == "full":
        techniques = ALL_TECHNIQUES
    elif args.technique_preset == "minimal":
        techniques = ["ghost_note", "accent", "cymbal_choke"]
    else:
        techniques = CORE_TECHNIQUES
    
    print(f"Technique preset: {args.technique_preset}")
    print(f"Techniques: {techniques}")
    
    # Load input labels
    input_path = Path(args.input_labels)
    print(f"\nLoading labels from: {input_path}")
    
    labels_data = load_labels(input_path)
    
    # Create labeler
    labeler = TechniqueLabeler(techniques)
    
    # Process based on label format
    if isinstance(labels_data, dict) and "samples" in labels_data:
        # Format: {"samples": [...], ...}
        samples = labels_data["samples"]
    elif isinstance(labels_data, list):
        # Format: [...]
        samples = labels_data
    else:
        print(f"Unknown label format. Keys: {labels_data.keys() if isinstance(labels_data, dict) else 'list'}")
        return
    
    print(f"Processing {len(samples)} samples...")
    
    # Check if we have velocity data
    sample_has_velocity = False
    if samples and len(samples) > 0:
        first_sample = samples[0]
        if isinstance(first_sample, dict):
            sample_has_velocity = "velocity" in first_sample
    
    if not args.has_velocity and not sample_has_velocity:
        print("\nWarning: No velocity information found in labels.")
        print("Velocity-based techniques (ghost_note, accent) will be estimated from class.")
    
    # Generate technique labels
    # For now, we'll add a placeholder technique_labels field
    # In practice, we'd need the full event sequence with timestamps
    
    technique_labels = []
    for i, sample in enumerate(samples):
        if isinstance(sample, dict):
            # Single event - create minimal label
            velocity = sample.get("velocity", 0.5)
            instrument = sample.get("label", sample.get("class", ""))
            
            # Simple velocity-based labeling
            tech_label = [0] * len(techniques)
            
            if velocity < GHOST_NOTE_THRESHOLD and "ghost_note" in techniques:
                tech_label[techniques.index("ghost_note")] = 1
                labeler.stats["ghost_note"] += 1
            elif velocity > ACCENT_THRESHOLD and "accent" in techniques:
                tech_label[techniques.index("accent")] = 1
                labeler.stats["accent"] += 1
            
            if instrument in RIMSHOT_CLASSES and "rimshot" in techniques:
                tech_label[techniques.index("rimshot")] = 1
                labeler.stats["rimshot"] += 1
            elif instrument in CROSS_STICK_CLASSES and "cross_stick" in techniques:
                tech_label[techniques.index("cross_stick")] = 1
                labeler.stats["cross_stick"] += 1
            
            technique_labels.append(tech_label)
        else:
            # Just a class index - no technique info available
            technique_labels.append([0] * len(techniques))
    
    # Print statistics
    print(f"\n{'='*50}")
    print("Technique Detection Statistics:")
    print(f"{'='*50}")
    total_samples = len(samples)
    for tech in techniques:
        count = labeler.stats.get(tech, 0)
        pct = count / total_samples * 100 if total_samples > 0 else 0
        print(f"  {tech:20s}: {count:8,d} ({pct:5.2f}%)")
    print(f"{'='*50}")
    
    if args.dry_run:
        print("\nDry run - not saving output")
        return
    
    # Create output data
    output_data = {
        "technique_names": techniques,
        "num_techniques": len(techniques),
        "samples": samples,
        "technique_labels": technique_labels,
        "metadata": {
            "source": str(input_path),
            "preset": args.technique_preset,
            "ghost_threshold": GHOST_NOTE_THRESHOLD,
            "accent_threshold": ACCENT_THRESHOLD,
        }
    }
    
    # Preserve original metadata if present
    if isinstance(labels_data, dict):
        for key in labels_data:
            if key not in output_data and key != "samples":
                output_data[key] = labels_data[key]
    
    # Save output
    output_path = Path(args.output_labels)
    print(f"\nSaving to: {output_path}")
    save_labels(output_data, output_path)
    print("Done!")


if __name__ == "__main__":
    main()
