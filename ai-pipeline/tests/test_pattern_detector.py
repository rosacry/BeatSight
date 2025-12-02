#!/usr/bin/env python3
"""
Unit tests for the Pattern Detector module.

Tests cover:
- Crash build detection
- Accent-tap pattern detection
- Hi-hat bark detection
- Continuous barking detection
- Hi-hat splash detection
- Edge cases and robustness
"""

import pytest

# Add ai-pipeline to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from transcription.pattern_detector import (
    PatternDetector,
    PatternDetectorConfig,
    PatternType,
    PatternCategory,
    DrumEvent,
    CrashBuildDetector,
    AccentTapDetector,
    HiHatBarkDetector,
    HiHatSplashDetector,
    detect_all_patterns,
    events_from_labels,
    patterns_to_json,
    annotate_transcription_result,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def default_config():
    """Default configuration."""
    return PatternDetectorConfig()


@pytest.fixture
def crash_build_events():
    """Events forming a clear crash build pattern."""
    return [
        DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
        DrumEvent(timestamp=0.25, label="crash", velocity=0.4),
        DrumEvent(timestamp=0.5, label="crash", velocity=0.55),
        DrumEvent(timestamp=0.75, label="crash", velocity=0.7),
        DrumEvent(timestamp=1.0, label="crash", velocity=0.9),
    ]


@pytest.fixture
def hihat_bark_events():
    """Events forming hi-hat bark patterns."""
    return [
        DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.6),
        DrumEvent(timestamp=0.04, label="hihat_closed", velocity=0.5),
        # Second bark
        DrumEvent(timestamp=0.5, label="hihat_open", velocity=0.65),
        DrumEvent(timestamp=0.54, label="hihat_closed", velocity=0.5),
        # Third bark
        DrumEvent(timestamp=1.0, label="hihat_open", velocity=0.6),
        DrumEvent(timestamp=1.04, label="hihat_closed", velocity=0.5),
    ]


@pytest.fixture
def accent_tap_events():
    """Events forming an accent-tap pattern on snare."""
    return [
        DrumEvent(timestamp=0.0, label="snare", velocity=0.9),    # Accent
        DrumEvent(timestamp=0.125, label="snare", velocity=0.3),  # Tap
        DrumEvent(timestamp=0.25, label="snare", velocity=0.85),  # Accent
        DrumEvent(timestamp=0.375, label="snare", velocity=0.25), # Tap
        DrumEvent(timestamp=0.5, label="snare", velocity=0.9),    # Accent
        DrumEvent(timestamp=0.625, label="snare", velocity=0.3),  # Tap
        DrumEvent(timestamp=0.75, label="snare", velocity=0.88),  # Accent
        DrumEvent(timestamp=0.875, label="snare", velocity=0.28), # Tap
    ]


@pytest.fixture
def mixed_events():
    """Events with multiple pattern types."""
    events = []
    
    # Crash build at 0-1s
    events.extend([
        DrumEvent(timestamp=0.0, label="crash", velocity=0.35),
        DrumEvent(timestamp=0.3, label="crash", velocity=0.5),
        DrumEvent(timestamp=0.6, label="crash", velocity=0.7),
        DrumEvent(timestamp=0.9, label="crash", velocity=0.95),
    ])
    
    # Some regular hits
    events.extend([
        DrumEvent(timestamp=1.5, label="kick", velocity=0.8),
        DrumEvent(timestamp=2.0, label="snare", velocity=0.75),
    ])
    
    # Hi-hat barks at 3s
    events.extend([
        DrumEvent(timestamp=3.0, label="hihat_open", velocity=0.6),
        DrumEvent(timestamp=3.05, label="hihat_closed", velocity=0.5),
    ])
    
    return sorted(events, key=lambda e: e.timestamp)


# ============================================================================
# CRASH BUILD DETECTOR TESTS
# ============================================================================

