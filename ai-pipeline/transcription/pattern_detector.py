#!/usr/bin/env python3
"""
Musical Pattern Detection Post-Processor

This module analyzes sequences of detected drum hits to identify higher-level
musical patterns that cannot be detected from single-hit analysis alone.

=== DETECTED PATTERNS ===

1. CRASH BUILDS (Cymbal Crescendos)
   Repeated cymbal hits (crash, china, splash, ride, stack, etc.) that 
   crescendo in velocity/intensity leading to a climactic hit. 
   Common in transitions, breakdowns, and song climaxes.
   
   Detection: 3+ consecutive cymbal hits with increasing velocity over a
   short time window (typically 0.5-4 seconds).

2. ACCENT-TAP PATTERNS (Moeller Technique)
   Alternating loud (accent) and soft (tap/ghost) strokes, often using the
   Moeller whip technique. Creates a flowing, dynamic groove.
   
   Detection: Alternating high/low velocity pattern on same instrument
   with consistent timing grid (8ths, 16ths, triplets).

3. HI-HAT BARKING
   Quick open-close hi-hat articulation creating a "bark" sound. Can be
   single barks or continuous barking patterns.
   
   Detection: Open hi-hat immediately followed by closed hi-hat within
   a short time window (typically 20-80ms).

4. CONTINUOUS HI-HAT BARKING
   Repeated barking patterns in a rhythmic pattern (e.g., on every beat
   or on specific subdivisions).

5. HI-HAT SPLASHES
   Foot-opened hi-hat with longer sustain, creating an airy "shhh" sound.
   
   Detection: Hi-hat pedal/foot event with specific acoustic signature
   or hihat_open with specific velocity/timing characteristics.

Usage:
    from transcription.pattern_detector import PatternDetector, detect_all_patterns
    
    # Process detected events
    detector = PatternDetector()
    patterns = detector.detect(events)
    
    # Or use convenience function
    patterns = detect_all_patterns(events)
    
    # Annotate events with detected patterns
    annotated_events = detector.annotate_events(events, patterns)

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set, Union, Any
from enum import Enum, auto
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# PATTERN TYPE DEFINITIONS
# ============================================================================

class PatternCategory(Enum):
    """High-level categorization of detected patterns."""
    DYNAMIC = auto()      # Velocity/intensity patterns (crescendo, accent-tap)
    ARTICULATION = auto() # Playing technique patterns (barking, splashes)
    RHYTHMIC = auto()     # Timing-based patterns (fills, polyrhythms)
    STRUCTURAL = auto()   # Song structure patterns (builds, drops)


class PatternType(Enum):
    """Specific pattern types that can be detected."""
    # Dynamic patterns
    CRASH_BUILD = "crash_build"
    ACCENT_TAP = "accent_tap"
    CRESCENDO = "crescendo"
    DECRESCENDO = "decrescendo"
    SFORZANDO = "sforzando"
    
    # Hi-hat articulation patterns
    HIHAT_BARK = "hihat_bark"
    HIHAT_BARK_CONTINUOUS = "hihat_bark_continuous"
    HIHAT_SPLASH = "hihat_splash"
    HIHAT_FOOT_CHICK = "hihat_foot_chick"
    HIHAT_SIZZLE = "hihat_sizzle"
    
    # Cymbal patterns
    CRASH_RIDE = "crash_ride"           # Riding on crash cymbal
    BELL_ACCENT = "bell_accent"         # Bell hits for emphasis
    CYMBAL_CHOKE_PATTERN = "cymbal_choke_pattern"  # Repeated chokes
    
    # Roll/sustained patterns
    ROLL = "roll"
    BUZZ_ROLL = "buzz_roll"
    PRESS_ROLL = "press_roll"
    
    # Sticking patterns (when detectable from velocity/timing)
    PARADIDDLE = "paradiddle"
    DOUBLE_STROKE = "double_stroke"
    SINGLE_STROKE = "single_stroke"
    FLAM_TAP = "flam_tap"
    
    # Structural patterns
    FILL = "fill"
    TRANSITION = "transition"
    BREAKDOWN = "breakdown"


@dataclass
class DetectedPattern:
    """A detected musical pattern with its properties."""
    
    # Core identification
    pattern_type: PatternType
    category: PatternCategory
    
    # Temporal boundaries
    start_time: float           # Start time in seconds
    end_time: float             # End time in seconds
    duration: float = field(init=False)
    
    # Event references
    event_indices: List[int]    # Indices into the original event list
    event_count: int = field(init=False)
    
    # Pattern-specific properties
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # Confidence and quality
    confidence: float = 1.0     # Detection confidence (0-1)
    strength: float = 1.0       # Pattern strength/intensity (0-1)
    
    # Musical context
    instrument: Optional[str] = None    # Primary instrument involved
    instruments: List[str] = field(default_factory=list)  # All instruments
    
    # Unique identifier
    pattern_id: Optional[str] = None
    
    def __post_init__(self):
        self.duration = self.end_time - self.start_time
        self.event_count = len(self.event_indices)
        if self.pattern_id is None:
            self.pattern_id = f"{self.pattern_type.value}_{self.start_time:.3f}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern_type": self.pattern_type.value,
            "category": self.category.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "event_indices": self.event_indices,
            "event_count": self.event_count,
            "properties": self.properties,
            "confidence": self.confidence,
            "strength": self.strength,
            "instrument": self.instrument,
            "instruments": self.instruments,
            "pattern_id": self.pattern_id,
        }


@dataclass
class DrumEvent:
    """
    A single drum event for pattern analysis.
    
    This is a normalized representation that can be created from various
    input formats (training labels, inference results, beatmap objects).
    """
    timestamp: float            # Time in seconds
    label: str                  # Instrument label (e.g., "crash", "snare")
    velocity: float = 0.75      # Velocity/dynamics (0-1)
    
    # Optional technique annotations
    techniques: List[str] = field(default_factory=list)
    
    # Optional confidence from inference
    confidence: float = 1.0
    
    # Pattern annotations (filled by pattern detector)
    pattern_ids: List[str] = field(default_factory=list)
    articulation: Optional[str] = None
    dynamic_change: Optional[str] = None
    
    # Original index for reference
    original_index: Optional[int] = None


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PatternDetectorConfig:
    """Configuration for the pattern detector."""
    
    # === Crash Build Detection ===
    crash_build_min_hits: int = 3           # Minimum cymbal hits for a build
    crash_build_max_duration: float = 4.0   # Maximum duration in seconds
    crash_build_min_velocity_increase: float = 0.15  # Minimum velocity increase
    crash_build_velocity_tolerance: float = 0.05  # Allow small dips
    crash_build_max_gap: float = 0.5        # Maximum gap between hits
    crash_build_instruments: Tuple[str, ...] = (
        # All cymbal types - not just crash cymbals
        "crash", "china", "splash", "ride", "ride_bow", "ride_bell", 
        "cymbal", "stack", "bell", "trash",
        # Hi-hats (especially open hi-hats for intensity builds)
        "hihat", "hihat_open", "hihat_closed"
    )
    
    # === Accent-Tap Detection ===
    accent_tap_min_hits: int = 4            # Minimum hits for pattern
    accent_tap_velocity_threshold: float = 0.5  # Accent vs tap threshold
    accent_tap_max_deviation: float = 0.15  # Max velocity deviation from mean
    accent_tap_timing_tolerance: float = 0.03  # Timing consistency (seconds)
    accent_tap_instruments: Tuple[str, ...] = (
        "snare", "hihat_closed", "hihat_open", "ride_bow", 
        "tom_high", "tom_mid", "tom_low"
    )
    
    # === Hi-Hat Bark Detection ===
    bark_max_gap: float = 0.08              # Max gap between open and close (80ms)
    bark_min_gap: float = 0.015             # Min gap (15ms, prevent false positives)
    bark_open_labels: Tuple[str, ...] = ("hihat_open",)
    bark_close_labels: Tuple[str, ...] = ("hihat_closed", "hihat_pedal")
    bark_min_open_velocity: float = 0.3     # Open hit must be audible
    
    # === Continuous Bark Detection ===
    continuous_bark_min_count: int = 3      # Minimum barks for continuous
    continuous_bark_max_gap: float = 0.5    # Max gap between barks
    continuous_bark_regularity: float = 0.7  # Timing consistency threshold
    
    # === Hi-Hat Splash Detection ===
    splash_labels: Tuple[str, ...] = ("hihat_open", "hihat_pedal", "hihat_foot")
    splash_min_duration: float = 0.1        # Minimum sustain time
    splash_velocity_range: Tuple[float, float] = (0.2, 0.7)  # Typical splash velocity
    
    # === Crescendo/Decrescendo Detection ===
    dynamic_change_min_hits: int = 4        # Minimum hits for dynamic change
    dynamic_change_min_slope: float = 0.1   # Minimum velocity change per second
    dynamic_change_max_duration: float = 8.0  # Maximum pattern duration
    
    # === General Settings ===
    enable_all_patterns: bool = True
    enabled_patterns: Set[PatternType] = field(default_factory=lambda: set(PatternType))
    min_confidence: float = 0.5             # Minimum pattern confidence to report
    merge_overlapping: bool = True          # Merge overlapping patterns of same type


# ============================================================================
# PATTERN DETECTORS
# ============================================================================

class CrashBuildDetector:
    """
    Detects cymbal build patterns (crescendos on any cymbal type).
    
    A cymbal build is characterized by:
    - Multiple consecutive cymbal hits (3+) on any cymbal type
    - Increasing velocity/intensity
    - Relatively short duration (0.5-4 seconds)
    - Often ends with a climactic hit (highest velocity)
    
    Supported cymbals:
    - Crash cymbals
    - China cymbals
    - Splash cymbals
    - Ride cymbals (bow, bell, edge)
    - Stack cymbals
    - Trash cymbals / effects cymbals
    - Hi-hats (open and closed)
    
    Common in:
    - Song transitions
    - Pre-chorus builds
    - Drop buildups
    - Breakdown endings
    """
    
    def __init__(self, config: PatternDetectorConfig):
        self.config = config
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """Detect all crash build patterns in the event sequence."""
        patterns = []
        
        # Extract cymbal events with their indices
        cymbal_events = [
            (i, e) for i, e in enumerate(events)
            if self._is_cymbal(e.label)
        ]
        
        if len(cymbal_events) < self.config.crash_build_min_hits:
            return patterns
        
        # Sliding window to find build sequences
        i = 0
        while i < len(cymbal_events) - self.config.crash_build_min_hits + 1:
            # Try to extend a build from this position
            build = self._try_build_from(cymbal_events, i)
            
            if build is not None:
                patterns.append(build)
                # Skip past this build
                i += len(build.event_indices)
            else:
                i += 1
        
        return patterns
    
    def _is_cymbal(self, label: str) -> bool:
        """Check if label is a cymbal type."""
        label_lower = label.lower()
        return any(
            cym in label_lower 
            for cym in self.config.crash_build_instruments
        )
    
    def _try_build_from(
        self, 
        cymbal_events: List[Tuple[int, DrumEvent]], 
        start_idx: int
    ) -> Optional[DetectedPattern]:
        """Try to detect a crash build starting from the given index."""
        
        build_events = [cymbal_events[start_idx]]
        velocities = [cymbal_events[start_idx][1].velocity]
        
        for j in range(start_idx + 1, len(cymbal_events)):
            idx, event = cymbal_events[j]
            prev_idx, prev_event = build_events[-1]
            
            # Check timing gap
            gap = event.timestamp - prev_event.timestamp
            if gap > self.config.crash_build_max_gap:
                break
            
            # Check total duration
            duration = event.timestamp - cymbal_events[start_idx][1].timestamp
            if duration > self.config.crash_build_max_duration:
                break
            
            # Add to potential build
            build_events.append((idx, event))
            velocities.append(event.velocity)
        
        # Validate the build
        if len(build_events) < self.config.crash_build_min_hits:
            return None
        
        # Check for overall velocity increase
        velocities = np.array(velocities)
        velocity_trend = self._calculate_velocity_trend(velocities)
        
        if velocity_trend < self.config.crash_build_min_velocity_increase:
            return None
        
        # Calculate confidence based on trend strength and consistency
        trend_score = min(1.0, velocity_trend / 0.3)  # Normalize to ~0.3 max
        consistency = self._calculate_consistency(velocities)
        confidence = 0.6 * trend_score + 0.4 * consistency
        
        # Create pattern
        event_indices = [idx for idx, _ in build_events]
        start_time = build_events[0][1].timestamp
        end_time = build_events[-1][1].timestamp
        
        # Determine climax position
        peak_idx = np.argmax(velocities)
        is_climax_at_end = peak_idx >= len(velocities) - 2
        
        return DetectedPattern(
            pattern_type=PatternType.CRASH_BUILD,
            category=PatternCategory.DYNAMIC,
            start_time=start_time,
            end_time=end_time,
            event_indices=event_indices,
            confidence=confidence,
            strength=float(velocity_trend),
            instrument=build_events[0][1].label,
            instruments=list(set(e.label for _, e in build_events)),
            properties={
                "velocity_start": float(velocities[0]),
                "velocity_end": float(velocities[-1]),
                "velocity_peak": float(velocities.max()),
                "velocity_trend": float(velocity_trend),
                "hit_count": len(build_events),
                "hits_per_second": len(build_events) / (end_time - start_time + 0.001),
                "climax_at_end": is_climax_at_end,
                "peak_position": int(peak_idx),
            }
        )
    
    def _calculate_velocity_trend(self, velocities: np.ndarray) -> float:
        """
        Calculate the overall velocity trend.
        
        Returns a value indicating the velocity increase:
        - Positive = crescendo (building)
        - Negative = decrescendo
        - Near zero = flat
        """
        if len(velocities) < 2:
            return 0.0
        
        # Linear regression slope
        x = np.arange(len(velocities))
        slope, _ = np.polyfit(x, velocities, 1)
        
        # Also consider first-to-last difference
        diff = velocities[-1] - velocities[0]
        
        # Weighted combination (slope is more robust to outliers)
        return 0.6 * slope * len(velocities) + 0.4 * diff
    
    def _calculate_consistency(self, velocities: np.ndarray) -> float:
        """
        Calculate how consistent the velocity increase is.
        
        A perfectly consistent build has monotonically increasing velocity.
        Small dips are tolerated based on config tolerance.
        """
        if len(velocities) < 2:
            return 1.0
        
        # Count violations (decreases beyond tolerance)
        diffs = np.diff(velocities)
        violations = np.sum(diffs < -self.config.crash_build_velocity_tolerance)
        
        # More violations = less consistent
        consistency = 1.0 - (violations / (len(velocities) - 1))
        return max(0.0, consistency)


class AccentTapDetector:
    """
    Detects accent-tap patterns (Moeller technique).
    
    An accent-tap pattern is characterized by:
    - Alternating high (accent) and low (tap) velocities
    - Consistent rhythmic grid (8ths, 16ths, triplets)
    - Same instrument throughout
    - At least 4 hits (2 accent-tap pairs)
    
    Common in:
    - Funk and R&B grooves
    - Gospel drumming
    - Linear drumming patterns
    - Hi-hat and ride patterns
    """
    
    def __init__(self, config: PatternDetectorConfig):
        self.config = config
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """Detect all accent-tap patterns in the event sequence."""
        patterns = []
        
        # Group events by instrument
        instrument_groups = self._group_by_instrument(events)
        
        for instrument, inst_events in instrument_groups.items():
            if not self._is_valid_instrument(instrument):
                continue
            
            if len(inst_events) < self.config.accent_tap_min_hits:
                continue
            
            # Find accent-tap sequences
            inst_patterns = self._detect_in_instrument(inst_events, instrument)
            patterns.extend(inst_patterns)
        
        return patterns
    
    def _group_by_instrument(
        self, 
        events: List[DrumEvent]
    ) -> Dict[str, List[Tuple[int, DrumEvent]]]:
        """Group events by instrument label."""
        groups = defaultdict(list)
        for i, event in enumerate(events):
            # Normalize to base instrument (e.g., "snare_rimshot" -> "snare")
            base = self._get_base_instrument(event.label)
            groups[base].append((i, event))
        return groups
    
    def _get_base_instrument(self, label: str) -> str:
        """Extract base instrument from label."""
        # Handle variants like "snare_rimshot", "hihat_closed"
        parts = label.lower().split("_")
        if parts[0] in ("hihat", "hi"):
            return "hihat"
        return parts[0]
    
    def _is_valid_instrument(self, instrument: str) -> bool:
        """Check if instrument supports accent-tap patterns."""
        instrument_lower = instrument.lower()
        # Check both exact match and prefix match (for "hihat" matching "hihat_closed")
        for inst in self.config.accent_tap_instruments:
            inst_lower = inst.lower()
            # Get base of the config instrument too
            inst_base = inst_lower.split("_")[0]
            if inst_lower in ("hihat_closed", "hihat_open") and instrument_lower == "hihat":
                return True
            if instrument_lower == inst_base or instrument_lower == inst_lower:
                return True
            if inst_lower in instrument_lower or instrument_lower in inst_lower:
                return True
        return False
    
    def _detect_in_instrument(
        self,
        inst_events: List[Tuple[int, DrumEvent]],
        instrument: str
    ) -> List[DetectedPattern]:
        """Detect accent-tap patterns within a single instrument's events."""
        patterns = []
        
        i = 0
        while i < len(inst_events) - self.config.accent_tap_min_hits + 1:
            pattern = self._try_pattern_from(inst_events, i, instrument)
            
            if pattern is not None:
                patterns.append(pattern)
                i += len(pattern.event_indices)
            else:
                i += 1
        
        return patterns
    
    def _try_pattern_from(
        self,
        inst_events: List[Tuple[int, DrumEvent]],
        start_idx: int,
        instrument: str
    ) -> Optional[DetectedPattern]:
        """Try to detect an accent-tap pattern starting from given index."""
        
        # Collect velocities and timings
        velocities = []
        timings = []
        indices = []
        
        for j in range(start_idx, len(inst_events)):
            idx, event = inst_events[j]
            
            # Check for timing consistency
            if velocities:
                prev_time = inst_events[start_idx + len(velocities) - 1][1].timestamp
                gap = event.timestamp - prev_time
                
                if timings:
                    avg_gap = np.mean(timings)
                    if abs(gap - avg_gap) > avg_gap * 0.5:  # Allow 50% deviation
                        break
            
            velocities.append(event.velocity)
            if len(velocities) > 1:
                timings.append(event.timestamp - inst_events[j-1][1].timestamp)
            indices.append(idx)
        
        if len(velocities) < self.config.accent_tap_min_hits:
            return None
        
        velocities = np.array(velocities)
        
        # Check for alternating pattern
        alternation_score = self._check_alternation(velocities)
        
        if alternation_score < 0.6:
            return None
        
        # Check timing consistency
        if timings:
            timing_consistency = 1.0 - (np.std(timings) / (np.mean(timings) + 0.001))
        else:
            timing_consistency = 1.0
        
        if timing_consistency < 0.5:
            return None
        
        # Calculate pattern properties
        threshold = self.config.accent_tap_velocity_threshold
        accents = velocities >= threshold
        taps = velocities < threshold
        
        accent_mean = velocities[accents].mean() if accents.any() else 0.5
        tap_mean = velocities[taps].mean() if taps.any() else 0.5
        dynamic_range = accent_mean - tap_mean
        
        # Calculate confidence
        confidence = 0.4 * alternation_score + 0.3 * timing_consistency + 0.3 * min(1.0, dynamic_range * 2)
        
        if confidence < self.config.min_confidence:
            return None
        
        # Detect subdivision type
        if timings:
            avg_gap = np.mean(timings)
            subdivision = self._classify_subdivision(avg_gap)
        else:
            subdivision = "unknown"
        
        start_time = inst_events[start_idx][1].timestamp
        end_time = inst_events[start_idx + len(indices) - 1][1].timestamp
        
        return DetectedPattern(
            pattern_type=PatternType.ACCENT_TAP,
            category=PatternCategory.DYNAMIC,
            start_time=start_time,
            end_time=end_time,
            event_indices=indices,
            confidence=confidence,
            strength=dynamic_range,
            instrument=instrument,
            instruments=[instrument],
            properties={
                "accent_count": int(np.sum(accents)),
                "tap_count": int(np.sum(taps)),
                "accent_mean_velocity": float(accent_mean),
                "tap_mean_velocity": float(tap_mean),
                "dynamic_range": float(dynamic_range),
                "alternation_score": float(alternation_score),
                "timing_consistency": float(timing_consistency),
                "subdivision": subdivision,
                "avg_interval": float(np.mean(timings)) if timings else None,
            }
        )
    
    def _check_alternation(self, velocities: np.ndarray) -> float:
        """
        Check how well velocities alternate between high and low.
        
        Returns a score from 0-1 where:
        - 1.0 = perfect alternation
        - 0.0 = no alternation
        """
        if len(velocities) < 2:
            return 0.0
        
        threshold = self.config.accent_tap_velocity_threshold
        
        # Classify each hit
        is_accent = velocities >= threshold
        
        # Count alternations
        alternations = 0
        for i in range(1, len(is_accent)):
            if is_accent[i] != is_accent[i-1]:
                alternations += 1
        
        # Perfect alternation = len - 1 alternations
        max_alternations = len(velocities) - 1
        return alternations / max_alternations
    
    def _classify_subdivision(self, avg_gap: float) -> str:
        """Classify the subdivision type based on average gap."""
        # Assuming common tempos (60-180 BPM)
        # Quarter note at 120 BPM = 0.5s
        
        if avg_gap < 0.1:
            return "32nd_notes"
        elif avg_gap < 0.15:
            return "16th_triplets"
        elif avg_gap < 0.2:
            return "16th_notes"
        elif avg_gap < 0.3:
            return "8th_triplets"
        elif avg_gap < 0.4:
            return "8th_notes"
        elif avg_gap < 0.6:
            return "quarter_triplets"
        else:
            return "quarter_notes"


