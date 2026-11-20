"""Paired exported-chart experiment: change only legacy RMS section gating.

Scoped patches are confined to this research process. Separation is performed
once per track and copied for each arm; onset/audio hashes must match exactly.
Application defaults are unchanged. Unknown training overlap limits conclusions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from evaluate_mdb import evaluate, scores
from transcribe import PIPELINE, run, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tracks", nargs="+", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(PIPELINE))
    from pipeline import process
    from transcription.multilabel_inference import MultiLabelDrumClassifier

    original_separator = process.separate_drums
    original_ensemble = MultiLabelDrumClassifier.classify_batch_ensemble
    summary = {"experiment": "RMS section gate on versus off; faithful profile in both arms",
               "seed": 0, "tolerance_seconds": 0.05,
               "training_overlap": "Unknown; diagnostic, not a held-out benchmark",
               "tracks": []}
    for track in args.tracks:
        audio = args.dataset / f"{track}_MIX.wav"
        annotations = args.dataset / f"{track}_class.txt"
        separation_cache = []

        def cached_separation(*positional, **keywords):
            if not separation_cache:
                separation_cache.append(original_separator(*positional, **keywords))
            samples, sample_rate = separation_cache[0]
            return samples.copy(), sample_rate

        track_result = {"track": track, "input_sha256": sha256(audio),
                        "annotation_sha256": sha256(annotations), "arms": {}}
        for enabled in (True, False):
            arm = "gate_on" if enabled else "gate_off"
            observations = []

            def recorded_ensemble(self, *positional, **keywords):
                if positional:
                    raise RuntimeError("Expected named ensemble inputs for paired verification")
                observations.append({
                    "drum_audio_sha256": hashlib.sha256(keywords["demucs_audio"].tobytes()).hexdigest(),
                    "primary_audio_sha256": hashlib.sha256(keywords["hybrid_audio"].tobytes()).hexdigest(),
                    "onsets_sha256": hashlib.sha256(json.dumps(keywords["onset_times"]).encode()).hexdigest(),
                    "onset_count": len(keywords["onset_times"]), "sample_rate": keywords["sr"],
                })
                return original_ensemble(self, **keywords, use_rms_section_gating=enabled)

            output = args.output_dir / track / arm
            with patch.object(process, "separate_drums", cached_separation), \
                    patch.object(MultiLabelDrumClassifier, "classify_batch_ensemble", recorded_ensemble):
                result = run(audio, output, profile="faithful")
            if len(observations) != 1:
                raise RuntimeError(f"Expected one ensemble invocation, got {len(observations)}")
            settings = {"use_rms_section_gating": enabled, "paired_inputs": observations[0],
                        "separation_reused": not enabled}
            (output / "experiment.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
            chart = json.loads((output / "chart.bsm").read_text(encoding="utf-8"))
            track_result["arms"][arm] = {**settings, **evaluate(chart, annotations)}
        first, second = track_result["arms"].values()
        if first["paired_inputs"] != second["paired_inputs"]:
            raise RuntimeError("Paired inputs differ; experiment invalid")
        summary["tracks"].append(track_result)
        summary["micro"] = {arm: scores(**{
            key: sum(t["arms"][arm]["micro"][key] for t in summary["tracks"])
            for key in ("tp", "fp", "fn")}) for arm in ("gate_on", "gate_off")}
        (args.output_dir / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({"track": track, "scores": {
            arm: data["micro"] for arm, data in track_result["arms"].items()}}), flush=True)


if __name__ == "__main__":
    main()
