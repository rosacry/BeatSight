"""Run the surviving local models into a new, self-contained review folder.

No installation, cloud service, training dataset, or F-drive output is needed.
The faithful profile is an evaluation candidate, not a claim of accuracy.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import random
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
PIPELINE = REPO / "ai-pipeline"
ASSETS = {
    "multilabel_model_path": "runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt",
    "multilabel_thresholds_path": "runs/v5_multilabel_final_v3_continued/thresholds_demucs_calibrated.json",
    "ensemble_demucs_model_path": "runs/v5_demucs_cymbal_boost/best_multilabel_model_ema.pt",
    "ensemble_demucs_thresholds_path": "runs/v5_demucs_cymbal_boost/thresholds_named.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preflight(audio: Path, output: Path) -> dict[str, str]:
    if not audio.is_file():
        raise FileNotFoundError(f"Audio does not exist: {audio}")
    if output.exists():
        raise FileExistsError(f"Choose a new output folder; refusing to overwrite {output}")
    assets = {key: str(PIPELINE / rel) for key, rel in ASSETS.items()}
    for path in assets.values():
        if not Path(path).is_file():
            raise FileNotFoundError(f"Required model asset missing: {path}; no fallback allowed")
    if audio.suffix.lower() not in {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aiff"}:
        raise ValueError("Use a supported audio file")
    return assets


def validate_chart(chart: dict, output: Path) -> dict:
    from collections import Counter

    hits = chart["hitObjects"]
    if not hits:
        raise ValueError("No drum hits generated")
    audio_name = chart["audio"]["filename"]
    if Path(audio_name).name != audio_name or not (output / audio_name).is_file():
        raise ValueError("Chart audio must be present in its output folder")
    duration = chart["audio"]["duration"]
    times = [hit["time"] for hit in hits]
    if any(not math.isfinite(t) or t < 0 or t > duration for t in times):
        raise ValueError("Chart contains an invalid note timestamp")
    if times != sorted(times):
        raise ValueError("Chart notes are not sorted")
    components = set(chart["drumKit"]["components"])
    if any(hit["component"] not in components for hit in hits):
        raise ValueError("A note references an undeclared drum component")
    return {"hit_count": len(hits), "duration_ms": duration,
            "components": dict(Counter(hit["component"] for hit in hits)),
            "bpm": chart["timing"]["bpm"], "time_signature": chart["timing"]["timeSignature"]}


def validate_inference(result: dict, debug: dict) -> None:
    if not result.get("success") or result.get("classifier") != "multilabel":
        raise RuntimeError(f"Expected recovered ML model, got {result.get('classifier')}")
    if debug.get("generation", {}).get("used_fallback") is not False:
        raise RuntimeError("Missing transcription evidence or synthetic fallback pattern; refusing to certify chart")


def run(audio: Path, output: Path, profile: str = "faithful", device: str = "cuda") -> dict:
    audio, output = audio.resolve(), output.resolve()
    assets = preflight(audio, output)
    settings = dict(assets, pipeline_mode="transcription", isolate_drums=True,
                    ensemble_classification=True, use_ml_classifier=True,
                    use_multilabel=True, ml_device=device, start_time=0.0,
                    auto_sensitivity=True, auto_quantization=True, num_lanes=7)
    if profile == "faithful":
        settings.update(force_quantization=False, max_snap_error_ms=0.0,
                        use_structured_decoding=False, use_advanced_quantization=False,
                        use_genre_detection=False, use_pattern_repair=False,
                        use_readability_filter=False, apply_difficulty_shaping=False,
                        use_hihat_refinement=False)
    elif profile != "legacy":
        raise ValueError(f"Unknown profile: {profile}")
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "started", "profile": profile,
        "quality_status": "Unreviewed AI draft; inspect and correct before learning from it",
        "input": {"path": str(audio), "sha256": sha256(audio)},
        "models": {key: {"path": path, "sha256": sha256(Path(path))}
                   for key, path in assets.items()},
        "code_sha256": {str(path.relative_to(REPO)): sha256(path) for path in [
            Path(__file__).resolve(), PIPELINE / "pipeline/process.py",
            PIPELINE / "pipeline/auto_parameters.py", PIPELINE / "pipeline/beatmap_generator.py",
            PIPELINE / "transcription/drum_classifier.py", PIPELINE / "transcription/multilabel_inference.py",
            PIPELINE / "transcription/onset_detector.py", PIPELINE / "separation/demucs_separator.py",
        ]},
        "python": sys.executable,
        "seed": 0,
        "reproducibility": "Fixed Python/NumPy/Torch seeds; GPU bitwise determinism is not guaranteed",
        "packages": {pkg: metadata.version(pkg) for pkg in
                     ("torch", "torchaudio", "librosa", "numpy", "demucs")},
        "settings": settings,
    }
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "run.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    try:
        shutil.copy2(audio, output / audio.name)
        if sha256(output / audio.name) != manifest["input"]["sha256"]:
            raise RuntimeError("Copied audio failed integrity verification")
        sys.path.insert(0, str(PIPELINE))
        with (output / "pipeline.log").open("x", encoding="utf-8") as log:
            with redirect_stdout(log), redirect_stderr(log):
                from pipeline.process import process_audio_file
                import numpy as np
                import torch
                random.seed(0)
                np.random.seed(0)
                torch.manual_seed(0)
                result = process_audio_file(str(output / audio.name), str(output / "chart.bsm"),
                                            debug_output_path=str(output / "debug.json"), **settings)
        debug = json.loads((output / "debug.json").read_text(encoding="utf-8"))
        validate_inference(result, debug)
        chart = json.loads((output / "chart.bsm").read_text(encoding="utf-8"))
        manifest.update(status="complete", result=result, validation=validate_chart(chart, output))
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True, help="A NEW folder; existing folders are rejected")
    parser.add_argument("--profile", choices=("faithful", "legacy"), default="faithful")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        assets = preflight(args.input.resolve(), args.output_dir.resolve())
        print(json.dumps({"input": str(args.input.resolve()), "output": str(args.output_dir.resolve()),
                          "profile": args.profile, "assets": assets}, indent=2))
    else:
        result = run(args.input, args.output_dir, args.profile, args.device)
        print(json.dumps({"status": result["status"], "validation": result["validation"],
                          "output": str(args.output_dir.resolve())}, indent=2))


if __name__ == "__main__":
    main()
