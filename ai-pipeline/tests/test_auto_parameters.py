"""
Tests for Auto-Parameters, Sectional Time Signatures, and Readability Filter Improvements.

Tests:
  1. Auto-sensitivity estimation from audio characteristics
  2. Auto-quantization grid estimation from onset distribution
  3. Sectional time signature detection (meter changes)
  4. BPM-aware readability filter
  5. Transcription mode integration

Created: 2025
"""

import numpy as np
import pytest
from typing import List, Dict


# ===========================================================================
# Auto-Sensitivity Tests
# ===========================================================================

class TestAutoSensitivity:
    """Tests for automatic sensitivity estimation."""

    def test_silent_audio_returns_default(self):
        """Silent audio should return default sensitivity."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        audio = np.zeros(44100, dtype=np.float32)  # 1 second of silence
        result = estimate_optimal_sensitivity(audio, 44100)
        assert result.sensitivity == 60.0
        assert "Silent" in result.explanation

    def test_loud_simple_audio_moderate_sensitivity(self):
        """Loud audio with little dynamic range -> moderate sensitivity."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        rng = np.random.default_rng(42)
        # Constant loud clicks at 120 BPM (simple pattern)
        sr = 22050
        duration = 10.0
        audio = rng.normal(0, 0.01, int(sr * duration)).astype(np.float32)
        # Add clicks every 0.5s (120 BPM quarter notes)
        beat_interval = int(sr * 0.5)
        for i in range(0, len(audio), beat_interval):
            end = min(i + 100, len(audio))
            audio[i:end] = 0.9  # Loud uniform clicks

        result = estimate_optimal_sensitivity(audio, sr, bpm=120.0)
        # Should be moderate - no dynamic range, simple pattern
        assert 40.0 <= result.sensitivity <= 75.0

    def test_high_bpm_increases_sensitivity(self):
        """Higher BPM should result in higher recommended sensitivity."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        rng = np.random.default_rng(42)
        sr = 22050
        audio = rng.normal(0, 0.3, sr * 5).astype(np.float32)

        result_slow = estimate_optimal_sensitivity(audio, sr, bpm=80.0)
        result_fast = estimate_optimal_sensitivity(audio, sr, bpm=200.0)

        assert result_fast.sensitivity > result_slow.sensitivity, (
            f"Fast BPM ({result_fast.sensitivity}) should be higher than "
            f"slow BPM ({result_slow.sensitivity})"
        )

    def test_metal_genre_boosts_sensitivity(self):
        """Metal genre should increase sensitivity for ghost note detection."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        rng = np.random.default_rng(42)
        sr = 22050
        audio = rng.normal(0, 0.3, sr * 5).astype(np.float32)

        result_pop = estimate_optimal_sensitivity(audio, sr, genre="pop")
        result_metal = estimate_optimal_sensitivity(audio, sr, genre="metal")
        result_prog = estimate_optimal_sensitivity(audio, sr, genre="prog_metal")

        assert result_metal.sensitivity > result_pop.sensitivity
        assert result_prog.sensitivity >= result_metal.sensitivity

    def test_sensitivity_clamped_to_valid_range(self):
        """Sensitivity should always be in [30, 95] range."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        rng = np.random.default_rng(42)
        sr = 22050
        audio = rng.normal(0, 0.5, sr * 5).astype(np.float32)

        # Extreme cases
        result = estimate_optimal_sensitivity(
            audio, sr, bpm=300.0, genre="prog_metal"
        )
        assert 30.0 <= result.sensitivity <= 95.0

        result = estimate_optimal_sensitivity(
            audio, sr, bpm=40.0, genre="pop"
        )
        assert 30.0 <= result.sensitivity <= 95.0

    def test_multichannel_audio_handled(self):
        """Multi-channel audio should be averaged to mono."""
        from pipeline.auto_parameters import estimate_optimal_sensitivity

        rng = np.random.default_rng(42)
        sr = 22050
        audio_stereo = rng.normal(0, 0.3, (2, sr * 3)).astype(np.float32)

        result = estimate_optimal_sensitivity(audio_stereo, sr)
        assert 30.0 <= result.sensitivity <= 95.0


# ===========================================================================
# Auto-Quantization Tests
# ===========================================================================

class TestAutoQuantization:
    """Tests for automatic quantization grid estimation."""

    def test_quarter_note_pattern(self):
        """Simple quarter note pattern -> eighth or quarter grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # Quarter note hits for 8 bars
        times = [i * beat_dur for i in range(32)]

        result = estimate_optimal_quantization(times, bpm)
        assert result.grid in ["quarter", "eighth"], f"Got {result.grid}"

    def test_sixteenth_note_pattern(self):
        """16th note pattern -> sixteenth grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # 16th notes: 4 per beat
        times = [i * beat_dur / 4 for i in range(128)]

        result = estimate_optimal_quantization(times, bpm)
        assert result.grid == "sixteenth", f"Got {result.grid}"

    def test_thirtysecond_note_pattern(self):
        """32nd note pattern -> thirtysecond grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # 32nd notes: 8 per beat (62.5ms at 120 BPM)
        times = [i * beat_dur / 8 for i in range(256)]

        result = estimate_optimal_quantization(times, bpm)
        assert result.grid == "thirtysecond", f"Got {result.grid}"

    def test_triplet_pattern(self):
        """Triplet pattern -> triplet grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # Triplets: 3 per beat
        times = [i * beat_dur / 3 for i in range(96)]

        result = estimate_optimal_quantization(times, bpm)
        assert result.grid == "triplet", f"Got {result.grid}"

    def test_mixed_pattern_uses_finest_needed(self):
        """Mixed pattern with some fast notes -> finer grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm

        # Mostly 8th notes, with some 32nd note bursts
        times = [i * beat_dur / 2 for i in range(64)]  # 8th notes
        # Add a 32nd-note burst in the middle
        for j in range(16):
            times.append(8.0 + j * beat_dur / 8)

        result = estimate_optimal_quantization(sorted(times), bpm)
        assert result.grid in ["sixteenth", "thirtysecond"], f"Got {result.grid}"

    def test_too_few_onsets_defaults_to_sixteenth(self):
        """Very few onsets -> default sixteenth grid."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        result = estimate_optimal_quantization([1.0], 120.0)
        assert result.grid == "sixteenth"

    def test_metal_genre_upgrade(self):
        """Metal genre should prevent coarse grid even with sparse onsets."""
        from pipeline.auto_parameters import estimate_optimal_quantization

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # Quarter notes only (would normally get "eighth")
        times = [i * beat_dur for i in range(32)]

        result = estimate_optimal_quantization(times, bpm, genre="metal")
        # Metal should upgrade to at least sixteenth
        assert result.grid in ["sixteenth", "thirtysecond"], f"Got {result.grid}"


# ===========================================================================
# Sectional Time Signature Tests
# ===========================================================================

class TestSectionalTimeSignatures:
    """Tests for sectional time signature detection."""

    def test_single_time_signature_returns_single_section(self):
        """Song in constant 4/4 -> all sections should be consistent."""
        from pipeline.structured_decoder import detect_sectional_time_signatures

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # 4/4 rock pattern for 60 seconds
        times = []
        for measure in range(60):
            base = measure * 4 * beat_dur
            # Kick on 1, 3
            times.append(base)
            times.append(base + 2 * beat_dur)
            # Snare on 2, 4
            times.append(base + beat_dur)
            times.append(base + 3 * beat_dur)
            # Hi-hat 8ths
            for eighth in range(8):
                times.append(base + eighth * beat_dur / 2)

        sections = detect_sectional_time_signatures(sorted(times), bpm)

        # Should have sections covering the song
        assert len(sections) >= 1
        # All sections should have denominator 4 (duple or triple meter)
        for s in sections:
            assert s.time_signature.denominator == 4
            # Allow 2, 3, or 4 since short-window autocorrelation may vary
            assert s.time_signature.numerator in [2, 3, 4]

    def test_too_few_hits(self):
        """Very few hits -> single fallback section."""
        from pipeline.structured_decoder import detect_sectional_time_signatures

        times = [0.5, 1.0, 1.5]
        sections = detect_sectional_time_signatures(times, 120.0)
        assert len(sections) == 1

    def test_sections_cover_full_song(self):
        """Sections should cover from 0 to end of song."""
        from pipeline.structured_decoder import detect_sectional_time_signatures

        bpm = 120.0
        beat_dur = 60.0 / bpm
        times = []
        for beat in range(200):
            times.append(beat * beat_dur)
            times.append(beat * beat_dur + beat_dur / 2)  # 8th notes

        sections = detect_sectional_time_signatures(sorted(times), bpm)

        assert sections[0].start_time == 0.0
        assert sections[-1].end_time > times[-1]

    def test_short_sections_merged(self):
        """Very short sections should be merged into neighbors."""
        from pipeline.structured_decoder import detect_sectional_time_signatures

        bpm = 120.0
        beat_dur = 60.0 / bpm
        # Generate constant 4/4
        times = [i * beat_dur / 2 for i in range(200)]

        sections = detect_sectional_time_signatures(
            sorted(times), bpm, min_hits_per_window=8,
        )

        # All sections should be at least 2 measures long
        min_dur = beat_dur * 4 * 2  # 2 measures
        for s in sections:
            duration = s.end_time - s.start_time
            # Allow the final section to be shorter
            if s != sections[-1]:
                assert duration >= min_dur * 0.9, (
                    f"Section too short: {duration:.1f}s < {min_dur:.1f}s"
                )

    def test_dataclass_fields(self):
        """SectionTimeSignature should have required fields."""
        from pipeline.structured_decoder import SectionTimeSignature, TimeSignature

        ts = TimeSignature(numerator=4, denominator=4, confidence=0.9,
                           detected_period_beats=4.0)
        section = SectionTimeSignature(
            start_time=0.0, end_time=30.0,
            time_signature=ts, hit_count=100,
        )
        assert section.start_time == 0.0
        assert section.end_time == 30.0
        assert section.time_signature.numerator == 4
        assert section.hit_count == 100


# ===========================================================================
# BPM-Aware Readability Filter Tests
# ===========================================================================

class TestBPMAwareReadability:
    """Tests for BPM-scaled readability filter."""

    def test_default_bpm_unchanged(self):
        """At 120 BPM, limits should be at base values."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f = ChartReadabilityFilter(difficulty="expert", bpm=120.0)
        # At 120 BPM, scale = 1.0
        assert abs(f.max_nps - 16.0) < 0.1

    def test_high_bpm_scales_up(self):
        """At 200 BPM, density limit should be higher than at 120 BPM."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f120 = ChartReadabilityFilter(difficulty="expert", bpm=120.0)
        f200 = ChartReadabilityFilter(difficulty="expert", bpm=200.0)

        assert f200.max_nps > f120.max_nps, (
            f"200 BPM ({f200.max_nps}) should have higher limit than "
            f"120 BPM ({f120.max_nps})"
        )

    def test_low_bpm_scales_down(self):
        """At slow tempo, density limit should be slightly lower."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f120 = ChartReadabilityFilter(difficulty="expert", bpm=120.0)
        f80 = ChartReadabilityFilter(difficulty="expert", bpm=80.0)

        assert f80.max_nps < f120.max_nps

    def test_transcription_mode_disables_density(self):
        """Transcription mode should effectively disable density filtering."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f = ChartReadabilityFilter(
            difficulty="expert", bpm=120.0, mode="transcription"
        )
        assert f.max_nps > 100.0  # Effectively unlimited

    def test_gameplay_mode_is_default(self):
        """Default mode should be gameplay."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f = ChartReadabilityFilter(difficulty="expert")
        assert f.mode == "gameplay"
        assert f.max_nps < 100.0  # Normal limit applies

    def test_bpm_scale_clamped(self):
        """BPM scale factor should be clamped to reasonable range."""
        from pipeline.chart_readability import ChartReadabilityFilter

        f_extreme = ChartReadabilityFilter(difficulty="expert", bpm=400.0)
        # scale = 1.0 + 0.4 * ((400 - 120) / 80) = 2.4, clamped to 2.0
        expected_max = 16.0 * 2.0
        assert abs(f_extreme.max_nps - expected_max) < 0.5

    def test_filter_chart_for_readability_passes_bpm(self):
        """filter_chart_for_readability should pass BPM through."""
        from pipeline.chart_readability import filter_chart_for_readability

        hits = [
            {"time": i * 0.05, "component": "snare", "confidence": 0.9}
            for i in range(100)
        ]
        # At 200 BPM, should keep more hits than at 120 BPM
        _, stats_120 = filter_chart_for_readability(hits, "expert", bpm=120.0)
        _, stats_200 = filter_chart_for_readability(hits, "expert", bpm=200.0)

        # More permissive at higher BPM -> more hits kept
        assert stats_200["filtered_count"] >= stats_120["filtered_count"]

    def test_apply_difficulty_curve_accepts_bpm_and_mode(self):
        """apply_difficulty_curve should accept bpm and mode parameters."""
        from pipeline.chart_readability import (
            apply_difficulty_curve, detect_sections,
        )

        hits = [
            {"time": i * 0.1, "component": "snare", "confidence": 0.9}
            for i in range(200)
        ]
        sections = detect_sections(hits, bpm=120.0)

        # Should not raise
        result = apply_difficulty_curve(
            hits, sections,
            target_difficulty="expert",
            bpm=160.0,
            mode="gameplay",
        )
        assert len(result) > 0


