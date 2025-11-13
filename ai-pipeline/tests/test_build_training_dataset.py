import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from training.tools.build_training_dataset import (
    build_dataset,
    ensure_output_dirs,
    verify_manifest,
    main as build_main,
)
from training.tools.console_utils import OutputLogger


def _write_sine_wave(path: Path, *, sample_rate: int = 44_100, duration: float = 0.25) -> Path:
    t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False, dtype=np.float32)
    waveform = np.sin(2.0 * math.pi * 440.0 * t).astype(np.float32)
    sf.write(path, waveform, sample_rate)
    return path


def test_build_dataset_exports_expected_files(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "source.wav")

    manifest_event = {
        "event_id": "evt-001",
        "session_id": "session-train",
        "audio_path": str(audio_path),
        "source_set": "unit_test",
        "onset_time": 0.0,
        "context_ms": {"pre": 80.0, "post": 200.0},
        "components": [{"label": "snare"}],
    }
    manifest_path = tmp_path / "events.jsonl"
    manifest_path.write_text(json.dumps(manifest_event) + "\n", encoding="utf-8")

    dataset_root = tmp_path / "dataset"
    ensure_output_dirs(dataset_root, overwrite=True, resume=False)

    logger = OutputLogger(enable_rich=False)
    try:
        metadata = build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=False,
            logger=logger,
            progress_total=1,
        )
    finally:
        logger.close()

    metadata_path = dataset_root / "metadata.json"
    assert metadata_path.exists()
    assert metadata["clip_fanout"] == 0
    assert metadata["statistics"]["written_clips"] == 1
    assert metadata["run_statistics"]["written_clips"] == 1
    assert metadata["run_label_counts"].get("snare") == 1
    assert metadata["run_statistics"]["written_seconds"] == pytest.approx(
        metadata["statistics"]["written_seconds"]
    )
    assert metadata["run_statistics"]["written_seconds"] == pytest.approx(
        metadata["run_statistics"]["train_seconds"] + metadata["run_statistics"].get("val_seconds", 0.0)
    )

    train_labels_path = dataset_root / "train" / "train_labels.json"
    val_labels_path = dataset_root / "val" / "val_labels.json"
    with train_labels_path.open("r", encoding="utf-8") as handle:
        train_entries = json.load(handle)
    with val_labels_path.open("r", encoding="utf-8") as handle:
        val_entries = json.load(handle)

    combined = train_entries + val_entries
    assert len(combined) == 1
    clip_entry = combined[0]
    assert clip_entry["label"] == "snare"
    assert "duration_seconds" in clip_entry

    split_dir = dataset_root / ("train" if train_entries else "val")
    split_name = "train" if train_entries else "val"
    clip_path = split_dir / clip_entry["file"]
    assert clip_path.exists()
    assert metadata["split_durations_seconds"][split_name] == pytest.approx(clip_entry["duration_seconds"])
    assert metadata["run_split_durations_seconds"][split_name] == pytest.approx(clip_entry["duration_seconds"])
    assert metadata["statistics"]["written_seconds"] == pytest.approx(
        metadata["split_durations_seconds"]["train"] + metadata["split_durations_seconds"]["val"]
    )
    assert metadata["duration_seconds_by_source"]["unit_test"] == pytest.approx(
        clip_entry["duration_seconds"]
    )
    assert metadata["run_duration_seconds_by_source"]["unit_test"] == pytest.approx(
        clip_entry["duration_seconds"]
    )

    with metadata_path.open("r", encoding="utf-8") as handle:
        persisted_metadata = json.load(handle)
    assert persisted_metadata["clip_fanout"] == 0
    assert persisted_metadata["statistics"]["written_clips"] == 1
    assert persisted_metadata["run_statistics"]["written_clips"] == 1
    assert persisted_metadata["run_statistics"]["written_seconds"] == pytest.approx(
        metadata["run_statistics"]["written_seconds"]
    )
    assert persisted_metadata["duration_seconds_by_source"]["unit_test"] == pytest.approx(
        clip_entry["duration_seconds"]
    )


