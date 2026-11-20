"""Safety and ambiguous-collision contract tests, independent of development scores."""
from copy import deepcopy
import pytest
from compare_snare_addition import add_snares, scoped_root
from pathlib import Path


def chart(*events):
    return {'metadata': {'preserve': True}, 'hitObjects': list(events)}


def hit(t, component='snare', native=False):
    return dict(time=t, component=component, **({'groove_pitch': 38, 'velocity': 80} if native else {'custom': 'unchanged'}))


def test_all_original_fields_and_duplicates_preserved_without_mutation():
    baseline = chart(hit(100), hit(100), hit(100, 'china'), hit(200, 'cross_stick'))
    native = chart(hit(200, native=True)); originals = deepcopy((baseline, native))
    result, decisions = add_snares(baseline, native)
    assert (baseline, native) == originals
    assert result == chart(*baseline['hitObjects'], native['hitObjects'][0])
    assert decisions[0]['decision'] == 'accepted'


def test_inclusive_boundary_and_future_baseline_priority():
    result, decisions = add_snares(chart(hit(100)), chart(hit(49.999, native=True), hit(50, native=True), hit(150, native=True), hit(150.001, native=True)))
    assert [d['decision'] for d in decisions] == ['accepted', 'baseline_collision', 'baseline_collision', 'accepted']
    assert [h['time'] for h in result['hitObjects']] == [49.999, 100, 150.001]


def test_earliest_accepted_wins_and_rejected_event_does_not_block():
    native = chart(hit(80, native=True), hit(40, native=True), hit(0, native=True), hit(0, native=True))
    result, decisions = add_snares(chart(), native)
    assert [h['time'] for h in result['hitObjects']] == [0, 80]
    assert [d['native_event_index'] for d in decisions] == [2, 3, 1, 0]
    assert decisions[2]['addition_blocker_native_indices'] == [2]


def test_other_families_never_collide_and_only_native_pitch_38_is_added():
    native = chart(hit(0, native=True), {'time': 200, 'component': 'snare', 'groove_pitch': 40}, {'time': 300, 'component': 'tom_mid', 'groove_pitch': 48})
    result, decisions = add_snares(chart(hit(0, 'kick'), hit(0, 'hihat_closed')), native)
    assert len(result['hitObjects']) == 3 and len(decisions) == 1


@pytest.mark.parametrize('t', [float('nan'), float('inf'), -1])
def test_invalid_time_rejected(t):
    with pytest.raises(ValueError):
        add_snares(chart(), chart(hit(t, native=True)))


def test_mapping_drift_and_non_scoped_roots_rejected():
    with pytest.raises(ValueError):
        add_snares(chart(), chart(hit(0, 'tom_mid', native=True)))
    for p in ['D:/experiment', 'F:/experiment', 'C:/', 'C:/Users/10ros/BeatSight-Recovery']:
        with pytest.raises(ValueError):
            scoped_root(Path(p))
