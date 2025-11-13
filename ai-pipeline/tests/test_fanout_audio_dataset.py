import json
from pathlib import Path

from training.tools.fanout_audio_dataset import _process_split


def _write_label_array(path: Path, relative_path: str) -> None:
    data = [
        {
            "file": relative_path,
            "label": "ride",
            "event_id": "evt",
            "session_id": "sess",
            "source_set": "unit_test",
        }
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_prepare_move_and_rewrite(tmp_path: Path) -> None:
    split_dir = tmp_path / "train"
    audio_dir = split_dir / "audio"
    audio_dir.mkdir(parents=True)

    clip_path = audio_dir / "aabbccdd__ride.wav"
    clip_path.write_bytes(b"00")

    labels_path = split_dir / "train_labels.json"
    _write_label_array(labels_path, "audio/aabbccdd__ride.wav")

    summary = _process_split(split_dir, fanout=2, dry_run=False)
    assert summary is not None
    assert summary.moved == 1
    assert summary.skipped == 0
    assert summary.label_updates == 1

    target_dir = split_dir / "audio"
    new_path = target_dir / "aa" / "aabbccdd__ride.wav"
    assert new_path.exists()
    assert not (split_dir / "audio_flat").exists()

    data = json.loads(labels_path.read_text(encoding="utf-8"))
    assert data[0]["file"] == "audio/aa/aabbccdd__ride.wav"