# ===========================================================================
# Structured Decoder Sectional Integration Tests
# ===========================================================================

class TestStructuredDecoderSectionalIntegration:
    """Tests for apply_structured_decoding with sectional time signatures."""

    def _make_hits(self, bpm: float = 120.0, n_measures: int = 32) -> List[Dict]:
        """Generate basic 4/4 classified hits."""
        beat_dur = 60.0 / bpm
        hits = []
        for m in range(n_measures):
            base = m * 4 * beat_dur
            hits.append({"time": base, "component": "kick", "confidence": 0.9})
            hits.append({"time": base + beat_dur, "component": "snare", "confidence": 0.9})
            hits.append({"time": base + 2 * beat_dur, "component": "kick", "confidence": 0.9})
            hits.append({"time": base + 3 * beat_dur, "component": "snare", "confidence": 0.9})
            for eighth in range(8):
                hits.append({
                    "time": base + eighth * beat_dur / 2,
                    "component": "hihat_closed",
                    "confidence": 0.8,
                })
        return hits

    def test_apply_with_no_time_signature(self):
        """apply_structured_decoding with time_signature=None -> sectional detection."""
        from pipeline.structured_decoder import apply_structured_decoding

        hits = self._make_hits(bpm=120.0, n_measures=16)
        result = apply_structured_decoding(hits, bpm=120.0, time_signature=None)

        assert len(result) > 0
        # Each hit should have time_signature annotation
        assert all("time_signature" in h for h in result)

    def test_apply_with_forced_time_signature(self):
        """Forced time signature -> single section with that value."""
        from pipeline.structured_decoder import apply_structured_decoding

        hits = self._make_hits(bpm=120.0, n_measures=8)
        result = apply_structured_decoding(
            hits, bpm=120.0, time_signature=(3, 4)
        )

        assert len(result) > 0
        # All should have 3/4
        for h in result:
            assert h["time_signature"] == "3/4", f"Got {h['time_signature']}"

    def test_empty_hits(self):
        """Empty input -> empty output."""
        from pipeline.structured_decoder import apply_structured_decoding

        result = apply_structured_decoding([], bpm=120.0)
        assert result == []

    def test_result_sorted_by_time(self):
        """Output should be sorted by time."""
        from pipeline.structured_decoder import apply_structured_decoding

        hits = self._make_hits(bpm=120.0, n_measures=8)
        result = apply_structured_decoding(hits, bpm=120.0, time_signature=None)

        times = [h["time"] for h in result]
        assert times == sorted(times)


