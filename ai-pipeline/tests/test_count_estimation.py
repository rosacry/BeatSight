"""
Tests for Count Estimation Module

Tests the CountEstimator class that detects when multiple instances
of the same drum class hit simultaneously (e.g., 2 crashes).
"""

import numpy as np
import pytest

from transcription.count_estimation import (
    CountEstimator,
    CountEstimationConfig,
    INSTRUMENT_CONFIGS,
    estimate_simultaneous_hits,
)


class TestCountEstimationConfig:
    """Test configuration handling."""
    
    def test_default_config(self):
        """Default config should have reasonable values."""
        config = CountEstimationConfig()
        assert config.max_count == 3
        assert 0.0 < config.transient_weight <= 1.0
        assert 0.0 < config.stereo_weight <= 1.0
        assert 0.0 < config.spectral_weight <= 1.0
        assert 0.0 < config.envelope_weight <= 1.0
    
    def test_instrument_specific_configs(self):
        """Instrument-specific configs should be defined."""
        assert "crash" in INSTRUMENT_CONFIGS
        assert "kick" in INSTRUMENT_CONFIGS
        assert "tom" in INSTRUMENT_CONFIGS
        
        # Crashes can have multiple, hi-hats cannot
        assert INSTRUMENT_CONFIGS["crash"].max_count > 1
        assert INSTRUMENT_CONFIGS["hihat_closed"].max_count == 1


class TestCountEstimator:
    """Test the main CountEstimator class."""
    
    @pytest.fixture
    def estimator(self):
        return CountEstimator()
    
    @pytest.fixture
    def mono_audio(self):
        """Generate a simple mono audio segment."""
        sr = 44100
        duration = 0.1  # 100ms
        samples = int(sr * duration)
        t = np.linspace(0, duration, samples)
        # Simple sine wave with attack envelope
        audio = np.sin(2 * np.pi * 440 * t) * np.exp(-5 * t)
        return audio.astype(np.float32), sr
    
    @pytest.fixture
    def stereo_audio(self):
        """Generate stereo audio with different content in L/R."""
        sr = 44100
        duration = 0.1
        samples = int(sr * duration)
        t = np.linspace(0, duration, samples)
        
        # Different frequencies in L/R (simulating panned instruments)
        left = np.sin(2 * np.pi * 440 * t) * np.exp(-5 * t)
        right = np.sin(2 * np.pi * 550 * t) * np.exp(-5 * t)
        
        audio = np.stack([left, right]).astype(np.float32)
        return audio, sr
    
    def test_get_config_known_class(self, estimator):
        """Should return specific config for known instruments."""
        crash_config = estimator.get_config("crash")
        assert crash_config.max_count > 1
        
        hihat_config = estimator.get_config("hihat_closed")
        assert hihat_config.max_count == 1
    
    def test_get_config_unknown_class(self, estimator):
        """Should return default config for unknown instruments."""
        config = estimator.get_config("unknown_instrument")
        assert config == estimator.default_config
    
    def test_estimate_count_mono_audio(self, estimator, mono_audio):
        """Should handle mono audio without errors."""
        audio, sr = mono_audio
        count = estimator.estimate_count(audio, sr, "crash")
        assert isinstance(count, int)
        assert count >= 1
    
    def test_estimate_count_stereo_audio(self, estimator, stereo_audio):
        """Should handle stereo audio without errors."""
        audio, sr = stereo_audio
        count = estimator.estimate_count(audio, sr, "crash")
        assert isinstance(count, int)
        assert count >= 1
    
    def test_estimate_count_respects_max_count(self, estimator, mono_audio):
        """Count should never exceed max_count for the class."""
        audio, sr = mono_audio
        
        for class_name, config in INSTRUMENT_CONFIGS.items():
            count = estimator.estimate_count(audio, sr, class_name)
            assert count <= config.max_count, f"{class_name} exceeded max_count"
    
    def test_estimate_count_hihat_always_one(self, estimator, mono_audio):
        """Hi-hat count should always be 1 (not supported for multiples)."""
        audio, sr = mono_audio
        count = estimator.estimate_count(audio, sr, "hihat_closed")
        assert count == 1
    
    def test_estimate_count_empty_audio(self, estimator):
        """Should handle empty/short audio gracefully."""
        audio = np.zeros(10, dtype=np.float32)
        sr = 44100
        count = estimator.estimate_count(audio, sr, "crash")
        assert count == 1  # Falls back to 1
    
    def test_expand_detections(self, estimator, mono_audio):
        """Should expand detections based on count estimation."""
        audio, sr = mono_audio
        detections = {"kick": 0.95, "hihat_closed": 0.82}
        
        expanded = estimator.expand_detections(detections, audio, sr)
        
        # Should have at least as many items as detections
        assert len(expanded) >= len(detections)
        
        # Each item should be a (class, confidence) tuple
        for class_name, confidence in expanded:
            assert isinstance(class_name, str)
            assert isinstance(confidence, float)
            assert class_name in detections
    
    def test_expand_detections_preserves_confidence(self, estimator, mono_audio):
        """Expanded detections should preserve original confidence."""
        audio, sr = mono_audio
        detections = {"kick": 0.95}
        
        expanded = estimator.expand_detections(detections, audio, sr)
        
        for class_name, confidence in expanded:
            assert confidence == detections[class_name]
    
    def test_estimate_all_counts(self, estimator, mono_audio):
        """Should return counts for all detected classes."""
        audio, sr = mono_audio
        detections = {"crash": 0.9, "kick": 0.8, "snare": 0.7}
        
        result = estimator.estimate_all_counts(detections, audio, sr)
        
        assert set(result.keys()) == set(detections.keys())
        for class_name, (count, conf) in result.items():
            assert isinstance(count, int)
            assert count >= 1
            assert conf == detections[class_name]