def test_build_dataset_with_clip_fanout(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "fanout-source.wav")

    manifest_event = {
        "event_id": "a1b2c3d4-e5f6-0000-1111-222233334444",
        "session_id": "fanout-session",
        "audio_path": str(audio_path),
        "source_set": "unit_test",
        "components": [{"label": "ride"}],
    }
    manifest_path = tmp_path / "fanout.jsonl"
    manifest_path.write_text(json.dumps(manifest_event) + "\n", encoding="utf-8")

    dataset_root = tmp_path / "dataset"
    ensure_output_dirs(dataset_root, overwrite=True, resume=False)

    logger = OutputLogger(enable_rich=False)
    try:
        metadata = build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=False,
            logger=logger,
            progress_total=1,
            clip_fanout=2,
        )
    finally:
        logger.close()

    assert metadata["clip_fanout"] == 2
    split_dir = dataset_root / "train"
    if not split_dir.exists():
        split_dir = dataset_root / "val"
    labels_path = split_dir / f"{split_dir.name}_labels.json"
    entries = json.loads(labels_path.read_text(encoding="utf-8"))
    assert len(entries) == 1
    clip_entry = entries[0]
    expected_rel = "audio/a1/a1b2c3d4-e5f6-0000-1111-222233334444__ride.wav"
    assert clip_entry["file"] == expected_rel
    clip_path = split_dir / clip_entry["file"]
    assert clip_path.exists()


def test_resume_does_not_duplicate_entries(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "src.wav")
    manifest_event = {
        "event_id": "evt-009",
        "session_id": "session-resume",
        "audio_path": str(audio_path),
        "source_set": "unit_test",
        "onset_time": 0.0,
        "context_ms": {"pre": 80.0, "post": 200.0},
        "components": [{"label": "kick"}],
    }
    manifest_path = tmp_path / "events.jsonl"
    manifest_path.write_text(json.dumps(manifest_event) + "\n", encoding="utf-8")

    dataset_root = tmp_path / "dataset"
    ensure_output_dirs(dataset_root, overwrite=True, resume=False)

    logger = OutputLogger(enable_rich=False)
    try:
        build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=False,
            logger=logger,
            progress_total=1,
        )
    finally:
        logger.close()

    first_metadata = json.loads((dataset_root / "metadata.json").read_text(encoding="utf-8"))
    assert first_metadata["statistics"]["written_clips"] == 1
    assert first_metadata["split_counts"]["train"] + first_metadata["split_counts"]["val"] == 1
    assert first_metadata["clip_fanout"] == 0

    ensure_output_dirs(dataset_root, overwrite=False, resume=True)

    logger = OutputLogger(enable_rich=False)
    try:
        metadata = build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=True,
            logger=logger,
            progress_total=1,
        )
    finally:
        logger.close()

    assert metadata["statistics"]["written_clips"] == 1
    assert metadata["run_statistics"]["written_clips"] == 0
    assert metadata["clip_fanout"] == 0
    assert metadata["split_counts"]["train"] + metadata["split_counts"]["val"] == 1
    assert sum(metadata["run_label_counts"].values()) == 0
    assert metadata["statistics"]["written_seconds"] == pytest.approx(
        first_metadata["statistics"]["written_seconds"]
    )
    assert metadata["run_statistics"]["written_seconds"] == pytest.approx(0.0)
    assert metadata["run_split_durations_seconds"]["train"] == pytest.approx(0.0)
    assert metadata["run_split_durations_seconds"]["val"] == pytest.approx(0.0)
    assert metadata["duration_seconds_by_source"]["unit_test"] == pytest.approx(
        first_metadata["duration_seconds_by_source"]["unit_test"]
    )
    assert metadata["run_duration_seconds_by_source"].get("unit_test", 0.0) == pytest.approx(0.0)

    total_entries = 0
    for split in ("train", "val"):
        labels_path = dataset_root / split / f"{split}_labels.json"
        if labels_path.exists():
            entries = json.loads(labels_path.read_text(encoding="utf-8"))
            total_entries += len(entries)
    assert total_entries == 1