class HiHatBarkDetector:
    """
    Detects hi-hat barking patterns.
    
    A hi-hat bark is characterized by:
    - Quick open hi-hat immediately followed by closed hi-hat
    - Very short gap (typically 20-80ms)
    - Creates a distinctive "bark" or "chick" sound
    
    Can occur as:
    - Single barks (for accents)
    - Continuous barking (repeated pattern)
    - Syncopated barking
    """
    
    def __init__(self, config: PatternDetectorConfig):
        self.config = config
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """Detect all hi-hat bark patterns in the event sequence."""
        patterns = []
        
        # Find all individual barks first
        barks = self._find_individual_barks(events)
        
        if not barks:
            return patterns
        
        # Add individual barks as patterns
        for bark in barks:
            patterns.append(bark)
        
        # Detect continuous barking sequences
        continuous = self._find_continuous_barks(barks, events)
        patterns.extend(continuous)
        
        return patterns
    
    def _is_open(self, label: str) -> bool:
        """Check if label is open hi-hat."""
        label_lower = label.lower()
        return any(o in label_lower for o in self.config.bark_open_labels)
    
    def _is_close(self, label: str) -> bool:
        """Check if label is closed hi-hat."""
        label_lower = label.lower()
        return any(c in label_lower for c in self.config.bark_close_labels)
    
    def _find_individual_barks(
        self, 
        events: List[DrumEvent]
    ) -> List[DetectedPattern]:
        """Find all individual hi-hat barks."""
        barks = []
        used_indices = set()
        
        for i, event in enumerate(events):
            if i in used_indices:
                continue
                
            if not self._is_open(event.label):
                continue
            
            if event.velocity < self.config.bark_min_open_velocity:
                continue
            
            # Look for a close event shortly after
            for j in range(i + 1, min(i + 5, len(events))):
                close_event = events[j]
                
                if not self._is_close(close_event.label):
                    continue
                
                gap = close_event.timestamp - event.timestamp
                
                if self.config.bark_min_gap <= gap <= self.config.bark_max_gap:
                    # Found a bark!
                    bark = DetectedPattern(
                        pattern_type=PatternType.HIHAT_BARK,
                        category=PatternCategory.ARTICULATION,
                        start_time=event.timestamp,
                        end_time=close_event.timestamp,
                        event_indices=[i, j],
                        confidence=self._calculate_bark_confidence(gap, event.velocity),
                        strength=event.velocity,
                        instrument="hihat",
                        instruments=["hihat_open", "hihat_closed"],
                        properties={
                            "open_velocity": event.velocity,
                            "close_velocity": close_event.velocity,
                            "gap_ms": gap * 1000,
                            "open_index": i,
                            "close_index": j,
                        }
                    )
                    barks.append(bark)
                    used_indices.add(i)
                    used_indices.add(j)
                    break
        
        return barks
    
    def _calculate_bark_confidence(self, gap: float, velocity: float) -> float:
        """Calculate confidence for a single bark detection."""
        # Ideal gap is around 40-60ms
        ideal_gap = 0.05
        gap_score = 1.0 - abs(gap - ideal_gap) / self.config.bark_max_gap
        
        # Higher velocity = more confident it's intentional
        velocity_score = min(1.0, velocity / 0.8)
        
        return 0.6 * gap_score + 0.4 * velocity_score
    
    def _find_continuous_barks(
        self,
        barks: List[DetectedPattern],
        events: List[DrumEvent]
    ) -> List[DetectedPattern]:
        """Find sequences of continuous barking."""
        if len(barks) < self.config.continuous_bark_min_count:
            return []
        
        continuous_patterns = []
        
        # Sort barks by time
        sorted_barks = sorted(barks, key=lambda b: b.start_time)
        
        i = 0
        while i < len(sorted_barks):
            # Try to build a continuous sequence
            sequence = [sorted_barks[i]]
            gaps = []
            
            for j in range(i + 1, len(sorted_barks)):
                gap = sorted_barks[j].start_time - sorted_barks[j-1].end_time
                
                if gap > self.config.continuous_bark_max_gap:
                    break
                
                sequence.append(sorted_barks[j])
                gaps.append(gap)
            
            if len(sequence) >= self.config.continuous_bark_min_count:
                # Check timing regularity
                if gaps:
                    regularity = 1.0 - (np.std(gaps) / (np.mean(gaps) + 0.001))
                else:
                    regularity = 1.0
                
                if regularity >= self.config.continuous_bark_regularity:
                    # Create continuous pattern
                    all_indices = []
                    for bark in sequence:
                        all_indices.extend(bark.event_indices)
                    
                    pattern = DetectedPattern(
                        pattern_type=PatternType.HIHAT_BARK_CONTINUOUS,
                        category=PatternCategory.ARTICULATION,
                        start_time=sequence[0].start_time,
                        end_time=sequence[-1].end_time,
                        event_indices=all_indices,
                        confidence=regularity * np.mean([b.confidence for b in sequence]),
                        strength=np.mean([b.strength for b in sequence]),
                        instrument="hihat",
                        instruments=["hihat_open", "hihat_closed"],
                        properties={
                            "bark_count": len(sequence),
                            "regularity": float(regularity),
                            "avg_gap_ms": float(np.mean(gaps) * 1000) if gaps else 0,
                            "barks_per_second": len(sequence) / (sequence[-1].end_time - sequence[0].start_time + 0.001),
                            "child_bark_ids": [b.pattern_id for b in sequence],
                        }
                    )
                    continuous_patterns.append(pattern)
                
                i += len(sequence)
            else:
                i += 1
        
        return continuous_patterns


