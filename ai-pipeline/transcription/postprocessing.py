#!/usr/bin/env python3
"""
Drum Transcription Post-Processing Pipeline

This module orchestrates all post-processing steps after the initial
drum classification. The classifier outputs generic labels like "crash",
"tom", "snare". Post-processing refines these into specific labels like
"crash_1", "crash_2", "tom_1", "tom_2" and detects cymbal chokes.

=== PIPELINE ORDER ===
1. CLASSIFIER → Generic labels (crash, tom, snare, hihat_open, etc.)
2. CHOKE DETECTOR → Adds 'choked' flag to cymbal events  
3. PITCH RANKER → Splits cymbals/toms into numbered variants

=== 13-CLASS MODEL OUTPUTS ===
After training with the consolidated class list:
- china         → pitch ranked to china_1, china_2
- crash         → pitch ranked to crash_1, crash_2, crash_3, crash_4
- cross_stick   → (no ranking, single type per kit)
- hihat_closed  → (no ranking, single hi-hat)
- hihat_open    → (no ranking, single hi-hat)
- hihat_pedal   → (no ranking, single hi-hat)  
- kick          → (no ranking, usually single kick or same-tuned double)
- ride_bell     → pitch ranked to ride_bell_1, ride_bell_2
- ride_bow      → pitch ranked to ride_bow_1, ride_bow_2
- rimshot       → (no ranking, always on snare)
- snare         → (no ranking, usually single snare)
- splash        → pitch ranked to splash_1, splash_2
- tom           → pitch ranked to tom_1, tom_2, tom_3, tom_4

=== USAGE ===
    from postprocessing import DrumPostProcessor
    
    processor = DrumPostProcessor()
    final_events = processor.process(classifier_events, audio, sr)

=== CLI ===
    python postprocessing.py --events events.json --audio song.wav -o output.json
"""

import numpy as np
import librosa
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

# Import our post-processors
from .cymbal_choke_detector import CymbalChokeDetector, ChokeConfig
from .instrument_pitch_ranker import InstrumentPitchRanker, InstrumentConfig

logger = logging.getLogger(__name__)


@dataclass
class PostProcessingConfig:
    """Configuration for the full post-processing pipeline."""
    
    # Choke detection
    enable_choke_detection: bool = True
    choke_config: Optional[ChokeConfig] = None
    
    # Pitch ranking
    enable_pitch_ranking: bool = True
    ranker_configs: Optional[Dict[str, InstrumentConfig]] = None
    
    # General
    sample_rate: int = 44100
    return_intermediate: bool = False  # Include intermediate results


class DrumPostProcessor:
    """
    Orchestrates all drum transcription post-processing.
    
    Combines:
    - Cymbal choke detection (adds 'choked' flag)
    - Instrument pitch ranking (crash → crash_1, tom → tom_1, etc.)
    """
    
    def __init__(self, config: Optional[PostProcessingConfig] = None):
        """
        Initialize the post-processor.
        
        Args:
            config: Pipeline configuration, or None for defaults
        """
        self.config = config or PostProcessingConfig()
        
        # Initialize sub-processors
        if self.config.enable_choke_detection:
            choke_config = self.config.choke_config or ChokeConfig()
            self.choke_detector = CymbalChokeDetector(config=choke_config)
        else:
            self.choke_detector = None
        
        if self.config.enable_pitch_ranking:
            self.pitch_ranker = InstrumentPitchRanker(
                configs=self.config.ranker_configs
            )
        else:
            self.pitch_ranker = None
    
    def process(
        self,
        events: List[Dict],
        audio: np.ndarray,
        sr: Optional[int] = None,
    ) -> List[Dict]:
        """
        Run the full post-processing pipeline.
        
        Args:
            events: Classifier output events with 'timestamp' and 'label'
            audio: Full song audio as numpy array
            sr: Sample rate (uses config default if None)
            
        Returns:
            Processed events with:
            - 'choked' flag on cymbal events
            - 'ranked_label' with pitch-based numbering
            - 'final_label' combining all information
        """
        sr = sr or self.config.sample_rate
        
        # Ensure audio is mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=0)
        
        results = list(events)  # Copy
        
        # Step 1: Detect chokes on cymbal events
        if self.choke_detector is not None:
            logger.info("Running choke detection...")
            results = self.choke_detector.process_song(results, audio, sr)
            choke_count = sum(1 for e in results if e.get("choked", False))
            logger.info(f"Found {choke_count} cymbal chokes")
        
        # Step 2: Rank instruments by pitch
        if self.pitch_ranker is not None:
            logger.info("Running pitch ranking...")
            results = self.pitch_ranker.process_song(results, audio, sr)
        
        # Step 3: Generate final labels
        for event in results:
            event["final_label"] = self._generate_final_label(event)
        
        return results
    
    def _generate_final_label(self, event: Dict) -> str:
        """
        Generate the final label combining all post-processing info.
        
        Format: {ranked_label}[_choked]
        
        Examples:
        - crash_1_choked (first crash, choked)
        - tom_2 (second tom by pitch)
        - snare (no ranking needed)
        """
        # Start with ranked label if available, else original
        label = event.get("ranked_label", event.get("label", "unknown"))
        
        # Add choke suffix if applicable
        if event.get("choked", False):
            label = f"{label}_choked"
        
        return label
    
    def process_file(
        self,
        events: List[Dict],
        audio_path: str,
    ) -> List[Dict]:
        """
        Convenience method to process events with audio from file.
        
        Args:
            events: Classifier output events
            audio_path: Path to audio file
            
        Returns:
            Processed events
        """
        logger.info(f"Loading audio: {audio_path}")
        audio, sr = librosa.load(audio_path, sr=self.config.sample_rate, mono=True)
        return self.process(events, audio, sr)