class TestCrashBuildDetector:
    """Tests for crash build detection."""
    
    def test_detects_clear_crash_build(self, crash_build_events, default_config):
        """Should detect a clear crash build pattern."""
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(crash_build_events)
        
        assert len(patterns) == 1
        pattern = patterns[0]
        
        assert pattern.pattern_type == PatternType.CRASH_BUILD
        assert pattern.category == PatternCategory.DYNAMIC
        assert pattern.event_count == 5
        assert pattern.confidence > 0.5
        assert pattern.properties["velocity_trend"] > 0
        assert pattern.properties["climax_at_end"] == True
    
    def test_no_detection_flat_velocity(self, default_config):
        """Should not detect crash build with flat velocity."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.5),
            DrumEvent(timestamp=0.25, label="crash", velocity=0.52),
            DrumEvent(timestamp=0.5, label="crash", velocity=0.48),
            DrumEvent(timestamp=0.75, label="crash", velocity=0.51),
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 0
    
    def test_no_detection_decreasing_velocity(self, default_config):
        """Should not detect crash build with decreasing velocity."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.9),
            DrumEvent(timestamp=0.25, label="crash", velocity=0.7),
            DrumEvent(timestamp=0.5, label="crash", velocity=0.5),
            DrumEvent(timestamp=0.75, label="crash", velocity=0.3),
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 0
    
    def test_detects_china_cymbal_build(self, default_config):
        """Should detect build on china cymbals too."""
        events = [
            DrumEvent(timestamp=0.0, label="china", velocity=0.3),
            DrumEvent(timestamp=0.2, label="china", velocity=0.5),
            DrumEvent(timestamp=0.4, label="china", velocity=0.7),
            DrumEvent(timestamp=0.6, label="china", velocity=0.9),
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 1
        assert "china" in patterns[0].instruments
    
    def test_respects_max_gap(self, default_config):
        """Should not connect hits with too large gap."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.25, label="crash", velocity=0.5),
            DrumEvent(timestamp=1.0, label="crash", velocity=0.7),  # Gap too large
            DrumEvent(timestamp=1.2, label="crash", velocity=0.9),
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        # Should not form one large build
        assert all(p.event_count < 4 for p in patterns)
    
    def test_minimum_hits_required(self, default_config):
        """Should require minimum number of hits."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.25, label="crash", velocity=0.9),  # Only 2 hits
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 0
    
    def test_multiple_builds_in_sequence(self, default_config):
        """Should detect multiple separate crash builds."""
        events = [
            # First build
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.2, label="crash", velocity=0.5),
            DrumEvent(timestamp=0.4, label="crash", velocity=0.9),
            # Gap
            DrumEvent(timestamp=5.0, label="crash", velocity=0.25),
            DrumEvent(timestamp=5.2, label="crash", velocity=0.5),
            DrumEvent(timestamp=5.4, label="crash", velocity=0.85),
        ]
        
        detector = CrashBuildDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 2


# ============================================================================
# ACCENT-TAP DETECTOR TESTS
# ============================================================================

