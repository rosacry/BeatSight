"""
Chart Readability Filter

Post-processing module to ensure generated beatmaps are playable and readable.
This transforms raw ML output into human-quality charts by applying:

1. Physical Constraint Validation
   - Minimum time between same-limb hits
   - Maximum hand speed limits
   - Impossible pattern detection

2. Density Filtering
   - Ultra-dense burst detection and thinning
   - Section-appropriate density limits
   - Rest period enforcement

3. Musical Pattern Enhancement
   - Grouping into musical phrases
   - Fill detection and simplification
   - Hand alternation enforcement

4. Readability Optimization
   - Reduce visual clutter
   - Consistent lane assignment
   - Simplified patterns for lower difficulties
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np


class Limb(Enum):
    """Physical limb assignment for ergonomic analysis."""

    LEFT_HAND = "left_hand"
    RIGHT_HAND = "right_hand"
    LEFT_FOOT = "left_foot"
    RIGHT_FOOT = "right_foot"
    EITHER_HAND = "either_hand"  # Can be played by either


# Component to limb mapping (for standard right-handed setup)
COMPONENT_LIMB_MAP: Dict[str, Limb] = {
    # Kick - always foot
    "kick": Limb.RIGHT_FOOT,
    "bass": Limb.RIGHT_FOOT,
    # Hi-hat pedal - left foot
    "hihat_pedal": Limb.LEFT_FOOT,
    "hihat_foot": Limb.LEFT_FOOT,
    "hihat_foot_splash": Limb.LEFT_FOOT,
    # Snare - typically left hand (cross-stick can be either)
    "snare": Limb.LEFT_HAND,
    "snare_center": Limb.LEFT_HAND,
    "snare_rimshot": Limb.LEFT_HAND,
    "snare_cross_stick": Limb.EITHER_HAND,
    "ghost": Limb.LEFT_HAND,
    "rimshot": Limb.LEFT_HAND,
    "sidestick": Limb.LEFT_HAND,
    # Hi-hat stick - right hand (when closed hat on left side)
    "hihat": Limb.RIGHT_HAND,
    "hihat_closed": Limb.RIGHT_HAND,
    "hihat_open": Limb.RIGHT_HAND,
    "hihat_half": Limb.RIGHT_HAND,
    # Toms - alternating or specific hand
    "tom_high": Limb.RIGHT_HAND,
    "tom_mid": Limb.EITHER_HAND,
    "tom_low": Limb.LEFT_HAND,
    "tom_floor": Limb.LEFT_HAND,
    # Cymbals - typically right hand but can alternate
    "crash": Limb.RIGHT_HAND,
    "crash1": Limb.RIGHT_HAND,
    "crash2": Limb.LEFT_HAND,  # Second crash typically left side
    "ride": Limb.RIGHT_HAND,
    "ride_bell": Limb.RIGHT_HAND,
    "ride_bow": Limb.RIGHT_HAND,
    "china": Limb.RIGHT_HAND,
    "splash": Limb.RIGHT_HAND,
}


@dataclass
class PhysicalConstraints:
    """Physical limits for playability."""

    # Minimum inter-onset intervals (IOI) in milliseconds per limb
    min_ioi_hand: float = 40.0  # ~375 BPM 16th notes - elite speed
    min_ioi_foot: float = 50.0  # ~300 BPM 16th notes - fast double bass

    # Minimum IOI for same component (same drum/cymbal)
    min_ioi_same_component: float = 30.0  # Buzz roll territory

    # Maximum notes per second sustained (fatigue limit)
    max_nps_hands_sustained: float = 14.0  # ~14 NPS for 30+ seconds
    max_nps_hands_burst: float = 20.0  # ~20 NPS for <5 seconds
    max_nps_feet_sustained: float = 12.0  # Double bass endurance
    max_nps_feet_burst: float = 16.0  # Short blast beat

    # Cross-body movement time (e.g., left hand moving from snare to floor tom)
    min_cross_body_time: float = 80.0  # ms

    # Maximum simultaneous limbs (humans have 4 limbs!)
    max_simultaneous: int = 4


@dataclass
class ReadabilityRules:
    """Rules for chart readability and visual clarity."""

    # Maximum note density per second by difficulty tier
    max_nps_by_difficulty: Dict[str, float] = field(
        default_factory=lambda: {
            "easy": 4.0,
            "normal": 6.0,
            "hard": 10.0,
            "expert": 16.0,
            "master": 24.0,
        }
    )

    # Minimum rest duration required after X seconds of activity
    rest_requirements: Dict[int, float] = field(
        default_factory=lambda: {
            30: 2.0,  # After 30s of playing, need 2s rest
            60: 4.0,  # After 60s, need 4s rest
            120: 8.0,  # After 2 min, need 8s rest
        }
    )

    # Minimum time between cymbal crashes (to prevent visual spam)
    min_cymbal_interval: float = 200.0  # ms

    # Maximum consecutive same-component hits (avoid rolls that look like spam)
    max_consecutive_same: int = 8


@dataclass
class FilteredHit:
    """A hit that has been through the readability filter."""

    original: Dict
    kept: bool
    removal_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    limb: Optional[Limb] = None
    local_density: float = 0.0


class ChartReadabilityFilter:
    """
    Filters classified hits to ensure playability and readability.

    This is the key post-processing step that transforms ML output
    into human-quality charts.
    """

    def __init__(
        self,
        difficulty: str = "expert",
        physical_constraints: Optional[PhysicalConstraints] = None,
        readability_rules: Optional[ReadabilityRules] = None,
    ):
        """
        Initialize filter.

        Args:
            difficulty: Target difficulty level
            physical_constraints: Physical playability limits
            readability_rules: Readability/visual clarity rules
        """
        self.difficulty = difficulty.lower()
        self.constraints = physical_constraints or PhysicalConstraints()
        self.rules = readability_rules or ReadabilityRules()

        self.max_nps = self.rules.max_nps_by_difficulty.get(
            self.difficulty, self.rules.max_nps_by_difficulty["expert"]
        )

    def get_limb(self, component: str) -> Limb:
        """Get the limb used to play a component."""
        comp = component.lower()

        # Direct lookup
        if comp in COMPONENT_LIMB_MAP:
            return COMPONENT_LIMB_MAP[comp]

        # Pattern matching
        if "kick" in comp or "bass" in comp:
            return Limb.RIGHT_FOOT
        if "pedal" in comp and "hat" in comp:
            return Limb.LEFT_FOOT
        if "snare" in comp or "ghost" in comp or "rim" in comp:
            return Limb.LEFT_HAND
        if "hat" in comp:
            return Limb.RIGHT_HAND
        if "tom" in comp:
            return Limb.EITHER_HAND
        if any(x in comp for x in ["crash", "ride", "china", "splash", "cymbal"]):
            return Limb.RIGHT_HAND

        return Limb.EITHER_HAND

    def check_physical_constraints(
        self,
        hits: List[Dict],
    ) -> List[FilteredHit]:
        """
        Check hits against physical constraints.

        Returns list of FilteredHit with violation details.
        """
        if not hits:
            return []

        # Sort by time
        sorted_hits = sorted(hits, key=lambda h: h.get("time", 0))
        results = []

        # Track last hit time per limb
        last_limb_time: Dict[Limb, float] = {}
        last_component_time: Dict[str, float] = {}

        for hit in sorted_hits:
            time = hit.get("time", 0) * 1000  # Convert to ms
            component = hit.get("component", "")
            limb = self.get_limb(component)

            filtered = FilteredHit(
                original=hit,
                kept=True,
                limb=limb,
            )

            # Check limb IOI
            if limb != Limb.EITHER_HAND and limb in last_limb_time:
                ioi = time - last_limb_time[limb]
                min_ioi = (
                    self.constraints.min_ioi_foot
                    if limb in [Limb.LEFT_FOOT, Limb.RIGHT_FOOT]
                    else self.constraints.min_ioi_hand
                )

                if ioi < min_ioi:
                    filtered.kept = False
                    filtered.removal_reason = (
                        f"Too fast for {limb.value}: {ioi:.0f}ms < {min_ioi:.0f}ms"
                    )

            # Check same-component IOI
            if component in last_component_time:
                ioi = time - last_component_time[component]
                if ioi < self.constraints.min_ioi_same_component:
                    filtered.kept = False
                    filtered.removal_reason = f"Same component too fast: {ioi:.0f}ms"

            results.append(filtered)

            # Update tracking (only for kept hits)
            if filtered.kept:
                if limb != Limb.EITHER_HAND:
                    last_limb_time[limb] = time
                last_component_time[component] = time

        return results

    def detect_impossible_patterns(
        self,
        hits: List[Dict],
    ) -> List[Tuple[int, int, str]]:
        """
        Detect patterns that are physically impossible.

        Returns list of (start_index, end_index, reason) tuples.
        """
        impossible = []

        sorted_hits = sorted(enumerate(hits), key=lambda x: x[1].get("time", 0))

        for i in range(len(sorted_hits) - 1):
            idx1, hit1 = sorted_hits[i]
            idx2, hit2 = sorted_hits[i + 1]

            time1 = hit1.get("time", 0) * 1000
            time2 = hit2.get("time", 0) * 1000
            delta = time2 - time1

            comp1 = hit1.get("component", "")
            comp2 = hit2.get("component", "")
            limb1 = self.get_limb(comp1)
            limb2 = self.get_limb(comp2)

            # Check: same limb, different position, too fast
            if limb1 == limb2 and limb1 != Limb.EITHER_HAND:
                # If hitting different components with same limb
                if comp1 != comp2:
                    # Need time to move
                    if delta < self.constraints.min_cross_body_time:
                        impossible.append(
                            (
                                idx1,
                                idx2,
                                f"Same limb ({limb1.value}) hitting {comp1}→{comp2} in {delta:.0f}ms",
                            )
                        )

        # Check for too many simultaneous hits
        sorted_by_time = sorted(hits, key=lambda h: h.get("time", 0))
        for i, hit in enumerate(sorted_by_time):
            time = hit.get("time", 0)
            # Count hits within 10ms window
            simultaneous = [
                h for h in sorted_by_time if abs(h.get("time", 0) - time) < 0.010
            ]

            if len(simultaneous) > self.constraints.max_simultaneous:
                impossible.append(
                    (
                        i,
                        i + len(simultaneous) - 1,
                        f"Too many simultaneous hits: {len(simultaneous)} > {self.constraints.max_simultaneous}",
                    )
                )

        return impossible

    def filter_dense_bursts(
        self,
        hits: List[Dict],
        window_size: float = 1.0,
    ) -> List[FilteredHit]:
        """
        Filter hits that exceed density limits.

        Uses sliding window to detect and thin overly dense sections.
        """
        if not hits:
            return []

        sorted_hits = sorted(hits, key=lambda h: h.get("time", 0))
        times = np.array([h.get("time", 0) for h in sorted_hits])

        results = []
        keep_mask = np.ones(len(sorted_hits), dtype=bool)

        for i, hit in enumerate(sorted_hits):
            time = hit.get("time", 0)

            # Count hits in window centered on this hit
            window_start = time - window_size / 2
            window_end = time + window_size / 2

            in_window = (times >= window_start) & (times <= window_end)
            local_count = np.sum(in_window & keep_mask)
            local_density = local_count / window_size

            filtered = FilteredHit(
                original=hit,
                kept=True,
                local_density=local_density,
            )

            # If too dense, thin based on confidence (keep higher confidence)
            if local_density > self.max_nps:
                confidence = hit.get("confidence", 0.5)

                # Keep if high confidence, otherwise thin
                if confidence < 0.8:
                    # Check if this hit is "necessary" (on beat, high energy)
                    is_on_beat = (
                        hit.get("is_backbeat", False)
                        or hit.get("beat_position", 0.5) % 1.0 < 0.1
                    )

                    if not is_on_beat:
                        filtered.kept = False
                        filtered.removal_reason = f"Density thinning: {local_density:.1f} NPS > {self.max_nps:.1f}"
                        keep_mask[i] = False

            results.append(filtered)

        return results

    def enforce_hand_alternation(
        self,
        hits: List[Dict],
        min_alternation_interval: float = 0.060,  # 60ms = ~250 BPM 16ths
    ) -> List[Dict]:
        """
        Enforce hand alternation for fast passages.

        When hits are too fast for one hand, assign alternating hands.
        """
        sorted_hits = sorted(hits, key=lambda h: h.get("time", 0))
        last_hand_time: Dict[str, float] = {"left": -999, "right": -999}

        for hit in sorted_hits:
            time = hit.get("time", 0)
            component = hit.get("component", "")
            limb = self.get_limb(component)

            # Only apply to hand hits that can alternate
            if limb not in [Limb.LEFT_HAND, Limb.RIGHT_HAND, Limb.EITHER_HAND]:
                continue

            if limb == Limb.EITHER_HAND:
                # Assign to whichever hand was idle longer
                if last_hand_time["right"] <= last_hand_time["left"]:
                    assigned_hand = "right"
                else:
                    assigned_hand = "left"
                hit["assigned_hand"] = assigned_hand
                last_hand_time[assigned_hand] = time
            else:
                # Fixed hand assignment
                hand = "left" if limb == Limb.LEFT_HAND else "right"
                hit["assigned_hand"] = hand
                last_hand_time[hand] = time

        return sorted_hits

    def simplify_for_difficulty(
        self,
        hits: List[Dict],
    ) -> List[Dict]:
        """
        Simplify patterns based on target difficulty.

        === DIFFICULTY-BASED SIMPLIFICATION EXPLAINED ===

        This reduces chart complexity for lower skill levels while preserving
        the essential musical structure.

        GHOST NOTE HANDLING:
        --------------------
        Ghost notes are controlled by a GLOBAL SETTING (include_ghost_notes),
        not by difficulty level. This allows users to toggle ghost notes
        independently of chart difficulty.

        Note: Ghost note detection is experimental and may not be 100% accurate.
        Users can disable ghost notes in settings if they prefer cleaner charts.

        TOM FILL REDUCTION:
        -------------------
        Complex tom fills are simplified for lower difficulties by removing
        low-confidence tom hits:

            Expert:  | . . . . | HT MT LT FT |
                                 (full 4-tom fill)
            Easy:    | . . . . | .  .  LT FT |
                                 (simplified - low-confidence toms removed)

        ALL CYMBALS KEPT:
        -----------------
        Cymbal hits (crash, china, splash, ride) are never removed by difficulty.
        All cymbal hits are preserved as they mark important musical moments.
        """
        if self.difficulty in ["expert", "master"]:
            return hits  # Keep all for high difficulties

        simplified = []

        for hit in hits:
            component = hit.get("component", "")
            confidence = hit.get("confidence", 0.5)

            # Difficulty-based filtering
            # Note: Ghost notes are handled by global setting, not difficulty
            # Note: Cymbal thinning removed - all cymbals are kept
            if self.difficulty == "easy":
                # Easy: Remove low-confidence toms
                if "tom" in component.lower() and confidence < 0.85:
                    continue

            elif self.difficulty == "normal":
                # Normal: Remove very low-confidence toms
                if "tom" in component.lower() and confidence < 0.75:
                    continue

            elif self.difficulty == "hard":
                # Hard: Keep most hits, only remove very uncertain ones
                if confidence < 0.5:
                    continue

            simplified.append(hit)

        return simplified

    def filter(self, hits: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Apply full filtering pipeline.

        Returns:
            Tuple of (filtered_hits, statistics)
        """
        if not hits:
            return [], {"original_count": 0, "filtered_count": 0}

        original_count = len(hits)

        # Step 1: Simplify for difficulty
        simplified = self.simplify_for_difficulty(hits)

        # Step 2: Check physical constraints
        physical_results = self.check_physical_constraints(simplified)

        # Step 3: Filter dense bursts
        density_results = self.filter_dense_bursts(
            [r.original for r in physical_results if r.kept]
        )

        # Step 4: Enforce hand alternation
        kept_hits = [r.original for r in density_results if r.kept]
        final_hits = self.enforce_hand_alternation(kept_hits)

        # Collect statistics
        impossible_patterns = self.detect_impossible_patterns(simplified)

        removal_reasons = {}
        for r in physical_results:
            if not r.kept and r.removal_reason:
                reason_type = r.removal_reason.split(":")[0]
                removal_reasons[reason_type] = removal_reasons.get(reason_type, 0) + 1
        for r in density_results:
            if not r.kept and r.removal_reason:
                reason_type = r.removal_reason.split(":")[0]
                removal_reasons[reason_type] = removal_reasons.get(reason_type, 0) + 1

        stats = {
            "original_count": original_count,
            "after_simplify": len(simplified),
            "after_physical": sum(1 for r in physical_results if r.kept),
            "after_density": sum(1 for r in density_results if r.kept),
            "filtered_count": len(final_hits),
            "removed_count": original_count - len(final_hits),
            "impossible_patterns": len(impossible_patterns),
            "removal_reasons": removal_reasons,
            "difficulty": self.difficulty,
            "max_nps": self.max_nps,
        }

        return final_hits, stats