def postprocess_beatmap(
    events: List[Dict],
    audio_path: str,
    enable_chokes: bool = True,
    enable_ranking: bool = True,
    sample_rate: int = 44100,
) -> List[Dict]:
    """
    High-level convenience function for post-processing a beatmap.
    
    Args:
        events: Raw classifier events
        audio_path: Path to audio file
        enable_chokes: Whether to detect cymbal chokes
        enable_ranking: Whether to rank instruments by pitch
        sample_rate: Audio sample rate
        
    Returns:
        Fully processed events ready for beatmap export
    """
    config = PostProcessingConfig(
        enable_choke_detection=enable_chokes,
        enable_pitch_ranking=enable_ranking,
        sample_rate=sample_rate,
    )
    
    processor = DrumPostProcessor(config)
    return processor.process_file(events, audio_path)


def get_instrument_summary(events: List[Dict]) -> Dict[str, int]:
    """
    Get a summary of unique instruments after post-processing.
    
    Args:
        events: Post-processed events with 'final_label'
        
    Returns:
        Dict mapping label to hit count
    """
    from collections import Counter
    
    labels = [e.get("final_label", e.get("label", "unknown")) for e in events]
    return dict(Counter(labels))


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    import json
    
    parser = argparse.ArgumentParser(
        description="Post-process drum transcription events"
    )
    parser.add_argument("--events", "-e", required=True, 
                        help="Path to events JSON file")
    parser.add_argument("--audio", "-a", required=True,
                        help="Path to audio file")
    parser.add_argument("--output", "-o",
                        help="Output JSON file (default: stdout)")
    parser.add_argument("--no-chokes", action="store_true",
                        help="Disable choke detection")
    parser.add_argument("--no-ranking", action="store_true",
                        help="Disable pitch ranking")
    parser.add_argument("--sr", type=int, default=44100,
                        help="Sample rate")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s"
    )
    
    # Load events
    print(f"Loading events: {args.events}")
    with open(args.events, "r") as f:
        events = json.load(f)
    print(f"  {len(events)} events")
    
    # Process
    results = postprocess_beatmap(
        events=events,
        audio_path=args.audio,
        enable_chokes=not args.no_chokes,
        enable_ranking=not args.no_ranking,
        sample_rate=args.sr,
    )
    
    # Summary
    summary = get_instrument_summary(results)
    print("\nInstrument Summary:")
    for label, count in sorted(summary.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")
    
    # Choke summary
    choke_count = sum(1 for e in results if e.get("choked", False))
    if choke_count > 0:
        print(f"\nCymbal chokes detected: {choke_count}")
    
    # Output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {args.output}")