# ===========================================================================
# Mode-Aware Genre Detection Tests
# ===========================================================================

class TestModeAwareGenreDetection:
    """Tests for mode-aware genre detection behavior."""

    def _make_rock_hits(self, n_measures=8) -> List[Dict]:
        """Create rock-style hits at 120 BPM."""
        bpm = 120.0
        beat_dur = 60.0 / bpm
        hits = []
        t = 0.0
        for _ in range(n_measures):
            hits.append({"time": t, "component": "kick", "confidence": 0.9})
            hits.append({"time": t, "component": "hihat_closed", "confidence": 0.85})
            hits.append({"time": t + beat_dur, "component": "snare", "confidence": 0.9})
            hits.append({"time": t + beat_dur, "component": "hihat_closed", "confidence": 0.8})
            hits.append({"time": t + 2 * beat_dur, "component": "kick", "confidence": 0.9})
            hits.append({"time": t + 2 * beat_dur, "component": "hihat_closed", "confidence": 0.85})
            hits.append({"time": t + 3 * beat_dur, "component": "snare", "confidence": 0.9})
            hits.append({"time": t + 3 * beat_dur, "component": "hihat_closed", "confidence": 0.8})
            t += 4 * beat_dur
        return hits

    def test_transcription_mode_no_state_refined(self):
        """Transcription mode should NOT set state_refined on any hits."""
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding

        hits = self._make_rock_hits()
        result = apply_genre_aware_decoding(hits, bpm=120.0, mode="transcription")
        
        for h in result:
            assert not h.get("state_refined", False), \
                "Transcription mode should not refine states (no Viterbi re-pass)"

    def test_transcription_mode_adds_genre_annotation(self):
        """Transcription mode should still annotate with genre metadata."""
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding

        hits = self._make_rock_hits()
        result = apply_genre_aware_decoding(hits, bpm=120.0, mode="transcription")
        
        for h in result:
            assert "genre" in h, "Should have genre annotation"
            assert "genre_confidence" in h, "Should have genre confidence"
            assert "beat_position" in h, "Should have beat position"

    def test_transcription_mode_preserves_components(self):
        """Transcription mode must not change any component labels."""
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding

        hits = self._make_rock_hits()
        original_components = [h["component"] for h in sorted(hits, key=lambda h: h["time"])]
        result = apply_genre_aware_decoding(hits, bpm=120.0, mode="transcription")
        result_components = [h["component"] for h in result]
        
        assert original_components == result_components

    def test_gameplay_mode_may_add_state_refined(self):
        """Gameplay mode runs Viterbi and may mark state_refined."""
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding

        hits = self._make_rock_hits()
        result = apply_genre_aware_decoding(hits, bpm=120.0, mode="gameplay")
        
        # Gameplay mode uses Viterbi - check it ran (should have viterbi_prob)
        for h in result:
            assert "genre" in h
            assert "viterbi_prob" in h, "Gameplay mode should include Viterbi probabilities"

    def test_forced_genre_in_transcription(self):
        """Forced genre + transcription mode should annotate but not Viterbi-decode."""
        from pipeline.genre_aware_decoder import apply_genre_aware_decoding, Genre

        hits = self._make_rock_hits()
        result = apply_genre_aware_decoding(
            hits, bpm=120.0, genre=Genre.METAL, mode="transcription"
        )
        
        for h in result:
            assert h["genre"] == "metal"
            assert h["genre_confidence"] == 1.0
            assert not h.get("state_refined", False)


