"""
Drum transcription and classification module

This package provides:
- Onset detection (onset_detector.py)
- Drum classification (ml_drum_classifier.py, ml_drum_classifier_v2.py)
- Instrument pitch ranking (instrument_pitch_ranker.py)
- Pattern detection (pattern_detector.py)
- Ensemble inference (ensemble.py)
"""

# Pattern detection - post-processing for musical patterns
from transcription.pattern_detector import (
    PatternDetector,
    PatternDetectorConfig,
    PatternType,
    PatternCategory,
    DrumEvent,
    DetectedPattern,
    CrashBuildDetector,
    AccentTapDetector,
    HiHatBarkDetector,
    HiHatSplashDetector,
    CrescendoDecrescendoDetector,
    detect_all_patterns,
    events_from_labels,
    patterns_to_json,
    annotate_transcription_result,
)

__all__ = [
    # Pattern detection
    "PatternDetector",
    "PatternDetectorConfig",
    "PatternType",
    "PatternCategory",
    "DrumEvent",
    "DetectedPattern",
    "CrashBuildDetector",
    "AccentTapDetector",
    "HiHatBarkDetector",
    "HiHatSplashDetector",
    "CrescendoDecrescendoDetector",
    "detect_all_patterns",
    "events_from_labels",
    "patterns_to_json",
    "annotate_transcription_result",
]
