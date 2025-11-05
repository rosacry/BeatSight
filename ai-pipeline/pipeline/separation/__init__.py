"""Compatibility layer exposing separation modules within the pipeline package."""

from separation.demucs_separator import DrumSeparator, separate_drums  # noqa: F401

__all__ = ["DrumSeparator", "separate_drums"]
