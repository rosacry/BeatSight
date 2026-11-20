"""Independent checks for the reference audit's time axes."""
import numpy as np
import pytest

from audit_clone_hero_reference import attack_envelope, attack_profile, independent_chart_clock, compare_decoder_window
from build_reference_admission_review import snare_click_overlay


@pytest.mark.parametrize("sr", [44100, 48000])
@pytest.mark.parametrize("shift", [-.04, 0, .035])
def test_audio_attack_lag_sign_and_absolute_clock(sr, shift):
    rng = np.random.default_rng(7)
    y = np.zeros((3 * sr, 2))
    hits = [.5, 1.5, 2.5]
    for hit in hits:
        start, count = round((hit + shift) * sr), round(.06 * sr)
        envelope = np.exp(-np.arange(count) / (.008 * sr))
        y[start:start + count] = rng.normal(size=(count, 2)) * envelope[:, None]
    times, rises = attack_envelope(y, sr)
    result = attack_profile(times, rises, hits)
    assert result["peak_lag_ms"] == pytest.approx(shift * 1000, abs=1.5)
    assert result["individual_support_within_10_ms"] == 1


def test_independent_tempo_changes_and_metadata_shift(tmp_path):
    chart = tmp_path / "notes.chart"
    chart.write_text('[Song]\n{\nResolution = 192\n}\n[SyncTrack]\n{\n0 = B 120000\n384 = B 60000\n}\n')
    events = [{"tick": 192, "time_seconds": .51}, {"tick": 576, "time_seconds": 2.01}]
    result = independent_chart_clock(chart, events, .01)
    assert result["status"] == "pass"
    events[-1]["time_seconds"] += .04
    assert independent_chart_clock(chart, events, .01)["status"] == "FAIL"


def test_clock_refuses_unhandled_anchors(tmp_path):
    chart = tmp_path / "notes.chart"
    chart.write_text('[Song]\n{Resolution = 192}\n[SyncTrack]\n{0 = B 120000\n192 = A 500000\n}')
    with pytest.raises(ValueError, match="Anchor"):
        independent_chart_clock(chart, [{"tick": 192, "time_seconds": .5}], 0)


def test_decoder_comparison_does_not_invent_lag_for_silence():
    result = compare_decoder_window(np.zeros(1000), np.zeros(1000), 44100)
    assert result["best_lag_samples"] is None
    assert result["zero_lag_correlation"] is None


def test_decoder_comparison_detects_sample_shift():
    rng = np.random.default_rng(42)
    a = rng.normal(size=10000).astype(np.float32)
    b = np.r_[np.zeros(17), a[:-17]].astype(np.float32)
    assert compare_decoder_window(a, b, 44100)["best_lag_samples"] == 17


def test_trial_click_starts_at_signed_shift_without_shifting_audio():
    sr = 48000
    y = np.full((sr, 2), .02, dtype=np.float32)
    overlay, meta = snare_click_overlay(y, sr, [.5], -.04)
    differences = np.flatnonzero(np.any(np.abs(overlay - y) > 1e-7, axis=1))
    assert differences[0] == 22080  # .460 seconds exactly
    assert meta["click_sample_indices"] == [22080]
    assert np.array_equal(overlay[:22080], y[:22080])
    assert np.array_equal(overlay[23000:], y[23000:])


def test_trial_click_does_not_wrap_negative_time_to_clip_end():
    y = np.zeros((48000, 2), dtype=np.float32)
    overlay, meta = snare_click_overlay(y, 48000, [.02], -.04)
    assert not overlay.any()
    assert not meta["click_sample_indices"]