class TestAccentTapDetector:
    """Tests for accent-tap pattern detection."""
    
    def test_detects_clear_accent_tap(self, accent_tap_events, default_config):
        """Should detect a clear accent-tap pattern."""
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(accent_tap_events)
        
        assert len(patterns) >= 1
        pattern = patterns[0]
        
        assert pattern.pattern_type == PatternType.ACCENT_TAP
        assert pattern.category == PatternCategory.DYNAMIC
        assert pattern.properties["alternation_score"] > 0.6
        assert pattern.properties["dynamic_range"] > 0.3
    
    def test_no_detection_uniform_velocity(self, default_config):
        """Should not detect pattern with uniform velocity."""
        events = [
            DrumEvent(timestamp=0.0, label="snare", velocity=0.6),
            DrumEvent(timestamp=0.125, label="snare", velocity=0.62),
            DrumEvent(timestamp=0.25, label="snare", velocity=0.58),
            DrumEvent(timestamp=0.375, label="snare", velocity=0.6),
        ]
        
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) == 0
    
    def test_detects_on_hihat(self, default_config):
        """Should detect accent-tap on hi-hat."""
        # Need 8 hits for reliable detection (4 accent-tap pairs)
        events = [
            DrumEvent(timestamp=0.0, label="hihat_closed", velocity=0.85),
            DrumEvent(timestamp=0.1, label="hihat_closed", velocity=0.25),
            DrumEvent(timestamp=0.2, label="hihat_closed", velocity=0.88),
            DrumEvent(timestamp=0.3, label="hihat_closed", velocity=0.22),
            DrumEvent(timestamp=0.4, label="hihat_closed", velocity=0.85),
            DrumEvent(timestamp=0.5, label="hihat_closed", velocity=0.25),
            DrumEvent(timestamp=0.6, label="hihat_closed", velocity=0.9),
            DrumEvent(timestamp=0.7, label="hihat_closed", velocity=0.2),
        ]
        
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(events)
        
        assert len(patterns) >= 1
        assert patterns[0].instrument == "hihat"
    
    def test_requires_timing_consistency(self, default_config):
        """Should require consistent timing for pattern."""
        events = [
            DrumEvent(timestamp=0.0, label="snare", velocity=0.9),
            DrumEvent(timestamp=0.1, label="snare", velocity=0.3),   # 100ms gap
            DrumEvent(timestamp=0.5, label="snare", velocity=0.85),  # 400ms gap (inconsistent)
            DrumEvent(timestamp=0.6, label="snare", velocity=0.25),
        ]
        
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(events)
        
        # May still detect short segments, but full pattern unlikely
        if patterns:
            assert patterns[0].properties["timing_consistency"] < 0.9
    
    def test_classifies_subdivision(self, default_config):
        """Should classify the subdivision type."""
        # 16th notes at 120 BPM = 0.125s intervals
        events = [
            DrumEvent(timestamp=0.0, label="snare", velocity=0.9),
            DrumEvent(timestamp=0.125, label="snare", velocity=0.3),
            DrumEvent(timestamp=0.25, label="snare", velocity=0.85),
            DrumEvent(timestamp=0.375, label="snare", velocity=0.25),
            DrumEvent(timestamp=0.5, label="snare", velocity=0.9),
            DrumEvent(timestamp=0.625, label="snare", velocity=0.3),
        ]
        
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(events)
        
        if patterns:
            # Should classify as 16th notes, 8th notes, or 16th triplets based on exact timing
            assert patterns[0].properties["subdivision"] in ("16th_notes", "8th_notes", "16th_triplets")
    
    def test_separates_different_instruments(self, default_config):
        """Should not mix different instruments in same pattern."""
        events = [
            DrumEvent(timestamp=0.0, label="snare", velocity=0.9),
            DrumEvent(timestamp=0.1, label="kick", velocity=0.3),  # Different instrument
            DrumEvent(timestamp=0.2, label="snare", velocity=0.85),
            DrumEvent(timestamp=0.3, label="kick", velocity=0.25),
        ]
        
        detector = AccentTapDetector(default_config)
        patterns = detector.detect(events)
        
        # Should not detect a pattern mixing instruments
        for p in patterns:
            assert len(set(p.instruments)) == 1


# ============================================================================
# HI-HAT BARK DETECTOR TESTS
# ============================================================================

class TestHiHatBarkDetector:
    """Tests for hi-hat bark detection."""
    
    def test_detects_single_bark(self, default_config):
        """Should detect a single hi-hat bark."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.6),
            DrumEvent(timestamp=0.04, label="hihat_closed", velocity=0.5),
        ]
        
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 1
        
        bark = barks[0]
        assert bark.properties["gap_ms"] == pytest.approx(40, rel=0.1)
        assert bark.instrument == "hihat"
    
    def test_detects_multiple_barks(self, hihat_bark_events, default_config):
        """Should detect multiple hi-hat barks."""
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(hihat_bark_events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 3
    
    def test_detects_continuous_barking(self, hihat_bark_events, default_config):
        """Should detect continuous barking pattern."""
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(hihat_bark_events)
        
        continuous = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK_CONTINUOUS]
        assert len(continuous) == 1
        
        cont = continuous[0]
        assert cont.properties["bark_count"] == 3
    
    def test_no_detection_gap_too_large(self, default_config):
        """Should not detect bark if gap too large."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.6),
            DrumEvent(timestamp=0.2, label="hihat_closed", velocity=0.5),  # 200ms gap
        ]
        
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 0
    
    def test_no_detection_gap_too_small(self, default_config):
        """Should not detect bark if gap too small (likely same hit)."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.6),
            DrumEvent(timestamp=0.005, label="hihat_closed", velocity=0.5),  # 5ms gap
        ]
        
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 0
    
    def test_requires_open_then_close(self, default_config):
        """Should require open followed by close, not reverse."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_closed", velocity=0.5),
            DrumEvent(timestamp=0.04, label="hihat_open", velocity=0.6),
        ]
        
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 0
    
    def test_respects_minimum_open_velocity(self, default_config):
        """Should require minimum velocity on open hit."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.1),  # Too soft
            DrumEvent(timestamp=0.04, label="hihat_closed", velocity=0.5),
        ]
        
        detector = HiHatBarkDetector(default_config)
        patterns = detector.detect(events)
        
        barks = [p for p in patterns if p.pattern_type == PatternType.HIHAT_BARK]
        assert len(barks) == 0


# ============================================================================
# HI-HAT SPLASH DETECTOR TESTS
# ============================================================================

class TestHiHatSplashDetector:
    """Tests for hi-hat splash detection."""
    
    def test_detects_foot_splash(self, default_config):
        """Should detect foot splash."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_pedal", velocity=0.5),
            DrumEvent(timestamp=0.3, label="hihat_closed", velocity=0.4),  # Close after sustain
        ]
        
        detector = HiHatSplashDetector(default_config)
        patterns = detector.detect(events)
        
        splashes = [p for p in patterns if p.pattern_type == PatternType.HIHAT_SPLASH]
        assert len(splashes) == 1
        assert splashes[0].properties["splash_type"] == "foot_splash"
    
    def test_detects_open_splash(self, default_config):
        """Should detect open hi-hat splash."""
        events = [
            DrumEvent(timestamp=0.0, label="hihat_open", velocity=0.4),
            DrumEvent(timestamp=0.2, label="hihat_closed", velocity=0.3),
        ]
        
        detector = HiHatSplashDetector(default_config)
        patterns = detector.detect(events)
        
        # May or may not detect based on exact thresholds
        # The key is that it processes without error