def test_resume_restores_missing_audio(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "src.wav")
    manifest_event = {
        "event_id": "evt-010",
        "session_id": "session-heal",
        "audio_path": str(audio_path),
        "source_set": "unit_test",
        "onset_time": 0.0,
        "context_ms": {"pre": 80.0, "post": 200.0},
        "components": [{"label": "hat"}],
    }
    manifest_path = tmp_path / "events.jsonl"
    manifest_path.write_text(json.dumps(manifest_event) + "\n", encoding="utf-8")

    dataset_root = tmp_path / "dataset"
    ensure_output_dirs(dataset_root, overwrite=True, resume=False)

    logger = OutputLogger(enable_rich=False)
    try:
        build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=False,
            logger=logger,
            progress_total=1,
        )
    finally:
        logger.close()

    labels_path = dataset_root / "train" / "train_labels.json"
    split = "train"
    if not labels_path.exists():
        labels_path = dataset_root / "val" / "val_labels.json"
        split = "val"
    entries = json.loads(labels_path.read_text(encoding="utf-8"))
    clip_rel = entries[0]["file"]
    clip_path = dataset_root / split / clip_rel
    assert clip_path.exists()

    clip_path.unlink()
    assert not clip_path.exists()

    ensure_output_dirs(dataset_root, overwrite=False, resume=True)

    logger = OutputLogger(enable_rich=False)
    try:
        metadata = build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=None,
            audio_root_overrides={},
            target_sample_rate=44_100,
            val_ratio=0.5,
            limit=None,
            pad_to_seconds=None,
            progress_interval=0,
            resume=True,
            logger=logger,
            progress_total=1,
            heal_missing_clips=True,
        )
    finally:
        logger.close()

    assert clip_path.exists()
    assert metadata["run_statistics"].get("healed_clips", 0) == 1
    assert metadata["clip_fanout"] == 0
    healed_split_counts = metadata.get("run_healed_split_counts", {})
    assert healed_split_counts.get(split, 0) == 1
    healed_sources = metadata.get("run_healed_duration_seconds_by_source", {})
    assert healed_sources.get("unit_test", 0.0) > 0.0



def test_ensure_output_dirs_resume_preserves_existing(tmp_path):
    dataset_root = tmp_path / "resume-dataset"
    ensure_output_dirs(dataset_root, overwrite=True, resume=False)

    existing_clip = dataset_root / "train" / "audio" / "existing.wav"
    existing_clip.parent.mkdir(parents=True, exist_ok=True)
    existing_clip.write_bytes(b"00")

    ensure_output_dirs(dataset_root, overwrite=False, resume=True)
    assert existing_clip.exists()

    with pytest.raises(SystemExit):
        ensure_output_dirs(dataset_root, overwrite=False, resume=False)

    with pytest.raises(SystemExit):
        ensure_output_dirs(dataset_root, overwrite=True, resume=True)


def test_verify_manifest_reports_missing_audio(tmp_path):
    existing_audio = _write_sine_wave(tmp_path / "good.wav")
    good_event = {
        "event_id": "evt-good",
        "session_id": "sess-1",
        "audio_path": str(existing_audio),
        "source_set": "unit_test",
        "components": [{"label": "snare"}],
    }
    missing_event = {
        "event_id": "evt-missing",
        "session_id": "sess-2",
        "audio_path": "missing.wav",
        "source_set": "unit_test",
        "components": [{"label": "kick"}],
    }
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        "\n".join(json.dumps(evt) for evt in (good_event, missing_event)) + "\n",
        encoding="utf-8",
    )

    logger = OutputLogger(enable_rich=False)
    try:
        report = verify_manifest(
            manifest_path=manifest_path,
            audio_root=None,
            audio_root_overrides={},
            limit=None,
            progress_interval=0,
            logger=logger,
            progress_total=2,
        )
    finally:
        logger.close()

    stats = report["statistics"]
    assert stats["total_events"] == 2
    assert stats["resolved_audio"] == 1
    assert stats["missing_audio"] == 1
    assert stats["missing_components"] == 0
    assert report["label_counts"].get("snare") == 1
    assert report["label_counts"].get("kick") == 1
    assert report["missing_sources"].get("unit_test") == 1
    assert any(example.get("event_id") == "evt-missing" for example in report["missing_examples"])
    assert stats["expected_seconds"] == pytest.approx(0.56, rel=1e-6)
    by_source = report["expected_seconds_by_source"]
    assert by_source["unit_test"] == pytest.approx(0.56, rel=1e-6)


