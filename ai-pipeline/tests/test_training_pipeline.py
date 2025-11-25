"""
Comprehensive tests for the training pipeline.

These tests validate critical paths for the warmup probe and training runs.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, List

import numpy as np
import pytest
import torch

# Ensure the training module is importable
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.train_classifier import (
    DrumSampleDataset,
    stratified_sample_indices,
    train_epoch,
    validate,
)
from transcription.ml_drum_classifier import DrumClassifierCNN
from tests.test_utils import create_mock_dataloader


class TestDrumClassifierCNN:
    """Test suite for the model architecture."""

    def test_model_output_shape(self):
        """Verify model produces correct output shape."""
        model = DrumClassifierCNN(num_classes=24)
        batch = torch.randn(8, 1, 128, 128)
        output = model(batch)
        assert output.shape == (8, 24), f"Expected (8, 24), got {output.shape}"

    def test_model_parameter_count(self):
        """Verify model is reasonably sized for 12GB VRAM."""
        model = DrumClassifierCNN(num_classes=24)
        param_count = sum(p.numel() for p in model.parameters())
        # Model should be under 5M parameters for efficiency
        assert param_count < 5_000_000, f"Model has {param_count} params, may be too large"
        # But not too small to learn
        assert param_count > 100_000, f"Model has {param_count} params, may be too small"

    def test_model_channels_last(self):
        """Verify model works with channels_last memory format."""
        model = DrumClassifierCNN(num_classes=24)
        model = model.to(memory_format=torch.channels_last)
        batch = torch.randn(8, 1, 128, 128).to(memory_format=torch.channels_last)
        output = model(batch)
        assert output.shape == (8, 24)

    def test_model_amp_compatibility(self):
        """Verify model is compatible with AMP."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")
        
        device = torch.device("cuda")
        model = DrumClassifierCNN(num_classes=24).to(device)
        batch = torch.randn(4, 1, 128, 128, device=device)
        
        with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
            output = model(batch)
        
        assert output.shape == (4, 24)
        assert output.dtype == torch.float16

    def test_model_gradient_flow(self):
        """Verify gradients flow through all layers."""
        model = DrumClassifierCNN(num_classes=24)
        batch = torch.randn(4, 1, 128, 128, requires_grad=True)
        labels = torch.randint(0, 24, (4,))
        
        output = model(batch)
        loss = torch.nn.functional.cross_entropy(output, labels)
        loss.backward()
        
        # Check that all parameters received gradients
        for name, param in model.named_parameters():
            assert param.grad is not None, f"No gradient for {name}"
            assert not torch.all(param.grad == 0), f"Zero gradient for {name}"


class TestStratifiedSampling:
    """Test suite for stratified sampling."""

    def test_stratified_preserves_class_ratio(self):
        """Verify stratified sampling maintains class distribution."""
        labels = [
            {"component_idx": 0} for _ in range(100)
        ] + [
            {"component_idx": 1} for _ in range(50)
        ] + [
            {"component_idx": 2} for _ in range(25)
        ]
        
        indices = stratified_sample_indices(labels, fraction=0.5, seed=42)
        
        sampled_classes = [labels[i]["component_idx"] for i in indices]
        class_counts = {c: sampled_classes.count(c) for c in [0, 1, 2]}
        
        # Should maintain ~2:1:0.5 ratio
        assert class_counts[0] > class_counts[1] > class_counts[2]
        # Total should be ~half
        assert len(indices) == pytest.approx(len(labels) * 0.5, rel=0.1)

    def test_stratified_deterministic(self):
        """Verify stratified sampling is deterministic with same seed."""
        labels = [{"component_idx": i % 5} for i in range(100)]
        
        indices1 = stratified_sample_indices(labels, fraction=0.3, seed=42)
        indices2 = stratified_sample_indices(labels, fraction=0.3, seed=42)
        
        assert indices1 == indices2


