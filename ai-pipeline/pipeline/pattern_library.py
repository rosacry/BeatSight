"""
Drum Pattern Library for Intelligent Pattern Recognition

This module provides a library of common drum patterns that can be:
1. Recognized in raw transcription (pattern matching)
2. Used to repair ambiguous/noisy transcriptions
3. Applied for auto-generation suggestions

Patterns are organized by:
- Category (groove, fill, transition)
- Genre (rock, jazz, funk, metal, etc.)
- Complexity (beginner, intermediate, advanced)

This is what separates "AI transcription" from "professional charting":
recognizing that a sequence of hits IS a known pattern and should be
charted consistently according to that pattern's canonical form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence
from enum import Enum
import numpy as np
import re


class PatternCategory(Enum):
    """Categories of drum patterns."""
    GROOVE = "groove"          # Main beat patterns
    FILL = "fill"              # Fill patterns (usually 1-2 beats)
    TRANSITION = "transition"  # Section transitions (crashes, stops)
    INTRO = "intro"            # Intro patterns (count-in, build-up)
    BREAKDOWN = "breakdown"    # Sparse/breakdown patterns
    BUILDUP = "buildup"        # Building intensity


class PatternComplexity(Enum):
    """Complexity levels for patterns."""
    BEGINNER = 1      # Simple, standard patterns
    INTERMEDIATE = 2  # Common but requires coordination
    ADVANCED = 3      # Technical patterns
    EXPERT = 4        # Challenging patterns
    MASTER = 5        # Elite-level patterns


@dataclass
class DrumPattern:
    """
    A single drum pattern with timing and classification.
    
    Patterns are defined relative to beat positions (0.0 = beat 1, 1.0 = beat 2, etc.)
    with components at each position.
    """
    name: str
    id: str
    category: PatternCategory
    complexity: PatternComplexity
    description: str
    
    # Pattern definition: list of (beat_position, component, velocity)
    # Beat positions are relative (0.0 to length_beats)
    hits: List[Tuple[float, str, float]] = field(default_factory=list)
    
    # Pattern length in beats
    length_beats: float = 4.0
    
    # Time signature this pattern fits
    time_signature: Tuple[int, int] = (4, 4)
    
    # Genre tags
    genres: List[str] = field(default_factory=list)
    
    # Can this pattern repeat?
    repeatable: bool = True
    
    # Typical tempo range
    tempo_range: Tuple[float, float] = (60, 200)
    
    # Swing ratio (1.0 = straight, 1.5 = triplet swing)
    swing: float = 1.0
    
    # Variations (IDs of related patterns)
    variations: List[str] = field(default_factory=list)
    
    def get_hits_in_range(self, start_beat: float, end_beat: float) -> List[Tuple[float, str, float]]:
        """Get hits within a beat range."""
        return [
            (pos, comp, vel)
            for pos, comp, vel in self.hits
            if start_beat <= pos < end_beat
        ]
    
    def to_absolute_times(self, bpm: float, offset: float = 0.0) -> List[Dict]:
        """Convert pattern to absolute time events."""
        beat_duration = 60.0 / bpm
        events = []
        for pos, comp, vel in self.hits:
            events.append({
                'time': offset + pos * beat_duration,
                'component': comp,
                'velocity': vel,
                'pattern_id': self.id,
                'pattern_beat': pos,
            })
        return events


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

# Basic Rock Patterns
ROCK_PATTERNS = [
    DrumPattern(
        name="Basic Rock Beat",
        id="rock_basic_4",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.BEGINNER,
        description="Standard 4/4 rock beat with kick on 1/3, snare on 2/4",
        hits=[
            # Beat 1
            (0.0, "kick", 1.0),
            (0.0, "hihat_closed", 0.8),
            (0.5, "hihat_closed", 0.6),
            # Beat 2
            (1.0, "snare", 1.0),
            (1.0, "hihat_closed", 0.8),
            (1.5, "hihat_closed", 0.6),
            # Beat 3
            (2.0, "kick", 1.0),
            (2.0, "hihat_closed", 0.8),
            (2.5, "hihat_closed", 0.6),
            # Beat 4
            (3.0, "snare", 1.0),
            (3.0, "hihat_closed", 0.8),
            (3.5, "hihat_closed", 0.6),
        ],
        length_beats=4.0,
        genres=["rock", "pop"],
        tempo_range=(80, 140),
    ),
    
    DrumPattern(
        name="Driving Rock",
        id="rock_driving_4",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.BEGINNER,
        description="Four-on-the-floor kick pattern for driving rock",
        hits=[
            (0.0, "kick", 1.0), (0.0, "hihat_closed", 0.8),
            (0.5, "hihat_closed", 0.6),
            (1.0, "kick", 0.9), (1.0, "snare", 1.0), (1.0, "hihat_closed", 0.8),
            (1.5, "hihat_closed", 0.6),
            (2.0, "kick", 1.0), (2.0, "hihat_closed", 0.8),
            (2.5, "hihat_closed", 0.6),
            (3.0, "kick", 0.9), (3.0, "snare", 1.0), (3.0, "hihat_closed", 0.8),
            (3.5, "hihat_closed", 0.6),
        ],
        length_beats=4.0,
        genres=["rock", "alternative"],
        tempo_range=(100, 160),
    ),
    
    DrumPattern(
        name="Half-Time Rock",
        id="rock_halftime",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.BEGINNER,
        description="Half-time feel with snare on 3",
        hits=[
            (0.0, "kick", 1.0), (0.0, "crash", 0.9),
            (0.5, "hihat_closed", 0.6),
            (1.0, "hihat_closed", 0.7),
            (1.5, "hihat_closed", 0.6),
            (2.0, "snare", 1.0), (2.0, "hihat_closed", 0.8),
            (2.5, "hihat_closed", 0.6),
            (3.0, "hihat_closed", 0.7),
            (3.5, "kick", 0.8), (3.5, "hihat_closed", 0.6),
        ],
        length_beats=4.0,
        genres=["rock", "grunge"],
        tempo_range=(70, 120),
    ),
]

# Funk Patterns
FUNK_PATTERNS = [
    DrumPattern(
        name="Basic Funk",
        id="funk_basic_16",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.INTERMEDIATE,
        description="16th note hi-hat funk pattern with ghost notes",
        hits=[
            # Beat 1
            (0.0, "kick", 1.0), (0.0, "hihat_closed", 0.8),
            (0.25, "hihat_closed", 0.5),
            (0.5, "hihat_closed", 0.6),
            (0.75, "ghost", 0.4), (0.75, "hihat_closed", 0.5),
            # Beat 2
            (1.0, "snare", 1.0), (1.0, "hihat_closed", 0.8),
            (1.25, "hihat_closed", 0.5),
            (1.5, "kick", 0.7), (1.5, "hihat_closed", 0.6),
            (1.75, "hihat_closed", 0.5),
            # Beat 3
            (2.0, "hihat_closed", 0.7),
            (2.25, "ghost", 0.4), (2.25, "hihat_closed", 0.5),
            (2.5, "kick", 0.9), (2.5, "hihat_closed", 0.6),
            (2.75, "ghost", 0.4), (2.75, "hihat_closed", 0.5),
            # Beat 4
            (3.0, "snare", 1.0), (3.0, "hihat_closed", 0.8),
            (3.25, "hihat_closed", 0.5),
            (3.5, "hihat_closed", 0.6),
            (3.75, "ghost", 0.4), (3.75, "hihat_closed", 0.5),
        ],
        length_beats=4.0,
        genres=["funk", "soul", "r&b"],
        tempo_range=(85, 120),
    ),
    
    DrumPattern(
        name="Syncopated Funk",
        id="funk_syncopated",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.ADVANCED,
        description="Heavily syncopated funk with off-beat kicks",
        hits=[
            (0.0, "kick", 1.0), (0.0, "hihat_closed", 0.8),
            (0.25, "hihat_closed", 0.5),
            (0.5, "hihat_closed", 0.6),
            (0.75, "kick", 0.7), (0.75, "hihat_closed", 0.5),
            (1.0, "snare", 1.0), (1.0, "hihat_closed", 0.8),
            (1.25, "ghost", 0.4), (1.25, "hihat_closed", 0.5),
            (1.5, "hihat_closed", 0.6),
            (1.75, "hihat_closed", 0.5),
            (2.0, "hihat_closed", 0.7),
            (2.25, "kick", 0.8), (2.25, "hihat_closed", 0.5),
            (2.5, "ghost", 0.4), (2.5, "hihat_closed", 0.6),
            (2.75, "ghost", 0.5), (2.75, "hihat_closed", 0.5),
            (3.0, "snare", 1.0), (3.0, "hihat_closed", 0.8),
            (3.25, "hihat_closed", 0.5),
            (3.5, "kick", 0.6), (3.5, "hihat_closed", 0.6),
            (3.75, "hihat_closed", 0.5),
        ],
        length_beats=4.0,
        genres=["funk", "fusion"],
        tempo_range=(90, 115),
    ),
]

# Jazz Patterns
JAZZ_PATTERNS = [
    DrumPattern(
        name="Jazz Ride Pattern",
        id="jazz_ride_swing",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.INTERMEDIATE,
        description="Standard jazz ride pattern with swing",
        hits=[
            # Using triplet feel positions (swing)
            (0.0, "ride", 0.9),
            (0.67, "ride", 0.6),  # Swung position
            (1.0, "ride", 0.8),
            (1.67, "ride", 0.6),
            (2.0, "ride", 0.9),
            (2.67, "ride", 0.6),
            (3.0, "ride", 0.8),
            (3.67, "ride", 0.6),
            # Hi-hat on 2 and 4
            (1.0, "hihat_pedal", 0.7),
            (3.0, "hihat_pedal", 0.7),
        ],
        length_beats=4.0,
        time_signature=(4, 4),
        swing=1.5,
        genres=["jazz", "bebop", "swing"],
        tempo_range=(100, 200),
    ),
    
    DrumPattern(
        name="Jazz Waltz",
        id="jazz_waltz_3",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.INTERMEDIATE,
        description="3/4 jazz waltz pattern",
        hits=[
            (0.0, "ride", 0.9),
            (0.67, "ride", 0.5),
            (1.0, "ride", 0.7),
            (1.67, "ride", 0.5),
            (2.0, "ride", 0.7),
            (2.67, "ride", 0.5),
            # Hi-hat on 2
            (1.0, "hihat_pedal", 0.7),
        ],
        length_beats=3.0,
        time_signature=(3, 4),
        swing=1.4,
        genres=["jazz"],
        tempo_range=(90, 180),
    ),
]

# Metal Patterns
METAL_PATTERNS = [
    DrumPattern(
        name="Double Bass Pattern",
        id="metal_doublebass",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.ADVANCED,
        description="16th note double bass pattern",
        hits=[
            # 16th note kicks
            (0.0, "kick", 1.0), (0.25, "kick", 0.9),
            (0.5, "kick", 0.95), (0.75, "kick", 0.9),
            (1.0, "kick", 1.0), (1.0, "snare", 1.0),
            (1.25, "kick", 0.9), (1.5, "kick", 0.95), (1.75, "kick", 0.9),
            (2.0, "kick", 1.0), (2.25, "kick", 0.9),
            (2.5, "kick", 0.95), (2.75, "kick", 0.9),
            (3.0, "kick", 1.0), (3.0, "snare", 1.0),
            (3.25, "kick", 0.9), (3.5, "kick", 0.95), (3.75, "kick", 0.9),
            # Ride pattern
            (0.0, "ride", 0.8), (0.5, "ride", 0.7),
            (1.0, "ride", 0.8), (1.5, "ride", 0.7),
            (2.0, "ride", 0.8), (2.5, "ride", 0.7),
            (3.0, "ride", 0.8), (3.5, "ride", 0.7),
        ],
        length_beats=4.0,
        genres=["metal", "death metal", "thrash"],
        tempo_range=(100, 180),
    ),
    
    DrumPattern(
        name="Blast Beat",
        id="metal_blast",
        category=PatternCategory.GROOVE,
        complexity=PatternComplexity.EXPERT,
        description="Standard blast beat pattern",
        hits=[
            # Alternating snare/kick on 16ths with ride
            (0.0, "kick", 1.0), (0.0, "ride", 0.9),
            (0.25, "snare", 1.0),
            (0.5, "kick", 1.0), (0.5, "ride", 0.8),
            (0.75, "snare", 1.0),
            (1.0, "kick", 1.0), (1.0, "ride", 0.9),
            (1.25, "snare", 1.0),
            (1.5, "kick", 1.0), (1.5, "ride", 0.8),
            (1.75, "snare", 1.0),
            (2.0, "kick", 1.0), (2.0, "ride", 0.9),
            (2.25, "snare", 1.0),
            (2.5, "kick", 1.0), (2.5, "ride", 0.8),
            (2.75, "snare", 1.0),
            (3.0, "kick", 1.0), (3.0, "ride", 0.9),
            (3.25, "snare", 1.0),
            (3.5, "kick", 1.0), (3.5, "ride", 0.8),
            (3.75, "snare", 1.0),
        ],
        length_beats=4.0,
        genres=["metal", "black metal", "death metal", "grindcore"],
        tempo_range=(140, 220),
    ),
]

# Fill Patterns
FILL_PATTERNS = [
    DrumPattern(
        name="Simple Tom Fill",
        id="fill_tom_basic",
        category=PatternCategory.FILL,
        complexity=PatternComplexity.BEGINNER,
        description="Basic descending tom fill",
        hits=[
            (0.0, "snare", 1.0),
            (0.5, "tom_high", 0.9),
            (1.0, "tom_mid", 0.9),
            (1.5, "tom_low", 0.9),
        ],
        length_beats=2.0,
        genres=["rock", "pop"],
        repeatable=False,
    ),
    
    DrumPattern(
        name="16th Note Fill",
        id="fill_16th_toms",
        category=PatternCategory.FILL,
        complexity=PatternComplexity.INTERMEDIATE,
        description="16th note fill around the toms",
        hits=[
            (0.0, "snare", 1.0), (0.25, "snare", 0.8),
            (0.5, "tom_high", 0.9), (0.75, "tom_high", 0.7),
            (1.0, "tom_mid", 0.9), (1.25, "tom_mid", 0.7),
            (1.5, "tom_low", 0.9), (1.75, "tom_low", 0.8),
        ],
        length_beats=2.0,
        genres=["rock", "metal"],
        repeatable=False,
    ),
    
    DrumPattern(
        name="Triplet Fill",
        id="fill_triplet_snare",
        category=PatternCategory.FILL,
        complexity=PatternComplexity.INTERMEDIATE,
        description="Snare triplet fill leading to crash",
        hits=[
            (0.0, "snare", 1.0), (0.33, "snare", 0.8), (0.67, "snare", 0.9),
            (1.0, "snare", 1.0), (1.33, "snare", 0.8), (1.67, "snare", 0.9),
        ],
        length_beats=2.0,
        swing=1.0,  # Triplets, not swing
        genres=["rock", "blues"],
        repeatable=False,
    ),
]

# Transition Patterns
TRANSITION_PATTERNS = [
    DrumPattern(
        name="Crash on One",
        id="trans_crash",
        category=PatternCategory.TRANSITION,
        complexity=PatternComplexity.BEGINNER,
        description="Crash cymbal marking section change",
        hits=[
            (0.0, "kick", 1.0),
            (0.0, "crash", 1.0),
        ],
        length_beats=1.0,
        genres=["all"],
        repeatable=False,
    ),
    
    DrumPattern(
        name="Build-up Snare Roll",
        id="trans_snare_buildup",
        category=PatternCategory.BUILDUP,
        complexity=PatternComplexity.INTERMEDIATE,
        description="Snare roll building intensity",
        hits=[
            # Accelerating snare hits
            (0.0, "snare", 0.6),
            (0.5, "snare", 0.65),
            (1.0, "snare", 0.7), (1.25, "snare", 0.65),
            (1.5, "snare", 0.75), (1.75, "snare", 0.7),
            (2.0, "snare", 0.8), (2.25, "snare", 0.75), (2.5, "snare", 0.8), (2.75, "snare", 0.8),
            (3.0, "snare", 0.85), (3.125, "snare", 0.8), (3.25, "snare", 0.85), (3.375, "snare", 0.85),
            (3.5, "snare", 0.9), (3.625, "snare", 0.9), (3.75, "snare", 0.95), (3.875, "snare", 1.0),
        ],
        length_beats=4.0,
        genres=["rock", "electronic"],
        repeatable=False,
    ),
]


# =============================================================================
# PATTERN LIBRARY
# =============================================================================

class PatternLibrary:
    """
    Central library for managing and querying drum patterns.
    """
    
    def __init__(self):
        """Initialize with built-in patterns."""
        self.patterns: Dict[str, DrumPattern] = {}
        self._load_builtin_patterns()
    
    def _load_builtin_patterns(self):
        """Load all built-in patterns."""
        all_patterns = (
            ROCK_PATTERNS + 
            FUNK_PATTERNS + 
            JAZZ_PATTERNS + 
            METAL_PATTERNS + 
            FILL_PATTERNS + 
            TRANSITION_PATTERNS
        )
        for pattern in all_patterns:
            self.patterns[pattern.id] = pattern
    
    def get_pattern(self, pattern_id: str) -> Optional[DrumPattern]:
        """Get a pattern by ID."""
        return self.patterns.get(pattern_id)
    
    def find_patterns(
        self,
        category: Optional[PatternCategory] = None,
        genre: Optional[str] = None,
        max_complexity: Optional[PatternComplexity] = None,
        tempo: Optional[float] = None,
        time_signature: Optional[Tuple[int, int]] = None,
    ) -> List[DrumPattern]:
        """
        Find patterns matching criteria.
        
        Args:
            category: Filter by category
            genre: Filter by genre
            max_complexity: Maximum complexity level
            tempo: Filter by tempo range
            time_signature: Filter by time signature
            
        Returns:
            List of matching patterns
        """
        matches = []
        
        for pattern in self.patterns.values():
            # Category filter
            if category and pattern.category != category:
                continue
            
            # Genre filter
            if genre and genre.lower() not in [g.lower() for g in pattern.genres]:
                if "all" not in pattern.genres:
                    continue
            
            # Complexity filter
            if max_complexity and pattern.complexity.value > max_complexity.value:
                continue
            
            # Tempo filter
            if tempo:
                if not (pattern.tempo_range[0] <= tempo <= pattern.tempo_range[1]):
                    continue
            
            # Time signature filter
            if time_signature and pattern.time_signature != time_signature:
                continue
            
            matches.append(pattern)
        
        return matches
    
    def match_pattern(
        self,
        hits: List[Dict],
        bpm: float,
        tolerance_ms: float = 50.0,
        min_match_ratio: float = 0.7,
    ) -> List[Tuple[DrumPattern, float, float]]:
        """
        Find patterns that match a sequence of hits.
        
        Args:
            hits: Sequence of classified hits
            bpm: Tempo
            tolerance_ms: Timing tolerance
            min_match_ratio: Minimum match ratio to consider
            
        Returns:
            List of (pattern, match_score, start_time) tuples
        """
        if not hits:
            return []
        
        beat_duration = 60.0 / bpm
        tolerance = tolerance_ms / 1000.0
        
        matches = []
        sorted_hits = sorted(hits, key=lambda h: h.get('time', 0))
        
        # Try each pattern at each possible start position
        for pattern in self.patterns.values():
            pattern_length = pattern.length_beats * beat_duration
            
            # For each hit as potential pattern start
            for start_idx, start_hit in enumerate(sorted_hits):
                start_time = start_hit.get('time', 0)
                end_time = start_time + pattern_length
                
                # Get hits in this window
                window_hits = [
                    h for h in sorted_hits
                    if start_time <= h.get('time', 0) < end_time
                ]
                
                # Calculate match score
                score = self._calculate_match_score(
                    pattern, window_hits, start_time, bpm, tolerance
                )
                
                if score >= min_match_ratio:
                    matches.append((pattern, score, start_time))
        
        # Sort by score
        matches.sort(key=lambda x: -x[1])
        return matches
    
    def _calculate_match_score(
        self,
        pattern: DrumPattern,
        hits: List[Dict],
        start_time: float,
        bpm: float,
        tolerance: float,
    ) -> float:
        """Calculate how well hits match a pattern."""
        if not hits or not pattern.hits:
            return 0.0
        
        beat_duration = 60.0 / bpm
        
        # Convert pattern to absolute times
        pattern_events = pattern.to_absolute_times(bpm, start_time)
        
        matched_pattern_hits = 0
        matched_actual_hits = set()
        
        for p_event in pattern_events:
            p_time = p_event['time']
            p_comp = p_event['component'].lower()
            
            # Find closest matching hit
            best_match = None
            best_dist = float('inf')
            
            for i, hit in enumerate(hits):
                if i in matched_actual_hits:
                    continue
                
                h_time = hit.get('time', 0)
                h_comp = hit.get('component', '').lower()
                
                # Check component match
                if not self._components_match(p_comp, h_comp):
                    continue
                
                dist = abs(h_time - p_time)
                if dist < best_dist and dist <= tolerance:
                    best_dist = dist
                    best_match = i
            
            if best_match is not None:
                matched_pattern_hits += 1
                matched_actual_hits.add(best_match)
        
        # Score based on how many pattern hits were matched
        pattern_match_ratio = matched_pattern_hits / len(pattern_events)
        
        # Penalize extra hits not in pattern
        extra_hits = len(hits) - len(matched_actual_hits)
        extra_penalty = extra_hits / (len(hits) + 1) * 0.3
        
        return max(0, pattern_match_ratio - extra_penalty)
    
    def _components_match(self, pattern_comp: str, hit_comp: str) -> bool:
        """Check if a pattern component matches a hit component."""
        # Exact match
        if pattern_comp == hit_comp:
            return True
        
        # Category matches
        if 'hihat' in pattern_comp and 'hihat' in hit_comp:
            return True
        if 'tom' in pattern_comp and 'tom' in hit_comp:
            return True
        if pattern_comp in ['crash', 'ride', 'cymbal'] and \
           any(x in hit_comp for x in ['crash', 'ride', 'china', 'splash']):
            return True
        
        return False


# =============================================================================
# PATTERN-BASED REPAIR
# =============================================================================

def repair_with_patterns(
    hits: List[Dict],
    bpm: float,
    library: Optional[PatternLibrary] = None,
    confidence_threshold: float = 0.6,
) -> List[Dict]:
    """
    Repair low-confidence hits using pattern matching.
    
    If a sequence of hits matches a known pattern, use the pattern's
    canonical form to repair ambiguous classifications.
    
    Args:
        hits: Classified hits with confidence scores
        bpm: Tempo
        library: Pattern library (uses default if None)
        confidence_threshold: Below this, attempt repair
        
    Returns:
        Repaired hit list
    """
    if library is None:
        library = PatternLibrary()
    
    # Find pattern matches
    matches = library.match_pattern(hits, bpm, min_match_ratio=0.6)
    
    if not matches:
        return hits
    
    # Sort hits by time
    sorted_hits = sorted(hits, key=lambda h: h.get('time', 0))
    repaired = [h.copy() for h in sorted_hits]
    
    beat_duration = 60.0 / bpm
    
    # Apply best matching patterns
    applied_regions = set()  # Track which time regions we've already repaired
    
    for pattern, score, start_time in matches:
        # Skip if this region already repaired
        end_time = start_time + pattern.length_beats * beat_duration
        region_key = (round(start_time, 3), round(end_time, 3))
        
        if region_key in applied_regions:
            continue
        
        # Only apply if pattern is a strong match
        if score < 0.7:
            continue
        
        # Get pattern events
        pattern_events = pattern.to_absolute_times(bpm, start_time)
        
        # Repair low-confidence hits in this region
        for i, hit in enumerate(repaired):
            hit_time = hit.get('time', 0)
            if not (start_time <= hit_time < end_time):
                continue
            
            if hit.get('confidence', 1.0) >= confidence_threshold:
                continue  # Don't repair high-confidence hits
            
            # Find matching pattern event
            for p_event in pattern_events:
                if abs(p_event['time'] - hit_time) < 0.05:  # 50ms tolerance
                    # Repair with pattern's component
                    repaired[i] = hit.copy()
                    repaired[i]['component'] = p_event['component']
                    repaired[i]['pattern_repaired'] = True
                    repaired[i]['pattern_id'] = pattern.id
                    repaired[i]['pattern_confidence'] = score
                    break
        
        applied_regions.add(region_key)
    
    return repaired


# =============================================================================
# GLOBAL LIBRARY INSTANCE
# =============================================================================

# Singleton pattern library
_library_instance: Optional[PatternLibrary] = None


def get_pattern_library() -> PatternLibrary:
    """Get the global pattern library instance."""
    global _library_instance
    if _library_instance is None:
        _library_instance = PatternLibrary()
    return _library_instance
