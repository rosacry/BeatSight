"""Guard the benchmark boundary between Groove pitches and MDB families."""
import pytest
from compare_oaf_drums import notes_to_chart
from evaluate_mdb import drum_family


def test_groove_overrides_and_unknown_events_are_retained():
    chart = notes_to_chart([[.1, .15, p, 80] for p in [22, 26, 37, 48, 53, 58, 75, 108]])
    assert [drum_family(h['component']) for h in chart['hitObjects']] == [
        'HH', 'HH', 'OT', 'TT', 'CY', 'TT', 'OT', 'OT']
    assert len(chart['hitObjects']) == 8


def test_adjacent_frames_and_simultaneous_family_duplicates_survive():
    chart = notes_to_chart([[i * 512 / 44100, .1, p, 1]
                           for i, p in [(0, 36), (0, 35), (1, 36), (2, 36)]])
    assert len(chart['hitObjects']) == 4
    assert all(drum_family(h['component']) == 'KD' for h in chart['hitObjects'])
    assert chart['hitObjects'][2]['time'] == pytest.approx(512 / 44.1)
    with pytest.raises(ValueError):
        notes_to_chart([[0, .05, 109, 80]])
