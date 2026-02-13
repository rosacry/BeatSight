"""
Automatic parameter estimation for the BeatSight transcription pipeline.

Replaces hardcoded --sensitivity and --quantization values with audio-adaptive
estimates so the pipeline works well across different songs without manual tuning.

Two main functions:
  - estimate_optimal_sensitivity(): Analyzes audio characteristics to pick sensitivity
  - estimate_optimal_quantization(): Analyzes onset density + BPM to pick grid resolution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SensitivityEstimate:
    """Result of automatic sensitivity estimation."""
    sensitivity: float          # Recommended value [0, 100]
    dynamic_range_db: float     # Measured dynamic range in dB
    spectral_flux_density: float  # Mean spectral flux (onset density proxy)
    estimated_bpm: float        # BPM used in calculation
    genre_hint: Optional[str]   # Genre if detected
    explanation: str            # Human-readable reasoning


@dataclass
class QuantizationEstimate:
    """Result of automatic quantization grid estimation."""
    grid: str                      # Recommended grid name
    finest_ioi_ms: float          # Shortest inter-onset interval found (ms)
    median_ioi_ms: float          # Median IOI (ms)
    pct_sub_sixteenth: float      # % of IOIs shorter than a 16th note
    estimated_bpm: float          # BPM used in calculation
    explanation: str              # Human-readable reasoning


def estimate_optimal_sensitivity(
    audio_data: np.ndarray,
    sample_rate: int,
    bpm: Optional[float] = None,
    genre: Optional[str] = None,
) -> SensitivityEstimate:
    """
    Estimate the optimal onset detection sensitivity for a given audio signal.

    Analyzes:
    1. Dynamic range - wider range means ghost notes exist -> higher sensitivity
    2. Spectral flux density - higher density suggests faster playing -> higher sensitivity
    3. BPM - faster tempo needs higher sensitivity to catch 32nd notes
    4. Genre - metal/prog naturally needs higher sensitivity than pop

    Args:
        audio_data: Raw audio samples (mono or multi-channel, will be averaged)
        sample_rate: Sample rate in Hz
        bpm: Optional BPM (if already detected). None = estimate internally.
        genre: Optional genre string (e.g. "metal", "prog_metal", "jazz")

    Returns:
        SensitivityEstimate with the recommended sensitivity value
    """
    # Ensure mono
    if audio_data.ndim > 1:
        audio_mono = np.mean(audio_data, axis=0)
    else:
        audio_mono = audio_data

    # Normalize to prevent scale issues
    peak = np.max(np.abs(audio_mono))
    if peak > 0:
        audio_norm = audio_mono / peak
    else:
        return SensitivityEstimate(
            sensitivity=60.0, dynamic_range_db=0.0, spectral_flux_density=0.0,
            estimated_bpm=bpm or 120.0, genre_hint=genre,
            explanation="Silent audio, using default sensitivity",
        )

    # === 1. Dynamic Range Analysis ===
    # Compute RMS in overlapping windows
    hop = sample_rate // 20  # 50ms windows
    frame_size = sample_rate // 10  # 100ms
    n_frames = max(1, (len(audio_norm) - frame_size) // hop)

    rms_values = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * hop
        end = start + frame_size
        frame = audio_norm[start:end]
        rms_values[i] = np.sqrt(np.mean(frame ** 2) + 1e-10)

    # Remove silence frames (below -60dB)
    silence_threshold = 10 ** (-60 / 20)
    active_rms = rms_values[rms_values > silence_threshold]

    if len(active_rms) < 5:
        dynamic_range_db = 20.0  # Default for very sparse audio
    else:
        # Dynamic range = difference between loud and quiet active frames
        p95 = np.percentile(active_rms, 95)
        p5 = np.percentile(active_rms, 5)
        dynamic_range_db = 20 * np.log10(p95 / max(p5, 1e-10))
        dynamic_range_db = min(dynamic_range_db, 80.0)  # Cap at 80dB

    # === 2. Spectral Flux (Onset Density Proxy) ===
    try:
        import librosa
        # Compute mel spectrogram and spectral flux
        hop_length = 512
        S = librosa.feature.melspectrogram(
            y=audio_norm, sr=sample_rate, hop_length=hop_length, n_mels=40
        )
        S_db = librosa.power_to_db(S, ref=np.max)

        # Spectral flux = sum of positive differences across frames
        flux = np.sum(np.maximum(0, np.diff(S_db, axis=1)), axis=0)
        # Normalize by number of frames and duration
        duration = len(audio_norm) / sample_rate
        spectral_flux_density = float(np.mean(flux)) if len(flux) > 0 else 0.0
        # Also count "onset-like" frames (flux above mean + 1 std)
        if len(flux) > 1:
            flux_threshold = np.mean(flux) + np.std(flux)
            onset_frame_count = np.sum(flux > flux_threshold)
            onsets_per_second = onset_frame_count / max(duration, 1.0) * (sample_rate / hop_length)
            # Normalize to a reasonable scale
            onsets_per_second = min(onsets_per_second, 30.0)
        else:
            onsets_per_second = 4.0  # Default
    except Exception:
        spectral_flux_density = 5.0
        onsets_per_second = 4.0

    # === 3. BPM Factor ===
    estimated_bpm = bpm if bpm and bpm > 0 else 120.0

    # === 4. Compute Sensitivity Score ===
    # Start from a base of 55 (slightly below current default of 60)
    sensitivity = 55.0

    # Dynamic range contribution: wider range -> higher sensitivity
    # 10dB range is narrow (simple pop), 40dB is very dynamic (prog/ghost notes)
    if dynamic_range_db > 30:
        sensitivity += min(15.0, (dynamic_range_db - 30) * 0.75)
    elif dynamic_range_db < 15:
        sensitivity -= min(10.0, (15 - dynamic_range_db) * 0.5)

    # BPM contribution: faster songs need higher sensitivity for fast subdivisions
    # 120 BPM = neutral, 200+ BPM = +10 sensitivity
    if estimated_bpm > 140:
        sensitivity += min(10.0, (estimated_bpm - 140) * 0.15)
    elif estimated_bpm < 90:
        sensitivity -= min(8.0, (90 - estimated_bpm) * 0.15)

    # Spectral flux density: more transient-rich audio -> higher sensitivity
    if spectral_flux_density > 8:
        sensitivity += min(8.0, (spectral_flux_density - 8) * 0.8)

    # Genre-based adjustment (if known)
    genre_label = (genre or "").lower().replace("-", "_")
    genre_adjustments = {
        "metal": 8.0,
        "prog_metal": 10.0,
        "progressive": 6.0,
        "jazz": 5.0,
        "funk": 4.0,
        "rock": 2.0,
        "pop": -3.0,
        "electronic": -2.0,
        "country": -2.0,
        "blues": 1.0,
        "latin": 3.0,
    }
    genre_adj = genre_adjustments.get(genre_label, 0.0)
    sensitivity += genre_adj

    # Clamp to valid range
    sensitivity = float(np.clip(sensitivity, 30.0, 95.0))

    # Build explanation
    parts = [f"base=55"]
    if dynamic_range_db > 30:
        parts.append(f"dynamic_range={dynamic_range_db:.0f}dB(+{min(15.0, (dynamic_range_db-30)*0.75):.1f})")
    elif dynamic_range_db < 15:
        parts.append(f"dynamic_range={dynamic_range_db:.0f}dB(-{min(10.0, (15-dynamic_range_db)*0.5):.1f})")
    if estimated_bpm > 140:
        parts.append(f"bpm={estimated_bpm:.0f}(+{min(10.0, (estimated_bpm-140)*0.15):.1f})")
    elif estimated_bpm < 90:
        parts.append(f"bpm={estimated_bpm:.0f}(-{min(8.0, (90-estimated_bpm)*0.15):.1f})")
    if genre_adj != 0:
        parts.append(f"genre={genre_label}({genre_adj:+.0f})")

    explanation = f"Auto-sensitivity: {sensitivity:.0f} [{', '.join(parts)}]"

    return SensitivityEstimate(
        sensitivity=sensitivity,
        dynamic_range_db=dynamic_range_db,
        spectral_flux_density=spectral_flux_density,
        estimated_bpm=estimated_bpm,
        genre_hint=genre,
        explanation=explanation,
    )


def estimate_optimal_quantization(
    onset_times: Sequence[float],
    bpm: float,
    genre: Optional[str] = None,
) -> QuantizationEstimate:
    """
    Estimate the optimal quantization grid resolution based on onset distribution.

    Analyzes inter-onset intervals (IOIs) relative to the beat grid to determine
    how fine a grid is needed to faithfully represent the rhythm.

    Grid levels (at 120 BPM as reference):
      - quarter:     500ms (1 per beat)
      - eighth:      250ms (2 per beat)
      - triplet:     167ms (3 per beat)
      - sixteenth:   125ms (4 per beat)
      - thirtysecond: 62.5ms (8 per beat)

    Args:
        onset_times: Detected onset times in seconds (sorted)
        bpm: Detected BPM
        genre: Optional genre hint

    Returns:
        QuantizationEstimate with recommended grid
    """
    if len(onset_times) < 2:
        return QuantizationEstimate(
            grid="sixteenth", finest_ioi_ms=0.0, median_ioi_ms=0.0,
            pct_sub_sixteenth=0.0, estimated_bpm=bpm,
            explanation="Too few onsets, using default sixteenth grid",
        )

    times = np.array(sorted(onset_times))
    iois = np.diff(times) * 1000  # Convert to milliseconds

    # Filter out very large gaps (> 2 seconds = silence/gaps between sections)
    iois_active = iois[iois < 2000]
    if len(iois_active) < 2:
        iois_active = iois

    # Calculate grid thresholds at this BPM
    beat_ms = 60000.0 / max(bpm, 1.0)  # ms per beat
    grid_thresholds = {
        "quarter": beat_ms,            # 1 per beat
        "eighth": beat_ms / 2,         # 2 per beat
        "triplet": beat_ms / 3,        # 3 per beat
        "sixteenth": beat_ms / 4,      # 4 per beat
        "thirtysecond": beat_ms / 8,   # 8 per beat
    }

    # Key statistics
    finest_ioi_ms = float(np.percentile(iois_active, 2))  # 2nd percentile (robust)
    p10_ioi_ms = float(np.percentile(iois_active, 10))
    median_ioi_ms = float(np.median(iois_active))

    # What percentage of IOIs are shorter than various grid levels?
    sixteenth_ms = grid_thresholds["sixteenth"]
    thirtysecond_ms = grid_thresholds["thirtysecond"]

    # An IOI "needs" a grid level if it's closer to that grid than the next coarser one
    # Use a tolerance of 1.3x the grid level to decide
    pct_sub_sixteenth = float(np.mean(iois_active < sixteenth_ms * 0.8)) * 100
    pct_sub_eighth = float(np.mean(iois_active < grid_thresholds["eighth"] * 0.8)) * 100

    # Decision logic:
    # 1. If >5% of IOIs are shorter than sixteenth, need thirtysecond
    # 2. If >5% of IOIs are shorter than eighth, need sixteenth
    # 3. If most IOIs cluster at quarter or eighth, use that
    # 4. Check for triplet feel separately

    # Check for triplet feel: IOIs clustering near beat_ms/3 or beat_ms/6
    triplet_ms = grid_thresholds["triplet"]
    triplet_tolerance = triplet_ms * 0.15  # 15% tolerance
    near_triplet = np.sum(np.abs(iois_active - triplet_ms) < triplet_tolerance)
    near_sixth = np.sum(np.abs(iois_active - triplet_ms / 2) < triplet_tolerance / 2)
    triplet_ratio = (near_triplet + near_sixth) / max(len(iois_active), 1)

    # Determine grid
    if pct_sub_sixteenth > 5.0 or finest_ioi_ms < thirtysecond_ms * 1.5:
        grid = "thirtysecond"
        explanation = (f"Thirtysecond grid needed: {pct_sub_sixteenth:.1f}% of IOIs "
                       f"below sixteenth ({sixteenth_ms:.0f}ms), "
                       f"finest IOI={finest_ioi_ms:.0f}ms")
    elif triplet_ratio > 0.15:
        grid = "triplet"
        explanation = (f"Triplet feel detected: {triplet_ratio*100:.0f}% of IOIs "
                       f"near triplet grid ({triplet_ms:.0f}ms)")
    elif pct_sub_eighth > 10.0 or p10_ioi_ms < sixteenth_ms * 1.3:
        grid = "sixteenth"
        explanation = (f"Sixteenth grid: {pct_sub_eighth:.1f}% of IOIs below eighth "
                       f"({grid_thresholds['eighth']:.0f}ms), p10={p10_ioi_ms:.0f}ms")
    elif median_ioi_ms > grid_thresholds["eighth"] * 1.5:
        grid = "eighth"
        explanation = (f"Eighth grid sufficient: median IOI={median_ioi_ms:.0f}ms, "
                       f"eighth threshold={grid_thresholds['eighth']:.0f}ms")
    else:
        grid = "sixteenth"
        explanation = f"Default sixteenth grid: median IOI={median_ioi_ms:.0f}ms"

    # Genre override: metal/prog almost always needs at least sixteenth
    genre_label = (genre or "").lower().replace("-", "_")
    if genre_label in ("metal", "prog_metal", "progressive") and grid in ("eighth", "quarter"):
        grid = "sixteenth"
        explanation += f" (upgraded from coarser grid for {genre_label})"

    return QuantizationEstimate(
        grid=grid,
        finest_ioi_ms=finest_ioi_ms,
        median_ioi_ms=median_ioi_ms,
        pct_sub_sixteenth=pct_sub_sixteenth,
        estimated_bpm=bpm,
        explanation=explanation,
    )