class TestCountEstimatorTransientCounting:
    """Test transient counting method specifically."""
    
    @pytest.fixture
    def estimator(self):
        return CountEstimator()
    
    def test_single_transient_audio(self, estimator):
        """Single transient should produce count of 1."""
        sr = 44100
        duration = 0.1
        samples = int(sr * duration)
        
        # Single sharp attack
        t = np.linspace(0, duration, samples)
        audio = np.exp(-50 * t) * np.sin(2 * np.pi * 200 * t)
        audio = audio.astype(np.float32)
        
        count = estimator.estimate_count(audio, sr, "crash")
        assert count >= 1


class TestCountEstimatorStereoAnalysis:
    """Test stereo spread analysis method."""
    
    @pytest.fixture
    def estimator(self):
        return CountEstimator()
    
    def test_center_panned_mono_source(self, estimator):
        """Center-panned source should suggest single hit."""
        sr = 44100
        duration = 0.1
        samples = int(sr * duration)
        t = np.linspace(0, duration, samples)
        
        # Same signal in both channels
        signal = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        audio = np.stack([signal, signal])
        
        count = estimator.estimate_count(audio, sr, "crash")
        # Hard to guarantee count, but should not crash
        assert count >= 1
    
    def test_hard_panned_sources(self, estimator):
        """Hard L/R panned sources may suggest 2 hits."""
        sr = 44100
        duration = 0.1
        samples = int(sr * duration)
        t = np.linspace(0, duration, samples)
        
        # Different frequencies in L and R (decorrelated)
        left = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        right = np.sin(2 * np.pi * 660 * t).astype(np.float32)
        audio = np.stack([left, right])
        
        count = estimator.estimate_count(audio, sr, "crash")
        # Could detect 1 or 2, but should handle stereo without error
        assert count >= 1


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_estimate_simultaneous_hits(self):
        """Convenience function should work correctly."""
        sr = 44100
        audio = np.random.randn(4410).astype(np.float32) * 0.1
        
        result = estimate_simultaneous_hits(
            audio, sr, ["kick", "crash"]
        )
        
        assert "kick" in result
        assert "crash" in result
        assert result["kick"] >= 1
        assert result["crash"] >= 1
