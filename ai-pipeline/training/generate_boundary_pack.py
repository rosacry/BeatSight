"""Generate streaming boundary pack examples from event annotations.

Identifies events that occur near the start or end of sliding windows and
exports them as JSONL for boundary recall evaluation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass
class Event:
    sample_id: str
    session_id: Optional[str]
    onset_ms: float
    labels: List[str]
    payload: Dict

    @classmethod
    def from_dict(cls, payload: Dict) -> "Event":
        sample_id = payload.get("sample_id")
        if not sample_id:
            raise ValueError("Event missing sample_id")
        onset = payload.get("onset_time")
        if onset is None:
            raise ValueError(f"Event {sample_id} missing onset_time")
        labels: Set[str] = set()
        for component in payload.get("components", []):
            label = component.get("label")
            if label:
                labels.add(label)
        # Fallback single label
        if not labels and payload.get("label"):
            labels.add(payload["label"])
        return cls(
            sample_id=sample_id,
            session_id=payload.get("session_id"),
            onset_ms=float(onset) * 1000.0,
            labels=sorted(labels),
            payload=payload,
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate boundary pack JSONL")
    parser.add_argument("--events", required=True, help="Input events JSONL (annotations/events.jsonl)")
    parser.add_argument("--output", required=True, help="Output boundary JSONL path")
    parser.add_argument("--window-ms", type=float, required=True, help="Sliding window length in milliseconds")
    parser.add_argument("--hop-ms", type=float, required=True, help="Sliding window hop size in milliseconds")
    parser.add_argument("--margin-ms", type=float, default=40.0, help="Distance from edge considered boundary")
    parser.add_argument(
        "--edges",
        nargs="*",
        choices=["leading", "trailing"],
        default=["leading", "trailing"],
        help="Edges to include",
    )
    parser.add_argument("--max-per-edge", type=int, default=2000, help="Maximum samples per edge type")
    parser.add_argument("--include-label", action="append", default=[], help="Optional label whitelist")
    parser.add_argument("--exclude-label", action="append", default=[], help="Optional label blacklist")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only")
    return parser.parse_args(argv)


def load_events(path: Path) -> List[Event]:
    events: List[Event] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            try:
                events.append(Event.from_dict(payload))
            except ValueError as exc:
                print(f"[boundary_pack] Skipping event: {exc}", file=sys.stderr)
    if not events:
        raise ValueError(f"No valid events found in {path}")
    return events


def compute_edges(
    event: Event,
    window_ms: float,
    hop_ms: float,
    margin_ms: float,
    include_edges: Set[str],
) -> List[Tuple[str, int, float]]:
    """Return list of (edge, window_index, distance_ms)."""
    onset_ms = event.onset_ms
    window_index = int(math.floor(onset_ms / hop_ms))
    window_start = window_index * hop_ms
    window_end = window_start + window_ms

    results: List[Tuple[str, int, float]] = []

    # Leading edge: close to window start
    dist_start = onset_ms - window_start
    if "leading" in include_edges and 0.0 <= dist_start <= margin_ms:
        results.append(("leading", window_index, dist_start))

    # Trailing edge: close to window end
    dist_end = window_end - onset_ms
    if "trailing" in include_edges and 0.0 <= dist_end <= margin_ms:
        results.append(("trailing", window_index, dist_end))

    return results


def event_to_record(
    event: Event,
    edge: str,
    window_index: int,
    distance_ms: float,
    window_ms: float,
    hop_ms: float,
) -> Dict:
    record = {
        "sample_id": event.sample_id,
        "session_id": event.session_id,
        "labels": event.labels,
        "window_index": window_index,
        "window_size_ms": window_ms,
        "hop_size_ms": hop_ms,
        "edge": edge,
        "distance_ms": round(distance_ms, 3),
        "onset_ms": round(event.onset_ms, 3),
    }
    if event.payload.get("audio_path"):
        record["audio_path"] = event.payload["audio_path"]
    return record


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    include_labels = set(args.include_label) if args.include_label else None
    exclude_labels = set(args.exclude_label)

    try:
        events = load_events(Path(args.events))
    except Exception as exc:
        print(f"[boundary_pack] Failed to load events: {exc}", file=sys.stderr)
        return 2

    records: List[Dict] = []
    counts: Dict[str, int] = {"leading": 0, "trailing": 0}
    include_edges = set(args.edges)

    for event in events:
        if include_labels is not None and not (set(event.labels) & include_labels):
            continue
        if exclude_labels and (set(event.labels) & exclude_labels):
            continue

        edges = compute_edges(event, args.window_ms, args.hop_ms, args.margin_ms, include_edges)
        for edge, window_index, distance in edges:
            if counts[edge] >= args.max_per_edge:
                continue
            record = event_to_record(event, edge, window_index, distance, args.window_ms, args.hop_ms)
            records.append(record)
            counts[edge] += 1

    print(
        f"Collected {len(records)} boundary samples (leading={counts['leading']}, "
        f"trailing={counts['trailing']})."
    )

    if args.dry_run:
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record))
            handle.write("\n")

    print(f"Boundary pack written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
