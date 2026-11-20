from copy import deepcopy

import pytest

from apply_song_feedback import apply_edits


def test_cymbal_correction_preserves_simultaneous_kick_and_source():
    chart = {"hitObjects": [
        {"time": 8750, "component": "kick", "velocity": 0.8},
        {"time": 8750, "component": "hihat_closed", "velocity": 0.8},
        {"time": 8750, "component": "crash", "velocity": 0.8},
        {"time": 9080, "component": "hihat_closed", "velocity": 0.8}]}
    original = deepcopy(chart)
    corrected = apply_edits(chart, [{"operation": "remove", "time_ms": 8750, "from_component": "hihat_closed"}])
    assert chart == original
    assert corrected["hitObjects"] == [original["hitObjects"][i] for i in (0, 2, 3)]


def test_china_relabel_does_not_shift_time_or_leave_duplicate():
    chart = {"hitObjects": [{"time": 1000, "component": c, "velocity": 0.8}
                            for c in ("hihat_closed", "crash")]}
    corrected = apply_edits(chart, [
        {"operation": "remove", "time_ms": 1000, "from_component": "hihat_closed"},
        {"operation": "relabel", "time_ms": 1000, "from_component": "crash", "to_component": "china"}])
    assert corrected["hitObjects"] == [{"time": 1000, "component": "china", "velocity": 0.8}]


@pytest.mark.parametrize("notes", [[], [{"time": 1000, "component": "crash"}] * 2])
def test_ambiguous_or_missing_note_is_rejected(notes):
    with pytest.raises(ValueError, match="exactly one"):
        apply_edits({"hitObjects": notes}, [{"operation": "remove", "time_ms": 1000, "from_component": "crash"}])
