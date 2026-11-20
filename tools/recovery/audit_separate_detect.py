"""Probe pinned Separate-and-Detect I/O without model weights or neural inference.

Execute only inspected AST methods from the saved author source. Real synthetic
WAV files exercise the loader; supplied peaks exercise only the postfilter.
This does not measure transcription quality or establish runtime parity.
"""
import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import soundfile as sf
import torch
import torchaudio


COMMIT = "0ac2fe6a35a7968d70ecfb8866cad025c350f5bd"


def load_tree(path):
    return ast.parse(path.read_text(encoding="utf8"), filename=str(path))


def function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def execute(nodes, namespace, filename):
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(filename), "exec"), namespace)


def audit(root, output_name="io-probes"):
    root = root.resolve()
    allowed = Path(r"C:\Users\10ros\BeatSight-Recovery").resolve()
    if root.parent != allowed or not root.is_dir():
        raise ValueError("Expected an existing, scoped C: experiment directory")
    if Path(output_name).name != output_name or not output_name.startswith("io-probes"):
        raise ValueError("Expected a single io-probes output directory name")
    out = root / output_name
    if out.exists():
        raise FileExistsError("Never rerun into completed probe output")
    source = root / "primary/source"
    tree = json.loads((root / "primary/github-tree.json").read_text())
    assert tree["sha"] == COMMIT and not tree["truncated"]
    entries = {e["path"]: e for e in tree["tree"]}
    verified = []
    for manifest in ["source-fetches.json", "source-support-fetches.json"]:
        for item in json.loads((root / "primary" / manifest).read_text()):
            p = source / item["relative_path"]
            data = p.read_bytes()
            assert hashlib.sha256(data).hexdigest() == item["sha256"]
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            assert blob == entries[item["relative_path"]]["sha"]
            verified.append(item["relative_path"])
    out.mkdir()
    checks = []

    def record(name, evidence):
        checks.append({"name": name, "observed": evidence})

    dataset_path = source / "src/utilities/data/dataset.py"
    dataset_tree = load_tree(dataset_path)
    cls = next(n for n in dataset_tree.body if isinstance(n, ast.ClassDef)
               and n.name == "StemGMDOnsetDataset")
    wanted = {"read_datafile", "_get_duration_sec_like_slakh", "_filter_tracks_like_slakh",
              "get_index_offset", "read_wav"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(methods) == len(wanted)
    probe_cls = ast.ClassDef(name="NativeLoaderProbe", bases=[], keywords=[],
                            body=methods, decorator_list=[])
    ns = {"os": os, "np": np, "torch": torch, "torchaudio": torchaudio}
    execute([probe_cls], ns, dataset_path)
    loader = ns["NativeLoaderProbe"]()
    loader.sampling_rate = 16000
    loader.segment_length = 163840
    loader.train = False
    loader.whole_track = False
    loader.config = {"path": {"stems": ["kick", "snare", "toms", "hi_hats", "cymbals"]}}

    fixtures = out / "duration-fixtures"
    fixtures.mkdir()
    durations = [9.0, 10.0, 10.24, 20.48, 20.49, 75.16, 450.0, 640.0]
    for duration in durations:
        folder = fixtures / str(duration)
        folder.mkdir()
        sf.write(folder / "drums.wav", np.zeros(round(duration * 8000), dtype=np.float32),
                 8000, subtype="PCM_16")
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        rows = loader.read_datafile(str(fixtures), None, False)
    for duration in durations:
        items = [row for row in rows if Path(row["wav_path"]).name == str(duration)]
        starts = [loader.get_index_offset(item)[1] for item in items]
        expected_count = 0 if duration < 10 or duration >= 640 else max(1, int(duration / 10.24))
        assert len(starts) == expected_count
        covered_to = min(duration, max(starts) + 10.24) if starts else 0.0
        record("native_coverage_" + str(duration), {
            "duration_seconds": duration, "segments": len(starts), "start_seconds": starts,
            "unread_tail_seconds": round(duration - covered_to, 6),
            "excluded": not bool(starts),
        })

    # Execute the actual filename expression and the author's evaluation parser.
    item_method = function(cls, "__getitem__")
    fname_stmt = next(n for n in item_method.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                              and t.slice.value == "fname" for t in n.targets))
    evaluator = source / "mdb_onset_evaluation.py"
    parse_ns = {}
    execute([function(load_tree(evaluator), "extract_segment_info")], parse_ns, evaluator)
    timing = []
    for row in rows:
        if Path(row["wav_path"]).name != "450.0":
            continue
        actual = loader.get_index_offset(row)[1]
        local = {"data_dict": {}, "track_id": "synthetic", "frame_offset": actual}
        execute([fname_stmt], local, dataset_path)
        name = local["data_dict"]["fname"]
        _, index, recovered = parse_ns["extract_segment_info"](name + ".wav")
        timing.append(dict(actual_start=actual, filename=name, parsed_index=index,
                           parsed_start=recovered, error_seconds=recovered - actual))
    wrong = [r for r in timing if abs(r["error_seconds"]) > 1e-6]
    assert len(wrong) == 1 and abs(wrong[0]["actual_start"] - 430.08) < 1e-6
    assert all(abs(r["error_seconds"] - 10.24) < 1e-6 for r in wrong)
    record("filename_evaluation_roundtrip", {"segments": len(timing), "mismatches": wrong})
    (out / "filename-roundtrip.json").write_text(json.dumps(timing, indent=2))

    for sr in [16000, 44100, 48000]:
        # Record arguments and raw PCM at the real torchaudio.load boundary.
        # Resampler DC gain makes amplitude-based time decoding unreliable.
        wav = out / f"time-ramp-{sr}.wav"
        sf.write(wav, np.arange(sr * 60, dtype=np.float32) / (sr * 100.0), sr, subtype="FLOAT")
        loads = []

        def observed_load(filename, **kwargs):
            raw, rate = torchaudio.load(filename, **kwargs)
            loads.append(dict(**kwargs, sample_rate=rate, raw_samples=raw.shape[-1],
                              first_raw_sample=float(raw[0, 0])))
            return raw, rate

        ns["torchaudio"] = SimpleNamespace(load=observed_load, functional=torchaudio.functional)
        decoded = loader.read_wav(str(wav), 10.24).numpy()[0]
        assert len(loads) == 1
        assert len(decoded) == 163840
        source_start = loads[0]["frame_offset"] / loads[0]["sample_rate"]
        expected = int(10.24 * 44100) / sr
        assert source_start == expected
        assert abs(loads[0]["first_raw_sample"] * 100.0 - source_start) < 1e-4
        zeros = len(decoded) - np.flatnonzero(decoded)[-1] - 1
        record(f"native_read_wav_{sr}", {
            "file_sample_rate": sr, "requested_start_seconds": 10.24,
            "observed_load": loads[0], "actual_source_start_seconds": source_start,
            "expected_source_start_seconds": expected,
            "start_error_seconds": source_start - 10.24, "output_samples": len(decoded),
            "trailing_zero_samples": int(zeros),
        })

    # Isolate the exact post-CNN source statements. This is not CNN inference.
    onset_path = source / "single_audio_onset_detection.py"
    onset_tree = load_tree(onset_path)
    supplied = np.array([0.1, 0.2, 0.5, 0.55, 10.04, 10.09])
    for family in ["kick", "snare", "toms", "hi_hats", "cymbals"]:
        fn = function(onset_tree, f"detect_{family}_onsets")
        begin = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == ("filtered" if family == "hi_hats" else "duration")
                             for t in n.targets))
        body = fn.body[begin:]
        wrapper = ast.FunctionDef(name="postfilter", args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=body, decorator_list=[])
        local = {"audio": np.zeros(163840), "sr": 16000,
                 "detected_onsets_cnn": supplied.copy(), "min_separation": 0.1}
        execute([wrapper], local, onset_path)
        filtered = local["postfilter"]()
        expected = [0.1, 0.2, 0.5, 10.04] if family == "hi_hats" else [0.2, 0.5, 0.55, 10.04]
        assert np.allclose(filtered, expected), (family, filtered)
        loaded_min = sum(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                         and n.id == "min_separation" for n in ast.walk(fn))
        assert loaded_min == (1 if family == "hi_hats" else 0)
        record("native_postfilter_" + family, {
            "supplied_peaks_seconds": supplied.tolist(), "retained_peaks_seconds": filtered,
            "min_separation_argument_reads": loaded_min,
            "neural_detector_executed": False,
        })

    result = {"commit": COMMIT, "verified_source_files": len(verified),
              "check_count": len(checks), "checks": checks,
              "limitations": ["No weights loaded, neural inference, or quality measurement.",
                              "Native loader methods executed outside training constructor.",
                              "Peak postfilter tested with supplied events, not madmom outputs.",
                              "Current torch runtime is not declared historical runtime parity."]}
    (out / "native-loader.log").write_text(log.getvalue(), encoding="utf8")
    (out / "results.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps({"checks": len(checks), "source_files": len(verified), "result": str(out / "results.json")}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-name", default="io-probes")
    args = parser.parse_args()
    audit(args.root, args.output_name)
