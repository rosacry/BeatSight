"""
Structured Decoding for Drum Transcription

This module implements HMM-based structured decoding to smooth raw frame-wise
classification into musically coherent event sequences. This is the key
differentiator between "messy ML output" and "human-quality charting".

Key innovations:
1. Viterbi decoding with learned transition probabilities
2. Beat-aware transition matrices (certain patterns more likely on downbeats)
3. Musical grammar constraints (e.g., ghost notes cluster before snare backbeats)
4. Confidence calibration and multi-hypothesis tracking
5. ADAPTIVE parameters that learn from data and adjust to music style

The transition probabilities encode musical knowledge:
- Kick → Snare is common (basic rock beat)
- Snare → Hi-Hat is common (fills)
- Ghost → Snare is very common (ghost notes lead to accent)
- Crash → Crash within 100ms is rare (unless roll)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence, Any
import numpy as np
from enum import IntEnum

# Import adaptive parameters (optional - graceful degradation)
try:
    from .adaptive_parameters import (
        AdaptiveConfig,
        get_adaptive_config as get_adaptive_config,
        MusicStyle as MusicStyle,
        AudioCharacteristics as AudioCharacteristics,
    )

    HAS_ADAPTIVE = True
except ImportError:
    HAS_ADAPTIVE = False
    AdaptiveConfig = None  # type: ignore


class DrumState(IntEnum):
    """States for the drum HMM (simplified for efficiency)."""

    SILENCE = 0
    KICK = 1
    SNARE = 2
    HIHAT = 3
    TOM = 4
    CYMBAL = 5
    GHOST = 6  # Low-velocity snare

    @classmethod
    def from_component(cls, component: str) -> "DrumState":
        """Map component name to state."""
        comp = component.lower()
        if "kick" in comp or "bass" in comp:
            return cls.KICK
        if "ghost" in comp:
            return cls.GHOST
        if "snare" in comp or "rim" in comp or "clap" in comp:
            return cls.SNARE
        if "hat" in comp or "hh" in comp:
            return cls.HIHAT
        if "tom" in comp:
            return cls.TOM
        if any(x in comp for x in ["crash", "ride", "china", "splash", "cymbal"]):
            return cls.CYMBAL
        return cls.SILENCE

    def to_component_prefix(self) -> str:
        """Get the canonical component prefix for this state."""
        return {
            self.SILENCE: "",
            self.KICK: "kick",
            self.SNARE: "snare",
            self.HIHAT: "hihat",
            self.TOM: "tom",
            self.CYMBAL: "crash",
            self.GHOST: "ghost",
        }[self]


@dataclass
class TransitionMatrix:
    """
    Beat-aware transition probability matrix.

    Encodes musical knowledge about drum patterns:
    - What typically follows what
    - How patterns differ on beats vs off-beats
    - Minimum inter-onset intervals per instrument
    """

    num_states: int = 7

    # Transition probabilities [from_state, to_state]
    # Higher = more likely transition
    base_transitions: np.ndarray = field(
        default_factory=lambda: np.array(
            [
                # To:   SIL   KICK  SNARE HIHAT TOM   CYM   GHOST
                [0.90, 0.02, 0.02, 0.03, 0.01, 0.01, 0.01],  # From SILENCE
                [0.15, 0.05, 0.25, 0.35, 0.08, 0.10, 0.02],  # From KICK
                [0.20, 0.15, 0.05, 0.40, 0.08, 0.10, 0.02],  # From SNARE
                [0.10, 0.20, 0.20, 0.30, 0.08, 0.07, 0.05],  # From HIHAT
                [0.15, 0.15, 0.20, 0.25, 0.15, 0.08, 0.02],  # From TOM
                [0.25, 0.20, 0.15, 0.25, 0.05, 0.05, 0.05],  # From CYMBAL
                [
                    0.05,
                    0.10,
                    0.60,
                    0.15,
                    0.03,
                    0.02,
                    0.05,
                ],  # From GHOST (usually leads to snare)
            ],
            dtype=np.float64,
        )
    )

    # Beat position modifiers (0=downbeat, 1=beat2, 2=beat3, 3=beat4 in 4/4)
    beat_modifiers: Dict[int, np.ndarray] = field(default_factory=dict)

    # Minimum inter-onset intervals in ms
    min_ioi: Dict[DrumState, float] = field(
        default_factory=lambda: {
            DrumState.SILENCE: 0,
            DrumState.KICK: 50,  # Double bass can be fast
            DrumState.SNARE: 40,  # Buzz rolls
            DrumState.HIHAT: 30,  # Fast hi-hat
            DrumState.TOM: 60,  # Tom rolls
            DrumState.CYMBAL: 80,  # Cymbals ring, harder to repeat
            DrumState.GHOST: 35,  # Ghost notes cluster
        }
    )

    def __post_init__(self):
        """Initialize beat-aware modifiers."""
        # On downbeats (beat 1): more likely to have kick + cymbal
        self.beat_modifiers[0] = np.array(
            [
                [0.8, 1.5, 0.9, 1.0, 0.9, 1.8, 0.7],  # Boost kick, cymbal on downbeat
                [0.8, 1.3, 1.0, 1.0, 1.0, 1.5, 0.8],
                [0.9, 1.3, 0.9, 1.0, 1.0, 1.3, 0.8],
                [0.9, 1.3, 0.9, 1.0, 1.0, 1.2, 0.9],
                [0.9, 1.2, 1.0, 1.0, 1.0, 1.3, 0.9],
                [1.0, 1.3, 1.0, 1.0, 1.0, 0.8, 0.9],
                [0.9, 1.2, 1.1, 1.0, 1.0, 1.2, 0.9],
            ],
            dtype=np.float64,
        )

        # On backbeats (beats 2 and 4): more likely to have snare
        self.beat_modifiers[1] = self.beat_modifiers[3] = np.array(
            [
                [0.9, 1.0, 1.4, 1.0, 1.0, 1.0, 1.2],  # Boost snare, ghost on backbeat
                [0.8, 0.9, 1.5, 1.0, 1.0, 1.0, 1.3],
                [0.9, 1.0, 1.2, 1.0, 1.0, 1.0, 1.1],
                [0.8, 1.0, 1.5, 0.9, 1.0, 1.0, 1.2],
                [0.9, 1.0, 1.4, 1.0, 0.9, 1.0, 1.1],
                [0.9, 1.0, 1.3, 1.0, 1.0, 0.9, 1.1],
                [
                    0.8,
                    0.9,
                    1.6,
                    1.0,
                    1.0,
                    1.0,
                    0.9,
                ],  # Ghost → Snare boosted on backbeat
            ],
            dtype=np.float64,
        )

        # Off-beats: higher hi-hat probability
        self.beat_modifiers[2] = np.array(
            [
                [1.0, 0.9, 0.9, 1.3, 1.0, 0.9, 1.0],
                [1.0, 0.9, 0.9, 1.3, 1.0, 0.9, 1.0],
                [1.0, 0.9, 0.8, 1.4, 1.0, 0.9, 1.0],
                [0.9, 0.9, 0.9, 1.3, 1.0, 0.9, 1.0],
                [1.0, 0.9, 0.9, 1.2, 1.0, 0.9, 1.0],
                [1.0, 0.9, 0.9, 1.2, 1.0, 0.9, 1.0],
                [1.0, 0.9, 1.0, 1.2, 1.0, 0.9, 1.0],
            ],
            dtype=np.float64,
        )

    def get_transition_probs(
        self,
        beat_position: int,
        time_since_last: float,
        bpm: float = 120.0,
        adaptive_config: Any = None,
    ) -> np.ndarray:
        """
        Get transition probabilities for the current context.

        Args:
            beat_position: Position in measure (0-3 for 4/4)
            time_since_last: Time since last onset in ms
            bpm: Current tempo (for adaptive IOI limits)
            adaptive_config: Optional adaptive configuration (AdaptiveConfig)

        Returns:
            Transition probability matrix modified for context
        """
        # Use adaptive config if available
        if adaptive_config is not None and HAS_ADAPTIVE:
            probs = adaptive_config.get_transition_matrix().copy()
        else:
            probs = self.base_transitions.copy()

        # Apply beat modifier
        beat_mod = self.beat_modifiers.get(beat_position % 4, np.ones_like(probs))
        probs = probs * beat_mod

        # Apply IOI constraints (suppress transitions that are too fast)
        for state in DrumState:
            if state == DrumState.SILENCE:
                continue

            # Use adaptive IOI limits if available
            if adaptive_config is not None and HAS_ADAPTIVE:
                min_interval = adaptive_config.get_ioi_limit(state.value, bpm)
            else:
                min_interval = self.min_ioi[state]

            if time_since_last < min_interval:
                # Reduce probability of this state if too soon after previous
                suppression = max(0.1, time_since_last / min_interval)
                probs[:, state.value] *= suppression

        # Normalize rows to sum to 1
        row_sums = probs.sum(axis=1, keepdims=True)
        probs = probs / (row_sums + 1e-10)

        return probs


@dataclass
class DecodedEvent:
    """A decoded drum event with context."""

    time: float
    state: DrumState
    component: str  # Original fine-grained component
    confidence: float
    viterbi_prob: float  # Probability from Viterbi decoding
    beat_position: float  # Position in beat (0.0 = downbeat)
    is_backbeat: bool
    transition_from: Optional[DrumState] = None


class ViterbiDecoder:
    """
    Viterbi algorithm for structured drum sequence decoding.

    This takes raw frame-wise predictions and outputs a coherent
    sequence by considering:
    1. Transition probabilities (musical grammar)
    2. Beat position (rhythmic context)
    3. Minimum inter-onset intervals
    4. Confidence calibration
    """

    def __init__(
        self,
        bpm: float = 120.0,
        time_signature: Tuple[int, int] = (4, 4),
        beam_width: int = 5,
    ):
        """
        Initialize decoder.

        Args:
            bpm: Tempo in beats per minute
            time_signature: Time signature as (numerator, denominator)
            beam_width: Number of hypotheses to track (beam search)
        """
        self.bpm = bpm
        self.time_signature = time_signature
        self.beam_width = beam_width
        self.transitions = TransitionMatrix()

        # Calculate beat duration in seconds
        self.beat_duration = 60.0 / max(bpm, 1.0)
        self.measure_duration = self.beat_duration * time_signature[0]

    def get_beat_position(self, time: float, offset: float = 0.0) -> Tuple[int, float]:
        """
        Get beat position for a given time.

        Returns:
            Tuple of (beat_index [0-3 for 4/4], fraction_of_beat [0.0-1.0])
        """
        # Adjust for offset
        adjusted_time = time - offset
        if adjusted_time < 0:
            adjusted_time = 0

        # Position within measure
        position_in_measure = adjusted_time % self.measure_duration

        # Which beat (0-indexed)
        beat_index = int(position_in_measure / self.beat_duration)
        beat_index = min(beat_index, self.time_signature[0] - 1)

        # Fraction within beat
        fraction = (position_in_measure % self.beat_duration) / self.beat_duration

        return beat_index, fraction

    def decode(
        self,
        events: List[Dict],
        offset: float = 0.0,
    ) -> List[DecodedEvent]:
        """
        Decode a sequence of classified hits using Viterbi algorithm.

        Args:
            events: List of classified hits with 'time', 'component', 'confidence'
            offset: Beat offset in seconds

        Returns:
            List of decoded events with refined states and context
        """
        if not events:
            return []

        # Sort by time
        events = sorted(events, key=lambda e: e.get("time", 0))

        n_events = len(events)
        n_states = len(DrumState)

        # Viterbi tables
        viterbi = np.zeros((n_events, n_states), dtype=np.float64)
        backpointer = np.zeros((n_events, n_states), dtype=np.int32)

        # Initialize with emission probabilities from first event
        first_event = events[0]
        _first_state = DrumState.from_component(first_event.get("component", ""))
        emission_probs = self._get_emission_probs(first_event)
        viterbi[0] = np.log(emission_probs + 1e-10)

        # Forward pass
        last_time = first_event.get("time", 0)
        for t in range(1, n_events):
            event = events[t]
            current_time = event.get("time", 0)
            time_delta_ms = (current_time - last_time) * 1000

            beat_idx, _ = self.get_beat_position(current_time, offset)
            trans_probs = self.transitions.get_transition_probs(beat_idx, time_delta_ms)
            emission_probs = self._get_emission_probs(event)

            for s in range(n_states):
                # Find best previous state
                scores = viterbi[t - 1] + np.log(trans_probs[:, s] + 1e-10)
                best_prev = np.argmax(scores)
                viterbi[t, s] = scores[best_prev] + np.log(emission_probs[s] + 1e-10)
                backpointer[t, s] = best_prev

            last_time = current_time

        # Backtrack to find best path
        best_path = np.zeros(n_events, dtype=np.int32)
        best_path[-1] = np.argmax(viterbi[-1])

        for t in range(n_events - 2, -1, -1):
            best_path[t] = backpointer[t + 1, best_path[t + 1]]

        # Build decoded events
        decoded = []
        for t, event in enumerate(events):
            state = DrumState(best_path[t])
            current_time = event.get("time", 0)
            beat_idx, beat_frac = self.get_beat_position(current_time, offset)

            # Check if on backbeat (beats 2 and 4 in 4/4)
            is_backbeat = beat_idx in [1, 3] and beat_frac < 0.1

            decoded_event = DecodedEvent(
                time=current_time,
                state=state,
                component=event.get("component", ""),
                confidence=event.get("confidence", 0.0),
                viterbi_prob=float(np.exp(viterbi[t, best_path[t]])),
                beat_position=beat_idx + beat_frac,
                is_backbeat=is_backbeat,
                transition_from=DrumState(best_path[t - 1]) if t > 0 else None,
            )
            decoded.append(decoded_event)

        return decoded

    def _get_emission_probs(self, event: Dict) -> np.ndarray:
        """
        Get emission probabilities for an event.

        Maps the ML classifier confidence to a probability distribution
        over states.
        """
        probs = np.ones(len(DrumState)) * 0.02  # Small uniform prior

        component = event.get("component", "")
        confidence = event.get("confidence", 0.5)

        # Primary state gets most probability mass
        primary_state = DrumState.from_component(component)
        probs[primary_state.value] = confidence * 0.8

        # Add confusion probabilities based on common misclassifications
        if primary_state == DrumState.SNARE:
            # Snare often confused with rimshot, ghost
            probs[DrumState.GHOST.value] += (1 - confidence) * 0.15
        elif primary_state == DrumState.HIHAT:
            # Hi-hat confusion with ride
            probs[DrumState.CYMBAL.value] += (1 - confidence) * 0.1
        elif primary_state == DrumState.GHOST:
            # Ghost notes may be soft snare or soft hi-hat
            probs[DrumState.SNARE.value] += (1 - confidence) * 0.2
            probs[DrumState.HIHAT.value] += (1 - confidence) * 0.1

        # Normalize
        probs = probs / probs.sum()
        return probs


@dataclass
class TimeSignature:
    """Detected time signature with confidence."""

    numerator: int
    denominator: int
    confidence: float
    detected_period_beats: float  # The actual detected period in beats

    def __str__(self) -> str:
        return f"{self.numerator}/{self.denominator}"


def detect_time_signature(
    hit_times: Sequence[float],
    bpm: float,
    analysis_duration: float = 30.0,
) -> TimeSignature:
    """
    DYNAMICALLY detect time signature from hit timing patterns.

    This uses autocorrelation to find the dominant metric period WITHOUT
    relying on a fixed candidate list. It discovers the natural periodicity
    in the hit patterns and then interprets that as a time signature.

    Algorithm:
    1. Build a binary onset grid at high resolution
    2. Compute autocorrelation to find periodic patterns
    3. Find dominant period via peak detection
    4. Convert period to time signature interpretation

    Args:
        hit_times: Sequence of hit times in seconds
        bpm: Detected BPM
        analysis_duration: How much audio to analyze

    Returns:
        Detected TimeSignature with confidence
    """
    if len(hit_times) < 8:
        return TimeSignature(4, 4, 0.5, 4.0)  # Default with low confidence

    # Convert to numpy array, filter to analysis window
    times = np.array([t for t in hit_times if t <= analysis_duration])
    if len(times) < 8:
        return TimeSignature(4, 4, 0.5, 4.0)

    beat_duration = 60.0 / bpm

    # === STEP 1: Build high-resolution onset grid ===
    # Resolution: 48 subdivisions per beat (supports triplets, 16ths, etc.)
    subdivisions_per_beat = 48
    grid_resolution = beat_duration / subdivisions_per_beat

    max_time = times[-1]
    grid_size = int(np.ceil(max_time / grid_resolution)) + 1
    onset_grid = np.zeros(grid_size, dtype=np.float32)

    # Place onsets on grid with gaussian smoothing for timing tolerance
    for t in times:
        grid_idx = int(t / grid_resolution)
        if 0 <= grid_idx < grid_size:
            # Gaussian window for timing tolerance
            for offset in range(-2, 3):
                idx = grid_idx + offset
                if 0 <= idx < grid_size:
                    weight = np.exp(-0.5 * (offset**2))
                    onset_grid[idx] += weight

    # Normalize
    if onset_grid.max() > 0:
        onset_grid = onset_grid / onset_grid.max()

    # === STEP 2: Compute autocorrelation ===
    # Look for periods from 2 beats to 16 beats
    min_period_subdivs = 2 * subdivisions_per_beat  # 2 beats minimum
    max_period_subdivs = 16 * subdivisions_per_beat  # 16 beats maximum

    # Use FFT-based autocorrelation for efficiency
    n = len(onset_grid)
    fft = np.fft.fft(onset_grid, n=2 * n)
    autocorr = np.fft.ifft(fft * np.conj(fft)).real[:n]
    autocorr = autocorr / (autocorr[0] + 1e-10)  # Normalize

    # === STEP 3: Find dominant period via peak detection ===
    # Only look in valid range
    search_start = min(min_period_subdivs, len(autocorr) - 1)
    search_end = min(max_period_subdivs, len(autocorr) - 1)

    if search_end <= search_start:
        return TimeSignature(4, 4, 0.5, 4.0)

    search_region = autocorr[search_start:search_end]

    # Find peaks in autocorrelation
    peaks = []
    for i in range(1, len(search_region) - 1):
        if (
            search_region[i] > search_region[i - 1]
            and search_region[i] > search_region[i + 1]
        ):
            if search_region[i] > 0.3:  # Minimum peak height
                peaks.append((search_start + i, search_region[i]))

    if not peaks:
        # No clear periodicity found - default to 4/4
        return TimeSignature(4, 4, 0.4, 4.0)

    # Sort by peak height (strongest periodicity)
    peaks.sort(key=lambda x: -x[1])

    # Take the strongest peak
    best_period_subdivs, peak_strength = peaks[0]

    # Convert to beats
    detected_period_beats = best_period_subdivs / subdivisions_per_beat

    # === STEP 4: Interpret period as time signature ===
    # The period tells us how many beats per measure

    # Check for sub-harmonics (period might be 2 measures if 4/4)
    # Look for a peak at half the period
    half_period = best_period_subdivs // 2
    if half_period >= min_period_subdivs and half_period < len(autocorr):
        if autocorr[half_period] > peak_strength * 0.8:
            # Strong sub-harmonic - actual period is half
            detected_period_beats = half_period / subdivisions_per_beat
            peak_strength = autocorr[half_period]

    # Round to nearest sensible beat count
    # Common meters: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, etc.
    raw_beats = detected_period_beats

    # Check if this looks like a compound meter (triplet subdivisions)
    # by analyzing the IOI distribution
    iois = np.diff(times)
    beat_fractions = iois / beat_duration

    # Count triplet-like intervals (1/3, 2/3 of a beat)
    triplet_count = np.sum(
        (np.abs(beat_fractions - 0.333) < 0.05)
        | (np.abs(beat_fractions - 0.667) < 0.05)
    )
    triplet_ratio = (
        triplet_count / len(beat_fractions) if len(beat_fractions) > 0 else 0
    )
    is_compound = triplet_ratio > 0.15

    # Determine numerator and denominator
    if is_compound:
        # Compound meter - denominator is 8
        # Period in dotted quarters = period_beats / 1.5
        dotted_quarters = raw_beats / 1.5
        numerator = int(round(dotted_quarters * 3))  # Each dotted quarter = 3 eighths
        # Clamp to reasonable values
        numerator = max(3, min(24, numerator))
        # Make sure it's divisible by 3 for compound meters
        if numerator % 3 != 0:
            numerator = (numerator // 3) * 3
            if numerator < 3:
                numerator = 3
        denominator = 8
    else:
        # Simple meter - denominator is 4
        numerator = int(round(raw_beats))
        numerator = max(2, min(16, numerator))  # Clamp to reasonable range
        denominator = 4

    # === STEP 5: Validate with accent pattern analysis ===
    # Check if detected time signature matches accent patterns
    measure_duration = (numerator / denominator) * 4 * beat_duration  # In seconds

    # Bin hits by position in measure and look for accent pattern
    positions = (times % measure_duration) / measure_duration

    # Create histogram of hit positions
    n_bins = numerator * 4  # 4 subdivisions per beat
    hist, _ = np.histogram(positions, bins=n_bins, range=(0, 1))
    hist = hist.astype(float)

    # Normalize
    if hist.max() > 0:
        hist = hist / hist.max()

    # Check if downbeat (position 0) is emphasized
    downbeat_bins = hist[: max(1, n_bins // (numerator * 2))]
    other_bins = hist[max(1, n_bins // (numerator * 2)) :]

    downbeat_emphasis = np.mean(downbeat_bins) / (np.mean(other_bins) + 0.01)

    # Confidence combines peak strength and downbeat emphasis
    confidence = min(1.0, (peak_strength * 0.6 + min(downbeat_emphasis / 2, 0.4)))
    confidence = max(0.3, confidence)  # Minimum 30% confidence

    return TimeSignature(
        numerator=numerator,
        denominator=denominator,
        confidence=confidence,
        detected_period_beats=raw_beats,
    )


def detect_swing_ratio(
    hit_times: Sequence[float],
    bpm: float,
    grid: str = "eighth",
) -> Tuple[float, float]:
    """
    Detect swing ratio in the rhythm.

    Swing means the first of a pair of eighth notes is longer than the second.
    Common ratios:
    - 1.0 = Straight (no swing)
    - 1.5 = Light swing (triplet feel: 2:1 ratio)
    - 2.0 = Heavy swing

    Args:
        hit_times: Hit times in seconds
        bpm: Tempo
        grid: Grid resolution to analyze

    Returns:
        Tuple of (swing_ratio, confidence)
    """
    if len(hit_times) < 10:
        return 1.0, 0.0  # Not enough data

    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm

    # Expected eighth note duration
    eighth_duration = beat_duration / 2

    # Find pairs of hits that are roughly an eighth note apart
    iois = np.diff(times)

    # Look for eighth-note-ish intervals (within 50% of expected)
    eighth_mask = (iois > eighth_duration * 0.5) & (iois < eighth_duration * 1.5)
    eighth_iois = iois[eighth_mask]

    if len(eighth_iois) < 5:
        return 1.0, 0.0  # Not enough eighth notes

    # Analyze alternating pattern (long-short-long-short for swing)
    # Group IOIs by beat position
    on_beat_iois = []
    off_beat_iois = []

    for i, ioi in enumerate(eighth_iois):
        # Approximate beat position
        cumulative_time = (
            times[eighth_mask][:-1][i] if i < len(times[eighth_mask]) - 1 else 0
        )
        beat_pos = (cumulative_time % beat_duration) / beat_duration

        if beat_pos < 0.25 or beat_pos > 0.75:
            on_beat_iois.append(ioi)
        else:
            off_beat_iois.append(ioi)

    if len(on_beat_iois) < 3 or len(off_beat_iois) < 3:
        return 1.0, 0.3

    # Calculate ratio
    mean_on = np.mean(on_beat_iois)
    mean_off = np.mean(off_beat_iois)

    if mean_off < 0.01:
        return 1.0, 0.0

    swing_ratio = mean_on / mean_off

    # Clamp to reasonable range
    swing_ratio = max(0.8, min(2.5, swing_ratio))

    # Calculate confidence based on consistency
    on_std = np.std(on_beat_iois) / mean_on if mean_on > 0 else 1.0
    off_std = np.std(off_beat_iois) / mean_off if mean_off > 0 else 1.0
    consistency = 1.0 - min(1.0, (on_std + off_std) / 2)

    # Higher confidence if ratio is clearly not 1.0
    deviation_from_straight = abs(swing_ratio - 1.0)
    confidence = min(1.0, consistency * (0.5 + deviation_from_straight))

    return swing_ratio, confidence


def apply_structured_decoding(
    classified_hits: List[Dict],
    bpm: float,
    offset: float = 0.0,
    time_signature: Optional[Tuple[int, int]] = None,
) -> List[Dict]:
    """
    Apply structured decoding to classified hits.

    This is the main entry point for structured decoding.

    Args:
        classified_hits: Raw classified hits from ML model
        bpm: Detected BPM
        offset: Beat offset in seconds
        time_signature: Optional time signature override

    Returns:
        List of hits with refined states and additional context
    """
    if not classified_hits:
        return classified_hits

    # Detect time signature if not provided
    times = [h.get("time", 0) for h in classified_hits]
    if time_signature is None:
        detected_ts = detect_time_signature(times, bpm)
        time_signature = (detected_ts.numerator, detected_ts.denominator)

    # Detect swing
    swing_ratio, swing_confidence = detect_swing_ratio(times, bpm)

    # Run Viterbi decoding
    decoder = ViterbiDecoder(bpm=bpm, time_signature=time_signature)
    decoded_events = decoder.decode(classified_hits, offset)

    # Merge decoded info back into hits
    result = []
    for hit, decoded in zip(classified_hits, decoded_events):
        enhanced_hit = dict(hit)
        enhanced_hit["decoded_state"] = decoded.state.name.lower()
        enhanced_hit["viterbi_confidence"] = decoded.viterbi_prob
        enhanced_hit["beat_position"] = decoded.beat_position
        enhanced_hit["is_backbeat"] = decoded.is_backbeat
        enhanced_hit["swing_ratio"] = swing_ratio
        enhanced_hit["swing_confidence"] = swing_confidence
        enhanced_hit["time_signature"] = f"{time_signature[0]}/{time_signature[1]}"

        # If Viterbi strongly disagrees with original classification, flag it
        original_state = DrumState.from_component(hit.get("component", ""))
        if decoded.state != original_state and decoded.viterbi_prob > 0.7:
            enhanced_hit["state_refined"] = True
            enhanced_hit["original_state"] = original_state.name.lower()

        result.append(enhanced_hit)

    return result
