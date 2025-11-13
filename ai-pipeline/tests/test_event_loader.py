from __future__ import annotations

import json
from pathlib import Path

from training import event_loader


def _write_manifest(path: Path, events: list[dict]) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            json.dump(event, handle)
            handle.write("\n")
    return path


def test_manifest_event_loader_filters_any(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {"event_id": "1", "techniques": ["hihat_bark"]},
            {"event_id": "2", "techniques": []},
        ],
    )

    loader = event_loader.ManifestEventLoader(manifest, technique_filter=["hihat_bark"])
    records = list(loader)

    assert len(records) == 2
    assert records[0].matches_filter is True
    assert records[1].matches_filter is False
    assert records[0].techniques == ("hihat_bark",)


def test_manifest_event_loader_summary(tmp_path: Path) -> None:
    manifest = _write_manifest(
        tmp_path / "manifest.jsonl",
        [
            {"event_id": "1", "techniques": ["hihat_bark", "ghost_note"]},
            {"event_id": "2", "techniques": ["hihat_bark"]},
            {"event_id": "3"},
        ],
    )

    summary = event_loader.ManifestEventLoader(manifest).summary()

    assert summary.total_events == 3
    assert summary.technique_counts == {"ghost_note": 1, "hihat_bark": 2}
