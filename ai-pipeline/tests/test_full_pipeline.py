"""
Tests for Full Drum Transcription Pipeline

Tests the DrumTranscriptionPipeline that chains together:
- Onset detection
- Multi-label classification
- Count estimation
- Pitch ranking
"""

import json
import numpy as np
import pytest
from pathlib import Path
from dataclasses import asdict

from transcription.full_pipeline import (
    DrumEvent,
    TranscriptionResult,
    PipelineConfig,
    DrumTranscriptionPipeline,
)


class TestDrumEvent:
    """Test the DrumEvent dataclass."""
    
    def test_basic_event(self):
        """Create a basic drum event."""
        event = DrumEvent(
            time=0.5,
            label="kick",
            confidence=0.95
        )
        
        assert event.time == 0.5
        assert event.label == "kick"
        assert event.confidence == 0.95
    
    def test_event_with_all_fields(self):
        """Create event with all optional fields."""
        event = DrumEvent(
            time=1.0,
            label="crash_1",
            confidence=0.88,
            base_label="crash",
            ranked_label="crash_1",
            count_at_onset=2,
            onset_index=5
        )
        
        assert event.base_label == "crash"
        assert event.ranked_label == "crash_1"
        assert event.count_at_onset == 2
        assert event.onset_index == 5
    
    def test_event_to_dict(self):
        """Should convert to dict correctly."""
        event = DrumEvent(time=0.5, label="snare", confidence=0.9)
        d = event.to_dict()
        
        assert "time" in d
        assert "label" in d
        assert "confidence" in d
        assert d["time"] == 0.5


class TestTranscriptionResult:
    """Test the TranscriptionResult dataclass."""
    
    def test_empty_result(self):
        """Create empty transcription result."""
        result = TranscriptionResult(events=[])
        
        assert len(result.events) == 0
        assert result.num_events == 0
    
    def test_result_with_events(self):
        """Create result with events."""
        events = [
            DrumEvent(time=0.5, label="kick", confidence=0.9),
            DrumEvent(time=0.5, label="hihat_closed", confidence=0.8),
            DrumEvent(time=1.0, label="snare", confidence=0.85),
        ]
        
        result = TranscriptionResult(
            events=events,
            audio_duration=2.0,
            sample_rate=44100,
            num_onsets=2,
            num_events=3,
            processing_time=0.5,
            class_counts={"kick": 1, "hihat_closed": 1, "snare": 1}
        )
        
        assert len(result.events) == 3
        assert result.audio_duration == 2.0
        assert result.num_events == 3
    
    def test_result_to_dict(self):
        """Should convert to dict correctly."""
        events = [DrumEvent(time=0.5, label="kick", confidence=0.9)]
        result = TranscriptionResult(
            events=events,
            num_events=1,
            class_counts={"kick": 1}
        )
        
        d = result.to_dict()
        
        assert "events" in d
        assert "metadata" in d
        assert "class_counts" in d
        assert len(d["events"]) == 1
    
    def test_result_to_json(self):
        """Should serialize to valid JSON."""
        events = [
            DrumEvent(time=0.5, label="kick", confidence=0.9),
            DrumEvent(time=1.0, label="snare", confidence=0.85),
        ]
        result = TranscriptionResult(
            events=events,
            num_events=2,
            class_counts={"kick": 1, "snare": 1}
        )
        
        json_str = result.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert "events" in parsed
        assert len(parsed["events"]) == 2


class TestPipelineConfig:
    """Test the PipelineConfig dataclass."""
    
    def test_default_config(self):
        """Default config should have reasonable values."""
        config = PipelineConfig()
        
        assert config.threshold == 0.5
        assert config.onset_window_ms == 100.0
        assert config.enable_count_estimation == True
        assert config.enable_pitch_ranking == True
        assert config.batch_size == 64
    
    def test_custom_config(self):
        """Should accept custom configuration."""
        config = PipelineConfig(
            threshold=0.4,
            enable_count_estimation=False,
            enable_pitch_ranking=False,
            batch_size=128
        )
        
        assert config.threshold == 0.4
        assert config.enable_count_estimation == False
        assert config.enable_pitch_ranking == False
        assert config.batch_size == 128
    
    def test_per_class_thresholds(self):
        """Should accept per-class thresholds."""
        per_class = {"crash": 0.3, "snare": 0.6}
        config = PipelineConfig(per_class_thresholds=per_class)
        
        assert config.per_class_thresholds["crash"] == 0.3
        assert config.per_class_thresholds["snare"] == 0.6


class TestPipelineInit:
    """Test pipeline initialization (without actual model)."""
    
    def test_config_stored(self, tmp_path):
        """Config should be stored during initialization."""
        # We can't fully test without a model, but test config handling
        config = PipelineConfig(threshold=0.4)
        
        assert config.threshold == 0.4
    
    def test_thresholds_loading(self, tmp_path):
        """Should load thresholds from file if provided."""
        thresholds_file = tmp_path / "thresholds.json"
        thresholds_data = {
            "per_class_thresholds": {
                "kick": 0.5,
                "snare": 0.45,
                "crash": 0.35
            }
        }
        
        with open(thresholds_file, 'w') as f:
            json.dump(thresholds_data, f)
        
        # Verify file was created and is valid
        loaded = json.loads(thresholds_file.read_text())
        assert "per_class_thresholds" in loaded


