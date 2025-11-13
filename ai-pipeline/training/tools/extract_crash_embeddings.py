#!/usr/bin/env python3
"""Generate crash-centric audio embeddings for manifest events.

This utility scans a manifest, extracts short audio windows around crash hits,
computes lightweight spectral descriptors, and emits one JSON line per event.
The resulting file is intended to feed the upcoming spectral clustering stage
for crash voice differentiation.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, Optional

import librosa
import numpy as np
import soundfile as sf

DEFAULT_SAMPLE_RATE = 22_050
DEFAULT_WINDOW_MS = 800.0
DEFAULT_PREROLL_MS = 120.0
DEFAULT_N_MFCC = 13


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Events JSONL manifest to inspect")
    parser.add_argument("--audio-root", type=Path, help="Optional root path for relative audio files")
    parser.add_argument(
        "--audio-root-map",
        action="append",
        default=[],
        metavar="SOURCE=PATH",
        help="Override audio root per source_set (repeatable, e.g. slakh2100=data/raw/slakh2100)",
    )
    parser.add_argument("--output", type=Path, required=True, help="Destination JSONL file for per-event embeddings")
    parser.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE, help="Resample audio to this rate (default: 22050)")
    parser.add_argument("--window-ms", type=float, default=DEFAULT_WINDOW_MS, help="Duration of each extracted window in milliseconds")
    parser.add_argument("--preroll-ms", type=float, default=DEFAULT_PREROLL_MS, help="Audio captured before onset in milliseconds")
    parser.add_argument("--n-mfcc", type=int, default=DEFAULT_N_MFCC, help="Number of MFCC coefficients to compute")
    parser.add_argument("--limit", type=int, help="Optional hard cap on processed events")
    parser.add_argument("--limit-per-session", type=int, help="Restrict processed events per session")
    parser.add_argument("--include-component", action="append", default=["crash", "crash2"], help="Process events containing the supplied component labels (repeatable)")
    parser.add_argument("--progress", action="store_true", help="Emit periodic progress updates")
    parser.add_argument("--fail-fast", action="store_true", help="Abort on the first audio read error")
    parser.add_argument("--sessions", action="append", help="Optional whitelist of session_ids to process (repeat flag to add more)")
    parser.add_argument("--dry-run", action="store_true", help="List candidate events without writing output")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.window_ms <= 0:
        raise SystemExit("--window-ms must be positive")
    if args.preroll_ms < 0:
        raise SystemExit("--preroll-ms must be non-negative")
    if args.n_mfcc <= 0:
        raise SystemExit("--n-mfcc must be positive")
    return args


def parse_audio_root_map(entries: Iterable[str]) -> Dict[str, Path]:
    mapping: Dict[str, Path] = {}
    for entry in entries:
        if not entry:
            continue
        if "=" not in entry:
            raise SystemExit("--audio-root-map entries must be formatted as SOURCE=PATH")
        source, raw_path = entry.split("=", 1)
        source = source.strip()
        if not source:
            raise SystemExit("--audio-root-map entries must specify a non-empty SOURCE")
        path_obj = Path(raw_path.strip()).expanduser().resolve()
        mapping[source] = path_obj
    return mapping


def resolve_audio_path(audio_root: Optional[Path], audio_path: str) -> Optional[Path]:
    candidate = Path(audio_path)
    if candidate.is_file():
        return candidate
    if audio_root is not None:
        joined = audio_root / audio_path
        if joined.is_file():
            return joined
    return None


def iter_manifest_events(manifest_path: Path) -> Iterator[Mapping[str, object]]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Failed to parse JSON on line {line_number}: {exc}") from exc
            yield event


def has_component(event: Mapping[str, object], targets: Iterable[str]) -> bool:
    components = event.get("components")
    if not isinstance(components, list):
        return False
    labels = {str(comp.get("label")) for comp in components if isinstance(comp, dict) and comp.get("label")}
    return any(label in labels for label in targets)


def extract_window(
    audio_path: Path,
    onset_time: float,
    sample_rate: int,
    window_ms: float,
    preroll_ms: float,
) -> np.ndarray:
    target_duration = max(window_ms / 1000.0, 0.001)
    start_time = max(onset_time - (preroll_ms / 1000.0), 0.0)
    # Clamp offset so we do not request negative duration from the audio reader.
    with sf.SoundFile(audio_path, "r") as handle:
        if start_time >= handle.frames / handle.samplerate:
            return np.array([], dtype=np.float32)
    audio, _ = librosa.load(
        audio_path,
        sr=sample_rate,
        offset=start_time,
        duration=target_duration,
        mono=True,
    )
    return audio.astype(np.float32, copy=False)


def compute_descriptors(audio: np.ndarray, sample_rate: int, n_mfcc: int) -> Optional[Dict[str, object]]:
    if audio.size == 0:
        return None
    rms = librosa.feature.rms(y=audio).mean()
    centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate).mean()
    bandwidth = librosa.feature.spectral_bandwidth(y=audio, sr=sample_rate).mean()
    rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sample_rate, roll_percent=0.85).mean()
    zcr = librosa.feature.zero_crossing_rate(y=audio).mean()
    mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=n_mfcc)
    mfcc_mean = mfcc.mean(axis=1).tolist()
    mfcc_std = mfcc.std(axis=1).tolist()
    return {
        "rms": float(rms),
        "spectral_centroid": float(centroid),
        "spectral_bandwidth": float(bandwidth),
        "spectral_rolloff": float(rolloff),
        "zero_crossing_rate": float(zcr),
        "mfcc_mean": [float(x) for x in mfcc_mean],
        "mfcc_std": [float(x) for x in mfcc_std],
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    manifest_path: Path = args.manifest
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    audio_root = args.audio_root.resolve() if args.audio_root else None
    audio_root_overrides = parse_audio_root_map(args.audio_root_map)
    include_components = tuple({label.strip() for label in args.include_component if label and label.strip()}) or ("crash", "crash2")
    session_whitelist = None
    if args.sessions:
        session_whitelist = {item.strip() for item in args.sessions if item and item.strip()}

    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_handle = args.output.open("w", encoding="utf-8")
    else:
        output_handle = None

    processed = 0
    skipped_audio = 0
    failed = 0
    per_session_counts: Dict[str, int] = defaultdict(int)

    for event in iter_manifest_events(manifest_path):
        if not has_component(event, include_components):
            continue

        session_id = str(event.get("session_id") or "")
        if session_whitelist and session_id not in session_whitelist:
            continue

        if args.limit_per_session is not None and per_session_counts[session_id] >= args.limit_per_session:
            continue

        onset_time = float(event.get("onset_time") or 0.0)
        audio_path_value = event.get("audio_path")
        if not isinstance(audio_path_value, str) or not audio_path_value:
            continue

        source_set = str(event.get("source_set") or "")
        # Prefer a dataset-specific root when available, otherwise fall back to the global root
        resolved_audio = resolve_audio_path(audio_root_overrides.get(source_set, audio_root), audio_path_value)
        if resolved_audio is None:
            skipped_audio += 1
            if args.fail_fast:
                raise FileNotFoundError(f"Audio file not found for event {event.get('event_id')}: {audio_path_value}")
            continue

        try:
            window = extract_window(
                resolved_audio,
                onset_time=onset_time,
                sample_rate=args.sample_rate,
                window_ms=args.window_ms,
                preroll_ms=args.preroll_ms,
            )
        except Exception as exc:  # pragma: no cover - audio IO issues
            failed += 1
            if args.fail_fast:
                raise
            print(f"[extract_crash_embeddings] Failed to read {resolved_audio}: {exc}", file=sys.stderr)
            continue

        descriptors = compute_descriptors(window, sample_rate=args.sample_rate, n_mfcc=args.n_mfcc)
        if descriptors is None:
            continue

        record = {
            "event_id": event.get("event_id"),
            "session_id": session_id,
            "audio_path": audio_path_value,
            "resolved_path": str(resolved_audio),
            "onset_time": onset_time,
            "components": [comp.get("label") for comp in event.get("components", []) if isinstance(comp, dict)],
            "techniques": event.get("techniques"),
            "metrics": descriptors,
        }

        if output_handle is not None:
            output_handle.write(json.dumps(record, ensure_ascii=False)
                                + "\n")
        processed += 1
        per_session_counts[session_id] += 1

        if args.progress and processed % 100 == 0:
            print(f"Processed {processed} crash events...", file=sys.stderr)

        if args.limit is not None and processed >= args.limit:
            break

    if output_handle is not None:
        output_handle.close()

    print(
        json.dumps(
            {
                "processed_events": processed,
                "skipped_missing_audio": skipped_audio,
                "failed_audio_reads": failed,
                "unique_sessions": len(per_session_counts),
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