class HiHatSplashDetector:
    """
    Detects hi-hat splash patterns.
    
    A hi-hat splash is characterized by:
    - Foot-operated open hi-hat (pedal opens then closes)
    - Longer sustain than a bark
    - Creates an airy "shhh" sound
    - Typically lower velocity than stick hits
    
    Can occur as:
    - Foot splashes (hihat_pedal/foot events)
    - Open hi-hats with specific velocity profile
    """
    
    def __init__(self, config: PatternDetectorConfig):
        self.config = config
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """Detect all hi-hat splash patterns."""
        patterns = []
        
        for i, event in enumerate(events):
            if not self._is_splash_candidate(event):
                continue
            
            # Check for subsequent events to determine sustain
            sustain_info = self._analyze_sustain(events, i)
            
            if sustain_info["is_splash"]:
                pattern = DetectedPattern(
                    pattern_type=PatternType.HIHAT_SPLASH,
                    category=PatternCategory.ARTICULATION,
                    start_time=event.timestamp,
                    end_time=event.timestamp + sustain_info["duration"],
                    event_indices=[i] + sustain_info["related_indices"],
                    confidence=sustain_info["confidence"],
                    strength=event.velocity,
                    instrument="hihat",
                    instruments=["hihat"],
                    properties={
                        "velocity": event.velocity,
                        "estimated_sustain": sustain_info["duration"],
                        "splash_type": sustain_info["type"],
                    }
                )
                patterns.append(pattern)
        
        return patterns
    
    def _is_splash_candidate(self, event: DrumEvent) -> bool:
        """Check if event could be a splash."""
        label_lower = event.label.lower()
        
        # Check if it's a hihat event
        if not any(s in label_lower for s in self.config.splash_labels):
            return False
        
        # Check velocity range
        min_vel, max_vel = self.config.splash_velocity_range
        if not (min_vel <= event.velocity <= max_vel):
            return False
        
        return True
    
    def _analyze_sustain(
        self, 
        events: List[DrumEvent], 
        idx: int
    ) -> Dict[str, Any]:
        """Analyze the sustain characteristics of a potential splash."""
        event = events[idx]
        
        # Look for the next hi-hat event (close)
        next_hihat_idx = None
        for j in range(idx + 1, min(idx + 10, len(events))):
            if "hihat" in events[j].label.lower():
                next_hihat_idx = j
                break
        
        if next_hihat_idx is not None:
            duration = events[next_hihat_idx].timestamp - event.timestamp
            related = [next_hihat_idx]
        else:
            # Assume typical splash duration
            duration = 0.2
            related = []
        
        # Determine if this is a splash based on duration
        is_splash = duration >= self.config.splash_min_duration
        
        # Classify splash type
        if "pedal" in event.label.lower() or "foot" in event.label.lower():
            splash_type = "foot_splash"
            confidence = 0.9 if is_splash else 0.3
        else:
            splash_type = "open_splash"
            confidence = 0.7 if is_splash else 0.2
        
        return {
            "is_splash": is_splash,
            "duration": duration,
            "confidence": confidence,
            "type": splash_type,
            "related_indices": related,
        }


