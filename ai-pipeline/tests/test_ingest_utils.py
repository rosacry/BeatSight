import json
import textwrap

from training.tools import ingest_utils


def test_load_techniques_from_json(tmp_path):
    taxonomy = tmp_path / "taxonomy.json"
    taxonomy.write_text(
        json.dumps(
            {
                "techniques": [
                    "flam",
                    {"id": "cymbal_choke"},
                    {"id": "duplicate"},
                    "duplicate",
                ]
            }
        ),
        encoding="utf-8",
    )

    result = ingest_utils.load_techniques(taxonomy)

    assert result == ["cymbal_choke", "duplicate", "flam"]


def test_load_techniques_from_text(tmp_path):
    reference = tmp_path / "additionaldrummertech.txt"
    reference.write_text(
        textwrap.dedent(
            """
            # comments are ignored
            flam
            
            rimshot
            # duplicates collapse
            flam
            """
        ),
        encoding="utf-8",
    )

    result = ingest_utils.load_techniques(reference)

    assert result == ["flam", "rimshot"]


def test_load_technique_taxonomy_handles_missing(tmp_path):
    missing_path = tmp_path / "does_not_exist.json"

    result = ingest_utils.load_technique_taxonomy(missing_path)

    assert result == {"techniques": []}


def test_load_technique_taxonomy_accepts_list(tmp_path):
    taxonomy = tmp_path / "taxonomy_as_list.json"
    taxonomy.write_text(
        json.dumps([
            {"id": "hihat_bark", "aliases": ["bark"]},
            "ride_bell_accent",
        ]),
        encoding="utf-8",
    )

    result = ingest_utils.load_technique_taxonomy(taxonomy)

    assert result == {
        "techniques": [
            {"id": "hihat_bark", "aliases": ["bark"]},
            "ride_bell_accent",
        ]
    }


def test_apply_taxonomy_inference_cymbal_variants():
    events = [
        {
            "onset_time": 0.1,
            "components": [{"label": "crash", "instrument_variant": "high"}],
            "techniques": [],
        },
        {
            "onset_time": 0.2,
            "components": [{"label": "crash", "instrument_variant": "low"}],
            "techniques": [],
        },
    ]

    inferred = ingest_utils.apply_taxonomy_inference(events)

    assert {"crash_high", "crash_low", "multi_cymbal_same_class"}.issubset(inferred)
    assert "crash_high" in events[0]["techniques"]
    assert "crash_low" in events[1]["techniques"]
    assert "multi_cymbal_same_class" in events[0]["techniques"] or "multi_cymbal_same_class" in events[1]["techniques"]


def test_apply_taxonomy_inference_metric_and_meter():
    events = [
        {
            "onset_time": 0.0,
            "meter": "4/4",
            "tempo_bpm": 120.0,
            "components": [{"label": "snare"}],
            "techniques": [],
        },
        {
            "onset_time": 0.5,
            "meter": "12/8",
            "tempo_bpm": 180.0,
            "components": [{"label": "ride_bell", "strike_position": "bell"}],
            "techniques": [],
        },
    ]

    inferred = ingest_utils.apply_taxonomy_inference(events)

    assert "variable_meter" in inferred
    assert "metric_modulation" in inferred
    assert "metric_modulation" in events[1]["techniques"]
    assert "ride_bell_accent" in events[1]["techniques"]


def test_apply_taxonomy_inference_hihat_articulations():
    events = [
        {
            "onset_time": 0.0,
            "components": [{"label": "hihat_open", "openness": 0.9}],
            "techniques": [],
        },
        {
            "onset_time": 0.1,
            "components": [{"label": "hihat_pedal"}],
            "techniques": [],
        },
    ]

    inferred = ingest_utils.apply_taxonomy_inference(events)

    assert {"hihat_splash", "hihat_foot_chick"}.issubset(inferred)
    assert "hihat_splash" in events[0]["techniques"]
    assert "hihat_foot_chick" in events[1]["techniques"]
