"""Shared test utilities for ai-pipeline tests.

This module provides common mock objects, fixtures, and helper functions
used across multiple test files to reduce duplication.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Optional

import numpy as np
import torch


class MockAudioData:
    """Mock audio data for testing audio processing functions."""

    def __init__(
        self,
        duration_seconds: float = 5.0,
        sample_rate: int = 44100,
        channels: int = 1,
    ):
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.num_samples = int(duration_seconds * sample_rate)

    def to_numpy(self) -> np.ndarray:
        """Generate random audio samples as numpy array."""
        if self.channels == 1:
            return np.random.randn(self.num_samples).astype(np.float32)
        return np.random.randn(self.channels, self.num_samples).astype(np.float32)

    def to_tensor(self) -> torch.Tensor:
        """Generate random audio samples as torch tensor."""
        return torch.from_numpy(self.to_numpy())


class MockLibrosaModule:
    """Mock librosa module for testing without librosa dependency.
    
    Usage:
        mock_librosa = MockLibrosaModule(version="0.10.1")
        monkeypatch.setattr(detector, "librosa", mock_librosa)
    """

    def __init__(self, version: str = "0.10.1"):
        self.__version__ = version

    def load(self, path: str, sr: Optional[int] = None, **kwargs):
        """Mock load function returning dummy audio."""
        sr = sr or 22050
        duration = kwargs.get("duration", 5.0)
        y = np.random.randn(int(sr * duration)).astype(np.float32)
        return y, sr

    @staticmethod
    def tempo(*args, **kwargs):
        """Mock tempo detection returning sensible BPM."""
        return np.array([120.0])

    @staticmethod
    def onset_detect(*args, **kwargs):
        """Mock onset detection returning sparse onsets."""
        return np.array([0.5, 1.0, 1.5, 2.0, 2.5])


class MockImportModule:
    """Factory for creating mock import_module functions.
    
    Usage:
        def test_something(monkeypatch):
            mock_import = MockImportModule()
            mock_import.register("librosa.feature.rhythm", {"tempo": lambda: 120})
            monkeypatch.setattr(module, "import_module", mock_import)
    """

    def __init__(self):
        self._modules: dict[str, Any] = {}
        self._captured_imports: list[str] = []

    def register(self, module_name: str, attrs: dict[str, Any]):
        """Register a mock module with specified attributes."""
        mock = SimpleNamespace(**attrs)
        self._modules[module_name] = mock

    def __call__(self, name: str) -> Any:
        self._captured_imports.append(name)
        if name in self._modules:
            return self._modules[name]
        raise ImportError(f"No module named '{name}' (mock)")

    @property
    def captured_imports(self) -> list[str]:
        """Return list of import attempts in order."""
        return self._captured_imports


class MockDataset(torch.utils.data.Dataset):
    """Mock PyTorch dataset for testing training loops.
    
    Args:
        size: Number of samples in the dataset.
        input_shape: Shape of input tensors (e.g., (1, 128, 128) for mel specs).
        num_classes: Number of output classes for label generation.
    """

    def __init__(
        self,
        size: int = 32,
        input_shape: tuple[int, ...] = (1, 128, 128),
        num_classes: int = 24,
    ):
        self.size = size
        self.input_shape = input_shape
        self.num_classes = num_classes

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        x = torch.randn(*self.input_shape)
        y = idx % self.num_classes
        return x, y


def create_mock_dataloader(
    batch_size: int = 8,
    dataset_size: int = 32,
    input_shape: tuple[int, ...] = (1, 128, 128),
    num_classes: int = 24,
    shuffle: bool = True,
) -> torch.utils.data.DataLoader:
    """Create a mock dataloader for testing training loops.
    
    Returns:
        DataLoader with MockDataset.
    """
    dataset = MockDataset(
        size=dataset_size,
        input_shape=input_shape,
        num_classes=num_classes,
    )
    return torch.utils.data.DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
    )


class MockProgressCallback:
    """Mock progress callback that captures progress updates.
    
    Usage:
        progress = MockProgressCallback()
        some_function(progress_callback=progress)
        assert progress.calls[-1] >= 0.9
    """

    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, progress: float, message: Optional[str] = None):
        self.calls.append(progress)

    @property
    def final_progress(self) -> Optional[float]:
        """Return the last progress value, or None if no calls."""
        return self.calls[-1] if self.calls else None


def make_tempo_dummy_module(
    tempo_return_value: Any = "tempo",
    captured_dict: Optional[dict] = None,
) -> Callable[[str], Any]:
    """Create a fake import function that returns a module with tempo function.
    
    This is used to test librosa version compatibility code that dynamically
    imports different modules based on librosa version.
    
    Args:
        tempo_return_value: What the tempo() function should return.
        captured_dict: Optional dict to capture the imported module name.
        
    Returns:
        A function suitable for monkeypatching import_module.
    """
    captured = captured_dict if captured_dict is not None else {}

    def fake_import(name: str):
        captured["name"] = name

        class _DummyModule:
            @staticmethod
            def tempo(*_args, **_kwargs):
                return tempo_return_value

        return _DummyModule()

    return fake_import


def create_synthetic_mel_spectrogram(
    n_mels: int = 128,
    n_frames: int = 128,
    batch_size: int = 1,
) -> torch.Tensor:
    """Create synthetic mel spectrogram data for testing.
    
    Args:
        n_mels: Number of mel frequency bins.
        n_frames: Number of time frames.
        batch_size: Batch dimension.
        
    Returns:
        Tensor of shape (batch_size, 1, n_mels, n_frames).
    """
    return torch.randn(batch_size, 1, n_mels, n_frames)


def assert_tensor_shape(tensor: torch.Tensor, expected_shape: tuple[int, ...]):
    """Assert that a tensor has the expected shape.
    
    Provides clear error message on shape mismatch.
    """
    assert tensor.shape == expected_shape, (
        f"Tensor shape mismatch: got {tensor.shape}, expected {expected_shape}"
    )


def assert_valid_probability_distribution(tensor: torch.Tensor, dim: int = -1):
    """Assert that tensor values form valid probability distributions.
    
    Checks that values are non-negative and sum to 1 along the specified dimension.
    """
    assert (tensor >= 0).all(), "Probabilities must be non-negative"
    sums = tensor.sum(dim=dim)
    assert torch.allclose(sums, torch.ones_like(sums)), (
        f"Probabilities must sum to 1, got sums: {sums}"
    )
