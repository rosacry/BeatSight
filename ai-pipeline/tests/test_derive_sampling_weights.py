from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.tools import derive_sampling_weights as dsw


def _write_manifest(path: Path, events: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            json.dump(event, handle)
            handle.write("\n")
    return path


def test_compute_weights_with_technique_boost(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {
                "audio_path": "stem_a.wav",
                "session_id": "sess_a",
                "techniques": ["hihat_bark"],
            },
            {
                "audio_path": "stem_a.wav",
                "session_id": "sess_a",
                "techniques": [],
            },
        ],
    )

    weights, totals = dsw.compute_weights_with_options(
        manifest_path=manifest,
        group_field="audio_path",
        min_count=1,
        smoothing=0.0,
        exponent=0.5,
        technique_boosts={"hihat_bark": 0.5},
    )

    assert weights["stem_a.wav"]["count"] == 2
    assert weights["stem_a.wav"]["technique_counts"]["hihat_bark"] == 1
    expected_weight = (2.0) ** (-0.5) * 0.5
    assert weights["stem_a.wav"]["weight"] == pytest.approx(expected_weight)
    assert totals == {"hihat_bark": 1}


def test_compute_weights_with_dedupe_and_cap(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {
                "audio_path": "stem_b.wav",
                "session_id": "sess_b",
                "onset_time": 0.0,
            },
            {
                "audio_path": "stem_b.wav",
                "session_id": "sess_b",
                "onset_time": 0.0,
            },
            {
                "audio_path": "stem_b.wav",
                "session_id": "sess_b",
                "onset_time": 0.1,
            },
        ],
    )

    weights, totals = dsw.compute_weights_with_options(
        manifest_path=manifest,
        group_field="audio_path",
        min_count=1,
        smoothing=0.0,
        exponent=0.5,
        dedupe_fields=("session_id", "onset_time"),
        max_per_group=1,
    )

    assert weights["stem_b.wav"]["count"] == 1
    assert weights["stem_b.wav"]["weight"] == pytest.approx(1.0)
    assert totals == {}


def test_compute_weights_with_filter(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {
                "audio_path": "stem_a.wav",
                "session_id": "sess",
                "techniques": ["hihat_bark"],
            },
            {
                "audio_path": "stem_a.wav",
                "session_id": "sess",
                "techniques": [],
            },
            {
                "audio_path": "stem_b.wav",
                "session_id": "sess",
                "techniques": ["ghost_note"],
            },
        ],
    )

    weights, totals = dsw.compute_weights_with_options(
        manifest_path=manifest,
        group_field="audio_path",
        min_count=1,
        smoothing=0.0,
        exponent=0.5,
        technique_filter=("hihat_bark",),
    )

    assert set(weights.keys()) == {"stem_a.wav"}
    assert weights["stem_a.wav"]["count"] == 1
    assert totals == {"hihat_bark": 1}

    weights_unmatched, totals_unmatched = dsw.compute_weights_with_options(
        manifest_path=manifest,
        group_field="audio_path",
        min_count=1,
        smoothing=0.0,
        exponent=0.5,
        technique_filter=("hihat_bark",),
        include_unmatched=True,
    )

    assert weights_unmatched["stem_a.wav"]["count"] == 2
    assert "stem_b.wav" in weights_unmatched
    assert totals_unmatched == {"hihat_bark": 1, "ghost_note": 1}


def test_compute_weights_with_clamps(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {
                "audio_path": "low_weight.wav",
                "session_id": "sess",
            }
        ]
        + [
            {
                "audio_path": "high_weight.wav",
                "session_id": "sess",
            }
            for _ in range(25)
        ]
    )

    weights, _ = dsw.compute_weights_with_options(
        manifest_path=manifest,
        group_field="audio_path",
        min_count=1,
        smoothing=0.0,
        exponent=0.5,
        min_weight=0.2,
        max_weight=0.4,
    )

    assert weights["low_weight.wav"]["count"] == 1
    assert weights["low_weight.wav"]["weight"] == pytest.approx(0.4)

    # Without the clamp the weight would be (25)^(-0.5) == 0.2; adding another event would go smaller.
    assert weights["high_weight.wav"]["count"] == 25
    assert weights["high_weight.wav"]["weight"] == pytest.approx(0.2)
