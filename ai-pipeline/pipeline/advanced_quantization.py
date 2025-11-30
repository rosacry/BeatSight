"""
Advanced Quantization Module for Intelligent Subdivision Detection

This module extends the basic quantization system with:
1. DYNAMIC tuplet detection (any N-tuplet: 3, 5, 7, 9, 11, etc.)
2. Mixed subdivision support (different sections use different grids)
3. Swing-aware quantization that preserves groove
4. Micro-timing analysis for humanization preservation
5. Polyrhythm detection (e.g., 3 over 4, 5 over 4)
6. Metric modulation detection
7. Dynamic time signature changes

The key innovation is that instead of forcing all hits to a single grid,
this module:
- Analyzes the ACTUAL subdivision patterns in the music
- Detects ANY tuplet dynamically (not just predefined ones)
- Chooses per-section grids based on what fits best
- Preserves intentional micro-timing (groove) while fixing errors
- Handles complex progressive/jazz rhythms

This is what separates AI-generated charts from human-quality ones:
a human charter LISTENS and adapts their grid choice per section.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence, Set, Callable
from enum import Enum
import numpy as np


class SubdivisionType(Enum):
    """Types of rhythmic subdivisions."""
    STRAIGHT = "straight"       # Binary: 1/4, 1/8, 1/16, 1/32
    TRIPLET = "triplet"         # Ternary: 1/4T, 1/8T, 1/16T
    TUPLET = "tuplet"           # Any N-tuplet (5, 7, 9, 11, etc.)
    SWING = "swing"             # Shuffle/swing feel
    MIXED = "mixed"             # Multiple subdivisions present
    IRRATIONAL = "irrational"   # Non-standard divisions (e.g., 7 in the space of 4)


@dataclass
class SubdivisionGrid:
    """A quantization grid with subdivision info."""
    name: str
    divisor: int                    # Divisions per beat
    step_ratio: float               # Fraction of a beat
    subdivision_type: SubdivisionType
    swing_ratio: float = 1.0        # 1.0 = straight, 1.5 = shuffle
    tuplet_n: int = 0               # For tuplets: the N in N-tuplet
    tuplet_in_space_of: int = 0     # For tuplets: N notes in space of M
    
    def step_duration(self, beat_duration: float) -> float:
        """Get step duration in seconds."""
        return beat_duration * self.step_ratio
    
    @classmethod
    def create_tuplet(cls, n: int, in_space_of: int = 0, level: str = "quarter") -> 'SubdivisionGrid':
        """
        Dynamically create any N-tuplet grid.
        
        Args:
            n: Number of notes in the tuplet (e.g., 5 for quintuplet)
            in_space_of: How many regular notes it replaces (default: next lower power of 2)
                         e.g., 5 in space of 4, 7 in space of 4 or 8
            level: Base note level ("quarter", "eighth", "sixteenth")
            
        Returns:
            SubdivisionGrid for the specified tuplet
        """
        if in_space_of == 0:
            # Default: tuplet fills the space of the nearest power of 2
            # 3 → 2, 5 → 4, 6 → 4, 7 → 4 or 8, 9 → 8, etc.
            if n <= 2:
                in_space_of = 2
            elif n <= 4:
                in_space_of = 2 if n == 3 else 4
            elif n <= 8:
                in_space_of = 4
            else:
                in_space_of = 8
        
        # Calculate step ratio
        # For "N in the space of M", each note is M/N of the base duration
        level_multiplier = {"quarter": 1, "eighth": 2, "sixteenth": 4, "thirtysecond": 8}
        base_mult = level_multiplier.get(level, 1)
        
        step_ratio = in_space_of / (n * base_mult)
        divisor = n * base_mult // in_space_of
        
        # Generate name
        tuplet_names = {3: "triplet", 5: "quintuplet", 6: "sextuplet", 7: "septuplet",
                        9: "nonuplet", 10: "decuplet", 11: "undecuplet", 12: "dodecuplet"}
        base_name = tuplet_names.get(n, f"{n}-tuplet")
        name = f"{level}_{base_name}"
        
        sub_type = SubdivisionType.TRIPLET if n == 3 else SubdivisionType.TUPLET
        
        return cls(
            name=name,
            divisor=divisor,
            step_ratio=step_ratio,
            subdivision_type=sub_type,
            tuplet_n=n,
            tuplet_in_space_of=in_space_of,
        )
    
    @classmethod
    def create_swing(cls, swing_ratio: float, level: str = "eighth") -> 'SubdivisionGrid':
        """
        Create a swing grid with any ratio.
        
        Args:
            swing_ratio: The long:short ratio (1.0=straight, 1.5=triplet feel, 2.0=heavy)
            level: Base level ("eighth" or "sixteenth")
        """
        divisor = 2 if level == "eighth" else 4
        step_ratio = 1.0 / divisor
        
        # Categorize swing intensity
        if swing_ratio < 1.2:
            intensity = "straight"
        elif swing_ratio < 1.4:
            intensity = "light"
        elif swing_ratio < 1.6:
            intensity = "medium"
        elif swing_ratio < 1.8:
            intensity = "heavy"
        else:
            intensity = "extreme"
        
        return cls(
            name=f"{level}_swing_{intensity}",
            divisor=divisor,
            step_ratio=step_ratio,
            subdivision_type=SubdivisionType.SWING,
            swing_ratio=swing_ratio,
        )


def generate_all_grids(
    max_tuplet: int = 13,
    include_compound_tuplets: bool = True,
    swing_ratios: Sequence[float] = (1.33, 1.5, 1.67, 2.0),
) -> Dict[str, SubdivisionGrid]:
    """
    Dynamically generate all subdivision grids up to max_tuplet.
    
    This allows the system to detect ANY tuplet, not just predefined ones.
    
    Args:
        max_tuplet: Maximum tuplet to generate (e.g., 13 for 13-tuplets)
        include_compound_tuplets: Include eighth and sixteenth level tuplets
        swing_ratios: Swing ratios to generate grids for
        
    Returns:
        Dict of grid_name → SubdivisionGrid
    """
    grids: Dict[str, SubdivisionGrid] = {}
    
    # Straight subdivisions
    grids["quarter"] = SubdivisionGrid("quarter", 1, 1.0, SubdivisionType.STRAIGHT)
    grids["eighth"] = SubdivisionGrid("eighth", 2, 0.5, SubdivisionType.STRAIGHT)
    grids["sixteenth"] = SubdivisionGrid("sixteenth", 4, 0.25, SubdivisionType.STRAIGHT)
    grids["thirtysecond"] = SubdivisionGrid("thirtysecond", 8, 0.125, SubdivisionType.STRAIGHT)
    grids["sixtyfourth"] = SubdivisionGrid("sixtyfourth", 16, 0.0625, SubdivisionType.STRAIGHT)
    
    # Generate all tuplets dynamically
    for n in range(3, max_tuplet + 1):
        # Quarter-level tuplet
        grids[f"quarter_{n}tuplet"] = SubdivisionGrid.create_tuplet(n, level="quarter")
        
        if include_compound_tuplets:
            # Eighth-level tuplet
            grids[f"eighth_{n}tuplet"] = SubdivisionGrid.create_tuplet(n, level="eighth")
            
            # Sixteenth-level (for very fast passages)
            if n <= 7:  # Don't go too crazy
                grids[f"sixteenth_{n}tuplet"] = SubdivisionGrid.create_tuplet(n, level="sixteenth")
    
    # Swing grids
    for ratio in swing_ratios:
        grids[f"eighth_swing_{ratio:.2f}"] = SubdivisionGrid.create_swing(ratio, "eighth")
        grids[f"sixteenth_swing_{ratio:.2f}"] = SubdivisionGrid.create_swing(ratio, "sixteenth")
    
    return grids


# Default grid set - can be regenerated dynamically
SUBDIVISION_GRIDS = generate_all_grids(max_tuplet=13)


@dataclass
class QuantizationResult:
    """Result of smart quantization analysis."""
    primary_grid: SubdivisionGrid
    quantized_times: np.ndarray
    errors: np.ndarray
    coverage: float                     # % of hits within tolerance
    mean_error: float
    median_error: float
    offset: float
    
    # Advanced analysis
    detected_subdivisions: Dict[str, float]  # Grid name → confidence
    swing_detected: bool
    swing_ratio: float
    tuplet_detected: bool
    tuplet_type: Optional[str]
    
    # Per-section analysis (if available)
    section_grids: Optional[List[Dict]] = None
    
    # Groove preservation
    micro_timing_preserved: bool = False
    groove_signature: Optional[np.ndarray] = None
    
    # Dynamic tuplet detection (any N-tuplet)
    dynamic_tuplet_n: Optional[int] = None          # The N in "N in the space of M"
    dynamic_tuplet_base: Optional[int] = None       # The M (space of)
    dynamic_tuplet_confidence: float = 0.0
    
    # Polyrhythm detection
    is_polyrhythmic: bool = False
    polyrhythm_grids: Optional[List[str]] = None
    
    # Time signature analysis
    detected_time_signature: Optional[Tuple[int, int]] = None
    is_additive_meter: bool = False
    beat_grouping: Optional[List[int]] = None  # e.g., [3, 3, 2] for 8/8


@dataclass
class SubdivisionAnalysis:
    """Analysis of subdivision patterns in a time sequence."""
    grid_scores: Dict[str, float]       # Grid name → fit score
    best_grid: str
    confidence: float
    is_polyrhythmic: bool               # Multiple grids present
    secondary_grid: Optional[str]       # If polyrhythmic
    residual_analysis: Dict             # What doesn't fit any grid


def analyze_subdivisions(
    hit_times: Sequence[float],
    bpm: float,
    tolerance_ms: float = 15.0,
    analysis_window: float = 8.0,  # beats
) -> SubdivisionAnalysis:
    """
    Analyze hit times to detect which subdivision grid(s) are being used.
    
    This is more sophisticated than just checking "does 1/16 fit":
    - Tests ALL supported grids
    - Detects polyrhythms (e.g., 3 over 4)
    - Identifies section-specific subdivisions
    - Handles swing detection
    
    Args:
        hit_times: Sequence of hit times in seconds
        bpm: Tempo in BPM
        tolerance_ms: Tolerance for "on grid" detection
        analysis_window: Window size in beats for analysis
        
    Returns:
        SubdivisionAnalysis with grid scores and recommendations
    """
    if len(hit_times) < 4:
        return SubdivisionAnalysis(
            grid_scores={"sixteenth": 1.0},
            best_grid="sixteenth",
            confidence=0.5,
            is_polyrhythmic=False,
            secondary_grid=None,
            residual_analysis={},
        )
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    tolerance = tolerance_ms / 1000.0
    
    # Test each grid
    grid_scores: Dict[str, float] = {}
    
    for grid_name, grid in SUBDIVISION_GRIDS.items():
        step = grid.step_duration(beat_duration)
        
        # Handle swing grids specially
        if grid.subdivision_type == SubdivisionType.SWING:
            score = _score_swing_grid(times, beat_duration, grid, tolerance)
        else:
            score = _score_straight_grid(times, step, tolerance)
        
        grid_scores[grid_name] = score
    
    # Find best grid
    sorted_grids = sorted(grid_scores.items(), key=lambda x: -x[1])
    best_grid = sorted_grids[0][0]
    best_score = sorted_grids[0][1]
    
    # Check for polyrhythm (two grids both score well)
    secondary_grid = None
    is_polyrhythmic = False
    
    if len(sorted_grids) >= 2:
        second_score = sorted_grids[1][1]
        # If second grid also fits well (>70% of best) and is different type
        if second_score > 0.7 * best_score:
            second_type = SUBDIVISION_GRIDS[sorted_grids[1][0]].subdivision_type
            first_type = SUBDIVISION_GRIDS[best_grid].subdivision_type
            if second_type != first_type:
                is_polyrhythmic = True
                secondary_grid = sorted_grids[1][0]
    
    # Analyze residuals (hits that don't fit any grid well)
    residual_analysis = _analyze_residuals(times, beat_duration, best_grid, tolerance)
    
    return SubdivisionAnalysis(
        grid_scores=grid_scores,
        best_grid=best_grid,
        confidence=best_score,
        is_polyrhythmic=is_polyrhythmic,
        secondary_grid=secondary_grid,
        residual_analysis=residual_analysis,
    )


def _score_straight_grid(
    times: np.ndarray,
    step: float,
    tolerance: float,
) -> float:
    """Score how well times fit a straight (non-swing) grid."""
    if step <= 0 or len(times) == 0:
        return 0.0
    
    # Find optimal offset
    remainders = np.mod(times, step)
    
    # Use circular statistics for offset (handle wrap-around)
    angles = 2 * np.pi * remainders / step
    mean_sin = np.mean(np.sin(angles))
    mean_cos = np.mean(np.cos(angles))
    offset = (np.arctan2(mean_sin, mean_cos) / (2 * np.pi)) * step
    if offset < 0:
        offset += step
    
    # Measure fit with optimal offset
    snapped = offset + np.round((times - offset) / step) * step
    errors = np.abs(snapped - times)
    
    within_tolerance = np.sum(errors <= tolerance)
    coverage = within_tolerance / len(times)
    
    # Penalize very fine grids slightly (prefer simpler grids if fit is similar)
    complexity_penalty = max(0, (1.0 / step - 8) * 0.01)  # Penalize > 8 per beat
    
    return max(0.0, coverage - complexity_penalty)


def _score_swing_grid(
    times: np.ndarray,
    beat_duration: float,
    grid: SubdivisionGrid,
    tolerance: float,
) -> float:
    """Score how well times fit a swing grid."""
    if len(times) < 4:
        return 0.0
    
    swing_ratio = grid.swing_ratio
    
    # In swing, the first of each pair is longer
    # For ratio 1.5 (triplet feel): long=2/3, short=1/3
    # The grid positions within a beat are [0, long/(long+short)]
    long_frac = swing_ratio / (swing_ratio + 1)
    
    # Expected positions within each beat
    swing_positions = np.array([0.0, long_frac])
    
    # Check each hit's position within beat
    beat_positions = np.mod(times / beat_duration, 1.0)
    
    # Find closest swing position for each hit
    min_distances = []
    for pos in beat_positions:
        distances = np.abs(swing_positions - pos)
        # Handle wrap-around
        distances = np.minimum(distances, 1.0 - distances)
        min_distances.append(np.min(distances))
    
    min_distances = np.array(min_distances)
    tol_fraction = tolerance / beat_duration
    
    within_tolerance = np.sum(min_distances <= tol_fraction)
    coverage = within_tolerance / len(times)
    
    return coverage


def _analyze_residuals(
    times: np.ndarray,
    beat_duration: float,
    best_grid: str,
    tolerance: float,
) -> Dict:
    """Analyze hits that don't fit the best grid."""
    grid = SUBDIVISION_GRIDS[best_grid]
    step = grid.step_duration(beat_duration)
    
    # Find residual hits
    remainders = np.mod(times, step)
    offset = np.median(remainders)
    snapped = offset + np.round((times - offset) / step) * step
    errors = np.abs(snapped - times)
    
    residual_mask = errors > tolerance
    residual_times = times[residual_mask]
    residual_count = len(residual_times)
    
    return {
        "count": residual_count,
        "fraction": residual_count / len(times) if len(times) > 0 else 0,
        "times": residual_times.tolist() if residual_count < 20 else [],
    }


