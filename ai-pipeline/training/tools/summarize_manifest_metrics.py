#!/usr/bin/env python3
"""Generate quick health metrics for an events manifest.

The ingestion step now emits label and technique snapshots immediately after a
manifest is produced. This script consumes a JSONL events manifest and writes a
summary JSON containing:

* `num_events`
* `num_sessions`
* `label_counts`
* `technique_counts`
* `source_set_counts`
* optional percentile statistics for velocities and openness (when present)

Example usage::

    python ai-pipeline/training/tools/summarize_manifest_metrics.py \
        --manifest ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
        --output ai-pipeline/training/reports/metrics/prod_combined_ingest_snapshot.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Optional


def float_or_none(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_manifest(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON on line {line_number} of {path}: {exc}") from exc


def summarize_manifest(path: Path) -> Dict[str, object]:
    label_counts: Counter[str] = Counter()
    technique_counts: Counter[str] = Counter()
    source_set_counts: Counter[str] = Counter()

    velocities: list[float] = []
    openness_values: list[float] = []
    sessions: set[str] = set()

    num_events = 0

    for event in load_manifest(path):
        num_events += 1
        session_id = event.get("session_id")
        if isinstance(session_id, str):
            sessions.add(session_id)

        source_set = event.get("source_set")
        if isinstance(source_set, str):
            source_set_counts[source_set] += 1

        components = event.get("components") or []
        for component in components:
            label = component.get("label")
            if isinstance(label, str):
                label_counts[label] += 1

            velocity = float_or_none(component.get("velocity"))
            if velocity is not None:
                velocities.append(velocity)

            openness = float_or_none(component.get("openness"))
            if openness is not None:
                openness_values.append(openness)

        techniques = event.get("techniques") or []
        for technique in techniques:
            if isinstance(technique, str):
                technique_counts[technique] += 1

    summary: Dict[str, object] = {
        "manifest": str(path),
        "num_events": num_events,
        "num_sessions": len(sessions),
        "label_counts": dict(label_counts),
        "technique_counts": dict(technique_counts),
        "source_set_counts": dict(source_set_counts),
    }

    if velocities:
        velocities_sorted = sorted(velocities)
        summary["velocity_stats"] = _percentiles(velocities_sorted)
    if openness_values:
        openness_sorted = sorted(openness_values)
        summary["openness_stats"] = _percentiles(openness_sorted)

    return summary


def _percentiles(values: list[float]) -> Dict[str, float]:
    def percentile(p: float) -> float:
        if not values:
            return 0.0
        if p <= 0:
            return values[0]
        if p >= 100:
            return values[-1]
        k = (len(values) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(values) - 1)
        if f == c:
            return values[f]
        return values[f] + (values[c] - values[f]) * (k - f)

    return {
        "p05": percentile(5),
        "p25": percentile(25),
        "p50": percentile(50),
        "p75": percentile(75),
        "p95": percentile(95),
        "min": values[0],
        "max": values[-1],
        "mean": sum(values) / len(values),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Events JSONL manifest to summarize",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the summary JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = args.manifest
    if not manifest.exists():
        raise SystemExit(f"Manifest not found: {manifest}")

    summary = summarize_manifest(manifest)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Wrote manifest metrics to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
