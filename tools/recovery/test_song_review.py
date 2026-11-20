"""Protect review evidence from duplicate matches and silent export changes."""
from copy import deepcopy

import pytest

from package_song import verify_exported_notes
from review_song import match_indices


def test_review_matching_prefers_two_valid_pairs_over_one_nearest_pair():
    matches = match_indices([1000, 1060], [1040, 1100], tolerance=50)
    assert {(i, j) for i, j, _ in matches} == {(0, 0), (1, 1)}


def test_review_matching_does_not_reuse_an_onset():
    matches = match_indices([1000, 1000], [1000], tolerance=50)
    assert len(matches) == 1


def test_stereo_package_rejects_tampered_notes_and_preserves_simultaneous_hits():
    predictions = {"hitObjects": [
        {"time": 1000.0, "component": "kick"},
        {"time": 1000.0, "component": "hihat"},
    ]}
    chart = {"hitObjects": [
        {"time": 1000, "component": "kick", "velocity": 0.8},
        {"time": 1000, "component": "hihat_closed", "velocity": 0.8},
    ]}
    verify_exported_notes(chart, predictions)
    for key, value in [("time", 1010), ("component", "crash")]:
        altered = deepcopy(chart)
        altered["hitObjects"][1][key] = value
        with pytest.raises(ValueError, match="hash-verified"):
            verify_exported_notes(altered, predictions)
    chart["hitObjects"].pop()
    with pytest.raises(ValueError, match="hash-verified"):
        verify_exported_notes(chart, predictions)
