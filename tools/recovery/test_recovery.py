from pathlib import Path

import pytest

from evaluate_mdb import drum_family, match_events
from transcribe import preflight, validate_inference


def test_existing_output_is_never_overwritten(tmp_path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"original audio")
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "chart.bsm"
    sentinel.write_text("original chart")
    with pytest.raises(FileExistsError):
        preflight(audio, output)
    assert sentinel.read_text() == "original chart"
    assert audio.read_bytes() == b"original audio"


def test_matching_does_not_reuse_a_reference_onset():
    result = match_events([1.0], [0.99, 1.01])
    assert (result["tp"], result["fp"], result["fn"]) == (1, 1, 0)


@pytest.mark.parametrize("debug", [{}, {"generation": {}}, {"generation": {"used_fallback": True}}])
def test_synthetic_or_unverified_patterns_are_rejected(debug):
    with pytest.raises(RuntimeError):
        validate_inference({"success": True, "classifier": "multilabel"}, debug)


def test_actual_model_transcription_is_accepted():
    validate_inference({"success": True, "classifier": "multilabel"},
                       {"generation": {"used_fallback": False}})


def test_matching_tolerance_and_misses():
    result = match_events([1.0, 2.0, 3.0], [0.95, 2.1, 4.0])
    assert (result["tp"], result["fp"], result["fn"]) == (1, 2, 2)


def test_matching_maximizes_number_of_matches():
    result = match_events([1.0, 1.06], [1.04, 1.10])
    assert result["tp"] == 2


@pytest.mark.parametrize("component,family", [
    ("kick", "KD"), ("cross_stick", "OT"), ("hihat_pedal", "HH"),
    ("tom_3", "TT"), ("ride_bell_2", "CY"), ("china_1", "CY"),
])
def test_family_mapping(component, family):
    assert drum_family(component) == family
