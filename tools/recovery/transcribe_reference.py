"""Paired full-song ADTOF inference and native review drafts, without retraining.

Requires the pinned, separately acquired reference checkout. Keeps broad model
families in predictions.json; native lane aliases are explicitly presentation
proxies, not estimates of hat openness, cymbal identity, or tom pitch.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time
import uuid

from evaluate_adtof import REFERENCE_REVISION, REFERENCE_WEIGHTS_SHA256, FAMILY_COMPONENTS
from transcribe import PIPELINE, REPO, sha256, validate_chart

# The current native schema has detailed components but no broad HH/TT/CY IDs.
NATIVE_ALIASES = {"kick": "kick", "snare": "snare", "tom": "tom_mid",
                  "hihat": "hihat_closed", "cymbal": "crash"}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def reference_preflight(checkout: Path):
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if revision != REFERENCE_REVISION:
        raise ValueError("Reference revision differs from the audited version")
    changes = subprocess.check_output(
        ["git", "-C", str(checkout), "diff", "--name-only", "HEAD", "--", "src"], text=True)
    if changes.strip():
        raise ValueError("Reference source has local changes; review them before inference")
    weights = checkout / "src/adtof_pytorch/data/adtof_frame_rnn_pytorch_weights.pth"
    if sha256(weights) != REFERENCE_WEIGHTS_SHA256:
        raise ValueError("Reference weights differ; random initialization is forbidden")
    return weights


def native_chart(events, *, title, artist, audio_name, audio_hash, duration_ms, sr, bpm, arm):
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": "1.1.0",
        "metadata": {
            "title": title, "artist": artist, "creator": "BeatSight recovery draft",
            "difficulty": 0, "beatmapId": str(uuid.uuid4()), "createdAt": now,
            "modifiedAt": now, "tags": ["unreviewed-draft", "broad-families"],
            "description": f"Unreviewed ADTOF {arm} draft. Broad drum families only. "
                "Native hihat_closed, tom_mid and crash are display proxies for unspecified "
                "hi-hat, tom and cymbal; do not learn articulations from these names. "
                "Constant velocity is a display default, not measured dynamics. "
                "BPM/meter are provisional grid metadata; notes retain detected times. "
                "Song-level precision, recall and timing accuracy are unmeasured."
        },
        "audio": {"filename": audio_name, "hash": "sha256:" + audio_hash,
                  "duration": duration_ms, "sampleRate": sr},
        "timing": {"bpm": bpm, "offset": 0, "timeSignature": "4/4"},
        "drumKit": {"components": list(NATIVE_ALIASES.values()), "layout": "custom"},
        "hitObjects": [{"time": round(e["time"]), "component": NATIVE_ALIASES[e["component"]],
                        "velocity": 0.8} for e in events],
        "editor": {"visualLanes": 5, "beatGridVisible": False,
                   "aiGenerationMetadata": {"modelVersion": "ADTOF-pytorch broad families",
                       "processedAt": now, "manualEdits": False}}
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--reference-repo", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--artist", required=True)
    args = parser.parse_args()
    audio, out, reference = args.input.resolve(), args.output_dir.resolve(), args.reference_repo.resolve()
    if out.drive.upper() != "C:":
        raise ValueError("Recovery experiment output must be a new C: directory")
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    if not audio.is_file():
        raise FileNotFoundError(audio)
    weights = reference_preflight(reference)
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "started", "input": {"path": str(audio), "sha256": sha256(audio)},
                "reference_revision": REFERENCE_REVISION, "weights_sha256": sha256(weights),
                "source": "https://github.com/xavriley/ADTOF-pytorch",
                "training_overlap": "unknown", "ground_truth": None,
                "native_aliases": NATIVE_ALIASES, "seed": 0,
                "code_sha256": {str(p): sha256(p) for p in [Path(__file__).resolve(),
                    REPO / "tools/recovery/evaluate_adtof.py",
                    PIPELINE / "separation/demucs_separator.py", PIPELINE / "pipeline/preprocessing.py"]},
                "reference_code_sha256": {str(p.relative_to(reference)): sha256(p)
                    for p in sorted((reference / "src/adtof_pytorch").glob("*.py"))},
                "python": sys.executable,
                "packages": {p: metadata.version(p) for p in
                    ["torch", "librosa", "numpy", "demucs", "soundfile", "pretty_midi"]},
                "arms": {}}
    write_json(out / "run.json", manifest)
    try:
        import numpy as np
        import soundfile as sf
        import torch
        import librosa
        import jsonschema
        sys.path.insert(0, str(reference / "src"))
        sys.path.insert(0, str(PIPELINE))
        from adtof_pytorch import (transcribe_to_midi, PeakPicker, FRAME_RNN_THRESHOLDS,
                                  LABELS_5, activations_to_pretty_midi)
        from pipeline.preprocessing import preprocess_audio
        from separation.demucs_separator import separate_drums
        torch.set_num_threads(2)
        random.seed(0)
        np.random.seed(0)
        torch.manual_seed(0)
        manifest["thresholds"] = FRAME_RNN_THRESHOLDS
        manifest["fps"] = 100
        manifest["separation"] = {"model": "htdemucs_ft", "overlap": 0.25,
                                  "input": "normalized mono duplicated to stereo, inherited preprocessing",
                                  "checkpoint_files": {p.name: sha256(p) for p in
                                      (Path(torch.hub.get_dir()) / "checkpoints").glob("*.th")}}
        raw, raw_sr = sf.read(audio, dtype="float32", always_2d=True)
        if not np.isfinite(raw).all() or not np.any(raw):
            raise ValueError("Audio is nonfinite or silent")
        manifest["audio_health"] = {"sample_rate": raw_sr, "channels": raw.shape[1],
            "samples": len(raw), "duration_seconds": len(raw) / raw_sr,
            "peak_absolute": float(np.abs(raw).max()), "rms": float(np.sqrt(np.mean(raw ** 2)))}
        print(json.dumps(manifest["audio_health"]), flush=True)
        started = time.perf_counter()
        with (out / "separation.log").open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                stem, sr = separate_drums(preprocess_audio(str(audio)), model_name="htdemucs_ft")
        if not np.isfinite(stem).all() or len(stem) != round(len(raw) * sr / raw_sr):
            raise ValueError("Stem is nonfinite or changed duration")
        stem_path = out / "drums.wav"
        sf.write(stem_path, stem, sr, subtype="FLOAT")
        manifest["separation"].update(seconds=time.perf_counter() - started, sha256=sha256(stem_path))
        # Grid only: no detected note is snapped to this estimate.
        tempo, _ = librosa.beat.beat_track(y=stem, sr=sr)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        if not 20 <= bpm <= 400:
            bpm = 120.0
        manifest["grid"] = {"bpm_estimate": bpm, "meter_assumption": "4/4", "quantized": False}
        schema = json.loads((REPO / "shared/schemas/beatmap_schema.json").read_text())
        for name, inference_audio in [("full-mix", audio), ("separated", stem_path)]:
            folder = out / name
            folder.mkdir()
            shutil.copy2(audio, folder / audio.name)
            if sha256(folder / audio.name) != manifest["input"]["sha256"]:
                raise RuntimeError("Audio copy mismatch")
            start = time.perf_counter()
            with (folder / "inference.log").open("x", encoding="utf-8") as log:
                with redirect_stdout(log), redirect_stderr(log):
                    activations = transcribe_to_midi(inference_audio, folder / "reference.mid",
                        weights=weights, device="cpu", return_activations=True)
            log_text = (folder / "inference.log").read_text(encoding="utf-8")
            if "Missing keys" in log_text or "Unexpected keys" in log_text:
                raise RuntimeError("Reference parameter load mismatch")
            if not np.isfinite(activations).all():
                raise ValueError("Nonfinite model activations")
            np.save(folder / "activations.npy", activations)
            peaks = PeakPicker(thresholds=FRAME_RNN_THRESHOLDS, fps=100).pick(activations, labels=LABELS_5)[0]
            events = sorted([{"time": float(t) * 1000, "component": FAMILY_COMPONENTS[int(p)]}
                             for p, times in peaks.items() for t in times], key=lambda e: e["time"])
            write_json(folder / "predictions.json", {"hitObjects": events})
            activations_to_pretty_midi(peaks).write(str(folder / "reference.mid"))
            chart = native_chart(events, title=args.title, artist=args.artist,
                audio_name=audio.name, audio_hash=manifest["input"]["sha256"],
                duration_ms=round(len(raw) / raw_sr * 1000), sr=raw_sr, bpm=bpm, arm=name)
            jsonschema.validate(chart, schema)
            validation = validate_chart(chart, folder)
            write_json(folder / "chart.bsm", chart)
            manifest["arms"][name] = {"runtime_seconds": time.perf_counter() - start,
                "inference_audio_sha256": sha256(inference_audio), "validation": validation,
                "family_counts": dict(Counter(e["component"] for e in events)),
                "predictions_sha256": sha256(folder / "predictions.json"),
                "chart_sha256": sha256(folder / "chart.bsm")}
            write_json(out / "run.json", manifest)
            print(json.dumps({name: manifest["arms"][name]}), flush=True)
        manifest["status"] = "complete"
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        write_json(out / "run.json", manifest)


if __name__ == "__main__":
    main()
