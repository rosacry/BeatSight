import json
from pathlib import Path

import numpy as np
import pytest

from training.tools import extract_crash_embeddings as extractor


@pytest.fixture()
def sample_audio(tmp_path: Path) -> Path:
    import soundfile as sf

    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    sweep = np.sin(2 * np.pi * (300 + 700 * t) * t)
    audio_path = tmp_path / "crash.wav"
    sf.write(audio_path, sweep.astype(np.float32), sr)
    return audio_path


@pytest.fixture()
def sample_manifest(tmp_path: Path, sample_audio: Path) -> Path:
    manifest_path = tmp_path / "manifest.jsonl"
    payload = {
        "event_id": "evt_1",
        "session_id": "session_a",
        "audio_path": str(sample_audio),
        "onset_time": 0.1,
        "components": [
            {"label": "crash", "velocity": 0.5},
        ],
        "techniques": ["crash_dual_label"],
    }
    manifest_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return manifest_path


def test_parse_args_defaults(tmp_path: Path):
    out_path = tmp_path / "out.jsonl"
    args = extractor.parse_args([
        str(tmp_path / "manifest.jsonl"),
        "--output",
        str(out_path),
    ])
    assert args.sample_rate == extractor.DEFAULT_SAMPLE_RATE
    assert args.window_ms == extractor.DEFAULT_WINDOW_MS
    assert args.n_mfcc == extractor.DEFAULT_N_MFCC
    assert "crash" in args.include_component


def test_has_component_detects_targets(sample_manifest: Path):
    (event,) = list(extractor.iter_manifest_events(sample_manifest))
    assert extractor.has_component(event, ["crash"]) is True
    assert extractor.has_component(event, ["ride"]) is False


def test_extract_window_returns_audio(sample_manifest: Path, sample_audio: Path):
    (event,) = list(extractor.iter_manifest_events(sample_manifest))
    window = extractor.extract_window(
        sample_audio,
        onset_time=float(event["onset_time"]),
        sample_rate=extractor.DEFAULT_SAMPLE_RATE,
        window_ms=extractor.DEFAULT_WINDOW_MS,
        preroll_ms=extractor.DEFAULT_PREROLL_MS,
    )
    assert window.size > 0


def test_compute_descriptors(sample_manifest: Path, sample_audio: Path):
    (event,) = list(extractor.iter_manifest_events(sample_manifest))
    window = extractor.extract_window(
        sample_audio,
        onset_time=float(event["onset_time"]),
        sample_rate=extractor.DEFAULT_SAMPLE_RATE,
        window_ms=extractor.DEFAULT_WINDOW_MS,
        preroll_ms=extractor.DEFAULT_PREROLL_MS,
    )
    metrics = extractor.compute_descriptors(window, extractor.DEFAULT_SAMPLE_RATE, extractor.DEFAULT_N_MFCC)
    assert metrics is not None
    assert "spectral_centroid" in metrics
    assert len(metrics["mfcc_mean"]) == extractor.DEFAULT_N_MFCC


def test_cli_execution(tmp_path: Path, sample_manifest: Path):
    out_path = tmp_path / "embeddings.jsonl"
    exit_code = extractor.main([
        str(sample_manifest),
        "--output",
        str(out_path),
        "--progress",
    ])
    assert exit_code == 0
    payload = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert payload
    record = payload[0]
    assert record["event_id"] == "evt_1"
    assert record["metrics"]["mfcc_mean"]
