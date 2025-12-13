"""
Drum transcription and classification module

This package provides:
- Onset detection (onset_detector.py)
- Drum classification (ml_drum_classifier.py, ml_drum_classifier_v2.py)
- Instrument pitch ranking (instrument_pitch_ranker.py)
- Cymbal choke detection (cymbal_choke_detector.py)
- Post-processing pipeline (postprocessing.py)
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

# Instrument pitch ranking - distinguishes multiple cymbals/toms
from transcription.instrument_pitch_ranker import (
    InstrumentPitchRanker,
    InstrumentConfig,
    RankingStrategy,
    DetectedEvent,
    rank_instruments_in_beatmap,
    rank_cymbals_in_beatmap,  # Backward compatibility alias
    get_unique_instruments,
)

# Cymbal choke detection - finds muted cymbals
from transcription.cymbal_choke_detector import (
    CymbalChokeDetector,
    ChokeConfig,
    ChokeAnalysis,
    detect_chokes_in_beatmap,
    CHOKEABLE_CYMBALS,
)

# Full post-processing pipeline
from transcription.postprocessing import (
    DrumPostProcessor,
    PostProcessingConfig,
    postprocess_beatmap,
    get_instrument_summary,
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
    # Pitch ranking
    "InstrumentPitchRanker",
    "InstrumentConfig",
    "RankingStrategy",
    "DetectedEvent",
    "rank_instruments_in_beatmap",
    "rank_cymbals_in_beatmap",
    "get_unique_instruments",
    # Choke detection
    "CymbalChokeDetector",
    "ChokeConfig",
    "ChokeAnalysis",
    "detect_chokes_in_beatmap",
    "CHOKEABLE_CYMBALS",
    # Post-processing pipeline
    "DrumPostProcessor",
    "PostProcessingConfig",
    "postprocess_beatmap",
    "get_instrument_summary",
]