class CrescendoDecrescendoDetector:
    """
    Detects general crescendo and decrescendo patterns.
    
    Unlike crash builds which are specific to cymbals, this detects
    velocity changes on any instrument or across the full kit.
    """
    
    def __init__(self, config: PatternDetectorConfig):
        self.config = config
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """Detect crescendo and decrescendo patterns."""
        patterns = []
        
        if len(events) < self.config.dynamic_change_min_hits:
            return patterns
        
        # Sliding window analysis
        window_size = self.config.dynamic_change_min_hits
        
        for i in range(len(events) - window_size + 1):
            window = events[i:i + window_size]
            
            # Check for crescendo
            cresc = self._check_dynamic_change(window, is_crescendo=True)
            if cresc is not None:
                patterns.append(cresc)
            
            # Check for decrescendo
            decresc = self._check_dynamic_change(window, is_crescendo=False)
            if decresc is not None:
                patterns.append(decresc)
        
        # Merge overlapping patterns
        patterns = self._merge_overlapping(patterns)
        
        return patterns
    
    def _check_dynamic_change(
        self,
        window: List[DrumEvent],
        is_crescendo: bool
    ) -> Optional[DetectedPattern]:
        """Check if window contains a dynamic change."""
        velocities = np.array([e.velocity for e in window])
        times = np.array([e.timestamp for e in window])
        
        # Calculate slope
        duration = times[-1] - times[0]
        if duration < 0.1:
            return None
        
        # Linear regression
        slope, intercept = np.polyfit(times - times[0], velocities, 1)
        slope_per_second = slope
        
        # Check direction matches
        if is_crescendo and slope_per_second < self.config.dynamic_change_min_slope:
            return None
        if not is_crescendo and slope_per_second > -self.config.dynamic_change_min_slope:
            return None
        
        # Calculate fit quality (R²)
        predicted = intercept + slope * (times - times[0])
        ss_res = np.sum((velocities - predicted) ** 2)
        ss_tot = np.sum((velocities - velocities.mean()) ** 2)
        r_squared = 1 - (ss_res / (ss_tot + 0.001))
        
        if r_squared < 0.5:
            return None
        
        pattern_type = PatternType.CRESCENDO if is_crescendo else PatternType.DECRESCENDO
        
        return DetectedPattern(
            pattern_type=pattern_type,
            category=PatternCategory.DYNAMIC,
            start_time=times[0],
            end_time=times[-1],
            event_indices=list(range(len(window))),  # Relative indices
            confidence=r_squared,
            strength=abs(slope_per_second),
            instrument=None,
            instruments=list(set(e.label for e in window)),
            properties={
                "velocity_start": float(velocities[0]),
                "velocity_end": float(velocities[-1]),
                "slope_per_second": float(slope_per_second),
                "r_squared": float(r_squared),
                "hit_count": len(window),
            }
        )
    
    def _merge_overlapping(
        self, 
        patterns: List[DetectedPattern]
    ) -> List[DetectedPattern]:
        """Merge overlapping patterns of the same type."""
        if not patterns:
            return patterns
        
        # Group by type
        by_type = defaultdict(list)
        for p in patterns:
            by_type[p.pattern_type].append(p)
        
        merged = []
        for pattern_type, type_patterns in by_type.items():
            # Sort by start time
            type_patterns.sort(key=lambda p: p.start_time)
            
            current = type_patterns[0]
            for next_p in type_patterns[1:]:
                # Check overlap
                if next_p.start_time <= current.end_time:
                    # Merge
                    current = DetectedPattern(
                        pattern_type=pattern_type,
                        category=current.category,
                        start_time=current.start_time,
                        end_time=max(current.end_time, next_p.end_time),
                        event_indices=list(set(current.event_indices + next_p.event_indices)),
                        confidence=(current.confidence + next_p.confidence) / 2,
                        strength=(current.strength + next_p.strength) / 2,
                        instrument=current.instrument,
                        instruments=list(set(current.instruments + next_p.instruments)),
                        properties={**current.properties, **next_p.properties},
                    )
                else:
                    merged.append(current)
                    current = next_p
            
            merged.append(current)
        
        return merged


