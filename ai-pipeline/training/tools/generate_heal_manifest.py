#!/usr/bin/env python3
"""Generate a trimmed manifest containing only events with missing audio clips.

This helper inspects an existing dataset bundle produced by
``build_training_dataset.py``. It identifies clips referenced in the label
files that are missing on disk, validates the label metadata for duplicates or
inconsistencies, and emits a compact JSONL manifest suitable for a targeted
``--resume --heal-missing-clips`` run.

The script performs three phases:

1. Scan every ``*_labels.json`` file under the dataset root and collect clips
   whose audio file is absent. During this pass it reports duplicate label
   entries and summaries per split.
2. Walk the original manifest once, writing only those events whose
   ``event_id`` matches a missing clip discovered in step 1.
3. Produce an optional JSON summary describing the findings so downstream
   automation can double-check the healing workflow.

The resulting manifest generally contains a few hundred thousand events instead
of tens of millions, dramatically reducing the time required to heal missing
clips after an interrupted export.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class MissingClip:
    """Metadata captured for a single clip whose audio file is missing."""

    split: str
    relative_path: str
    event_id: str
    label: str
    session_id: str
    source_set: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "split": self.split,
            "relative_path": self.relative_path,
            "event_id": self.event_id,
            "label": self.label,
            "session_id": self.session_id,
            "source_set": self.source_set,
        }


@dataclass
class MissingScanResult:
    """Container describing dataset-level findings."""

    missing_by_event: Dict[str, List[MissingClip]] = field(default_factory=dict)
    duplicate_label_entries: List[Tuple[str, str]] = field(default_factory=list)
    total_label_entries: int = 0
    missing_clip_total: int = 0

    def add_missing_clip(self, clip: MissingClip) -> None:
        self.missing_by_event.setdefault(clip.event_id, []).append(clip)
        self.missing_clip_total += 1


@dataclass
class ManifestFilterStats:
    """Summary emitted after trimming the manifest."""

    written_events: int
    remaining_events: Set[str]
    missing_component_labels: Dict[str, Set[str]]


def _discover_label_files(dataset_root: Path) -> Iterator[Tuple[str, Path]]:
    for split_dir in dataset_root.iterdir():
        if not split_dir.is_dir():
            continue
        split_name = split_dir.name
        label_path = split_dir / f"{split_name}_labels.json"
        if label_path.is_file():
            yield split_name, label_path


def _iter_label_entries(path: Path) -> Iterator[Mapping[str, object]]:
    """Stream JSON objects from the pretty-printed label arrays."""

    buffer: List[str] = []
    depth = 0
    collecting = False
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not collecting:
                if stripped.startswith("{"):
                    collecting = True
                    depth = stripped.count("{") - stripped.count("}")
                    buffer = [raw_line]
                    if depth <= 0:
                        payload = stripped.rstrip(",")
                        yield json.loads(payload)
                        collecting = False
                    continue
                # Skip array delimiters and whitespace
                continue
            buffer.append(raw_line)
            depth += raw_line.count("{") - raw_line.count("}")
            if depth <= 0:
                payload = "".join(buffer).strip().rstrip(",")
                if payload:
                    yield json.loads(payload)
                buffer = []
                collecting = False
    if buffer:
        payload = "".join(buffer).strip().rstrip(",")
        if payload:
            yield json.loads(payload)


def _collect_missing_clips(dataset_root: Path) -> MissingScanResult:
    result = MissingScanResult()
    for split, label_path in sorted(_discover_label_files(dataset_root)):
        seen_paths: Set[str] = set()
        for entry in _iter_label_entries(label_path):
            result.total_label_entries += 1
            rel_path = str(entry.get("file") or "").strip()
            if not rel_path:
                continue
            normalized_rel = rel_path.replace("\\", "/")
            if normalized_rel in seen_paths:
                result.duplicate_label_entries.append((split, normalized_rel))
            else:
                seen_paths.add(normalized_rel)
            audio_path = (dataset_root / split / Path(normalized_rel)).resolve()
            if audio_path.is_file():
                continue
            event_id = str(entry.get("event_id") or "").strip()
            label = str(entry.get("label") or "").strip()
            session_id = str(entry.get("session_id") or "").strip()
            source_set = str(entry.get("source_set") or "").strip()
            clip = MissingClip(
                split=split,
                relative_path=normalized_rel,
                event_id=event_id,
                label=label,
                session_id=session_id,
                source_set=source_set,
            )
            result.add_missing_clip(clip)
    return result


def _filter_manifest(
    manifest_path: Path,
    output_path: Path,
    missing_by_event: Mapping[str, Sequence[MissingClip]],
) -> ManifestFilterStats:
    remaining_event_ids: Set[str] = set(event_id for event_id in missing_by_event if event_id)
    missing_component_labels: Dict[str, Set[str]] = {
        event_id: {clip.label for clip in clips if clip.label}
        for event_id, clips in missing_by_event.items()
    }
    written_events = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8"
    ) as dest:
        for raw_line in src:
            if not remaining_event_ids:
                break
            stripped = raw_line.strip()
            if not stripped:
                continue
            event: Mapping[str, object]
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            event_id = str(event.get("event_id") or "").strip()
            if event_id not in remaining_event_ids:
                continue
            components = event.get("components")
            if isinstance(components, Sequence):
                labels_in_event = {
                    str((component or {}).get("label") or "").strip()
                    for component in components
                    if isinstance(component, Mapping)
                }
                missing_labels = missing_component_labels.get(event_id)
                if missing_labels is not None:
                    missing_component_labels[event_id] = {
                        label for label in missing_labels if label not in labels_in_event
                    }
            dest.write(raw_line if raw_line.endswith("\n") else f"{raw_line}\n")
            written_events += 1
            remaining_event_ids.discard(event_id)
    return ManifestFilterStats(
        written_events=written_events,
        remaining_events=remaining_event_ids,
        missing_component_labels={
            event_id: labels for event_id, labels in missing_component_labels.items() if labels
        },
    )


def _write_summary(
    summary_path: Path,
    scan: MissingScanResult,
    manifest_stats: ManifestFilterStats,
) -> None:
    summary = {
        "missing_clip_total": scan.missing_clip_total,
        "missing_event_total": len(scan.missing_by_event),
        "duplicate_label_entries": [
            {"split": split, "relative_path": rel_path} for split, rel_path in scan.duplicate_label_entries
        ],
        "events_unmatched": sorted(manifest_stats.remaining_events),
        "events_missing_components": {
            event_id: sorted(labels)
            for event_id, labels in manifest_stats.missing_component_labels.items()
        },
        "written_event_total": manifest_stats.written_events,
        "missing_clip_details": {
            event_id: [clip.as_dict() for clip in clips]
            for event_id, clips in scan.missing_by_event.items()
        },
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def generate_heal_manifest(
    *,
    dataset_root: Path,
    manifest_path: Path,
    output_manifest: Path,
    summary_path: Optional[Path] = None,
    fail_on_duplicates: bool = True,
) -> ManifestFilterStats:
    dataset_root = dataset_root.resolve()
    manifest_path = manifest_path.resolve()
    output_manifest = output_manifest.resolve()
    scan = _collect_missing_clips(dataset_root)
    if scan.duplicate_label_entries and fail_on_duplicates:
        duplicates = ", ".join(f"{split}:{path}" for split, path in scan.duplicate_label_entries[:5])
        raise RuntimeError(
            "Duplicate label entries detected (first examples: "
            f"{duplicates}). Pass --allow-duplicates to continue."
        )
    if scan.missing_clip_total == 0:
        raise RuntimeError("No missing clips detected; healing manifest would be empty.")
    manifest_stats = _filter_manifest(manifest_path, output_manifest, scan.missing_by_event)
    if manifest_stats.remaining_events:
        missing_events = ", ".join(sorted(manifest_stats.remaining_events)[:5])
        raise RuntimeError(
            "Failed to locate all missing events in manifest (first examples: "
            f"{missing_events})."
        )
    if manifest_stats.missing_component_labels:
        missing_details = ", ".join(
            f"{event_id}:{sorted(labels)}" for event_id, labels in manifest_stats.missing_component_labels.items()
        )
        raise RuntimeError(
            "Manifest entries missing expected component labels: "
            f"{missing_details}"
        )
    if summary_path is not None:
        _write_summary(summary_path, scan, manifest_stats)
    return manifest_stats


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path, help="Existing dataset directory (train/val/... folders)")
    parser.add_argument("manifest", type=Path, help="Source manifest JSONL used to build the dataset")
    parser.add_argument(
        "output_manifest",
        type=Path,
        help="Destination path for JSONL manifest containing only the missing events",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Optional JSON summary describing the missing clips and manifest generation results",
    )
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Continue even if duplicate label entries are encountered",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        stats = generate_heal_manifest(
            dataset_root=args.dataset_root,
            manifest_path=args.manifest,
            output_manifest=args.output_manifest,
            summary_path=args.summary,
            fail_on_duplicates=not args.allow_duplicates,
        )
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"[generate_heal_manifest] ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Generated heal manifest with"
        f" {stats.written_events:,} events -> {args.output_manifest}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
