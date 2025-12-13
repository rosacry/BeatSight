#!/usr/bin/env python3
"""
Cymbal Choke Detector - Post-Processing Module

Detects cymbal chokes by analyzing abrupt sustain cutoffs after cymbal events.
A choke occurs when a drummer grabs a ringing cymbal to stop its sustain.

The classifier doesn't detect chokes directly - they're not a sound but an
absence of sound. This module analyzes the audio envelope after each cymbal
hit to detect when sustain is unnaturally cut short.

=== DETECTION ALGORITHM ===
1. For each cymbal event (crash, china, splash, ride_bow, ride_bell):
   - Extract audio segment starting at the hit
   - Compute the RMS envelope
   - Analyze the decay profile
   - If decay drops faster than natural cymbal decay AND
     drops below threshold within choke window → CHOKE DETECTED

2. Choke characteristics:
   - Natural cymbal decay: exponential, gradual (1-5+ seconds)
   - Choked decay: sharp cutoff (50-200ms after initial attack)
   - The cutoff is abrupt, not gradual

=== USAGE ===
    from cymbal_choke_detector import CymbalChokeDetector
    
    detector = CymbalChokeDetector()
    events_with_chokes = detector.process_song(events, audio, sr)
    
    # Each cymbal event will have 'choked': True/False added

=== INTEGRATION ===
Call this AFTER the main classifier, BEFORE pitch ranking:
1. Run classifier → get events with labels
2. Run choke detector → add 'choked' flag to cymbal events  
3. Run pitch ranker → assign crash_1, crash_2, etc.
"""

import numpy as np
import librosa
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum

logger = logging.getLogger(__name__)


# Cymbal types that can be choked
CHOKEABLE_CYMBALS: Set[str] = {
    "crash",
    "china", 
    "splash",
    "ride_bow",
    "ride_bell",
    # Also check ranked versions
    "crash_1", "crash_2", "crash_3", "crash_4",
    "china_1", "china_2",
    "splash_1", "splash_2",
    "ride_bow_1", "ride_bow_2",
    "ride_bell_1", "ride_bell_2",
}


@dataclass
class ChokeConfig:
    """Configuration for choke detection parameters."""
    
    # Analysis window
    analysis_duration: float = 2.0  # Seconds of audio to analyze after hit
    
    # Choke timing constraints
    min_choke_delay: float = 0.05   # Minimum time after hit for choke (50ms)
    max_choke_delay: float = 1.5    # Maximum time after hit for choke (1.5s)
    
    # Decay analysis
    natural_decay_threshold: float = 0.3  # Expected decay ratio at 500ms for natural
    choke_decay_threshold: float = 0.1    # Decay ratio threshold indicating choke
    
    # Abruptness detection
    abruptness_window: float = 0.05  # Window to measure decay rate (50ms)
    abruptness_threshold: float = 0.7  # Ratio drop in abruptness window = choke
    
    # Envelope analysis
    envelope_hop: int = 512  # Hop size for envelope computation
    envelope_smoothing: float = 0.02  # Smoothing window in seconds
    
    # Confidence thresholds
    min_confidence: float = 0.6  # Minimum confidence to report a choke


@dataclass
class ChokeAnalysis:
    """Results from analyzing a potential cymbal choke."""
    
    timestamp: float  # Time of original cymbal hit
    label: str  # Cymbal type
    is_choked: bool = False
    choke_time: Optional[float] = None  # Time when choke occurred
    confidence: float = 0.0
    decay_profile: Optional[np.ndarray] = None
    analysis_notes: List[str] = field(default_factory=list)


