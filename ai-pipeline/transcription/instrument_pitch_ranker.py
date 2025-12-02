#!/usr/bin/env python3
"""
Instrument Pitch Ranking Post-Processor

This module automatically distinguishes multiple instruments of the same type
within a song by analyzing their acoustic properties (pitch, timbre).

The classifier detects generic types (e.g., "crash", "china", "tom_high"),
then this post-processor clusters and ranks them to produce specific labels
(e.g., "crash_1", "crash_2", "china_1", "tom_high_1", "tom_high_2").

=== CYMBAL RANKING ===
See docs/CYMBAL_PITCH_RANKING.md for detailed documentation.

Supported cymbal types:
- crash → crash_1, crash_2, crash_3, crash_4 (ranked by pitch, high to low)
- china → china_1, china_2 (ranked by pitch)
- splash → splash_1, splash_2 (ranked by pitch)
- ride_bow → ride_bow_1, ride_bow_2 (for dual-ride setups)
- ride_bell → ride_bell_1, ride_bell_2

=== TOM RANKING ===
See docs/TOM_PITCH_RANKING.md for detailed documentation.

Supported tom types:
- tom_high → tom_high_1, tom_high_2 (e.g., 10" vs 12" rack toms)
- tom_mid → tom_mid_1, tom_mid_2 (e.g., 13" vs 14" rack toms)
- tom_low → tom_low_1, tom_low_2 (e.g., 16" vs 18" floor toms)

=== HI-HATS ===
Hi-hats (hihat_closed, hihat_open, hihat_pedal, etc.) are NOT ranked
as drummers typically have only one hi-hat per kit.

Usage:
    from instrument_pitch_ranker import InstrumentPitchRanker
    
    ranker = InstrumentPitchRanker()
    refined_events = ranker.process_song(events, audio, sr)
    
    # Convenience functions
    from instrument_pitch_ranker import rank_cymbals_in_beatmap
    ranked = rank_cymbals_in_beatmap(events, "song.wav")
"""

import numpy as np
import librosa
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from enum import Enum
import warnings

logger = logging.getLogger(__name__)


class RankingStrategy(Enum):
    """Strategy for assigning numeric suffixes to instruments."""
    PITCH_HIGH_TO_LOW = "pitch_high_to_low"  # crash_1 = highest pitch
    PITCH_LOW_TO_HIGH = "pitch_low_to_high"  # crash_1 = lowest pitch
    FIRST_OCCURRENCE = "first_occurrence"     # crash_1 = first heard in song


@dataclass
class DetectedEvent:
    """A single detected drum/cymbal event."""
    timestamp: float          # Time in seconds
    label: str                # Original label from classifier (e.g., "crash")
    confidence: float = 1.0   # Classifier confidence
    audio_segment: Optional[np.ndarray] = None  # Raw audio around the event
    
    # Filled by feature extraction
    spectral_centroid: Optional[float] = None
    mfcc: Optional[np.ndarray] = None
    attack_time: Optional[float] = None
    decay_time: Optional[float] = None
    rms_energy: Optional[float] = None
    
    # Filled by clustering/ranking
    cluster_id: Optional[int] = None
    ranked_label: Optional[str] = None  # e.g., "crash_1"


@dataclass
class InstrumentConfig:
    """Configuration for how to handle a specific instrument type."""
    base_label: str                    # e.g., "crash"
    supports_multiples: bool = True    # Whether this instrument can have multiples
    ranking_strategy: RankingStrategy = RankingStrategy.PITCH_HIGH_TO_LOW
    min_samples_for_clustering: int = 3  # Need at least N hits to cluster
    typical_count: Tuple[int, int] = (1, 3)  # (min, max) expected in typical kit
    
    # Feature weights for clustering (sum to 1.0)
    centroid_weight: float = 0.6
    mfcc_weight: float = 0.3
    decay_weight: float = 0.1


