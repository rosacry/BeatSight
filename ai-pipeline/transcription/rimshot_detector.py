#!/usr/bin/env python3
"""
Rimshot Detection Post-Processor

Detects rimshots (stick hits head + rim simultaneously) from snare events
based on acoustic analysis. Rimshots have:
- Sharper attack transient
- Higher amplitude
- More high-frequency content (the "crack" from the rim)
- Shorter decay in lower frequencies

This is applied AFTER the main classifier labels a hit as "snare",
adding a "rimshot" articulation flag similar to how choke detection works.

=== USAGE ===
    from rimshot_detector import RimshotDetector
    
    detector = RimshotDetector()
    events = detector.process_song(events, audio, sr)
    # Snare events now have 'articulation' field with 'rimshot', 'center', or 'ghost'

=== ACOUSTIC FEATURES ===
1. **Attack sharpness**: Rimshots have faster attack (< 5ms to peak vs 10-15ms)
2. **Spectral centroid**: Rimshots have higher centroid (3-6kHz vs 2-4kHz for center)
3. **Peak amplitude**: Rimshots are typically louder
4. **High-frequency ratio**: More energy above 4kHz due to rim "crack"
"""

import numpy as np
import librosa
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RimshotConfig:
    """Configuration for rimshot detection."""
    
    # Analysis window
    window_ms: float = 50.0  # Analysis window around hit
    attack_window_ms: float = 10.0  # Window for attack analysis
    
    # Thresholds (calibrated on typical drum recordings)
    attack_sharpness_threshold: float = 0.7  # 0-1, higher = sharper required
    spectral_centroid_threshold: float = 3500.0  # Hz, above this suggests rimshot
    hf_ratio_threshold: float = 0.25  # Ratio of energy above 4kHz
    amplitude_percentile: float = 70.0  # Hits above this percentile considered "loud"
    
    # Combination logic
    min_features_for_rimshot: int = 2  # How many features must indicate rimshot
    
    # Ghost note detection (very soft snare hits)
    ghost_note_percentile: float = 25.0  # Hits below this percentile
    
    # Debug
    return_features: bool = False  # Include computed features in output


