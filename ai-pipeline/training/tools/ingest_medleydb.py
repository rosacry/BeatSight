#!/usr/bin/env python3
"""Ingest MedleyDB stems into BeatSight manifests and provenance logs."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys
import uuid
import wave
import yaml
from typing import Dict, List, Optional, Set, Tuple, Sequence

try:
    import soundfile as _sf
except ImportError:
    _sf = None

if __package__:
    from . import ingest_utils
else:
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_ROOT_CANDIDATES = (
    "data/raw/MedleyDB",
    "E:/data/raw/MedleyDB",
    "/mnt/e/data/raw/MedleyDB",
)
DEFAULT_EVENTS_OUTPUT = pathlib.Path("ai-pipeline/training/data/manifests/medleydb_events.jsonl")
DEFAULT_PROVENANCE_OUTPUT = pathlib.Path("ai-pipeline/training/data/provenance/medleydb_provenance.jsonl")
DEFAULT_LICENSE_REF = "ai-pipeline/training/data/licenses/medleydb.md"
EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/medleydb")

# Mapping from MedleyDB instrument names to BeatSight labels
INSTRUMENT_MAP = {
    "drum set": "drum_mix",
    "drums": "drum_mix",
    "kick drum": "kick",
    "snare drum": "snare_center",
    "tom-tom": "tom_mid", # Generic tom
    "high tom": "tom_high",
    "mid tom": "tom_mid",
    "low tom": "tom_low",
    "floor tom": "tom_low",
    "hi-hat": "hihat_closed", # Generic
    "cymbal": "crash_1", # Generic
    "ride cymbal": "ride_bow",
    "crash cymbal": "crash_1",
    "cowbell": "cowbell",
    "claps": "clap",
    "shaker": "shaker",
    "tambourine": "tambourine",
    "bongo": "aux_percussion",
    "conga": "aux_percussion",
    "timbales": "aux_percussion",
    "cajon": "aux_percussion",
    "tabla": "aux_percussion",
    "darbuka": "aux_percussion",
    "djembe": "aux_percussion",
    "percussion": "aux_percussion",
}

def parse_args():
    parser = argparse.ArgumentParser(description="Ingest MedleyDB")
    parser.add_argument(
        "--medleydb-root",
        help="Path to MedleyDB root directory",
    )
    parser.add_argument(
        "--output-events",
        type=pathlib.Path,
        default=DEFAULT_EVENTS_OUTPUT,
        help="Path to output events JSONL",
    )
    parser.add_argument(
        "--output-provenance",
        type=pathlib.Path,
        default=DEFAULT_PROVENANCE_OUTPUT,
        help="Path to output provenance JSONL",
    )
    parser.add_argument(
        "--license-ref",
        default=DEFAULT_LICENSE_REF,
        help="Relative path to license file",
    )
    parser.add_argument(
        "--ingestion-version",
        default=None,
        help="Version tag or git commit",
    )
    return parser.parse_args()

def find_root(provided: Optional[str]) -> pathlib.Path:
    if provided:
        return ingest_utils.resolve_repo_path(provided)
    for candidate in DEFAULT_ROOT_CANDIDATES:
        path = ingest_utils.resolve_repo_path(candidate)
        if path.exists():
            return path
    raise FileNotFoundError("Could not find MedleyDB root. Please provide --medleydb-root.")

def _probe_audio_stats(path: pathlib.Path) -> Tuple[Optional[int], Optional[float], Optional[int]]:
    if _sf is not None:
        try:
            info = _sf.info(str(path))
            duration = float(info.frames) / info.samplerate if info.samplerate else None
            return info.samplerate, duration, info.channels
        except Exception:
            pass

    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            samplerate = handle.getframerate()
            channels = handle.getnchannels()
            duration = frames / samplerate if samplerate else None
            return samplerate, duration, channels
    except Exception:
        return None, None, None

def process_session(
    track_dir: pathlib.Path,
    metadata_path: pathlib.Path,
    medleydb_root: pathlib.Path,
    license_ref: str,
    ingestion_version: str,
) -> Tuple[List[Dict], Optional[str]]:
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading metadata {metadata_path}: {e}", file=sys.stderr)
        return [], None

    session_id = metadata.get("title", track_dir.name)
    stems = metadata.get("stems", {})
    
    events = []
    sample_paths = []
    hash_entries = []
    session_techniques = set()

    for stem_key, stem_info in stems.items():
        instrument = stem_info.get("instrument", "")
        label = INSTRUMENT_MAP.get(instrument)
        
        if not label:
            continue

        filename = stem_info.get("filename")
        if not filename:
            continue

        audio_path = None
        for r, d, f in os.walk(track_dir):
            if filename in f:
                audio_path = pathlib.Path(r) / filename
                break
        
        if not audio_path:
            continue

        try:
            rel_path = audio_path.relative_to(medleydb_root).as_posix()
        except ValueError:
            rel_path = str(audio_path)

        sample_paths.append(rel_path)
        # Optional: Hash file (can be slow for large datasets)
        # digest = ingest_utils.sha256_file(audio_path)
        # hash_entries.append({"path": rel_path, "sha256": digest})

        samplerate, duration, channels = _probe_audio_stats(audio_path)
        file_size = audio_path.stat().st_size

        event_id = str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{rel_path}"))
        
        components = [{
            "label": label,
            "source_track": rel_path,
            "instrument_original": instrument
        }]

        # Add specific variants based on instrument name
        if "cowbell" in instrument:
            components[0]["instrument_variant"] = "cowbell"
            session_techniques.add("cowbell")
        
        event = {
            "event_id": event_id,
            "session_id": session_id,
            "source_set": "medleydb",
            "is_synthetic": False,
            "audio_path": rel_path, # Store relative path from root
            "midi_path": None,
            "onset_time": 0.0,
            "offset_time": None,
            "tempo_bpm": None, # Could extract from metadata if available
            "meter": None,
            "components": components,
            "techniques": sorted(list(session_techniques)),
            "context_ms": {"pre": 0, "post": 0},
            "metadata_ref": f"provenance:{session_id}",
            "negative_example": False,
        }

        if samplerate:
            event["sample_rate"] = samplerate
        if duration:
            event["duration_seconds"] = round(duration, 6)
        if channels:
            event["channels"] = channels
        if file_size:
            event["file_size_bytes"] = file_size

        events.append(event)

    provenance_json = None
    if events:
        record = ingest_utils.ProvenanceRecord(
            source_set="medleydb",
            session_id=session_id,
            sample_paths=sample_paths,
            hashes=hash_entries,
            license_ref=license_ref,
            ingestion_script="training/tools/ingest_medleydb.py",
            ingestion_version=ingestion_version,
            processing_chain=["raw_multitrack"],
            timestamp_utc=_dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
            techniques=sorted(list(session_techniques)),
            notes="MedleyDB stem ingestion",
        )
        provenance_json = record.to_json()

    return events, provenance_json

def main():
    args = parse_args()
    root = find_root(args.medleydb_root)
    print(f"Scanning MedleyDB at: {root}")

    ingestion_version = args.ingestion_version or ingest_utils.git_rev_parse_head()
    
    all_events = []
    provenance_rows = []

    # Try to find a central Metadata folder
    metadata_root = root / "Metadata"
    if metadata_root.exists():
        print(f"Found central Metadata folder at {metadata_root}")
        metadata_files = list(metadata_root.glob("*_METADATA.yaml"))
        
        for metadata_file in ingest_utils.track_progress(metadata_files, "Ingesting MedleyDB", total=len(metadata_files)):
            # Infer track directory name from metadata filename
            # Format: Artist_Title_METADATA.yaml -> Artist_Title
            track_name = metadata_file.name.replace("_METADATA.yaml", "")
            
            # Look for track dir in root (flat structure) or in Audio/ (standard structure)
            track_dir = root / track_name
            if not track_dir.exists():
                track_dir = root / "Audio" / track_name
            
            if not track_dir.exists():
                # print(f"Warning: Audio directory not found for {track_name}", file=sys.stderr)
                continue

            events, provenance = process_session(
                track_dir, 
                metadata_file, 
                root,
                args.license_ref,
                ingestion_version
            )
            all_events.extend(events)
            if provenance:
                provenance_rows.append(provenance)
    else:
        print("No central Metadata folder found. Scanning track directories...")
        # Iterate over all subdirectories in root
        track_dirs = [d for d in root.iterdir() if d.is_dir()]
        
        for track_dir in ingest_utils.track_progress(track_dirs, "Ingesting MedleyDB", total=len(track_dirs)):
            # Look for metadata file inside the track directory
            # Usually named Artist_Title_METADATA.yaml
            metadata_files = list(track_dir.glob("*_METADATA.yaml"))
            
            if not metadata_files:
                # Fallback: look for any yaml
                metadata_files = list(track_dir.glob("*.yaml"))
                
            if not metadata_files:
                # print(f"Warning: No metadata found for {track_dir.name}", file=sys.stderr)
                continue
                
            metadata_file = metadata_files[0]

            events, provenance = process_session(
                track_dir, 
                metadata_file, 
                root,
                args.license_ref,
                ingestion_version
            )
            all_events.extend(events)
            if provenance:
                provenance_rows.append(provenance)

    print(f"Found {len(all_events)} drum/percussion stems from {len(provenance_rows)} sessions.")
    
    args.output_events.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_events, "w", encoding="utf-8") as f:
        for event in all_events:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
            
    args.output_provenance.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_provenance, "w", encoding="utf-8") as f:
        for row in provenance_rows:
            f.write(row + "\n")
    
    print(f"Wrote events to {args.output_events}")
    print(f"Wrote provenance to {args.output_provenance}")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_medleydb.py",
        events_path=args.output_events,
        manifest_path=args.output_events,
    )

if __name__ == "__main__":
    main()
