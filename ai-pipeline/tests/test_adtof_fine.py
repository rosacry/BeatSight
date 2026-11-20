"""Contract tests for the experimental 16-class model path of the ADTOF engine."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

from adtof_engine import engine, fine
from adtof_engine.fine import FINE_CLASSES, FINE_COMPONENTS, FineFrameRnn, decode_fine, load_fine_model

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_RUN = Path(r"C:\Users\10ros\BeatSight-Recovery\2026-10-16-finetune-01\runs\smoke-02")


def _model_dir(tmp_path, state=None, thresholds=None):
    d = tmp_path / "model"
    d.mkdir()
    torch.save({"model": state if state is not None else FineFrameRnn().state_dict()}, d / "best.pt")
    th = thresholds if thresholds is not None else {c: {"threshold": 0.3} for c in FINE_CLASSES}
    (d / "thresholds.json").write_text(json.dumps(th))
    return d


def test_components_are_schema_ids_and_cover_all_classes():
    schema = json.loads((REPO_ROOT / "shared/schemas/beatmap_schema.json").read_text(encoding="utf-8"))
    allowed = set(schema["$defs"]["drumComponent"]["enum"])
    assert list(FINE_COMPONENTS) == list(FINE_CLASSES)
    assert set(FINE_COMPONENTS.values()) <= allowed
    assert len(set(FINE_COMPONENTS.values())) == len(FINE_CLASSES)


def test_decode_uses_per_class_thresholds_and_maps_components():
    acts = np.zeros((300, 16), np.float32)
    acts[100, FINE_CLASSES.index("RD")] = 0.5   # ride above its 0.4 threshold
    acts[150, FINE_CLASSES.index("SS")] = 0.5   # cross-stick above 0.2
    acts[200, FINE_CLASSES.index("CR")] = 0.5   # crash below its 0.6 threshold
    th = np.full(16, 0.2)
    th[FINE_CLASSES.index("RD")], th[FINE_CLASSES.index("CR")] = 0.4, 0.6
    events = decode_fine(acts, th)
    assert [(e["time"], e["component"]) for e in events] == [(1000.0, "ride"), (1500.0, "cross_stick")]
    with pytest.raises(ValueError):
        decode_fine(np.zeros((10, 5), np.float32), th)


def _spikes(*hits, frames=400):
    """hits: (class, frame, activation) -> (frames, 16) activations with isolated peaks."""
    acts = np.zeros((frames, 16), np.float32)
    for c, frame, value in hits:
        acts[frame, FINE_CLASSES.index(c)] = value
    return acts


def test_hihat_classes_on_one_stroke_become_one_event_with_the_strongest_class():
    acts = _spikes(("HHC", 100, 0.5), ("HHP", 101, 0.4), ("HHO", 102, 0.9), ("KD", 100, 0.5))
    th = np.full(16, 0.2)
    events = [(e["time"], e["component"]) for e in decode_fine(acts, th)]
    assert events == [(1000.0, "hihat_open"), (1000.0, "kick")]  # left time, strongest class
    plain = [(e["time"], e["component"]) for e in decode_fine(acts, th, hh_combine_seconds=None)]
    assert plain == [(1000.0, "hihat_closed"), (1000.0, "kick"), (1010.0, "hihat_pedal"), (1020.0, "hihat_open")]


def test_hihat_rule_keeps_left_retention_and_leaves_other_families_alone():
    # 1.00 and 1.02 merge; 1.04 is 40 ms after the retained left event, so it stays (no chaining).
    acts = _spikes(("HHC", 100, 0.5), ("HHP", 102, 0.4), ("HHC", 104, 0.5), ("HHO", 200, 0.5), ("HHC", 203, 0.5),
                   ("CR", 300, 0.5), ("RD", 301, 0.5))
    events = [(round(e["time"], 6), e["component"]) for e in decode_fine(acts, np.full(16, 0.2), cymbal_combine_seconds=None)]
    assert events == [(1000.0, "hihat_closed"), (1040.0, "hihat_closed"), (2000.0, "hihat_open"), (2030.0, "hihat_closed"),
                      (3000.0, "crash"), (3010.0, "ride")]


DIAGNOSIS_ROOT = Path(r"C:\Users\10ros\BeatSight-Recovery\2026-10-23-tierb-drop-diagnosis-01")


@pytest.mark.skipif(not (DIAGNOSIS_ROOT / "validate_combine.py").is_file(), reason="diagnosis root absent")
def test_hihat_rule_equals_the_validated_research_rule():
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_combine_rule", DIAGNOSIS_ROOT / "validate_combine.py")
    research = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(research)
    rng = np.random.default_rng(20261023)
    for _ in range(20):
        acts = np.zeros((3000, 16), np.float32)
        for c in ("HHC", "HHP", "HHO", "KD", "CR"):
            frames = rng.choice(3000, size=120, replace=False)
            acts[frames, FINE_CLASSES.index(c)] = rng.uniform(0.25, 1.0, size=120)
        th = rng.uniform(0.1, 0.5, size=16)
        pred = research.hh_combine(research.peaks(acts, th), research.VARIANTS["W20"])
        want = sorted((t * 1000, FINE_COMPONENTS[c]) for c, ts in pred.items() for t in ts)
        got = [(e["time"], e["component"]) for e in decode_fine(acts, th, cymbal_combine_seconds=None)]
        assert got == want


def test_ride_bell_and_crash_on_one_hit_become_one_event_china_and_splash_stay():
    acts = _spikes(("RD", 100, 0.5), ("CR", 101, 0.9), ("RB", 200, 0.7), ("RD", 202, 0.4),
                   ("CH", 300, 0.6), ("CR", 300, 0.8), ("SP", 400, 0.5), ("RD", 401, 0.6), frames=600)
    events = [(round(e["time"], 6), e["component"]) for e in decode_fine(acts, np.full(16, 0.2))]
    assert events == [(1000.0, "crash"), (2000.0, "ride_bell"), (3000.0, "china"), (3000.0, "crash"),
                      (4000.0, "splash"), (4010.0, "ride")]
    plain = [e["component"] for e in decode_fine(acts, np.full(16, 0.2), cymbal_combine_seconds=None)]
    assert plain.count("ride") == 3 and plain.count("crash") == 2


def test_percussion_is_left_out_of_charts_unless_asked_for():
    acts = _spikes(("OT", 100, 0.9), ("KD", 100, 0.5), ("CB", 200, 0.5), ("SD", 300, 0.5))
    th = np.full(16, 0.2)
    assert fine.DROPPED_CLASSES == ("OT",)
    assert [(e["time"], e["component"]) for e in decode_fine(acts, th)] == [(1000.0, "kick"), (2000.0, "cowbell"), (3000.0, "snare")]
    kept = [(e["time"], e["component"]) for e in decode_fine(acts, th, drop_classes=())]
    assert kept == [(1000.0, "kick"), (1000.0, "percussion"), (2000.0, "cowbell"), (3000.0, "snare")]


CYMBAL_ROOT = Path(r"C:\Users\10ros\BeatSight-Recovery\2026-10-24-cymbal-ghost-rules-01")


@pytest.mark.skipif(not (CYMBAL_ROOT / "rules.py").is_file(), reason="cymbal rule root absent")
def test_cymbal_rule_equals_the_tested_research_rule():
    import importlib.util

    spec = importlib.util.spec_from_file_location("cymbal_ghost_rules", CYMBAL_ROOT / "rules.py")
    research = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(research)
    assert fine.CYMBAL_COMBINE_CLASSES == research.CYMBAL_VARIANTS["C20-ridecrash"]
    rng = np.random.default_rng(20261024)
    for _ in range(20):
        acts = np.zeros((3000, 16), np.float32)
        for c in ("HHC", "HHO", "RD", "RB", "CR", "CH", "SP", "KD"):
            frames = rng.choice(3000, size=120, replace=False)
            acts[frames, FINE_CLASSES.index(c)] = rng.uniform(0.25, 1.0, size=120)
        th = rng.uniform(0.1, 0.5, size=16)
        pred = research.combine_group(research.base_peaks(acts, th), acts, research.CYMBAL_VARIANTS["C20-ridecrash"])
        want = sorted((t * 1000, FINE_COMPONENTS[c]) for c, ts in pred.items() for t in ts)
        assert [(e["time"], e["component"]) for e in decode_fine(acts, th)] == want


def test_load_rejects_missing_or_bad_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_fine_model(tmp_path)
    bad = _model_dir(tmp_path, thresholds={"KD": {"threshold": 0.3}})
    with pytest.raises(ValueError, match="exactly"):
        load_fine_model(bad)
    shutil.rmtree(bad)
    zero = _model_dir(tmp_path, thresholds={c: {"threshold": 0.0} for c in FINE_CLASSES})
    with pytest.raises(ValueError, match="positive"):
        load_fine_model(zero)
    shutil.rmtree(zero)
    wrong = _model_dir(tmp_path, state={"output_layer.weight": torch.zeros(16, 120)})
    with pytest.raises(RuntimeError):
        load_fine_model(wrong)


@pytest.mark.skipif(not (SMOKE_RUN / "best.pt").is_file(), reason="training smoke checkpoint absent")
def test_loads_a_checkpoint_written_by_the_training_code(tmp_path):
    d = tmp_path / "run"
    d.mkdir()
    shutil.copy(SMOKE_RUN / "best.pt", d / "best.pt")
    (d / "thresholds.json").write_text(json.dumps({c: {"threshold": 0.3, "validation_f1": 0.5} for c in FINE_CLASSES}))
    model, th, info = load_fine_model(d)
    with torch.no_grad():
        out = model(torch.zeros(1, 50, 84, 1))
    assert out.shape == (1, 50, 16) and th.shape == (16,) and len(info["weights_sha256"]) == 64


def test_engine_writes_schema_valid_16_class_chart(tmp_path, monkeypatch):
    from tests.test_adtof_engine import _write_click_track  # same click-track fixture as the ADTOF tests

    d = _model_dir(tmp_path)
    monkeypatch.setattr(fine, "decode_fine", lambda _a, _t: [{"time": 123.4, "component": "kick"},
                                                             {"time": 500.0, "component": "ride_bell"},
                                                             {"time": 750.0, "component": "cross_stick"}])
    audio = tmp_path / "song.wav"
    _write_click_track(audio)
    out, debug = tmp_path / "out.bsm", tmp_path / "debug.json"
    summary = engine.transcribe(audio, out, debug_path=debug, separate=False, fine_model_dir=d, log=lambda _m: None)
    chart = json.loads(out.read_text(encoding="utf-8"))
    assert [(h["time"], h["component"]) for h in chart["hitObjects"]] == [(123, "kick"), (500, "ride_bell"), (750, "cross_stick")]
    assert chart["drumKit"]["components"] == ["kick", "ride_bell", "cross_stick"]
    assert "experimental" in chart["metadata"]["tags"]
    assert summary["engine"] == "beatsight-16class" and summary["family_counts"] == {"kick": 1, "ride_bell": 1, "cross_stick": 1}
    assert summary["engine_version"] == "beatsight-16class-4" and summary["hh_combine_seconds"] == fine.HH_COMBINE_SECONDS
    assert summary["cymbal_combine_seconds"] == fine.CYMBAL_COMBINE_SECONDS and summary["cymbal_combine_classes"] == ["RD", "RB", "CR"]
    assert summary["dropped_classes"] == ["OT"]
    assert json.loads(debug.read_text())["model"]["model_dir"] == str(d)
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((REPO_ROOT / "shared/schemas/beatmap_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(chart, schema)


def test_cli_routes_fine_model_and_rejects_it_for_legacy(tmp_path, monkeypatch):
    from pipeline import process
    from tests.test_adtof_engine import _write_click_track

    audio = tmp_path / "song.wav"
    _write_click_track(audio)
    calls = {}

    def fake_transcribe(input_path, output_path, **kwargs):
        calls.update(kwargs)
        return {}

    import adtof_engine.engine as engine_module
    monkeypatch.setattr(engine_module, "transcribe", fake_transcribe)
    base = ["process", "--input", str(audio), "--output", str(tmp_path / "o.bsm")]
    monkeypatch.setattr(sys, "argv", base + ["--fine-model", str(tmp_path)])
    assert process.main() == 0 and calls["fine_model_dir"] == str(tmp_path)
    monkeypatch.setattr(sys, "argv", base)
    calls.clear()
    assert process.main() == 0 and calls["fine_model_dir"] is None
    monkeypatch.setattr(sys, "argv", base + ["--engine", "legacy", "--fine-model", str(tmp_path)])
    assert process.main() == 2
