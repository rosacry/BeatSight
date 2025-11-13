#!/usr/bin/env python3
"""Derive crash cymbal variant labels using metadata heuristics and spectral cues."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# Default heuristics mapping metadata hints to crash variant labels.
# "crash" remains the canonical first cymbal; additional variants map to crash2/3.
_METADATA_VARIANT_MAP: Dict[str, Tuple[str, float]] = {
    "high": ("crash", 1.0),
    "primary": ("crash", 1.0),
    "bright": ("crash", 0.95),
    "low": ("crash2", 1.0),
    "secondary": ("crash2", 1.0),
    "dark": ("crash2", 0.95),
    "mid": ("crash2", 0.9),
    "medium": ("crash2", 0.9),
    "tertiary": ("crash3", 1.0),
    "third": ("crash3", 0.95),
}

_TECHNIQUE_VARIANT_MAP: Dict[str, Tuple[str, float]] = {
    "crash_high": ("crash", 0.8),
    "crash_low": ("crash2", 0.85),
    "crash_mid": ("crash2", 0.75),
    "crash_dark": ("crash2", 0.75),
    "crash_bright": ("crash", 0.75),
}


@dataclass
class CrashAssignment:
    event_id: str
    session_id: str
    label: str
    method: str
    confidence: float
    notes: str

    def to_json(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "session_id": self.session_id,
            "label": self.label,
            "method": self.method,
            "confidence": round(self.confidence, 4),
        }
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass
class AssignmentSummary:
    total_events: int
    assigned_events: int
    by_label: Dict[str, int]
    methods: Dict[str, int]

    def to_json(self) -> Dict[str, object]:
        return {
            "total_crash_events": self.total_events,
            "assigned_events": self.assigned_events,
            "coverage": {label: count for label, count in sorted(self.by_label.items())},
            "methods": {method: count for method, count in sorted(self.methods.items())},
        }


@dataclass
class EmbeddingRecord:
    """Minimal descriptor extracted from the crash embeddings export."""

    event_id: str
    session_id: str
    spectral_centroid: float
    metadata: Dict[str, float]


@dataclass
class SpectralConfig:
    """Runtime configuration for the spectral clustering fallback."""

    min_events: int = 8
    min_cluster_size: int = 3
    min_centroid_gap: float = 200.0
    min_gap_ratio: float = 0.25


def iter_events(path: Path) -> Iterator[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
                raise ValueError(f"Failed to parse JSON on line {line_number}: {exc.msg}") from exc


def _instrument_variant(component: Dict[str, object]) -> Optional[str]:
    variant = component.get("instrument_variant")
    if isinstance(variant, str):
        cleaned = variant.strip().lower()
        return cleaned or None
    return None


def _infer_from_metadata(component: Dict[str, object]) -> Optional[Tuple[str, float, str]]:
    variant = _instrument_variant(component)
    if not variant:
        return None
    mapping = _METADATA_VARIANT_MAP.get(variant)
    if mapping:
        label, confidence = mapping
        return label, confidence, f"instrument_variant={variant}"
    return None


def _infer_from_techniques(techniques: Sequence[str]) -> Optional[Tuple[str, float, str]]:
    for technique in techniques:
        if not isinstance(technique, str):
            continue
        technique_key = technique.strip().lower()
        if not technique_key:
            continue
        mapping = _TECHNIQUE_VARIANT_MAP.get(technique_key)
        if mapping:
            label, confidence = mapping
            return label, confidence, f"technique={technique_key}"
    return None


def load_embedding_records(path: Path) -> Dict[str, EmbeddingRecord]:
    """Load per-event crash embeddings emitted by ``extract_crash_embeddings``."""

    records: Dict[str, EmbeddingRecord] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Failed to parse embedding JSON on line {line_number}: {exc.msg}") from exc

            event_id = str(payload.get("event_id") or "").strip()
            session_id = str(payload.get("session_id") or "").strip()
            metrics = payload.get("metrics") or {}
            centroid = metrics.get("spectral_centroid")
            if not event_id or not session_id:
                continue
            if not isinstance(centroid, (int, float)):
                continue

            metadata: Dict[str, float] = {}
            for key in ("spectral_bandwidth", "spectral_rolloff", "zero_crossing_rate", "rms"):
                value = metrics.get(key)
                if isinstance(value, (int, float)):
                    metadata[key] = float(value)

            records[event_id] = EmbeddingRecord(
                event_id=event_id,
                session_id=session_id,
                spectral_centroid=float(centroid),
                metadata=metadata,
            )

    return records


def _cluster_session_spectral(session_id: str, records: Sequence[EmbeddingRecord], config: SpectralConfig) -> List[CrashAssignment]:
    """Split crash events into low/high spectral groups and label the lows as crash2."""

    total_events = len(records)
    if total_events < max(config.min_events, config.min_cluster_size * 2):
        return []

    ordered_indices = sorted(range(total_events), key=lambda idx: records[idx].spectral_centroid)
    ordered_centroids = [records[idx].spectral_centroid for idx in ordered_indices]

    if ordered_centroids[-1] - ordered_centroids[0] <= 1e-6:
        return []

    prefix_sums: List[float] = []
    running_total = 0.0
    for value in ordered_centroids:
        running_total += value
        prefix_sums.append(running_total)

    best_result: Optional[Tuple[int, float, float, float, float]] = None  # split, gap, ratio, mean_low, mean_high
    min_cluster = max(config.min_cluster_size, 2)
    total_sum = prefix_sums[-1]

    for split in range(min_cluster, total_events - min_cluster + 1):
        left_sum = prefix_sums[split - 1]
        right_sum = total_sum - left_sum
        left_count = split
        right_count = total_events - split
        left_mean = left_sum / left_count
        right_mean = right_sum / right_count
        gap = right_mean - left_mean
        if gap <= 0:
            continue

        span = ordered_centroids[-1] - ordered_centroids[0]
        ratio = gap / span if span > 1e-6 else 0.0
        if gap < config.min_centroid_gap and ratio < config.min_gap_ratio:
            continue

        score = gap * (ratio + 1.0)
        if best_result is None or score > best_result[1] * (best_result[2] + 1.0):
            best_result = (split, gap, ratio, left_mean, right_mean)

    if best_result is None:
        return []

    split, gap, ratio, mean_low, mean_high = best_result
    low_indices = ordered_indices[:split]

    confidence_raw = max(ratio, gap / (gap + config.min_centroid_gap))
    confidence = round(max(0.05, min(confidence_raw, 1.0)), 4)
    notes = (
        f"spectral_centroid_gap={gap:.1f}Hz "
        f"mean_low={mean_low:.1f}Hz mean_high={mean_high:.1f}Hz"
    )

    return [
        CrashAssignment(
            event_id=records[idx].event_id,
            session_id=session_id,
            label="crash2",
            method="spectral_cluster",
            confidence=confidence,
            notes=notes,
        )
        for idx in low_indices
    ]


def derive_assignments(
    events: Iterable[Dict[str, object]],
    embeddings: Optional[Dict[str, EmbeddingRecord]] = None,
    spectral_config: Optional[SpectralConfig] = None,
) -> Tuple[Dict[str, CrashAssignment], AssignmentSummary, Dict[str, Dict[str, object]]]:
    assignments: Dict[str, CrashAssignment] = {}
    total_crash_events = 0
    label_counts: Dict[str, int] = {}
    method_counts: Dict[str, int] = {}
    session_details: Dict[str, Dict[str, object]] = {}

    embedding_map = embeddings or {}
    pending_spectral: Dict[str, List[EmbeddingRecord]] = defaultdict(list)

    for event in events:
        components = event.get("components")
        if not isinstance(components, list):
            continue

        crash_components = [comp for comp in components if isinstance(comp, dict) and comp.get("label") == "crash"]
        if not crash_components:
            continue

        total_crash_events += len(crash_components)

        techniques = event.get("techniques") or []
        techniques = techniques if isinstance(techniques, list) else []

        session_id = event.get("session_id")
        session_id = session_id if isinstance(session_id, str) else "unknown"
        session_stats = session_details.setdefault(
            session_id,
            {"total_crash_events": 0, "assigned": 0, "methods": set()},
        )
        session_stats["total_crash_events"] += len(crash_components)

        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue

        best_assignment: Optional[CrashAssignment] = None

        for component in crash_components:
            metadata_candidate = _infer_from_metadata(component)
            if metadata_candidate:
                label, confidence, notes = metadata_candidate
                best_assignment = CrashAssignment(
                    event_id=event_id,
                    session_id=session_id,
                    label=label,
                    method="metadata_variant",
                    confidence=confidence,
                    notes=notes,
                )
                break

        if best_assignment is None:
            technique_candidate = _infer_from_techniques(techniques)
            if technique_candidate:
                label, confidence, notes = technique_candidate
                best_assignment = CrashAssignment(
                    event_id=event_id,
                    session_id=session_id,
                    label=label,
                    method="technique_hint",
                    confidence=confidence,
                    notes=notes,
                )

        if best_assignment is None:
            record = embedding_map.get(event_id)
            if record and record.spectral_centroid > 0:
                if record.session_id == session_id:
                    pending_spectral[session_id].append(record)
            continue

        if best_assignment.event_id in assignments:
            continue

        if best_assignment.label == "crash":
            # Nothing to re-label; skip but keep per-session bookkeeping consistent.
            continue

        assignments[best_assignment.event_id] = best_assignment
        label_counts[best_assignment.label] = label_counts.get(best_assignment.label, 0) + 1
        method_counts[best_assignment.method] = method_counts.get(best_assignment.method, 0) + 1
        session_stats["assigned"] += 1
        session_stats["methods"].add(best_assignment.method)

    if spectral_config and pending_spectral:
        for session_id, records in pending_spectral.items():
            spectral_assignments = _cluster_session_spectral(session_id, records, spectral_config)
            if not spectral_assignments:
                continue
            for assignment in spectral_assignments:
                if assignment.event_id in assignments:
                    continue
                assignments[assignment.event_id] = assignment
                label_counts[assignment.label] = label_counts.get(assignment.label, 0) + 1
                method_counts[assignment.method] = method_counts.get(assignment.method, 0) + 1
                session_stats = session_details.setdefault(
                    assignment.session_id,
                    {"total_crash_events": 0, "assigned": 0, "methods": set()},
                )
                session_stats["assigned"] = session_stats.get("assigned", 0) + 1
                methods = session_stats.get("methods")
                if isinstance(methods, set):
                    methods.add(assignment.method)

    summary = AssignmentSummary(
        total_events=total_crash_events,
        assigned_events=len(assignments),
        by_label=label_counts,
        methods=method_counts,
    )

    # Finalise session metadata (convert method sets to sorted lists)
    for stats in session_details.values():
        methods = stats.get("methods", set())
        if isinstance(methods, set):
            stats["methods"] = sorted(methods)

    return assignments, summary, session_details


def write_assignments(
    assignments: Dict[str, CrashAssignment],
    summary: AssignmentSummary,
    sessions: Dict[str, Dict[str, object]],
    output: Path,
) -> None:
    payload = {
        "summary": summary.to_json(),
        "events": {event_id: assignment.to_json() for event_id, assignment in assignments.items()},
        "sessions": {
            session_id: {
                "total_crash_events": data.get("total_crash_events", 0),
                "assigned": data.get("assigned", 0),
                "methods": data.get("methods", []),
            }
            for session_id, data in sessions.items()
        },
    }
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive crash dual-label assignments from metadata and spectral embeddings",
    )
    parser.add_argument("events", type=Path, help="Events JSONL file to analyse")
    parser.add_argument("output", type=Path, help="Output JSON mapping file")
    parser.add_argument(
        "--embeddings",
        type=Path,
        help="Crash embeddings JSONL generated by extract_crash_embeddings.py",
    )
    parser.add_argument(
        "--spectral-min-events",
        type=int,
        default=8,
        help="Minimum crash events per session before spectral clustering runs (default: 8)",
    )
    parser.add_argument(
        "--spectral-min-cluster",
        type=int,
        default=3,
        help="Minimum events per spectral cluster when splitting (default: 3)",
    )
    parser.add_argument(
        "--spectral-min-gap",
        type=float,
        default=200.0,
        help="Minimum spectral centroid gap in Hz to accept a split (default: 200)",
    )
    parser.add_argument(
        "--spectral-min-gap-ratio",
        type=float,
        default=0.25,
        help="Minimum gap-to-range ratio (0-1) required to accept a split (default: 0.25)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    embeddings: Optional[Dict[str, EmbeddingRecord]] = None
    spectral_config: Optional[SpectralConfig] = None

    if args.embeddings:
        embeddings = load_embedding_records(args.embeddings)
        spectral_config = SpectralConfig(
            min_events=max(args.spectral_min_events, args.spectral_min_cluster * 2),
            min_cluster_size=max(args.spectral_min_cluster, 2),
            min_centroid_gap=args.spectral_min_gap,
            min_gap_ratio=args.spectral_min_gap_ratio,
        )

    assignments, summary, sessions = derive_assignments(
        iter_events(args.events),
        embeddings=embeddings,
        spectral_config=spectral_config,
    )
    write_assignments(assignments, summary, sessions, args.output)


if __name__ == "__main__":
    main()
