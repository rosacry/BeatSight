"""Evaluate exported charts against MDB Drums events, including onset errors.

This is a diagnostic benchmark. Historical training overlap is unknown.
Download audio and annotations separately; this script never trains a model.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

from transcribe import run, sha256


def drum_family(component: str) -> str:
    if component == "kick":
        return "KD"
    if component == "snare":
        return "SD"
    # MDB Table 1 places side-stick (SST) in Other, not Snare.
    if component == "cross_stick":
        return "OT"
    if component.startswith("hihat"):
        return "HH"
    if component.startswith("tom"):
        return "TT"
    if component == "cymbal" or component.startswith(("ride", "crash", "china", "splash")):
        return "CY"
    return "OT"


def match_events(reference: list[float], predicted: list[float], tolerance: float = 0.05) -> dict:
    """Maximum-cardinality, one-to-one matching on sorted timestamp intervals."""
    reference, predicted = sorted(reference), sorted(predicted)
    i = j = true_positive = 0
    while i < len(reference) and j < len(predicted):
        delta = predicted[j] - reference[i]
        if abs(delta) <= tolerance + 1e-9:
            true_positive += 1
            i += 1
            j += 1
        elif delta < -tolerance:
            j += 1
        else:
            i += 1
    return scores(true_positive, len(predicted) - true_positive, len(reference) - true_positive)


def scores(tp: int, fp: int, fn: int) -> dict:
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def evaluate(chart: dict, annotations: Path) -> dict:
    truth, predictions = defaultdict(list), defaultdict(list)
    for line in annotations.read_text(encoding="utf-8").splitlines():
        if line.strip():
            time, label = line.split()
            truth[label].append(float(time))
    for hit in chart["hitObjects"]:
        predictions[drum_family(hit["component"])].append(hit["time"] / 1000.0)
    by_class = {label: match_events(truth[label], predictions[label])
                for label in sorted(truth.keys() | predictions.keys())}
    totals = {key: sum(row[key] for row in by_class.values()) for key in ("tp", "fp", "fn")}
    return {"micro": scores(**totals), "by_class": by_class}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("legacy", "faithful"), required=True)
    parser.add_argument("--tracks", nargs="+", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    summary = {"profile": args.profile, "tolerance_seconds": 0.05,
               "task": "Full mix -> separated drums -> exported chart, 6 broad drum families",
               "training_overlap": "Unknown: diagnostic only, not a held-out accuracy claim",
               "tracks": []}
    for track in args.tracks:
        audio = args.dataset / f"{track}_MIX.wav"
        labels = args.dataset / f"{track}_class.txt"
        result = run(audio, args.output_dir / track, profile=args.profile)
        chart = json.loads((args.output_dir / track / "chart.bsm").read_text(encoding="utf-8"))
        row = {"track": track, "input_sha256": sha256(audio),
               "annotation_sha256": sha256(labels), "runtime_seconds": result["result"]["processing_time"],
               **evaluate(chart, labels)}
        summary["tracks"].append(row)
        summary["micro"] = scores(**{key: sum(t["micro"][key] for t in summary["tracks"])
                                     for key in ("tp", "fp", "fn")})
        (args.output_dir / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
