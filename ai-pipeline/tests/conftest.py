"""Test configuration for ai-pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Ensure the ai-pipeline package is available without relying on PYTHONPATH tweaks.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import shared test utilities for use as fixtures
from tests.test_utils import (
    MockAudioData,
    MockDataset,
    MockProgressCallback,
    create_mock_dataloader,
    create_synthetic_mel_spectrogram,
)


@pytest.fixture
def mock_audio():
    """Provide MockAudioData factory."""
    return MockAudioData


@pytest.fixture
def mock_dataset():
    """Provide pre-configured MockDataset."""
    return MockDataset(size=32, input_shape=(1, 128, 128), num_classes=24)


@pytest.fixture
def mock_dataloader():
    """Provide pre-configured mock dataloader."""
    return create_mock_dataloader(batch_size=8, dataset_size=32)


@pytest.fixture
def progress_callback():
    """Provide MockProgressCallback for tracking progress updates."""
    return MockProgressCallback()


@pytest.fixture
def synthetic_mel():
    """Provide synthetic mel spectrogram tensor."""
    return create_synthetic_mel_spectrogram(n_mels=128, n_frames=128, batch_size=4)
