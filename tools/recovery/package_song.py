"""Package a verified reference run as an explicitly unreviewed practice draft."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid

from transcribe import REPO, sha256, validate_chart
from transcribe_reference import NATIVE_ALIASES


def verify_exported_notes(chart, predictions):
    """Reject modified notes even when a stereo run has no recorded chart hash."""
    expected = [{"time": round(e["time"]), "component": NATIVE_ALIASES[e["component"]],
                 "velocity": 0.8} for e in predictions["hitObjects"]]
    if chart["hitObjects"] != expected:
        raise ValueError("Chart notes differ from the hash-verified reference predictions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--bookmarks", nargs="*", type=float, default=[])
    parser.add_argument("--stereo", action="store_true", help="Package the separate stereo probe without replacing earlier drafts")
    parser.add_argument("--pcm-wav", action="store_true", help="Decode PCM16 FLAC losslessly for native playback compatibility")
    args = parser.parse_args()
    root = args.root.resolve()
    if root.drive.upper() != "C:":
        raise ValueError("Recovery output must be on C:")
    run = json.loads((root / "reference-comparison/run.json").read_text())
    if run["status"] != "complete":
        raise ValueError("Reference comparison did not complete")
    source = root / ("stereo-probe" if args.stereo else "reference-comparison/separated") / "chart.bsm"
    stem_source = root / ("stereo-probe" if args.stereo else "reference-comparison") / "drums.wav"
    stem_hash = run["separation"]["sha256"]
    if args.stereo:
        stereo = json.loads((root / "stereo-probe/run.json").read_text())
        if stereo["status"] != "complete" or stereo["input_sha256"] != run["input"]["sha256"]:
            raise ValueError("Stereo probe incomplete or used a different input")
        stem_hash = stereo["stem_sha256"]
        if sha256(root / "stereo-probe/predictions.json") != stereo["prediction_sha256"]:
            raise ValueError("Stereo predictions changed")
    elif sha256(source) != run["arms"]["separated"]["chart_sha256"]:
        raise ValueError("Reference chart changed after inference")
    chart = json.loads(source.read_text())
    if args.stereo:
        verify_exported_notes(chart, json.loads((root / "stereo-probe/predictions.json").read_text()))
    out = root / ("practice-stereo-draft" if args.stereo else "practice-draft")
    out.mkdir(exist_ok=False)
    original_notes = chart["hitObjects"]
    chart["metadata"]["title"] += " [DRAFT]"
    chart["metadata"]["beatmapId"] = str(uuid.uuid4())
    chart["metadata"]["modifiedAt"] = datetime.now(timezone.utc).isoformat()
    chart["editor"]["bookmarks"] = sorted(set(round(t * 1000) for t in args.bookmarks
                                                 if 0 <= t * 1000 <= chart["audio"]["duration"]))
    copies = [(source.parent / chart["audio"]["filename"], out / chart["audio"]["filename"], run["input"]["sha256"]),
              (stem_source, out / "drums.wav", stem_hash)]
    for src, dst, expected in copies:
        if sha256(src) != expected:
            raise ValueError(f"Changed input: {src}")
        shutil.copy2(src, dst)
        if sha256(dst) != expected:
            raise ValueError(f"Copy mismatch: {dst}")
    audio_conversion = None
    if args.pcm_wav:
        import soundfile as sf
        import numpy as np
        original = out / chart["audio"]["filename"]
        if original.suffix.lower() != ".flac" or sf.info(original).subtype != "PCM_16":
            raise ValueError("Lossless compatibility conversion currently requires PCM16 FLAC")
        samples, sr = sf.read(original, dtype="int16", always_2d=True)
        wav = out / "full-mix.wav"
        sf.write(wav, samples, sr, subtype="PCM_16")
        decoded, decoded_sr = sf.read(wav, dtype="int16", always_2d=True)
        if sr != decoded_sr or not np.array_equal(samples, decoded):
            raise ValueError("Compatibility WAV changed decoded PCM")
        chart["audio"].update(filename=wav.name, hash="sha256:" + sha256(wav))
        audio_conversion = {"original": original.name, "derived": wav.name, "pcm_samples_equal": True,
                            "frames": len(samples), "sample_rate": sr, "sha256": sha256(wav)}
    chart["audio"].update(drumStem="drums.wav", drumStemHash="sha256:" + stem_hash)
    import jsonschema
    jsonschema.validate(chart, json.loads((REPO / "shared/schemas/beatmap_schema.json").read_text()))
    validation = validate_chart(chart, out)
    assert chart["hitObjects"] == original_notes
    chart_path = out / "chart.bsm"
    chart_path.write_text(json.dumps(chart, indent=2), encoding="utf-8")
    (out / "READ-ME.txt").write_text(
        "Import chart.bsm into BeatSight with the adjacent audio files present.\n\n"
        "This is an unreviewed, full-song practice DRAFT using separated-input ADTOF.\n"
        + ("Stereo information was retained for this experimental draft. Earlier drafts remain preserved.\n" if args.stereo else "") +
        "No note-level ground truth was supplied; precision/recall and true timing error are unknown.\n"
        "hihat_closed means unspecified hi-hat; tom_mid means unspecified tom; crash means\n"
        "unspecified cymbal. These are native display aliases, NOT confirmed articulations.\n"
        "Velocity 0.8 is constant, not measured dynamics. Notes are unquantized.\n"
        "Tempo/meter are provisional; the beat grid is hidden. The estimated drum stem\n"
        "is included for the native mixer, but may contain separation artifacts.\n\n"
        "See ../review-v2/review.html (or ../review/review.html for earlier runs)\n"
        "for synchronized comparison with the full-mix and\n"
        "inherited drafts; see the repository song report for known uncertainties.\n",
        encoding="utf-8")
    manifest = {"source_chart": str(source), "source_chart_sha256": sha256(source),
                "chart_sha256": sha256(chart_path), "validation": validation,
                "notes_equal_to_reference_export": original_notes == json.loads(source.read_text())["hitObjects"],
                "copies": [{"path": str(dst), "sha256": sha256(dst)} for _, dst, _ in copies],
                "audio_conversion": audio_conversion, "stereo_probe": args.stereo,
                "quality_status": "unreviewed", "precision": None, "recall": None,
                "packager_sha256": sha256(Path(__file__).resolve())}
    (out / "package.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest["validation"]))


if __name__ == "__main__":
    main()
