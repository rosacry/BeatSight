import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.tools import ingest_cambridge  # noqa: E402


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("Skyeez_BananaSplit_Full/40_Beep.wav", "beep"),
        ("Strobe_Maya_Full/16_Footsteps.wav", "footsteps"),
        ("Strobe_Maya_Full/18_Rain.wav", "rain"),
        ("TheFerryboatMen_WindsOfGypsyMoor_Full/28_Waves.wav", "waves"),
        ("TheFerryboatMen_WindsOfGypsyMoor_Full/29_Wind.wav", "wind"),
        ("TheFerryboatMen_WindsOfGypsyMoor_Full/30_Owl.wav", "wind"),
        ("Triviul_Angelsaint_Full/13_LeadDouble.wav", "leadvox"),
        ("KungFu_DaddyD_Full/OVER_04-07.wav", "overheads"),
    ],
)
def test_non_drum_filters_capture_recent_keywords(stem: str, expected: str):
    tokens = ingest_cambridge._tokenize(stem)
    assert ingest_cambridge._match_non_drum(tokens) == expected


def test_kalimba_stem_infers_aux_percussion_variant():
    stem = "Triviul_ToSamRawfers_Full/04_Kalimba.wav"
    inferred = ingest_cambridge._infer_component(stem)
    assert inferred is not None
    label, extras, _ = inferred
    assert label == "aux_percussion"
    assert extras.get("instrument_variant") == "kalimba"