def test_main_verify_only_summary_json(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "clip.wav")
    manifest_events = [
        {
            "event_id": "evt-ok",
            "session_id": "sess-verify-1",
            "audio_path": audio_path.name,
            "source_set": "unit_test",
            "components": [{"label": "snare"}],
        },
        {
            "event_id": "evt-missing",
            "session_id": "sess-verify-2",
            "audio_path": "missing.wav",
            "source_set": "unit_test",
            "components": [{"label": "kick"}],
        },
    ]
    manifest_path = tmp_path / "verify.jsonl"
    manifest_path.write_text("\n".join(json.dumps(evt) for evt in manifest_events) + "\n", encoding="utf-8")

    summary_path = tmp_path / "reports" / "verify.json"
    duration_csv = tmp_path / "reports" / "verify_durations.csv"
    output_dir = tmp_path / "noop"

    build_main(
        [
            str(manifest_path),
            str(output_dir),
            "--verify-only",
            "--audio-root",
            str(tmp_path),
            "--summary-json",
            str(summary_path),
            "--expected-duration-csv",
            str(duration_csv),
            "--disable-rich",
        ]
    )

    assert summary_path.exists()
    report = json.loads(summary_path.read_text(encoding="utf-8"))
    assert report["statistics"]["total_events"] == 2
    assert report["statistics"]["resolved_audio"] == 1
    assert report["statistics"]["missing_audio"] == 1
    assert duration_csv.exists()
    with duration_csv.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["category"] == "expected"
    assert rows[0]["source_set"] == "unit_test"
    assert float(rows[0]["seconds"]) > 0.0


def test_main_export_summary_json(tmp_path):
    audio_path = _write_sine_wave(tmp_path / "export.wav")
    manifest_event = {
        "event_id": "evt-export",
        "session_id": "sess-export",
        "audio_path": str(audio_path),
        "source_set": "unit_test",
        "components": [{"label": "ride"}],
    }
    manifest_path = tmp_path / "export.jsonl"
    manifest_path.write_text(json.dumps(manifest_event) + "\n", encoding="utf-8")

    dataset_root = tmp_path / "dataset"
    summary_path = tmp_path / "export-summary.json"

    duration_csv = tmp_path / "export_durations.csv"

    build_main(
        [
            str(manifest_path),
            str(dataset_root),
            "--overwrite",
            "--disable-rich",
            "--summary-json",
            str(summary_path),
            "--expected-duration-csv",
            str(duration_csv),
        ]
    )

    assert summary_path.exists()
    metadata = json.loads(summary_path.read_text(encoding="utf-8"))
    assert metadata["run_statistics"]["written_clips"] == 1
    assert metadata["run_label_counts"].get("ride") == 1
    assert metadata["run_statistics"].get("written_seconds") == pytest.approx(
        metadata["run_split_durations_seconds"]["train"] + metadata["run_split_durations_seconds"].get("val", 0.0)
    )
    assert metadata["duration_seconds_by_source"]["unit_test"] == pytest.approx(
        metadata["statistics"]["written_seconds"]
    )
    assert metadata["run_duration_seconds_by_source"]["unit_test"] == pytest.approx(
        metadata["run_statistics"]["written_seconds"]
    )
    assert duration_csv.exists()
    with duration_csv.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    categories = {(row["category"], row["source_set"]): float(row["seconds"]) for row in rows}
    assert ("total", "unit_test") in categories and categories[("total", "unit_test")] > 0.0
    assert ("run", "unit_test") in categories and categories[("run", "unit_test")] > 0.0
