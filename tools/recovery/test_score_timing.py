import pytest

from score_timing import evaluate_timing, match_timing


def test_duplicate_predictions_do_not_double_count():
    result = match_timing([1.0], [1.0, 1.0])
    assert (result['tp'], result['fp'], result['fn']) == (1, 1, 0)


def test_maximum_cardinality_precedes_closest_pair():
    result = match_timing([0.0, 0.04], [0.03, 0.08])
    assert result['tp'] == 2
    assert result['signed_errors_seconds'] == pytest.approx([0.03, 0.04])


def test_timing_chooses_nearest_among_equally_large_matchings():
    result = match_timing([1.0, 1.01], [1.009])
    assert (result['tp'], result['fn']) == (1, 1)
    assert result['signed_errors_seconds'] == pytest.approx([-0.001])


def test_wrong_instrument_is_false_positive_and_false_negative():
    result = evaluate_timing({'hitObjects': [{'time': 1000, 'component': 'snare'}]}, {'KD': [1.0]})
    assert result['micro']['tp'] == 0
    assert result['micro']['fp'] == 1
    assert result['micro']['fn'] == 1
    assert result['timing']['median_absolute_ms'] is None


def test_tolerance_boundary_and_nonfinite_times():
    assert match_timing([0.0], [0.05])['tp'] == 1
    assert match_timing([0.0], [0.0501])['tp'] == 0
    with pytest.raises(ValueError):
        match_timing([float('nan')], [0.0])


def test_empty_predictions_and_references():
    assert match_timing([], [1.0])['fp'] == 1
    assert match_timing([1.0], [])['fn'] == 1
    assert match_timing([], [])['tp'] == 0
