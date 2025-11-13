#!/usr/bin/env python3
"""Ingest MUSDB18 (HQ) drum stems into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import random
import sys
import uuid
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import soundfile  # type: ignore[import]

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_HQ_ROOT = pathlib.Path("data/raw/musdb18_hq")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/musdb_hq_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/musdb_hq_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/musdb18.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/musdb18_hq")
STEMS_EXPECTED = ("drums.wav", "bass.wav", "other.wav", "vocals.wav", "mixture.wav")


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def duration_seconds(path: pathlib.Path) -> float:
    with soundfile.SoundFile(path) as handle:
        return handle.frames / float(handle.samplerate)


def iter_track_dirs(root: pathlib.Path) -> Iterable[Tuple[str, pathlib.Path]]:
    for split in ("train", "test"):
        split_root = root / split
        if not split_root.exists():
            continue
        for track_dir in sorted(p for p in split_root.iterdir() if p.is_dir()):
            yield split, track_dir


def apply_track_limits(
    items: Sequence[Tuple[str, pathlib.Path]],
    max_tracks: Optional[int],
    seed: Optional[int],
) -> Sequence[Tuple[str, pathlib.Path]]:
    if not max_tracks or max_tracks <= 0 or max_tracks >= len(items):
        return list(items)
    rng = random.Random(seed)
    return rng.sample(list(items), k=max_tracks)


def gather_stems(track_dir: pathlib.Path) -> Dict[str, pathlib.Path]:
    stems: Dict[str, pathlib.Path] = {}
    for stem_name in STEMS_EXPECTED:
        path = track_dir / stem_name
        if path.exists():
            stems[stem_name] = path
    return stems

def build_event(
    session_id: str,
    dataset_root: pathlib.Path,
    drums_path: pathlib.Path,
    stems: Dict[str, pathlib.Path],
    duration: float
) -> dict:
    component = {
        "label": "drum_mix",
        "velocity": None,
        "dynamic_bucket": "unknown",
        "duration_seconds": round(duration, 6)
    }
    available = sorted(stems.keys())
    return {
        "event_id": str(uuid.uuid5(EVENT_NAMESPACE, session_id)),
        "session_id": session_id,
        "source_set": "musdb18_hq",
        "is_synthetic": False,
        "audio_path": relative_path(dataset_root, drums_path),
        "midi_path": None,
        "onset_time": 0.0,
        "offset_time": round(duration, 6),
        "tempo_bpm": None,
        "meter": None,
        "components": [component],
        "techniques": ["multitrack_context"],
        "context_ms": {"pre": 0, "post": 0},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False,
        "available_stems": available
    }


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    stems: Dict[str, pathlib.Path],
    license_ref: str,
    ingestion_version: str
) -> ingest_utils.ProvenanceRecord:
    sample_paths: List[str] = []
    hashes: List[dict] = []
    for name, path in stems.items():
        rel = relative_path(dataset_root, path)
        sample_paths.append(rel)
        hashes.append({"path": rel, "sha256": ingest_utils.sha256_file(path)})

    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    notes = ", ".join(sorted(stems.keys()))
    return ingest_utils.ProvenanceRecord(
        source_set="musdb18_hq",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_musdb.py",
        ingestion_version=ingestion_version,
        processing_chain=["multitrack_stems"],
        timestamp_utc=timestamp,
        techniques=["multitrack_context"],
        notes=f"stems={notes}"
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hq-root",
        default=str(DEFAULT_HQ_ROOT),
        help=f"MUSDB18 HQ root directory (default: {DEFAULT_HQ_ROOT})"
    )
    parser.add_argument(
        "--output-events",
        default=str(DEFAULT_EVENTS_PATH),
        help=f"Path for events JSONL (default: {DEFAULT_EVENTS_PATH})"
    )
    parser.add_argument(
        "--output-provenance",
        default=str(DEFAULT_PROVENANCE_PATH),
        help=f"Path for provenance JSONL (default: {DEFAULT_PROVENANCE_PATH})"
    )
    parser.add_argument(
        "--license-ref",
        default=DEFAULT_LICENSE_REF,
        help="Relative path to the dataset license summary"
    )
    parser.add_argument(
        "--ingestion-version",
        default=None,
        help="Version tag or git commit hash (default: current git HEAD)"
    )
    parser.add_argument(
        "--max-tracks",
        type=int,
        help="Optional limit on number of tracks to ingest (random subset)."
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Seed used when sampling tracks (default: deterministic order)."
    )
    args = parser.parse_args(argv)

    dataset_root = ingest_utils.resolve_repo_path(args.hq_root)
    if not dataset_root.exists():
        parser.error(f"dataset root does not exist: {dataset_root}")

    output_events = ingest_utils.resolve_repo_path(args.output_events)
    output_provenance = ingest_utils.resolve_repo_path(args.output_provenance)
    ingestion_version = args.ingestion_version or ingest_utils.git_rev_parse_head()

    track_dirs = list(iter_track_dirs(dataset_root))
    if not track_dirs:
        parser.error(f"No track folders found under {dataset_root}")

    selected_dirs = apply_track_limits(track_dirs, args.max_tracks, args.random_seed)
    if len(selected_dirs) != len(track_dirs):
        print(f"Limiting MUSDB18 HQ ingest to {len(selected_dirs)} of {len(track_dirs)} tracks.")
    else:
        selected_dirs = track_dirs

    events: List[dict] = []
    provenance_rows: List[str] = []

    for split, track_dir in ingest_utils.track_progress(selected_dirs, "MUSDB18 HQ", total=len(selected_dirs)):
        stems = gather_stems(track_dir)
        drums_path = stems.get("drums.wav")
        if not drums_path:
            continue

        duration = duration_seconds(drums_path)
        session_id = f"musdb18_hq_{split}_{track_dir.name}"
        events.append(build_event(session_id, dataset_root, drums_path, stems, duration))
        provenance = build_provenance_record(
            session_id=session_id,
            dataset_root=dataset_root,
            stems=stems,
            license_ref=args.license_ref,
            ingestion_version=ingestion_version
        )
        provenance_rows.append(provenance.to_json())

    if not events:
        raise SystemExit("No events were generated; check the dataset root")

    output_events.parent.mkdir(parents=True, exist_ok=True)
    with output_events.open("w", encoding="utf-8") as handle:
        for row in events:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    output_provenance.parent.mkdir(parents=True, exist_ok=True)
    with output_provenance.open("w", encoding="utf-8") as handle:
        for row in provenance_rows:
            handle.write(row + "\n")

    print(
        "MUSDB18 HQ ingest complete: "
    f"{len(events)} events from {len(provenance_rows)} tracks across {len(selected_dirs)} folders."
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_musdb.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