def smart_quantize(
    hit_times: Sequence[float],
    bpm: float,
    tolerance_ms: float = 12.0,
    prefer_simple: bool = True,
    detect_per_section: bool = True,
    section_duration_beats: int = 16,
    preserve_groove: bool = True,
    groove_threshold_ms: float = 8.0,
) -> QuantizationResult:
    """
    Intelligently quantize hit times with automatic subdivision detection.
    
    This is the "smart" quantization that:
    1. Detects the actual subdivision being used (straight/triplet/tuplet/swing)
    2. Optionally uses different grids per section
    3. Preserves intentional micro-timing (groove) while fixing errors
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        tolerance_ms: Tolerance for grid snapping
        prefer_simple: Prefer simpler grids when scores are similar
        detect_per_section: Analyze each section separately
        section_duration_beats: Section length for per-section analysis
        preserve_groove: Keep intentional micro-timing
        groove_threshold_ms: Threshold for what counts as "groove" vs "error"
        
    Returns:
        QuantizationResult with quantized times and analysis
    """
    if len(hit_times) == 0:
        return QuantizationResult(
            primary_grid=SUBDIVISION_GRIDS["sixteenth"],
            quantized_times=np.array([]),
            errors=np.array([]),
            coverage=1.0,
            mean_error=0.0,
            median_error=0.0,
            offset=0.0,
            detected_subdivisions={},
            swing_detected=False,
            swing_ratio=1.0,
            tuplet_detected=False,
            tuplet_type=None,
            dynamic_tuplet_n=None,
            dynamic_tuplet_base=None,
            dynamic_tuplet_confidence=0.0,
            is_polyrhythmic=False,
            polyrhythm_grids=None,
            detected_time_signature=None,
            is_additive_meter=False,
            beat_grouping=None,
        )
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    tolerance = tolerance_ms / 1000.0
    groove_tolerance = groove_threshold_ms / 1000.0
    
    # Analyze subdivisions
    analysis = analyze_subdivisions(times, bpm, tolerance_ms)
    
    # Get primary grid
    primary_grid = SUBDIVISION_GRIDS[analysis.best_grid]
    
    # Detect swing and tuplets
    swing_detected = primary_grid.subdivision_type == SubdivisionType.SWING
    tuplet_detected = primary_grid.subdivision_type in [
        SubdivisionType.TRIPLET,
        SubdivisionType.QUINTUPLET,
        SubdivisionType.SEPTUPLET,
    ]
    tuplet_type = primary_grid.subdivision_type.value if tuplet_detected else None
    
    # Dynamic tuplet detection - discovers ANY N-tuplet ratio
    dynamic_tuplet = discover_tuplet_ratio(list(hit_times), bpm)
    dynamic_n, dynamic_base, dynamic_conf = dynamic_tuplet
    
    # If dynamic detection found a significant tuplet we didn't catch
    if dynamic_conf > 0.6 and not tuplet_detected:
        tuplet_detected = True
        tuplet_type = f"{dynamic_n}:{dynamic_base}"
    
    # Polyrhythm detection
    polyrhythm = detect_polyrhythm(list(hit_times), bpm)
    is_polyrhythmic = polyrhythm.is_polyrhythmic
    polyrhythm_grids = polyrhythm.active_grids if is_polyrhythmic else None
    
    # Time signature detection
    time_sig = detect_dynamic_time_signature(list(hit_times), bpm)
    detected_time_sig = (time_sig.numerator, time_sig.denominator)
    is_additive = time_sig.is_additive
    beat_grouping = time_sig.grouping if is_additive else None
    
    # Calculate swing ratio from best swing grid (if applicable)
    swing_ratio = 1.0
    for name, score in analysis.grid_scores.items():
        if "swing" in name and score > 0.7:
            swing_ratio = SUBDIVISION_GRIDS[name].swing_ratio
            swing_detected = True
            break
    
    # Also try dynamic swing detection
    if not swing_detected:
        detected_swing, swing_conf = detect_arbitrary_swing_ratio(list(hit_times), bpm)
        if swing_conf > 0.5 and abs(detected_swing - 1.0) > 0.15:
            swing_detected = True
            swing_ratio = detected_swing
    
    # Per-section analysis
    section_grids = None
    if detect_per_section:
        section_grids = _analyze_sections(
            times, bpm, section_duration_beats, tolerance_ms
        )
    
    # Quantize using best grid
    quantized, errors, offset = _quantize_with_grid(
        times, beat_duration, primary_grid, tolerance
    )
    
    # Groove preservation: keep small deviations that are consistent
    groove_signature = None
    if preserve_groove:
        quantized, groove_signature = _preserve_groove(
            times, quantized, beat_duration, groove_tolerance
        )
        errors = quantized - times
    
    # Calculate statistics
    abs_errors = np.abs(errors)
    within_tolerance = np.sum(abs_errors <= tolerance)
    coverage = within_tolerance / len(times)
    mean_error = float(np.mean(abs_errors))
    median_error = float(np.median(abs_errors))
    
    return QuantizationResult(
        primary_grid=primary_grid,
        quantized_times=quantized,
        errors=errors,
        coverage=coverage,
        mean_error=mean_error,
        median_error=median_error,
        offset=offset,
        detected_subdivisions=analysis.grid_scores,
        swing_detected=swing_detected,
        swing_ratio=swing_ratio,
        tuplet_detected=tuplet_detected,
        tuplet_type=tuplet_type,
        section_grids=section_grids,
        micro_timing_preserved=preserve_groove,
        groove_signature=groove_signature,
        dynamic_tuplet_n=dynamic_n if dynamic_conf > 0.3 else None,
        dynamic_tuplet_base=dynamic_base if dynamic_conf > 0.3 else None,
        dynamic_tuplet_confidence=dynamic_conf,
        is_polyrhythmic=is_polyrhythmic,
        polyrhythm_grids=polyrhythm_grids,
        detected_time_signature=detected_time_sig,
        is_additive_meter=is_additive,
        beat_grouping=beat_grouping,
    )