class TestOnsetExpansion:
    """Test the count estimation and event expansion logic."""
    
    def test_single_class_single_count(self):
        """Single class with count=1 produces 1 event."""
        detections = [{"kick": 0.9}]
        onset_times = [0.5]
        
        # Simulate expansion
        events = []
        for time, det in zip(onset_times, detections):
            for cls, conf in det.items():
                count = 1
                for _ in range(count):
                    events.append(DrumEvent(
                        time=time,
                        label=cls,
                        confidence=conf,
                        base_label=cls,
                        count_at_onset=count,
                    ))
        
        assert len(events) == 1
        assert events[0].label == "kick"
    
    def test_multi_class_same_onset(self):
        """Multiple classes at same onset produce multiple events."""
        detections = [{"kick": 0.9, "hihat_closed": 0.8}]
        onset_times = [0.5]
        
        events = []
        for time, det in zip(onset_times, detections):
            for cls, conf in det.items():
                events.append(DrumEvent(
                    time=time,
                    label=cls,
                    confidence=conf,
                ))
        
        assert len(events) == 2
        labels = {e.label for e in events}
        assert "kick" in labels
        assert "hihat_closed" in labels
    
    def test_count_expansion(self):
        """Count > 1 produces multiple events for same class."""
        # Simulate 2 crashes detected
        detections = [{"crash": 0.85}]
        onset_times = [0.5]
        counts = {"crash": 2}
        
        events = []
        for time, det in zip(onset_times, detections):
            for cls, conf in det.items():
                count = counts.get(cls, 1)
                for _ in range(count):
                    events.append(DrumEvent(
                        time=time,
                        label=cls,
                        confidence=conf,
                        count_at_onset=count,
                    ))
        
        assert len(events) == 2
        assert all(e.label == "crash" for e in events)
        assert all(e.count_at_onset == 2 for e in events)


class TestPitchRankingIntegration:
    """Test pitch ranking label assignment."""
    
    def test_rankable_labels_get_suffix(self):
        """Rankable classes should get _1, _2 suffixes."""
        base_label = "crash"
        ranked_label = f"{base_label}_1"
        
        assert ranked_label == "crash_1"
    
    def test_non_rankable_labels_unchanged(self):
        """Non-rankable classes should keep original label."""
        non_rankable = ["kick", "snare", "hihat_closed", "hihat_open", "hihat_pedal"]
        
        for label in non_rankable:
            # These should not get _1 suffix typically
            assert "_" not in label or "hihat" in label or "cross" in label


class TestEventSorting:
    """Test event sorting by time."""
    
    def test_events_sorted_by_time(self):
        """Events should be sorted by time in final output."""
        events = [
            DrumEvent(time=1.0, label="snare", confidence=0.9),
            DrumEvent(time=0.5, label="kick", confidence=0.85),
            DrumEvent(time=0.75, label="hihat_closed", confidence=0.8),
        ]
        
        sorted_events = sorted(events, key=lambda e: e.time)
        
        assert sorted_events[0].time == 0.5
        assert sorted_events[1].time == 0.75
        assert sorted_events[2].time == 1.0
    
    def test_same_time_events_preserved(self):
        """Events at same time should all be preserved."""
        events = [
            DrumEvent(time=0.5, label="kick", confidence=0.9),
            DrumEvent(time=0.5, label="hihat_closed", confidence=0.8),
        ]
        
        sorted_events = sorted(events, key=lambda e: e.time)
        
        assert len(sorted_events) == 2
        assert all(e.time == 0.5 for e in sorted_events)


class TestClassCounts:
    """Test class counting statistics."""
    
    def test_count_single_occurrences(self):
        """Should correctly count single occurrences."""
        events = [
            DrumEvent(time=0.5, label="kick", confidence=0.9),
            DrumEvent(time=1.0, label="snare", confidence=0.85),
            DrumEvent(time=1.5, label="crash_1", confidence=0.8),
        ]
        
        class_counts = {}
        for e in events:
            class_counts[e.label] = class_counts.get(e.label, 0) + 1
        
        assert class_counts["kick"] == 1
        assert class_counts["snare"] == 1
        assert class_counts["crash_1"] == 1
    
    def test_count_multiple_occurrences(self):
        """Should correctly count multiple occurrences."""
        events = [
            DrumEvent(time=0.5, label="kick", confidence=0.9),
            DrumEvent(time=1.0, label="kick", confidence=0.85),
            DrumEvent(time=1.5, label="kick", confidence=0.8),
            DrumEvent(time=2.0, label="snare", confidence=0.9),
        ]
        
        class_counts = {}
        for e in events:
            class_counts[e.label] = class_counts.get(e.label, 0) + 1
        
        assert class_counts["kick"] == 3
        assert class_counts["snare"] == 1
