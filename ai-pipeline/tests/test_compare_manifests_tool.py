import json
import sys
from pathlib import Path

import pytest

from training.tools.compare_manifests import (
    ManifestStats,
    diff_counters,
    gather_stats,
    main as compare_manifests_main,
)


def write_manifest(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            json.dump(event, handle)
            handle.write("\n")


@pytest.fixture()
def sample_manifests(tmp_path: Path) -> tuple[Path, Path]:
    baseline_events = [
        {
            "session_id": "session_a",
            "components": [{"label": "kick"}],
            "techniques": ["straight"],
        },
        {
            "session_id": "session_b",
            "components": [{"label": "snare"}],
            "techniques": [],
        },
    ]
    candidate_events = [
        {
            "session_id": "session_a",
            "components": [{"label": "kick"}],
            "techniques": ["straight"],
        },
        {
            "session_id": "session_b",
            "components": [{"label": "snare"}],
            "techniques": ["ghost_notes"],
        },
        {
            "session_id": "session_c",
            "components": [{"label": "hihat_open"}],
            "techniques": ["open_hat"],
        },
    ]

    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    write_manifest(baseline_path, baseline_events)
    write_manifest(candidate_path, candidate_events)
    return baseline_path, candidate_path


def test_gather_stats_counts(sample_manifests: tuple[Path, Path]) -> None:
    baseline_path, candidate_path = sample_manifests
    baseline_stats = gather_stats(baseline_path)
    candidate_stats = gather_stats(candidate_path)

    assert isinstance(baseline_stats, ManifestStats)
    assert baseline_stats.total_events == 2
    assert candidate_stats.total_events == 3
    assert baseline_stats.session_counts["session_a"] == 1
    assert candidate_stats.session_counts["session_c"] == 1
    assert candidate_stats.component_counts["hihat_open"] == 1
    assert baseline_stats.technique_counts["straight"] == 1


def test_diff_counters_detects_changes(sample_manifests: tuple[Path, Path]) -> None:
    baseline_path, candidate_path = sample_manifests
    baseline_stats = gather_stats(baseline_path)
    candidate_stats = gather_stats(candidate_path)

    diffs = diff_counters(baseline_stats.session_counts, candidate_stats.session_counts)
    by_label = {diff.label: diff for diff in diffs}
    assert by_label["session_c"].baseline == 0
    assert by_label["session_c"].candidate == 1
    assert by_label["session_c"].delta == 1


def test_compare_manifests_cli_writes_json(sample_manifests: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    baseline_path, candidate_path = sample_manifests
    output_path = tmp_path / "diff.json"

    argv = [
        "compare_manifests",
        str(baseline_path),
        str(candidate_path),
        "--json-output",
        str(output_path),
        "--limit",
        "2",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    assert compare_manifests_main() == 0
    captured = capsys.readouterr()
    assert "Totals" in captured.out
    assert output_path.exists()

    with output_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["delta"]["total_events"] == 1
    assert "session_counts" in payload["delta"]
    assert payload["candidate"]["total_events"] == 3