def _quantize_with_grid(
    times: np.ndarray,
    beat_duration: float,
    grid: SubdivisionGrid,
    tolerance: float,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Quantize times using a specific grid."""
    step = grid.step_duration(beat_duration)
    
    if grid.subdivision_type == SubdivisionType.SWING:
        return _quantize_swing(times, beat_duration, grid)
    
    # Find optimal offset using circular mean
    remainders = np.mod(times, step)
    angles = 2 * np.pi * remainders / step
    mean_sin = np.mean(np.sin(angles))
    mean_cos = np.mean(np.cos(angles))
    offset = (np.arctan2(mean_sin, mean_cos) / (2 * np.pi)) * step
    if offset < 0:
        offset += step
    
    # Snap to grid
    quantized = offset + np.round((times - offset) / step) * step
    errors = quantized - times
    
    return quantized, errors, offset


def _quantize_swing(
    times: np.ndarray,
    beat_duration: float,
    grid: SubdivisionGrid,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Quantize to a swing grid."""
    swing_ratio = grid.swing_ratio
    long_frac = swing_ratio / (swing_ratio + 1)
    
    # Grid positions within each beat
    swing_positions = np.array([0.0, long_frac])
    
    # Find which beat each hit is in
    beat_indices = np.floor(times / beat_duration).astype(int)
    beat_positions = np.mod(times / beat_duration, 1.0)
    
    # Snap to nearest swing position
    quantized = np.zeros_like(times)
    for i, (beat_idx, pos) in enumerate(zip(beat_indices, beat_positions)):
        distances = np.abs(swing_positions - pos)
        # Handle wrap-around
        wrap_distances = 1.0 - distances
        all_distances = np.minimum(distances, wrap_distances)
        
        closest_idx = np.argmin(all_distances)
        
        # Handle wrap-around snapping
        if wrap_distances[closest_idx] < distances[closest_idx]:
            # Wrapped to previous/next beat
            if swing_positions[closest_idx] < pos:
                quantized[i] = (beat_idx + 1) * beat_duration
            else:
                quantized[i] = beat_idx * beat_duration
        else:
            quantized[i] = (beat_idx + swing_positions[closest_idx]) * beat_duration
    
    errors = quantized - times
    offset = 0.0
    
    return quantized, errors, offset


def _analyze_sections(
    times: np.ndarray,
    bpm: float,
    section_duration_beats: int,
    tolerance_ms: float,
) -> List[Dict]:
    """Analyze subdivision patterns per section."""
    beat_duration = 60.0 / bpm
    section_duration = beat_duration * section_duration_beats
    
    max_time = times[-1] if len(times) > 0 else 0
    sections = []
    
    section_start = 0.0
    while section_start < max_time:
        section_end = section_start + section_duration
        
        # Get hits in this section
        mask = (times >= section_start) & (times < section_end)
        section_times = times[mask]
        
        if len(section_times) >= 4:
            analysis = analyze_subdivisions(section_times, bpm, tolerance_ms)
            sections.append({
                "start": section_start,
                "end": section_end,
                "best_grid": analysis.best_grid,
                "confidence": analysis.confidence,
                "is_polyrhythmic": analysis.is_polyrhythmic,
                "hit_count": len(section_times),
            })
        
        section_start = section_end
    
    return sections


def _preserve_groove(
    original_times: np.ndarray,
    quantized_times: np.ndarray,
    beat_duration: float,
    groove_tolerance: float,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Preserve intentional micro-timing (groove) while fixing errors.
    
    Groove is detected as CONSISTENT small deviations at specific
    beat positions. Random errors are not groove.
    """
    if len(original_times) == 0:
        return quantized_times, None
    
    # Calculate position-in-beat for each hit
    beat_positions = np.mod(original_times / beat_duration, 1.0)
    
    # Discretize to 16 positions per beat for analysis
    position_bins = (beat_positions * 16).astype(int) % 16
    
    # Calculate deviations from quantized at each position
    deviations = original_times - quantized_times
    
    # Group deviations by beat position
    position_deviations: Dict[int, List[float]] = {i: [] for i in range(16)}
    for pos, dev in zip(position_bins, deviations):
        if abs(dev) <= groove_tolerance:
            position_deviations[pos].append(dev)
    
    # Calculate mean deviation per position (this is the groove signature)
    groove_signature = np.zeros(16)
    for pos, devs in position_deviations.items():
        if len(devs) >= 3:  # Need enough samples
            mean_dev = np.mean(devs)
            std_dev = np.std(devs)
            # Only count as groove if consistent (low std)
            if std_dev < groove_tolerance * 0.5:
                groove_signature[pos] = mean_dev
    
    # Apply groove to quantized times
    result = quantized_times.copy()
    for i, pos in enumerate(position_bins):
        if abs(groove_signature[pos]) > 0:
            result[i] += groove_signature[pos]
    
    return result, groove_signature


# Convenience function for integration with existing beatmap generator
def auto_quantize_with_subdivision_detection(
    times: np.ndarray,
    bpm: float,
    tolerance_ms: float = 12.0,
) -> Dict:
    """
    Drop-in replacement for existing quantization that adds smart detection.
    
    Returns a dict compatible with existing _quantize_times format but with
    additional subdivision analysis.
    """
    result = smart_quantize(
        times, bpm, tolerance_ms,
        prefer_simple=True,
        detect_per_section=True,
        preserve_groove=True,
    )
    
    return {
        "bpm": bpm,
        "grid": result.primary_grid.name,
        "quantized": result.quantized_times,
        "errors": result.errors,
        "coverage": result.coverage,
        "mean_error": result.mean_error,
        "median_error": result.median_error,
        "offset": result.offset,
        "step": result.primary_grid.step_duration(60.0 / bpm),
        # New fields
        "detected_subdivisions": result.detected_subdivisions,
        "swing_detected": result.swing_detected,
        "swing_ratio": result.swing_ratio,
        "tuplet_detected": result.tuplet_detected,
        "tuplet_type": result.tuplet_type,
        "section_analysis": result.section_grids,
        "groove_preserved": result.micro_timing_preserved,
    }


# =============================================================================
# DYNAMIC TUPLET DISCOVERY
# =============================================================================

def discover_tuplet_ratio(
    hit_times: Sequence[float],
    bpm: float,
    max_n: int = 15,
    tolerance_ms: float = 15.0,
) -> Tuple[int, int, float]:
    """
    Dynamically discover what N-tuplet (if any) best fits the timing data.
    
    This doesn't assume any particular tuplet - it searches for the N that
    best explains the inter-onset intervals.
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        max_n: Maximum N to search for (e.g., 15 for up to 15-tuplets)
        tolerance_ms: Tolerance for matching
        
    Returns:
        Tuple of (n, in_space_of, confidence)
        e.g., (5, 4, 0.92) means "5 in the space of 4" with 92% confidence
    """
    if len(hit_times) < 3:
        return (4, 4, 0.0)  # Default to straight
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    tolerance = tolerance_ms / 1000.0
    
    # Calculate inter-onset intervals
    iois = np.diff(times)
    
    # Normalize IOIs to beat fractions
    beat_fractions = iois / beat_duration
    
    best_n = 4
    best_in_space_of = 4
    best_score = 0.0
    
    # Try each possible tuplet
    for n in range(2, max_n + 1):
        # Try different "in space of" values
        for in_space_of in [2, 4, 8]:
            if n <= in_space_of:
                continue  # Not a valid tuplet
            
            # Expected step size for this tuplet
            expected_step = in_space_of / n
            
            # Score how well IOIs match this step (or multiples thereof)
            scores = []
            for frac in beat_fractions:
                # How many steps is this interval?
                num_steps = frac / expected_step
                # How close to an integer?
                step_error = abs(num_steps - round(num_steps))
                if round(num_steps) > 0:
                    scores.append(1.0 - min(step_error * 2, 1.0))
            
            if scores:
                avg_score = np.mean(scores)
                # Slight penalty for higher N (prefer simpler interpretations)
                complexity_penalty = (n - 4) * 0.01
                final_score = avg_score - complexity_penalty
                
                if final_score > best_score:
                    best_score = final_score
                    best_n = n
                    best_in_space_of = in_space_of
    
    return (best_n, best_in_space_of, best_score)


def detect_arbitrary_swing_ratio(
    hit_times: Sequence[float],
    bpm: float,
) -> Tuple[float, float]:
    """
    Detect the exact swing ratio from timing data.
    
    Instead of matching against predefined ratios (1.33, 1.5, 1.67),
    this calculates the actual ratio from the music.
    
    Returns:
        Tuple of (swing_ratio, confidence)
    """
    if len(hit_times) < 6:
        return (1.0, 0.0)
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    
    # Look at pairs of eighth notes
    eighth_duration = beat_duration / 2
    
    # Find IOIs that are roughly eighth-note sized
    iois = np.diff(times)
    eighth_mask = (iois > eighth_duration * 0.3) & (iois < eighth_duration * 1.7)
    
    if np.sum(eighth_mask) < 4:
        return (1.0, 0.0)
    
    # Separate into "on-beat" and "off-beat" based on position
    on_beat_iois = []
    off_beat_iois = []
    
    cumulative_time = times[0]
    for i, (ioi, is_eighth) in enumerate(zip(iois, eighth_mask)):
        if is_eighth:
            beat_pos = (cumulative_time / beat_duration) % 1.0
            if beat_pos < 0.25 or beat_pos > 0.75:
                on_beat_iois.append(ioi)
            else:
                off_beat_iois.append(ioi)
        cumulative_time += ioi
    
    if len(on_beat_iois) < 2 or len(off_beat_iois) < 2:
        return (1.0, 0.3)
    
    # Calculate ratio
    mean_on = np.mean(on_beat_iois)
    mean_off = np.mean(off_beat_iois)
    
    if mean_off < 0.001:
        return (1.0, 0.0)
    
    ratio = mean_on / mean_off
    
    # Confidence based on consistency
    on_std = np.std(on_beat_iois) / mean_on if mean_on > 0 else 1.0
    off_std = np.std(off_beat_iois) / mean_off if mean_off > 0 else 1.0
    consistency = 1.0 - min(1.0, (on_std + off_std))
    
    # Clamp ratio to reasonable range
    ratio = max(0.8, min(2.5, ratio))
    
    return (ratio, consistency)


# =============================================================================
# DYNAMIC TIME SIGNATURE DETECTION
# =============================================================================

@dataclass
class DynamicTimeSignature:
    """Dynamically detected time signature."""
    numerator: int
    denominator: int
    confidence: float
    beat_grouping: List[int]  # e.g., [3, 3, 2] for 8/8 additive meter
    is_compound: bool
    is_additive: bool  # Asymmetric meters like 7/8 as 2+2+3
    detected_period_beats: float


def detect_dynamic_time_signature(
    hit_times: Sequence[float],
    bpm: float,
    max_numerator: int = 15,
    check_additive: bool = True,
) -> DynamicTimeSignature:
    """
    Dynamically detect time signature without assuming standard meters.
    
    This can detect:
    - Standard meters (4/4, 3/4, 6/8)
    - Odd meters (5/4, 7/8, 11/8)
    - Additive meters (7/8 as 2+2+3 or 3+2+2)
    - Compound meters (6/8, 9/8, 12/8)
    - Mixed meters that change
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        max_numerator: Maximum numerator to consider
        check_additive: Whether to analyze additive/asymmetric groupings
        
    Returns:
        DynamicTimeSignature with full analysis
    """
    if len(hit_times) < 8:
        return DynamicTimeSignature(
            numerator=4, denominator=4, confidence=0.5,
            beat_grouping=[4], is_compound=False, is_additive=False,
            detected_period_beats=4.0
        )
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    
    # Resolution for analysis
    subdivisions_per_beat = 48
    grid_resolution = beat_duration / subdivisions_per_beat
    
    # Build onset grid
    max_time = times[-1]
    grid_size = int(np.ceil(max_time / grid_resolution)) + 1
    onset_grid = np.zeros(grid_size, dtype=np.float32)
    
    for t in times:
        idx = int(t / grid_resolution)
        if 0 <= idx < grid_size:
            onset_grid[idx] += 1.0
    
    if onset_grid.max() > 0:
        onset_grid /= onset_grid.max()
    
    # Autocorrelation to find period
    n = len(onset_grid)
    fft = np.fft.fft(onset_grid, n=2*n)
    autocorr = np.fft.ifft(fft * np.conj(fft)).real[:n]
    autocorr = autocorr / (autocorr[0] + 1e-10)
    
    # Search for best period
    min_period = 2 * subdivisions_per_beat
    max_period = max_numerator * subdivisions_per_beat
    
    best_period = 4 * subdivisions_per_beat
    best_strength = 0.0
    
    for period in range(min_period, min(max_period, len(autocorr))):
        if autocorr[period] > best_strength:
            best_strength = autocorr[period]
            best_period = period
    
    detected_beats = best_period / subdivisions_per_beat
    
    # Analyze for compound vs simple
    iois = np.diff(times)
    beat_fractions = iois / beat_duration
    triplet_count = np.sum(
        (np.abs(beat_fractions - 1/3) < 0.1) |
        (np.abs(beat_fractions - 2/3) < 0.1)
    )
    triplet_ratio = triplet_count / len(beat_fractions) if len(beat_fractions) > 0 else 0
    is_compound = triplet_ratio > 0.2
    
    # Determine numerator and denominator
    if is_compound:
        numerator = int(round(detected_beats * 3 / 1.5))
        numerator = max(3, (numerator // 3) * 3)  # Round to multiple of 3
        denominator = 8
    else:
        numerator = int(round(detected_beats))
        numerator = max(2, min(max_numerator, numerator))
        denominator = 4
    
    # Analyze additive grouping for odd meters
    beat_grouping = [numerator]
    is_additive = False
    
    if check_additive and numerator in [5, 7, 9, 10, 11, 13]:
        grouping, grouping_confidence = _detect_additive_grouping(
            times, beat_duration, numerator
        )
        if grouping_confidence > 0.6:
            beat_grouping = grouping
            is_additive = True
    
    return DynamicTimeSignature(
        numerator=numerator,
        denominator=denominator,
        confidence=min(1.0, best_strength + 0.2),
        beat_grouping=beat_grouping,
        is_compound=is_compound,
        is_additive=is_additive,
        detected_period_beats=detected_beats,
    )


def _detect_additive_grouping(
    times: np.ndarray,
    beat_duration: float,
    numerator: int,
) -> Tuple[List[int], float]:
    """
    Detect additive grouping for asymmetric meters.
    
    For example, 7/8 could be:
    - 2+2+3 (most common in Balkan music)
    - 3+2+2 (common in progressive rock)
    - 2+3+2
    
    Returns (grouping, confidence)
    """
    # Common groupings for each meter
    grouping_options = {
        5: [[2, 3], [3, 2]],
        7: [[2, 2, 3], [3, 2, 2], [2, 3, 2]],
        9: [[2, 2, 2, 3], [3, 3, 3], [2, 3, 2, 2]],
        10: [[3, 3, 2, 2], [2, 2, 3, 3], [3, 2, 3, 2]],
        11: [[2, 2, 3, 2, 2], [3, 3, 3, 2], [2, 3, 3, 3]],
        13: [[3, 3, 3, 2, 2], [2, 2, 3, 3, 3], [3, 2, 3, 2, 3]],
    }
    
    if numerator not in grouping_options:
        return [numerator], 0.0
    
    # Analyze accent patterns
    iois = np.diff(times)
    beat_fractions = iois / beat_duration
    
    # Normalize to eighth notes (assuming denominator 8)
    eighth_duration = beat_duration / 2
    
    best_grouping = [numerator]
    best_score = 0.0
    
    for grouping in grouping_options[numerator]:
        score = _score_grouping(times, beat_duration, grouping)
        if score > best_score:
            best_score = score
            best_grouping = grouping
    
    return best_grouping, best_score


def _score_grouping(
    times: np.ndarray,
    beat_duration: float,
    grouping: List[int],
) -> float:
    """Score how well a grouping matches the accent pattern."""
    if len(times) < 4:
        return 0.0
    
    # Calculate expected accent positions
    total_eighths = sum(grouping)
    eighth_duration = beat_duration / 2
    measure_duration = total_eighths * eighth_duration
    
    accent_positions = []
    pos = 0
    for group_size in grouping:
        accent_positions.append(pos / total_eighths)
        pos += group_size
    
    # Check if hits cluster near accent positions
    hit_positions = np.mod(times / measure_duration, 1.0)
    
    scores = []
    for hit_pos in hit_positions:
        min_dist = min(abs(hit_pos - acc) for acc in accent_positions)
        min_dist = min(min_dist, 1.0 - min_dist)  # Wrap-around
        scores.append(1.0 - min_dist * 4)
    
    return max(0.0, np.mean(scores))


# =============================================================================
# POLYRHYTHM DETECTION
# =============================================================================

@dataclass
class PolyrhythmAnalysis:
    """Analysis of polyrhythmic patterns."""
    is_polyrhythmic: bool
    primary_division: int       # e.g., 4 for the "4" in "3 against 4"
    secondary_division: int     # e.g., 3 for the "3" in "3 against 4"
    confidence: float
    pattern_description: str    # e.g., "3:4 polyrhythm"


def detect_polyrhythm(
    hit_times: Sequence[float],
    bpm: float,
    max_divisions: int = 9,
) -> PolyrhythmAnalysis:
    """
    Detect if the rhythm contains polyrhythmic patterns.
    
    Polyrhythms are when two different divisions happen simultaneously,
    like 3 against 4 (common in African and Cuban music).
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        max_divisions: Maximum division to check
        
    Returns:
        PolyrhythmAnalysis with detection results
    """
    if len(hit_times) < 6:
        return PolyrhythmAnalysis(
            is_polyrhythmic=False,
            primary_division=4,
            secondary_division=4,
            confidence=0.0,
            pattern_description="insufficient data",
        )
    
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    
    # Test each pair of divisions
    best_pair = (4, 4)
    best_score = 0.0
    
    for div1 in range(2, max_divisions + 1):
        for div2 in range(div1 + 1, max_divisions + 1):
            # Skip if one divides the other (not polyrhythm)
            if div2 % div1 == 0 or div1 % div2 == 0:
                continue
            
            # Check if GCD is 1 (true polyrhythm) or small
            from math import gcd
            if gcd(div1, div2) > 2:
                continue
            
            score = _score_polyrhythm(times, beat_duration, div1, div2)
            if score > best_score:
                best_score = score
                best_pair = (div1, div2)
    
    is_poly = best_score > 0.7 and best_pair[0] != best_pair[1]
    
    return PolyrhythmAnalysis(
        is_polyrhythmic=is_poly,
        primary_division=best_pair[1],  # Larger division
        secondary_division=best_pair[0],  # Smaller division
        confidence=best_score,
        pattern_description=f"{best_pair[0]}:{best_pair[1]} polyrhythm" if is_poly else "no polyrhythm",
    )


def _score_polyrhythm(
    times: np.ndarray,
    beat_duration: float,
    div1: int,
    div2: int,
) -> float:
    """Score how well times fit a polyrhythmic grid."""
    # Combined grid positions for both divisions
    step1 = beat_duration / div1
    step2 = beat_duration / div2
    
    # Find positions that are on either grid
    combined_score1 = _score_straight_grid(times, step1, 0.015)
    combined_score2 = _score_straight_grid(times, step2, 0.015)
    
    # For polyrhythm, both should score reasonably well
    # But not perfectly on either (that would just be one division)
    if combined_score1 > 0.95 or combined_score2 > 0.95:
        return 0.0  # One grid explains everything
    
    # Both grids need to explain significant portions
    if combined_score1 < 0.3 or combined_score2 < 0.3:
        return 0.0
    
    # Score based on combined coverage
    return (combined_score1 + combined_score2) / 2


# =============================================================================
# METRIC MODULATION DETECTION
# =============================================================================

@dataclass
class MetricModulation:
    """Detected metric modulation (tempo relationship change)."""
    time: float                 # When the modulation occurs
    old_bpm: float
    new_bpm: float
    ratio: Tuple[int, int]      # e.g., (3, 2) for dotted quarter = quarter
    confidence: float
    description: str


def detect_metric_modulations(
    hit_times: Sequence[float],
    initial_bpm: float,
    min_section_length: float = 4.0,  # seconds
) -> List[MetricModulation]:
    """
    Detect metric modulations (tempo changes based on rhythmic relationships).
    
    Metric modulation is when the tempo changes but maintains a relationship
    to the previous tempo, like "dotted quarter = quarter" (3:2 ratio).
    
    Args:
        hit_times: Hit times in seconds
        initial_bpm: Starting tempo
        min_section_length: Minimum section length to analyze
        
    Returns:
        List of detected metric modulations
    """
    if len(hit_times) < 20:
        return []
    
    times = np.array(sorted(hit_times))
    modulations = []
    
    # Analyze in windows
    window_size = min_section_length
    current_bpm = initial_bpm
    
    for i in range(0, int(times[-1] - window_size), int(window_size / 2)):
        window_start = i
        window_end = i + window_size
        
        mask = (times >= window_start) & (times < window_end)
        window_times = times[mask]
        
        if len(window_times) < 8:
            continue
        
        # Estimate local tempo from IOIs
        iois = np.diff(window_times)
        if len(iois) < 4:
            continue
        
        # Find most common IOI (assumed to be the beat or subdivision)
        median_ioi = np.median(iois)
        local_bpm = 60.0 / median_ioi
        
        # Check for simple ratios
        ratio = local_bpm / current_bpm
        
        simple_ratios = [
            ((3, 2), 1.5),      # dotted quarter = quarter
            ((2, 3), 2/3),      # quarter = dotted quarter
            ((4, 3), 4/3),      # triplet relationship
            ((3, 4), 0.75),
            ((5, 4), 1.25),     # quintuplet relationship
            ((4, 5), 0.8),
            ((2, 1), 2.0),      # double time
            ((1, 2), 0.5),      # half time
        ]
        
        for (num, denom), expected_ratio in simple_ratios:
            if abs(ratio - expected_ratio) < 0.1:
                modulations.append(MetricModulation(
                    time=window_start,
                    old_bpm=current_bpm,
                    new_bpm=current_bpm * expected_ratio,
                    ratio=(num, denom),
                    confidence=1.0 - abs(ratio - expected_ratio) * 5,
                    description=f"{num}:{denom} modulation at {window_start:.1f}s",
                ))
                current_bpm = local_bpm
                break
    
    return modulations


# =============================================================================
# COMPOSITE ANALYSIS
# =============================================================================

@dataclass
class ComprehensiveRhythmAnalysis:
    """Complete rhythmic analysis of a track."""
    bpm: float
    time_signature: DynamicTimeSignature
    primary_subdivision: SubdivisionGrid
    swing_ratio: float
    is_swing: bool
    polyrhythm: PolyrhythmAnalysis
    tuplet_info: Tuple[int, int, float]  # (n, in_space_of, confidence)
    metric_modulations: List[MetricModulation]
    section_analyses: List[Dict]
    groove_signature: Optional[np.ndarray]
    complexity_score: float  # 0-1, how rhythmically complex


def comprehensive_rhythm_analysis(
    hit_times: Sequence[float],
    bpm: float,
    tolerance_ms: float = 12.0,
) -> ComprehensiveRhythmAnalysis:
    """
    Perform complete rhythmic analysis on hit timing data.
    
    This combines all analysis methods to give a full picture of the
    rhythmic content, useful for:
    - Choosing the best quantization strategy
    - Detecting complex rhythmic patterns
    - Generating appropriate difficulty ratings
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        tolerance_ms: Tolerance for grid matching
        
    Returns:
        ComprehensiveRhythmAnalysis with all analysis results
    """
    times = list(hit_times)
    
    # Time signature
    time_sig = detect_dynamic_time_signature(times, bpm)
    
    # Subdivision analysis
    subdivision_analysis = analyze_subdivisions(times, bpm, tolerance_ms)
    primary_grid = SUBDIVISION_GRIDS.get(
        subdivision_analysis.best_grid,
        SUBDIVISION_GRIDS["sixteenth"]
    )
    
    # Swing detection
    swing_ratio, swing_conf = detect_arbitrary_swing_ratio(times, bpm)
    is_swing = swing_conf > 0.5 and abs(swing_ratio - 1.0) > 0.15
    
    # Polyrhythm
    polyrhythm = detect_polyrhythm(times, bpm)
    
    # Tuplet discovery
    tuplet_info = discover_tuplet_ratio(times, bpm)
    
    # Metric modulations
    modulations = detect_metric_modulations(times, bpm)
    
    # Section-by-section analysis
    beat_duration = 60.0 / bpm
    section_duration = beat_duration * 16
    sections = _analyze_sections(np.array(times), bpm, 16, tolerance_ms)
    
    # Groove signature
    result = smart_quantize(times, bpm, tolerance_ms)
    groove_sig = result.groove_signature
    
    # Calculate complexity score
    complexity = _calculate_complexity(
        time_sig, primary_grid, is_swing, polyrhythm, tuplet_info, modulations
    )
    
    return ComprehensiveRhythmAnalysis(
        bpm=bpm,
        time_signature=time_sig,
        primary_subdivision=primary_grid,
        swing_ratio=swing_ratio,
        is_swing=is_swing,
        polyrhythm=polyrhythm,
        tuplet_info=tuplet_info,
        metric_modulations=modulations,
        section_analyses=sections,
        groove_signature=groove_sig,
        complexity_score=complexity,
    )


def _calculate_complexity(
    time_sig: DynamicTimeSignature,
    subdivision: SubdivisionGrid,
    is_swing: bool,
    polyrhythm: PolyrhythmAnalysis,
    tuplet_info: Tuple[int, int, float],
    modulations: List[MetricModulation],
) -> float:
    """Calculate overall rhythmic complexity score (0-1)."""
    score = 0.0
    
    # Odd time signatures add complexity
    if time_sig.numerator not in [2, 3, 4]:
        score += 0.15
    if time_sig.numerator in [5, 7, 11, 13]:
        score += 0.1
    if time_sig.is_additive:
        score += 0.1
    
    # Tuplets add complexity
    if subdivision.subdivision_type == SubdivisionType.TUPLET:
        score += 0.15
    if tuplet_info[0] >= 5:  # Quintuplet or higher
        score += 0.1
    
    # Swing is slightly complex
    if is_swing:
        score += 0.05
    
    # Polyrhythms are complex
    if polyrhythm.is_polyrhythmic:
        score += 0.2
    
    # Metric modulations are very complex
    score += len(modulations) * 0.15
    
    return min(1.0, score)


# =============================================================================
# DYNAMIC GRID MANAGEMENT
# =============================================================================

class DynamicGridRegistry:
    """
    Runtime registry for dynamically creating and caching grids.
    
    This allows creating arbitrary tuplet grids on-demand without
    having to pre-generate all possible combinations.
    """
    
    def __init__(self) -> None:
        """Initialize with base grids."""
        self._grids: Dict[str, SubdivisionGrid] = dict(SUBDIVISION_GRIDS)
        self._custom_grids: Dict[str, SubdivisionGrid] = {}
    
    def get_grid(self, name: str) -> Optional[SubdivisionGrid]:
        """Get a grid by name, creating it if possible."""
        if name in self._grids:
            return self._grids[name]
        
        # Try to parse dynamic grid name like "tuplet_7:4" or "17_tuplet"
        if "tuplet" in name.lower():
            n = self._parse_tuplet_name(name)
            if n:
                return self.create_tuplet_grid(n)
        
        return None
    
    def _parse_tuplet_name(self, name: str) -> Optional[int]:
        """Parse a tuplet name to get the N value."""
        import re
        
        # Match patterns like "7:4", "7_tuplet", "septuplet", etc.
        patterns = [
            r"(\d+):(\d+)",           # 7:4 format
            r"(\d+)_tuplet",          # 7_tuplet
            r"tuplet_(\d+)",          # tuplet_7
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name.lower())
            if match:
                return int(match.group(1))
        
        # Named tuplets
        named = {
            "triplet": 3, "quintuplet": 5, "septuplet": 7,
            "nonuplet": 9, "undecuplet": 11, "tredecuplet": 13,
        }
        for tuplet_name, n in named.items():
            if tuplet_name in name.lower():
                return n
        
        return None
    
    def create_tuplet_grid(
        self, 
        n: int, 
        in_space_of: int = 4,
        base: str = "quarter",
    ) -> SubdivisionGrid:
        """
        Create an N-tuplet grid dynamically.
        
        Args:
            n: Number of notes in the tuplet
            in_space_of: Space the tuplet occupies (default: 4 = quarter note)
            base: Base note value
            
        Returns:
            SubdivisionGrid for the tuplet
        """
        name = f"{n}_in_{in_space_of}_tuplet"
        
        if name in self._custom_grids:
            return self._custom_grids[name]
        
        # Create the grid
        grid = SubdivisionGrid.create_tuplet(n, in_space_of, base)
        self._custom_grids[name] = grid
        self._grids[name] = grid
        
        return grid
    
    def create_swing_grid(
        self,
        ratio: float,
        base: str = "eighth",
    ) -> SubdivisionGrid:
        """
        Create a swing grid with arbitrary ratio.
        
        Args:
            ratio: Swing ratio (long/short, e.g., 1.5 = light swing)
            base: Base note value
            
        Returns:
            SubdivisionGrid for the swing pattern
        """
        name = f"swing_{ratio:.3f}_{base}"
        
        if name in self._custom_grids:
            return self._custom_grids[name]
        
        grid = SubdivisionGrid.create_swing(ratio, base)
        self._custom_grids[name] = grid
        self._grids[name] = grid
        
        return grid
    
    def create_compound_grid(
        self,
        groupings: List[int],
        base_division: int = 8,
    ) -> SubdivisionGrid:
        """
        Create a grid for compound/additive meters.
        
        Args:
            groupings: Beat groupings (e.g., [3, 3, 2] for 8/8)
            base_division: Base note value (8 = eighth note)
            
        Returns:
            SubdivisionGrid that respects the groupings
        """
        name = f"compound_{'+'.join(map(str, groupings))}_{base_division}"
        
        if name in self._custom_grids:
            return self._custom_grids[name]
        
        total = sum(groupings)
        # For compound meters, we create grid points at each subdivision
        # with emphasis on grouping boundaries
        divisions = total * 2  # Double for common subdivisions
        
        grid = SubdivisionGrid(
            name=name,
            divisions_per_beat=divisions,
            subdivision_type=SubdivisionType.TUPLET,
            tuplet_ratio=(total, 4),
            swing_ratio=1.0,
        )
        
        self._custom_grids[name] = grid
        self._grids[name] = grid
        
        return grid
    
    def register_grid(self, name: str, grid: SubdivisionGrid) -> None:
        """Register a custom grid."""
        self._custom_grids[name] = grid
        self._grids[name] = grid
    
    def list_grids(self) -> List[str]:
        """List all available grid names."""
        return sorted(self._grids.keys())
    
    def list_custom_grids(self) -> List[str]:
        """List only custom-created grids."""
        return sorted(self._custom_grids.keys())


# Global registry instance
GRID_REGISTRY = DynamicGridRegistry()


def create_adaptive_grid(
    hit_times: Sequence[float],
    bpm: float,
    tolerance_ms: float = 12.0,
) -> SubdivisionGrid:
    """
    Create an optimal grid based on actual hit timing data.
    
    This function analyzes the hit times and creates a custom grid
    that best fits the actual rhythmic content, even if it's an
    unusual tuplet or non-standard subdivision.
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        tolerance_ms: Matching tolerance
        
    Returns:
        Optimal SubdivisionGrid for the data
    """
    # First try standard analysis
    analysis = analyze_subdivisions(hit_times, bpm, tolerance_ms)
    
    if analysis.confidence > 0.85:
        # Standard grid works well
        return SUBDIVISION_GRIDS[analysis.best_grid]
    
    # Try dynamic tuplet detection
    n, base, conf = discover_tuplet_ratio(list(hit_times), bpm)
    
    if conf > 0.6:
        # Found a good tuplet match
        return GRID_REGISTRY.create_tuplet_grid(n, base)
    
    # Try swing detection
    swing_ratio, swing_conf = detect_arbitrary_swing_ratio(list(hit_times), bpm)
    
    if swing_conf > 0.6 and abs(swing_ratio - 1.0) > 0.1:
        return GRID_REGISTRY.create_swing_grid(swing_ratio)
    
    # Fall back to best standard grid
    return SUBDIVISION_GRIDS[analysis.best_grid]


def quantize_with_dynamic_grid(
    hit_times: Sequence[float],
    bpm: float,
    tolerance_ms: float = 12.0,
    preserve_groove: bool = True,
) -> QuantizationResult:
    """
    Quantize using automatically-created optimal grid.
    
    This is the most flexible quantization method - it will:
    1. Detect what grid is actually being used
    2. Create a custom grid if needed (unusual tuplets, swing)
    3. Quantize with groove preservation
    
    Args:
        hit_times: Hit times in seconds
        bpm: Tempo in BPM
        tolerance_ms: Snap tolerance
        preserve_groove: Keep intentional micro-timing
        
    Returns:
        QuantizationResult with fully adaptive quantization
    """
    # Create optimal grid
    optimal_grid = create_adaptive_grid(hit_times, bpm, tolerance_ms)
    
    # Register it for future use
    GRID_REGISTRY.register_grid(f"adaptive_{id(hit_times)}", optimal_grid)
    
    # Quantize using this grid
    times = np.array(sorted(hit_times))
    beat_duration = 60.0 / bpm
    tolerance = tolerance_ms / 1000.0
    
    quantized, errors, offset = _quantize_with_grid(
        times, beat_duration, optimal_grid, tolerance
    )
    
    # Groove preservation
    groove_signature = None
    if preserve_groove:
        groove_tolerance = (tolerance_ms * 0.66) / 1000.0
        quantized, groove_signature = _preserve_groove(
            times, quantized, beat_duration, groove_tolerance
        )
        errors = quantized - times
    
    # Get additional detection info
    dynamic_tuplet = discover_tuplet_ratio(list(hit_times), bpm)
    polyrhythm = detect_polyrhythm(list(hit_times), bpm)
    time_sig = detect_dynamic_time_signature(list(hit_times), bpm)
    swing_ratio, _ = detect_arbitrary_swing_ratio(list(hit_times), bpm)
    
    # Statistics
    abs_errors = np.abs(errors)
    within_tolerance = np.sum(abs_errors <= tolerance)
    
    return QuantizationResult(
        primary_grid=optimal_grid,
        quantized_times=quantized,
        errors=errors,
        coverage=within_tolerance / len(times) if len(times) > 0 else 1.0,
        mean_error=float(np.mean(abs_errors)) if len(times) > 0 else 0.0,
        median_error=float(np.median(abs_errors)) if len(times) > 0 else 0.0,
        offset=offset,
        detected_subdivisions={optimal_grid.name: 1.0},
        swing_detected=abs(swing_ratio - 1.0) > 0.1,
        swing_ratio=swing_ratio,
        tuplet_detected=optimal_grid.subdivision_type in [
            SubdivisionType.TRIPLET, SubdivisionType.TUPLET,
            SubdivisionType.QUINTUPLET, SubdivisionType.SEPTUPLET,
        ],
        tuplet_type=optimal_grid.subdivision_type.value,
        micro_timing_preserved=preserve_groove,
        groove_signature=groove_signature,
        dynamic_tuplet_n=dynamic_tuplet[0] if dynamic_tuplet[2] > 0.3 else None,
        dynamic_tuplet_base=dynamic_tuplet[1] if dynamic_tuplet[2] > 0.3 else None,
        dynamic_tuplet_confidence=dynamic_tuplet[2],
        is_polyrhythmic=polyrhythm.is_polyrhythmic,
        polyrhythm_grids=polyrhythm.active_grids if polyrhythm.is_polyrhythmic else None,
        detected_time_signature=(time_sig.numerator, time_sig.denominator),
        is_additive_meter=time_sig.is_additive,
        beat_grouping=time_sig.grouping if time_sig.is_additive else None,
    )
