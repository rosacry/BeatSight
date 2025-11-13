#!/usr/bin/env python3
"""Ingest the ENST-Drums corpus into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys
import uuid
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_ROOT = pathlib.Path("data/raw/ENST-Drums")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/enst_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/enst_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/enst_drums.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/enst-drums")

TOKEN_MAP: Dict[str, Tuple[str, Dict[str, str]]] = {
    "bd": ("kick", {}),
    "sd": ("snare", {}),
    "sd-": ("snare", {"instrument_variant": "snares_off"}),
    "rs": ("snare", {"strike_position": "rimshot"}),
    "cs": ("cross_stick", {}),
    "mt": ("tom_mid", {}),
    "mtr": ("tom_mid", {"strike_position": "rimshot"}),
    "lt": ("tom_low", {}),
    "ltr": ("tom_low", {"strike_position": "rimshot"}),
    "lmt": ("tom_low", {"instrument_variant": "mid_floor"}),
    "lft": ("tom_low", {"instrument_variant": "floor"}),
    "chh": ("hihat_closed", {}),
    "ohh": ("hihat_open", {}),
    "ch1": ("china", {"instrument_variant": "china_low"}),
    "ch5": ("china", {"instrument_variant": "china_high"}),
    "c1": ("crash", {"instrument_variant": "crash_primary"}),
    "cr1": ("crash", {"instrument_variant": "crash_primary"}),
    "cr2": ("crash", {"instrument_variant": "crash_secondary"}),
    "cr5": ("crash", {"instrument_variant": "crash_tertiary"}),
    "c4": ("ride_bow", {"instrument_variant": "ride_alt"}),
    "rc2": ("ride_bow", {}),
    "rc3": ("ride_bell", {"strike_position": "bell"}),
    "rc4": ("ride_bow", {"instrument_variant": "ride_edge"}),
    "cb": ("aux_percussion", {"instrument_variant": "cowbell", "technique": "cowbell"}),
    "spl2": ("splash", {}),
    "sticks": ("aux_percussion", {"instrument_variant": "stick_click", "technique": "stick_click"}),
    "sweep": ("snare", {"technique": "brush_sweep"})
}

CYMBAL_MULTI_LABELS = {"crash", "splash", "china"}
IMPLEMENT_TECHNIQUES = {
    "sticks": "implement_sticks",
    "brushes": "implement_brushes",
    "mallets": "implement_mallets",
    "rods": "implement_rods",
    "hands": "implement_hands",
    "pedal": "implement_pedal"
}
X_COUNT_RE = re.compile(r"x\d+$")


class EventContext:
    def __init__(self) -> None:
        self.variants: DefaultDict[str, Set[str]] = defaultdict(set)

    def register(self, label: str, token: str) -> None:
        self.variants[label].add(token)

    def has_multiple(self, label: str) -> bool:
        return len(self.variants[label]) > 1


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def parse_annotation(path: pathlib.Path) -> Iterable[Tuple[float, str]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) != 2:
                continue
            try:
                onset = float(parts[0])
            except ValueError:
                continue
            yield onset, parts[1]


def extract_playing_style(stem_name: str) -> Optional[str]:
    tokens = stem_name.split("_")
    if not tokens:
        return None
    candidate = tokens[-1]
    if X_COUNT_RE.match(candidate) and len(tokens) >= 2:
        candidate = tokens[-2]
    return candidate if candidate in IMPLEMENT_TECHNIQUES else None


def build_event(
    session_id: str,
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    onset: float,
    token: str,
    context: EventContext,
    playing_style: Optional[str]
) -> Optional[dict]:
    mapping = TOKEN_MAP.get(token)
    if not mapping:
        return None

    label, extras = mapping
    event_id = str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{onset:.6f}:{token}"))

    component: Dict[str, object] = {
        "label": label,
        "velocity": None,
        "dynamic_bucket": "unknown"
    }

    strike = extras.get("strike_position")
    if strike:
        component["strike_position"] = strike

    variant = extras.get("instrument_variant")
    if variant:
        component["instrument_variant"] = variant

    techniques = set()
    extra_tech = extras.get("technique")
    if extra_tech:
        techniques.add(extra_tech)

    if playing_style:
        mapped = IMPLEMENT_TECHNIQUES.get(playing_style)
        if mapped:
            techniques.add(mapped)

    if label in CYMBAL_MULTI_LABELS:
        variant_token = variant or token
        if variant_token and "instrument_variant" not in component:
            component["instrument_variant"] = variant_token
        context.register(label, variant_token)
        if context.has_multiple(label):
            techniques.add("multi_cymbal_same_class")

    techniques_sorted = sorted(techniques)

    return {
        "event_id": event_id,
        "session_id": session_id,
        "source_set": "enst_drums",
        "is_synthetic": False,
        "audio_path": relative_path(dataset_root, audio_path),
        "midi_path": None,
        "onset_time": round(onset, 6),
        "offset_time": None,
        "tempo_bpm": None,
        "meter": None,
        "components": [component],
        "techniques": techniques_sorted,
        "context_ms": {"pre": 60, "post": 120},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False
    }


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    audio_path: pathlib.Path,
    techniques: Sequence[str],
    license_ref: str,
    ingestion_version: str,
    notes: str
) -> ingest_utils.ProvenanceRecord:
    rel_audio = relative_path(dataset_root, audio_path)
    sample_paths = [rel_audio]
    hashes = [{"path": rel_audio, "sha256": ingest_utils.sha256_file(audio_path)}]
    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    return ingest_utils.ProvenanceRecord(
        source_set="enst_drums",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_enst.py",
        ingestion_version=ingestion_version,
        processing_chain=["audio_annotation"],
        timestamp_utc=timestamp,
        techniques=techniques,
        notes=notes
    )


def iter_annotation_pairs(root: pathlib.Path) -> Iterable[Tuple[str, pathlib.Path, pathlib.Path]]:
    for drummer_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        ann_root = drummer_dir / "annotation"
        audio_root = drummer_dir / "audio" / "dry_mix"
        if not ann_root.exists() or not audio_root.exists():
            continue
        for ann_file in sorted(ann_root.glob("*.txt")):
            audio_file = audio_root / ann_file.name.replace(".txt", ".wav")
            if audio_file.exists():
                session_id = f"{drummer_dir.name}_{ann_file.stem}"
                yield session_id, ann_file, audio_file


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"ENST-Drums root directory (default: {DEFAULT_ROOT})"
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
        "--techniques-file",
        default=ingest_utils.DEFAULT_TECHNIQUES_PATH,
        help="Path to additional techniques reference"
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
    techniques_path = ingest_utils.resolve_repo_path(args.techniques_file)
    techniques_reference = set(ingest_utils.load_techniques(techniques_path))
    ingestion_version = args.ingestion_version or ingest_utils.git_rev_parse_head()

    annotation_pairs = list(iter_annotation_pairs(dataset_root))
    if not annotation_pairs:
        parser.error(f"No annotated sessions found under {dataset_root}")

    events: List[dict] = []
    provenance_rows: List[str] = []

    for session_id, ann_path, audio_path in ingest_utils.track_progress(
        annotation_pairs, "ENST-Drums", total=len(annotation_pairs)
    ):
        context = EventContext()
        stem_name = ann_path.stem
        playing_style = extract_playing_style(stem_name)
        notes = f"playing_style={playing_style}" if playing_style else ""

        session_events: List[dict] = []
        for onset, token in parse_annotation(ann_path):
            event = build_event(session_id, dataset_root, audio_path, onset, token, context, playing_style)
            if event:
                session_events.append(event)

        if not session_events:
            continue

        session_taxonomy = ingest_utils.apply_taxonomy_inference(session_events)

        unified_techniques = set()
        for event in session_events:
            unified_techniques.update(event.get("techniques", []))
        unified_techniques.update(session_taxonomy)

        if techniques_reference:
            unified_techniques = unified_techniques.intersection(techniques_reference) or unified_techniques

        for event in session_events:
            updated = set(event.get("techniques", []))
            updated.update(unified_techniques)
            event["techniques"] = sorted(updated)
            events.append(event)

        provenance = build_provenance_record(
            session_id=session_id,
            dataset_root=dataset_root,
            audio_path=audio_path,
            techniques=sorted(unified_techniques),
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
        "ENST-Drums ingest complete: "
        f"{len(events)} events from {len(provenance_rows)} sessions across {len(annotation_pairs)} annotations."
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_enst.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
