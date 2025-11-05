#!/usr/bin/env python3
"""
Export BeatSight events JSONL from a CSV annotation file.

- Skips blank lines and lines starting with '#'
- Aliases raw labels (e.g., china2 -> china) per export_config.json
- Adds instance:2 for second-piece aliases (e.g., tom_floor2, china2)
- Computes dynamic_bucket from velocity thresholds
- Only attaches 'openness' / 'openness_level' for hi-hat labels
- Quantizes hi-hat openness to 3 levels: "none" | "some" | "full"
- Enforces basic invariants (ranges, negatives have no components)

CSV expected headers (semicolon- or comma-separated multi-values):
  sample_id,audio_path,onset_time,labels,velocities,openness,openness_level,
  session_id,drummer_id,kit_id,room_id,is_synthetic,bleed_level,mix_context,negative_example
"""

import argparse, csv, json, sys
from pathlib import Path

HIHAT_LABELS = {
    "hihat_closed", "hihat_open", "hihat_pedal", "hihat_foot_splash"
}

def load_cfg(p: str) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def bucket_from_velocity(v, thr: dict):
    # v in [0,1]; thr = {ghost, light, medium, accent}
    if v is None:
        return None
    if v < thr["ghost"]:
        return "ghost"
    if v < thr["light"]:
        return "light"
    if v < thr["medium"]:
        return "medium"
    return "accent"

def parse_float(x):
    try:
        return None if x is None or x == "" else float(x)
    except Exception:
        return None

def split_list(x):
    """For label-like fields: drop empty tokens."""
    if not x:
        return []
    return [t.strip() for t in x.replace(";", ",").split(",") if t.strip()]

def split_list_preserve_blanks(x):
    """For numeric/aligned fields: keep blanks to preserve alignment with labels."""
    if x is None:
        return []
    s = x.replace(";", ",")
    return [t.strip() for t in s.split(",")]  # keep "" entries

def quantize_openness_level(o, thr: dict):
    """Map numeric openness ∈[0,1] to 'none'|'some'|'full'."""
    if o is None:
        return None
    # Fallback thresholds if not in config
    none_max = float(thr.get("none_max", 0.15))
    full_min = float(thr.get("full_min", 0.85))
    if o <= none_max:
        return "none"
    if o >= full_min:
        return "full"
    return "some"

def build_components(labels, velocities, opennesses, openness_levels, cfg, strict: bool):
    """
    Build per-component dicts with:
      - canonical label (after aliasing)
      - instance (if alias indicates second piece)
      - velocity (0..1) and dynamic_bucket
      - openness/openness_level only for hi-hat labels
    """
    # Parse aligned lists
    vel_list  = [parse_float(v) for v in velocities] if velocities else []
    open_list = [parse_float(o) for o in opennesses] if opennesses else []
    lvl_list  = [lv if lv else None for lv in openness_levels] if openness_levels else []

    # Pad to len(labels) for safe indexing
    need = len(labels)
    if len(vel_list)  < need: vel_list  += [None] * (need - len(vel_list))
    if len(open_list) < need: open_list += [None] * (need - len(open_list))
    if len(lvl_list)  < need: lvl_list  += [None] * (need - len(lvl_list))

    comps = []
    thr_vel = cfg["dynamic_thresholds"]
    thr_open_lvl = cfg.get("openness_level_thresholds", {"none_max": 0.15, "full_min": 0.85})

    for i, raw_label in enumerate(labels):
        # alias to canonical label
        label = cfg["label_aliases"].get(raw_label, raw_label)
        if strict and (label not in cfg["required_labels"]):
            raise ValueError(f"Unknown label after aliasing: '{raw_label}' → '{label}'")

        comp = {"label": label}

        # if alias denotes a second physical piece, keep instance hint
        inst = cfg["alias_instances"].get(raw_label)
        if inst is not None:
            comp["instance"] = inst

        # velocity + dynamic bucket
        v = vel_list[i]
        if v is not None:
            comp["velocity"] = max(0.0, min(1.0, v))
            comp["dynamic_bucket"] = bucket_from_velocity(comp["velocity"], thr_vel)

        # openness only for hi-hat labels
        if label in HIHAT_LABELS:
            # Prefer discrete level if provided; else derive from numeric openness
            lvl = lvl_list[i]
            if lvl not in (None, ""):
                comp["openness_level"] = lvl  # expect "none"|"some"|"full"
            else:
                o = open_list[i]
                if o is not None:
                    o = max(0.0, min(1.0, o))
                    comp["openness"] = o  # keep raw if present
                    comp["openness_level"] = quantize_openness_level(o, thr_open_lvl)

        comps.append(comp)
    return comps

