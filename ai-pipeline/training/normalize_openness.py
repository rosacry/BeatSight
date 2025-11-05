"""Normalize hi-hat openness values using vendor-specific CC4 curves.

Reads BeatSight event JSONL files, maps `openness_raw` (0-127) to `openness`
values in [0,1], and annotates each component with the curve metadata used.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


HAT_LABELS = {"hihat_closed", "hihat_open", "hihat_pedal", "hihat_foot_splash"}


@dataclass
class Curve:
    curve_id: str
    breakpoints: List[Tuple[int, float]]
    offset: float

    def map_value(self, raw: float) -> float:
        raw_val = float(raw)
        clamped = max(min(raw_val, 127.0), 0.0)
        points = self.breakpoints
        for idx in range(len(points) - 1):
            left_raw, left_norm = points[idx]
            right_raw, right_norm = points[idx + 1]
            if clamped <= right_raw:
                if right_raw == left_raw:
                    return max(min(left_norm + self.offset, 1.0), 0.0)
                ratio = (clamped - left_raw) / (right_raw - left_raw)
                value = left_norm + ratio * (right_norm - left_norm)
                return max(min(value + self.offset, 1.0), 0.0)
        # Beyond last breakpoint
        return max(min(points[-1][1] + self.offset, 1.0), 0.0)


class OpennessNormalizer:
    def __init__(self, curves: Dict[Tuple[str, str], Curve]) -> None:
        self.curves = curves

    @classmethod
    def from_file(cls, path: Path) -> "OpennessNormalizer":
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        curves: Dict[Tuple[str, str], Curve] = {}
        vendors = payload.get("vendors", {})
        for vendor, models in vendors.items():
            for model, data in models.items():
                breakpoints = [(int(bp["raw"]), float(bp["normalized"])) for bp in data["breakpoints"]]
                breakpoints.sort(key=lambda item: item[0])
                curve = Curve(
                    curve_id=data.get("curve_id", f"{vendor}_{model}"),
                    breakpoints=breakpoints,
                    offset=float(data.get("offset", 0.0)),
                )
                key = (vendor.lower(), model.lower())
                curves[key] = curve
        return cls(curves)

    def normalize_event(self, event: Dict) -> Tuple[Dict, bool]:
        updated = False
        vendor = (event.get("device_vendor") or event.get("vendor") or "").lower()
        model = (event.get("device_model") or event.get("model") or "").lower()
        curve = self.curves.get((vendor, model)) if vendor and model else None

        components = event.get("components", [])
        for component in components:
            label = component.get("label")
            if label not in HAT_LABELS:
                continue
            openness_raw = component.get("openness_raw")
            if openness_raw is None:
                continue
            curve_override = component.get("openness_curve_id")
            selected_curve = curve
            if curve_override:
                selected_curve = self._get_curve_by_id(curve_override)
            if selected_curve is None:
                continue
            component["openness"] = selected_curve.map_value(float(openness_raw))
            component["openness_curve_id"] = selected_curve.curve_id
            component["openness_calibrated"] = True
            updated = True
        return event, updated

    def _get_curve_by_id(self, curve_id: str) -> Optional[Curve]:
        target = curve_id.lower()
        for curve in self.curves.values():
            if curve.curve_id.lower() == target:
                return curve
        return None


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize hi-hat openness values")
    parser.add_argument("--events", required=True, help="Input events JSONL file")
    parser.add_argument("--output", required=True, help="Output JSONL file with normalized openness")
    parser.add_argument("--curves", default=str(Path(__file__).with_name("calibration") / "openness_curves.json"), help="Path to openness curves JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing output")
    return parser.parse_args(argv)


def load_events(path: Path) -> List[Dict]:
    events: List[Dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            events.append(json.loads(line))
    if not events:
        raise ValueError(f"No events found in {path}")
    return events


def write_events(path: Path, events: Iterable[Dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")))
            handle.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    try:
        normalizer = OpennessNormalizer.from_file(Path(args.curves))
        events = load_events(Path(args.events))
    except Exception as exc:
        print(f"[normalize_openness] Failed to load input: {exc}", file=sys.stderr)
        return 2

    total = 0
    updated = 0
    unknown_devices = 0

    processed: List[Dict] = []
    for event in events:
        total += 1
        event_vendor = event.get("device_vendor") or event.get("vendor")
        event_model = event.get("device_model") or event.get("model")
        before = json.dumps(event, sort_keys=True)
        new_event, changed = normalizer.normalize_event(event)
        processed.append(new_event)
        if changed:
            updated += 1
        elif any(component.get("label") in HAT_LABELS and component.get("openness_raw") is not None for component in event.get("components", [])):
            unknown_devices += 1

    print(f"Processed {total} events. Updated {updated} events with calibrated openness.")
    if unknown_devices:
        print(f"Warning: {unknown_devices} events contained hi-hat openness but no matching device curve.")

    if args.dry_run:
        return 0

    try:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_events(output_path, processed)
    except Exception as exc:
        print(f"[normalize_openness] Failed to write output: {exc}", file=sys.stderr)
        return 3

    print(f"Normalized events written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
