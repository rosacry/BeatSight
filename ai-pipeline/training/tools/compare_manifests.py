#!/usr/bin/env python3
"""Compare two BeatSight event manifests and summarize distribution changes.

The report focuses on high-level counts that typically shift after a reingest:

* Total event count and unique session tally
* Per-session event totals
* Per-component (label) counts derived from ``components[].label``
* Technique coverage counts via :class:`training.event_loader.ManifestEventLoader`

Use this to sanity-check that a refreshed manifest still covers the expected
sessions, labels, and techniques before pushing it into the training pipeline.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from training.event_loader import ManifestEventLoader

_SESSION_UNKNOWN = "<unknown_session>"
_COMPONENT_UNKNOWN = "<unknown_component>"
_COMPONENT_MISSING = "<missing_components>"


@dataclass
class ManifestStats:
    """Aggregated counts describing a manifest."""

    total_events: int
    session_counts: Counter[str]
    component_counts: Counter[str]
    technique_counts: Counter[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_events": self.total_events,
            "unique_sessions": len(self.session_counts),
            "session_counts": dict(self.session_counts),
            "component_counts": dict(self.component_counts),
            "technique_counts": dict(self.technique_counts),
        }


@dataclass
class CounterDiff:
    label: str
    baseline: int
    candidate: int
    delta: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "baseline": self.baseline,
            "candidate": self.candidate,
            "delta": self.delta,
        }


def _normalise_session(value: object) -> str:
    if isinstance(value, str) and value:
        return value
    return _SESSION_UNKNOWN


def _extract_component_labels(components: object) -> Iterable[str]:
    if not isinstance(components, list):
        return ()

    labels: List[str] = []
    for entry in components:
        if isinstance(entry, dict):
            label = entry.get("label")
            if isinstance(label, str) and label:
                labels.append(label)
            else:
                labels.append(_COMPONENT_UNKNOWN)
        else:
            labels.append(_COMPONENT_UNKNOWN)
    if not labels:
        return (_COMPONENT_MISSING,)
    return labels


def gather_stats(manifest_path: Path) -> ManifestStats:
    loader = ManifestEventLoader(manifest_path)
    session_counts: Counter[str] = Counter()
    component_counts: Counter[str] = Counter()
    technique_counts: Counter[str] = Counter()
    total_events = 0

    for record in loader:
        total_events += 1

        event = record.event
        session_counts[_normalise_session(event.get("session_id"))] += 1

        component_labels = list(_extract_component_labels(event.get("components")))
        if component_labels:
            component_counts.update(component_labels)
        else:
            component_counts[_COMPONENT_MISSING] += 1

        technique_counts.update(record.techniques)

    return ManifestStats(
        total_events=total_events,
        session_counts=session_counts,
        component_counts=component_counts,
        technique_counts=technique_counts,
    )


def diff_counters(baseline: Counter[str], candidate: Counter[str]) -> List[CounterDiff]:
    labels = set(baseline.keys()) | set(candidate.keys())
    diffs: List[CounterDiff] = []
    for label in sorted(labels):
        base = int(baseline.get(label, 0))
        cand = int(candidate.get(label, 0))
        if base == cand == 0:
            continue
        diffs.append(CounterDiff(label=label, baseline=base, candidate=cand, delta=cand - base))
    diffs.sort(key=lambda item: (-abs(item.delta), item.label))
    return diffs


def format_diff_table(title: str, rows: List[CounterDiff], limit: int) -> None:
    print(f"\n{title}")
    if not rows:
        print("  (no differences)")
        return

    header = f"  {'label':30} {'baseline':>12} {'candidate':>12} {'delta':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for diff in rows[:limit]:
        label = diff.label if len(diff.label) <= 30 else diff.label[:27] + "..."
        print(
            f"  {label:30} {diff.baseline:12,d} {diff.candidate:12,d} {diff.delta:+8,d}"
        )
    if len(rows) > limit:
        suppressed = len(rows) - limit
        print(f"  ... ({suppressed} additional entries suppressed; see --json-output for full list)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Reference events JSONL manifest")
    parser.add_argument("candidate", type=Path, help="New events JSONL manifest to compare")
    parser.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Number of rows to display per section (default: 15)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path to write the full diff as JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    baseline_path: Path = args.baseline
    candidate_path: Path = args.candidate

    if not baseline_path.exists():
        raise FileNotFoundError(f"Baseline manifest not found: {baseline_path}")
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate manifest not found: {candidate_path}")

    baseline_stats = gather_stats(baseline_path)
    candidate_stats = gather_stats(candidate_path)

    total_delta = candidate_stats.total_events - baseline_stats.total_events
    print("Totals")
    print(f"  Baseline events : {baseline_stats.total_events:,}")
    print(f"  Candidate events: {candidate_stats.total_events:,}")
    print(f"  Delta           : {total_delta:+,}")
    print(f"  Baseline sessions : {len(baseline_stats.session_counts):,}")
    print(f"  Candidate sessions: {len(candidate_stats.session_counts):,}")
    print(
        f"  Session delta     : {len(candidate_stats.session_counts) - len(baseline_stats.session_counts):+,}"
    )

    session_diffs = diff_counters(baseline_stats.session_counts, candidate_stats.session_counts)
    component_diffs = diff_counters(
        baseline_stats.component_counts,
        candidate_stats.component_counts,
    )
    technique_diffs = diff_counters(
        baseline_stats.technique_counts,
        candidate_stats.technique_counts,
    )

    format_diff_table("Per-session counts", session_diffs, args.limit)
    format_diff_table("Component label counts", component_diffs, args.limit)
    format_diff_table("Technique counts", technique_diffs, args.limit)

    if args.json_output:
        payload = {
            "baseline": baseline_stats.to_dict(),
            "candidate": candidate_stats.to_dict(),
            "delta": {
                "total_events": total_delta,
                "session_counts": {diff.label: diff.to_dict() for diff in session_diffs},
                "component_counts": {diff.label: diff.to_dict() for diff in component_diffs},
                "technique_counts": {diff.label: diff.to_dict() for diff in technique_diffs},
            },
        }
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nFull JSON diff written to {args.json_output}")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