def main():
    ap = argparse.ArgumentParser(description="Export BeatSight events JSONL from CSV annotations.")
    ap.add_argument("--csv", required=True, help="Input CSV annotations")
    ap.add_argument("--out", required=True, help="Output JSONL file")
    ap.add_argument("--audio-root", default="", help="Prefix to prepend to audio_path if CSV has relative paths")
    ap.add_argument("--config", required=True, help="export_config.json")
    ap.add_argument("--strict", action="store_true", help="Fail on unknown labels after aliasing")
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    audio_root = Path(args.audio_root)

    # CSV schema (header names):
    # sample_id,audio_path,onset_time,labels,velocities,openness,openness_level,
    # session_id,drummer_id,kit_id,room_id,is_synthetic,bleed_level,mix_context,negative_example
    required_cols = ["sample_id", "audio_path", "onset_time", "labels"]

    with open(args.csv, newline="") as f_in, open(args.out, "w", encoding="utf-8") as f_out:
        # Skip blank lines and comment lines starting with '#'
        lines = (ln for ln in f_in if ln.strip() and not ln.lstrip().startswith("#"))
        reader = csv.DictReader(lines)

        missing = [c for c in required_cols if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"CSV missing columns: {missing}")

        for row in reader:
            sample_id = (row.get("sample_id") or "").strip()
            audio_rel = (row.get("audio_path") or "").strip()
            if not sample_id or not audio_rel:
                # Be forgiving: skip rows that don't have essential fields
                sys.stderr.write(f"skip row (missing sample_id/audio_path): {row}\n")
                continue

            audio_path = str((audio_root / audio_rel).as_posix()) if args.audio_root else audio_rel

            onset = parse_float(row.get("onset_time"))
            if onset is None:
                raise ValueError(f"{sample_id}: onset_time missing/invalid")

            labels        = split_list(row.get("labels"))
            velocities    = split_list_preserve_blanks(row.get("velocities"))
            opennesses    = split_list_preserve_blanks(row.get("openness"))
            open_levels   = split_list_preserve_blanks(row.get("openness_level"))

            negative = str(row.get("negative_example", "")).lower() in ("1", "true", "yes", "y")

            is_syn = row.get("is_synthetic")
            if is_syn in (None, ""):
                is_syn = cfg["defaults"].get("is_synthetic", False)
            else:
                is_syn = str(is_syn).lower() in ("1", "true", "yes", "y")

            # negatives have no components
            if negative and labels:
                labels, velocities, opennesses, open_levels = [], [], [], []

            comps = build_components(labels, velocities, opennesses, open_levels, cfg, strict=args.strict)

            obj = {
                "sample_id": sample_id,
                "session_id": row.get("session_id") or "sess_unknown",
                "drummer_id": row.get("drummer_id") or "d_unknown",
                "kit_id": row.get("kit_id") or "k_unknown",
                "room_id": row.get("room_id") or "r_unknown",
                "source_set": cfg["defaults"].get("source_set", "BeatSight"),
                "is_synthetic": is_syn,
                "audio_path": audio_path,
                "onset_time": onset,
                "components": comps,
                "bleed_level": row.get("bleed_level") or cfg["defaults"].get("bleed_level", "med"),
                "mix_context": row.get("mix_context") or cfg["defaults"].get("mix_context", "full_mix"),
                "negative_example": negative
                # (optional) add 'loudness' later when available
            }

            # Basic invariants
            if negative and obj["components"]:
                raise ValueError(f"{sample_id}: negative_example true but components non-empty")
            if any(c.get("velocity", 0) < 0 or c.get("velocity", 0) > 1 for c in obj["components"]):
                raise ValueError(f"{sample_id}: velocity out of [0,1]")
            if any(
                c.get("openness", 0) < 0 or c.get("openness", 0) > 1
                for c in obj["components"] if "openness" in c
            ):
                raise ValueError(f"{sample_id}: openness out of [0,1]")

            f_out.write(json.dumps(obj, separators=(",", ":")) + "\n")

if __name__ == "__main__":
    main()
