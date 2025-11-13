#!/usr/bin/env python3
"""Utilities for normalising component aliases and crash dual-label assignments."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ALIAS = {
    "china2": "china",
    "tom_floor": "tom_low",
    "tom_low2": "tom_low",
}


@dataclass(frozen=True)
class CrashLabelAssignment:
    """Mapping entry describing a crash label override for a specific event."""

    event_id: str
    session_id: Optional[str]
    target_label: str
    method: str
    confidence: Optional[float]
    notes: Optional[str]

    @classmethod
    def from_payload(cls, event_id: str, payload: Dict[str, object]) -> "CrashLabelAssignment":
        label = payload.get("label") or payload.get("target_label")
        if not isinstance(label, str):
            raise ValueError(f"Crash assignment for {event_id!r} missing 'label'")
        method = payload.get("method", "unknown")
        if not isinstance(method, str):
            raise ValueError(f"Crash assignment for {event_id!r} has invalid 'method'")
        session_id = payload.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError(
                f"Crash assignment for {event_id!r} has non-string 'session_id'"
            )
        confidence_raw = payload.get("confidence")
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else None
        notes = payload.get("notes")
        if notes is not None and not isinstance(notes, str):
            notes = str(notes)
        return cls(
            event_id=event_id,
            session_id=session_id,
            target_label=label,
            method=method,
            confidence=confidence,
            notes=notes,
        )

    def to_history_entry(self, stage: str) -> Dict[str, object]:
        entry: Dict[str, object] = {"annotation_stage": stage, "method": self.method}
        if self.confidence is not None:
            entry["confidence"] = self.confidence
        if self.notes:
            entry["notes"] = self.notes
        if self.session_id:
            entry.setdefault("session_id", self.session_id)
        return entry


def normalize_components(components: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """Apply simple alias rewrites to component labels."""

    normalized: List[Dict[str, object]] = []
    for component in components or []:
        if not isinstance(component, dict):
            continue
        label = component.get("label")
        if not isinstance(label, str):
            normalized.append(component)
            continue

        mapped = ALIAS.get(label, label)
        if mapped != label:
            if label == "china2":
                component["instance"] = 2
            if label in ("tom_floor", "tom_low2"):
                component["instance"] = 2
            component["label"] = mapped
        normalized.append(component)
    return normalized


def load_crash_mapping(path: Optional[Path]) -> Dict[str, CrashLabelAssignment]:
    """Load crash dual-label assignments when provided."""

    if not path:
        return {}

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    events_block = payload.get("events") if isinstance(payload, dict) else None
    if events_block is None and isinstance(payload, dict):
        # Allow direct mapping dict[event_id] -> {...}
        events_block = {
            key: value
            for key, value in payload.items()
            if isinstance(value, dict) and key not in {"summary", "sessions"}
        }

    if not isinstance(events_block, dict):
        raise ValueError("Crash mapping must contain an 'events' object with per-event data")

    assignments: Dict[str, CrashLabelAssignment] = {}
    for event_id, entry in events_block.items():
        if not isinstance(event_id, str) or not isinstance(entry, dict):
            continue
        mapping = CrashLabelAssignment.from_payload(event_id, entry)
        assignments[event_id] = mapping
    return assignments


def apply_crash_assignment(
    event: Dict[str, object],
    assignment: CrashLabelAssignment,
    stage_tag: str,
    technique_tag: str,
) -> bool:
    """Mutate *event* in-place according to the provided crash assignment."""

    components = event.get("components")
    if not isinstance(components, list):
        return False

    changed = False
    for component in components:
        if not isinstance(component, dict):
            continue
        if component.get("label") != "crash":
            continue
        if assignment.target_label == "crash":
            # No change required, keep label but propagate provenance if missing.
            continue
        component["label"] = assignment.target_label
        component.setdefault("annotation_stage", stage_tag)
        component.setdefault("annotation_method", assignment.method)
        if assignment.confidence is not None:
            component["annotation_confidence"] = assignment.confidence
        if assignment.notes:
            component.setdefault("annotation_notes", assignment.notes)
        changed = True

    if not changed:
        return False

    history = assignment.to_history_entry(stage_tag)
    history_list = event.setdefault("annotation_history", [])
    if isinstance(history_list, list):
        history_list.append(history)
    else:  # fallback: replace invalid value
        event["annotation_history"] = [history]

    techniques = event.get("techniques") or []
    if not isinstance(techniques, list):
        techniques = []
    if technique_tag not in techniques:
        techniques.append(technique_tag)
        techniques_sorted = sorted({t for t in techniques if isinstance(t, str) and t})
        event["techniques"] = techniques_sorted

    return True


def process_events(
    src: Path,
    dst: Path,
    crash_mapping: Dict[str, CrashLabelAssignment],
    crash_stage_tag: str,
    crash_technique_tag: str,
) -> Dict[str, int]:
    """Transform events JSONL file, applying aliases and optional crash mappings."""

    stats = {"total": 0, "alias_normalized": 0, "crash_relabelled": 0}

    with src.open("r", encoding="utf-8") as handle_in, dst.open(
        "w", encoding="utf-8"
    ) as handle_out:
        for raw in handle_in:
            if not raw.strip():
                continue
            event = json.loads(raw)
            stats["total"] += 1

            components = event.get("components")
            if event.get("negative_example"):
                event["components"] = []
            elif isinstance(components, list):
                normalized = normalize_components(components)
                if normalized != components:
                    stats["alias_normalized"] += 1
                event["components"] = normalized

            event_id = event.get("event_id")
            assignment = crash_mapping.get(event_id) if isinstance(event_id, str) else None
            if assignment and apply_crash_assignment(
                event, assignment, crash_stage_tag, crash_technique_tag
            ):
                stats["crash_relabelled"] += 1

            handle_out.write(json.dumps(event, separators=(",", ":")) + "\n")

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalise components and apply crash dual-label assignments"
    )
    parser.add_argument("src", type=Path, help="Input events JSONL file")
    parser.add_argument("dst", type=Path, help="Output events JSONL file")
    parser.add_argument(
        "--crash-mapping",
        type=Path,
        help="Optional JSON file describing crash label assignments",
    )
    parser.add_argument(
        "--crash-stage-tag",
        default="crash_dual_label",
        help="Annotation history tag applied when relabelling crashes",
    )
    parser.add_argument(
        "--crash-technique-tag",
        default="crash_dual_label",
        help="Technique added to events relabelled via crash mapping",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    crash_mapping = load_crash_mapping(args.crash_mapping)
    stats = process_events(
        src=args.src,
        dst=args.dst,
        crash_mapping=crash_mapping,
        crash_stage_tag=args.crash_stage_tag,
        crash_technique_tag=args.crash_technique_tag,
    )
    if crash_mapping:
        print(
            json.dumps(
                {
                    "events_total": stats["total"],
                    "alias_normalized": stats["alias_normalized"],
                    "crash_relabelled": stats["crash_relabelled"],
                }
            )
        )


if __name__ == "__main__":
    main()