class RimshotDetector:
    """
    Detects rimshot articulation on snare events.
    
    After the classifier labels an event as "snare", this detector
    analyzes the audio to determine if it's:
    - rimshot: Head + rim hit, loud crack
    - center: Normal snare hit in center of head
    - ghost: Very soft snare hit (dynamics, not articulation)
    """
    
    def __init__(self, config: Optional[RimshotConfig] = None):
        """
        Initialize the detector.
        
        Args:
            config: Detection configuration, or None for defaults
        """
        self.config = config or RimshotConfig()
    
    def process_song(
        self,
        events: List[Dict],
        audio: np.ndarray,
        sr: int,
    ) -> List[Dict]:
        """
        Process all events in a song, detecting rimshots on snare events.
        
        Args:
            events: List of classifier events with 'timestamp', 'label'
            audio: Song audio as numpy array (mono)
            sr: Sample rate
            
        Returns:
            Events with 'articulation' field added to snare events
        """
        if audio.ndim > 1:
            audio = np.mean(audio, axis=0)
        
        # Filter snare events
        snare_events = [e for e in events if self._is_snare_event(e)]
        
        if not snare_events:
            logger.debug("No snare events to process")
            return events
        
        logger.info(f"Analyzing {len(snare_events)} snare events for rimshots...")
        
        # Extract features for all snare events
        features = []
        for event in snare_events:
            feat = self._extract_features(event, audio, sr)
            features.append(feat)
        
        # Compute amplitude statistics for relative thresholding
        amplitudes = [f["peak_amplitude"] for f in features]
        if amplitudes:
            amplitude_p70 = np.percentile(amplitudes, self.config.amplitude_percentile)
            amplitude_p25 = np.percentile(amplitudes, self.config.ghost_note_percentile)
        else:
            amplitude_p70 = amplitude_p25 = 0
        
        # Classify each snare event
        rimshot_count = 0
        ghost_count = 0
        
        for event, feat in zip(snare_events, features):
            articulation, confidence = self._classify_articulation(
                feat, amplitude_p70, amplitude_p25
            )
            event["articulation"] = articulation
            event["articulation_confidence"] = confidence
            
            if self.config.return_features:
                event["rimshot_features"] = feat
            
            if articulation == "rimshot":
                rimshot_count += 1
            elif articulation == "ghost":
                ghost_count += 1
        
        logger.info(f"Detected {rimshot_count} rimshots, {ghost_count} ghost notes "
                    f"out of {len(snare_events)} snare events")
        
        return events
    
    def _is_snare_event(self, event: Dict) -> bool:
        """Check if event is a snare hit."""
        label = event.get("label", "").lower()
        return label in ["snare", "snare_center", "snare_rimshot"]
    
    def _extract_features(
        self,
        event: Dict,
        audio: np.ndarray,
        sr: int,
    ) -> Dict:
        """
        Extract acoustic features from a snare event.
        
        Returns dict with:
        - attack_sharpness: 0-1, how fast the attack is
        - spectral_centroid: Hz, center of spectral mass
        - hf_ratio: Ratio of energy above 4kHz
        - peak_amplitude: Maximum amplitude
        """
        timestamp = event.get("timestamp", 0)
        window_samples = int(self.config.window_ms * sr / 1000)
        attack_samples = int(self.config.attack_window_ms * sr / 1000)
        
        # Extract window around hit
        center_sample = int(timestamp * sr)
        start = max(0, center_sample - window_samples // 4)  # Slight offset before hit
        end = min(len(audio), start + window_samples)
        
        segment = audio[start:end]
        
        if len(segment) < 100:
            return {
                "attack_sharpness": 0.5,
                "spectral_centroid": 2500,
                "hf_ratio": 0.15,
                "peak_amplitude": 0.0,
            }
        
        # 1. Attack sharpness (time to peak)
        attack_segment = segment[:attack_samples]
        if len(attack_segment) > 0:
            peak_idx = np.argmax(np.abs(attack_segment))
            # Normalize: 0 = slow attack, 1 = instant peak
            attack_sharpness = 1.0 - (peak_idx / len(attack_segment))
        else:
            attack_sharpness = 0.5
        
        # 2. Spectral centroid
        try:
            centroid = librosa.feature.spectral_centroid(
                y=segment, sr=sr, n_fft=min(1024, len(segment))
            )
            spectral_centroid = float(np.mean(centroid))
        except Exception:
            spectral_centroid = 2500.0
        
        # 3. High-frequency ratio (energy above 4kHz / total)
        try:
            fft = np.abs(np.fft.rfft(segment))
            freqs = np.fft.rfftfreq(len(segment), 1/sr)
            hf_mask = freqs > 4000
            hf_energy = np.sum(fft[hf_mask] ** 2)
            total_energy = np.sum(fft ** 2) + 1e-10
            hf_ratio = hf_energy / total_energy
        except Exception:
            hf_ratio = 0.15
        
        # 4. Peak amplitude
        peak_amplitude = float(np.max(np.abs(segment)))
        
        return {
            "attack_sharpness": attack_sharpness,
            "spectral_centroid": spectral_centroid,
            "hf_ratio": hf_ratio,
            "peak_amplitude": peak_amplitude,
        }
    
    def _classify_articulation(
        self,
        features: Dict,
        amplitude_p70: float,
        amplitude_p25: float,
    ) -> Tuple[str, float]:
        """
        Classify snare articulation based on features.
        
        Returns:
            (articulation, confidence) where articulation is one of:
            - "rimshot": Head + rim hit
            - "center": Normal center hit
            - "ghost": Very soft hit
        """
        # Check for ghost note first (based on amplitude)
        if features["peak_amplitude"] < amplitude_p25:
            return "ghost", 0.8
        
        # Count rimshot indicators
        rimshot_indicators = 0
        confidence_sum = 0.0
        
        # Check attack sharpness
        if features["attack_sharpness"] > self.config.attack_sharpness_threshold:
            rimshot_indicators += 1
            confidence_sum += features["attack_sharpness"]
        
        # Check spectral centroid
        if features["spectral_centroid"] > self.config.spectral_centroid_threshold:
            rimshot_indicators += 1
            confidence_sum += min(1.0, features["spectral_centroid"] / 5000)
        
        # Check high-frequency ratio
        if features["hf_ratio"] > self.config.hf_ratio_threshold:
            rimshot_indicators += 1
            confidence_sum += min(1.0, features["hf_ratio"] / 0.4)
        
        # Check amplitude (rimshots are typically louder)
        if features["peak_amplitude"] > amplitude_p70:
            rimshot_indicators += 1
            confidence_sum += 0.7
        
        # Classify based on indicator count
        if rimshot_indicators >= self.config.min_features_for_rimshot:
            confidence = confidence_sum / max(rimshot_indicators, 1)
            return "rimshot", min(1.0, confidence)
        else:
            # Default to center hit
            return "center", 0.7


def detect_rimshots(
    events: List[Dict],
    audio_path: str,
    sample_rate: int = 44100,
) -> List[Dict]:
    """
    High-level function to detect rimshots in a transcription.
    
    Args:
        events: Raw classifier events
        audio_path: Path to audio file
        sample_rate: Target sample rate
        
    Returns:
        Events with 'articulation' field on snare events
    """
    audio, sr = librosa.load(audio_path, sr=sample_rate, mono=True)
    
    detector = RimshotDetector()
    return detector.process_song(events, audio, sr)


if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Detect rimshots in drum transcription")
    parser.add_argument("--events", required=True, help="Input events JSON file")
    parser.add_argument("--audio", required=True, help="Audio file path")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--debug", action="store_true", help="Include feature values")
    args = parser.parse_args()
    
    # Load events
    with open(args.events) as f:
        events = json.load(f)
    
    # Configure
    config = RimshotConfig(return_features=args.debug)
    detector = RimshotDetector(config=config)
    
    # Process
    audio, sr = librosa.load(args.audio, sr=44100, mono=True)
    result = detector.process_song(events, audio, sr)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Saved to {args.output}")
    else:
        # Print summary
        snare_events = [e for e in result if "articulation" in e]
        for art in ["rimshot", "center", "ghost"]:
            count = sum(1 for e in snare_events if e.get("articulation") == art)
            print(f"{art}: {count}")
