"""Diagnose HH/CY co-detections; never change charts or production thresholds."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from evaluate_mdb import drum_family, scores
from score_timing import evaluate_timing
from transcribe import sha256


def suppress_overlaps(chart):
    """Fixed diagnostic: remove HH within one 10 ms frame of a CY prediction."""
    cymbals = [n for n in chart["hitObjects"] if drum_family(n["component"]) == "CY"]
    kept, removed = [], []
    for note in chart["hitObjects"]:
        nearby = [c for c in cymbals if abs(note["time"] - c["time"]) <= 10 + 1e-7]
        if drum_family(note["component"]) == "HH" and nearby:
            closest = min(nearby, key=lambda c: abs(note["time"] - c["time"]))
            removed.append({"hihat": note, "cymbal": closest,
                            "delta_ms": note["time"] - closest["time"]})
        else:
            kept.append(note)
    return {"hitObjects": kept}, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--stereo-diagnostic", type=Path, required=True)
    parser.add_argument("--song-roots", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out.drive.upper() != "C:":
        raise ValueError("New output must be on C:")
    out.mkdir(parents=True, exist_ok=False)
    data = args.data_root / "diagnostic-mdb-plus-seven-inputs"
    sources = json.loads((data / "sources.json").read_text())
    prior = json.loads((args.stereo_diagnostic / "metrics.json").read_text())
    result = {"status": "started", "rule": "Remove HH predicted within 10 ms of CY, fixed before scoring; diagnostic only",
              "training_overlap": "unknown", "dataset_role": "previously used development diagnostic",
              "annotations_independently_audited": False, "parameter_search": False,
              "code_sha256": sha256(Path(__file__)), "tracks": [], "songs": []}
    for source in sources["tracks"]:
        name = source["track"]
        annotations = data / f"{name}_class.txt"
        if sha256(annotations) != source["annotation_sha256"]:
            raise ValueError("Annotation hash changed")
        pred_path = args.stereo_diagnostic / f"{name}.predictions.json"
        before = json.loads(pred_path.read_text())
        after, removed = suppress_overlaps(before)
        truth = defaultdict(list)
        for line in annotations.read_text().splitlines():
            time, family = line.split()
            truth[family].append(float(time))
        row = {"track": name, "prediction_sha256": sha256(pred_path),
               "annotation_sha256": sha256(annotations), "removed_count": len(removed),
               "candidates": removed, "scores": {}}
        for ms in (25, 50):
            original = evaluate_timing(before, truth, ms / 1000)
            expected = next(t for t in prior["tracks"] if t["track"] == name)["scores"][str(ms)]["stereo"]
            if original["micro"] != expected["micro"]:
                raise ValueError("Baseline scores no longer reproduce")
            row["scores"][str(ms)] = {"before": original, "after": evaluate_timing(after, truth, ms / 1000)}
        result["tracks"].append(row)
    for root in args.song_roots:
        pred_path = root / "stereo-probe/predictions.json"
        before = json.loads(pred_path.read_text())
        _, candidates = suppress_overlaps(before)
        result["songs"].append({"root": str(root), "prediction_sha256": sha256(pred_path),
                                "candidate_count": len(candidates), "candidates": candidates,
                                "status": "Review candidates, not verified errors; no automated changes made"})
    result["micro"] = {str(ms): {arm: scores(**{key: sum(t["scores"][str(ms)][arm]["micro"][key]
        for t in result["tracks"]) for key in ("tp", "fp", "fn")})
        for arm in ("before", "after")} for ms in (25, 50)}
    result["removed_count"] = sum(t["removed_count"] for t in result["tracks"])
    result["status"] = "complete"
    with (out / "metrics.json").open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: result[k] for k in ("removed_count", "micro")}))
    print(json.dumps([{k: s[k] for k in ("root", "candidate_count")} for s in result["songs"]]))


if __name__ == "__main__":
    main()
