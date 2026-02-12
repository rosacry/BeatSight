#!/usr/bin/env python3
"""
Full Drum Transcription Pipeline

This module chains together all components of the drum transcription pipeline:
1. Onset Detection - Find drum hit times
2. Multi-Label Classification - Identify which instruments hit at each onset  
3. Count Estimation - Detect multiple simultaneous same-class hits (e.g., 2 crashes)
4. Pitch Ranking - Assign specific labels (crash_1, crash_2, tom_1, tom_2, etc.)

The final output is a list of DrumEvents with timestamps and specific labels.

Usage:
    from transcription.full_pipeline import DrumTranscriptionPipeline

    pipeline = DrumTranscriptionPipeline(
        multilabel_model_path="runs/v5_multilabel/best_model.pt",
        thresholds_path="runs/v5_multilabel/thresholds.json",
    )

    events = pipeline.transcribe("path/to/song.wav")
    # Returns: [
    #     DrumEvent(time=0.5, label="kick", confidence=0.95),
    #     DrumEvent(time=0.5, label="hihat_closed", confidence=0.82),
    #     DrumEvent(time=1.0, label="snare", confidence=0.91),
    #     DrumEvent(time=1.0, label="crash_1", confidence=0.78),
    #     DrumEvent(time=1.0, label="crash_2", confidence=0.78),
    #     ...
    # ]

Pipeline Flow:
    Audio → Onset Detection → Multi-Label Classification → Count Estimation → Pitch Ranking → Final Events
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

logger = logging.getLogger(__name__)


@dataclass
class DrumEvent:
    """A single drum event in the transcription."""
    
    time: float  # Time in seconds
    label: str  # Final label (e.g., "crash_1", "kick", "tom_2")
    confidence: float = 1.0  # Detection confidence
    
    # Original/intermediate labels
    base_label: Optional[str] = None  # Base class from classifier (e.g., "crash")
    ranked_label: Optional[str] = None  # After pitch ranking
    
    # Additional metadata
    count_at_onset: int = 1  # How many of this class at this onset
    onset_index: int = 0  # Index of the onset in the original detection
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "label": self.label,
            "confidence": self.confidence,
            "base_label": self.base_label,
            "count_at_onset": self.count_at_onset,
        }


@dataclass 
class TranscriptionResult:
    """Complete transcription result with metadata."""
    
    events: List[DrumEvent]
    audio_duration: float = 0.0
    sample_rate: int = 44100
    num_onsets: int = 0
    num_events: int = 0
    processing_time: float = 0.0
    
    # Statistics
    class_counts: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [e.to_dict() for e in self.events],
            "metadata": {
                "audio_duration": self.audio_duration,
                "sample_rate": self.sample_rate,
                "num_onsets": self.num_onsets,
                "num_events": self.num_events,
                "processing_time": self.processing_time,
            },
            "class_counts": self.class_counts,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class PipelineConfig:
    """Configuration for the transcription pipeline."""
    
    # Multi-label classifier settings
    threshold: float = 0.5
    per_class_thresholds: Optional[Dict[str, float]] = None
    
    # Onset detection settings
    onset_window_ms: float = 100.0
    onset_min_confidence: float = 0.1
    
    # Count estimation settings
    enable_count_estimation: bool = True
    count_max: int = 3
    
    # Pitch ranking settings
    enable_pitch_ranking: bool = True
    min_samples_for_ranking: int = 3
    
    # Processing settings
    batch_size: int = 64
    device: Optional[str] = None


class DrumTranscriptionPipeline:
    """
    Full drum transcription pipeline combining all components.
    
    This pipeline:
    1. Detects onsets in the audio
    2. Classifies each onset using multi-label model
    3. Estimates counts for simultaneous same-class hits
    4. Applies pitch ranking to distinguish between cymbals/toms
    5. Returns a list of DrumEvents with final labels
    """
    
    def __init__(
        self,
        multilabel_model_path: str,
        single_label_model_path: Optional[str] = None,
        thresholds_path: Optional[str] = None,
        config: Optional[PipelineConfig] = None,
    ):
        """
        Initialize the transcription pipeline.
        
        Args:
            multilabel_model_path: Path to trained multi-label model checkpoint
            single_label_model_path: Optional path to single-label model (for fallback)
            thresholds_path: Optional path to per-class thresholds JSON
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        
        # Load per-class thresholds if provided
        per_class_thresholds = self.config.per_class_thresholds or {}
        if thresholds_path and os.path.exists(thresholds_path):
            with open(thresholds_path) as f:
                data = json.load(f)
            if "per_class_thresholds" in data:
                per_class_thresholds.update(data["per_class_thresholds"])
            elif "thresholds" in data:
                per_class_thresholds.update(data["thresholds"])
            else:
                per_class_thresholds.update(data)
            logger.info(f"Loaded {len(per_class_thresholds)} thresholds from {thresholds_path}")
        
        # Initialize components
        self._init_classifier(
            multilabel_model_path, 
            per_class_thresholds,
        )
        self._init_count_estimator()
        self._init_pitch_ranker()
        
        logger.info("DrumTranscriptionPipeline initialized")
    
    def _init_classifier(
        self,
        model_path: str,
        per_class_thresholds: Dict[str, float],
    ):
        """Initialize the multi-label classifier."""
        try:
            from transcription.multilabel_inference import MultiLabelDrumClassifier
            
            self.classifier = MultiLabelDrumClassifier(
                model_path=model_path,
                threshold=self.config.threshold,
                per_class_thresholds=per_class_thresholds,
                device=self.config.device,
            )
            self.use_multilabel = True
            logger.info("Using multi-label classifier")
        except Exception as e:
            logger.error(f"Failed to load multi-label classifier: {e}")
            self.classifier = None
            self.use_multilabel = False
    
    def _init_count_estimator(self):
        """Initialize the count estimator."""
        if self.config.enable_count_estimation:
            try:
                from transcription.count_estimation import CountEstimator
                self.count_estimator = CountEstimator()
                logger.info("Count estimation enabled")
            except Exception as e:
                logger.warning(f"Count estimation not available: {e}")
                self.count_estimator = None
        else:
            self.count_estimator = None
    
    def _init_pitch_ranker(self):
        """Initialize the pitch ranker."""
        if self.config.enable_pitch_ranking:
            try:
                from transcription.instrument_pitch_ranker import InstrumentPitchRanker
                self.pitch_ranker = InstrumentPitchRanker()
                logger.info("Pitch ranking enabled")
            except Exception as e:
                logger.warning(f"Pitch ranking not available: {e}")
                self.pitch_ranker = None
        else:
            self.pitch_ranker = None
    
    def transcribe(
        self,
        audio_path: str,
        onset_times: Optional[List[float]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe drums from an audio file.
        
        Args:
            audio_path: Path to audio file
            onset_times: Optional pre-computed onset times (skips detection)
            
        Returns:
            TranscriptionResult with list of DrumEvents
        """
        import time
        start_time = time.time()
        
        if not HAS_LIBROSA:
            raise RuntimeError("librosa is required for transcription")
        
        # Load audio
        logger.info(f"Loading audio: {audio_path}")
        audio, sr = librosa.load(audio_path, sr=None, mono=False)
        
        # Handle stereo audio - keep for count estimation, but get mono for detection
        if audio.ndim > 1:
            audio_stereo = audio
            audio_mono = audio.mean(axis=0) if audio.shape[0] == 2 else audio.mean(axis=1)
        else:
            audio_stereo = audio
            audio_mono = audio
        
        duration = len(audio_mono) / sr
        
        # Step 1: Onset detection
        if onset_times is None:
            logger.info("Detecting onsets...")
            onset_times = self._detect_onsets(audio_mono, sr)
        
        logger.info(f"Processing {len(onset_times)} onsets")
        
        # Step 2: Multi-label classification
        logger.info("Classifying onsets...")
        onset_detections = self._classify_onsets(audio_mono, sr, onset_times)
        
        # Step 3: Count estimation + expand events
        logger.info("Estimating counts and expanding events...")
        expanded_events = self._expand_with_counts(
            onset_detections, onset_times, audio_stereo, sr
        )
        
        # Step 4: Pitch ranking
        if self.pitch_ranker and len(expanded_events) >= self.config.min_samples_for_ranking:
            logger.info("Applying pitch ranking...")
            final_events = self._apply_pitch_ranking(expanded_events, audio_mono, sr)
        else:
            # No ranking - use base labels with _1 suffix for rankable classes
            final_events = []
            for e in expanded_events:
                if e.base_label in ("crash", "china", "splash", "tom", "ride_bow", "ride_bell"):
                    e.label = f"{e.base_label}_1"
                else:
                    e.label = e.base_label or e.label
                final_events.append(e)
        
        # Sort by time
        final_events.sort(key=lambda e: e.time)
        
        # Compute statistics
        class_counts: Dict[str, int] = {}
        for event in final_events:
            class_counts[event.label] = class_counts.get(event.label, 0) + 1
        
        processing_time = time.time() - start_time
        
        result = TranscriptionResult(
            events=final_events,
            audio_duration=duration,
            sample_rate=sr,
            num_onsets=len(onset_times),
            num_events=len(final_events),
            processing_time=processing_time,
            class_counts=class_counts,
        )
        
        logger.info(
            f"Transcription complete: {len(final_events)} events "
            f"in {processing_time:.2f}s"
        )
        
        return result
    
    def transcribe_audio(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: Optional[List[float]] = None,
    ) -> TranscriptionResult:
        """
        Transcribe drums from audio array.
        
        Args:
            audio: Audio array (mono or stereo)
            sr: Sample rate
            onset_times: Optional pre-computed onset times
            
        Returns:
            TranscriptionResult with list of DrumEvents
        """
        import time
        start_time = time.time()
        
        # Handle stereo
        if audio.ndim > 1:
            audio_stereo = audio
            audio_mono = audio.mean(axis=0) if audio.shape[0] == 2 else audio.mean(axis=1)
        else:
            audio_stereo = audio
            audio_mono = audio
        
        duration = len(audio_mono) / sr
        
        # Step 1: Onset detection
        if onset_times is None:
            onset_times = self._detect_onsets(audio_mono, sr)
        
        # Step 2: Classification
        onset_detections = self._classify_onsets(audio_mono, sr, onset_times)
        
        # Step 3: Count estimation
        expanded_events = self._expand_with_counts(
            onset_detections, onset_times, audio_stereo, sr
        )
        
        # Step 4: Pitch ranking
        if self.pitch_ranker and len(expanded_events) >= self.config.min_samples_for_ranking:
            final_events = self._apply_pitch_ranking(expanded_events, audio_mono, sr)
        else:
            for e in expanded_events:
                if e.base_label in ("crash", "china", "splash", "tom", "ride_bow", "ride_bell"):
                    e.label = f"{e.base_label}_1"
                else:
                    e.label = e.base_label or e.label
            final_events = expanded_events
        
        final_events.sort(key=lambda e: e.time)
        
        # Statistics
        class_counts = {}
        for event in final_events:
            class_counts[event.label] = class_counts.get(event.label, 0) + 1
        
        return TranscriptionResult(
            events=final_events,
            audio_duration=duration,
            sample_rate=sr,
            num_onsets=len(onset_times),
            num_events=len(final_events),
            processing_time=time.time() - start_time,
            class_counts=class_counts,
        )
    
    def _detect_onsets(
        self,
        audio: np.ndarray,
        sr: int,
    ) -> List[float]:
        """Detect drum onset times in the audio."""
        try:
            from transcription.onset_detector import detect_onsets
            
            # detect_onsets expects tuple (audio, sr)
            result = detect_onsets((audio, sr))
            return [
                onset.time for onset in result.onsets
                if onset.confidence >= self.config.onset_min_confidence
            ]
        except ImportError:
            # Fallback to librosa onset detection
            logger.warning("Using fallback onset detection")
            onset_frames = librosa.onset.onset_detect(y=audio, sr=sr)
            return librosa.frames_to_time(onset_frames, sr=sr).tolist()
    
    def _classify_onsets(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
    ) -> List[Dict[str, float]]:
        """
        Classify each onset using multi-label model.
        
        Returns:
            List of dicts, each mapping class -> confidence for detected classes
        """
        if self.classifier is None:
            # No classifier - return empty detections
            return [{} for _ in onset_times]
        
        return self.classifier.classify_batch(
            audio, sr, onset_times, 
            window_ms=self.config.onset_window_ms
        )
    
    def _expand_with_counts(
        self,
        onset_detections: List[Dict[str, float]],
        onset_times: List[float],
        audio: np.ndarray,
        sr: int,
    ) -> List[DrumEvent]:
        """
        Expand detections by estimating counts for each class.
        
        If count estimation detects 2 crashes at an onset, this creates
        2 DrumEvent entries with the same time.
        """
        events: List[DrumEvent] = []
        
        for i, (time, detections) in enumerate(zip(onset_times, onset_detections)):
            if not detections:
                continue
            
            # Extract audio segment for count estimation
            window_samples = int(self.config.onset_window_ms * sr / 1000)
            center = int(time * sr)
            start = max(0, center - window_samples // 4)
            end = min(audio.shape[-1], start + window_samples)
            
            if audio.ndim > 1:
                segment = audio[:, start:end] if audio.shape[0] == 2 else audio[start:end, :].T
            else:
                segment = audio[start:end]
            
            for class_name, confidence in detections.items():
                # Estimate count
                if self.count_estimator:
                    count = self.count_estimator.estimate_count(segment, sr, class_name)
                else:
                    count = 1
                
                # Create event(s)
                for _ in range(count):
                    events.append(DrumEvent(
                        time=time,
                        label=class_name,  # Will be updated by pitch ranking
                        confidence=confidence,
                        base_label=class_name,
                        count_at_onset=count,
                        onset_index=i,
                    ))
        
        return events
    
    def _apply_pitch_ranking(
        self,
        events: List[DrumEvent],
        audio: np.ndarray,
        sr: int,
    ) -> List[DrumEvent]:
        """
        Apply pitch ranking to events.
        
        Converts base labels (crash, tom) to ranked labels (crash_1, crash_2, tom_1, etc.)
        """
        if not events:
            return events
        
        # Convert to format expected by pitch ranker
        event_dicts = [
            {
                "timestamp": e.time,
                "label": e.base_label,
                "confidence": e.confidence,
            }
            for e in events
        ]
        
        # Run pitch ranking
        ranked_dicts = self.pitch_ranker.process_song(event_dicts, audio, sr)
        
        # Update events with ranked labels
        for event, ranked in zip(events, ranked_dicts):
            event.ranked_label = ranked.get("ranked_label", event.base_label)
            event.label = event.ranked_label or event.base_label
        
        return events


def transcribe_audio_file(
    audio_path: str,
    multilabel_model_path: str,
    thresholds_path: Optional[str] = None,
    output_path: Optional[str] = None,
    config: Optional[PipelineConfig] = None,
) -> TranscriptionResult:
    """
    Convenience function to transcribe a single audio file.
    
    Args:
        audio_path: Path to audio file
        multilabel_model_path: Path to model checkpoint
        thresholds_path: Path to thresholds JSON
        output_path: Optional path to save results JSON
        config: Pipeline configuration
        
    Returns:
        TranscriptionResult
    """
    pipeline = DrumTranscriptionPipeline(
        multilabel_model_path=multilabel_model_path,
        thresholds_path=thresholds_path,
        config=config,
    )
    
    result = pipeline.transcribe(audio_path)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result.to_json())
        logger.info(f"Saved results to {output_path}")
    
    return result


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Full drum transcription pipeline"
    )
    parser.add_argument(
        "--audio",
        type=str,
        required=True,
        help="Path to audio file",
    )
    parser.add_argument(
        "--multilabel-model",
        type=str,
        required=True,
        help="Path to multi-label model checkpoint",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Path to per-class thresholds JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for transcription JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Global classification threshold",
    )
    parser.add_argument(
        "--no-count-estimation",
        action="store_true",
        help="Disable count estimation",
    )
    parser.add_argument(
        "--no-pitch-ranking",
        action="store_true",
        help="Disable pitch ranking",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    # Validate paths
    if not os.path.exists(args.audio):
        print(f"ERROR: Audio file not found: {args.audio}")
        sys.exit(1)
    if not os.path.exists(args.multilabel_model):
        print(f"ERROR: Model not found: {args.multilabel_model}")
        sys.exit(1)
    
    # Configure pipeline
    config = PipelineConfig(
        threshold=args.threshold,
        enable_count_estimation=not args.no_count_estimation,
        enable_pitch_ranking=not args.no_pitch_ranking,
    )
    
    # Run transcription
    print(f"Transcribing: {args.audio}")
    result = transcribe_audio_file(
        audio_path=args.audio,
        multilabel_model_path=args.multilabel_model,
        thresholds_path=args.thresholds,
        output_path=args.output,
        config=config,
    )
    
    # Print summary
    print(f"\n=== TRANSCRIPTION RESULTS ===")
    print(f"Audio duration: {result.audio_duration:.2f}s")
    print(f"Onsets detected: {result.num_onsets}")
    print(f"Events transcribed: {result.num_events}")
    print(f"Processing time: {result.processing_time:.2f}s")
    print(f"\nClass counts:")
    for label, count in sorted(result.class_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")
    
    if args.verbose:
        print(f"\nFirst 20 events:")
        for event in result.events[:20]:
            print(f"  {event.time:.3f}s: {event.label} ({event.confidence:.2f})")
    
    if args.output:
        print(f"\nResults saved to: {args.output}")
