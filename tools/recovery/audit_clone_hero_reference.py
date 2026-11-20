"""Audit chart clocks and audio attacks without opening model predictions.

Writes a new C: experiment only. Attack peaks are acoustic timing evidence, not
instrument/completeness annotations. Original chart files are never changed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import correlate, correlation_lags
import soundfile as sf

from transcribe import sha256
from transcribe_reference import write_json

LAGS = np.arange(-100, 101, dtype=float) / 1000
METHOD = {
    "signal": "Original package mix; no model or estimated drum stem input",
    "envelope": "Stereo mean-square RMS in nonoverlapping ~1 ms blocks; positive first difference timestamped at block boundary",
    "profile": "Interpolate each snare attack curve on -100..100 ms / 1 ms grid, normalize by its own maximum, mean across anchors, Gaussian smooth sigma=1.5 grid samples",
    "windows": "Fixed 12 s beginning/middle/end windows from original chart extent, same as earlier flux screen",
    "shift_selection": "Beginning-window profile peak rounded to nearest 5 ms; middle/end are independent timing validation, not shift selection",
    "screen_gate": "At least 5 snares/window; each window peak within 10 ms of selected shift; at least 60% individual strongest attacks within 10 ms of window peak",
    "scope": "Diagnostic candidate only; no automatic reference admission or note relabeling",
    "uncertainty": "Attack-energy rise is not exact perceptual onset. Synthetic calibration illustrates estimator bias only; complex mixes can mask drums.",
}


def attack_envelope(y, sr):
    if y.ndim == 1:
        y = y[:, None]
    block = max(1, round(sr / 1000))
    frames = len(y) // block
    energy = np.square(y[:frames * block].astype(np.float64)).reshape(frames, block, y.shape[1]).mean(axis=(1, 2))
    rms = np.sqrt(energy)
    return np.arange(1, frames) * block / sr, np.maximum(np.diff(rms), 0)


def attack_profile(times, values, hits):
    profiles = np.asarray([np.interp(t + LAGS, times, values) for t in hits])
    peaks = np.max(profiles, axis=1)
    active = peaks > 1e-12
    normalized = profiles[active] / peaks[active, None]
    if not len(normalized):
        raise ValueError("No audible energy rise near anchors")
    profile = gaussian_filter1d(normalized.mean(axis=0), 1.5)
    peak = float(LAGS[np.argmax(profile)] * 1000)
    individual = LAGS[np.argmax(normalized, axis=1)] * 1000
    return {"notes": len(hits), "audible_energy_windows": int(active.sum()),
            "peak_lag_ms": peak, "individual_peak_lags_ms": individual.tolist(),
            "individual_support_within_10_ms": float(np.mean(np.abs(individual - peak) <= 10)),
            "profile": profile.tolist()}


def calibration():
    rows = []
    for sr in [44100, 48000]:
        for rise_ms in [0, 2, 5, 10]:
            rng = np.random.default_rng(0)
            y = rng.normal(0, 0.001, 2 * sr)
            n = np.arange(sr)
            ramp = np.minimum(n / max(1, sr * rise_ms / 1000), 1) if rise_ms else np.ones(sr)
            y[sr:] += rng.normal(0, 1, sr) * ramp * np.exp(-n / (sr * .03))
            t, a = attack_envelope(y, sr)
            row = attack_profile(t, a, [1.0])
            rows.append({"sample_rate": sr, "rise_ms": rise_ms,
                         "known_start_seconds": 1, "peak_error_ms": row["peak_lag_ms"]})
    return rows


def independent_chart_clock(chart, events, shift):
    if chart.suffix.lower() != ".chart":
        return {"status": "not applicable; MIDI baseline retained"}
    source = chart.read_text(encoding="utf-8-sig")
    resolution = int(re.search(r"\bResolution\s*=\s*(\d+)", source)[1])
    sync = re.search(r"\[SyncTrack\]\s*\{(.*?)\}", source, re.S)[1]
    if re.search(r"=\s*A\s", sync):
        raise ValueError("Anchor events require separate clock audit")
    tempos = sorted((int(t), int(b)) for t, b in re.findall(r"(\d+)\s*=\s*B\s+(\d+)", sync))
    if not tempos or tempos[0][0] != 0 or any(b <= 0 for _, b in tempos):
        raise ValueError("Missing/invalid starting tempo")
    errors = []
    for event in events:
        tick, seconds = event["tick"], shift
        for index, (start, bpm1000) in enumerate(tempos):
            end = min(tick, tempos[index + 1][0]) if index + 1 < len(tempos) else tick
            if start >= tick:
                break
            seconds += (end - start) * 60000 / (bpm1000 * resolution)
        errors.append(abs(seconds - event["time_seconds"]))
    return {"status": "pass" if max(errors) < 1e-8 else "FAIL",
            "events_checked": len(errors), "resolution": resolution,
            "tempo_events": tempos, "maximum_absolute_error_ms": max(errors) * 1000,
            "method": "Direct integration of raw SyncTrack BPM events, independent of YARG time conversion"}


def decoder_check(source, expected, ffmpeg):
    if sha256(source) != expected["sha256"]:
        raise ValueError("Original package audio changed")
    original, sr = sf.read(source, dtype="float32", always_2d=True)
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(source), "-map", "0:a:0",
                              "-f", "f32le", "-acodec", "pcm_f32le", "-"],
                             capture_output=True, check=True)
    other = np.frombuffer(decoded.stdout, dtype="<f4").reshape(-1, original.shape[1])
    size = min(len(original), len(other))
    # Compare actual PCM; no resampling, alignment or gain is applied to either decode.
    diff = original[:size] - other[:size]
    windows = []
    for fraction in [.1, .5, .9]:
        start = int((size - 2 * sr) * fraction)
        a, b = original[start:start + 2 * sr, 0], other[start:start + 2 * sr, 0]
        windows.append({"start_seconds": start / sr, **compare_decoder_window(a, b, sr)})
    return {"source": str(source), "source_sha256": expected["sha256"], "sample_rate": sr,
            "soundfile_frames": len(original), "ffmpeg_frames": len(other),
            "max_absolute_pcm_difference": float(np.max(np.abs(diff))),
            "rms_pcm_difference": float(np.sqrt(np.mean(np.square(diff, dtype=np.float64)))),
            "windows": windows}


def compare_decoder_window(a, b, sr):
    norm = float(np.linalg.norm(a) * np.linalg.norm(b))
    if norm <= 1e-12:
        return {"status": "silent; lag unmeasurable", "best_lag_samples": None,
                "zero_lag_correlation": None}
    corr = correlate(b, a, mode="full", method="fft")
    lags = correlation_lags(len(b), len(a))
    mask = np.abs(lags) <= round(sr * .1)
    best = int(lags[mask][np.argmax(corr[mask])])
    return {"status": "measured", "best_lag_samples": best,
            "zero_lag_correlation": float(np.clip(np.dot(a, b) / norm, -1, 1))}


def audit(benchmark, out):
    benchmark, out = benchmark.resolve(), out.resolve()
    if out.drive.upper() != "C:" or out == Path(out.anchor) or out.is_relative_to(benchmark):
        raise ValueError("Use a new scoped C: root outside the existing experiment")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("ffmpeg required for independent decoder check")
    prepared = benchmark / "prepared-v2"
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["status"] != "complete":
        raise ValueError("Incomplete source preparation")
    out.mkdir(exist_ok=False)
    (out / "evidence").mkdir()
    # Freeze protocol and implementation before reading song audio or predictions.
    write_json(out / "protocol.json", {"created_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": str(benchmark), "prepared_manifest_sha256": sha256(manifest_path),
        "method": METHOD, "model_predictions_used": False,
        "code_sha256": sha256(Path(__file__)), "ffmpeg": ffmpeg,
        "ffmpeg_version": subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, check=True).stdout.splitlines()[0],
        "soundfile_version": sf.__version__, "libsndfile_version": sf.__libsndfile_version__})
    shutil.copy2(Path(__file__), out / "evidence" / Path(__file__).name)
    shutil.copy2(manifest_path, out / "evidence/prepared-manifest.json")
    result = {"method": METHOD, "calibration": calibration(), "songs": []}
    print(json.dumps({"calibration": result["calibration"]}), flush=True)
    for src in manifest["songs"]:
        slug = src["id"]
        ref_path, audio = prepared / slug / "reference.json", prepared / slug / "mix.wav"
        if sha256(ref_path) != src["reference_sha256"] or sha256(audio) != src["audio"]["sha256"]:
            raise ValueError("Prepared source changed")
        ref = json.loads(ref_path.read_text())
        chart = Path(ref["chart"])
        if sha256(chart) != ref["chart_sha256"]:
            raise ValueError("Original chart changed")
        decoders = [decoder_check(chart.parent / s["name"], s, ffmpeg) for s in src["audio"]["sources"]]
        clock = independent_chart_clock(chart, ref["events"], ref["timing_shift_applied_seconds"])
        y, sr = sf.read(audio, dtype="float32", always_2d=True)
        times, attacks = attack_envelope(y, sr)
        first, last = src["first_note_seconds"], src["last_note_seconds"]
        starts = [max(0, first - 1), max(0, (first + last) / 2 - 6), max(0, last - 12)]
        rows = []
        fig, axes = plt.subplots(3, 2, figsize=(13, 9), constrained_layout=True)
        for name, start, axis in zip(["beginning", "middle", "end"], starts, axes):
            hits = sorted(set(e["time_seconds"] for e in ref["events"] if e["family_proxy"] == "SD" and start <= e["time_seconds"] < start + 12))
            evidence = attack_profile(times, attacks, hits)
            row = {"name": name, "start_seconds": start, "end_seconds": start + 12,
                   "anchor_times_seconds": hits, **evidence}
            rows.append(row)
            axis[0].plot(LAGS * 1000, evidence["profile"])
            axis[0].axvline(0, color="red", label="original chart")
            axis[0].axvline(evidence["peak_lag_ms"], color="green", label="attack-profile peak")
            axis[0].set(title=f"{name}: {len(hits)} chart snares", xlabel="lag from original chart (ms)")
            axis[0].legend()
            axis[1].hist(evidence["individual_peak_lags_ms"], bins=np.arange(-102.5, 105, 5))
            axis[1].set(title="Individual strongest energy rises", xlabel="lag (ms)", ylabel="anchor count")
        fig.suptitle(f"{slug}: original mix, no model events")
        fig.savefig(out / f"{slug}-attacks.png", dpi=140)
        plt.close(fig)
        selected = float(5 * round(rows[0]["peak_lag_ms"] / 5))
        passes = all(w["notes"] >= 5 and abs(w["peak_lag_ms"] - selected) <= 10
                     and w["individual_support_within_10_ms"] >= .6 for w in rows)
        row = {"id": slug, "split": src["split"], "reference_sha256": sha256(ref_path),
               "audio_sha256": sha256(audio), "independent_chart_clock": clock,
               "decoder_checks": decoders, "windows": rows,
               "beginning_selected_candidate_shift_ms": selected,
               "timing_screen_pass": passes,
               "status": "acoustic diagnostic only; reference admission and instrument/completeness audit pending"}
        result["songs"].append(row)
        write_json(out / "audit.json", result)
        print(json.dumps({"id": slug, "clock": clock, "decoders": decoders,
                          "shift_candidate_ms": selected, "timing_screen_pass": passes,
                          "windows": [{k: w[k] for k in ["name", "notes", "peak_lag_ms", "individual_support_within_10_ms"]} for w in rows]}), flush=True)
    write_json(out / "audit.json", result)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--benchmark", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    audit(args.benchmark, args.output_dir)
