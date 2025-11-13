#!/usr/bin/env python3
"""Analyze hi-hat transitions (open->close) to estimate bark frequency."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from training import event_loader

HIHAT_LABELS = {"hihat_open", "hihat_closed", "hihat_pedal"}
FOLLOW_UP = {"hihat_closed", "hihat_pedal"}


def summarize(session_results: Dict[str, dict]) -> dict:
    total_opens = sum(item["opens"] for item in session_results.values())
    total_barks = sum(item["bark_candidates"] for item in session_results.values())
    ratio = (total_barks / total_opens) if total_opens else 0.0
    top_sessions = sorted(
        session_results.items(), key=lambda kv: kv[1]["bark_candidates"], reverse=True
    )[:20]
    return {
        "total_sessions": len(session_results),
        "total_open_events": total_opens,
        "bark_candidates": total_barks,
        "bark_ratio": ratio,
        "top_sessions": [
            {"session_id": sid, **metrics} for sid, metrics in top_sessions
        ],
    }


def analyze_manifest(path: Path, window: float) -> dict:
    per_session: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {"opens": 0, "bark_candidates": 0, "queue": deque()}
    )

    for record in event_loader.ManifestEventLoader(path):
        event = record.event
        session_id = event.get("session_id") or "unknown"
        onset = float(event.get("onset_time", 0.0))
        components = event.get("components") or []

        if not components:
            continue

        session_data = per_session[session_id]
        queue: deque = session_data["queue"]  # type: ignore[assignment]

        # Drop stale opens that are beyond the window.
        while queue and onset - queue[0][0] > window:
            queue.popleft()

        for component in components:
            label = component.get("label")
            if label not in HIHAT_LABELS:
                continue

            if label == "hihat_open":
                session_data["opens"] += 1
                queue.append([onset, False])
            elif label in FOLLOW_UP:
                # Ensure queue only contains events within the window before matching.
                while queue and onset - queue[0][0] > window:
                    queue.popleft()
                for record in queue:
                    if not record[1]:
                        record[1] = True
                        session_data["bark_candidates"] += 1
                        break

    session_results: Dict[str, dict] = {}
    for session_id, data in per_session.items():
        opens = int(data["opens"])
        barks = int(data["bark_candidates"])
        session_results[session_id] = {
            "opens": opens,
            "bark_candidates": barks,
            "bark_ratio": (barks / opens) if opens else 0.0,
        }

    summary = summarize(session_results)
    summary["window_seconds"] = window
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifests",
        nargs="+",
        type=Path,
        help="One or more event manifest JSONL files",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=0.2,
        help="Open-to-close window in seconds to qualify as a bark (default: 0.2)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination JSON summary path",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-manifest progress output",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    report: Dict[str, dict] = {}
    for idx, manifest in enumerate(args.manifests, start=1):
        if not manifest.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest}")
        summary = analyze_manifest(manifest, args.window)
        report[manifest.stem] = summary
        if not args.quiet:
            print(
                f"[{idx}/{len(args.manifests)}] {manifest} :: opens={summary['total_open_events']} barks={summary['bark_candidates']}",
                flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":  # pragma: no cover
    main()
