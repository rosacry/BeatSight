#!/usr/bin/env python3
"""Ingest the Extended Groove MIDI Dataset (E-GMD) into BeatSight's unified events schema."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import random
import sys
import uuid
from collections import defaultdict
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import mido  # type: ignore[import]

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/egmd")

DEFAULT_ROOT = pathlib.Path("data/raw/egmd")
DEFAULT_EVENTS_PATH = pathlib.Path("ai-pipeline/training/data/manifests/egmd_events.jsonl")
DEFAULT_PROVENANCE_PATH = pathlib.Path("ai-pipeline/training/data/provenance/egmd_provenance.jsonl")

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


def relative_path(base: pathlib.Path, target: pathlib.Path) -> str:
    try:
        return str(target.relative_to(base))
    except ValueError:
        return str(target)


def collect_audio_path(midi_path: pathlib.Path) -> Optional[pathlib.Path]:
    for ext in (".wav", ".flac", ".ogg", ".mp3"):
        candidate = midi_path.with_suffix(ext)
        if candidate.exists():
            return candidate
    parent = midi_path.parent
    for ext in (".wav", ".flac", ".ogg", ".mp3"):
        for option in parent.glob(f"*{ext}"):
            if option.stem == midi_path.stem:
                return option
    return None


def extract_velocity_layers(track_name: str) -> Optional[str]:
    lower = track_name.lower()
    for keyword in ("soft", "medium", "hard", "accent", "ghost"):
        if keyword in lower:
            return keyword
    return None


def midi_events(
    midi_path: pathlib.Path,
    dataset_root: pathlib.Path,
    session_id: str,
    context: EventContext
) -> Iterable[dict]:
    midi = mido.MidiFile(midi_path)
    ticks_per_beat = midi.ticks_per_beat or 480
    tempo = 500000
    tempo_bpm = mido.tempo2bpm(tempo)
    meter = "4/4"
    hat_cc = 0.0
    absolute_ticks = 0

    audio_candidate = collect_audio_path(midi_path)
    audio_path = relative_path(dataset_root, audio_candidate) if audio_candidate else None

    velocity_layer = None
    for track in midi.tracks:
        if track.name:
            velocity_layer = extract_velocity_layers(track.name)
            if velocity_layer:
                break

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

        strike = extras.get("strike_position")
        if strike:
            component["strike_position"] = strike

        variant = extras.get("instrument_variant")
        if variant:
            component["instrument_variant"] = variant

        if label.startswith("hihat"):
            component["openness"] = round(hat_cc, 4)

        if velocity_layer:
            component["velocity_layer"] = velocity_layer

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
            "source_set": "extended_groove_mididataset",
            "is_synthetic": False,
            "audio_path": audio_path,
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
    midi_path: pathlib.Path,
    audio_path: Optional[pathlib.Path],
    techniques: Sequence[str],
    license_ref: str,
    ingestion_version: str
) -> ingest_utils.ProvenanceRecord:
    rel_midi = relative_path(dataset_root, midi_path)
    sample_paths = [rel_midi]
    hashes = [{"path": rel_midi, "sha256": ingest_utils.sha256_file(midi_path)}]

    if audio_path:
        rel_audio = relative_path(dataset_root, audio_path)
        sample_paths.append(rel_audio)
        hashes.append({"path": rel_audio, "sha256": ingest_utils.sha256_file(audio_path)})

    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
    return ingest_utils.ProvenanceRecord(
        source_set="extended_groove_mididataset",
        session_id=session_id,
        sample_paths=sample_paths,
        hashes=hashes,
        license_ref=license_ref,
        ingestion_script="training/tools/ingest_egmd.py",
        ingestion_version=ingestion_version,
        processing_chain=["midi_import"],
        timestamp_utc=timestamp,
        techniques=techniques,
        notes=""
    )


def iter_midi_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    for path in sorted(root.rglob("*.mid")):
        yield path
    for path in sorted(root.rglob("*.midi")):
        yield path


def apply_file_limits(
    items: Sequence[pathlib.Path],
    max_files: Optional[int],
    seed: Optional[int],
) -> List[pathlib.Path]:
    if not max_files or max_files <= 0 or max_files >= len(items):
        return list(items)
    rng = random.Random(seed)
    return rng.sample(list(items), k=max_files)


def e_session_id(midi_path: pathlib.Path, dataset_root: pathlib.Path) -> str:
    relative = relative_path(dataset_root, midi_path)
    return relative.replace("/", "_").replace("\\", "_").rsplit(".", 1)[0]


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=f"E-GMD root directory (default: {DEFAULT_ROOT})"
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
        default="training/data/licenses/egmd.md",
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
    parser.add_argument(
        "--max-files",
        type=int,
        help="Optional limit on number of MIDI files to ingest (random subset)."
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Seed used when sampling files (default: deterministic order)."
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

    midi_files = list(iter_midi_files(dataset_root))
    if not midi_files:
        parser.error(f"No MIDI files found under {dataset_root}")

    selected_files = apply_file_limits(midi_files, args.max_files, args.random_seed)
    if len(selected_files) != len(midi_files):
        print(f"Limiting E-GMD ingest to {len(selected_files)} of {len(midi_files)} MIDI files.")
    else:
        selected_files = midi_files

    output_events.parent.mkdir(parents=True, exist_ok=True)
    output_provenance.parent.mkdir(parents=True, exist_ok=True)

    event_count = 0
    session_count = 0

    with output_events.open("w", encoding="utf-8") as events_handle, output_provenance.open("w", encoding="utf-8") as provenance_handle:
        for midi_path in ingest_utils.track_progress(selected_files, "E-GMD", total=len(selected_files)):
            session_id = e_session_id(midi_path, dataset_root)
            session_context = EventContext()
            events_for_session = list(midi_events(midi_path, dataset_root, session_id, session_context))
            if not events_for_session:
                continue

            session_count += 1

            session_taxonomy = ingest_utils.apply_taxonomy_inference(events_for_session)

            unified_techniques = set()
            for event in events_for_session:
                unified_techniques.update(event.get("techniques", []))
            unified_techniques.update(session_taxonomy)
            if techniques_reference:
                unified_techniques = unified_techniques.intersection(techniques_reference) or unified_techniques

            audio_candidate = collect_audio_path(midi_path)
            provenance = build_provenance_record(
                session_id=session_id,
                dataset_root=dataset_root,
                midi_path=midi_path,
                audio_path=audio_candidate,
                techniques=sorted(unified_techniques),
                license_ref=args.license_ref,
                ingestion_version=ingestion_version
            )

            for event in events_for_session:
                updated = set(event.get("techniques", []))
                updated.update(unified_techniques)
                event["techniques"] = sorted(updated)
                if audio_candidate and not event.get("audio_path"):
                    event["audio_path"] = relative_path(dataset_root, audio_candidate)
                events_handle.write(json.dumps(event, separators=(",", ":")) + "\n")
                event_count += 1

            provenance_handle.write(provenance.to_json() + "\n")

    if event_count == 0:
        output_events.unlink(missing_ok=True)
        output_provenance.unlink(missing_ok=True)
        raise SystemExit("No events were generated; check the dataset root")

    print(
        "E-GMD ingest complete: "
        f"{event_count} events from {session_count} sessions across {len(selected_files)} MIDI files."
    )
    print(f"Events written to {output_events}")
    print(f"Provenance written to {output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_egmd.py",
        events_path=output_events,
        manifest_path=output_events,
    )


if __name__ == "__main__":
    main()
