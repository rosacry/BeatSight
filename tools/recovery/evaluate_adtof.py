"""Reproduce the local ADTOF reference comparison; no weights are bundled here.

Uses broad drum families only. Does not claim articulation recognition or
independent held-out accuracy. Requires an explicitly supplied upstream checkout.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import time

from evaluate_mdb import evaluate, scores
from transcribe import PIPELINE, sha256

REFERENCE_REVISION = "85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9"
REFERENCE_WEIGHTS_SHA256 = "1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320"
FAMILY_COMPONENTS = {35: "kick", 38: "snare", 47: "tom", 42: "hihat", 49: "cymbal"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-repo", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracks", nargs="+", required=True)
    parser.add_argument("--separate-drums", action="store_true", help="Evaluate on Demucs stems derived from the full mixes")
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.reference_repo), "rev-parse", "HEAD"], text=True).strip()
    if revision != REFERENCE_REVISION:
        raise ValueError("Reference revision differs from audited version; review before comparing")
    weights = args.reference_repo / "src/adtof_pytorch/data/adtof_frame_rnn_pytorch_weights.pth"
    if not weights.is_file() or sha256(weights) != REFERENCE_WEIGHTS_SHA256:
        raise ValueError("Reference weights missing or changed; random initialization is forbidden")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.reference_repo / "src"))
    import torch
    from adtof_pytorch import transcribe_to_midi, PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5
    torch.set_num_threads(2)
    torch.manual_seed(0)
    summary = {"source": "https://github.com/xavriley/ADTOF-pytorch", "revision": revision,
               "weights_sha256": sha256(weights), "thresholds": FRAME_RNN_THRESHOLDS,
               "tolerance_seconds": 0.05, "training_overlap": "Unknown; possibly present in training",
               "purpose": "Local research, five broad families; no articulation claims", "tracks": []}
    summary["separate_drums"] = args.separate_drums
    for track in args.tracks:
        audio = args.dataset / f"{track}_MIX.wav"
        annotations = args.dataset / f"{track}_class.txt"
        log = io.StringIO()
        start = time.perf_counter()
        with redirect_stdout(log), redirect_stderr(log):
            inference_audio = audio
            if args.separate_drums:
                import random
                import numpy as np
                import soundfile as sf
                sys.path.insert(0, str(PIPELINE))
                from pipeline.preprocessing import preprocess_audio
                from pipeline.separation.demucs_separator import separate_drums
                random.seed(0)
                np.random.seed(0)
                torch.manual_seed(0)
                stem, sr = separate_drums(preprocess_audio(str(audio)))
                inference_audio = args.output_dir / f"{track}.drums.wav"
                sf.write(str(inference_audio), stem.T if stem.ndim == 2 and stem.shape[0] <= 2 else stem,
                         sr, subtype="FLOAT")
            activations = transcribe_to_midi(inference_audio, args.output_dir / f"{track}.mid",
                                             weights=weights, return_activations=True, device="cpu")
        (args.output_dir / f"{track}.log").write_text(log.getvalue(), encoding="utf-8")
        if "Missing keys" in log.getvalue():
            raise RuntimeError("Reference model has missing parameters; invalid comparison")
        peaks = PeakPicker(thresholds=FRAME_RNN_THRESHOLDS, fps=100).pick(activations, labels=LABELS_5)[0]
        chart = {"hitObjects": sorted([
            {"time": float(t) * 1000.0, "component": FAMILY_COMPONENTS[int(pitch)]}
            for pitch, times in peaks.items() for t in times], key=lambda hit: hit["time"])}
        (args.output_dir / f"{track}.predictions.json").write_text(json.dumps(chart, indent=2), encoding="utf-8")
        row = {"track": track, "input_sha256": sha256(audio), "inference_audio_sha256": sha256(inference_audio),
               "annotation_sha256": sha256(annotations),
               "runtime_seconds": time.perf_counter() - start, **evaluate(chart, annotations)}
        summary["tracks"].append(row)
        summary["micro"] = scores(**{key: sum(t["micro"][key] for t in summary["tracks"])
                                     for key in ("tp", "fp", "fn")})
        (args.output_dir / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"track": track, "micro": row["micro"]}), flush=True)


if __name__ == "__main__":
    main()