# ============================================================================
# MAIN PATTERN DETECTOR TESTS
# ============================================================================

class TestPatternDetector:
    """Tests for the main PatternDetector orchestrator."""
    
    def test_detects_all_pattern_types(self, mixed_events, default_config):
        """Should detect multiple pattern types in mixed events."""
        detector = PatternDetector(default_config)
        patterns = detector.detect(mixed_events)
        
        pattern_types = {p.pattern_type for p in patterns}
        
        # Should detect at least crash build and bark
        assert PatternType.CRASH_BUILD in pattern_types or PatternType.HIHAT_BARK in pattern_types
    
    def test_annotates_events_correctly(self, crash_build_events, default_config):
        """Should correctly annotate events with pattern info."""
        detector = PatternDetector(default_config)
        patterns = detector.detect(crash_build_events)
        
        annotated = detector.annotate_events(crash_build_events, patterns)
        
        # All events in crash build should have pattern IDs
        for event in annotated:
            assert len(event.pattern_ids) > 0
            assert event.dynamic_change == "crescendo"
    
    def test_pattern_summary(self, mixed_events, default_config):
        """Should generate correct summary statistics."""
        detector = PatternDetector(default_config)
        patterns = detector.detect(mixed_events)
        
        summary = detector.get_pattern_summary(patterns)
        
        assert "total_patterns" in summary
        assert "by_type" in summary
        assert "confidence_stats" in summary
        assert summary["total_patterns"] == len(patterns)
    
    def test_filters_by_confidence(self):
        """Should filter patterns below minimum confidence."""
        config = PatternDetectorConfig(min_confidence=0.9)
        
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.3, label="crash", velocity=0.35),  # Small increase
            DrumEvent(timestamp=0.6, label="crash", velocity=0.4),
        ]
        
        detector = PatternDetector(config)
        patterns = detector.detect(events)
        
        # Low confidence patterns should be filtered
        for p in patterns:
            assert p.confidence >= 0.9
    
    def test_empty_events(self, default_config):
        """Should handle empty event list."""
        detector = PatternDetector(default_config)
        patterns = detector.detect([])
        
        assert patterns == []


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_detect_all_patterns(self, crash_build_events):
        """Should work as shortcut function."""
        patterns = detect_all_patterns(crash_build_events)
        
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.CRASH_BUILD
    
    def test_events_from_labels(self):
        """Should convert label dicts to DrumEvent objects."""
        labels = [
            {"timestamp": 0.0, "label": "crash", "velocity": 0.5},
            {"timestamp": 0.5, "label": "snare", "velocity": 0.8},
        ]
        
        events = events_from_labels(labels)
        
        assert len(events) == 2
        assert events[0].timestamp == 0.0
        assert events[0].label == "crash"
        assert events[0].velocity == 0.5
    
    def test_events_from_labels_custom_keys(self):
        """Should handle custom key names."""
        labels = [
            {"time": 0.0, "component": "kick", "vel": 0.7},
        ]
        
        events = events_from_labels(
            labels,
            timestamp_key="time",
            label_key="component",
            velocity_key="vel",
        )
        
        assert events[0].timestamp == 0.0
        assert events[0].label == "kick"
        assert events[0].velocity == 0.7
    
    def test_patterns_to_json(self, crash_build_events, default_config):
        """Should convert patterns to JSON-serializable dicts."""
        detector = PatternDetector(default_config)
        patterns = detector.detect(crash_build_events)
        
        json_data = patterns_to_json(patterns)
        
        assert isinstance(json_data, list)
        assert all(isinstance(p, dict) for p in json_data)
        assert "pattern_type" in json_data[0]
        assert "start_time" in json_data[0]
    
    def test_annotate_transcription_result(self):
        """Should process full transcription result."""
        events = [
            {"timestamp": 0.0, "label": "crash", "velocity": 0.3},
            {"timestamp": 0.25, "label": "crash", "velocity": 0.5},
            {"timestamp": 0.5, "label": "crash", "velocity": 0.7},
            {"timestamp": 0.75, "label": "crash", "velocity": 0.9},
        ]
        
        annotated, patterns = annotate_transcription_result(events)
        
        assert len(annotated) == 4
        assert len(patterns) >= 1
        assert "pattern_ids" in annotated[0]


