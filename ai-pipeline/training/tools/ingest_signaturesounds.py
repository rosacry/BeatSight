#!/usr/bin/env python3
"""Ingest SignatureSounds percussion packs into BeatSight's unified events schema."""

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

DEFAULT_ROOT = pathlib.Path("data/raw/signaturesounds")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/signaturesounds_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/signaturesounds_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/signaturesounds.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/signaturesounds")
AUDIO_SUFFIXES = {".wav", ".flac", ".aif", ".aiff", ".ogg"}
KEYWORD_PATTERNS: List[Tuple[str, re.Pattern[str], Dict[str, str]]] = [
    ("kick", re.compile(r"kick", re.IGNORECASE), {}),
    ("snare", re.compile(r"snare", re.IGNORECASE), {}),
    ("hihat_closed", re.compile(r"hi[-_ ]?hat|hh", re.IGNORECASE), {}),
    ("crash", re.compile(r"crash", re.IGNORECASE), {}),
    ("splash", re.compile(r"splash", re.IGNORECASE), {}),
    ("china", re.compile(r"china", re.IGNORECASE), {}),
    ("tom_low", re.compile(r"floor|low[-_ ]?tom", re.IGNORECASE), {"instrument_variant": "floor"}),
    ("tom_mid", re.compile(r"tom", re.IGNORECASE), {}),
    ("aux_percussion", re.compile(r"cowbell", re.IGNORECASE), {"instrument_variant": "cowbell"}),
    ("aux_percussion", re.compile(r"shaker", re.IGNORECASE), {"instrument_variant": "shaker"}),
    ("aux_percussion", re.compile(r"tamb", re.IGNORECASE), {"instrument_variant": "tambourine"}),
    ("aux_percussion", re.compile(r"clap", re.IGNORECASE), {"instrument_variant": "clap"}),
    ("aux_percussion", re.compile(r"perc", re.IGNORECASE), {"instrument_variant": "percussion"})
]


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def duration_seconds(path: pathlib.Path) -> float:
    with soundfile.SoundFile(path) as handle:
        return handle.frames / float(handle.samplerate)


def classify(label_source: str) -> Optional[Tuple[str, Dict[str, str]]]:
    for label, pattern, extras in KEYWORD_PATTERNS:
        if pattern.search(label_source):
            return label, extras
    return None


def iter_audio_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for audio_path in root.rglob("*"):
        if audio_path.is_file() and audio_path.suffix.lower() in AUDIO_SUFFIXES:
            yield audio_path


def build_event(
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    label: str,
    extras: Dict[str, str],
    duration: float
) -> dict:
    rel_audio = relative_path(dataset_root, audio_path)
    rel_no_ext = audio_path.relative_to(dataset_root).with_suffix("")
    sanitized = str(rel_no_ext).replace("/", "_").replace("\\", "_")
    session_id = f"signaturesounds_{sanitized}"
    event_id = str(uuid.uuid5(EVENT_NAMESPACE, session_id))

    component = {
        "label": label,
        "velocity": None,
        "dynamic_bucket": "unknown",
        "duration_seconds": round(duration, 6)
    }
    if extras:
        component.update(extras)

    return {
        "event_id": event_id,
        "session_id": session_id,
        "source_set": "signaturesounds",
        "is_synthetic": False,
        "audio_path": rel_audio,
        "midi_path": None,
        "onset_time": 0.0,
        "offset_time": round(duration, 6),
        "tempo_bpm": None,
        "meter": None,
        "components": [component],
        "techniques": ["sampled_one_shot"],
        "context_ms": {"pre": 0, "post": 0},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False
    }


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    license_ref: str,
    ingestion_version: str
) -> ingest_utils.ProvenanceRecord:
    rel_audio = relative_path(dataset_root, audio_path)
    sample_paths = [rel_audio]
    hashes = [{"path": rel_audio, "sha256": ingest_utils.sha256_file(audio_path)}]
    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    notes = str(audio_path.parent.relative_to(dataset_root))
    return ingest_utils.ProvenanceRecord(
        source_set="signaturesounds",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_signaturesounds.py",
        ingestion_version=ingestion_version,
        processing_chain=["sample_pack"],
        timestamp_utc=timestamp,
        techniques=["sampled_one_shot"],
        notes=notes
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"SignatureSounds root directory (default: {DEFAULT_ROOT})"
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

    for audio_path in ingest_utils.track_progress(audio_files, "SignatureSounds", total=len(audio_files)):
        classification = classify(str(audio_path))
        if not classification:
            continue
        try:
            duration = duration_seconds(audio_path)
        except RuntimeError:
            continue
        label, extras = classification
        event = build_event(dataset_root, audio_path, label, extras, duration)
        ingest_utils.apply_taxonomy_inference([event])
        events.append(event)
        provenance = build_provenance_record(
            session_id=event["session_id"],
            dataset_root=dataset_root,
            audio_path=audio_path,
            license_ref=args.license_ref,
            ingestion_version=ingestion_version
        )
        provenance_rows.append(provenance.to_json())

    if not events:
        raise SystemExit("No events were generated; refine keyword mappings or check dataset")

    output_events.parent.mkdir(parents=True, exist_ok=True)
    with output_events.open("w", encoding="utf-8") as handle:
        for row in events:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")

    output_provenance.parent.mkdir(parents=True, exist_ok=True)
    with output_provenance.open("w", encoding="utf-8") as handle:
        for row in provenance_rows:
            handle.write(row + "\n")

    print(
        "SignatureSounds ingest complete: "
        f"{len(events)} events captured across {len(audio_files)} audio files."  # noqa: E501
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_signaturesounds.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
