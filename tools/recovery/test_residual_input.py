"""Guard timeline/gain reconstruction and the frozen decision against regressions."""
import numpy as np
import pytest

from probe_residual_input import blend_input, acceptance, event_assignments


def test_residual_input_preserves_sample_positions_and_does_not_clip():
    mix = np.zeros((2, 20), dtype=np.float32)
    mix[:, 4] = [2, 0]
    mix[:, 12] = [.5, .5]
    stem = np.zeros(20, dtype=np.float32)
    stem[4] = 1.5
    candidate, peak = blend_input(mix, stem)
    assert peak == 1
    assert np.array_equal(np.flatnonzero(candidate), [4, 12])
    assert candidate[4] == 1.375 and candidate[12] == .125
    with pytest.raises(ValueError, match='timelines'):
        blend_input(mix, stem[:-1])
    with pytest.raises(ValueError, match='Silent'):
        blend_input(mix * 0, stem)
    mix[0, 0] = np.nan
    with pytest.raises(ValueError, match='Nonfinite'):
        blend_input(mix, stem)


def test_track_regression_cannot_hide_behind_pooled_gain():
    baseline = {'micro': {'f1': .7, 'precision': .8}, 'by_family': {'TT': {'tp': 30}, 'SD': {'recall': .6}}}
    candidate = {'micro': {'f1': .72, 'precision': .8}, 'by_family': {'TT': {'tp': 31}, 'SD': {'recall': .61}}}
    assert acceptance(baseline, candidate, [.02, -.01])['passes_development_gate']
    assert not acceptance(baseline, candidate, [.03, -.021])['passes_development_gate']


def test_event_audit_keeps_duplicate_targets_one_to_one_and_empty_families():
    chart = {'hitObjects': [{'time': 1010, 'component': 'tom'}, {'time': 1500, 'component': 'kick'}]}
    result = event_assignments(chart, {'TT': [1.0, 1.0], 'SD': [2.0]}, .05)
    assert sum(e['matched_prediction'] is not None for e in result['TT']['reference']) == 1
    assert result['KD']['unmatched_predictions'] == [1.5]
    assert result['SD']['reference'][0]['matched_prediction'] is None