# Default configurations for each instrument type
INSTRUMENT_CONFIGS: Dict[str, InstrumentConfig] = {
    # Cymbals - typically distinguished by pitch
    "crash": InstrumentConfig(
        base_label="crash",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 4),
        centroid_weight=0.7,
        mfcc_weight=0.2,
        decay_weight=0.1,
    ),
    "china": InstrumentConfig(
        base_label="china",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.6,
        mfcc_weight=0.3,
        decay_weight=0.1,
    ),
    "splash": InstrumentConfig(
        base_label="splash",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.7,
        mfcc_weight=0.2,
        decay_weight=0.1,
    ),
    "ride_bow": InstrumentConfig(
        base_label="ride_bow",
        supports_multiples=True,  # Some kits have 2 rides
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.5,
        mfcc_weight=0.4,
        decay_weight=0.1,
    ),
    "ride_bell": InstrumentConfig(
        base_label="ride_bell",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.5,
        mfcc_weight=0.4,
        decay_weight=0.1,
    ),
    
    # Hi-hats - typically single per kit, but distinguish open/closed/pedal
    "hihat_closed": InstrumentConfig(
        base_label="hihat_closed",
        supports_multiples=False,  # Usually just one hi-hat
        typical_count=(1, 1),
    ),
    "hihat_open": InstrumentConfig(
        base_label="hihat_open",
        supports_multiples=False,
        typical_count=(1, 1),
    ),
    "hihat_pedal": InstrumentConfig(
        base_label="hihat_pedal",
        supports_multiples=False,
        typical_count=(1, 1),
    ),
    "hihat_splash": InstrumentConfig(
        base_label="hihat_splash",
        supports_multiples=False,
        typical_count=(1, 1),
    ),
    "hihat_foot_splash": InstrumentConfig(
        base_label="hihat_foot_splash",
        supports_multiples=False,
        typical_count=(1, 1),
    ),
    
    # Toms - VERY important to distinguish!
    # A drummer might have 2 rack toms both classified as "tom_high"
    "tom_high": InstrumentConfig(
        base_label="tom_high",
        supports_multiples=True,  # Could have 2 high rack toms
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.5,
        mfcc_weight=0.3,
        decay_weight=0.2,
    ),
    "tom_mid": InstrumentConfig(
        base_label="tom_mid",
        supports_multiples=True,
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.5,
        mfcc_weight=0.3,
        decay_weight=0.2,
    ),
    "tom_low": InstrumentConfig(
        base_label="tom_low",
        supports_multiples=True,  # Could have 2 floor toms
        ranking_strategy=RankingStrategy.PITCH_HIGH_TO_LOW,
        typical_count=(1, 2),
        centroid_weight=0.5,
        mfcc_weight=0.3,
        decay_weight=0.2,
    ),
}


