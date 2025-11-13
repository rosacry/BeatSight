from __future__ import annotations

import json
from pathlib import Path

import pytest

from training import dataset_health


def _make_options(**overrides):
    defaults = dict(
        events_path=Path("dummy.jsonl"),
        output_path=None,
        html_output_path=None,
        metadata_path=None,
        components_path=None,
        max_duplication_rate=None,
        min_class_count=None,
        min_counts_path=None,
        require_labels=[],
        max_unknown_labels=None,
        require_techniques=[],
    )
    defaults.update(overrides)
    return dataset_health.HealthOptions(**defaults)


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "training" / "examples"


def test_analyse_events_basic_counts():
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy=None)

    assert report["summary"]["events_total"] == 5
    assert report["summary"]["events_synthetic"] == 1
    assert report["per_class_counts"]["snare"]["total"] == 1
    assert report["per_class_counts"]["kick"]["synthetic"] == 1
    assert report["openness_histogram"][0]["count"] == 1
    assert duplication_rate == 0.0
    assert report["technique_counts"].get("hihat_bark") == 1
    assert report["technique_counts"].get("metric_modulation") == 1
    assert report["technique_counts"].get("variable_meter") == 1
    assert report["technique_counts"].get("multi_cymbal_same_class") == 1


def test_analyse_events_unknown_labels(tmp_path):
    events_path = tmp_path / "events.jsonl"
    events = [
        {
            "sample_id": "x1",
            "session_id": "sess",
            "drummer_id": "d",
            "audio_path": "audio/train/wav/sess/x1.wav",
            "components": [{"label": "snare"}],
        },
        {
            "sample_id": "x2",
            "session_id": "sess",
            "drummer_id": "d",
            "audio_path": "audio/train/wav/sess/x2.wav",
            "components": [{"label": "mystery_drum"}],
        },
    ]

    with events_path.open("w", encoding="utf-8") as handle:
        for row in events:
            json.dump(row, handle)
            handle.write("\n")

    taxonomy = {"classes": [{"id": "snare"}]}
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy)

    assert report["unknown_labels"] == {"mystery_drum": 1}
    assert duplication_rate == 0.0


def test_collect_gate_failures_min_class_count(tmp_path):
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy=None)
    options = _make_options(min_class_count=2)
    failures, gate_results = dataset_health.collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels=set(),
        class_thresholds={},
    )

    assert any("Coverage gating failed" in msg for msg in failures)
    assert any(not result.passed for result in gate_results)


def test_collect_gate_failures_require_label():
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy=None)
    options = _make_options(require_labels=["snare", "tom_mid"])
    failures, gate_results = dataset_health.collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels=set(),
        class_thresholds={},
    )

    assert any("tom_mid" in msg for msg in failures)
    assert any(r.name == "require_label[tom_mid]" and not r.passed for r in gate_results)


def test_collect_gate_failures_threshold_json():
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy=None)
    thresholds = {"kick": 2}
    options = _make_options()
    failures, gate_results = dataset_health.collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels=set(),
        class_thresholds=thresholds,
    )

    assert any("kick" in msg for msg in failures)
    assert any(r.name == "min_counts[kick]" and not r.passed for r in gate_results)


def test_collect_gate_failures_require_technique():
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy=None)
    options = _make_options(require_techniques=["brush_swirl"])

    failures, gate_results = dataset_health.collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels=set(),
        class_thresholds={},
    )

    assert any("brush_swirl" in msg for msg in failures)
    assert any(
        result.name == "require_technique[brush_swirl]" and not result.passed
        for result in gate_results
    )


def test_write_html_report(tmp_path):
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, _ = dataset_health.analyse_events(events_path, taxonomy=None)
    html_path = tmp_path / "health.html"

    dataset_health.write_html_report(report, html_path, gate_results=None)

    content = html_path.read_text(encoding="utf-8")
    assert "BeatSight Dataset Health Report" in content
    assert "snare" in content
    assert "events_total" in content


def test_merge_metadata_durations_enriches_report():
    report = {"summary": {}}
    metadata = {
        "split_durations_seconds": {"train": "100.5", "val": 50},
        "run_split_durations_seconds": {"train": 10},
        "duration_seconds_by_source": {"BeatSight": 80, "Groove": 70.25},
        "run_duration_seconds_by_source": {"BeatSight": 5.5},
    }

    dataset_health.merge_metadata_durations(report, metadata)

    assert report["split_durations_seconds"]["train"] == pytest.approx(100.5)
    assert report["run_split_durations_seconds"]["train"] == pytest.approx(10.0)
    assert report["duration_seconds_by_source"]["Groove"] == pytest.approx(70.25)
    assert report["run_duration_seconds_by_source"]["BeatSight"] == pytest.approx(5.5)
    assert report["summary"]["duration_seconds_total"] == pytest.approx(150.5)
    assert report["summary"]["duration_hours_total"] == pytest.approx(150.5 / 3600.0, abs=1e-6)


def test_write_html_report_includes_duration_sections(tmp_path):
    events_path = EXAMPLES_DIR / "events_health_example.jsonl"
    report, _ = dataset_health.analyse_events(events_path, taxonomy=None)
    report["duration_seconds_by_source"] = {"BeatSight": 123.45}
    report["split_durations_seconds"] = {"train": 90.0, "val": 33.45}
    html_path = tmp_path / "health_duration.html"

    dataset_health.write_html_report(report, html_path, gate_results=None)

    content = html_path.read_text(encoding="utf-8")
    assert "Duration by Source" in content
    assert "Duration by Split" in content
    assert "123.450000" in content


def test_max_unknown_labels_gate(tmp_path):
    events_path = tmp_path / "events.jsonl"
    events = [
        {
            "sample_id": "a1",
            "session_id": "sess",
            "drummer_id": "d",
            "audio_path": "audio/train/wav/sess/a1.wav",
            "components": [{"label": "snare"}],
        },
        {
            "sample_id": "a2",
            "session_id": "sess",
            "drummer_id": "d",
            "audio_path": "audio/train/wav/sess/a2.wav",
            "components": [{"label": "mystery"}],
        },
    ]
    with events_path.open("w", encoding="utf-8") as handle:
        for row in events:
            json.dump(row, handle)
            handle.write("\n")

    taxonomy = {"classes": [{"id": "snare"}]}
    report, duplication_rate = dataset_health.analyse_events(events_path, taxonomy)
    options = _make_options(max_unknown_labels=0)
    failures, gate_results = dataset_health.collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels=dataset_health.allowed_labels_from_taxonomy(taxonomy),
        class_thresholds={},
    )

    assert any("Unknown label gating failed" in msg for msg in failures)


def test_require_labels_file(tmp_path):
    file_path = tmp_path / "required.txt"
    file_path.write_text("snare\n# comment\n tom_mid \n\n", encoding="utf-8")

    labels = dataset_health.load_required_labels(file_path)

    assert labels == ["snare", "tom_mid"]


def test_parse_args_require_techniques_file(monkeypatch, tmp_path):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text("", encoding="utf-8")

    techniques_file = tmp_path / "techs.txt"
    techniques_file.write_text("hihat_bark\nbrush_swirl\n", encoding="utf-8")

    argv = [
        "dataset_health.py",
        "--events",
        str(events_path),
        "--require-technique",
        "stick_click",
        "--require-techniques-file",
        str(techniques_file),
    ]
    monkeypatch.setattr(dataset_health.sys, "argv", argv)

    options = dataset_health.parse_args()

    assert options.events_path == events_path
    assert options.require_techniques == ["stick_click", "hihat_bark", "brush_swirl"]