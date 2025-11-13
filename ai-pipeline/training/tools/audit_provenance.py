#!/usr/bin/env python3
"""Audit manifest coverage against dataset provenance records."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MANIFEST = Path("ai-pipeline/training/data/manifests/prod_combined_events.jsonl")
_DEFAULT_PROVENANCE_DIR = Path("ai-pipeline/training/data/provenance")


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip()


class ProvenanceIndex:
    """In-memory index of provenance metadata grouped by ``source_set``."""

    def __init__(self) -> None:
        self.sessions: Dict[str, Set[str]] = defaultdict(set)
        self.audio_paths: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.files: Dict[str, Path] = {}

    def add_entry(self, path: Path, payload: Mapping[str, object]) -> None:
        source = str(payload.get("source_set") or "").strip()
        if not source:
            return
        session = str(payload.get("session_id") or "").strip()
        if not session:
            return

        self.sessions[source].add(session)
        self.files.setdefault(source, path)

        for sample in payload.get("sample_paths") or []:
            sample_str = _normalize_path(str(sample))
            if sample_str:
                self.audio_paths[source][session].add(sample_str)

    def provenance_sessions(self, source_set: str) -> Set[str]:
        return set(self.sessions.get(source_set, set()))

    def provenance_audio_paths(self, source_set: str) -> Dict[str, Set[str]]:
        paths = self.audio_paths.get(source_set, {})
        return {session: set(samples) for session, samples in paths.items()}

    def provenance_file(self, source_set: str) -> Optional[Path]:
        return self.files.get(source_set)

    def source_sets(self) -> Set[str]:
        return set(self.sessions.keys()) | set(self.files.keys())


def load_provenance(directory: Path) -> ProvenanceIndex:
    index = ProvenanceIndex()
    if not directory.exists():
        return index

    for path in sorted(directory.glob("*_provenance.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                index.add_entry(path, entry)
    return index


def create_dataset_entry(source_set: str, provenance: ProvenanceIndex) -> MutableMapping[str, object]:
    provenance_sessions = provenance.provenance_sessions(source_set)
    return {
        "event_count": 0,
        "unique_sessions": set(),
        "missing_provenance_sessions": set(),
        "metadata_ref_mismatches": set(),
        "audio_path_missing_from_provenance": set(),
        "provenance_sessions": provenance_sessions,
        "provenance_audio_paths": provenance.provenance_audio_paths(source_set),
        "provenance_file": provenance.provenance_file(source_set),
    }


def audit_manifest(
    manifest_path: Path,
    provenance_index: ProvenanceIndex,
    *,
    allow_unknown: bool = False,
) -> Tuple[Dict[str, MutableMapping[str, object]], Dict[str, int], MutableMapping[str, Set[str]], int]:
    datasets: Dict[str, MutableMapping[str, object]] = {}
    global_issues = {
        "missing_source_set": 0,
        "metadata_ref_missing": 0,
        "metadata_ref_format_errors": 0,
    }
    unknown_sources: MutableMapping[str, Set[str]] = {
        "source_sets": set(),
        "metadata_refs": set(),
        "audio_paths": set(),
    }
    total_events = 0

    with manifest_path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue

            total_events += 1
            source_set = event.get("source_set")
            if not isinstance(source_set, str) or not source_set:
                global_issues["missing_source_set"] += 1
                continue

            if source_set not in datasets:
                datasets[source_set] = create_dataset_entry(source_set, provenance_index)

            dataset_entry = datasets[source_set]
            dataset_entry["event_count"] += 1  # type: ignore[operator]

            session_id = event.get("session_id")
            session_str = str(session_id).strip() if session_id else ""
            if session_str:
                dataset_entry["unique_sessions"].add(session_str)  # type: ignore[index]
                if session_str not in dataset_entry["provenance_sessions"]:
                    dataset_entry["missing_provenance_sessions"].add(session_str)  # type: ignore[index]

            metadata_ref = event.get("metadata_ref")
            ref_session = None
            if metadata_ref in (None, ""):
                global_issues["metadata_ref_missing"] += 1
            elif not isinstance(metadata_ref, str) or not metadata_ref.startswith("provenance:"):
                global_issues["metadata_ref_format_errors"] += 1
            else:
                ref_session = metadata_ref.split(":", 1)[1].strip()
                if ref_session and ref_session not in dataset_entry["provenance_sessions"]:
                    dataset_entry["metadata_ref_mismatches"].add(metadata_ref)  # type: ignore[index]

            audio_path = event.get("audio_path")
            if isinstance(audio_path, str) and dataset_entry["provenance_audio_paths"]:
                normalized_audio = _normalize_path(audio_path)
                candidate_sessions = []
                if ref_session:
                    candidate_sessions.append(ref_session)
                if session_str:
                    candidate_sessions.append(session_str)
                found = False
                for candidate in candidate_sessions:
                    sample_paths = dataset_entry["provenance_audio_paths"].get(candidate)
                    if sample_paths and normalized_audio in sample_paths:
                        found = True
                        break
                if not found and candidate_sessions:
                    dataset_entry["audio_path_missing_from_provenance"].add(
                        f"{candidate_sessions[0]}::{normalized_audio}"
                    )  # type: ignore[index]

            if (
                source_set not in provenance_index.source_sets()
                and not allow_unknown
            ):
                unknown_sources["source_sets"].add(source_set)
                if isinstance(metadata_ref, str):
                    unknown_sources["metadata_refs"].add(metadata_ref)
                if isinstance(audio_path, str):
                    unknown_sources["audio_paths"].add(_normalize_path(audio_path))

    for source_set in provenance_index.source_sets():
        datasets.setdefault(source_set, create_dataset_entry(source_set, provenance_index))

    return datasets, global_issues, unknown_sources, total_events


def materialize_summary(
    datasets: Mapping[str, MutableMapping[str, object]],
    global_issues: Mapping[str, int],
    unknown_sources: MutableMapping[str, Set[str]],
    total_events: int,
) -> Dict[str, object]:
    summary_datasets: Dict[str, object] = {}
    for source_set in sorted(datasets.keys()):
        entry = datasets[source_set]
        provenance_sessions = entry.pop("provenance_sessions", set())  # type: ignore[assignment]
        provenance_audio_paths = entry.pop("provenance_audio_paths", {})  # type: ignore[assignment]
        provenance_file: Optional[Path] = entry.get("provenance_file")  # type: ignore[assignment]
        summary_datasets[source_set] = {
            "event_count": entry["event_count"],
            "unique_sessions": len(entry["unique_sessions"]),
            "missing_provenance_sessions": sorted(entry["missing_provenance_sessions"]),
            "metadata_ref_mismatches": sorted(entry["metadata_ref_mismatches"]),
            "audio_path_missing_from_provenance": sorted(entry["audio_path_missing_from_provenance"]),
            "unreferenced_provenance_sessions": sorted(provenance_sessions - entry["unique_sessions"]),
            "provenance_session_count": len(provenance_sessions),
            "provenance_file": _relativize_path(provenance_file) if provenance_file else None,
        }

    summary = {
        "manifest_path": _relativize_path(None),
        "total_events": total_events,
        "datasets": summary_datasets,
        "global_issues": dict(global_issues),
        "unknown_sources": {
            "event_count": sum(
                summary_datasets[name]["event_count"]
                for name in summary_datasets
                if summary_datasets[name]["provenance_file"] is None
            ),
            "metadata_ref_mismatches": sorted(unknown_sources["metadata_refs"]),
            "audio_path_missing_from_provenance": sorted(unknown_sources["audio_paths"]),
            "source_sets": sorted(unknown_sources["source_sets"]),
        },
    }
    return summary


def _relativize_path(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_json(summary: Mapping[str, object], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def write_markdown(summary: Mapping[str, object], destination: Path) -> None:
    datasets: Mapping[str, Mapping[str, object]] = summary["datasets"]  # type: ignore[assignment]
    lines: List[str] = []
    manifest = summary.get("manifest_path")
    lines.append("# Provenance Audit Summary\n")
    if manifest:
        lines.append(f"* Manifest: `{manifest}`")
    lines.append(f"* Total events: {summary.get('total_events', 0)}\n")

    header = "| Source set | Events | Manifest sessions | Provenance sessions | Missing sessions | Unreferenced sessions |"
    divider = "|---|---:|---:|---:|---:|---:|"
    rows: List[str] = []
    for name in datasets:
        stats = datasets[name]
        rows.append(
            f"| `{name}` | {stats['event_count']:,} | {stats['unique_sessions']:,} | {stats['provenance_session_count']:,} "
            f"| {len(stats['missing_provenance_sessions']):,} | {len(stats['unreferenced_provenance_sessions']):,} |"
        )

    lines.append(header)
    lines.append(divider)
    lines.extend(rows)
    lines.append("\n## Global Issues\n")
    for key, value in summary.get("global_issues", {}).items():
        lines.append(f"- `{key}`: {value}")

    unknown = summary.get("unknown_sources", {})
    if unknown and unknown.get("source_sets"):
        lines.append("\n## Unknown Sources\n")
        lines.append(f"- Source sets: {', '.join(unknown['source_sets'])}")
        lines.append(f"- Events: {unknown.get('event_count', 0)}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines), encoding="utf-8")


def compare_with_baseline(current: Mapping[str, object], baseline_path: Path) -> List[str]:
    if not baseline_path.exists():
        return []
    with baseline_path.open("r", encoding="utf-8") as handle:
        baseline = json.load(handle)

    diffs: List[str] = []
    baseline_datasets: Mapping[str, Mapping[str, object]] = baseline.get("datasets", {})
    current_datasets: Mapping[str, Mapping[str, object]] = current.get("datasets", {})
    dataset_names = set(baseline_datasets.keys()) | set(current_datasets.keys())

    keys_to_compare = [
        "missing_provenance_sessions",
        "metadata_ref_mismatches",
        "audio_path_missing_from_provenance",
        "unreferenced_provenance_sessions",
    ]

    for name in sorted(dataset_names):
        cur = current_datasets.get(name, {})
        base = baseline_datasets.get(name, {})
        for key in keys_to_compare:
            cur_set = set(cur.get(key, []))
            base_set = set(base.get(key, []))
            if cur_set != base_set:
                added = cur_set - base_set
                removed = base_set - cur_set
                message = [f"Dataset '{name}' differs for '{key}'"]
                if added:
                    message.append(f"  + Added: {sorted(added)}")
                if removed:
                    message.append(f"  - Removed: {sorted(removed)}")
                diffs.append("\n".join(message))

    for key in ["missing_source_set", "metadata_ref_missing", "metadata_ref_format_errors"]:
        if current.get("global_issues", {}).get(key) != baseline.get("global_issues", {}).get(key):
            diffs.append(f"Global issue '{key}' changed (baseline {baseline['global_issues'].get(key)}, current {current['global_issues'].get(key)})")

    return diffs


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST, help="Events JSONL manifest to audit")
    parser.add_argument(
        "--provenance-dir",
        type=Path,
        default=_DEFAULT_PROVENANCE_DIR,
        help="Directory containing *_provenance.jsonl files",
    )
    parser.add_argument("--output-json", type=Path, help="Where to write the audit JSON summary")
    parser.add_argument("--output-md", type=Path, help="Where to write a Markdown summary")
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Optional baseline JSON file to compare against. Non-empty diffs trigger a non-zero exit code.",
    )
    parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help="Do not treat events that reference unknown source sets as audit failures",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    manifest_path = args.manifest
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 2

    provenance_dir = args.provenance_dir
    provenance_index = load_provenance(provenance_dir)

    datasets, global_issues, unknown_sources, total_events = audit_manifest(
        manifest_path,
        provenance_index,
        allow_unknown=args.allow_unknown,
    )

    summary = materialize_summary(datasets, global_issues, unknown_sources, total_events)
    summary["manifest_path"] = _relativize_path(manifest_path)

    if args.output_json:
        write_json(summary, args.output_json)
    if args.output_md:
        write_markdown(summary, args.output_md)

    if args.baseline:
        diffs = compare_with_baseline(summary, args.baseline)
        if diffs:
            print("Provenance audit differs from baseline:\n", file=sys.stderr)
            for diff in diffs:
                print(diff, file=sys.stderr)
            return 1

    print(json.dumps({"total_events": total_events, "datasets": len(summary["datasets"]) }))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