# ============================================================================
# MAIN PATTERN DETECTOR
# ============================================================================

class PatternDetector:
    """
    Main pattern detection orchestrator.
    
    Coordinates all individual pattern detectors and provides a unified
    interface for pattern detection and event annotation.
    
    Usage:
        detector = PatternDetector()
        patterns = detector.detect(events)
        annotated = detector.annotate_events(events, patterns)
    """
    
    def __init__(self, config: Optional[PatternDetectorConfig] = None):
        self.config = config or PatternDetectorConfig()
        
        # Initialize individual detectors
        self.crash_build_detector = CrashBuildDetector(self.config)
        self.accent_tap_detector = AccentTapDetector(self.config)
        self.hihat_bark_detector = HiHatBarkDetector(self.config)
        self.hihat_splash_detector = HiHatSplashDetector(self.config)
        self.crescendo_detector = CrescendoDecrescendoDetector(self.config)
    
    def detect(self, events: List[DrumEvent]) -> List[DetectedPattern]:
        """
        Detect all patterns in the event sequence.
        
        Args:
            events: List of drum events to analyze
            
        Returns:
            List of detected patterns
        """
        all_patterns = []
        
        # Run each detector
        logger.debug(f"Detecting patterns in {len(events)} events")
        
        # Crash builds
        crash_builds = self.crash_build_detector.detect(events)
        all_patterns.extend(crash_builds)
        logger.debug(f"Found {len(crash_builds)} crash builds")
        
        # Accent-tap patterns
        accent_taps = self.accent_tap_detector.detect(events)
        all_patterns.extend(accent_taps)
        logger.debug(f"Found {len(accent_taps)} accent-tap patterns")
        
        # Hi-hat barks
        barks = self.hihat_bark_detector.detect(events)
        all_patterns.extend(barks)
        logger.debug(f"Found {len(barks)} hi-hat bark patterns")
        
        # Hi-hat splashes
        splashes = self.hihat_splash_detector.detect(events)
        all_patterns.extend(splashes)
        logger.debug(f"Found {len(splashes)} hi-hat splash patterns")
        
        # Crescendos/Decrescendos
        dynamics = self.crescendo_detector.detect(events)
        all_patterns.extend(dynamics)
        logger.debug(f"Found {len(dynamics)} dynamic change patterns")
        
        # Sort by start time
        all_patterns.sort(key=lambda p: p.start_time)
        
        # Filter by confidence
        filtered = [
            p for p in all_patterns 
            if p.confidence >= self.config.min_confidence
        ]
        
        logger.info(f"Detected {len(filtered)} patterns (filtered from {len(all_patterns)})")
        
        return filtered
    
    def annotate_events(
        self,
        events: List[DrumEvent],
        patterns: List[DetectedPattern]
    ) -> List[DrumEvent]:
        """
        Annotate events with their associated patterns.
        
        Modifies events in-place to add pattern_ids and articulation info.
        
        Args:
            events: Original events
            patterns: Detected patterns
            
        Returns:
            Annotated events (same list, modified in-place)
        """
        # Build index of which patterns each event belongs to
        event_patterns: Dict[int, List[str]] = defaultdict(list)
        event_articulations: Dict[int, str] = {}
        event_dynamics: Dict[int, str] = {}
        
        for pattern in patterns:
            for idx in pattern.event_indices:
                if 0 <= idx < len(events):
                    event_patterns[idx].append(pattern.pattern_id)
                    
                    # Set articulation for certain pattern types
                    if pattern.pattern_type == PatternType.HIHAT_BARK:
                        event_articulations[idx] = "bark"
                    elif pattern.pattern_type == PatternType.HIHAT_SPLASH:
                        event_articulations[idx] = "splash"
                    elif pattern.pattern_type == PatternType.ACCENT_TAP:
                        # Determine if accent or tap based on velocity
                        if events[idx].velocity >= self.config.accent_tap_velocity_threshold:
                            event_articulations[idx] = "accent"
                        else:
                            event_articulations[idx] = "tap"
                    
                    # Set dynamic change
                    if pattern.pattern_type == PatternType.CRASH_BUILD:
                        event_dynamics[idx] = "crescendo"
                    elif pattern.pattern_type == PatternType.CRESCENDO:
                        event_dynamics[idx] = "crescendo"
                    elif pattern.pattern_type == PatternType.DECRESCENDO:
                        event_dynamics[idx] = "decrescendo"
        
        # Apply annotations
        for i, event in enumerate(events):
            if i in event_patterns:
                event.pattern_ids = event_patterns[i]
            if i in event_articulations:
                event.articulation = event_articulations[i]
            if i in event_dynamics:
                event.dynamic_change = event_dynamics[i]
        
        return events
    
    def get_pattern_summary(self, patterns: List[DetectedPattern]) -> Dict[str, Any]:
        """Get a summary of detected patterns."""
        summary = {
            "total_patterns": len(patterns),
            "by_type": defaultdict(int),
            "by_category": defaultdict(int),
            "confidence_stats": {
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
            },
            "duration_stats": {
                "mean": 0.0,
                "min": 0.0,
                "max": 0.0,
                "total": 0.0,
            },
        }
        
        if not patterns:
            return summary
        
        for p in patterns:
            summary["by_type"][p.pattern_type.value] += 1
            summary["by_category"][p.category.name] += 1
        
        confidences = [p.confidence for p in patterns]
        durations = [p.duration for p in patterns]
        
        summary["confidence_stats"] = {
            "mean": float(np.mean(confidences)),
            "min": float(min(confidences)),
            "max": float(max(confidences)),
        }
        summary["duration_stats"] = {
            "mean": float(np.mean(durations)),
            "min": float(min(durations)),
            "max": float(max(durations)),
            "total": float(sum(durations)),
        }
        
        return summary


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def detect_all_patterns(
    events: List[DrumEvent],
    config: Optional[PatternDetectorConfig] = None
) -> List[DetectedPattern]:
    """
    Convenience function to detect all patterns in an event sequence.
    
    Args:
        events: List of drum events
        config: Optional configuration
        
    Returns:
        List of detected patterns
    """
    detector = PatternDetector(config)
    return detector.detect(events)