class InstrumentPitchRanker:
    """
    Post-processor that distinguishes multiple cymbals/toms of the same type.
    
    The classifier outputs generic labels like "crash" or "tom_high".
    This ranker clusters hits by timbre and assigns specific labels like
    "crash_1", "crash_2", "tom_high_1", "tom_high_2" based on pitch.
    
    Ranking is done via spectral centroid analysis:
    - Higher pitch = _1 (e.g., smaller/brighter cymbal or tom)
    - Lower pitch = _2, _3, etc. (e.g., larger/darker cymbal or tom)
    """
    
    def __init__(
        self,
        segment_duration: float = 0.5,  # Seconds of audio to analyze per hit
        segment_offset: float = -0.01,  # Start slightly before detected onset
        min_cluster_confidence: float = 0.6,
        configs: Optional[Dict[str, InstrumentConfig]] = None,
    ):
        """
        Initialize the pitch ranker.
        
        Args:
            segment_duration: Duration of audio segment to extract per hit
            segment_offset: Offset from detected onset (negative = before)
            min_cluster_confidence: Minimum confidence to trust clustering
            configs: Override default instrument configurations
        """
        self.segment_duration = segment_duration
        self.segment_offset = segment_offset
        self.min_cluster_confidence = min_cluster_confidence
        self.configs = configs or INSTRUMENT_CONFIGS.copy()
    
    def process_song(
        self,
        events: List[Dict],
        audio: np.ndarray,
        sr: int,
        return_features: bool = False,
    ) -> List[Dict]:
        """
        Process all events in a song, assigning ranked labels.
        
        Args:
            events: List of detection events, each with 'timestamp' and 'label'
            audio: Full song audio as numpy array
            sr: Sample rate
            return_features: If True, include extracted features in output
            
        Returns:
            List of events with 'ranked_label' added
        """
        # Convert to DetectedEvent objects
        detected = [
            DetectedEvent(
                timestamp=e.get("timestamp", e.get("time", 0)),
                label=e.get("label", e.get("class", "")),
                confidence=e.get("confidence", e.get("score", 1.0)),
            )
            for e in events
        ]
        
        # Extract audio segments and features
        self._extract_segments(detected, audio, sr)
        self._extract_features(detected, sr)
        
        # Group by base label
        by_label = defaultdict(list)
        for event in detected:
            by_label[event.label].append(event)
        
        # Process each instrument type
        for label, group in by_label.items():
            config = self.configs.get(label)
            
            if config is None or not config.supports_multiples:
                # No ranking needed - just use original label
                for event in group:
                    event.ranked_label = event.label
            elif len(group) < config.min_samples_for_clustering:
                # Not enough samples to cluster reliably
                for event in group:
                    event.ranked_label = f"{event.label}_1"
            else:
                # Cluster and rank
                self._cluster_and_rank(group, config)
        
        # Convert back to dicts
        results = []
        for event in detected:
            result = {
                "timestamp": event.timestamp,
                "label": event.label,
                "ranked_label": event.ranked_label or event.label,
                "confidence": event.confidence,
                "cluster_id": event.cluster_id,
            }
            if return_features:
                result["features"] = {
                    "spectral_centroid": event.spectral_centroid,
                    "rms_energy": event.rms_energy,
                    "attack_time": event.attack_time,
                    "decay_time": event.decay_time,
                }
            results.append(result)
        
        return results
    
    def _extract_segments(
        self,
        events: List[DetectedEvent],
        audio: np.ndarray,
        sr: int,
    ) -> None:
        """Extract audio segments around each event."""
        for event in events:
            start_sample = int((event.timestamp + self.segment_offset) * sr)
            end_sample = start_sample + int(self.segment_duration * sr)
            
            # Clamp to valid range
            start_sample = max(0, start_sample)
            end_sample = min(len(audio), end_sample)
            
            if end_sample > start_sample:
                event.audio_segment = audio[start_sample:end_sample]
            else:
                event.audio_segment = np.zeros(int(self.segment_duration * sr))
    
    def _extract_features(
        self,
        events: List[DetectedEvent],
        sr: int,
    ) -> None:
        """Extract acoustic features from each event's audio segment."""
        for event in events:
            if event.audio_segment is None or len(event.audio_segment) < 512:
                continue
            
            segment = event.audio_segment
            
            # Spectral centroid - primary pitch indicator
            try:
                centroid = librosa.feature.spectral_centroid(y=segment, sr=sr)
                event.spectral_centroid = float(np.mean(centroid))
            except (ValueError, librosa.util.exceptions.ParameterError) as e:
                logger.debug("Spectral centroid extraction failed at %.3fs: %s", event.timestamp, e)
                event.spectral_centroid = 0.0
            
            # MFCCs - timbre fingerprint
            try:
                mfcc = librosa.feature.mfcc(y=segment, sr=sr, n_mfcc=13)
                event.mfcc = np.mean(mfcc, axis=1)
            except (ValueError, librosa.util.exceptions.ParameterError) as e:
                logger.debug("MFCC extraction failed at %.3fs: %s", event.timestamp, e)
                event.mfcc = np.zeros(13)
            
            # RMS energy
            try:
                rms = librosa.feature.rms(y=segment)
                event.rms_energy = float(np.mean(rms))
            except (ValueError, librosa.util.exceptions.ParameterError) as e:
                logger.debug("RMS extraction failed at %.3fs: %s", event.timestamp, e)
                event.rms_energy = 0.0
            
            # Attack and decay estimation
            event.attack_time = self._estimate_attack(segment, sr)
            event.decay_time = self._estimate_decay(segment, sr)
    
    def _estimate_attack(self, segment: np.ndarray, sr: int) -> float:
        """Estimate attack time in milliseconds."""
        try:
            envelope = np.abs(segment)
            # Simple smoothing
            window = int(sr * 0.005)  # 5ms window
            if window > 0 and len(envelope) > window:
                envelope = np.convolve(envelope, np.ones(window)/window, mode='same')
            
            peak_idx = np.argmax(envelope)
            if peak_idx == 0:
                return 0.0
            
            # Find 10% threshold crossing
            threshold = envelope[peak_idx] * 0.1
            for i in range(peak_idx):
                if envelope[i] >= threshold:
                    return (i / sr) * 1000  # Convert to ms
            return (peak_idx / sr) * 1000
        except (ValueError, IndexError, ZeroDivisionError) as e:
            logger.debug("Attack estimation failed: %s", e)
            return 0.0
    
    def _estimate_decay(self, segment: np.ndarray, sr: int) -> float:
        """Estimate decay time (time to -20dB) in milliseconds."""
        try:
            envelope = np.abs(segment)
            window = int(sr * 0.01)  # 10ms window
            if window > 0 and len(envelope) > window:
                envelope = np.convolve(envelope, np.ones(window)/window, mode='same')
            
            peak_idx = np.argmax(envelope)
            peak_val = envelope[peak_idx]
            
            if peak_val == 0:
                return 0.0
            
            # Find -20dB point (0.1 of peak)
            threshold = peak_val * 0.1
            for i in range(peak_idx, len(envelope)):
                if envelope[i] <= threshold:
                    return ((i - peak_idx) / sr) * 1000  # Convert to ms
            
            # Didn't decay to -20dB within segment
            return ((len(envelope) - peak_idx) / sr) * 1000
        except (ValueError, IndexError, ZeroDivisionError) as e:
            logger.debug("Decay estimation failed: %s", e)
            return 0.0
    
    def _cluster_and_rank(
        self,
        events: List[DetectedEvent],
        config: InstrumentConfig,
    ) -> None:
        """
        Cluster events by timbre similarity, then rank by pitch.
        
        Uses a simple k-means-like approach optimized for small N.
        """
        n_events = len(events)
        
        # Build feature matrix
        features = []
        for event in events:
            feat = []
            
            # Normalized spectral centroid (primary feature)
            if event.spectral_centroid is not None:
                feat.append(event.spectral_centroid)
            else:
                feat.append(0.0)
            
            # MFCC coefficients (timbre)
            if event.mfcc is not None:
                feat.extend(event.mfcc[:6])  # Use first 6 MFCCs
            else:
                feat.extend([0.0] * 6)
            
            # Decay time (distinguishes cymbal sizes)
            if event.decay_time is not None:
                feat.append(event.decay_time)
            else:
                feat.append(0.0)
            
            features.append(feat)
        
        features = np.array(features)
        
        # Normalize features
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mean = np.mean(features, axis=0)
            std = np.std(features, axis=0)
            std[std == 0] = 1  # Avoid division by zero
            features_norm = (features - mean) / std
        
        # Determine optimal number of clusters
        n_clusters = self._estimate_n_clusters(features_norm, config)
        
        if n_clusters == 1:
            # All same cymbal
            for event in events:
                event.cluster_id = 0
                event.ranked_label = f"{config.base_label}_1"
            return
        
        # Simple k-means clustering
        cluster_ids = self._kmeans(features_norm, n_clusters)
        
        # Assign cluster IDs
        for i, event in enumerate(events):
            event.cluster_id = cluster_ids[i]
        
        # Compute mean centroid per cluster for ranking
        cluster_centroids = defaultdict(list)
        for event in events:
            if event.spectral_centroid is not None:
                cluster_centroids[event.cluster_id].append(event.spectral_centroid)
        
        mean_centroids = {
            cid: np.mean(vals) for cid, vals in cluster_centroids.items()
        }
        
        # Rank clusters by centroid (high to low by default)
        if config.ranking_strategy == RankingStrategy.PITCH_HIGH_TO_LOW:
            sorted_clusters = sorted(mean_centroids.keys(), 
                                    key=lambda c: mean_centroids[c], 
                                    reverse=True)
        elif config.ranking_strategy == RankingStrategy.PITCH_LOW_TO_HIGH:
            sorted_clusters = sorted(mean_centroids.keys(),
                                    key=lambda c: mean_centroids[c])
        else:  # FIRST_OCCURRENCE
            first_occurrence = {}
            for event in events:
                if event.cluster_id not in first_occurrence:
                    first_occurrence[event.cluster_id] = event.timestamp
            sorted_clusters = sorted(first_occurrence.keys(),
                                    key=lambda c: first_occurrence[c])
        
        # Create rank mapping
        rank_map = {cid: rank + 1 for rank, cid in enumerate(sorted_clusters)}
        
        # Assign ranked labels
        for event in events:
            rank = rank_map.get(event.cluster_id, 1)
            event.ranked_label = f"{config.base_label}_{rank}"
    
    def _estimate_n_clusters(
        self,
        features: np.ndarray,
        config: InstrumentConfig,
        max_clusters: int = 10,  # Absolute maximum to try
    ) -> int:
        """
        Estimate optimal number of clusters using elbow method.
        
        The typical_count in config is just a hint - we will detect MORE
        clusters if the data clearly shows them. This allows handling
        songs with 5, 6, or even 10 crashes without any code changes.
        
        Args:
            features: Normalized feature matrix
            config: Instrument configuration (typical_count is advisory)
            max_clusters: Hard limit on clusters to try (default 10)
            
        Returns:
            Optimal number of clusters (1 to max_clusters)
        """
        n_samples = len(features)
        min_k, typical_max_k = config.typical_count
        
        # Allow up to max_clusters, but never more than n_samples
        # typical_max_k is just advisory - we go beyond if data shows it
        actual_max_k = min(max_clusters, n_samples)
        
        if actual_max_k <= 1:
            return 1
        
        # Try different k values and find elbow
        inertias = []
        for k in range(1, actual_max_k + 1):
            _, inertia = self._kmeans(features, k, return_inertia=True)
            inertias.append(inertia)
        
        if len(inertias) < 2:
            return 1
        
        # Simple elbow detection: look for biggest drop ratio
        drops = []
        for i in range(1, len(inertias)):
            if inertias[i-1] > 0:
                drop = (inertias[i-1] - inertias[i]) / inertias[i-1]
                drops.append(drop)
            else:
                drops.append(0)
        
        # If no significant drop (>30%), assume single cluster
        best_k = 1
        for i, drop in enumerate(drops):
            if drop > 0.3:  # 30% reduction threshold
                best_k = i + 2  # k is i+2 (since drops start at k=2)
        
        # Ensure at least min_k (from typical_count) but NO upper limit
        # from typical_count - we detect as many as the data shows
        return max(min_k, best_k)
    
    def _kmeans(
        self,
        features: np.ndarray,
        k: int,
        max_iter: int = 100,
        return_inertia: bool = False,
    ) -> np.ndarray:
        """
        Simple k-means implementation (avoids sklearn dependency).
        
        Args:
            features: Normalized feature matrix (n_samples, n_features)
            k: Number of clusters
            max_iter: Maximum iterations
            return_inertia: If True, return (labels, inertia)
            
        Returns:
            Cluster labels for each sample (and inertia if requested)
        """
        n_samples = len(features)
        
        if k >= n_samples:
            labels = np.arange(n_samples)
            if return_inertia:
                return labels, 0.0
            return labels
        
        # Initialize centroids using k-means++
        centroids = [features[np.random.randint(n_samples)]]
        for _ in range(1, k):
            distances = np.min([
                np.sum((features - c) ** 2, axis=1) for c in centroids
            ], axis=0)
            probs = distances / (distances.sum() + 1e-10)
            cumprobs = np.cumsum(probs)
            r = np.random.random()
            for i, cp in enumerate(cumprobs):
                if r < cp:
                    centroids.append(features[i])
                    break
            else:
                centroids.append(features[-1])
        
        centroids = np.array(centroids)
        
        # Iterate
        labels = np.zeros(n_samples, dtype=int)
        for _ in range(max_iter):
            # Assign to nearest centroid
            distances = np.array([
                np.sum((features - c) ** 2, axis=1) for c in centroids
            ]).T  # (n_samples, k)
            new_labels = np.argmin(distances, axis=1)
            
            if np.all(new_labels == labels):
                break
            labels = new_labels
            
            # Update centroids
            for j in range(k):
                mask = labels == j
                if mask.any():
                    centroids[j] = features[mask].mean(axis=0)
        
        if return_inertia:
            # Compute within-cluster sum of squares
            inertia = 0.0
            for j in range(k):
                mask = labels == j
                if mask.any():
                    inertia += np.sum((features[mask] - centroids[j]) ** 2)
            return labels, inertia
        
        return labels


