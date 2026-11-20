"""Re-score saved predictions without rerunning inference or editing old metrics."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from evaluate_mdb import evaluate, scores
from transcribe import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new score file")
    root = args.root
    tracks = ["MusicDelta_80sRock", "MusicDelta_SpeedMetal", "MusicDelta_CoolJazz"]
    sources = {
        "legacy": "benchmark-legacy-v2/{track}/chart.bsm",
        "faithful": "benchmark-faithful/{track}/chart.bsm",
        "section_gate_on": "benchmark-section-ablation/{track}/gate_on/chart.bsm",
        "section_gate_off": "benchmark-section-ablation/{track}/gate_off/chart.bsm",
        "adtof": "benchmark-adtof-reproduced/{track}.predictions.json",
        "adtof_separated": "benchmark-adtof-separated/{track}.predictions.json",
    }
    report = {"mapping_revision": "MDB Table 1: side-stick maps to OT, not SD",
              "mapping_source": "https://www.open-access.bcu.ac.uk/6179/1/Southall2017a.pdf",
              "tolerance_seconds": 0.05, "training_overlap": "Unknown: diagnostics only",
              "systems": {}}
    for system, pattern in sources.items():
        rows = []
        for track in tracks:
            prediction = root / pattern.format(track=track)
            labels = root / "benchmark" / f"{track}_class.txt"
            chart = json.loads(prediction.read_text(encoding="utf-8"))
            rows.append({"track": track, "prediction": str(prediction),
                         "prediction_sha256": sha256(prediction), "labels_sha256": sha256(labels),
                         **evaluate(chart, labels)})
        report["systems"][system] = {"tracks": rows, "micro": scores(**{
            key: sum(row["micro"][key] for row in rows) for key in ("tp", "fp", "fn")})}
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({key: data["micro"] for key, data in report["systems"].items()}, indent=2))


if __name__ == "__main__":
    main()