def events_from_labels(
    labels: List[Dict[str, Any]],
    timestamp_key: str = "timestamp",
    label_key: str = "label",
    velocity_key: str = "velocity",
    default_velocity: float = 0.75,
) -> List[DrumEvent]:
    """
    Convert label dictionaries to DrumEvent objects.
    
    Args:
        labels: List of label dictionaries
        timestamp_key: Key for timestamp field
        label_key: Key for label field
        velocity_key: Key for velocity field
        default_velocity: Default velocity if not present
        
    Returns:
        List of DrumEvent objects
    """
    events = []
    
    for i, label in enumerate(labels):
        event = DrumEvent(
            timestamp=label.get(timestamp_key, 0.0),
            label=label.get(label_key, "unknown"),
            velocity=label.get(velocity_key, default_velocity),
            techniques=label.get("techniques", []),
            confidence=label.get("confidence", 1.0),
            original_index=i,
        )
        events.append(event)
    
    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)
    
    return events


def patterns_to_json(patterns: List[DetectedPattern]) -> List[Dict[str, Any]]:
    """Convert patterns to JSON-serializable dictionaries."""
    return [p.to_dict() for p in patterns]


# ============================================================================
# INTEGRATION WITH BEATMAP/TRANSCRIPTION
# ============================================================================

