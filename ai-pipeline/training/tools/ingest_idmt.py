#!/usr/bin/env python3
"""Ingest the IDMT-SMT-Drums V2 collection into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_ROOT = pathlib.Path("data/raw/idmt_smt_drums_v2")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/idmt_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/idmt_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/idmt_smt_drums_v2.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/idmt-smt-drums-v2")

INSTRUMENT_MAP: Dict[str, Tuple[str, Dict[str, str]]] = {
    "HH": ("hihat_closed", {}),
    "KD": ("kick", {}),
    "SD": ("snare", {})
}


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def parse_svl(path: pathlib.Path) -> Tuple[float, List[float]]:
    tree = ET.parse(path)
    root = tree.getroot()
    model = root.find(".//model")
    if model is None:
        raise ValueError(f"No <model> entry in {path}")
    sample_rate = float(model.get("sampleRate", "44100"))
    dataset = root.find(".//dataset")
    if dataset is None:
        raise ValueError(f"No <dataset> entry in {path}")
    onsets: List[float] = []
    for point in dataset.findall("point"):
        frame_str = point.get("frame")
        if frame_str is None:
            continue
        onsets.append(float(frame_str) / sample_rate)
    return sample_rate, onsets


def find_audio_path(audio_root: pathlib.Path, base: str, channel: str) -> Optional[pathlib.Path]:
    preferred = audio_root / f"{base}#{channel}#train.wav"
    if preferred.exists():
        return preferred
    fallback = audio_root / f"{base}#{channel}.wav"
    if fallback.exists():
        return fallback
    return None


def build_event(
    session_id: str,
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    onset: float,
    label: str,
    extras: Dict[str, str],
    kit_family: str,
    channel: str
) -> dict:
    event_id = str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{onset:.6f}:{channel}"))

    component = {
        "label": label,
        "velocity": None,
        "dynamic_bucket": "unknown",
        "kit_family": kit_family,
        "channel": channel
    }
    if extras:
        component.update(extras)

    return {
        "event_id": event_id,
        "session_id": session_id,
        "source_set": "idmt_smt_drums_v2",
        "is_synthetic": False,
        "audio_path": relative_path(dataset_root, audio_path),
        "midi_path": None,
        "onset_time": round(onset, 6),
        "offset_time": None,
        "tempo_bpm": None,
        "meter": None,
        "components": [component],
        "techniques": [],
        "context_ms": {"pre": 40, "post": 120},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False
    }


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    mix_path: Optional[pathlib.Path],
    license_ref: str,
    ingestion_version: str,
    notes: str
) -> ingest_utils.ProvenanceRecord:
    sample_paths = [relative_path(dataset_root, audio_path)]
    hashes = [{"path": sample_paths[0], "sha256": ingest_utils.sha256_file(audio_path)}]
    if mix_path is not None and mix_path.exists():
        mix_rel = relative_path(dataset_root, mix_path)
        sample_paths.append(mix_rel)
        hashes.append({"path": mix_rel, "sha256": ingest_utils.sha256_file(mix_path)})

    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    return ingest_utils.ProvenanceRecord(
        source_set="idmt_smt_drums_v2",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_idmt.py",
        ingestion_version=ingestion_version,
        processing_chain=["audio_annotation"],
        timestamp_utc=timestamp,
        techniques=[],
        notes=notes
    )


def iter_annotation_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    ann_root = root / "annotation_svl"
    return sorted(p for p in ann_root.glob("*.svl") if p.is_file())


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"IDMT-SMT-Drums V2 root directory (default: {DEFAULT_ROOT})"
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

    audio_root = dataset_root / "audio"
    if not audio_root.exists():
        parser.error(f"audio directory missing under {dataset_root}")

    output_events = ingest_utils.resolve_repo_path(args.output_events)
    output_provenance = ingest_utils.resolve_repo_path(args.output_provenance)
    ingestion_version = args.ingestion_version or ingest_utils.git_rev_parse_head()

    ann_files = list(iter_annotation_files(dataset_root))
    if not ann_files:
        parser.error(f"No annotation files found under {dataset_root}")

    events: List[dict] = []
    provenance_rows: List[str] = []

    for ann_path in ingest_utils.track_progress(ann_files, "IDMT-SMT", total=len(ann_files)):
        stem = ann_path.stem
        if "#" not in stem:
            continue
        base, channel = stem.split("#", 1)
        mapping = INSTRUMENT_MAP.get(channel)
        if not mapping:
            continue

        audio_path = find_audio_path(audio_root, base, channel)
        if audio_path is None:
            continue

        mix_path = audio_root / f"{base}#MIX.wav"
        kit_family = base.split("_", 1)[0]
        notes = f"kit_family={kit_family}"
        session_id = f"{base}_{channel}"

        try:
            _, onsets = parse_svl(ann_path)
        except ValueError:
            continue

        label, extras = mapping
        session_events: List[dict] = []
        for onset in onsets:
            session_events.append(
                build_event(session_id, dataset_root, audio_path, onset, label, extras, kit_family, channel)
            )

        if not session_events:
            continue

        ingest_utils.apply_taxonomy_inference(session_events)

        events.extend(session_events)
        provenance = build_provenance_record(
            session_id=session_id,
            dataset_root=dataset_root,
            audio_path=audio_path,
            mix_path=mix_path if mix_path.exists() else None,
            license_ref=args.license_ref,
            ingestion_version=ingestion_version,
            notes=notes
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
        "IDMT-SMT ingest complete: "
        f"{len(events)} events from {len(provenance_rows)} instrument tracks across {len(ann_files)} annotations."
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_idmt.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
