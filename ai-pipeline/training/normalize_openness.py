"""Normalize hi-hat openness values using vendor-specific CC4 curves.

Reads BeatSight event JSONL files, maps ``openness_raw`` (0-127) to ``openness``
values in [0, 1], and annotates each component with the curve metadata used.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from training.event_loader import ManifestEventLoader


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
    parser.add_argument(
        "--curves",
        default=str(Path(__file__).with_name("calibration") / "openness_curves.json"),
        help="Path to openness curves JSON",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing output")
    return parser.parse_args(argv)


def normalize_manifest(
    normalizer: OpennessNormalizer,
    loader: ManifestEventLoader,
    writer: Optional[TextIO],
) -> Tuple[int, int, int]:
    total = 0
    updated = 0
    unknown_devices = 0

    for record in loader:
        event = record.event
        total += 1
        components = event.get("components") or []
        has_hat_openness = any(
            component.get("label") in HAT_LABELS and component.get("openness_raw") is not None
            for component in components
        )

        _, changed = normalizer.normalize_event(event)
        if changed:
            updated += 1
        elif has_hat_openness:
            unknown_devices += 1

        if writer is not None:
            writer.write(json.dumps(event, separators=(",", ":")))
            writer.write("\n")

    return total, updated, unknown_devices


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    try:
        normalizer = OpennessNormalizer.from_file(Path(args.curves))
        loader = ManifestEventLoader(Path(args.events))
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"[normalize_openness] Failed to load input: {exc}", file=sys.stderr)
        return 2

    writer: Optional[TextIO] = None
    output_path = Path(args.output)
    if not args.dry_run:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            writer = output_path.open("w", encoding="utf-8")
        except Exception as exc:  # pragma: no cover - CLI guardrail
            print(f"[normalize_openness] Failed to prepare output: {exc}", file=sys.stderr)
            return 3

    try:
        total, updated, unknown_devices = normalize_manifest(normalizer, loader, writer)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass
            try:
                output_path.unlink(missing_ok=True)
            except Exception:
                pass
        print(f"[normalize_openness] Failed to process events: {exc}", file=sys.stderr)
        return 2
    else:
        if writer is not None:
            writer.close()

    print(f"Processed {total} events. Updated {updated} events with calibrated openness.")
    if unknown_devices:
        print(
            f"Warning: {unknown_devices} events contained hi-hat openness but no matching device curve."
        )

    if args.dry_run:
        return 0

    print(f"Normalized events written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
