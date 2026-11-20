"""Prepare a bounded, locally preserved chart-reference batch using YARG.Core.

No chart/audio is edited. All derived files go into a new root/prepared folder.
The raw Pro Drums lanes remain authoritative; five-family labels are explicitly
lane-convention proxies, not verified acoustic instruments or articulations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import configparser
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import soundfile as sf

from transcribe import sha256
from transcribe_reference import write_json

PAD_FAMILY = {"Kick": "KD", "RedDrum": "SD", "YellowDrum": "TT",
              "BlueDrum": "TT", "GreenDrum": "TT", "YellowCymbal": "HH",
              "BlueCymbal": "CY", "GreenCymbal": "CY"}
STEMS = {"song", "guitar", "rhythm", "bass", "keys", "vocals", "vocals_1",
         "vocals_2", "drums", "drums_1", "drums_2", "drums_3", "drums_4"}


def chart_offset(path):
    if path.suffix.lower() != ".chart":
        return 0.0
    text = path.read_text(encoding="utf-8-sig")
    block = re.search(r"\[Song\]\s*\{(.*?)\}", text, flags=re.S)
    if not block:
        raise ValueError("Missing chart Song metadata")
    offset = re.search(r"^\s*Offset\s*=\s*([^\r\n]+)", block[1], flags=re.M)
    value = float(offset[1]) if offset else 0.0
    if not np.isfinite(value):
        raise ValueError("Invalid chart offset")
    return value


def convert_events(parsed, delay_ms=0.0, offset_seconds=0.0):
    if not np.isfinite([delay_ms, offset_seconds]).all():
        raise ValueError("Nonfinite offset")
    # Override precedence varies by game; don't silently invent a combined shift.
    if delay_ms and offset_seconds:
        raise ValueError("Nonzero ini delay AND chart offset require explicit review")
    candidates = [t for t in parsed["tracks"] if t["difficulty"] == "ExpertPlus"]
    if not candidates:
        candidates = [t for t in parsed["tracks"] if t["difficulty"] == "Expert"]
    if len(candidates) != 1:
        raise ValueError("Missing or ambiguous Expert drum track")
    events = []
    for note in candidates[0]["notes"]:
        t = note["time_seconds"] + delay_ms / 1000 + offset_seconds
        if not np.isfinite(t) or t < 0:
            raise ValueError("Invalid event timestamp")
        if note["pad"] not in PAD_FAMILY:
            raise ValueError(f"Unsupported pad: {note['pad']}")
        events.append({**note, "time_seconds": t, "family_proxy": PAD_FAMILY[note["pad"]]})
    if not events:
        raise ValueError("Empty drum reference")
    return sorted(events, key=lambda n: (n["time_seconds"], n["pad"]))


def family_reference(events, merge_cymbals=False):
    """Event-presence target: collapse simultaneous same-family chart lanes.

    Raw lane multiplicity is retained in reference.json, separately counted.
    Broad-family model peaks cannot encode two distinct cymbals at the same time.
    """
    result = defaultdict(set)
    for event in events:
        family = event["family_proxy"]
        if merge_cymbals and family in {"HH", "CY"}:
            family = "CY"
        result[family].add(event["time_seconds"])
    return {f: sorted(ts) for f, ts in result.items()}


def package_audio(folder, output):
    paths = sorted(p for p in folder.iterdir() if p.stem.lower() in STEMS
                   and p.suffix.lower() in {".ogg", ".wav", ".mp3", ".flac"})
    if not paths or len({p.stem.lower() for p in paths}) != len(paths):
        raise ValueError("Missing or ambiguous package audio")
    arrays, manifest, sample_rate = [], [], None
    for p in paths:
        a, sr = sf.read(p, dtype="float32", always_2d=True)
        if not np.isfinite(a).all() or not len(a) or a.shape[1] not in {1, 2}:
            raise ValueError("Invalid package audio")
        if sample_rate is not None and sr != sample_rate:
            raise ValueError("Different stem sample rates require explicit review")
        sample_rate = sr
        arrays.append(np.repeat(a, 2, axis=1) if a.shape[1] == 1 else a)
        manifest.append({"name": p.name, "sha256": sha256(p), "frames": len(a), "channels": a.shape[1]})
    frames = max(map(len, arrays))
    mix = np.zeros((frames, 2), dtype=np.float32)
    for a in arrays:
        mix[:len(a)] += a
    peak = float(np.abs(mix).max())
    if peak == 0:
        raise ValueError("Silent mix")
    gain = 1 / max(1, peak)
    mix *= gain
    sf.write(output, mix, sample_rate, subtype="FLOAT")
    return {"sources": manifest, "sample_rate": sample_rate, "frames": frames,
            "duration_seconds": frames / sample_rate, "sum_peak": peak,
            "linear_gain": gain, "sha256": sha256(output),
            "pcm_sha256": __import__('hashlib').sha256(mix.tobytes()).hexdigest(),
            "method": "sum package stems at time zero, zero-pad tails, common gain only; no time shift"}


def prepare(root, exporter, selection_name="selection.json", output_name="prepared"):
    root, exporter = root.resolve(), exporter.resolve()
    if root.drive.upper() != "C:":
        raise ValueError("C: experiment root required")
    if Path(selection_name).name != selection_name or Path(output_name).name != output_name:
        raise ValueError("Selection and output must be simple names within experiment")
    selection = json.loads((root / selection_name).read_text())
    out = root / output_name
    out.mkdir(exist_ok=False)
    report = {"selection_sha256": sha256(root / selection_name),
              "exporter_sha256": sha256(exporter), "status": "started", "songs": []}
    for selected in selection["songs"]:
        chart = (root / selected["chart"]).resolve()
        if not chart.is_relative_to(root / "songs") or sha256(chart) != selected["chart_sha256"]:
            raise ValueError("Selected chart changed or outside song root")
        ini_path = chart.parent / "song.ini"
        ini = configparser.ConfigParser(interpolation=None, strict=False)
        ini.read(ini_path, encoding="utf-8-sig")
        meta = dict(ini["song"])
        if meta.get("five_lane_drums", "false").lower() in {"true", "1"}:
            raise ValueError("Five-lane charts are outside this batch")
        if chart.suffix == ".chart":
            drum_blocks = re.findall(r"\[\w*Drums\]\s*\{(.*?)\}", chart.read_text(encoding="utf-8-sig"), re.S)
            if any(re.search(r"=\s*N\s+5\s", block) for block in drum_blocks):
                raise ValueError("Possible five-lane drum chart; review before importing")
        dest = out / selected["id"]
        dest.mkdir()
        proc = subprocess.run(["dotnet", str(exporter), str(chart)], capture_output=True, text=True, check=True)
        (dest / "parser.stderr.log").write_text(proc.stderr, encoding="utf-8")
        parsed = json.loads(proc.stdout)
        write_json(dest / "parser.json", parsed)
        delay, offset = float(meta.get("delay", 0)), chart_offset(chart)
        events = convert_events(parsed, delay, offset)
        audio = package_audio(chart.parent, dest / "mix.wav")
        if events[-1]["time_seconds"] > audio["duration_seconds"]:
            raise ValueError("Chart extends beyond decoded audio")
        ref = {"metadata": meta, "chart": str(chart), "chart_sha256": sha256(chart),
               "ini_sha256": sha256(ini_path), "delay_ms": delay, "chart_offset_seconds": offset,
               "timing_shift_applied_seconds": delay / 1000 + offset,
               "events": events, "tempos": parsed["tempos"], "time_signatures": parsed["time_signatures"],
               "sections": parsed["sections"], "audio": audio,
               "limitations": ["Chart agreement only; audio audit pending", "Yellow cymbal = HH is a convention, not verified identity",
                               "ExpertPlus includes optional 2x kicks; chart omissions remain unknown",
                               "Training overlap unknown; reserved here does not mean unseen in pretraining"]}
        write_json(dest / "reference.json", ref)
        row = {"id": selected["id"], "split": selected["split"], "audio": audio,
               "raw_notes": len(events), "unique_family_events": sum(map(len, family_reference(events).values())),
               "double_kicks": sum(e["double_kick"] for e in events),
               "pad_counts": dict(Counter(e["pad"] for e in events)),
               "first_note_seconds": events[0]["time_seconds"], "last_note_seconds": events[-1]["time_seconds"],
               "reference_sha256": sha256(dest / "reference.json")}
        report["songs"].append(row)
        write_json(out / "manifest.json", report)
        print(json.dumps({k: v for k, v in row.items() if k != "audio"}), flush=True)
    report["status"] = "complete"
    write_json(out / "manifest.json", report)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--exporter", type=Path, required=True)
    ap.add_argument("--selection", default="selection.json")
    ap.add_argument("--output-name", default="prepared")
    args = ap.parse_args()
    prepare(args.root, args.exporter, args.selection, args.output_name)
