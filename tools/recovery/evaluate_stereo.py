"""Bounded stereo-input ablation against preserved annotated development data."""
import argparse
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
import json
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch

from transcribe import PIPELINE, sha256
from transcribe_reference import reference_preflight, write_json
from evaluate_adtof import FAMILY_COMPONENTS
from evaluate_mdb import scores
from score_timing import evaluate_timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--reference-repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.drive.upper() != "C:":
        raise ValueError("C: output required")
    weights = reference_preflight(args.reference_repo)
    dataset = args.data_root / "diagnostic-mdb-plus-seven-inputs"
    sources = json.loads((dataset / "sources.json").read_text())
    out.mkdir(exist_ok=False)
    sys.path.insert(0, str(PIPELINE))
    sys.path.insert(0, str(args.reference_repo / "src"))
    import librosa
    import soundfile as sf
    from separation.demucs_separator import separate_drums
    from adtof_pytorch import transcribe_to_midi, PeakPicker, FRAME_RNN_THRESHOLDS, LABELS_5
    torch.set_num_threads(2)
    result = {"status": "started", "rule": "Preserve stereo with identical mono-derived peak gain before Demucs; mean output to mono.",
              "training_overlap": "unknown", "purpose": "Existing development diagnostic, not held-out user-song accuracy",
              "weights_sha256": sha256(weights), "code_sha256": sha256(Path(__file__).resolve()),
              "source_manifest_sha256": sha256(dataset / "sources.json"), "tracks": []}
    write_json(out / "metrics.json", result)
    for src in sources["tracks"]:
        name = src["track"]
        audio, annotations = dataset / f"{name}_MIX.wav", dataset / f"{name}_class.txt"
        assert sha256(audio) == src["audio_sha256"]
        assert sha256(annotations) == src["annotation_sha256"]
        y, sr = librosa.load(audio, sr=44100, mono=False)
        if y.ndim == 1:
            y = np.stack([y,y])
        y = y / max(float(np.abs(librosa.to_mono(y)).max()), 1e-10)
        random.seed(0); np.random.seed(0); torch.manual_seed(0)
        start = time.perf_counter()
        with (out / f"{name}.log").open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                stem, sr = separate_drums((y,sr),model_name="htdemucs_ft")
                assert len(stem)==y.shape[1] and np.isfinite(stem).all()
                stem_path = out / f"{name}.drums.wav"
                sf.write(stem_path,stem,sr,subtype="FLOAT")
                act = transcribe_to_midi(stem_path, out / f"{name}.mid",weights=weights,device="cpu",return_activations=True)
        if "Missing keys" in (out / f"{name}.log").read_text(encoding="utf-8"):
            raise ValueError("Invalid parameter load")
        np.save(out / f"{name}.activations.npy",act)
        peaks=PeakPicker(thresholds=FRAME_RNN_THRESHOLDS).pick(act,LABELS_5)[0]
        chart={"hitObjects":sorted([{"time":t*1000,"component":FAMILY_COMPONENTS[p]}
                                   for p,ts in peaks.items() for t in ts],key=lambda e:e["time"])}
        write_json(out / f"{name}.predictions.json",chart)
        baseline_path=list(args.data_root.glob(f"diagnostic-mdb-plus-*-adtof-separated/{name}.predictions.json"))
        assert len(baseline_path)==1
        baseline=json.loads(baseline_path[0].read_text())
        truth=defaultdict(list)
        for line in annotations.read_text().splitlines():
            t,f=line.split(); truth[f].append(float(t))
        row={"track":name,"input_sha256":sha256(audio),"annotation_sha256":sha256(annotations),
             "baseline_sha256":sha256(baseline_path[0]),"stem_sha256":sha256(stem_path),
             "runtime_seconds":time.perf_counter()-start,"scores":{}}
        for ms in [25,50]:
            row["scores"][str(ms)]={"mono":evaluate_timing(baseline,truth,ms/1000),
                                    "stereo":evaluate_timing(chart,truth,ms/1000)}
        result["tracks"].append(row)
        write_json(out / "metrics.json",result)
        print(json.dumps({"track":name,"mono_f1":row["scores"]["50"]["mono"]["micro"]["f1"],
                          "stereo_f1":row["scores"]["50"]["stereo"]["micro"]["f1"]}),flush=True)
    result["micro"]={ms:{arm:scores(**{k:sum(t["scores"][ms][arm]["micro"][k] for t in result["tracks"])
                         for k in ["tp","fp","fn"]}) for arm in ["mono","stereo"]} for ms in ["25","50"]}
    result["by_family_50ms"]={arm:{f:scores(**{k:sum(t["scores"]["50"][arm]["by_family"].get(f,{}).get(k,0)
        for t in result["tracks"]) for k in ["tp","fp","fn"]}) for f in ["KD","SD","HH","TT","CY","OT"]} for arm in ["mono","stereo"]}
    result["status"]="complete"
    write_json(out / "metrics.json",result)
    print(json.dumps(result["micro"]),flush=True)


if __name__ == "__main__":
    main()