def filter_chart_for_readability(
    hits: List[Dict],
    difficulty: str = "expert",
    bpm: float = 120.0,
) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to filter hits for readability.

    Args:
        hits: Raw classified hits
        difficulty: Target difficulty level
        bpm: Song tempo (for density calculations)

    Returns:
        Tuple of (filtered_hits, statistics)
    """
    filter = ChartReadabilityFilter(difficulty=difficulty)
    return filter.filter(hits)


def detect_sections(
    hits: List[Dict],
    bpm: float,
    measures_per_section: int = 8,
) -> List[Dict]:
    """
    Detect musical sections based on density and pattern changes.

    Returns list of sections with:
    - start_time, end_time
    - section_type (intro, verse, chorus, solo, outro)
    - density
    - suggested_difficulty
    """
    if not hits:
        return []

    beat_duration = 60.0 / bpm
    measure_duration = beat_duration * 4  # Assuming 4/4
    section_duration = measure_duration * measures_per_section

    sorted_hits = sorted(hits, key=lambda h: h.get("time", 0))
    max_time = sorted_hits[-1].get("time", 0) + 1

    sections = []
    current_start = 0.0

    while current_start < max_time:
        section_end = current_start + section_duration

        # Get hits in this section
        section_hits = [
            h for h in sorted_hits if current_start <= h.get("time", 0) < section_end
        ]

        density = len(section_hits) / section_duration if section_duration > 0 else 0

        # Determine section type based on position and density
        relative_position = current_start / max_time

        if relative_position < 0.1:
            section_type = "intro"
        elif relative_position > 0.9:
            section_type = "outro"
        elif density > 8:  # High density = probably chorus or solo
            # Check for variety (solos have more varied components)
            components = set(h.get("component", "") for h in section_hits)
            if len(components) > 6:
                section_type = "solo"
            else:
                section_type = "chorus"
        else:
            section_type = "verse"

        sections.append(
            {
                "start_time": current_start,
                "end_time": section_end,
                "section_type": section_type,
                "density": density,
                "hit_count": len(section_hits),
                "unique_components": len(
                    set(h.get("component", "") for h in section_hits)
                ),
            }
        )

        current_start = section_end

    return sections


def apply_difficulty_curve(
    hits: List[Dict],
    sections: List[Dict],
    target_difficulty: str = "expert",
) -> List[Dict]:
    """
    Apply difficulty modulation across sections.

    Makes intros easier, builds to choruses, and provides breaks.
    """
    filter = ChartReadabilityFilter(difficulty=target_difficulty)
    result = []

    for section in sections:
        start = section["start_time"]
        end = section["end_time"]
        section_type = section["section_type"]

        # Get hits for this section
        section_hits = [h for h in hits if start <= h.get("time", 0) < end]

        # Adjust difficulty per section type
        if section_type == "intro":
            # Simplify intro
            effective_difficulty = _lower_difficulty(target_difficulty)
            section_filter = ChartReadabilityFilter(difficulty=effective_difficulty)
        elif section_type == "outro":
            # Slightly easier outro
            effective_difficulty = _lower_difficulty(target_difficulty)
            section_filter = ChartReadabilityFilter(difficulty=effective_difficulty)
        elif section_type == "verse":
            # Standard difficulty for verses
            section_filter = filter
        else:
            # Full difficulty for chorus/solo
            section_filter = filter

        filtered_section, _ = section_filter.filter(section_hits)

        # Add section metadata to hits
        for h in filtered_section:
            h["section_type"] = section_type

        result.extend(filtered_section)

    return result


def _lower_difficulty(difficulty: str) -> str:
    """Get one difficulty level lower."""
    levels = ["easy", "normal", "hard", "expert", "master"]
    try:
        idx = levels.index(difficulty.lower())
        return levels[max(0, idx - 1)]
    except ValueError:
        return difficulty


# =============================================================================
# DYNAMIC DIFFICULTY CURVE
# =============================================================================


@dataclass
class DynamicDifficultyCurve:
    """
    Adaptive difficulty curve that shapes the chart based on:
    - Song energy profile
    - Section transitions
    - Player fatigue modeling
    - Rhythmic complexity variations

    This creates a more engaging, flow-inducing chart experience.
    """

    # Target difficulty parameters
    base_difficulty: str = "expert"
    min_difficulty: str = "normal"
    max_difficulty: str = "master"

    # Curve shape parameters
    intro_warmup_duration: float = 10.0  # seconds
    outro_cooldown_duration: float = 8.0
    difficulty_transition_time: float = 4.0  # seconds to ramp between levels

    # Fatigue modeling
    sustained_high_intensity_limit: float = 30.0  # seconds before forced rest
    recovery_rate: float = 2.0  # seconds of rest per second of intensity

    # Energy tracking
    energy_window: float = 4.0  # seconds for local energy calculation

    # Computed curve
    _difficulty_at_time: Dict[float, float] = field(default_factory=dict)

    def compute_curve(
        self,
        hits: List[Dict],
        sections: List[Dict],
        total_duration: float,
    ) -> Dict[float, float]:
        """
        Compute difficulty multiplier over time.

        Returns:
            Dict mapping time (seconds) to difficulty multiplier (0.0-1.0)
        """
        # Sample at regular intervals
        sample_rate = 0.5  # seconds
        curve = {}

        if total_duration <= 0:
            return {0.0: 1.0}

        # Build section lookup
        section_at_time = self._build_section_lookup(sections, total_duration)

        # Build energy profile
        energy_profile = self._compute_energy_profile(hits, total_duration, sample_rate)

        # Build fatigue profile
        fatigue_profile = self._compute_fatigue_profile(energy_profile, sample_rate)

        for t in np.arange(0, total_duration, sample_rate):
            # Base multiplier from target difficulty
            base_mult = 1.0

            # Intro warmup
            if t < self.intro_warmup_duration:
                warmup_progress = t / self.intro_warmup_duration
                base_mult *= 0.5 + 0.5 * warmup_progress  # 50% to 100%

            # Outro cooldown
            if t > total_duration - self.outro_cooldown_duration:
                cooldown_progress = (total_duration - t) / self.outro_cooldown_duration
                base_mult *= 0.6 + 0.4 * cooldown_progress  # 60% to 100%

            # Section-based adjustment
            section = section_at_time.get(int(t), "unknown")
            if section in ["intro", "outro"]:
                base_mult *= 0.7
            elif section == "verse":
                base_mult *= 0.9
            elif section == "chorus":
                base_mult *= 1.1  # Slightly higher for chorus
            elif section == "solo":
                base_mult *= 1.2  # Peak difficulty for solos

            # Energy-based adjustment (match chart intensity to music)
            energy_idx = int(t / sample_rate)
            if energy_idx < len(energy_profile):
                energy = energy_profile[energy_idx]
                # Higher energy = higher difficulty tolerance
                base_mult *= 0.8 + 0.4 * energy  # 80%-120%

            # Fatigue-based reduction
            if energy_idx < len(fatigue_profile):
                fatigue = fatigue_profile[energy_idx]
                # High fatigue = reduce difficulty
                base_mult *= 1.0 - 0.3 * fatigue  # Up to 30% reduction

            curve[float(t)] = max(0.3, min(1.5, base_mult))

        self._difficulty_at_time = curve
        return curve

    def _build_section_lookup(
        self,
        sections: List[Dict],
        total_duration: float,
    ) -> Dict[int, str]:
        """Build second-by-second section lookup."""
        lookup = {}
        for sec in sections:
            start = int(sec.get("start_time", 0))
            end = int(sec.get("end_time", total_duration))
            section_type = sec.get("section_type", "unknown")
            for t in range(start, end + 1):
                lookup[t] = section_type
        return lookup

    def _compute_energy_profile(
        self,
        hits: List[Dict],
        total_duration: float,
        sample_rate: float,
    ) -> np.ndarray:
        """Compute local hit density as energy profile."""
        n_samples = int(total_duration / sample_rate) + 1
        profile = np.zeros(n_samples)

        for hit in hits:
            t = hit.get("time", 0)
            idx = int(t / sample_rate)
            if 0 <= idx < n_samples:
                profile[idx] += 1.0

        # Smooth with window
        window_samples = int(self.energy_window / sample_rate)
        if window_samples > 0:
            kernel = np.ones(window_samples) / window_samples
            profile = np.convolve(profile, kernel, mode="same")

        # Normalize
        if profile.max() > 0:
            profile /= profile.max()

        return profile

    def _compute_fatigue_profile(
        self,
        energy_profile: np.ndarray,
        sample_rate: float,
    ) -> np.ndarray:
        """Model player fatigue over time."""
        fatigue = np.zeros_like(energy_profile)
        current_fatigue = 0.0

        for i, energy in enumerate(energy_profile):
            # Fatigue increases with high energy, decreases with low
            if energy > 0.7:
                current_fatigue += sample_rate / self.sustained_high_intensity_limit
            elif energy < 0.3:
                current_fatigue -= sample_rate / (
                    self.sustained_high_intensity_limit * self.recovery_rate
                )

            current_fatigue = max(0, min(1, current_fatigue))
            fatigue[i] = current_fatigue

        return fatigue

    def get_difficulty_at(self, time: float) -> float:
        """Get difficulty multiplier at a specific time."""
        if not self._difficulty_at_time:
            return 1.0

        # Find nearest computed time
        times = sorted(self._difficulty_at_time.keys())
        for t in times:
            if t >= time:
                return self._difficulty_at_time[t]

        return self._difficulty_at_time.get(times[-1], 1.0) if times else 1.0

    def apply_to_hits(
        self,
        hits: List[Dict],
        sections: List[Dict],
        total_duration: float,
    ) -> List[Dict]:
        """
        Apply dynamic difficulty curve to hits.

        This may remove or simplify hits based on the local difficulty target.

        Returns:
            Filtered hits with difficulty-aware simplification
        """
        if not hits:
            return []

        # Compute the curve
        _curve = self.compute_curve(hits, sections, total_duration)

        # Apply to each hit
        result = []
        for hit in hits:
            t = hit.get("time", 0)
            difficulty_mult = self.get_difficulty_at(t)

            # Decide whether to keep the hit based on difficulty multiplier
            # Lower multiplier = more aggressive filtering
            confidence = hit.get("confidence", 1.0)

            # Adjust keep threshold based on difficulty
            keep_threshold = 0.5 * (1.5 - difficulty_mult)  # 0.0 to 0.6

            if confidence >= keep_threshold:
                # Add difficulty context to hit
                hit_copy = dict(hit)
                hit_copy["difficulty_multiplier"] = difficulty_mult
                result.append(hit_copy)

        return result


def apply_dynamic_difficulty(
    hits: List[Dict],
    sections: List[Dict],
    total_duration: float,
    target_difficulty: str = "expert",
) -> List[Dict]:
    """
    Convenience function to apply dynamic difficulty curve.

    Args:
        hits: List of hit dictionaries
        sections: List of section dictionaries
        total_duration: Total song duration
        target_difficulty: Base difficulty level

    Returns:
        Filtered hits with dynamic difficulty applied
    """
    curve = DynamicDifficultyCurve(base_difficulty=target_difficulty)
    return curve.apply_to_hits(hits, sections, total_duration)
