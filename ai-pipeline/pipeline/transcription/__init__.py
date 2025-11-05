"""Compatibility layer exposing transcription modules within the pipeline package."""

from transcription.drum_classifier import classify_drums  # noqa: F401
from transcription.onset_detector import detect_onsets  # noqa: F401
from transcription.ml_drum_classifier import DrumClassifierModel  # noqa: F401

__all__ = [
    "classify_drums",
    "detect_onsets",
    "DrumClassifierModel",
]
