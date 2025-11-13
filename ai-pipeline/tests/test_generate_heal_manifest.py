import json
from pathlib import Path

import pytest

from training.tools.generate_heal_manifest import generate_heal_manifest


@pytest.fixture()
def sample_dataset(tmp_path: Path) -> Path:
    dataset_root = tmp_path / "dataset"
    train_audio = dataset_root / "train" / "audio"
    val_audio = dataset_root / "val" / "audio"
    train_audio.mkdir(parents=True)
    val_audio.mkdir(parents=True)

    # Present clip
    (train_audio / "existing_clip.wav").write_bytes(b"abc")

    train_labels = dataset_root / "train" / "train_labels.json"
    train_labels.write_text(
        json.dumps(
            [
                {
                    "file": "audio/existing_clip.wav",
                    "label": "kick",
                    "component_idx": 0,
                    "event_id": "evt_present",
                    "session_id": "sess1",
                    "source_set": "test",
                },
                {
                    "file": "audio/missing_clip.wav",
                    "label": "snare",
                    "component_idx": 1,
                    "event_id": "evt_missing",
                    "session_id": "sess2",
                    "source_set": "test",
                },
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    val_labels = dataset_root / "val" / "val_labels.json"
    val_labels.write_text("[]\n", encoding="utf-8")

    return dataset_root


def test_generate_heal_manifest(tmp_path: Path, sample_dataset: Path) -> None:
    manifest_lines = [
        json.dumps(
            {
                "event_id": "evt_present",
                "session_id": "sess1",
                "components": [{"label": "kick"}],
                "audio_path": "path/to/present.wav",
            }
        ),
        json.dumps(
            {
                "event_id": "evt_missing",
                "session_id": "sess2",
                "components": [{"label": "snare"}],
                "audio_path": "path/to/missing.wav",
            }
        ),
    ]
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    output_manifest = tmp_path / "heal_manifest.jsonl"
    summary_path = tmp_path / "heal_summary.json"

    stats = generate_heal_manifest(
        dataset_root=sample_dataset,
        manifest_path=manifest_path,
        output_manifest=output_manifest,
        summary_path=summary_path,
    )

    assert stats.written_events == 1
    assert not stats.remaining_events
    assert not stats.missing_component_labels

    output_lines = output_manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(output_lines) == 1
    event = json.loads(output_lines[0])
    assert event["event_id"] == "evt_missing"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["missing_clip_total"] == 1
    assert summary["missing_event_total"] == 1
    assert summary["written_event_total"] == 1
    assert "evt_missing" in summary["missing_clip_details"]


def test_generate_heal_manifest_duplicate_labels(tmp_path: Path, sample_dataset: Path) -> None:
    # Add duplicate entry to trigger failure
    train_labels = sample_dataset / "train" / "train_labels.json"
    label_data = json.loads(train_labels.read_text(encoding="utf-8"))
    label_data.append(label_data[-1])
    train_labels.write_text(json.dumps(label_data, indent=2) + "\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text("[]\n", encoding="utf-8")

    output_manifest = tmp_path / "heal_manifest.jsonl"

    with pytest.raises(RuntimeError, match="Duplicate label entries detected"):
        generate_heal_manifest(
            dataset_root=sample_dataset,
            manifest_path=manifest_path,
            output_manifest=output_manifest,
        )