def annotate_transcription_result(
    events: List[Dict[str, Any]],
    config: Optional[PatternDetectorConfig] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process transcription results and add pattern annotations.
    
    This is the main integration point for the transcription pipeline.
    Takes raw transcription output and returns annotated events with
    pattern information.
    
    Args:
        events: Raw transcription events (list of dicts)
        config: Optional pattern detection config
        
    Returns:
        Tuple of (annotated_events, detected_patterns)
    """
    # Convert to DrumEvent objects
    drum_events = events_from_labels(events)
    
    # Detect patterns
    detector = PatternDetector(config)
    patterns = detector.detect(drum_events)
    
    # Annotate events
    annotated = detector.annotate_events(drum_events, patterns)
    
    # Convert back to dictionaries
    annotated_dicts = []
    for i, event in enumerate(annotated):
        original = events[event.original_index] if event.original_index is not None else {}
        annotated_dict = {
            **original,
            "timestamp": event.timestamp,
            "label": event.label,
            "velocity": event.velocity,
            "pattern_ids": event.pattern_ids,
            "articulation": event.articulation,
            "dynamic_change": event.dynamic_change,
        }
        annotated_dicts.append(annotated_dict)
    
    pattern_dicts = patterns_to_json(patterns)
    
    return annotated_dicts, pattern_dicts


# ============================================================================
# MAIN (DEMO/TEST)
# ============================================================================

if __name__ == "__main__":
    import json
    
    print("🥁 Pattern Detector Demo")
    print("=" * 60)
    
    # Create sample events
    sample_events = [
        # Crash build example
        DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
        DrumEvent(timestamp=0.25, label="crash", velocity=0.4),
        DrumEvent(timestamp=0.5, label="crash", velocity=0.55),
        DrumEvent(timestamp=0.75, label="crash", velocity=0.7),
        DrumEvent(timestamp=1.0, label="crash", velocity=0.9),
        
        # Hi-hat barking example
        DrumEvent(timestamp=2.0, label="hihat_open", velocity=0.6),
        DrumEvent(timestamp=2.04, label="hihat_closed", velocity=0.5),
        DrumEvent(timestamp=2.5, label="hihat_open", velocity=0.65),
        DrumEvent(timestamp=2.54, label="hihat_closed", velocity=0.5),
        DrumEvent(timestamp=3.0, label="hihat_open", velocity=0.6),
        DrumEvent(timestamp=3.04, label="hihat_closed", velocity=0.5),
        
        # Accent-tap example on snare
        DrumEvent(timestamp=4.0, label="snare", velocity=0.9),   # Accent
        DrumEvent(timestamp=4.125, label="snare", velocity=0.3),  # Tap
        DrumEvent(timestamp=4.25, label="snare", velocity=0.85),  # Accent
        DrumEvent(timestamp=4.375, label="snare", velocity=0.25), # Tap
        DrumEvent(timestamp=4.5, label="snare", velocity=0.9),    # Accent
        DrumEvent(timestamp=4.625, label="snare", velocity=0.3),  # Tap
        DrumEvent(timestamp=4.75, label="snare", velocity=0.88),  # Accent
        DrumEvent(timestamp=4.875, label="snare", velocity=0.28), # Tap
    ]
    
    print(f"\n📊 Sample events: {len(sample_events)}")
    for e in sample_events[:5]:
        print(f"  {e.timestamp:.2f}s: {e.label} (vel={e.velocity:.2f})")
    print("  ...")
    
    # Detect patterns
    detector = PatternDetector()
    patterns = detector.detect(sample_events)
    
    print(f"\n✨ Detected {len(patterns)} patterns:")
    for pattern in patterns:
        print(f"\n  📌 {pattern.pattern_type.value}")
        print(f"     Time: {pattern.start_time:.2f}s - {pattern.end_time:.2f}s")
        print(f"     Events: {pattern.event_count}")
        print(f"     Confidence: {pattern.confidence:.2f}")
        print(f"     Properties: {json.dumps(pattern.properties, indent=8)}")
    
    # Annotate events
    annotated = detector.annotate_events(sample_events, patterns)
    
    print("\n📝 Annotated events (sample):")
    for e in annotated:
        if e.pattern_ids or e.articulation:
            print(f"  {e.timestamp:.2f}s: {e.label}")
            if e.pattern_ids:
                print(f"     Patterns: {e.pattern_ids}")
            if e.articulation:
                print(f"     Articulation: {e.articulation}")
            if e.dynamic_change:
                print(f"     Dynamic: {e.dynamic_change}")
    
    # Summary
    summary = detector.get_pattern_summary(patterns)
    print(f"\n📈 Summary:")
    print(f"  Total patterns: {summary['total_patterns']}")
    print(f"  By type: {dict(summary['by_type'])}")
    print(f"  By category: {dict(summary['by_category'])}")
    
    print("\n✅ Pattern detection complete!")
