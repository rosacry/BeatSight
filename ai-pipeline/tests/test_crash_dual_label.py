from __future__ import annotations

import json
from pathlib import Path

from training.tools import crash_variant_clustering as clustering
from training.tools.alias_events import (
    CrashLabelAssignment,
    apply_crash_assignment,
    load_crash_mapping,
)


def _make_event(event_id: str, variant: str, techniques: list[str]) -> dict:
    return {
        "event_id": event_id,
        "session_id": "session_1",
        "components": [
            {
                "label": "crash",
                "instrument_variant": variant,
            }
        ],
        "techniques": techniques,
    }


def test_metadata_assignment_maps_low_variant_to_crash2():
    events = [
        _make_event("evt_high", "high", ["crash_high"]),
        _make_event("evt_low", "low", ["crash_low"]),
    ]

    assignments, summary, sessions = clustering.derive_assignments(events)

    assert "evt_low" in assignments
    assignment = assignments["evt_low"]
    assert assignment.label == "crash2"
    assert assignment.method == "metadata_variant"
    assert summary.assigned_events == 1
    assert summary.by_label == {"crash2": 1}
    assert sessions["session_1"]["assigned"] == 1


def test_apply_crash_assignment_updates_event(tmp_path):
    assignment = CrashLabelAssignment(
        event_id="evt_low",
        session_id="session_1",
        target_label="crash2",
        method="metadata_variant",
        confidence=1.0,
        notes="instrument_variant=low",
    )

    mapping_path = tmp_path / "mapping.json"
    mapping_payload = {
        "events": {
            assignment.event_id: {
                "session_id": assignment.session_id,
                "label": assignment.target_label,
                "method": assignment.method,
                "confidence": assignment.confidence,
                "notes": assignment.notes,
            }
        }
    }
    mapping_path.write_text(json.dumps(mapping_payload), encoding="utf-8")

    loaded_mapping = load_crash_mapping(mapping_path)
    assert assignment.event_id in loaded_mapping

    event = _make_event("evt_low", "low", ["crash_low"])
    changed = apply_crash_assignment(
        event,
        loaded_mapping[assignment.event_id],
        stage_tag="crash_dual_label",
        technique_tag="crash_dual_label",
    )

    assert changed
    assert event["components"][0]["label"] == "crash2"
    assert "crash_dual_label" in event["techniques"]
    history = event.get("annotation_history") or []
    assert history and history[-1]["annotation_stage"] == "crash_dual_label"
    assert history[-1]["method"] == "metadata_variant"


def test_spectral_clustering_assigns_low_centroid_to_crash2(tmp_path: Path):
    session_id = "session_spec"
    events = []
    embeddings_payload = []

    for idx, centroid in enumerate([750.0, 780.0, 800.0, 820.0, 840.0, 860.0]):
        event_id = f"low_{idx}"
        events.append(
            {
                "event_id": event_id,
                "session_id": session_id,
                "components": [{"label": "crash"}],
                "techniques": [],
            }
        )
        embeddings_payload.append(
            {
                "event_id": event_id,
                "session_id": session_id,
                "metrics": {
                    "spectral_centroid": centroid,
                    "spectral_bandwidth": 480.0,
                    "spectral_rolloff": 2200.0,
                    "zero_crossing_rate": 0.12,
                    "rms": 0.18,
                },
            }
        )

    for idx, centroid in enumerate([1850.0, 1900.0, 1950.0, 2000.0, 2050.0, 2100.0]):
        event_id = f"high_{idx}"
        events.append(
            {
                "event_id": event_id,
                "session_id": session_id,
                "components": [{"label": "crash"}],
                "techniques": [],
            }
        )
        embeddings_payload.append(
            {
                "event_id": event_id,
                "session_id": session_id,
                "metrics": {
                    "spectral_centroid": centroid,
                    "spectral_bandwidth": 520.0,
                    "spectral_rolloff": 3800.0,
                    "zero_crossing_rate": 0.2,
                    "rms": 0.22,
                },
            }
        )

    embeddings_path = tmp_path / "embeddings.jsonl"
    embeddings_path.write_text(
        "\n".join(json.dumps(row) for row in embeddings_payload) + "\n",
        encoding="utf-8",
    )

    embedding_records = clustering.load_embedding_records(embeddings_path)
    config = clustering.SpectralConfig(
        min_events=8,
        min_cluster_size=3,
        min_centroid_gap=300.0,
        min_gap_ratio=0.2,
    )

    assignments, summary, sessions = clustering.derive_assignments(
        events,
        embeddings=embedding_records,
        spectral_config=config,
    )

    low_ids = {f"low_{idx}" for idx in range(6)}
    assert low_ids.issubset(assignments)
    for event_id in low_ids:
        assignment = assignments[event_id]
        assert assignment.label == "crash2"
        assert assignment.method == "spectral_cluster"
        assert assignment.confidence > 0

    assert summary.by_label.get("crash2", 0) >= len(low_ids)
    assert summary.methods.get("spectral_cluster", 0) >= len(low_ids)
    assert sessions[session_id]["assigned"] >= len(low_ids)