class CymbalChokeDetector:
    """
    Post-processor that detects cymbal chokes by analyzing sustain cutoffs.
    
    A cymbal choke is when a drummer grabs a cymbal after hitting it to
    immediately stop its ring. This creates an abrupt decay that's very
    different from natural cymbal sustain.
    """
    
    def __init__(self, config: Optional[ChokeConfig] = None):
        """
        Initialize the choke detector.
        
        Args:
            config: Detection configuration, or None for defaults
        """
        self.config = config or ChokeConfig()
    
    def process_song(
        self,
        events: List[Dict],
        audio: np.ndarray,
        sr: int,
        return_analysis: bool = False,
    ) -> List[Dict]:
        """
        Process all events in a song, detecting chokes on cymbal hits.
        
        Args:
            events: List of detection events with 'timestamp' and 'label'
            audio: Full song audio as numpy array
            sr: Sample rate
            return_analysis: If True, include detailed analysis in output
            
        Returns:
            List of events with 'choked' boolean added to cymbal events
        """
        results = []
        
        # Sort events by timestamp for proper analysis
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", e.get("time", 0)))
        
        # Get timestamps of all events for inter-event analysis
        all_timestamps = [e.get("timestamp", e.get("time", 0)) for e in sorted_events]
        
        for i, event in enumerate(sorted_events):
            timestamp = event.get("timestamp", event.get("time", 0))
            label = event.get("label", event.get("class", ""))
            ranked_label = event.get("ranked_label", label)
            
            # Copy event
            result = dict(event)
            
            # Check if this is a chokeable cymbal
            if label in CHOKEABLE_CYMBALS or ranked_label in CHOKEABLE_CYMBALS:
                # Find next event time (constrains analysis window)
                next_event_time = None
                for j in range(i + 1, len(sorted_events)):
                    next_ts = all_timestamps[j]
                    if next_ts > timestamp + self.config.min_choke_delay:
                        next_event_time = next_ts
                        break
                
                # Analyze for choke
                analysis = self._analyze_choke(
                    audio=audio,
                    sr=sr,
                    timestamp=timestamp,
                    label=label,
                    next_event_time=next_event_time,
                )
                
                result["choked"] = analysis.is_choked
                if analysis.is_choked:
                    result["choke_time"] = analysis.choke_time
                    result["choke_confidence"] = analysis.confidence
                    
                if return_analysis:
                    result["choke_analysis"] = {
                        "confidence": analysis.confidence,
                        "choke_time": analysis.choke_time,
                        "notes": analysis.analysis_notes,
                    }
            else:
                result["choked"] = False
            
            results.append(result)
        
        return results
    
    def _analyze_choke(
        self,
        audio: np.ndarray,
        sr: int,
        timestamp: float,
        label: str,
        next_event_time: Optional[float] = None,
    ) -> ChokeAnalysis:
        """
        Analyze a single cymbal hit for choke detection.
        
        Args:
            audio: Full song audio
            sr: Sample rate
            timestamp: Time of cymbal hit
            label: Cymbal type
            next_event_time: Time of next drum event (optional)
            
        Returns:
            ChokeAnalysis with detection results
        """
        analysis = ChokeAnalysis(timestamp=timestamp, label=label)
        
        # Calculate analysis window
        analysis_duration = self.config.analysis_duration
        if next_event_time is not None:
            # Don't analyze past the next event
            max_duration = next_event_time - timestamp - 0.01
            analysis_duration = min(analysis_duration, max(0.2, max_duration))
        
        # Extract audio segment
        start_sample = int(timestamp * sr)
        end_sample = int((timestamp + analysis_duration) * sr)
        
        if start_sample < 0:
            start_sample = 0
        if end_sample > len(audio):
            end_sample = len(audio)
        
        if end_sample - start_sample < sr * 0.1:  # Need at least 100ms
            analysis.analysis_notes.append("Segment too short for analysis")
            return analysis
        
        segment = audio[start_sample:end_sample]
        
        # Compute RMS envelope
        envelope = self._compute_envelope(segment, sr)
        analysis.decay_profile = envelope
        
        if len(envelope) < 10:
            analysis.analysis_notes.append("Envelope too short")
            return analysis
        
        # Find peak (should be near start for a cymbal hit)
        peak_idx = np.argmax(envelope[:len(envelope)//4]) if len(envelope) > 4 else 0
        peak_val = envelope[peak_idx]
        
        if peak_val < 1e-6:
            analysis.analysis_notes.append("No significant energy detected")
            return analysis
        
        # Analyze decay from peak
        decay_portion = envelope[peak_idx:]
        normalized_decay = decay_portion / peak_val
        
        # Convert indices to time
        time_per_sample = self.config.envelope_hop / sr
        
        # Look for abrupt cutoff
        choke_detected = False
        choke_idx = None
        confidence = 0.0
        
        # Method 1: Look for sudden drop
        abruptness_samples = int(self.config.abruptness_window / time_per_sample)
        abruptness_samples = max(2, abruptness_samples)
        
        for i in range(abruptness_samples, len(normalized_decay) - 1):
            current_time = i * time_per_sample
            
            # Skip if outside choke window
            if current_time < self.config.min_choke_delay:
                continue
            if current_time > self.config.max_choke_delay:
                break
            
            # Check for abrupt drop
            prev_val = normalized_decay[i - abruptness_samples]
            curr_val = normalized_decay[i]
            
            if prev_val > 0.1:  # Only check if signal is still significant
                drop_ratio = curr_val / prev_val
                
                if drop_ratio < (1 - self.config.abruptness_threshold):
                    # Abrupt drop detected
                    choke_detected = True
                    choke_idx = i
                    
                    # Confidence based on how abrupt the drop is
                    confidence = min(1.0, (1 - drop_ratio) / self.config.abruptness_threshold)
                    analysis.analysis_notes.append(
                        f"Abrupt drop at {current_time:.3f}s: {drop_ratio:.2f} ratio"
                    )
                    break
        
        # Method 2: Compare to expected natural decay
        if not choke_detected:
            # Check decay at 500ms
            check_time = 0.5
            check_idx = int(check_time / time_per_sample)
            
            if check_idx < len(normalized_decay):
                decay_at_500ms = normalized_decay[check_idx]
                
                # Natural cymbals typically have >30% energy at 500ms
                # Choked cymbals have <10%
                if decay_at_500ms < self.config.choke_decay_threshold:
                    # Verify it's not just a quiet hit by checking earlier decay
                    check_early_idx = int(0.2 / time_per_sample)
                    if check_early_idx < len(normalized_decay):
                        decay_at_200ms = normalized_decay[check_early_idx]
                        
                        if decay_at_200ms > 0.3:  # Had energy at 200ms
                            choke_detected = True
                            choke_idx = check_idx
                            confidence = 0.7 * (1 - decay_at_500ms / self.config.natural_decay_threshold)
                            analysis.analysis_notes.append(
                                f"Unnaturally fast decay: {decay_at_500ms:.2%} at 500ms"
                            )
        
        if choke_detected and confidence >= self.config.min_confidence:
            analysis.is_choked = True
            analysis.choke_time = timestamp + (choke_idx * time_per_sample if choke_idx else 0.3)
            analysis.confidence = confidence
        else:
            analysis.analysis_notes.append("Natural decay detected")
        
        return analysis
    
    def _compute_envelope(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """Compute smoothed RMS envelope of audio segment."""
        hop = self.config.envelope_hop
        
        # Compute RMS
        rms = librosa.feature.rms(y=audio, hop_length=hop)[0]
        
        # Smooth the envelope
        smooth_samples = int(self.config.envelope_smoothing * sr / hop)
        if smooth_samples > 1 and len(rms) > smooth_samples:
            kernel = np.ones(smooth_samples) / smooth_samples
            rms = np.convolve(rms, kernel, mode='same')
        
        return rms


def detect_chokes_in_beatmap(
    events: List[Dict],
    audio_path: str,
    sr: int = 44100,
) -> List[Dict]:
    """
    Convenience function to detect chokes in a beatmap.
    
    Args:
        events: List of drum events with 'timestamp' and 'label'
        audio_path: Path to audio file
        sr: Target sample rate
        
    Returns:
        Events with 'choked' flag added to cymbal hits
    """
    # Load audio
    audio, _ = librosa.load(audio_path, sr=sr, mono=True)
    
    # Detect chokes
    detector = CymbalChokeDetector()
    return detector.process_song(events, audio, sr)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Detect cymbal chokes in a beatmap")
    parser.add_argument("events_json", help="Path to events JSON file")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("--output", "-o", help="Output JSON file (default: stdout)")
    parser.add_argument("--sr", type=int, default=44100, help="Sample rate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Include analysis details")
    
    args = parser.parse_args()
    
    # Load events
    with open(args.events_json, "r") as f:
        events = json.load(f)
    
    # Load audio
    print(f"Loading audio: {args.audio_path}")
    audio, sr = librosa.load(args.audio_path, sr=args.sr, mono=True)
    
    # Process
    print(f"Analyzing {len(events)} events...")
    detector = CymbalChokeDetector()
    results = detector.process_song(events, audio, sr, return_analysis=args.verbose)
    
    # Count chokes
    choke_count = sum(1 for e in results if e.get("choked", False))
    cymbal_count = sum(1 for e in results if e.get("label", "") in CHOKEABLE_CYMBALS)
    
    print(f"Found {choke_count} chokes out of {cymbal_count} cymbal hits")
    
    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Saved to {args.output}")
    else:
        # Print choked events
        for event in results:
            if event.get("choked", False):
                print(f"  CHOKE: {event['label']} at {event['timestamp']:.3f}s "
                      f"(choked at {event.get('choke_time', 0):.3f}s, "
                      f"confidence: {event.get('choke_confidence', 0):.2f})")
