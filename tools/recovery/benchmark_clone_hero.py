"""Run frozen audio-only candidates on a previously prepared chart batch.

References never reach either model. Saves exact events/activations and scores
at fixed tolerances without post-hoc alignment or parameter tuning.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from importlib import metadata
import json
from pathlib import Path
import random
import subprocess
import sys
import time

import numpy as np
import soundfile as sf
import torch

from clone_hero_reference import family_reference
from evaluate_adtof import FAMILY_COMPONENTS
from evaluate_mdb import drum_family, scores
from score_timing import evaluate_timing
from transcribe import PIPELINE, REPO, sha256
from transcribe_reference import reference_preflight, write_json


def score_views(chart, events):
    primary = family_reference(events)
    broad = family_reference(events, merge_cymbals=True)
    merged = {"hitObjects": []}
    seen = set()
    for e in chart["hitObjects"]:
        f = drum_family(e["component"])
        component = "cymbal" if f in {"CY", "HH"} else e["component"]
        key = (e["time"], drum_family(component))
        if key not in seen:
            merged["hitObjects"].append({**e, "component": component})
            seen.add(key)
    return {str(ms): {"five_family_proxy": evaluate_timing(chart, primary, ms / 1000),
                      "cymbals_merged": evaluate_timing(merged, broad, ms / 1000)} for ms in (25, 50)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prepared", type=Path, required=True)
    ap.add_argument("--reference-repo", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    out = args.output_dir.resolve()
    if out.drive.upper() != "C:":
        raise ValueError("C: output required")
    weights = reference_preflight(args.reference_repo)
    sources = json.loads((args.prepared / "manifest.json").read_text())
    if sources["status"] != "complete":
        raise ValueError("Preparation incomplete")
    out.mkdir(exist_ok=False)
    sys.path[:0] = [str(PIPELINE), str(args.reference_repo / "src")]
    import librosa
    from separation.demucs_separator import separate_drums
    from adtof_pytorch import transcribe_to_midi, PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5
    torch.set_num_threads(2)
    manifest = {"status": "started", "interpretation": "provisional chart agreement, not audio-audited accuracy",
                "training_overlap": "unknown", "selection_sha256": sources["selection_sha256"],
                "prepared_manifest_sha256": sha256(args.prepared / "manifest.json"),
                "reference_weights_sha256": sha256(weights), "thresholds": FRAME_RNN_THRESHOLDS,
                "fixed": {"seed": 0, "demucs": "htdemucs_ft", "overlap": .25,
                          "separation_input": "stereo divided by mono peak", "adtof_device": "cpu", "fps": 100},
                "code_sha256": {str(p): sha256(p) for p in [Path(__file__).resolve(),
                     REPO / "tools/recovery/clone_hero_reference.py", REPO / "tools/recovery/score_timing.py",
                     REPO / "tools/recovery/transcribe.py", PIPELINE / "separation/demucs_separator.py"]},
                "packages": {p: metadata.version(p) for p in ["torch", "numpy", "librosa", "soundfile", "demucs"]},
                "demucs_checkpoints": {p.name: sha256(p) for p in (Path(torch.hub.get_dir()) / "checkpoints").glob("*.th")},
                "songs": []}
    write_json(out / "metrics.json", manifest)
    try:
        for src in sources["songs"]:
            slug = src["id"]
            folder = out / slug
            folder.mkdir()
            audio = args.prepared / slug / "mix.wav"
            ref_path = args.prepared / slug / "reference.json"
            if sha256(audio) != src["audio"]["sha256"] or sha256(ref_path) != src["reference_sha256"]:
                raise ValueError("Prepared data changed")
            ref = json.loads(ref_path.read_text())
            row = {"id": slug, "split": src["split"], "arms": {}}
            manifest["songs"].append(row)
            start = time.perf_counter()
            print(f"{slug}: inherited faithful", flush=True)
            with (folder / "faithful-launch.log").open("x", encoding="utf8") as log:
                subprocess.run([sys.executable, str(REPO / "tools/recovery/transcribe.py"),
                                "--input", str(audio), "--output-dir", str(folder / "inherited-faithful")],
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            legacy = json.loads((folder / "inherited-faithful/chart.bsm").read_text())
            row["arms"]["inherited-faithful"] = {"runtime_seconds": time.perf_counter() - start,
                    "predictions_sha256": sha256(folder / "inherited-faithful/chart.bsm"),
                    "scores": score_views(legacy, ref["events"])}
            write_json(out / "metrics.json", manifest)
            random.seed(0); np.random.seed(0); torch.manual_seed(0)
            y, sr = librosa.load(audio, sr=44100, mono=False)
            if y.ndim != 2 or y.shape[0] != 2 or not np.isfinite(y).all():
                raise ValueError("Expected finite stereo")
            y /= max(float(np.abs(librosa.to_mono(y)).max()), 1e-10)
            print(f"{slug}: stereo separation", flush=True)
            start = time.perf_counter()
            with (folder / "separation.log").open("x", encoding="utf8") as log, redirect_stdout(log), redirect_stderr(log):
                stem, sr = separate_drums((y, sr), model_name="htdemucs_ft")
            if len(stem) != y.shape[1] or not np.isfinite(stem).all():
                raise ValueError("Invalid separated audio")
            sf.write(folder / "drums.wav", stem, sr, subtype="FLOAT")
            row["separation"] = {"seconds": time.perf_counter() - start, "sha256": sha256(folder / "drums.wav")}
            del y, stem
            for arm, input_path in [("adtof-full-mix", audio), ("adtof-stereo-separated", folder / "drums.wav")]:
                print(f"{slug}: {arm}", flush=True)
                dest = folder / arm
                dest.mkdir()
                start = time.perf_counter()
                with (dest / "inference.log").open("x", encoding="utf8") as log, redirect_stdout(log), redirect_stderr(log):
                    act = transcribe_to_midi(input_path, dest / "reference.mid", weights=weights, device="cpu", return_activations=True)
                log_text = (dest / "inference.log").read_text(encoding="utf8")
                if any(x in log_text for x in ("Missing keys", "Unexpected keys")) or not np.isfinite(act).all():
                    raise ValueError("Invalid reference inference")
                np.save(dest / "activations.npy", act)
                peaks = PeakPicker(thresholds=FRAME_RNN_THRESHOLDS, fps=100).pick(act, LABELS_5)[0]
                prediction = {"hitObjects": sorted([{"time": float(t) * 1000, "component": FAMILY_COMPONENTS[p]}
                                    for p, ts in peaks.items() for t in ts], key=lambda n: n["time"])}
                write_json(dest / "predictions.json", prediction)
                row["arms"][arm] = {"runtime_seconds": time.perf_counter() - start,
                                   "predictions_sha256": sha256(dest / "predictions.json"),
                                   "scores": score_views(prediction, ref["events"])}
                write_json(out / "metrics.json", manifest)
            print(json.dumps({"song": slug, "F1_50ms_proxy": {a: v["scores"]["50"]["five_family_proxy"]["micro"]["f1"]
                                                            for a, v in row["arms"].items()}}), flush=True)
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = repr(exc)
        raise
    finally:
        write_json(out / "metrics.json", manifest)


if __name__ == "__main__":
    main()
