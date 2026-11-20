"""Contract and parity tests for the ADTOF transcription engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from adtof_engine import FAMILIES, decoder, engine, frontend
from adtof_engine.model import WEIGHTS_SHA256, FrameRnn, FrequencyMaxPool, load_model

REPO_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = engine.default_weights_path()
needs_weights = pytest.mark.skipif(not WEIGHTS.is_file(), reason="local ADTOF weights not installed")

# Saved 2026-10-14 stereo-separated stem and 2026-10-15 audited outputs (outside the repo).
FIXTURE_STEM = Path(r"C:\Users\10ros\BeatSight-Recovery\2026-10-14-white-waves-01\stereo-diagnostic\MusicDelta_80sRock.drums.wav")
FIXTURE_AUDIT = Path(r"C:\Users\10ros\BeatSight-Recovery\2026-10-15-adtof-model-audit-01\full-recordings\MusicDelta_80sRock")


def test_frontend_shape_and_frame_count():
    audio = np.zeros(44100, dtype=np.float32)
    feats = frontend.features(audio)
    assert feats.shape == (100, 84, 1)
    assert feats.dtype == np.float32


def test_frontend_rejects_non_float32_or_stereo():
    with pytest.raises(ValueError):
        frontend.features(np.zeros(1000, dtype=np.float64))
    with pytest.raises(ValueError):
        frontend.features(np.zeros((2, 1000), dtype=np.float32))


def test_frequency_pool_ignores_padding_for_negative_inputs():
    x = torch.full((1, 1, 1, 28), -2.0)
    pooled = FrequencyMaxPool()(x)
    assert pooled.shape[-1] == 10
    # Zero padding would wrongly return 0 at the borders.
    assert torch.all(pooled == -2.0)


def test_model_output_shape_and_state_dict_names():
    model = FrameRnn().eval()
    with torch.no_grad():
        out = model(torch.zeros(1, 50, 84, 1))
    assert out.shape == (1, 50, 5)
    names = set(model.state_dict())
    assert "gru_layers.0.weight_ih_l0_reverse" in names
    assert "cnn_blocks.1.5.running_var" in names


def test_load_model_refuses_wrong_weights(tmp_path):
    bogus = tmp_path / "weights.pth"
    torch.save({"model_weights": FrameRnn().state_dict()}, bogus)
    with pytest.raises(ValueError, match="audited"):
        load_model(bogus)
    with pytest.raises(FileNotFoundError, match="Legacy"):
        load_model(tmp_path / "missing.pth")


def test_decoder_thresholds_and_combine_window():
    acts = np.zeros((300, 5), dtype=np.float32)
    acts[100, 0] = 0.9   # kick candidate at 1.000 s
    acts[101, 0] = 0.95  # higher neighbor 10 ms later is the only local maximum
    acts[200, 1] = 0.2   # snare below its .24 threshold
    events = decoder.decode(acts)
    assert [e["component"] for e in events] == ["kick"]
    assert events[0]["time"] == pytest.approx(1010.0)


def _fake_transcription(monkeypatch, events_ms):
    def fake_decode(_activations):
        return [{"time": float(t), "component": c} for t, c in events_ms]
    monkeypatch.setattr(decoder, "decode", fake_decode)
    monkeypatch.setattr(engine, "load_model", lambda _path: FrameRnn().eval())


def _write_click_track(path, seconds=2.0):
    import soundfile as sf
    sr = 44100
    audio = np.zeros((int(sr * seconds), 2), dtype=np.float32)
    audio[::sr // 2] = 0.8
    sf.write(path, audio, sr)


def test_engine_writes_schema_valid_unquantized_chart(tmp_path, monkeypatch):
    _fake_transcription(monkeypatch, [(123.4, "kick"), (511.6, "hihat"), (777.0, "cymbal")])
    audio = tmp_path / "song.wav"
    _write_click_track(audio)
    out = tmp_path / "out.bsm"
    debug = tmp_path / "debug.json"
    summary = engine.transcribe(audio, out, debug_path=debug, separate=False,
                                forced_bpm=97.5, forced_offset=0.321, log=lambda _m: None)
    chart = json.loads(out.read_text(encoding="utf-8"))
    assert [(h["time"], h["component"]) for h in chart["hitObjects"]] == [
        (123, "kick"), (512, "hihat_closed"), (777, "crash")]
    # Forced tempo/offset are grid metadata: notes are not moved or snapped.
    assert chart["timing"]["bpm"] == 97.5
    assert chart["timing"]["offset"] == 321
    assert chart["timing"]["timingPoints"][0]["time"] == 321
    assert summary["grid"]["quantized"] is False
    assert json.loads(debug.read_text())["engine"] == "adtof"
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "shared/schemas/beatmap_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(chart, schema)


def test_engine_adds_window_start_to_note_times(tmp_path, monkeypatch):
    _fake_transcription(monkeypatch, [(100.0, "snare")])
    audio = tmp_path / "song.wav"
    _write_click_track(audio, seconds=3.0)
    out = tmp_path / "out.bsm"
    engine.transcribe(audio, out, separate=False, start_time=1.5, end_time=2.5, log=lambda _m: None)
    chart = json.loads(out.read_text(encoding="utf-8"))
    assert chart["hitObjects"][0]["time"] == 1600


def test_engine_fails_instead_of_inventing_notes(tmp_path, monkeypatch):
    _fake_transcription(monkeypatch, [])
    audio = tmp_path / "song.wav"
    _write_click_track(audio)
    with pytest.raises(RuntimeError, match="No drum hits"):
        engine.transcribe(audio, tmp_path / "out.bsm", separate=False, log=lambda _m: None)
    assert not (tmp_path / "out.bsm").exists()


def test_cli_defaults_to_adtof_and_routes_arguments(tmp_path, monkeypatch):
    from pipeline import process

    audio = tmp_path / "song.wav"
    _write_click_track(audio)
    calls = {}

    def fake_transcribe(input_path, output_path, **kwargs):
        calls.update(kwargs, input=input_path, output=output_path)
        return {}

    import adtof_engine.engine as engine_module
    monkeypatch.setattr(engine_module, "transcribe", fake_transcribe)
    monkeypatch.setattr(sys, "argv", ["process", "--input", str(audio), "--output", str(tmp_path / "o.bsm"),
                                      "--mode", "gameplay", "--quantization", "sixteenth",
                                      "--force-bpm", "120", "--force-offset", "0.5", "--no-separation"])
    assert process.main() == 0
    assert calls["separate"] is False
    assert calls["forced_bpm"] == 120.0 and calls["forced_offset"] == 0.5


@needs_weights
def test_audited_weights_load():
    model = load_model(WEIGHTS)
    assert sum(p.numel() for p in model.parameters()) > 0
    assert engine.WEIGHTS_SHA256 == WEIGHTS_SHA256


@needs_weights
@pytest.mark.skipif(not FIXTURE_STEM.is_file() or not FIXTURE_AUDIT.is_dir(), reason="recovery fixture absent")
def test_bitwise_parity_with_audited_model_outputs():
    import soundfile as sf
    audio, sr = sf.read(FIXTURE_STEM, dtype="float32")
    assert sr == 44100
    torch.set_num_threads(2)
    with torch.no_grad():
        act = load_model(WEIGHTS)(torch.from_numpy(frontend.features(audio))[None])[0].numpy()
    reference = np.load(FIXTURE_AUDIT / "activations.npy")
    reference = reference[0] if reference.ndim == 3 else reference
    assert np.array_equal(act, reference)
    expected = json.loads((FIXTURE_AUDIT / "predictions.json").read_text())["hitObjects"]
    assert [(e["time"], e["component"]) for e in decoder.decode(act)] == \
        [(e["time"], e["component"]) for e in expected]
    assert set(FAMILIES) >= {e["component"] for e in expected}