# =============================================================================
# Backward compatibility alias
# =============================================================================

# Alias for backward compatibility with older code
CymbalPitchRanker = InstrumentPitchRanker


# =============================================================================
# Convenience functions
# =============================================================================

def rank_instruments_in_beatmap(
    beatmap_events: List[Dict],
    audio_path: str,
    ranker: Optional[InstrumentPitchRanker] = None,
) -> List[Dict]:
    """
    High-level function to process a beatmap and add ranked instrument labels.
    
    Processes all cymbals (crash, china, splash, ride) and toms (high, mid, low)
    to distinguish multiple instruments of the same type.
    
    Args:
        beatmap_events: List of events from beatmap generator
        audio_path: Path to audio file
        ranker: Optional pre-configured ranker instance
        
    Returns:
        Events with 'ranked_label' added (e.g., crash_1, tom_high_2)
    """
    if ranker is None:
        ranker = InstrumentPitchRanker()
    
    # Load audio
    audio, sr = librosa.load(audio_path, sr=22050, mono=True)
    
    # Process
    return ranker.process_song(beatmap_events, audio, sr)


# Alias for backward compatibility
rank_cymbals_in_beatmap = rank_instruments_in_beatmap


def get_unique_instruments(events: List[Dict]) -> Dict[str, int]:
    """
    Get count of unique instruments detected after ranking.
    
    Args:
        events: Events with 'ranked_label' field
        
    Returns:
        Dict mapping ranked_label to count
    """
    counts = defaultdict(int)
    for event in events:
        label = event.get("ranked_label", event.get("label", "unknown"))
        counts[label] += 1
    return dict(counts)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Test instrument pitch ranking")
    parser.add_argument("--audio", required=True, help="Path to audio file")
    parser.add_argument("--events", required=True, help="Path to events JSON")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()
    
    # Load events
    with open(args.events) as f:
        events = json.load(f)
    
    # Process
    ranker = InstrumentPitchRanker()
    audio, sr = librosa.load(args.audio, sr=22050, mono=True)
    results = ranker.process_song(events, audio, sr, return_features=True)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=lambda x: x.tolist() if isinstance(x, np.ndarray) else x)
        print(f"Saved to {args.output}")
    else:
        # Print summary
        unique = get_unique_instruments(results)
        print("Unique instruments detected:")
        for label, count in sorted(unique.items()):
            print(f"  {label}: {count} hits")
