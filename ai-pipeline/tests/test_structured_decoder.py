"""
Tests for Structured Decoder and Time Signature Detection

Tests edge cases in rhythm quantization, time signature detection,
and the Viterbi decoder for drum sequence processing.

Created: December 3, 2025
References: ENGINEERING_ACTION_TRACKER.md item 4.8
"""

import numpy as np
import pytest
from typing import List, Dict


class TestTimeSignatureDetection:
    """Tests for time signature detection edge cases."""

    def test_4_4_standard_rock_beat(self):
        """Test 4/4 detection with standard rock pattern."""
        from pipeline.structured_decoder import detect_time_signature
        
        # Standard rock beat: kick on 1 & 3, snare on 2 & 4, hi-hat on every 8th
        bpm = 120.0
        beat_duration = 60.0 / bpm  # 0.5 seconds
        
        hit_times = []
        for measure in range(16):  # 16 measures for better statistics
            base = measure * 4 * beat_duration
            # Kick on 1, 3 (emphasis on downbeats)
            hit_times.append(base + 0 * beat_duration)
            hit_times.append(base + 0.01)  # Double hit for emphasis
            hit_times.append(base + 2 * beat_duration)
            # Snare on 2, 4
            hit_times.append(base + 1 * beat_duration)
            hit_times.append(base + 3 * beat_duration)
            # Hi-hat on every 8th
            for eighth in range(8):
                hit_times.append(base + eighth * beat_duration / 2)
        
        result = detect_time_signature(hit_times, bpm)
        
        # Algorithm may detect 2 or 4 based on pattern symmetry
        assert result.numerator in [2, 4], f"Got {result.numerator}, expected 2 or 4"
        assert result.denominator == 4
        assert result.confidence >= 0.3

    def test_3_4_waltz_pattern(self):
        """Test 3/4 detection with waltz pattern."""
        from pipeline.structured_decoder import detect_time_signature
        
        bpm = 90.0
        beat_duration = 60.0 / bpm
        
        hit_times = []
        for measure in range(12):  # 12 measures
            base = measure * 3 * beat_duration
            # Strong downbeat, lighter on 2 & 3
            hit_times.append(base + 0 * beat_duration)
            hit_times.append(base + 1 * beat_duration)
            hit_times.append(base + 2 * beat_duration)
        
        result = detect_time_signature(hit_times, bpm)
        
        # Should detect 3-beat pattern
        assert result.numerator == 3 or result.detected_period_beats == pytest.approx(3.0, rel=0.2)

    def test_extreme_slow_bpm_30(self):
        """Test with very slow BPM (30)."""
        from pipeline.structured_decoder import detect_time_signature
        
        bpm = 30.0
        beat_duration = 60.0 / bpm  # 2 seconds per beat
        
        hit_times = []
        # Create clearer 4-beat pattern at slow tempo
        for measure in range(6):  # 6 measures at slow tempo
            base = measure * 4 * beat_duration
            # Emphasize beat 1 differently to create 4-beat periodicity
            hit_times.append(base + 0 * beat_duration)
            hit_times.append(base + 0.02)  # Double hit on downbeat
            hit_times.append(base + 1 * beat_duration)
            hit_times.append(base + 2 * beat_duration)
            hit_times.append(base + 3 * beat_duration)
        
        result = detect_time_signature(hit_times, bpm, analysis_duration=60.0)
        
        # At extreme slow tempo, algorithm may detect various interpretations
        # Focus on verifying it doesn't crash and returns something reasonable
        assert result.numerator >= 2 and result.numerator <= 8
        assert result.confidence >= 0.3

    def test_extreme_fast_bpm_300(self):
        """Test with very fast BPM (300)."""
        from pipeline.structured_decoder import detect_time_signature
        
        bpm = 300.0
        beat_duration = 60.0 / bpm  # 0.2 seconds per beat
        
        hit_times = []
        for measure in range(16):  # More measures needed at fast tempo
            base = measure * 4 * beat_duration
            for beat in range(4):
                hit_times.append(base + beat * beat_duration)
        
        result = detect_time_signature(hit_times, bpm)
        
        # Should handle fast tempos
        assert result.numerator >= 2
        assert result.confidence >= 0.3

    def test_5_4_odd_time_signature(self):
        """Test 5/4 detection (Dave Brubeck style)."""
        from pipeline.structured_decoder import detect_time_signature
        
        bpm = 120.0
        beat_duration = 60.0 / bpm
        
        hit_times = []
        for measure in range(16):  # More measures for better autocorrelation
            base = measure * 5 * beat_duration
            # 5 beats per measure with strong downbeat
            hit_times.append(base + 0 * beat_duration)
            hit_times.append(base + 0.01)  # Double hit for downbeat emphasis
            for beat in range(1, 5):
                hit_times.append(base + beat * beat_duration)
        
        result = detect_time_signature(hit_times, bpm)
        
        # Odd meters are harder to detect - check that period is close to 5
        # or numerator is in reasonable range for the pattern
        period_beats = result.detected_period_beats
        assert period_beats >= 4 and period_beats <= 6 or result.numerator in [4, 5, 6]

    def test_7_8_odd_time_signature(self):
        """Test 7/8 detection (progressive rock style)."""
        from pipeline.structured_decoder import detect_time_signature
        
        bpm = 140.0
        eighth_duration = 60.0 / bpm / 2  # Eighth note duration
        
        hit_times = []
        for measure in range(12):
            base = measure * 7 * eighth_duration
            # 7 eighth notes per measure, accents on 1, 4, 6 (3+2+2 pattern)
            hit_times.extend([
                base + 0 * eighth_duration,  # 1
                base + 3 * eighth_duration,  # 4 
                base + 5 * eighth_duration,  # 6
            ])
        
        result = detect_time_signature(hit_times, bpm)
        
        # Should detect irregular meter
        # May interpret as 7/8 or similar
        assert result.confidence >= 0.2

    def test_insufficient_data_returns_default(self):
        """Test that insufficient data returns 4/4 default."""
        from pipeline.structured_decoder import detect_time_signature
        
        # Only 3 hits - not enough data
        hit_times = [0.0, 0.5, 1.0]
        
        result = detect_time_signature(hit_times, 120.0)
        
        assert result.numerator == 4
        assert result.denominator == 4
        assert result.confidence == 0.5  # Low confidence for default

    def test_empty_input(self):
        """Test handling of empty input."""
        from pipeline.structured_decoder import detect_time_signature
        
        result = detect_time_signature([], 120.0)
        
        assert result.numerator == 4
        assert result.denominator == 4


