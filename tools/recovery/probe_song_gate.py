"""Paired section-gate probe with saved drum input and observable stages."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import soundfile as sf
from transcribe import PIPELINE, run, sha256
from evaluate_mdb import drum_family


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.drive.upper() != "C:":
        raise ValueError("Recovery output must be on C:")
    prior = json.loads((root / "reference-comparison/run.json").read_text())
    audio = root / "reference-comparison/separated" / Path(prior["input"]["path"]).name
    stem_path = root / "reference-comparison/drums.wav"
    assert sha256(audio) == prior["input"]["sha256"]
    assert sha256(stem_path) == prior["separation"]["sha256"]
    stem, sr = sf.read(stem_path, dtype="float32")
    out = root / "intro-gate-probe"
    out.mkdir(exist_ok=False)
    sys.path.insert(0, str(PIPELINE))
    from pipeline import process
    from transcription.multilabel_inference import MultiLabelDrumClassifier
    original_ensemble = MultiLabelDrumClassifier.classify_batch_ensemble
    original_refine = process.refine_onsets
    summary = {"code_sha256": sha256(Path(__file__).resolve()), "input_sha256": sha256(audio),
        "stem_sha256": sha256(stem_path), "ground_truth": None,
        "purpose": "Change only RMS section gate; capture detector/refinement/ensemble-input stages.", "arms": {}}
    for enabled in [True, False]:
        arm = "gate-on" if enabled else "gate-off"
        observations = {}
        def refine(*a, **kw):
            result = original_refine(*a, **kw)
            observations["refined_onsets_seconds"] = [e.time for e in result]
            return result
        def ensemble(self, *a, **kw):
            if a:
                raise ValueError("Expected named classifier arguments")
            observations["classifier_input_onsets_seconds"] = kw["onset_times"]
            observations["drum_array_sha256"] = hashlib.sha256(kw["demucs_audio"].tobytes()).hexdigest()
            observations["primary_array_sha256"] = hashlib.sha256(kw["hybrid_audio"].tobytes()).hexdigest()
            result = original_ensemble(self, **kw, use_rms_section_gating=enabled)
            return result
        with patch.object(process, "separate_drums", lambda *a, **kw:(stem.copy(), sr)), \
             patch.object(process, "refine_onsets", refine), \
             patch.object(MultiLabelDrumClassifier, "classify_batch_ensemble", ensemble):
            run(audio, out / arm)
        chart = json.loads((out / arm / "chart.bsm").read_text())
        observations["intro_10_20_counts"] = dict(Counter(drum_family(e["component"])
            for e in chart["hitObjects"] if 10000 <= e["time"] < 20000))
        (out / arm / "stages.json").write_text(json.dumps(observations, indent=2))
        summary["arms"][arm] = observations
        print(arm, observations["intro_10_20_counts"], flush=True)
    for key in ["classifier_input_onsets_seconds", "refined_onsets_seconds", "drum_array_sha256", "primary_array_sha256"]:
        assert summary["arms"]["gate-on"][key] == summary["arms"]["gate-off"][key], key
    summary["identical_paired_inputs"] = True
    candidates=json.loads((root / "review/intro-hihat-probe.json").read_text())["shared_candidates_absent_inherited_50ms"]
    onsets = summary["arms"]["gate-on"]["classifier_input_onsets_seconds"]
    summary["original_missing_candidates_near_classifier_input_50ms"] = sum(
        any(abs(t-u*1000)<=50 for u in onsets) for t in candidates)
    summary["original_missing_candidates_total"] = len(candidates)
    summary["limits"] = "Reference candidates unverified. This probe uses a saved stem, not byte-proven identical to original inherited separation; interpret gate difference within pair."
    (out / "summary.json").write_text(json.dumps(summary,indent=2))


if __name__ == "__main__":
    main()
