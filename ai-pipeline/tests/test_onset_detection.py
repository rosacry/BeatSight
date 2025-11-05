import numpy as np
import pytest
import librosa

from pipeline.transcription.onset_detector import detect_onsets, refine_onsets
from pipeline.beatmap_generator import _select_best_quantization

SR = 44100
BPM = 178


def synth_drum_excerpt(bpm: float = BPM, bars: int = 2, subdivision: int = 4, ghost_ratio: float = 0.35):
    """Generate a synthetic drum pattern with optional softer ghost hits."""
    beats_per_bar = 4
    beat_interval = 60.0 / bpm
    step = beat_interval / subdivision
    total_steps = beats_per_bar * bars * subdivision

    primary_times = np.arange(total_steps) * step
    length = int((primary_times[-1] + 1.0) * SR)
    click = 0.8 * librosa.clicks(times=primary_times, sr=SR, click_duration=0.01, click_freq=2000, length=length)

    # Add occasional softer ghost hits to test sensitivity handling.
    rng = np.random.default_rng(1234)
    ghost_mask = rng.random(total_steps) < ghost_ratio
    ghost_times = primary_times[ghost_mask] + 0.5 * step
    ghost_clicks = 0.35 * librosa.clicks(times=ghost_times, sr=SR, click_duration=0.008, click_freq=1600, length=len(click))

    audio = click.copy()
    audio[: len(ghost_clicks)] += ghost_clicks

    # Normalize to avoid clipping.
    if np.max(np.abs(audio)) > 0:
        audio /= np.max(np.abs(audio))

    return audio.astype(np.float32)


def simple_threshold_peak_pick(envelope: np.ndarray, threshold: float, min_frames: int = 3):
    """Naive fixed-threshold peak picker for comparison."""
    peaks = []
    last_idx = -min_frames
    for idx, value in enumerate(envelope):
        if value < threshold or idx - last_idx < min_frames:
            continue
        local_slice = envelope[max(0, idx - 1): idx + 2]
        if value >= np.max(local_slice):
            peaks.append(idx)
            last_idx = idx
    return peaks


def test_min_ioi_respected():
    audio = synth_drum_excerpt()
    detection = detect_onsets((audio, SR), sensitivity=85, tempo_hint=BPM)
    refined = refine_onsets((audio, SR), detection.onsets)

    times = np.array([onset.time for onset in refined])
    assert len(times) >= 30  # expect close to 32 sixteenth notes

    diffs = np.diff(times)
    expected_step = 60 / (BPM * 4)
    # pytest.approx no longer supports inequality comparisons, so compare against the
    # lower bound implied by the relative tolerance to ensure minimum spacing.
    assert np.min(diffs) >= expected_step * 0.8


def test_adaptive_threshold_beats_fixed():
    audio = synth_drum_excerpt(ghost_ratio=0.5)
    detection = detect_onsets((audio, SR), sensitivity=60, tempo_hint=BPM)

    adaptive_count = len(detection.onsets)
    fixed_peaks = simple_threshold_peak_pick(detection.envelope, threshold=0.55)

    assert adaptive_count > len(fixed_peaks)


def test_quantization_error_shrinks_with_sensitivity():
    audio = synth_drum_excerpt(ghost_ratio=0.4)

    low = detect_onsets((audio, SR), sensitivity=25, tempo_hint=BPM)
    high = detect_onsets((audio, SR), sensitivity=85, tempo_hint=BPM)

    low_refined = refine_onsets((audio, SR), low.onsets)
    high_refined = refine_onsets((audio, SR), high.onsets)

    low_times = np.array([o.time for o in low_refined])
    high_times = np.array([o.time for o in high_refined])

    quant_low = _select_best_quantization(low_times, [BPM], "sixteenth", 0.012)
    quant_high = _select_best_quantization(high_times, [BPM], "sixteenth", 0.012)

    assert quant_high["coverage"] >= quant_low["coverage"]
    assert quant_high["mean_error"] <= quant_low["mean_error"] + 1e-5


def test_host_tempo_hint_has_priority_over_detection_candidates():
    times = np.arange(0.0, 2.0, 0.5, dtype=float)

    detection_candidates = [240.0, 120.0]
    baseline = _select_best_quantization(times, detection_candidates, "sixteenth", 0.01)
    assert baseline["bpm"] == pytest.approx(240.0)

    combined_candidates = [120.0, 240.0]
    biased = _select_best_quantization(times, combined_candidates, "sixteenth", 0.01, hint_count=1)

    assert biased["bpm"] == pytest.approx(120.0)
    assert biased["candidates"][0]["hint"] is True


def test_hint_falls_back_when_coverage_poor():
    # Times align with a 90 BPM grid; a 120 BPM hint should incur large errors.
    step = 60.0 / (90.0 * 4)
    times = np.arange(0.0, 4.0, step, dtype=float)

    candidates = [120.0, 90.0]
    result = _select_best_quantization(times, candidates, "sixteenth", 0.01, hint_count=1)

    assert result["bpm"] == pytest.approx(90.0)
    # Candidate summaries should still include the original hint for diagnostics.
    assert any(item["hint"] for item in result["candidates"])
