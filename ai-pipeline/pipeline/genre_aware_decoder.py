"""
Genre-Aware Structured Decoding

This module provides genre-specific transition matrices and pattern recognition
for drum transcription. Different genres have distinct rhythmic vocabularies:

- Rock: Straight 8ths, kick-snare backbone, crash on downbeats
- Jazz: Swing feel, ride-based, ghost notes, syncopation
- Metal: Double bass, blast beats, china cymbals
- Funk: 16th note hi-hats, ghost notes, syncopated kicks
- Latin: Clave patterns, cowbell, timbale accents
- Electronic: Quantized, consistent patterns, four-on-the-floor

This is what separates "ML transcription" from "professional charting":
understanding the GENRE context and applying appropriate rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np

from .structured_decoder import DrumState, TransitionMatrix, DecodedEvent


class Genre(Enum):
    """Supported musical genres with distinct rhythmic vocabularies."""

    ROCK = "rock"
    METAL = "metal"
    PROG_METAL = "prog_metal"
    JAZZ = "jazz"
    FUNK = "funk"
    POP = "pop"
    LATIN = "latin"
    ELECTRONIC = "electronic"
    PROGRESSIVE = "progressive"
    BLUES = "blues"
    COUNTRY = "country"
    UNKNOWN = "unknown"


@dataclass
class GenreProfile:
    """
    Rhythmic profile for a specific genre.

    Encodes musical knowledge about typical patterns, acceptable
    densities, and style-specific transition probabilities.
    """

    genre: Genre
    name: str
    description: str

    # Typical tempo range
    tempo_range: Tuple[float, float] = (90, 140)

    # Dominant time signatures
    common_time_signatures: List[Tuple[int, int]] = field(
        default_factory=lambda: [(4, 4)]
    )

    # Swing characteristics (1.0 = straight, 1.5 = triplet feel)
    typical_swing_ratio: float = 1.0
    swing_tolerance: float = 0.1  # How much swing variance is acceptable

    # Dominant subdivision
    primary_subdivision: str = "sixteenth"

    # Hi-hat style
    hihat_density: str = "eighth"  # "quarter", "eighth", "sixteenth", "sparse"

    # Kick patterns
    kick_on_downbeats: float = 0.9  # Probability of kick on beat 1
    kick_syncopation: float = 0.2  # Probability of syncopated kicks

    # Snare characteristics
    backbeat_snare: float = 0.95  # Probability of snare on 2 and 4
    ghost_note_density: float = 0.3  # Relative frequency of ghost notes

    # Cymbal usage
    crash_on_sections: float = 0.85  # Crashes on section transitions
    ride_vs_hihat: float = 0.5  # 0 = all hi-hat, 1 = all ride

    # Tom fills
    fill_frequency: float = 0.25  # Fills every ~4 measures
    fill_complexity: float = 0.5  # 0 = simple, 1 = complex

    # Density limits (notes per second)
    typical_nps: float = 8.0
    max_burst_nps: float = 16.0

    # Custom transition modifiers (additive to base)
    transition_modifiers: Dict[Tuple[DrumState, DrumState], float] = field(
        default_factory=dict
    )


# =============================================================================
# GENRE PROFILES
# =============================================================================

GENRE_PROFILES: Dict[Genre, GenreProfile] = {
    Genre.ROCK: GenreProfile(
        genre=Genre.ROCK,
        name="Rock",
        description="Straight 8ths/16ths, kick-snare backbone, crash accents",
        tempo_range=(90, 160),
        common_time_signatures=[(4, 4)],
        typical_swing_ratio=1.0,
        hihat_density="eighth",
        kick_on_downbeats=0.9,
        kick_syncopation=0.2,
        backbeat_snare=0.95,
        ghost_note_density=0.1,
        crash_on_sections=0.9,
        typical_nps=6.0,
        max_burst_nps=14.0,
        transition_modifiers={
            # Rock: Kick → Hi-hat and Snare → Hi-hat are very common
            (DrumState.KICK, DrumState.HIHAT): 0.2,
            (DrumState.SNARE, DrumState.HIHAT): 0.2,
            # Crash typically follows section changes (after fill)
            (DrumState.TOM, DrumState.CYMBAL): 0.3,
        },
    ),
    Genre.METAL: GenreProfile(
        genre=Genre.METAL,
        name="Metal",
        description="Double bass, blast beats, china cymbals, high density",
        tempo_range=(120, 220),
        common_time_signatures=[(4, 4)],
        typical_swing_ratio=1.0,
        hihat_density="sixteenth",
        kick_on_downbeats=0.7,  # Less predictable
        kick_syncopation=0.5,  # More syncopation
        backbeat_snare=0.8,  # Less strict backbeat
        ghost_note_density=0.05,  # Fewer ghost notes
        crash_on_sections=0.95,
        typical_nps=12.0,
        max_burst_nps=24.0,  # Blast beats
        transition_modifiers={
            # Metal: Kick → Kick is common (double bass)
            (DrumState.KICK, DrumState.KICK): 0.4,
            # Snare → Snare for blast beats
            (DrumState.SNARE, DrumState.SNARE): 0.2,
            # Less hi-hat, more cymbal
            (DrumState.KICK, DrumState.CYMBAL): 0.15,
        },
    ),
    Genre.JAZZ: GenreProfile(
        genre=Genre.JAZZ,
        name="Jazz",
        description="Swing feel, ride-based, ghost notes, syncopation",
        tempo_range=(80, 200),
        common_time_signatures=[(4, 4), (3, 4), (5, 4), (7, 4)],
        typical_swing_ratio=1.5,  # Triplet swing
        swing_tolerance=0.2,
        primary_subdivision="triplet",
        hihat_density="sparse",  # Hi-hat mainly with foot
        kick_on_downbeats=0.6,  # Very syncopated
        kick_syncopation=0.7,
        backbeat_snare=0.4,  # Not locked to backbeat
        ghost_note_density=0.6,  # Lots of ghost notes
        crash_on_sections=0.5,  # Less crash usage
        ride_vs_hihat=0.9,  # Ride dominant
        typical_nps=7.0,
        max_burst_nps=15.0,
        transition_modifiers={
            # Jazz: Ghost → Snare is the signature
            (DrumState.GHOST, DrumState.SNARE): 0.5,
            # Ride patterns dominate
            (DrumState.CYMBAL, DrumState.CYMBAL): 0.3,
            # Kick more independent
            (DrumState.CYMBAL, DrumState.KICK): 0.2,
        },
    ),
    Genre.FUNK: GenreProfile(
        genre=Genre.FUNK,
        name="Funk",
        description="16th note hi-hats, ghost notes, syncopated kicks",
        tempo_range=(85, 130),
        common_time_signatures=[(4, 4)],
        typical_swing_ratio=1.0,  # Straight but with micro-timing
        hihat_density="sixteenth",
        kick_on_downbeats=0.6,  # Syncopated
        kick_syncopation=0.7,
        backbeat_snare=0.85,
        ghost_note_density=0.8,  # Ghost notes define funk
        crash_on_sections=0.7,
        typical_nps=10.0,
        max_burst_nps=16.0,
        transition_modifiers={
            # Funk: Ghost notes lead to everything
            (DrumState.GHOST, DrumState.SNARE): 0.5,
            (DrumState.GHOST, DrumState.GHOST): 0.3,
            # Hi-hat constant flow
            (DrumState.HIHAT, DrumState.HIHAT): 0.3,
            (DrumState.SNARE, DrumState.GHOST): 0.4,
        },
    ),
    Genre.PROGRESSIVE: GenreProfile(
        genre=Genre.PROGRESSIVE,
        name="Progressive",
        description="Odd meters, polyrhythms, metric modulation, complex fills",
        tempo_range=(70, 180),
        common_time_signatures=[(4, 4), (7, 8), (5, 4), (11, 8), (13, 8)],
        typical_swing_ratio=1.0,
        primary_subdivision="sixteenth",
        hihat_density="sixteenth",
        kick_on_downbeats=0.5,  # Very unpredictable
        kick_syncopation=0.8,
        backbeat_snare=0.5,  # Not locked
        ghost_note_density=0.4,
        crash_on_sections=0.8,
        fill_frequency=0.4,  # More fills
        fill_complexity=0.9,  # Complex fills
        typical_nps=10.0,
        max_burst_nps=20.0,
        transition_modifiers={
            # Prog: Tom fills are signature
            (DrumState.TOM, DrumState.TOM): 0.3,
            (DrumState.SNARE, DrumState.TOM): 0.2,
            # Odd patterns allowed
            (DrumState.KICK, DrumState.TOM): 0.15,
        },
    ),
    Genre.ELECTRONIC: GenreProfile(
        genre=Genre.ELECTRONIC,
        name="Electronic",
        description="Quantized, consistent patterns, four-on-the-floor",
        tempo_range=(100, 160),
        common_time_signatures=[(4, 4)],
        typical_swing_ratio=1.0,  # Perfectly straight
        swing_tolerance=0.05,  # Very strict
        hihat_density="eighth",
        kick_on_downbeats=1.0,  # Always on downbeat
        kick_syncopation=0.1,  # Minimal syncopation
        backbeat_snare=0.3,  # Often claps instead
        ghost_note_density=0.0,  # No ghost notes
        crash_on_sections=0.9,
        typical_nps=5.0,
        max_burst_nps=10.0,
        transition_modifiers={
            # Electronic: Predictable patterns
            (DrumState.KICK, DrumState.HIHAT): 0.4,
            (DrumState.HIHAT, DrumState.KICK): 0.2,
            (DrumState.SNARE, DrumState.HIHAT): 0.3,
        },
    ),
    Genre.LATIN: GenreProfile(
        genre=Genre.LATIN,
        name="Latin",
        description="Clave patterns, syncopation, percussion layers",
        tempo_range=(90, 140),
        common_time_signatures=[(4, 4), (6, 8)],
        typical_swing_ratio=1.0,
        hihat_density="sixteenth",
        kick_on_downbeats=0.5,  # Clave-based
        kick_syncopation=0.8,
        backbeat_snare=0.4,  # Timbale patterns
        ghost_note_density=0.3,
        crash_on_sections=0.6,
        fill_frequency=0.3,
        typical_nps=9.0,
        max_burst_nps=14.0,
        transition_modifiers={
            # Latin: Percussion layers
            (DrumState.HIHAT, DrumState.CYMBAL): 0.2,
            (DrumState.TOM, DrumState.SNARE): 0.2,
        },
    ),
    Genre.PROG_METAL: GenreProfile(
        genre=Genre.PROG_METAL,
        name="Progressive Metal",
        description="Double bass, odd meters, high syncopation, blast beats, complex fills",
        tempo_range=(100, 220),
        common_time_signatures=[(4, 4), (7, 8), (5, 4), (11, 8)],
        typical_swing_ratio=1.0,
        primary_subdivision="sixteenth",
        hihat_density="sixteenth",
        kick_on_downbeats=0.6,
        kick_syncopation=0.7,
        backbeat_snare=0.6,  # Moderate backbeat — not as locked as rock
        ghost_note_density=0.15,
        crash_on_sections=0.9,
        fill_frequency=0.35,
        fill_complexity=0.9,
        typical_nps=13.0,  # High density (double bass + cymbals)
        max_burst_nps=24.0,  # Blast beats
        transition_modifiers={
            (DrumState.KICK, DrumState.KICK): 0.4,  # Double bass
            (DrumState.SNARE, DrumState.SNARE): 0.2,  # Blast beats
            (DrumState.TOM, DrumState.TOM): 0.3,  # Tom fills
            (DrumState.SNARE, DrumState.TOM): 0.2,
            (DrumState.KICK, DrumState.CYMBAL): 0.15,
        },
    ),
    Genre.UNKNOWN: GenreProfile(
        genre=Genre.UNKNOWN,
        name="Unknown/General",
        description="Default profile for unidentified genres",
        tempo_range=(60, 200),
        common_time_signatures=[(4, 4)],
        typical_nps=8.0,
        max_burst_nps=16.0,
    ),
}


# =============================================================================
# GENRE DETECTION
# =============================================================================


def detect_genre(
    hits: List[Dict],
    bpm: float,
    detected_swing: float = 1.0,
    audio_features: Optional[Dict] = None,
) -> Tuple[Genre, float]:
    """
    Detect the most likely genre from hit patterns and audio features.

    Analyzes:
    - Tempo range match
    - Swing ratio match
    - Hit density patterns
    - Kick/snare placement
    - Ghost note frequency
    - Fill patterns

    Args:
        hits: Classified drum hits
        bpm: Detected tempo
        detected_swing: Detected swing ratio
        audio_features: Optional audio analysis features

    Returns:
        Tuple of (detected_genre, confidence)
    """
    if not hits:
        return Genre.UNKNOWN, 0.0

    scores: Dict[Genre, float] = {}

    for genre, profile in GENRE_PROFILES.items():
        if genre == Genre.UNKNOWN:
            continue

        score = 0.0
        max_score = 0.0

        # Tempo match (weighted VERY heavily — out-of-range genres should not win)
        max_score += 3.0
        if profile.tempo_range[0] <= bpm <= profile.tempo_range[1]:
            # Score based on how central the tempo is in the range
            range_center = (profile.tempo_range[0] + profile.tempo_range[1]) / 2
            range_width = profile.tempo_range[1] - profile.tempo_range[0]
            tempo_score = 1.0 - abs(bpm - range_center) / (range_width / 2)
            score += 3.0 * max(0, tempo_score)
        else:
            # NEGATIVE scoring: BPM outside range actively penalizes
            if bpm < profile.tempo_range[0]:
                distance = profile.tempo_range[0] - bpm
            else:
                distance = bpm - profile.tempo_range[1]
            penalty = min(1.0, distance / 40.0)  # Full penalty at 40 BPM out of range
            score -= 1.5 * penalty

        # Swing match
        max_score += 1.5
        swing_diff = abs(detected_swing - profile.typical_swing_ratio)
        if swing_diff <= profile.swing_tolerance:
            score += 1.5
        elif swing_diff <= profile.swing_tolerance * 2:
            score += 0.75

        # Analyze hit patterns
        hit_analysis = _analyze_hits_for_genre(hits, bpm, profile)

        # Ghost note density match
        max_score += 1.0
        ghost_diff = abs(hit_analysis["ghost_density"] - profile.ghost_note_density)
        if ghost_diff < 0.2:
            score += 1.0
        elif ghost_diff < 0.4:
            score += 0.5

        # Backbeat snare match
        max_score += 1.0
        backbeat_diff = abs(hit_analysis["backbeat_ratio"] - profile.backbeat_snare)
        if backbeat_diff < 0.15:
            score += 1.0
        elif backbeat_diff < 0.3:
            score += 0.5

        # Kick pattern match
        max_score += 1.0
        synco_diff = abs(hit_analysis["kick_syncopation"] - profile.kick_syncopation)
        if synco_diff < 0.2:
            score += 1.0
        elif synco_diff < 0.4:
            score += 0.5

        # Density match (with gating: extreme mismatch caps score)
        max_score += 1.0
        density_ratio = hit_analysis["avg_nps"] / profile.typical_nps if profile.typical_nps > 0 else 1.0
        if 0.7 <= density_ratio <= 1.4:
            score += 1.0
        elif 0.5 <= density_ratio <= 2.0:
            score += 0.5

        # Density gating: if density is >2.5x or <0.25x typical, cap score
        if density_ratio > 2.5 or density_ratio < 0.25:
            score = min(score, max_score * 0.35)

        # Normalize score
        scores[genre] = score / max_score if max_score > 0 else 0

    # Find best match
    best_genre = max(scores, key=scores.get)
    best_score = scores[best_genre]

    # Require minimum confidence
    if best_score < 0.4:
        return Genre.UNKNOWN, best_score

    return best_genre, best_score


def _analyze_hits_for_genre(
    hits: List[Dict],
    bpm: float,
    profile: GenreProfile,
) -> Dict[str, float]:
    """Analyze hit patterns for genre matching."""

    beat_duration = 60.0 / bpm

    result = {
        "ghost_density": 0.0,
        "backbeat_ratio": 0.0,
        "kick_syncopation": 0.0,
        "avg_nps": 0.0,
        "ride_vs_hihat": 0.0,
    }

    if not hits:
        return result

    sorted_hits = sorted(hits, key=lambda h: h.get("time", 0))
    total_time = sorted_hits[-1].get("time", 1) - sorted_hits[0].get("time", 0)

    if total_time <= 0:
        return result

    # Count components
    ghost_count = sum(1 for h in hits if "ghost" in h.get("component", "").lower())
    snare_count = sum(1 for h in hits if "snare" in h.get("component", "").lower())
    _kick_count = sum(1 for h in hits if "kick" in h.get("component", "").lower())
    hihat_count = sum(1 for h in hits if "hat" in h.get("component", "").lower())
    ride_count = sum(1 for h in hits if "ride" in h.get("component", "").lower())

    # Ghost density (relative to snare hits)
    if snare_count > 0:
        result["ghost_density"] = ghost_count / (ghost_count + snare_count)

    # Backbeat ratio (snares on beats 2 and 4)
    backbeat_snares = 0
    total_snares = 0
    for h in hits:
        if "snare" in h.get("component", "").lower():
            total_snares += 1
            time = h.get("time", 0)
            beat_pos = (time / beat_duration) % 4
            if 1.8 <= beat_pos <= 2.2 or 3.8 <= beat_pos <= 4.2 or beat_pos <= 0.2:
                # On beats 2 or 4 (with tolerance)
                if 1.8 <= beat_pos <= 2.2 or 3.8 <= beat_pos or beat_pos <= 0.2:
                    backbeat_snares += 1

    if total_snares > 0:
        result["backbeat_ratio"] = backbeat_snares / total_snares

    # Kick syncopation (kicks NOT on downbeat)
    syncopated_kicks = 0
    total_kicks = 0
    for h in hits:
        if "kick" in h.get("component", "").lower():
            total_kicks += 1
            time = h.get("time", 0)
            beat_pos = (time / beat_duration) % 1
            if beat_pos > 0.15:  # Not on downbeat
                syncopated_kicks += 1

    if total_kicks > 0:
        result["kick_syncopation"] = syncopated_kicks / total_kicks

    # Average NPS
    result["avg_nps"] = len(hits) / total_time

    # Ride vs hi-hat
    cymbal_total = hihat_count + ride_count
    if cymbal_total > 0:
        result["ride_vs_hihat"] = ride_count / cymbal_total

    return result


# =============================================================================
# GENRE-AWARE TRANSITION MATRIX
# =============================================================================


class GenreAwareTransitionMatrix(TransitionMatrix):
    """
    Transition matrix modified for a specific genre.

    Applies genre-specific modifiers to the base transition probabilities,
    creating more stylistically appropriate sequences.
    """

    def __init__(self, genre: Genre = Genre.UNKNOWN):
        super().__init__()
        self.genre = genre
        self.profile = GENRE_PROFILES.get(genre, GENRE_PROFILES[Genre.UNKNOWN])

        # Apply genre modifiers
        self._apply_genre_modifiers()

    def _apply_genre_modifiers(self):
        """Apply genre-specific transition modifiers."""
        for (
            from_state,
            to_state,
        ), modifier in self.profile.transition_modifiers.items():
            self.base_transitions[from_state.value, to_state.value] += modifier

        # Renormalize rows
        row_sums = self.base_transitions.sum(axis=1, keepdims=True)
        self.base_transitions = self.base_transitions / (row_sums + 1e-10)

        # Adjust IOI limits based on genre density
        density_factor = self.profile.typical_nps / 8.0  # Relative to default
        if density_factor > 1.0:
            # Higher density genre = allow faster hits
            for state in self.min_ioi:
                self.min_ioi[state] /= density_factor

    def get_transition_probs(
        self,
        beat_position: int,
        time_since_last: float,
        bpm: float = 120.0,
        adaptive_config=None,
    ) -> np.ndarray:
        """Get genre-aware transition probabilities."""
        probs = super().get_transition_probs(
            beat_position, time_since_last, bpm, adaptive_config
        )

        # Additional genre-specific beat modifiers
        if self.genre == Genre.ELECTRONIC:
            # Electronic: Boost kick on every beat
            if beat_position in [0, 1, 2, 3]:
                probs[:, DrumState.KICK.value] *= 1.2

        elif self.genre == Genre.JAZZ:
            # Jazz: Boost ghost notes before backbeat
            if beat_position in [0, 2]:  # Before 2 and 4
                probs[:, DrumState.GHOST.value] *= 1.3

        elif self.genre == Genre.METAL:
            # Metal: Allow kick → kick transitions (double bass)
            probs[DrumState.KICK.value, DrumState.KICK.value] = max(
                probs[DrumState.KICK.value, DrumState.KICK.value], 0.4
            )

        # Renormalize
        row_sums = probs.sum(axis=1, keepdims=True)
        return probs / (row_sums + 1e-10)


# =============================================================================
# GENRE-AWARE DECODER
# =============================================================================


class GenreAwareDecoder:
    """
    Decoder that automatically detects genre and applies
    genre-specific transition probabilities.

    This is the key innovation for "human-quality" charting:
    understanding musical CONTEXT, not just raw events.
    """

    def __init__(
        self,
        bpm: float = 120.0,
        time_signature: Tuple[int, int] = (4, 4),
        genre: Optional[Genre] = None,
        swing_ratio: float = 1.0,
    ):
        self.bpm = bpm
        self.time_signature = time_signature
        self.swing_ratio = swing_ratio

        # If genre provided, use it; otherwise will auto-detect
        self.genre = genre
        self.genre_confidence = 1.0 if genre else 0.0

        self.beat_duration = 60.0 / max(bpm, 1.0)
        self.measure_duration = self.beat_duration * time_signature[0]

    def decode(
        self,
        events: List[Dict],
        offset: float = 0.0,
        auto_detect_genre: bool = True,
    ) -> Tuple[List[DecodedEvent], Dict]:
        """
        Decode events with genre awareness.

        Args:
            events: Classified hits
            offset: Beat offset
            auto_detect_genre: Whether to auto-detect genre

        Returns:
            Tuple of (decoded_events, metadata)
        """
        if not events:
            return [], {"genre": Genre.UNKNOWN, "confidence": 0.0}

        # Auto-detect genre if needed
        if auto_detect_genre and self.genre is None:
            self.genre, self.genre_confidence = detect_genre(
                events, self.bpm, self.swing_ratio
            )

        # Create genre-aware transition matrix
        transitions = GenreAwareTransitionMatrix(self.genre or Genre.UNKNOWN)

        # Perform Viterbi decoding with genre-aware transitions
        events = sorted(events, key=lambda e: e.get("time", 0))
        n_events = len(events)
        n_states = len(DrumState)

        viterbi = np.zeros((n_events, n_states), dtype=np.float64)
        backpointer = np.zeros((n_events, n_states), dtype=np.int32)

        # Initialize
        first_event = events[0]
        emission_probs = self._get_emission_probs(first_event)
        viterbi[0] = np.log(emission_probs + 1e-10)

        # Forward pass
        last_time = first_event.get("time", 0)
        for t in range(1, n_events):
            event = events[t]
            current_time = event.get("time", 0)
            time_delta_ms = (current_time - last_time) * 1000

            beat_idx = self._get_beat_position(current_time, offset)
            trans_probs = transitions.get_transition_probs(
                beat_idx, time_delta_ms, self.bpm
            )
            emission_probs = self._get_emission_probs(event)

            for s in range(n_states):
                scores = viterbi[t - 1] + np.log(trans_probs[:, s] + 1e-10)
                best_prev = np.argmax(scores)
                viterbi[t, s] = scores[best_prev] + np.log(emission_probs[s] + 1e-10)
                backpointer[t, s] = best_prev

            last_time = current_time

        # Backtrack
        best_path = np.zeros(n_events, dtype=np.int32)
        best_path[-1] = np.argmax(viterbi[-1])

        for t in range(n_events - 2, -1, -1):
            best_path[t] = backpointer[t + 1, best_path[t + 1]]

        # Build decoded events
        decoded = []
        for t, event in enumerate(events):
            state = DrumState(best_path[t])
            current_time = event.get("time", 0)
            beat_idx = self._get_beat_position(current_time, offset)
            beat_frac = (current_time % self.beat_duration) / self.beat_duration

            decoded.append(
                DecodedEvent(
                    time=current_time,
                    state=state,
                    component=event.get("component", ""),
                    confidence=event.get("confidence", 0.0),
                    viterbi_prob=float(np.exp(viterbi[t, best_path[t]])),
                    beat_position=beat_idx + beat_frac,
                    is_backbeat=beat_idx in [1, 3] and beat_frac < 0.1,
                    transition_from=DrumState(best_path[t - 1]) if t > 0 else None,
                )
            )

        metadata = {
            "genre": self.genre,
            "genre_confidence": self.genre_confidence,
            "profile": GENRE_PROFILES.get(
                self.genre, GENRE_PROFILES[Genre.UNKNOWN]
            ).name,
        }

        return decoded, metadata

    def _get_beat_position(self, time: float, offset: float) -> int:
        """Get beat position for a given time."""
        adjusted_time = max(0, time - offset)
        position_in_measure = adjusted_time % self.measure_duration
        return min(
            int(position_in_measure / self.beat_duration), self.time_signature[0] - 1
        )

    def _get_emission_probs(self, event: Dict) -> np.ndarray:
        """Get emission probabilities for an event."""
        n_states = len(DrumState)
        probs = np.ones(n_states) * 0.01  # Small floor probability

        component = event.get("component", "")
        confidence = event.get("confidence", 0.5)

        # Map component to state
        state = DrumState.from_component(component)
        probs[state.value] = confidence

        # Add small probability mass to related states
        if state == DrumState.SNARE:
            probs[DrumState.GHOST.value] = 0.1 * confidence
        elif state == DrumState.GHOST:
            probs[DrumState.SNARE.value] = 0.1 * confidence

        # Normalize
        probs = probs / probs.sum()
        return probs


# =============================================================================
# INTEGRATION FUNCTION
# =============================================================================


def apply_genre_aware_decoding(
    classified_hits: List[Dict],
    bpm: float = 120.0,
    offset: float = 0.0,
    time_signature: Tuple[int, int] = (4, 4),
    swing_ratio: float = 1.0,
    genre: Optional[Genre] = None,
    mode: str = "gameplay",
) -> List[Dict]:
    """
    Apply genre-aware structured decoding to classified hits.

    This is the main entry point for genre-aware processing.

    In "transcription" mode, only lightweight genre annotation is applied
    (no Viterbi re-pass) to preserve raw model accuracy.

    In "gameplay" mode, full Viterbi decoding with genre-aware transitions
    is applied to produce more stylistically consistent charts.

    Args:
        classified_hits: List of classified drum hits
        bpm: Song tempo
        offset: Beat offset
        time_signature: Time signature
        swing_ratio: Detected swing ratio
        genre: Optional forced genre (None = auto-detect)
        mode: "gameplay" or "transcription"

    Returns:
        List of refined hits with genre-aware classification
    """
    # Detect genre (lightweight — no Viterbi needed for this)
    if genre is None:
        detected_genre, detected_confidence = detect_genre(
            classified_hits, bpm, swing_ratio
        )
    else:
        detected_genre = genre
        detected_confidence = 1.0

    # In transcription mode, only annotate with genre metadata — skip Viterbi
    # re-pass to preserve raw model accuracy.
    if mode == "transcription":
        sorted_hits = sorted(classified_hits, key=lambda h: h.get("time", 0))
        beat_duration = 60.0 / max(bpm, 1.0)
        annotated = []
        for hit in sorted_hits:
            refined = hit.copy()
            refined["genre"] = detected_genre.value
            refined["genre_confidence"] = detected_confidence
            hit_time = hit.get("time", 0)
            beat_pos = (hit_time / beat_duration) % time_signature[0]
            refined["beat_position"] = beat_pos
            beat_frac = (hit_time % beat_duration) / beat_duration
            beat_idx = int(beat_pos)
            refined["is_backbeat"] = beat_idx in [1, 3] and beat_frac < 0.1
            annotated.append(refined)
        return annotated

    # Gameplay mode: full Viterbi decode with genre-aware transitions
    decoder = GenreAwareDecoder(
        bpm=bpm,
        time_signature=time_signature,
        genre=detected_genre,
        swing_ratio=swing_ratio,
    )

    decoded, metadata = decoder.decode(
        classified_hits,
        offset=offset,
        auto_detect_genre=False,  # Already detected above
    )

    # Convert back to hit dictionaries
    refined_hits = []
    for event, original in zip(
        decoded, sorted(classified_hits, key=lambda h: h.get("time", 0))
    ):
        refined = original.copy()

        # IMPORTANT: Do NOT reassign component labels for multi-label output.
        # The multi-label classifier already detected the correct set of
        # components per onset. Viterbi decoding was designed for single-label
        # sequences and will incorrectly collapse multi-label output.
        # We only add metadata (genre, beat position, etc.) without
        # overwriting the classifier's component decisions.
        decoded_component = event.state.to_component_prefix()
        original_state = DrumState.from_component(refined.get("component", ""))
        if decoded_component and event.state != original_state:
            refined["decoded_state"] = decoded_component
            refined["state_refined"] = True
            refined["original_state"] = original_state.name.lower()
            # Keep original component — do NOT overwrite

        # Add genre metadata
        refined["genre"] = metadata["genre"].value
        refined["genre_confidence"] = metadata["genre_confidence"]
        refined["viterbi_prob"] = event.viterbi_prob
        refined["beat_position"] = event.beat_position
        refined["is_backbeat"] = event.is_backbeat

        refined_hits.append(refined)

    return refined_hits