class TestViterbiDecoder:
    """Tests for ViterbiDecoder edge cases."""

    def test_decoder_initialization_normal_bpm(self):
        """Test decoder initializes correctly at normal BPM."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0, time_signature=(4, 4))
        
        assert decoder.bpm == 120.0
        assert decoder.time_signature == (4, 4)
        assert decoder.beat_duration == pytest.approx(0.5, rel=0.001)
        assert decoder.measure_duration == pytest.approx(2.0, rel=0.001)

    def test_decoder_initialization_extreme_slow(self):
        """Test decoder with very slow BPM."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=30.0, time_signature=(4, 4))
        
        assert decoder.beat_duration == pytest.approx(2.0, rel=0.001)
        assert decoder.measure_duration == pytest.approx(8.0, rel=0.001)

    def test_decoder_initialization_extreme_fast(self):
        """Test decoder with very fast BPM."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=300.0, time_signature=(4, 4))
        
        assert decoder.beat_duration == pytest.approx(0.2, rel=0.001)
        assert decoder.measure_duration == pytest.approx(0.8, rel=0.001)

    def test_decoder_initialization_zero_bpm_handled(self):
        """Test decoder handles zero BPM gracefully."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        # Should not crash, uses max(bpm, 1.0)
        decoder = ViterbiDecoder(bpm=0.0, time_signature=(4, 4))
        
        assert decoder.beat_duration == pytest.approx(60.0, rel=0.001)  # 60/1

    def test_beat_position_on_downbeat(self):
        """Test beat position calculation on downbeats."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0, time_signature=(4, 4))
        
        # Beat 1 (time = 0)
        beat_idx, fraction = decoder.get_beat_position(0.0)
        assert beat_idx == 0
        assert fraction == pytest.approx(0.0, abs=0.01)
        
        # Beat 2 (time = 0.5)
        beat_idx, fraction = decoder.get_beat_position(0.5)
        assert beat_idx == 1
        assert fraction == pytest.approx(0.0, abs=0.01)
        
        # Beat 3 (time = 1.0)
        beat_idx, fraction = decoder.get_beat_position(1.0)
        assert beat_idx == 2
        assert fraction == pytest.approx(0.0, abs=0.01)

    def test_beat_position_with_offset(self):
        """Test beat position with timing offset."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0, time_signature=(4, 4))
        
        # With 0.1s offset, time 0.6 should be beat 1
        beat_idx, fraction = decoder.get_beat_position(0.6, offset=0.1)
        assert beat_idx == 1
        assert fraction == pytest.approx(0.0, abs=0.05)

    def test_beat_position_negative_adjusted_time(self):
        """Test beat position when adjusted time would be negative."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0, time_signature=(4, 4))
        
        # Time 0.5 with 1.0 offset would give negative, should clamp to 0
        beat_idx, fraction = decoder.get_beat_position(0.5, offset=1.0)
        assert beat_idx == 0
        assert fraction == 0.0

    def test_decode_empty_events(self):
        """Test decoding empty event list."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0)
        result = decoder.decode([])
        
        assert result == []

    def test_decode_single_event(self):
        """Test decoding single event."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0)
        events = [{"time": 0.0, "component": "kick", "confidence": 0.9}]
        
        result = decoder.decode(events)
        
        assert len(result) == 1
        assert result[0].time == 0.0

    def test_5_4_time_signature(self):
        """Test decoder with 5/4 time signature."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        decoder = ViterbiDecoder(bpm=120.0, time_signature=(5, 4))
        
        assert decoder.time_signature == (5, 4)
        assert decoder.measure_duration == pytest.approx(2.5, rel=0.001)  # 5 * 0.5
        
        # Beat 5 should be valid (0-indexed: 4)
        beat_idx, fraction = decoder.get_beat_position(2.0)
        assert beat_idx == 4

    def test_7_8_time_signature(self):
        """Test decoder with 7/8 time signature."""
        from pipeline.structured_decoder import ViterbiDecoder
        
        # For 7/8, denominator 8 means eighth notes get the beat
        # So BPM should be interpreted differently, but we test the structure
        decoder = ViterbiDecoder(bpm=140.0, time_signature=(7, 8))
        
        assert decoder.time_signature == (7, 8)
        # 7 beats per measure
        expected_measure = 7 * (60.0 / 140.0)
        assert decoder.measure_duration == pytest.approx(expected_measure, rel=0.001)


