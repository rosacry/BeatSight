#!/usr/bin/env python3
"""
Count Estimation Module for Multi-Label Drum Transcription

This module estimates how many instances of the same drum class hit simultaneously.
The multi-label model outputs BINARY presence (crash=1/0), but when 2 crashes hit
together, we need to know it's actually 2 crashes, not 1.

Detection Methods:
1. Transient Counting - Multiple attack transients in the window
2. Stereo Spread Analysis - L/R energy distribution (panned instruments)
3. Bimodal Spectrum Detection - Two distinct spectral peaks
4. Attack Envelope Analysis - Multiple rise phases in the envelope

Usage:
    from transcription.count_estimation import CountEstimator
    
    estimator = CountEstimator()
    count = estimator.estimate_count(audio_segment, sr, "crash")
    # Returns 1, 2, or 3 (capped at max_count)

    # Or use for expanding multi-label detections:
    expanded_events = estimator.expand_detections(
        detections={"crash": 0.95, "kick": 0.98},
        audio_segment=audio,
        sr=44100
    )
    # Returns [("crash", 0.95), ("crash", 0.95), ("kick", 0.98)] if 2 crashes detected
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

try:
    from scipy import signal as scipy_signal
    from scipy.ndimage import maximum_filter1d
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    scipy_signal = None
    maximum_filter1d = None

logger = logging.getLogger(__name__)


def _safe_n_fft(signal_length: int, preferred: int, minimum: int = 4) -> int:
    """Choose an FFT window that does not exceed the available signal length."""
    if signal_length <= 2:
        return max(2, signal_length)

    clipped = min(preferred, signal_length)
    if clipped < minimum:
        return clipped

    return 1 << int(np.floor(np.log2(clipped)))


@dataclass
class CountEstimationConfig:
    """Configuration for count estimation per instrument class."""
    
    # Maximum count to return (caps estimation)
    max_count: int = 3
    
    # Transient detection settings
    transient_threshold: float = 0.3  # Relative threshold for onset detection
    min_transient_gap_ms: float = 5.0  # Minimum gap between transients (ms)
    
    # Stereo spread settings
    stereo_threshold: float = 0.3  # L/R ratio threshold for panning detection
    stereo_energy_threshold: float = 0.1  # Minimum energy to consider a channel active
    
    # Spectral bimodal detection settings
    spectral_peak_distance_hz: float = 200.0  # Minimum Hz between spectral peaks
    spectral_peak_prominence: float = 0.2  # Minimum prominence for peak detection
    
    # Envelope analysis settings
    envelope_smoothing_ms: float = 5.0  # RMS smoothing window
    envelope_peak_threshold: float = 0.5  # Relative threshold for envelope peaks
    envelope_min_gap_ms: float = 8.0  # Minimum gap between envelope peaks
    
    # Feature weights for final decision
    transient_weight: float = 0.35
    stereo_weight: float = 0.25
    spectral_weight: float = 0.25
    envelope_weight: float = 0.15
    
    # Confidence threshold for counting additional hits
    count_confidence_threshold: float = 0.6


# Instrument-specific configurations
INSTRUMENT_CONFIGS: Dict[str, CountEstimationConfig] = {
    # Crashes are often panned L/R and have distinct spectral signatures
    "crash": CountEstimationConfig(
        max_count=3,
        stereo_weight=0.35,
        spectral_weight=0.30,
        transient_weight=0.25,
        envelope_weight=0.10,
        spectral_peak_distance_hz=300.0,  # Crashes have wider spectral spread
    ),
    # China cymbals - similar to crashes
    "china": CountEstimationConfig(
        max_count=2,
        stereo_weight=0.30,
        spectral_weight=0.35,
        transient_weight=0.25,
        envelope_weight=0.10,
    ),
    # Splash - usually single, but can have multiples
    "splash": CountEstimationConfig(
        max_count=2,
        stereo_weight=0.30,
        spectral_weight=0.35,
        transient_weight=0.25,
        envelope_weight=0.10,
    ),
    # Toms - different sizes have different pitches
    "tom": CountEstimationConfig(
        max_count=4,  # Kits can have 4+ toms
        spectral_weight=0.40,  # Toms are well-separated by pitch
        stereo_weight=0.25,
        transient_weight=0.25,
        envelope_weight=0.10,
        spectral_peak_distance_hz=80.0,  # Toms are closer in frequency
    ),
    # Ride - bow and bell can hit together but ML separates them
    "ride_bow": CountEstimationConfig(
        max_count=2,
        stereo_weight=0.20,
        spectral_weight=0.35,
        transient_weight=0.30,
        envelope_weight=0.15,
    ),
    "ride_bell": CountEstimationConfig(
        max_count=2,
        stereo_weight=0.20,
        spectral_weight=0.35,
        transient_weight=0.30,
        envelope_weight=0.15,
    ),
    # Kick - usually single, rarely simultaneous doubles (double bass)
    "kick": CountEstimationConfig(
        max_count=2,
        transient_weight=0.45,  # Kick transients are very distinctive
        envelope_weight=0.35,
        spectral_weight=0.15,
        stereo_weight=0.05,  # Kick is usually center-panned
        min_transient_gap_ms=20.0,  # Double bass has wider gaps
    ),
    # Snare - ghost notes and rimshots are handled by rimshot detector
    "snare": CountEstimationConfig(
        max_count=2,  # Rare to have 2 snares, but possible in some kits
        transient_weight=0.40,
        envelope_weight=0.30,
        spectral_weight=0.20,
        stereo_weight=0.10,
    ),
    # Hi-hats - almost never multiple simultaneous
    "hihat_closed": CountEstimationConfig(
        max_count=1,  # Effectively disabled
    ),
    "hihat_open": CountEstimationConfig(
        max_count=1,
    ),
    "hihat_pedal": CountEstimationConfig(
        max_count=1,
    ),
    # Cross-stick - single per kit
    "cross_stick": CountEstimationConfig(
        max_count=1,
    ),
}


class CountEstimator:
    """
    Estimates how many instances of the same instrument hit simultaneously.
    
    The multi-label classifier outputs binary presence (crash=1 means "crash detected"),
    but doesn't distinguish between 1 crash and 2+ crashes hitting together.
    This module analyzes the audio to estimate the actual count.
    
    Primary use case: When the multi-label model detects "crash", this estimates
    whether it's 1 crash, 2 crashes (L/R panned), or 3 crashes (fills).
    
    Example:
        estimator = CountEstimator()
        
        # For a single detection
        count = estimator.estimate_count(audio_window, 44100, "crash")
        
        # For expanding all detections from multi-label model
        expanded = estimator.expand_detections(
            {"crash": 0.95, "kick": 0.88},
            audio_window,
            44100
        )
    """
    
    def __init__(
        self,
        default_config: Optional[CountEstimationConfig] = None,
        instrument_configs: Optional[Dict[str, CountEstimationConfig]] = None,
    ):
        """
        Initialize the count estimator.
        
        Args:
            default_config: Default configuration for unknown instruments
            instrument_configs: Per-instrument configuration overrides
        """
        self.default_config = default_config or CountEstimationConfig()
        self.instrument_configs = instrument_configs or INSTRUMENT_CONFIGS.copy()
        
        if not HAS_LIBROSA:
            logger.warning("librosa not available - some features disabled")
        if not HAS_SCIPY:
            logger.warning("scipy not available - some features disabled")
    
    def get_config(self, detected_class: str) -> CountEstimationConfig:
        """Get configuration for an instrument class."""
        return self.instrument_configs.get(detected_class, self.default_config)
    
    def estimate_count(
        self,
        audio_segment: np.ndarray,
        sr: int,
        detected_class: str,
    ) -> int:
        """
        Estimate how many instances of the detected class hit simultaneously.
        
        Args:
            audio_segment: Audio window around the onset (typically 100ms)
            sr: Sample rate
            detected_class: Class detected by ML model (e.g., "crash")
            
        Returns:
            Count (1, 2, 3...) of simultaneous hits, capped at max_count
        """
        config = self.get_config(detected_class)
        
        # Early exit for instruments that don't support multiples
        if config.max_count <= 1:
            return 1
        
        # Handle mono/stereo
        audio = np.asarray(audio_segment)
        if audio.ndim == 1:
            is_stereo = False
            mono_audio = audio
        elif audio.ndim == 2:
            is_stereo = audio.shape[0] == 2 or audio.shape[1] == 2
            # Normalize to (channels, samples) format
            if audio.shape[0] > audio.shape[1]:
                audio = audio.T
            mono_audio = audio.mean(axis=0) if is_stereo else audio.flatten()
        else:
            logger.warning(f"Unexpected audio shape: {audio.shape}")
            return 1
        
        # Collect evidence from each detection method
        scores: Dict[str, Tuple[int, float]] = {}  # method -> (count, confidence)
        
        # 1. Transient counting
        transient_count, transient_conf = self._count_transients(
            mono_audio, sr, config
        )
        scores["transient"] = (transient_count, transient_conf)
        
        # 2. Stereo spread analysis (if stereo)
        if is_stereo:
            stereo_count, stereo_conf = self._analyze_stereo_spread(
                audio, sr, config
            )
            scores["stereo"] = (stereo_count, stereo_conf)
        else:
            scores["stereo"] = (1, 0.0)  # No stereo evidence
        
        # 3. Bimodal spectrum detection
        spectral_count, spectral_conf = self._detect_bimodal_spectrum(
            mono_audio, sr, config, detected_class
        )
        scores["spectral"] = (spectral_count, spectral_conf)
        
        # 4. Attack envelope analysis
        envelope_count, envelope_conf = self._analyze_attack_envelope(
            mono_audio, sr, config
        )
        scores["envelope"] = (envelope_count, envelope_conf)
        
        # Combine evidence with weighted voting
        final_count = self._combine_evidence(scores, config)
        
        return min(final_count, config.max_count)
    
    def _count_transients(
        self,
        audio: np.ndarray,
        sr: int,
        config: CountEstimationConfig,
    ) -> Tuple[int, float]:
        """
        Count attack transients in the audio window.
        
        Multiple attack transients = multiple hits.
        Uses onset detection with low threshold.
        """
        if not HAS_LIBROSA:
            return 1, 0.0

        try:
            audio_len = int(len(audio))
            if audio_len < 4:
                return 1, 0.0

            onset_n_fft = _safe_n_fft(audio_len, preferred=2048, minimum=8)
            hop_length = max(1, min(64, onset_n_fft // 4))

            # Compute onset strength envelope
            onset_env = librosa.onset.onset_strength(
                y=audio.astype(np.float32),
                sr=sr,
                n_fft=onset_n_fft,
                hop_length=hop_length,
            )
            
            if len(onset_env) < 2:
                return 1, 0.5
            
            # Normalize
            onset_env = onset_env / (onset_env.max() + 1e-8)
            
            # Find peaks above threshold
            threshold = config.transient_threshold
            min_gap_frames = int(
                config.min_transient_gap_ms * sr / (1000 * hop_length)
            )
            min_gap_frames = max(1, min_gap_frames)
            
            # Simple peak finding with minimum distance
            peaks = self._find_peaks_simple(
                onset_env,
                threshold=threshold,
                min_distance=min_gap_frames,
            )
            
            count = len(peaks)
            
            # Confidence based on peak prominence
            if count >= 2 and len(onset_env) > 0:
                # Higher confidence if peaks are clearly separated
                prominences = onset_env[peaks] - threshold
                avg_prominence = np.mean(prominences)
                confidence = min(0.9, avg_prominence / (1.0 - threshold + 1e-8))
            elif count == 1:
                confidence = 0.7
            else:
                count = 1
                confidence = 0.3
            
            return count, confidence
            
        except Exception as e:
            logger.debug(f"Transient counting failed: {e}")
            return 1, 0.0
    
    def _analyze_stereo_spread(
        self,
        audio: np.ndarray,
        sr: int,
        config: CountEstimationConfig,
    ) -> Tuple[int, float]:
        """
        Analyze stereo spread to detect panned instruments.
        
        If audio has high energy on both L and R channels, it suggests
        two instruments panned apart (common for crashes).
        """
        if audio.ndim != 2 or audio.shape[0] != 2:
            return 1, 0.0
        
        try:
            left = audio[0]
            right = audio[1]
            
            # Compute RMS energy for each channel
            left_rms = np.sqrt(np.mean(left ** 2))
            right_rms = np.sqrt(np.mean(right ** 2))
            total_rms = left_rms + right_rms + 1e-8
            
            # Check if both channels have significant energy
            left_ratio = left_rms / total_rms
            right_ratio = right_rms / total_rms
            
            min_threshold = config.stereo_energy_threshold
            
            if left_rms < min_threshold and right_rms < min_threshold:
                return 1, 0.0  # Too quiet to analyze
            
            # Check for balanced energy (indicates possible panning)
            # If one channel dominates, it's likely a single panned source
            spread_threshold = config.stereo_threshold
            
            # Compute decorrelation (different sources = lower correlation)
            if len(left) > 10:
                correlation = np.corrcoef(left, right)[0, 1]
                if np.isnan(correlation):
                    correlation = 1.0
            else:
                correlation = 1.0
            
            # Evidence for multiple sources:
            # 1. Both channels have significant energy
            # 2. Low correlation between channels
            both_active = (
                left_ratio > spread_threshold and 
                right_ratio > spread_threshold
            )
            low_correlation = correlation < 0.7
            
            if both_active and low_correlation:
                # Strong evidence of 2 panned sources
                confidence = (1.0 - correlation) * min(left_ratio, right_ratio) * 2
                return 2, min(0.9, confidence)
            elif both_active:
                # Possible 2 sources but high correlation
                return 2, 0.4
            else:
                return 1, 0.6
                
        except Exception as e:
            logger.debug(f"Stereo analysis failed: {e}")
            return 1, 0.0
    
    def _detect_bimodal_spectrum(
        self,
        audio: np.ndarray,
        sr: int,
        config: CountEstimationConfig,
        detected_class: str,
    ) -> Tuple[int, float]:
        """
        Detect bimodal spectrum indicating two instruments with different pitches.
        
        Two distinct spectral peaks = two instruments with different fundamentals.
        Works well for toms (different sizes = different pitches) and crashes.
        """
        if not HAS_LIBROSA or not HAS_SCIPY:
            return 1, 0.0
        
        try:
            # Compute FFT
            n_fft = min(2048, len(audio))
            if n_fft < 256:
                return 1, 0.0
            
            # Use windowed FFT
            window = np.hanning(n_fft)
            audio_windowed = audio[:n_fft] * window
            
            fft = np.fft.rfft(audio_windowed)
            magnitude = np.abs(fft)
            freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
            
            # Focus on relevant frequency range based on instrument
            if detected_class in ("kick",):
                freq_min, freq_max = 30, 200
            elif detected_class in ("tom",):
                freq_min, freq_max = 60, 400
            elif detected_class in ("snare",):
                freq_min, freq_max = 100, 500
            else:  # Cymbals
                freq_min, freq_max = 200, 8000
            
            # Filter to frequency range
            mask = (freqs >= freq_min) & (freqs <= freq_max)
            filtered_mag = magnitude[mask]
            filtered_freqs = freqs[mask]
            
            if len(filtered_mag) < 10:
                return 1, 0.0
            
            # Normalize
            filtered_mag = filtered_mag / (filtered_mag.max() + 1e-8)
            
            # Find peaks
            min_distance_hz = config.spectral_peak_distance_hz
            freq_resolution = sr / n_fft
            min_distance_bins = max(1, int(min_distance_hz / freq_resolution))
            
            peaks = self._find_peaks_simple(
                filtered_mag,
                threshold=config.spectral_peak_prominence,
                min_distance=min_distance_bins,
            )
            
            if len(peaks) >= 3:
                # Multiple distinct spectral peaks
                confidence = min(0.8, 0.4 + len(peaks) * 0.1)
                return min(3, len(peaks)), confidence
            elif len(peaks) == 2:
                # Two peaks - check if they're well separated
                peak_freqs = filtered_freqs[peaks]
                freq_ratio = max(peak_freqs) / (min(peak_freqs) + 1e-8)
                
                if freq_ratio > 1.3:  # Well separated
                    confidence = 0.7
                else:
                    confidence = 0.4
                return 2, confidence
            else:
                return 1, 0.5
                
        except Exception as e:
            logger.debug(f"Spectral analysis failed: {e}")
            return 1, 0.0
    
    def _analyze_attack_envelope(
        self,
        audio: np.ndarray,
        sr: int,
        config: CountEstimationConfig,
    ) -> Tuple[int, float]:
        """
        Analyze attack envelope for multiple rise phases.
        
        Multiple rise phases in the envelope = multiple hits.
        """
        try:
            # Compute smoothed RMS envelope
            smoothing_samples = int(config.envelope_smoothing_ms * sr / 1000)
            smoothing_samples = max(1, smoothing_samples)
            
            # Simple RMS envelope with sliding window
            audio_sq = audio ** 2
            
            if len(audio_sq) < smoothing_samples * 2:
                return 1, 0.0
            
            # Moving average for smoothing
            kernel = np.ones(smoothing_samples) / smoothing_samples
            envelope = np.sqrt(np.convolve(audio_sq, kernel, mode='same'))
            
            # Normalize
            envelope = envelope / (envelope.max() + 1e-8)
            
            # Compute derivative to find rising edges
            derivative = np.diff(envelope)
            
            # Find positive peaks in derivative (attack phases)
            attack_threshold = config.envelope_peak_threshold * derivative.max()
            min_gap_samples = int(config.envelope_min_gap_ms * sr / 1000)
            
            # Find attack peaks
            attack_peaks = self._find_peaks_simple(
                derivative,
                threshold=attack_threshold,
                min_distance=max(1, min_gap_samples),
            )
            
            count = len(attack_peaks)
            
            if count >= 2:
                # Multiple attacks detected
                confidence = min(0.8, 0.4 + count * 0.15)
                return count, confidence
            else:
                return 1, 0.5
                
        except Exception as e:
            logger.debug(f"Envelope analysis failed: {e}")
            return 1, 0.0
    
    def _find_peaks_simple(
        self,
        signal: np.ndarray,
        threshold: float,
        min_distance: int,
    ) -> np.ndarray:
        """
        Simple peak finding without scipy dependency.
        
        Args:
            signal: 1D signal array
            threshold: Minimum value for peak detection
            min_distance: Minimum samples between peaks
            
        Returns:
            Array of peak indices
        """
        if len(signal) < 3:
            return np.array([], dtype=int)
        
        # Find local maxima
        peaks = []
        for i in range(1, len(signal) - 1):
            if signal[i] > signal[i-1] and signal[i] > signal[i+1]:
                if signal[i] >= threshold:
                    peaks.append(i)
        
        if not peaks:
            return np.array([], dtype=int)
        
        # Filter by minimum distance (keep highest peaks)
        peaks = np.array(peaks)
        peak_values = signal[peaks]
        
        # Sort by value descending
        sorted_indices = np.argsort(peak_values)[::-1]
        
        selected = []
        for idx in sorted_indices:
            peak_pos = peaks[idx]
            # Check if far enough from already selected peaks
            too_close = False
            for sel_pos in selected:
                if abs(peak_pos - sel_pos) < min_distance:
                    too_close = True
                    break
            if not too_close:
                selected.append(peak_pos)
        
        return np.array(sorted(selected), dtype=int)
    
    def _combine_evidence(
        self,
        scores: Dict[str, Tuple[int, float]],
        config: CountEstimationConfig,
    ) -> int:
        """
        Combine evidence from all detection methods using weighted voting.
        
        Args:
            scores: Dict of method -> (count, confidence)
            config: Configuration with weights
            
        Returns:
            Final estimated count
        """
        weights = {
            "transient": config.transient_weight,
            "stereo": config.stereo_weight,
            "spectral": config.spectral_weight,
            "envelope": config.envelope_weight,
        }
        
        # Weighted vote for each possible count
        count_votes: Dict[int, float] = {}
        
        for method, (count, confidence) in scores.items():
            weight = weights.get(method, 0.0)
            vote_strength = weight * confidence
            
            if vote_strength > 0:
                count_votes[count] = count_votes.get(count, 0.0) + vote_strength
        
        if not count_votes:
            return 1
        
        # Find count with highest weighted vote
        best_count = max(count_votes.keys(), key=lambda c: count_votes[c])
        best_vote = count_votes[best_count]
        
        # Require minimum confidence to report count > 1
        if best_count > 1 and best_vote < config.count_confidence_threshold:
            return 1
        
        return best_count
    
    def expand_detections(
        self,
        detections: Dict[str, float],
        audio_segment: np.ndarray,
        sr: int,
    ) -> List[Tuple[str, float]]:
        """
        Expand multi-label detections by estimating counts.
        
        Takes the output of the multi-label classifier and expands
        single detections to multiple events based on count estimation.
        
        Args:
            detections: Dict of class -> confidence from multi-label model
                       e.g., {"crash": 0.95, "kick": 0.88}
            audio_segment: Audio window around the onset
            sr: Sample rate
            
        Returns:
            List of (class, confidence) tuples, with repeated entries
            for multiple simultaneous hits.
            e.g., [("crash", 0.95), ("crash", 0.95), ("kick", 0.88)]
        """
        expanded: List[Tuple[str, float]] = []
        
        for class_name, confidence in detections.items():
            count = self.estimate_count(audio_segment, sr, class_name)
            
            # Add 'count' copies of this detection
            for _ in range(count):
                expanded.append((class_name, confidence))
        
        return expanded
    
    def estimate_all_counts(
        self,
        detections: Dict[str, float],
        audio_segment: np.ndarray,
        sr: int,
    ) -> Dict[str, Tuple[int, float]]:
        """
        Estimate counts for all detected classes.
        
        Args:
            detections: Dict of class -> confidence from multi-label model
            audio_segment: Audio window around the onset
            sr: Sample rate
            
        Returns:
            Dict of class -> (count, original_confidence)
        """
        return {
            class_name: (self.estimate_count(audio_segment, sr, class_name), conf)
            for class_name, conf in detections.items()
        }


def estimate_simultaneous_hits(
    audio: np.ndarray,
    sr: int,
    detected_classes: List[str],
) -> Dict[str, int]:
    """
    Convenience function to estimate counts for a list of detected classes.
    
    Args:
        audio: Audio segment around the onset
        sr: Sample rate
        detected_classes: List of classes detected by multi-label model
        
    Returns:
        Dict mapping each class to its estimated count
    """
    estimator = CountEstimator()
    return {
        cls: estimator.estimate_count(audio, sr, cls)
        for cls in detected_classes
    }


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Test count estimation on audio files"
    )
    parser.add_argument(
        "--audio",
        type=str,
        required=True,
        help="Path to audio file",
    )
    parser.add_argument(
        "--onset-time",
        type=float,
        default=None,
        help="Specific onset time to analyze (seconds). If not provided, uses first 100ms.",
    )
    parser.add_argument(
        "--window-ms",
        type=float,
        default=100.0,
        help="Window size in milliseconds (default: 100)",
    )
    parser.add_argument(
        "--class",
        dest="detected_class",
        type=str,
        default="crash",
        help="Class to estimate count for (default: crash)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed analysis",
    )
    
    args = parser.parse_args()
    
    if not HAS_LIBROSA:
        print("ERROR: librosa is required for count estimation")
        sys.exit(1)
    
    # Load audio
    print(f"Loading audio: {args.audio}")
    audio, sr = librosa.load(args.audio, sr=None, mono=False)
    print(f"  Sample rate: {sr}")
    print(f"  Shape: {audio.shape}")
    print(f"  Duration: {audio.shape[-1] / sr:.2f}s")
    
    # Extract segment
    window_samples = int(args.window_ms * sr / 1000)
    
    if args.onset_time is not None:
        center = int(args.onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(audio.shape[-1], start + window_samples)
    else:
        start = 0
        end = min(window_samples, audio.shape[-1])
    
    if audio.ndim == 1:
        segment = audio[start:end]
    else:
        segment = audio[:, start:end]
    
    print(f"Analyzing segment: {start/sr:.3f}s - {end/sr:.3f}s")
    print(f"  Segment shape: {segment.shape}")
    print(f"  Testing class: {args.detected_class}")
    print()
    
    # Run estimation
    estimator = CountEstimator()
    config = estimator.get_config(args.detected_class)
    print(f"Config for {args.detected_class}:")
    print(f"  max_count: {config.max_count}")
    print(f"  transient_weight: {config.transient_weight}")
    print(f"  stereo_weight: {config.stereo_weight}")
    print(f"  spectral_weight: {config.spectral_weight}")
    print(f"  envelope_weight: {config.envelope_weight}")
    print()
    
    # Get count
    count = estimator.estimate_count(segment, sr, args.detected_class)
    
    print(f"=== RESULT ===")
    print(f"Estimated count for '{args.detected_class}': {count}")
    
    if count > 1:
        print(f"  → Would emit {count}x {args.detected_class} events")
