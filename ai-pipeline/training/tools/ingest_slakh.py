#!/usr/bin/env python3
"""Ingest the Slakh2100 dataset into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys
import uuid
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import mido  # type: ignore[import]
import yaml  # type: ignore[import]

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_ROOT = pathlib.Path("data/raw/slakh2100")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/slakh_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/slakh_provenance.jsonl")
DEFAULT_LICENSE_REF = "training/data/licenses/slakh2100.md"

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/slakh2100")
HIHAT_BARK_WINDOW = 0.2

NOTE_MAP: Dict[int, Tuple[str, Dict[str, str]]] = {
    36: ("kick", {}),
    35: ("kick", {"instrument_variant": "sub"}),
    38: ("snare", {}),
    40: ("snare", {"strike_position": "rimshot"}),
    37: ("cross_stick", {}),
    39: ("rimshot", {}),
    48: ("tom_high", {}),
    50: ("tom_high", {}),
    47: ("tom_mid", {}),
    45: ("tom_low", {}),
    43: ("tom_low", {"instrument_variant": "floor"}),
    42: ("hihat_closed", {}),
    44: ("hihat_pedal", {}),
    46: ("hihat_open", {}),
    26: ("hihat_foot_splash", {}),
    51: ("ride_bow", {}),
    53: ("ride_bell", {"strike_position": "bell"}),
    59: ("ride_bell", {"strike_position": "bell"}),
    49: ("crash", {"instrument_variant": "high"}),
    57: ("crash", {"instrument_variant": "low"}),
    55: ("splash", {}),
    52: ("china", {"instrument_variant": "high"}),
    54: ("china", {"instrument_variant": "low"}),
    56: ("aux_percussion", {"instrument_variant": "cowbell", "technique": "cowbell"}),
    58: ("aux_percussion", {"instrument_variant": "vibraslap"})
}

CYMBAL_MULTI_LABELS = {"crash", "splash", "china"}


class EventContext:
    def __init__(self) -> None:
        self.variants: DefaultDict[str, Set[str]] = defaultdict(set)

    def register(self, label: str, token: str) -> None:
        self.variants[label].add(token)

    def has_multiple(self, label: str) -> bool:
        return len(self.variants[label]) > 1


def bucket_velocity(velocity: int) -> str:
    ratio = velocity / 127.0
    if ratio <= 0.25:
        return "ghost"
    if ratio <= 0.5:
        return "light"
    if ratio <= 0.8:
        return "medium"
    return "accent"


def relative_path(base: pathlib.Path, target: Optional[pathlib.Path]) -> Optional[str]:
    if target is None:
        return None
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def load_metadata(path: pathlib.Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def midi_events(
    midi_path: pathlib.Path,
    dataset_root: pathlib.Path,
    session_id: str,
    context: EventContext,
    audio_relative: Optional[str],
    component_metadata: Dict[str, object]
) -> Iterable[dict]:
    midi = mido.MidiFile(midi_path)
    ticks_per_beat = midi.ticks_per_beat or 480
    tempo = 500000
    tempo_bpm = mido.tempo2bpm(tempo)
    meter = "4/4"
    hat_cc = 0.0
    absolute_ticks = 0

    merged = mido.merge_tracks(midi.tracks)

    for message in merged:
        absolute_ticks += message.time
        if message.type == "set_tempo":
            tempo = message.tempo
            tempo_bpm = mido.tempo2bpm(tempo)
            continue
        if message.type == "time_signature":
            meter = f"{message.numerator}/{message.denominator}"
            continue
        if message.type == "control_change" and message.control == 4:
            hat_cc = message.value / 127.0
            continue
        if message.type != "note_on" or message.velocity <= 0:
            continue

        mapped = NOTE_MAP.get(message.note)
        if not mapped:
            continue

        label, extras = mapped
        onset_seconds = mido.tick2second(absolute_ticks, ticks_per_beat, tempo)
        event_id = str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{message.note}:{absolute_ticks}"))

        component: Dict[str, object] = {
            "label": label,
            "velocity": round(message.velocity / 127.0, 4),
            "dynamic_bucket": bucket_velocity(message.velocity)
        }
        component.update(component_metadata)

        strike = extras.get("strike_position")
        if strike:
            component["strike_position"] = strike

        variant = extras.get("instrument_variant")
        if variant:
            component["instrument_variant"] = variant

        if label.startswith("hihat"):
            component["openness"] = round(hat_cc, 4)

        techniques = set()
        if extras.get("technique"):
            techniques.add(extras["technique"])

        if label in CYMBAL_MULTI_LABELS:
            variant_token = extras.get("instrument_variant") or f"note_{message.note}"
            if variant_token and "instrument_variant" not in component:
                component["instrument_variant"] = variant_token
            context.register(label, str(variant_token))
            if context.has_multiple(label):
                techniques.add("multi_cymbal_same_class")

        event = {
            "event_id": event_id,
            "session_id": session_id,
            "source_set": "slakh2100",
            "is_synthetic": True,
            "audio_path": audio_relative,
            "midi_path": relative_path(dataset_root, midi_path),
            "onset_time": round(onset_seconds, 6),
            "offset_time": None,
            "tempo_bpm": round(tempo_bpm, 3),
            "meter": meter,
            "components": [component],
            "techniques": sorted(techniques),
            "context_ms": {"pre": 80, "post": 200},
            "metadata_ref": f"provenance:{session_id}",
            "negative_example": False
        }
        yield event


def build_provenance_record(
    session_id: str,
    dataset_root: pathlib.Path,
    midi_paths: Sequence[pathlib.Path],
    audio_paths: Sequence[pathlib.Path],
    mix_path: Optional[pathlib.Path],
    techniques: Sequence[str],
    license_ref: str,
    ingestion_version: str,
    notes: str
) -> ingest_utils.ProvenanceRecord:
    sample_paths: List[str] = []
    hashes: List[dict] = []

    for path in midi_paths:
        rel = relative_path(dataset_root, path)
        if rel:
            sample_paths.append(rel)
            hashes.append({"path": rel, "sha256": ingest_utils.sha256_file(path)})

    for path in audio_paths:
        rel = relative_path(dataset_root, path)
        if rel:
            sample_paths.append(rel)
            hashes.append({"path": rel, "sha256": ingest_utils.sha256_file(path)})

    if mix_path is not None:
        rel = relative_path(dataset_root, mix_path)
        if rel:
            sample_paths.append(rel)
            hashes.append({"path": rel, "sha256": ingest_utils.sha256_file(mix_path)})

    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    return ingest_utils.ProvenanceRecord(
        source_set="slakh2100",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_slakh.py",
        ingestion_version=ingestion_version,
        processing_chain=["midi_import", "synthetic_render"],
        timestamp_utc=timestamp,
        techniques=techniques,
        notes=notes
    )


def iter_track_dirs(root: pathlib.Path) -> Iterable[Tuple[str, pathlib.Path]]:
    for split_name in ("train", "validation", "test"):
        split_root = root / split_name
        if not split_root.exists():
            continue
        for track_dir in sorted(p for p in split_root.iterdir() if p.is_dir()):
            yield split_name, track_dir


def load_drum_stems(metadata: dict) -> Dict[str, dict]:
    stems = metadata.get("stems", {})
    drum_entries: Dict[str, dict] = {}
    for stem_id, info in stems.items():
        if info.get("is_drum") and info.get("audio_rendered"):
            drum_entries[stem_id] = info
    return drum_entries


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"Slakh2100 root directory (default: {DEFAULT_ROOT})"
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

    track_dirs = list(iter_track_dirs(dataset_root))
    if not track_dirs:
        parser.error(f"No track folders found under {dataset_root}")

    events: List[dict] = []
    provenance_rows: List[str] = []

    for split_name, track_dir in ingest_utils.track_progress(track_dirs, "Slakh2100", total=len(track_dirs)):
        metadata_path = track_dir / "metadata.yaml"
        if not metadata_path.exists():
            continue

        metadata = load_metadata(metadata_path)
        drum_stems = load_drum_stems(metadata)
        if not drum_stems:
            continue

        session_id = f"{split_name}_{track_dir.name}"
        mix_path = track_dir / "mix.flac"

        stem_events: List[dict] = []
        midi_files: List[pathlib.Path] = []
        audio_files: List[pathlib.Path] = []
        stem_notes: List[str] = []

        for stem_id, info in drum_stems.items():
            midi_path = track_dir / "MIDI" / f"{stem_id}.mid"
            audio_path = track_dir / "stems" / f"{stem_id}.flac"
            if not midi_path.exists() or not audio_path.exists():
                continue

            midi_files.append(midi_path)
            audio_files.append(audio_path)

            component_meta: Dict[str, object] = {
                "source_stem": stem_id,
                "instrument_class": info.get("inst_class"),
                "source_plugin": info.get("plugin_name"),
                "integrated_loudness": info.get("integrated_loudness")
            }

            context = EventContext()
            audio_rel = relative_path(dataset_root, audio_path)
            for event in midi_events(midi_path, dataset_root, session_id, context, audio_rel, component_meta):
                stem_events.append(event)

            stem_notes.append(
                f"stem {stem_id}: {info.get('inst_class')} via {info.get('plugin_name')}"
            )

        if not stem_events:
            continue

        ingest_utils.tag_hihat_barks(stem_events, window_seconds=HIHAT_BARK_WINDOW)
        session_taxonomy = ingest_utils.apply_taxonomy_inference(stem_events)

        unified_techniques = set()
        for event in stem_events:
            unified_techniques.update(event.get("techniques", []))
        unified_techniques.update(session_taxonomy)

        if techniques_reference:
            unified_techniques = unified_techniques.intersection(techniques_reference) or unified_techniques

        for event in stem_events:
            updated = set(event.get("techniques", []))
            updated.update(unified_techniques)
            event["techniques"] = sorted(updated)
            events.append(event)

        provenance = build_provenance_record(
            session_id=session_id,
            dataset_root=dataset_root,
            midi_paths=midi_files,
            audio_paths=audio_files,
            mix_path=mix_path if mix_path.exists() else None,
            techniques=sorted(unified_techniques),
            license_ref=args.license_ref,
            ingestion_version=ingestion_version,
            notes="; ".join(stem_notes)
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
        "Slakh2100 ingest complete: "
        f"{len(events)} events from {len(provenance_rows)} sessions across {len(track_dirs)} track folders."
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_slakh.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
