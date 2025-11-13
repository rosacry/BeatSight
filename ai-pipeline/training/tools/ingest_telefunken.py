#!/usr/bin/env python3
"""Ingest Telefunken multitrack sessions into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
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

DEFAULT_ROOT = pathlib.Path("data/raw/telefunken")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/telefunken_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/telefunken_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/telefunken.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/telefunken")
AUDIO_SUFFIXES = {".wav", ".flac", ".aif", ".aiff", ".ogg"}
KEYWORD_RE = {
    "kick": re.compile(r"kick|bd|bass[-_ ]?drum", re.IGNORECASE),
    "snare": re.compile(r"snare|sd", re.IGNORECASE),
    "hihat": re.compile(r"hi[-_ ]?hat|hh", re.IGNORECASE),
    "ride": re.compile(r"ride", re.IGNORECASE),
    "china": re.compile(r"china", re.IGNORECASE),
    "splash": re.compile(r"splash", re.IGNORECASE),
    "crash": re.compile(r"crash", re.IGNORECASE),
    "floor_tom": re.compile(r"floor|ftom", re.IGNORECASE),
    "rack_tom": re.compile(r"rack|rtom|tom", re.IGNORECASE),
    "cowbell": re.compile(r"cowbell", re.IGNORECASE),
    "perc": re.compile(r"perc|shaker|tamb|clap", re.IGNORECASE)
}


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def duration_seconds(path: pathlib.Path) -> float:
    with soundfile.SoundFile(path) as handle:
        return handle.frames / float(handle.samplerate)


def classify_label(name: str) -> Optional[Tuple[str, Dict[str, str]]]:
    lower = name.lower()
    if KEYWORD_RE["kick"].search(lower):
        variant = "sub" if "sub" in lower else None
        extras: Dict[str, str] = {"instrument_variant": variant} if variant else {}
        return "kick", extras
    if KEYWORD_RE["snare"].search(lower):
        if "rim" in lower:
            return "snare", {"strike_position": "rimshot"}
        return "snare", {}
    if KEYWORD_RE["hihat"].search(lower):
        if "open" in lower:
            return "hihat_open", {}
        if "pedal" in lower or "foot" in lower:
            return "hihat_pedal", {}
        return "hihat_closed", {}
    if KEYWORD_RE["ride"].search(lower):
        if "bell" in lower:
            return "ride_bell", {"strike_position": "bell"}
        return "ride_bow", {}
    if KEYWORD_RE["china"].search(lower):
        return "china", {}
    if KEYWORD_RE["splash"].search(lower):
        return "splash", {}
    if KEYWORD_RE["crash"].search(lower):
        variant = "low" if "low" in lower else "high" if "high" in lower else None
        extras = {"instrument_variant": variant} if variant else {}
        return "crash", extras
    if KEYWORD_RE["floor_tom"].search(lower):
        return "tom_low", {"instrument_variant": "floor"}
    if KEYWORD_RE["rack_tom"].search(lower):
        return "tom_mid", {}
    if KEYWORD_RE["cowbell"].search(lower):
        return "aux_percussion", {"instrument_variant": "cowbell"}
    if KEYWORD_RE["perc"].search(lower):
        return "aux_percussion", {"instrument_variant": "percussion"}
    return None


def iter_audio_files(root: pathlib.Path) -> Iterable[Tuple[pathlib.Path, pathlib.Path]]:
    for session_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if session_dir.name.startswith("__"):
            continue
        for audio_path in session_dir.rglob("*"):
            if audio_path.is_file() and audio_path.suffix.lower() in AUDIO_SUFFIXES:
                if "__MACOSX" in audio_path.parts:
                    continue
                yield session_dir, audio_path


def build_event(
    dataset_root: pathlib.Path,
    session_dir: pathlib.Path,
    audio_path: pathlib.Path,
    label: str,
    extras: Dict[str, str],
    duration: float
) -> dict:
    rel_audio = relative_path(dataset_root, audio_path)
    rel_session_path = audio_path.relative_to(session_dir).with_suffix("")
    sanitized = str(rel_session_path).replace("/", "_").replace("\\", "_")
    session_id = f"telefunken_{session_dir.name}_{sanitized}"
    event_id = str(uuid.uuid5(EVENT_NAMESPACE, session_id))

    component = {
        "label": label,
        "velocity": None,
        "dynamic_bucket": "unknown",
        "duration_seconds": round(duration, 6)
    }
    if extras:
        component.update(extras)

    techniques = ["live_multitrack", "telefunken_session"]

    return {
        "event_id": event_id,
        "session_id": session_id,
        "source_set": "telefunken_sessions",
        "is_synthetic": False,
        "audio_path": rel_audio,
        "midi_path": None,
        "onset_time": 0.0,
        "offset_time": round(duration, 6),
        "tempo_bpm": None,
        "meter": None,
        "components": [component],
        "techniques": techniques,
        "context_ms": {"pre": 0, "post": 0},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False,
        "session_name": session_dir.name
    }


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    session_dir: pathlib.Path,
    audio_path: pathlib.Path,
    license_ref: str,
    ingestion_version: str
) -> ingest_utils.ProvenanceRecord:
    rel_audio = relative_path(dataset_root, audio_path)
    sample_paths = [rel_audio]
    hashes = [{"path": rel_audio, "sha256": ingest_utils.sha256_file(audio_path)}]
    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    notes = f"session={session_dir.name}"
    return ingest_utils.ProvenanceRecord(
        source_set="telefunken_sessions",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_telefunken.py",
        ingestion_version=ingestion_version,
        processing_chain=["multitrack_capture"],
        timestamp_utc=timestamp,
        techniques=["live_multitrack"],
        notes=notes
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"Telefunken sessions root directory (default: {DEFAULT_ROOT})"
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
    args = parser.parse_args(argv)

    dataset_root = ingest_utils.resolve_repo_path(args.root)
    if not dataset_root.exists():
        parser.error(f"dataset root does not exist: {dataset_root}")

    output_events = ingest_utils.resolve_repo_path(args.output_events)
    output_provenance = ingest_utils.resolve_repo_path(args.output_provenance)
    ingestion_version = args.ingestion_version or ingest_utils.git_rev_parse_head()

    audio_files = list(iter_audio_files(dataset_root))
    if not audio_files:
        parser.error(f"No audio files found under {dataset_root}")

    events: List[dict] = []
    provenance_rows: List[str] = []

    for session_dir, audio_path in ingest_utils.track_progress(audio_files, "Telefunken", total=len(audio_files)):
        classification = classify_label(audio_path.name)
        if not classification:
            continue

        try:
            duration = duration_seconds(audio_path)
        except RuntimeError:
            continue

        label, extras = classification
        event = build_event(dataset_root, session_dir, audio_path, label, extras, duration)
        ingest_utils.apply_taxonomy_inference([event])
        events.append(event)
        provenance = build_provenance_record(
            session_id=event["session_id"],
            dataset_root=dataset_root,
            session_dir=session_dir,
            audio_path=audio_path,
            license_ref=args.license_ref,
            ingestion_version=ingestion_version
        )
        provenance_rows.append(provenance.to_json())

    if not events:
        raise SystemExit("No events were generated; refine classification rules or check dataset")

    output_events.parent.mkdir(parents=True, exist_ok=True)
    with output_events.open("w", encoding="utf-8") as handle:
        for row in events:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    output_provenance.parent.mkdir(parents=True, exist_ok=True)
    with output_provenance.open("w", encoding="utf-8") as handle:
        for row in provenance_rows:
            handle.write(row + "\n")

    print(
        "Telefunken ingest complete: "
        f"{len(events)} events captured across {len(audio_files)} audio files."  # noqa: E501
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_telefunken.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
