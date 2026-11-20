"""Change only spatial input to the inherited Demucs wrapper; retain mono gain.

This produces a separate candidate, never modifies completed drafts or defaults.
"""
import argparse
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import json
from pathlib import Path
import random
import shutil
import sys
import time

import numpy as np
import soundfile as sf
import torch

from transcribe import PIPELINE, sha256, validate_chart, REPO
from transcribe_reference import reference_preflight, native_chart, write_json
from evaluate_adtof import FAMILY_COMPONENTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--reference-repo", type=Path, required=True)
    args = parser.parse_args()
    root, reference = args.root.resolve(), args.reference_repo.resolve()
    if root.drive.upper() != "C:":
        raise ValueError("New recovery output must be on C:")
    weights = reference_preflight(reference)
    old = json.loads((root / "reference-comparison/run.json").read_text())
    old_chart = json.loads((root / "reference-comparison/separated/chart.bsm").read_text())
    if old["status"] != "complete":
        raise ValueError("Prior paired run incomplete")
    audio = root / "reference-comparison/separated" / old_chart["audio"]["filename"]
    if sha256(audio) != old["input"]["sha256"]:
        raise ValueError("Audio changed")
    out = root / "stereo-probe"
    out.mkdir(exist_ok=False)
    sys.path.insert(0, str(PIPELINE))
    sys.path.insert(0, str(reference / "src"))
    import librosa
    from separation.demucs_separator import separate_drums
    from adtof_pytorch import transcribe_to_midi, PeakPicker, LABELS_5, FRAME_RNN_THRESHOLDS, activations_to_pretty_midi
    manifest = {"status": "started", "input_sha256": sha256(audio), "weights_sha256": sha256(weights),
        "code_sha256": sha256(Path(__file__).resolve()), "source_run_sha256": sha256(root / "reference-comparison/run.json"),
        "change": "Keep stereo channels instead of duplicating mono. Divide both by identical mono peak gain.",
        "fixed": "htdemucs_ft, overlap .25, seed 0, mean separated stereo to mono, default ADTOF thresholds, CPU ADTOF",
        "ground_truth": None}
    write_json(out / "run.json", manifest)
    try:
        torch.set_num_threads(2)
        random.seed(0); np.random.seed(0); torch.manual_seed(0)
        y, sr = librosa.load(audio, sr=44100, mono=False)
        if y.ndim != 2 or y.shape[0] != 2:
            raise ValueError("Stereo source required")
        mono_peak = float(np.abs(librosa.to_mono(y)).max())
        y = y / mono_peak
        start = time.perf_counter()
        with (out / "inference.log").open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                stem, sr = separate_drums((y, sr), model_name="htdemucs_ft")
                if len(stem) != y.shape[1] or not np.isfinite(stem).all():
                    raise ValueError("Invalid stem")
                sf.write(out / "drums.wav", stem, sr, subtype="FLOAT")
                activations = transcribe_to_midi(out / "drums.wav", out / "reference.mid", weights=weights,
                                                device="cpu", return_activations=True)
        if "Missing keys" in (out / "inference.log").read_text(encoding="utf-8"):
            raise ValueError("Reference weights failed to load")
        np.save(out / "activations.npy", activations)
        peaks = PeakPicker(thresholds=FRAME_RNN_THRESHOLDS).pick(activations, LABELS_5)[0]
        events = sorted([{"time": t * 1000, "component": FAMILY_COMPONENTS[p]}
                         for p, times in peaks.items() for t in times], key=lambda e:e["time"])
        write_json(out / "predictions.json", {"hitObjects": events})
        activations_to_pretty_midi(peaks).write(str(out / "reference.mid"))
        shutil.copy2(audio, out / audio.name)
        assert sha256(out / audio.name) == old["input"]["sha256"]
        chart = native_chart(events, title=old_chart["metadata"]["title"], artist=old_chart["metadata"]["artist"],
            audio_name=audio.name, audio_hash=sha256(audio), duration_ms=old_chart["audio"]["duration"],
            sr=old_chart["audio"]["sampleRate"], bpm=old_chart["timing"]["bpm"], arm="stereo-separation probe")
        import jsonschema
        jsonschema.validate(chart, json.loads((REPO / "shared/schemas/beatmap_schema.json").read_text()))
        manifest.update(status="complete", runtime_seconds=time.perf_counter()-start, mono_peak_gain=mono_peak,
                        validation=validate_chart(chart, out), family_counts=dict(Counter(e["component"] for e in events)),
                        stem_sha256=sha256(out/"drums.wav"), prediction_sha256=sha256(out/"predictions.json"))
        write_json(out/"chart.bsm", chart)
        print(json.dumps(manifest["family_counts"]), flush=True)
    except Exception as exc:
        manifest.update(status="failed", error=str(exc))
        raise
    finally:
        write_json(out / "run.json", manifest)


if __name__ == "__main__":
    main()
