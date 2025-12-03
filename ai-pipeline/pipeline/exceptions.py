"""
BeatSight Pipeline Exceptions

Custom exception hierarchy for the AI pipeline.
Enables precise error handling and better logging/monitoring.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all pipeline errors."""

    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


class AudioDownloadError(PipelineError):
    """Failed to download audio from storage."""

    def __init__(self, message: str, url: str | None = None):
        super().__init__(message, recoverable=True)
        self.url = url


class AudioProcessingError(PipelineError):
    """Failed to process/separate audio."""

    def __init__(self, message: str, stage: str | None = None):
        super().__init__(message, recoverable=False)
        self.stage = stage


class TranscriptionError(PipelineError):
    """Failed to transcribe drum hits."""

    def __init__(self, message: str, onset_count: int | None = None):
        super().__init__(message, recoverable=False)
        self.onset_count = onset_count


class BeatmapGenerationError(PipelineError):
    """Failed to generate beatmap file."""

    def __init__(self, message: str):
        super().__init__(message, recoverable=False)


class ResultUploadError(PipelineError):
    """Failed to upload results to storage."""

    def __init__(self, message: str, uri: str | None = None):
        super().__init__(message, recoverable=True)
        self.uri = uri


class JobTimeoutError(PipelineError):
    """Job processing timed out."""

    def __init__(self, message: str, elapsed_seconds: float | None = None):
        super().__init__(message, recoverable=True)
        self.elapsed_seconds = elapsed_seconds


class ModelLoadError(PipelineError):
    """Failed to load ML model."""

    def __init__(self, message: str, model_path: str | None = None):
        super().__init__(message, recoverable=False)
        self.model_path = model_path