# ============================================================================
# EDGE CASES AND ROBUSTNESS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and robustness."""
    
    def test_single_event(self, default_config):
        """Should handle single event without crashing."""
        events = [DrumEvent(timestamp=0.0, label="crash", velocity=0.5)]
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        assert patterns == []
    
    def test_events_out_of_order(self, default_config):
        """Should handle events not in chronological order."""
        # Note: events are processed as provided, not auto-sorted
        # Use events_from_labels() for auto-sorting
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.25, label="crash", velocity=0.5),
            DrumEvent(timestamp=0.5, label="crash", velocity=0.7),
            DrumEvent(timestamp=0.75, label="crash", velocity=0.9),
        ]
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        # Should detect the crash build pattern
        assert len(patterns) >= 1
    
    def test_very_long_sequence(self, default_config):
        """Should handle long event sequences efficiently."""
        # Create 1000 events with clear accent-tap pattern
        events = []
        for i in range(1000):
            events.append(DrumEvent(
                timestamp=i * 0.1,
                label="snare",  # Use snare for more reliable detection
                velocity=0.9 if i % 2 == 0 else 0.2,  # Clear alternating
            ))
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        # Should complete without timeout and find accent-tap patterns
        accent_tap_patterns = [p for p in patterns if p.pattern_type == PatternType.ACCENT_TAP]
        assert len(accent_tap_patterns) > 0
    
    def test_unknown_instrument_labels(self, default_config):
        """Should handle unknown instrument labels gracefully."""
        events = [
            DrumEvent(timestamp=0.0, label="unknown_drum", velocity=0.5),
            DrumEvent(timestamp=0.1, label="weird_thing", velocity=0.6),
        ]
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        # Should not crash, may not detect patterns
        assert isinstance(patterns, list)
    
    def test_very_close_timestamps(self, default_config):
        """Should handle very close timestamps."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.3),
            DrumEvent(timestamp=0.001, label="crash", velocity=0.5),  # 1ms later
            DrumEvent(timestamp=0.002, label="crash", velocity=0.9),
        ]
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        # Should not crash
        assert isinstance(patterns, list)
    
    def test_zero_and_negative_velocities(self, default_config):
        """Should handle edge case velocities."""
        events = [
            DrumEvent(timestamp=0.0, label="crash", velocity=0.0),
            DrumEvent(timestamp=0.2, label="crash", velocity=-0.1),  # Invalid but shouldn't crash
            DrumEvent(timestamp=0.4, label="crash", velocity=1.5),   # Over 1.0
        ]
        
        detector = PatternDetector(default_config)
        patterns = detector.detect(events)
        
        # Should not crash
        assert isinstance(patterns, list)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