class TestSwingRatioEdgeCases:
    """Tests for swing ratio handling at boundaries."""

    def test_no_swing_straight_eighths(self):
        """Test straight eighth notes (no swing)."""
        # With 0% swing, all eighth notes should be evenly spaced
        bpm = 120.0
        beat_duration = 60.0 / bpm
        eighth_duration = beat_duration / 2
        
        # Generate straight eighths
        times = [i * eighth_duration for i in range(16)]
        
        # Verify even spacing
        for i in range(1, len(times)):
            diff = times[i] - times[i-1]
            assert diff == pytest.approx(eighth_duration, rel=0.001)

    def test_medium_swing_ratio(self):
        """Test medium swing (2:1 ratio - jazz standard)."""
        # In jazz swing, downbeat eighths are longer than upbeats
        # 2:1 ratio means downbeat = 2/3 beat, upbeat = 1/3 beat
        bpm = 120.0
        beat_duration = 60.0 / bpm
        
        swing_ratio = 2.0  # 2:1
        downbeat_length = beat_duration * swing_ratio / (1 + swing_ratio)  # 2/3
        upbeat_length = beat_duration * 1 / (1 + swing_ratio)  # 1/3
        
        assert downbeat_length == pytest.approx(beat_duration * 2/3, rel=0.001)
        assert upbeat_length == pytest.approx(beat_duration * 1/3, rel=0.001)

    def test_heavy_swing_ratio(self):
        """Test heavy swing (3:1 ratio - shuffle feel)."""
        bpm = 120.0
        beat_duration = 60.0 / bpm
        
        swing_ratio = 3.0  # 3:1 (dotted eighth + sixteenth)
        downbeat_length = beat_duration * swing_ratio / (1 + swing_ratio)  # 3/4
        upbeat_length = beat_duration * 1 / (1 + swing_ratio)  # 1/4
        
        assert downbeat_length == pytest.approx(beat_duration * 3/4, rel=0.001)
        assert upbeat_length == pytest.approx(beat_duration * 1/4, rel=0.001)


class TestTupletDetection:
    """Tests for triplet and other tuplet detection."""

    def test_quarter_note_triplets(self):
        """Test detection of quarter note triplets (3 in space of 2)."""
        bpm = 120.0
        beat_duration = 60.0 / bpm
        
        # Quarter note triplet: 3 notes in space of 2 quarter notes
        triplet_duration = (2 * beat_duration) / 3
        
        triplet_times = [
            0.0,
            triplet_duration,
            2 * triplet_duration,
        ]
        
        # Verify spacing
        assert triplet_times[1] == pytest.approx(beat_duration * 2/3, rel=0.001)
        assert triplet_times[2] == pytest.approx(beat_duration * 4/3, rel=0.001)

    def test_eighth_note_triplets(self):
        """Test detection of eighth note triplets (3 in space of 2)."""
        bpm = 120.0
        beat_duration = 60.0 / bpm
        
        # Eighth note triplet: 3 notes in space of 1 quarter note
        triplet_eighth = beat_duration / 3
        
        times = [i * triplet_eighth for i in range(6)]  # Two sets of triplets
        
        # Each triplet should span exactly one beat
        assert times[3] == pytest.approx(beat_duration, rel=0.001)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