class TestDatasetIntegration:
    """Integration tests for the dataset class."""

    @pytest.fixture
    def mock_dataset_dir(self, tmp_path: Path):
        """Create a minimal mock dataset structure."""
        train_dir = tmp_path / "train"
        train_dir.mkdir()
        
        # Create mock audio files (just silent clips for testing)
        for i in range(10):
            audio_path = train_dir / f"sample_{i}.wav"
            # Create minimal valid WAV file
            import wave
            with wave.open(str(audio_path), 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                # 0.1 second of silence
                wav.writeframes(b'\x00' * 8820)
        
        # Create labels file
        labels = [
            {"file": f"sample_{i}.wav", "component_idx": i % 5}
            for i in range(10)
        ]
        labels_path = tmp_path / "train_labels.json"
        with labels_path.open("w") as f:
            json.dump(labels, f)
        
        return tmp_path

    def test_dataset_length(self, mock_dataset_dir):
        """Verify dataset reports correct length."""
        dataset = DrumSampleDataset(
            mock_dataset_dir / "train",
            mock_dataset_dir / "train_labels.json",
            sr=44100,
        )
        assert len(dataset) == 10

    def test_dataset_item_shape(self, mock_dataset_dir):
        """Verify dataset returns correct tensor shapes."""
        dataset = DrumSampleDataset(
            mock_dataset_dir / "train",
            mock_dataset_dir / "train_labels.json",
            sr=44100,
            n_mels=128,
            target_frames=128,
        )
        features, label = dataset[0]
        assert features.shape == (1, 128, 128), f"Got shape {features.shape}"
        assert isinstance(label, int)

    def test_dataset_caching(self, mock_dataset_dir, tmp_path):
        """Verify dataset caching works correctly."""
        cache_dir = tmp_path / "cache"
        
        dataset = DrumSampleDataset(
            mock_dataset_dir / "train",
            mock_dataset_dir / "train_labels.json",
            sr=44100,
            cache_dir=cache_dir,
            cache_dtype="float16",
        )
        
        # First access should create cache
        features1, _ = dataset[0]
        assert (cache_dir / "sample_0.pt").exists()
        
        # Second access should load from cache
        features2, _ = dataset[0]
        assert torch.allclose(features1, features2, atol=1e-3)


class TestTrainingLoop:
    """Test the training loop components."""

    @pytest.fixture
    def mock_dataloader(self):
        """Create a minimal mock dataloader using shared test utilities."""
        return create_mock_dataloader(
            batch_size=8,
            dataset_size=32,
            input_shape=(1, 128, 128),
            num_classes=24,
            shuffle=True,
        )

    def test_train_epoch_runs(self, mock_dataloader):
        """Verify train_epoch completes without errors."""
        model = DrumClassifierCNN(num_classes=24)
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        device = torch.device("cpu")
        
        loss, acc = train_epoch(
            model,
            mock_dataloader,
            criterion,
            optimizer,
            device,
            amp_enabled=False,
        )
        
        assert isinstance(loss, float)
        assert isinstance(acc, float)
        assert loss >= 0
        assert 0 <= acc <= 100

    def test_validate_runs(self, mock_dataloader):
        """Verify validate completes without errors."""
        model = DrumClassifierCNN(num_classes=24)
        criterion = torch.nn.CrossEntropyLoss()
        device = torch.device("cpu")
        
        loss, acc = validate(
            model,
            mock_dataloader,
            criterion,
            device,
            amp_enabled=False,
        )
        
        assert isinstance(loss, float)
        assert isinstance(acc, float)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_train_epoch_with_amp(self, mock_dataloader):
        """Verify training works with AMP enabled."""
        device = torch.device("cuda")
        model = DrumClassifierCNN(num_classes=24).to(device)
        criterion = torch.nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        scaler = torch.amp.GradScaler()
        
        # Move data to GPU
        class GPUDataset(torch.utils.data.Dataset):
            def __len__(self):
                return 16
            
            def __getitem__(self, idx):
                return torch.randn(1, 128, 128), idx % 24
        
        gpu_loader = torch.utils.data.DataLoader(
            GPUDataset(),
            batch_size=8,
        )
        
        loss, acc = train_epoch(
            model,
            gpu_loader,
            criterion,
            optimizer,
            device,
            amp_enabled=True,
            scaler=scaler,
            autocast_dtype=torch.float16,
        )
        
        assert isinstance(loss, float)
        assert isinstance(acc, float)


class TestHardwareOptimization:
    """Tests specific to RTX 3080 Ti optimization."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_recommended_batch_size_fits_vram(self):
        """Verify recommended batch size fits in VRAM."""
        device = torch.device("cuda")
        model = DrumClassifierCNN(num_classes=24).to(device)
        model = model.to(memory_format=torch.channels_last)
        
        # Warmup probe batch size
        batch_size = 32
        batch = torch.randn(batch_size, 1, 128, 128, device=device)
        batch = batch.to(memory_format=torch.channels_last)
        
        # Forward pass
        with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
            output = model(batch)
        
        # Should not OOM with 32 batch size on 12GB card
        assert output.shape == (batch_size, 24)
        
        # Check memory usage (should be well under 12GB)
        memory_used_gb = torch.cuda.max_memory_allocated() / (1024 ** 3)
        assert memory_used_gb < 6, f"Used {memory_used_gb:.2f}GB, expected < 6GB for batch_size=32"

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_torch_compile_compatibility(self):
        """Verify model is compatible with torch.compile."""
        if not hasattr(torch, "compile"):
            pytest.skip("torch.compile not available")
        
        # Check if triton is available (required for inductor backend)
        try:
            import triton
        except ImportError:
            pytest.skip("triton not installed (required for torch.compile inductor backend)")
        
        device = torch.device("cuda")
        model = DrumClassifierCNN(num_classes=24).to(device)
        
        try:
            compiled_model = torch.compile(model, mode="reduce-overhead")
            batch = torch.randn(4, 1, 128, 128, device=device)
            output = compiled_model(batch)
            assert output.shape == (4, 24)
        except Exception as e:
            pytest.fail(f"torch.compile failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
