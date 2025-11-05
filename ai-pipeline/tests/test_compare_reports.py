import json
from pathlib import Path

from training.compare_health_reports import CompareOptions, compare_reports


def write_report(tmp_path: Path, name: str, data: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def base_report(per_class: dict, gating=None, unknown=None) -> dict:
    return {
        "per_class_counts": per_class,
        "gating_results": gating or [],
        "unknown_labels": unknown or {},
    }


def test_compare_reports_pass(tmp_path: Path) -> None:
    baseline = write_report(
        tmp_path,
        "baseline.json",
        base_report(
            {
                "kick": {"total": 100, "real": 90, "synthetic": 10},
                "snare": {"total": 120, "real": 100, "synthetic": 20},
            }
        ),
    )
    candidate = write_report(
        tmp_path,
        "candidate.json",
        base_report(
            {
                "kick": {"total": 110, "real": 95, "synthetic": 15},
                "snare": {"total": 130, "real": 102, "synthetic": 28},
            }
        ),
    )
    options = CompareOptions(
        baseline_path=baseline,
        candidate_path=candidate,
        max_drop=0,
        ignore_labels=set(),
        json_output=None,
    )
    result = compare_reports(options)
    assert result.passes
    assert not result.gating_regressions
    assert result.unknown_label_delta == 0


def test_compare_reports_rejects_drop(tmp_path: Path) -> None:
    baseline = write_report(
        tmp_path,
        "baseline.json",
        base_report({"kick": {"total": 100, "real": 90, "synthetic": 10}}),
    )
    candidate = write_report(
        tmp_path,
        "candidate.json",
        base_report({"kick": {"total": 80, "real": 70, "synthetic": 10}}),
    )
    options = CompareOptions(
        baseline_path=baseline,
        candidate_path=candidate,
        max_drop=5,
        ignore_labels=set(),
        json_output=None,
    )
    result = compare_reports(options)
    assert not result.passes


def test_compare_reports_rejects_unknown_increase(tmp_path: Path) -> None:
    baseline = write_report(
        tmp_path,
        "baseline.json",
        base_report({"kick": {"total": 100, "real": 90, "synthetic": 10}}, unknown={}),
    )
    candidate = write_report(
        tmp_path,
        "candidate.json",
        base_report(
            {"kick": {"total": 100, "real": 90, "synthetic": 10}},
            unknown={"mystery": 3},
        ),
    )
    options = CompareOptions(
        baseline_path=baseline,
        candidate_path=candidate,
        max_drop=0,
        ignore_labels=set(),
        json_output=None,
    )
    result = compare_reports(options)
    assert not result.passes
    assert result.unknown_label_delta == 3


def test_compare_reports_ignores_label(tmp_path: Path) -> None:
    baseline = write_report(
        tmp_path,
        "baseline.json",
        base_report({"ignore": {"total": 100, "real": 90, "synthetic": 10}}),
    )
    candidate = write_report(
        tmp_path,
        "candidate.json",
        base_report({"ignore": {"total": 50, "real": 40, "synthetic": 10}}),
    )
    options = CompareOptions(
        baseline_path=baseline,
        candidate_path=candidate,
        max_drop=0,
        ignore_labels={"ignore"},
        json_output=None,
    )
    result = compare_reports(options)
    assert result.passes


def test_compare_reports_detects_gating_failure(tmp_path: Path) -> None:
    baseline = write_report(
        tmp_path,
        "baseline.json",
        base_report({"kick": {"total": 100, "real": 90, "synthetic": 10}}, gating=[]),
    )
    candidate = write_report(
        tmp_path,
        "candidate.json",
        base_report(
            {"kick": {"total": 100, "real": 90, "synthetic": 10}},
            gating=[{"name": "min_count", "passed": False}],
        ),
    )
    options = CompareOptions(
        baseline_path=baseline,
        candidate_path=candidate,
        max_drop=0,
        ignore_labels=set(),
        json_output=None,
    )
    result = compare_reports(options)
    assert not result.passes
    assert result.gating_regressions == ["min_count"]
