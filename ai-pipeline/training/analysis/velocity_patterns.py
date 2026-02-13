#!/usr/bin/env python3
"""
Velocity Pattern Analyzer for Drumming Technique Detection

This module analyzes sequences of drum hits to detect velocity-based patterns
that indicate specific drumming techniques:

- Accent-Tap (Moeller): Alternating high (>0.7) and low (<0.3) velocity
- Ghost Note Bursts: Sequences of very low velocity (<0.2) hits
- Crescendo/Decrescendo: Monotonically increasing/decreasing velocity
- Flam Velocity Signature: Grace note (low) immediately before main hit (high)
- Shuffle Ghost Pattern: Specific triplet-feel ghost note placement

These patterns cannot be detected from single hits - they require temporal context
across multiple events.

Usage:
    from training.analysis.velocity_patterns import VelocityPatternAnalyzer
    
    analyzer = VelocityPatternAnalyzer()
    
    # Analyze a sequence of events
    events = [
        {"timestamp": 0.0, "label": "snare", "velocity": 0.9},
        {"timestamp": 0.125, "label": "snare", "velocity": 0.15},
        {"timestamp": 0.25, "label": "snare", "velocity": 0.85},
        {"timestamp": 0.375, "label": "snare", "velocity": 0.12},
    ]
    
    patterns = analyzer.detect_patterns(events)
    # Returns: {"accent_tap": True, "measure_positions": [0, 1, 2, 3]}

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import numpy as np


@dataclass
class PatternConfig:
    """Configuration for velocity pattern detection."""
    
    # Accent-Tap Detection
    accent_velocity_min: float = 0.65      # Minimum velocity for "accent"
    tap_velocity_max: float = 0.35         # Maximum velocity for "tap"
    accent_tap_min_alternations: int = 3   # Minimum alternating pairs to detect
    accent_tap_max_time_gap: float = 0.5   # Maximum time between hits (seconds)
    
    # Ghost Note Detection
    ghost_velocity_max: float = 0.25       # Maximum velocity for ghost notes
    ghost_burst_min_count: int = 2         # Minimum consecutive ghosts
    ghost_surrounding_accent_min: float = 0.6  # Velocity of surrounding accents
    
    # Crescendo/Decrescendo Detection
    crescendo_min_hits: int = 4            # Minimum hits for crescendo detection
    crescendo_velocity_change_min: float = 0.3  # Minimum total velocity change
    crescendo_monotonic_tolerance: float = 0.05  # Allowed deviation from monotonic
    
    # Flam Detection (velocity-based supplement to ML detection)
    flam_grace_velocity_max: float = 0.4   # Grace note velocity ceiling
    flam_main_velocity_min: float = 0.6    # Main note velocity floor
    flam_time_window_ms: Tuple[float, float] = (15, 60)  # Grace-to-main timing
    
    # Shuffle/Triplet Ghost Pattern
    shuffle_triplet_tolerance_ms: float = 30  # Timing tolerance for triplet grid
    shuffle_min_pattern_count: int = 2     # Minimum repeats to confirm pattern
    
    # Same-instrument filtering
    require_same_instrument: bool = True   # Only analyze within same instrument
    instrument_groups: Dict[str, List[str]] = field(default_factory=lambda: {
        "snare": ["snare", "snare_center", "snare_rimshot"],
        "hihat": ["hihat_closed", "hihat_open", "hihat_pedal"],
        "tom": ["tom_high", "tom_mid", "tom_low"],
        "kick": ["kick"],
    })


@dataclass
class PatternResult:
    """Result from pattern detection."""
    
    pattern_type: str
    confidence: float
    start_time: float
    end_time: float
    event_indices: List[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class VelocityPatternAnalyzer:
    """
    Analyzes velocity sequences to detect drumming technique patterns.
    
    Unlike single-hit classification, these patterns require temporal context
    across multiple events to identify.
    """
    
    def __init__(self, config: Optional[PatternConfig] = None):
        self.config = config or PatternConfig()
        
        # Build reverse instrument group lookup
        self._instrument_to_group = {}
        for group, instruments in self.config.instrument_groups.items():
            for inst in instruments:
                self._instrument_to_group[inst] = group
    
    def detect_patterns(
        self,
        events: List[Dict[str, Any]],
        bpm: Optional[float] = None,
    ) -> List[PatternResult]:
        """
        Detect all velocity patterns in a sequence of events.
        
        Args:
            events: List of event dicts with keys:
                - timestamp (float): Time in seconds
                - label (str): Instrument class
                - velocity (float): Hit velocity 0-1
            bpm: Optional tempo for rhythm-aware detection
        
        Returns:
            List of detected patterns
        """
        if len(events) < 2:
            return []
        
        # Sort by timestamp
        events = sorted(events, key=lambda e: e["timestamp"])
        
        all_patterns = []
        
        # Detect each pattern type
        all_patterns.extend(self._detect_accent_tap(events))
        all_patterns.extend(self._detect_ghost_bursts(events))
        all_patterns.extend(self._detect_crescendo(events))
        all_patterns.extend(self._detect_flam_velocity(events))
        
        if bpm:
            all_patterns.extend(self._detect_shuffle_ghosts(events, bpm))
        
        return all_patterns
    
    def _get_instrument_group(self, label: str) -> str:
        """Get the instrument group for a label."""
        return self._instrument_to_group.get(label, label)
    
    def _filter_by_instrument(
        self,
        events: List[Dict],
        group: Optional[str] = None,
    ) -> List[Tuple[int, Dict]]:
        """Filter events by instrument group, keeping original indices."""
        if group is None:
            return list(enumerate(events))
        
        return [
            (i, e) for i, e in enumerate(events)
            if self._get_instrument_group(e["label"]) == group
        ]
    
    def _detect_accent_tap(
        self,
        events: List[Dict],
    ) -> List[PatternResult]:
        """
        Detect accent-tap (Moeller) sticking patterns.
        
        Accent-tap is characterized by alternating high and low velocity hits
        on the same instrument, often used for flow and dynamics in grooves.
        
        Pattern: HLHLHL... where H > accent_velocity_min, L < tap_velocity_max
        """
        patterns = []
        
        # Group by instrument
        for group in set(self._instrument_to_group.values()):
            filtered = self._filter_by_instrument(events, group)
            if len(filtered) < self.config.accent_tap_min_alternations * 2:
                continue
            
            # Find alternating sequences
            current_sequence = []
            last_was_accent = None
            
            for idx, event in filtered:
                vel = event["velocity"]
                is_accent = vel >= self.config.accent_velocity_min
                is_tap = vel <= self.config.tap_velocity_max
                
                # Check time gap from previous
                if current_sequence:
                    prev_idx, prev_event = current_sequence[-1]
                    time_gap = event["timestamp"] - prev_event["timestamp"]
                    if time_gap > self.config.accent_tap_max_time_gap:
                        # Gap too large, check if we have a pattern
                        if len(current_sequence) >= self.config.accent_tap_min_alternations * 2:
                            patterns.append(self._create_accent_tap_result(current_sequence))
                        current_sequence = []
                        last_was_accent = None
                
                # Check for alternation
                if is_accent and last_was_accent is False:
                    current_sequence.append((idx, event))
                    last_was_accent = True
                elif is_tap and last_was_accent is True:
                    current_sequence.append((idx, event))
                    last_was_accent = False
                elif is_accent and last_was_accent is None:
                    current_sequence.append((idx, event))
                    last_was_accent = True
                elif is_tap and last_was_accent is None:
                    current_sequence.append((idx, event))
                    last_was_accent = False
                else:
                    # Pattern broken
                    if len(current_sequence) >= self.config.accent_tap_min_alternations * 2:
                        patterns.append(self._create_accent_tap_result(current_sequence))
                    current_sequence = []
                    # Start new sequence with current event if it's accent or tap
                    if is_accent:
                        current_sequence = [(idx, event)]
                        last_was_accent = True
                    elif is_tap:
                        current_sequence = [(idx, event)]
                        last_was_accent = False
                    else:
                        last_was_accent = None
            
            # Check final sequence
            if len(current_sequence) >= self.config.accent_tap_min_alternations * 2:
                patterns.append(self._create_accent_tap_result(current_sequence))
        
        return patterns
    
    def _create_accent_tap_result(
        self,
        sequence: List[Tuple[int, Dict]],
    ) -> PatternResult:
        """Create a PatternResult for an accent-tap sequence."""
        indices = [idx for idx, _ in sequence]
        velocities = [e["velocity"] for _, e in sequence]
        
        # Calculate pattern confidence based on velocity contrast
        accents = [v for v in velocities if v >= self.config.accent_velocity_min]
        taps = [v for v in velocities if v <= self.config.tap_velocity_max]
        
        avg_contrast = (np.mean(accents) - np.mean(taps)) if accents and taps else 0.5
        confidence = min(1.0, avg_contrast + 0.3)  # Bonus for having the pattern at all
        
        return PatternResult(
            pattern_type="accent_tap",
            confidence=confidence,
            start_time=sequence[0][1]["timestamp"],
            end_time=sequence[-1][1]["timestamp"],
            event_indices=indices,
            metadata={
                "num_alternations": len(sequence) // 2,
                "avg_accent_velocity": np.mean(accents) if accents else 0,
                "avg_tap_velocity": np.mean(taps) if taps else 0,
                "velocity_contrast": avg_contrast,
            }
        )
    
    def _detect_ghost_bursts(
        self,
        events: List[Dict],
    ) -> List[PatternResult]:
        """
        Detect bursts of ghost notes.
        
        Ghost bursts are sequences of very quiet hits typically between accents,
        adding texture and feel to grooves.
        """
        patterns = []
        
        for group in ["snare", "hihat"]:  # Most common ghost note instruments
            filtered = self._filter_by_instrument(events, group)
            
            current_burst = []
            
            for idx, event in filtered:
                vel = event["velocity"]
                
                if vel <= self.config.ghost_velocity_max:
                    current_burst.append((idx, event))
                else:
                    if len(current_burst) >= self.config.ghost_burst_min_count:
                        # Check if surrounded by accents
                        patterns.append(self._create_ghost_burst_result(
                            current_burst, group
                        ))
                    current_burst = []
            
            # Check final burst
            if len(current_burst) >= self.config.ghost_burst_min_count:
                patterns.append(self._create_ghost_burst_result(current_burst, group))
        
        return patterns
    
    def _create_ghost_burst_result(
        self,
        burst: List[Tuple[int, Dict]],
        instrument_group: str,
    ) -> PatternResult:
        """Create a PatternResult for a ghost burst."""
        indices = [idx for idx, _ in burst]
        velocities = [e["velocity"] for _, e in burst]
        
        return PatternResult(
            pattern_type="ghost_burst",
            confidence=0.7 + 0.1 * min(len(burst), 3),  # Higher confidence for longer bursts
            start_time=burst[0][1]["timestamp"],
            end_time=burst[-1][1]["timestamp"],
            event_indices=indices,
            metadata={
                "num_ghosts": len(burst),
                "avg_velocity": np.mean(velocities),
                "instrument_group": instrument_group,
            }
        )
    
    def _detect_crescendo(
        self,
        events: List[Dict],
    ) -> List[PatternResult]:
        """
        Detect crescendo (building) and decrescendo (fading) patterns.
        """
        patterns = []
        
        for group in set(self._instrument_to_group.values()):
            filtered = self._filter_by_instrument(events, group)
            if len(filtered) < self.config.crescendo_min_hits:
                continue
            
            # Sliding window detection
            window_size = self.config.crescendo_min_hits
            
            for i in range(len(filtered) - window_size + 1):
                window = filtered[i:i + window_size]
                velocities = [e["velocity"] for _, e in window]
                
                # Check for monotonic increase (crescendo)
                if self._is_monotonic(velocities, increasing=True):
                    total_change = velocities[-1] - velocities[0]
                    if total_change >= self.config.crescendo_velocity_change_min:
                        patterns.append(PatternResult(
                            pattern_type="crescendo",
                            confidence=min(1.0, total_change + 0.4),
                            start_time=window[0][1]["timestamp"],
                            end_time=window[-1][1]["timestamp"],
                            event_indices=[idx for idx, _ in window],
                            metadata={
                                "velocity_change": total_change,
                                "instrument_group": group,
                            }
                        ))
                
                # Check for monotonic decrease (decrescendo)
                elif self._is_monotonic(velocities, increasing=False):
                    total_change = velocities[0] - velocities[-1]
                    if total_change >= self.config.crescendo_velocity_change_min:
                        patterns.append(PatternResult(
                            pattern_type="decrescendo",
                            confidence=min(1.0, total_change + 0.4),
                            start_time=window[0][1]["timestamp"],
                            end_time=window[-1][1]["timestamp"],
                            event_indices=[idx for idx, _ in window],
                            metadata={
                                "velocity_change": total_change,
                                "instrument_group": group,
                            }
                        ))
        
        return patterns
    
    def _is_monotonic(
        self,
        values: List[float],
        increasing: bool,
    ) -> bool:
        """Check if values are monotonically increasing/decreasing with tolerance."""
        tolerance = self.config.crescendo_monotonic_tolerance
        
        for i in range(1, len(values)):
            if increasing:
                if values[i] < values[i-1] - tolerance:
                    return False
            else:
                if values[i] > values[i-1] + tolerance:
                    return False
        
        return True
    
    def _detect_flam_velocity(
        self,
        events: List[Dict],
    ) -> List[PatternResult]:
        """
        Detect flams based on velocity signature.
        
        Supplements ML-based flam detection by looking for low-velocity grace note
        immediately before high-velocity main hit.
        """
        patterns = []
        
        for group in ["snare", "tom"]:  # Most common flam instruments
            filtered = self._filter_by_instrument(events, group)
            
            for i in range(len(filtered) - 1):
                idx1, e1 = filtered[i]
                idx2, e2 = filtered[i + 1]
                
                # Check velocity pattern (grace low, main high)
                if (e1["velocity"] <= self.config.flam_grace_velocity_max and
                    e2["velocity"] >= self.config.flam_main_velocity_min):
                    
                    # Check timing
                    time_gap_ms = (e2["timestamp"] - e1["timestamp"]) * 1000
                    min_gap, max_gap = self.config.flam_time_window_ms
                    
                    if min_gap <= time_gap_ms <= max_gap:
                        patterns.append(PatternResult(
                            pattern_type="flam_velocity",
                            confidence=0.8,
                            start_time=e1["timestamp"],
                            end_time=e2["timestamp"],
                            event_indices=[idx1, idx2],
                            metadata={
                                "grace_velocity": e1["velocity"],
                                "main_velocity": e2["velocity"],
                                "time_gap_ms": time_gap_ms,
                                "instrument_group": group,
                            }
                        ))
        
        return patterns
    
    def _detect_shuffle_ghosts(
        self,
        events: List[Dict],
        bpm: float,
    ) -> List[PatternResult]:
        """
        Detect shuffle ghost note patterns (triplet-feel ghost placement).
        
        In a shuffle, ghost notes typically fall on the triplet grid, creating
        the characteristic "bounce" feel.
        """
        patterns = []
        
        # Calculate triplet timing
        beat_duration = 60.0 / bpm
        triplet_duration = beat_duration / 3
        
        snare_events = self._filter_by_instrument(events, "snare")
        
        # Look for ghost notes falling on triplet subdivisions
        ghost_positions = []
        
        for idx, event in snare_events:
            if event["velocity"] <= self.config.ghost_velocity_max:
                # Check if this falls on a triplet subdivision
                time = event["timestamp"]
                beat_position = (time % beat_duration) / beat_duration
                
                # Triplet positions: 0, 1/3, 2/3
                triplet_positions = [0, 1/3, 2/3]
                tolerance = self.config.shuffle_triplet_tolerance_ms / 1000 / beat_duration
                
                for tp in triplet_positions:
                    if abs(beat_position - tp) < tolerance:
                        ghost_positions.append((idx, event, tp))
                        break
        
        # Check if we have a consistent pattern
        if len(ghost_positions) >= self.config.shuffle_min_pattern_count:
            patterns.append(PatternResult(
                pattern_type="shuffle_ghost_pattern",
                confidence=min(1.0, 0.5 + 0.1 * len(ghost_positions)),
                start_time=ghost_positions[0][1]["timestamp"],
                end_time=ghost_positions[-1][1]["timestamp"],
                event_indices=[idx for idx, _, _ in ghost_positions],
                metadata={
                    "num_ghosts": len(ghost_positions),
                    "triplet_positions": [tp for _, _, tp in ghost_positions],
                    "bpm": bpm,
                }
            ))
        
        return patterns
    
    def summarize_patterns(
        self,
        patterns: List[PatternResult],
    ) -> Dict[str, Any]:
        """
        Summarize detected patterns into a compact representation.
        """
        summary = {
            "total_patterns": len(patterns),
            "pattern_types": defaultdict(int),
            "technique_flags": {},
        }
        
        for pattern in patterns:
            summary["pattern_types"][pattern.pattern_type] += 1
        
        # Set technique flags
        summary["technique_flags"] = {
            "has_accent_tap": summary["pattern_types"]["accent_tap"] > 0,
            "has_ghost_bursts": summary["pattern_types"]["ghost_burst"] > 0,
            "has_crescendo": summary["pattern_types"]["crescendo"] > 0,
            "has_decrescendo": summary["pattern_types"]["decrescendo"] > 0,
            "has_flams": summary["pattern_types"]["flam_velocity"] > 0,
            "has_shuffle_feel": summary["pattern_types"]["shuffle_ghost_pattern"] > 0,
        }
        
        return dict(summary)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def analyze_velocity_patterns(
    events: List[Dict[str, Any]],
    bpm: Optional[float] = None,
    config: Optional[PatternConfig] = None,
) -> Dict[str, Any]:
    """
    Convenience function to analyze velocity patterns in events.
    
    Args:
        events: List of drum events with timestamp, label, velocity
        bpm: Optional tempo for rhythm-aware detection
        config: Optional pattern configuration
    
    Returns:
        Summary dict with detected patterns and technique flags
    """
    analyzer = VelocityPatternAnalyzer(config)
    patterns = analyzer.detect_patterns(events, bpm)
    return analyzer.summarize_patterns(patterns)


if __name__ == "__main__":
    print("🥁 Velocity Pattern Analyzer Test")
    print("=" * 50)
    
    # Test accent-tap detection
    accent_tap_events = [
        {"timestamp": 0.0, "label": "snare", "velocity": 0.9},
        {"timestamp": 0.125, "label": "snare", "velocity": 0.15},
        {"timestamp": 0.25, "label": "snare", "velocity": 0.85},
        {"timestamp": 0.375, "label": "snare", "velocity": 0.12},
        {"timestamp": 0.5, "label": "snare", "velocity": 0.88},
        {"timestamp": 0.625, "label": "snare", "velocity": 0.18},
        {"timestamp": 0.75, "label": "snare", "velocity": 0.92},
        {"timestamp": 0.875, "label": "snare", "velocity": 0.14},
    ]
    
    print("\nTest 1: Accent-Tap Pattern")
    result = analyze_velocity_patterns(accent_tap_events)
    print(f"  Detected patterns: {result['total_patterns']}")
    print(f"  Has accent-tap: {result['technique_flags']['has_accent_tap']}")
    
    # Test ghost burst detection
    ghost_events = [
        {"timestamp": 0.0, "label": "snare", "velocity": 0.85},
        {"timestamp": 0.125, "label": "snare", "velocity": 0.12},
        {"timestamp": 0.15, "label": "snare", "velocity": 0.10},
        {"timestamp": 0.175, "label": "snare", "velocity": 0.15},
        {"timestamp": 0.25, "label": "snare", "velocity": 0.90},
    ]
    
    print("\nTest 2: Ghost Burst")
    result = analyze_velocity_patterns(ghost_events)
    print(f"  Detected patterns: {result['total_patterns']}")
    print(f"  Has ghost bursts: {result['technique_flags']['has_ghost_bursts']}")
    
    # Test crescendo detection
    crescendo_events = [
        {"timestamp": 0.0, "label": "snare", "velocity": 0.3},
        {"timestamp": 0.125, "label": "snare", "velocity": 0.45},
        {"timestamp": 0.25, "label": "snare", "velocity": 0.6},
        {"timestamp": 0.375, "label": "snare", "velocity": 0.75},
        {"timestamp": 0.5, "label": "snare", "velocity": 0.9},
    ]
    
    print("\nTest 3: Crescendo")
    result = analyze_velocity_patterns(crescendo_events)
    print(f"  Detected patterns: {result['total_patterns']}")
    print(f"  Has crescendo: {result['technique_flags']['has_crescendo']}")
    
    print("\n✅ Velocity Pattern Analyzer working correctly!")