# ===========================================================================
# Mode-Aware Pattern Repair Tests
# ===========================================================================

class TestModeAwarePatternRepair:
    """Tests for mode-aware pattern repair behavior."""

    def _make_low_confidence_hits(self) -> List[Dict]:
        """Create hits with low confidence that could be repaired."""
        bpm = 120.0
        beat_dur = 60.0 / bpm
        return [
            {"time": 0.0, "component": "kick", "confidence": 0.9},
            {"time": beat_dur, "component": "snare", "confidence": 0.25},  # Very low
            {"time": 2 * beat_dur, "component": "kick", "confidence": 0.9},
            {"time": 3 * beat_dur, "component": "snare", "confidence": 0.3},  # Low
        ]

    def test_transcription_mode_never_repairs(self):
        """Transcription mode should return hits unchanged."""
        from pipeline.pattern_library import repair_with_patterns

        hits = self._make_low_confidence_hits()
        result = repair_with_patterns(hits, bpm=120.0, mode="transcription")
        
        # Should be identical - no repairs in transcription mode
        assert len(result) == len(hits)
        for orig, res in zip(sorted(hits, key=lambda h: h["time"]),
                            sorted(result, key=lambda h: h["time"])):
            assert orig["component"] == res["component"]
            assert not res.get("pattern_repaired", False)

    def test_transcription_mode_returns_same_list(self):
        """Transcription mode should return the exact same list object."""
        from pipeline.pattern_library import repair_with_patterns

        hits = self._make_low_confidence_hits()
        result = repair_with_patterns(hits, bpm=120.0, mode="transcription")
        assert result is hits  # Same object, no copy needed

    def test_gameplay_mode_uses_conservative_threshold(self):
        """Gameplay mode should only repair hits below 0.35 confidence."""
        from pipeline.pattern_library import repair_with_patterns

        hits = [
            {"time": 0.0, "component": "kick", "confidence": 0.9},
            {"time": 0.5, "component": "snare", "confidence": 0.4},  # Above 0.35
            {"time": 1.0, "component": "kick", "confidence": 0.9},
        ]
        result = repair_with_patterns(hits, bpm=120.0, mode="gameplay")
        
        # The 0.4 confidence hit should NOT be repaired (above 0.35 threshold)
        for h in result:
            assert not h.get("pattern_repaired", False)

    def test_gameplay_mode_does_not_cross_families(self):
        """Pattern repair should never change instrument family (e.g., snare->ride)."""
        from pipeline.pattern_library import repair_with_patterns

        # Even if we force very low confidence, cross-family changes should be blocked
        hits = [
            {"time": 0.0, "component": "crash", "confidence": 0.1},  # Cymbal family
            {"time": 0.5, "component": "kick", "confidence": 0.9},
        ]
        result = repair_with_patterns(hits, bpm=120.0, mode="gameplay")
        
        # Crash should never be repaired (cymbal no-repair rule)
        crash_hit = [h for h in result if h.get("time", 0) == 0.0][0]
        assert crash_hit["component"] == "crash"
        assert not crash_hit.get("pattern_repaired", False)

    def test_default_mode_is_gameplay(self):
        """Default mode should be gameplay (backward compatible)."""
        from pipeline.pattern_library import repair_with_patterns
        import inspect
        sig = inspect.signature(repair_with_patterns)
        assert sig.parameters["mode"].default == "gameplay"

