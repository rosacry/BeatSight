#!/usr/bin/env python3
"""Shared helpers for dataset ingestion scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import pathlib
import shlex
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

try:  # Optional dependency for progress bars.
    from rich.progress import (  # type: ignore[import]
        BarColumn,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )

    _HAS_RICH = True
except ImportError:  # pragma: no cover - optional feature
    _HAS_RICH = False

_THIS_FILE = pathlib.Path(__file__).resolve()
AI_PIPELINE_ROOT = _THIS_FILE.parents[2]
REPO_ROOT = _THIS_FILE.parents[3]
DATA_RAW_ROOT = REPO_ROOT / "data" / "raw"
TECHNIQUE_TAXONOMY_PATH = AI_PIPELINE_ROOT / "training" / "configs" / "technique_taxonomy.json"
ADDITIONAL_TECHNIQUES_PATH = REPO_ROOT / "additionaldrummertech.txt"
DEFAULT_TECHNIQUES_PATH = TECHNIQUE_TAXONOMY_PATH if TECHNIQUE_TAXONOMY_PATH.exists() else ADDITIONAL_TECHNIQUES_PATH


def sha256_file(path: pathlib.Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA256 hex digest of ``path``."""
    h_obj = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h_obj.update(chunk)
    return h_obj.hexdigest()


def _load_techniques_from_text(path: pathlib.Path) -> List[str]:
    values: List[str] = []
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        values.append(line)
    return sorted(set(values))


def _load_techniques_from_json(path: pathlib.Path) -> List[str]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    entries: List[str] = []
    payload = data.get("techniques") if isinstance(data, dict) else data
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                entries.append(item)
            elif isinstance(item, dict):
                identifier = item.get("id")
                if identifier:
                    entries.append(str(identifier))

    return sorted(set(entries))


def load_techniques(path: pathlib.Path = DEFAULT_TECHNIQUES_PATH) -> List[str]:
    """Load technique identifiers from taxonomy JSON or legacy text list."""

    resolved = resolve_repo_path(str(path))
    if not resolved.exists():
        # Fall back to legacy text list if taxonomy is missing.
        if resolved != ADDITIONAL_TECHNIQUES_PATH and ADDITIONAL_TECHNIQUES_PATH.exists():
            return _load_techniques_from_text(ADDITIONAL_TECHNIQUES_PATH)
        return []

    if resolved.suffix.lower() == ".json":
        loaded = _load_techniques_from_json(resolved)
        if loaded:
            return loaded
        # Attempt legacy fallback when taxonomy is malformed.
        if ADDITIONAL_TECHNIQUES_PATH.exists():
            return _load_techniques_from_text(ADDITIONAL_TECHNIQUES_PATH)
        return []

    return _load_techniques_from_text(resolved)


def load_technique_taxonomy(path: pathlib.Path = TECHNIQUE_TAXONOMY_PATH) -> dict:
    """Return the full technique taxonomy payload for downstream consumers."""

    resolved = resolve_repo_path(str(path))
    if not resolved.exists():
        return {"techniques": []}

    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"techniques": []}

    if isinstance(data, dict):
        if "techniques" in data and isinstance(data["techniques"], list):
            return data
        return {"techniques": []}

    if isinstance(data, list):
        return {"techniques": data}

    return {"techniques": []}


@dataclass
class ProvenanceRecord:
    source_set: str
    session_id: str
    sample_paths: Sequence[str]
    hashes: Sequence[dict]
    license_ref: str
    ingestion_script: str
    ingestion_version: str
    processing_chain: Sequence[str]
    timestamp_utc: str
    techniques: Sequence[str]
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))


def write_jsonl(output: pathlib.Path, rows: Iterable[dict]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def print_post_ingest_checklist_hint(
    script_name: str,
    *,
    events_path: Optional[pathlib.Path] = None,
    manifest_path: Optional[pathlib.Path] = None,
    weights_output: Optional[pathlib.Path] = None,
) -> None:
    """Display an actionable command for the post-ingest checklist.

    Args:
        script_name: Name of the ingest script finishing execution.
        events_path: Events manifest written by the ingest script.
        manifest_path: Manifest path to hand to the checklist for sampling weights.
        weights_output: Optional explicit sampling weights destination.
    """

    cmd: List[str] = ["python", "ai-pipeline/training/tools/post_ingest_checklist.py"]
    if events_path is not None:
        cmd.extend(["--events", events_path.as_posix()])
    if manifest_path is not None and manifest_path != events_path:
        cmd.extend(["--manifest", manifest_path.as_posix()])
    if weights_output is not None:
        cmd.extend(["--weights-output", weights_output.as_posix()])

    printable = " ".join(shlex.quote(token) for token in cmd)
    print(
        "\nNext step: run the post-ingest checklist for {script}.\n  {command}"
        .format(script=script_name, command=printable)
    )


def tag_hihat_barks(
    events: Sequence[dict],
    window_seconds: float = 0.2,
    technique_label: str = "hihat_bark",
) -> None:
    """Annotate hi-hat bark techniques in-place for ``events``.

    Args:
        events: Sequence of event dictionaries sorted (or sortable) by onset time.
        window_seconds: Max gap between open and close hits to flag a bark.
        technique_label: Technique identifier to attach when a bark is detected.
    """

    if not events:
        return

    open_queue = deque()
    for event in sorted(events, key=lambda item: float(item.get("onset_time") or 0.0)):
        onset = float(event.get("onset_time") or 0.0)

        while open_queue and onset - open_queue[0]["onset"] > window_seconds:
            open_queue.popleft()

        components = event.get("components") or []
        for component in components:
            label = component.get("label")
            if label == "hihat_open":
                open_queue.append({"onset": onset, "event": event, "matched": False})
            elif label in {"hihat_closed", "hihat_pedal"}:
                while open_queue and onset - open_queue[0]["onset"] > window_seconds:
                    open_queue.popleft()

                for record in open_queue:
                    if record["matched"]:
                        continue

                    record["matched"] = True
                    open_event = record["event"]
                    for target in (open_event, event):
                        techniques = set(target.get("techniques") or [])
                        techniques.add(technique_label)
                        target["techniques"] = sorted(techniques)
                    break


_CYMBAL_FAMILY_LABELS: Set[str] = {"crash", "china", "splash"}
_CYMBAL_VARIANT_TECHNIQUES: Dict[str, Dict[str, str]] = {
    "crash": {
        "high": "crash_high",
        "mid": "crash_mid",
        "low": "crash_low",
    },
    "china": {
        "high": "china_high",
        "mid": "china_mid",
        "low": "china_low",
    },
}
_LABEL_TECHNIQUE_MAP: Dict[str, str] = {
    "rimshot": "rimshot",
    "cross_stick": "cross_stick",
    "sidestick": "cross_stick",
    "rim_click": "rim_click",
    "rim": "rim_click",
    "hihat_pedal": "hihat_foot_chick",
    "hihat_foot": "hihat_foot_chick",
    "hihat_foot_splash": "hihat_splash",
    "ride_bell": "ride_bell_accent",
    "ride_bow": "ride_tip_articulation",
}
_HIHAT_HALF_OPEN_MIN = 0.35
_HIHAT_SPLASH_MIN = 0.8
_METRIC_RATIO_TOLERANCE = 0.025


def _coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _categorize_cymbal_variant(label: str, variant: str) -> Optional[str]:
    text = (variant or "").strip().lower()
    if not text:
        return None

    if any(token in text for token in ("high", "bright", "small", "primary", "top")):
        return "high"
    if any(token in text for token in ("low", "dark", "large", "bottom", "floor", "tertiary")):
        return "low"
    if any(token in text for token in ("mid", "medium", "secondary", "center")):
        return "mid"

    # Heuristic for numeric suffixes (e.g., crash_1/crash_2/crash_3).
    if text.endswith("1") or text.endswith("_1"):
        return "high"
    if text.endswith("2") or text.endswith("_2"):
        return "mid"
    if text.endswith("3") or text.endswith("_3"):
        return "low"

    if label == "china":
        if text.startswith("china_high"):
            return "high"
        if text.startswith("china_mid"):
            return "mid"
        if text.startswith("china_low"):
            return "low"

    return None


def _infer_component_techniques(component: Mapping[str, object]) -> Set[str]:
    techniques: Set[str] = set()
    label = str(component.get("label") or "").lower()
    if not label:
        return techniques

    direct = _LABEL_TECHNIQUE_MAP.get(label)
    if direct:
        techniques.add(direct)

    strike_position = str(component.get("strike_position") or "").lower()
    if strike_position == "bell":
        techniques.add("ride_bell_accent")

    family = label.split("_", 1)[0]
    if family.startswith("ride") and strike_position not in {"bell", "edge"}:
        techniques.add("ride_tip_articulation")

    variant = str(component.get("instrument_variant") or "")
    category = _categorize_cymbal_variant(family, variant)
    mapped = _CYMBAL_VARIANT_TECHNIQUES.get(family, {}).get(category)
    if mapped:
        techniques.add(mapped)

    if family == "hihat":
        openness = _coerce_float(component.get("openness"))
        if openness is not None:
            if openness >= _HIHAT_SPLASH_MIN:
                techniques.add("hihat_splash")
            elif openness >= _HIHAT_HALF_OPEN_MIN:
                techniques.add("hihat_half_open")

    return techniques


def _looks_like_metric_modulation(prev_tempo: float, new_tempo: float) -> bool:
    if prev_tempo <= 0 or new_tempo <= 0:
        return False

    ratio = new_tempo / prev_tempo
    if math.isclose(ratio, 1.0, rel_tol=0.015, abs_tol=0.015):
        return False

    approx = Fraction(ratio).limit_denominator(8)
    approx_ratio = approx.numerator / approx.denominator
    return abs(ratio - approx_ratio) <= _METRIC_RATIO_TOLERANCE


def apply_taxonomy_inference(events: Sequence[dict]) -> Set[str]:
    """Derive taxonomy-aligned techniques from event metadata in-place."""

    session_techniques: Set[str] = set()
    if not events:
        return session_techniques

    indexed_events = list(enumerate(events))
    indexed_events.sort(key=lambda item: float(item[1].get("onset_time") or 0.0))

    cymbal_variants: Dict[str, Set[str]] = defaultdict(set)
    cymbal_event_indices: Dict[str, Set[int]] = defaultdict(set)

    prev_meter: Optional[str] = None
    prev_tempo: Optional[float] = None
    meter_flagged = False
    metric_flagged = False

    for idx, event in indexed_events:
        techniques = set(event.get("techniques") or [])
        components = event.get("components") or []

        for component in components:
            inferred = _infer_component_techniques(component)
            if inferred:
                techniques.update(inferred)
                session_techniques.update(inferred)

            label = str(component.get("label") or "").lower()
            family = label.split("_", 1)[0]
            if family in _CYMBAL_FAMILY_LABELS:
                variant_token = str(component.get("instrument_variant") or "").strip()
                if variant_token:
                    cymbal_variants[family].add(variant_token.lower())
                    cymbal_event_indices[family].add(idx)

        event["techniques"] = sorted(techniques)

        meter = event.get("meter")
        if isinstance(meter, str) and meter:
            if prev_meter is not None and meter != prev_meter and not meter_flagged:
                techniques = set(event.get("techniques") or [])
                techniques.add("variable_meter")
                event["techniques"] = sorted(techniques)
                session_techniques.add("variable_meter")
                meter_flagged = True
            prev_meter = meter

        tempo_value = _coerce_float(event.get("tempo_bpm"))
        if tempo_value is not None:
            if (
                prev_tempo is not None
                and not math.isclose(tempo_value, prev_tempo, rel_tol=0.01, abs_tol=0.1)
                and not metric_flagged
                and _looks_like_metric_modulation(prev_tempo, tempo_value)
            ):
                techniques = set(event.get("techniques") or [])
                techniques.add("metric_modulation")
                event["techniques"] = sorted(techniques)
                session_techniques.add("metric_modulation")
                metric_flagged = True
            prev_tempo = tempo_value

    multi_label = "multi_cymbal_same_class"
    for family, variants in cymbal_variants.items():
        if len(variants) > 1:
            session_techniques.add(multi_label)
            for idx in cymbal_event_indices[family]:
                techniques = set(events[idx].get("techniques") or [])
                techniques.add(multi_label)
                events[idx]["techniques"] = sorted(techniques)

    return session_techniques


def resolve_repo_path(value: str) -> pathlib.Path:
    raw_value = str(value)
    candidate = pathlib.Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if resolved.exists():
        return resolved

    # Handle Windows drive letters when running inside WSL.
    if ":" in raw_value[:3]:
        drive_letter = raw_value[0].lower()
        remainder = raw_value[2:].lstrip("\\/")
        remainder_posix = remainder.replace("\\", "/")
        alt = pathlib.Path(f"/mnt/{drive_letter}/{remainder_posix}")
        alt_resolved = alt.resolve(strict=False)
        if alt_resolved.exists():
            return alt_resolved

    # Handle WSL-style paths when running on Windows.
    if raw_value.startswith("/mnt/") and os.name == "nt":
        parts = raw_value.split("/", 3)
        if len(parts) >= 4 and len(parts[2]) == 1:
            drive_letter = parts[2].upper()
            alt = pathlib.Path(f"{drive_letter}:/{parts[3]}")
            alt_resolved = alt.resolve(strict=False)
            if alt_resolved.exists():
                return alt_resolved

    return resolved


def path_type(value: str) -> pathlib.Path:
    candidate = resolve_repo_path(value)
    if not candidate.exists():
        raise argparse.ArgumentTypeError(f"path does not exist: {candidate}")
    return candidate


def git_rev_parse_head(default: str = "unknown") -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=REPO_ROOT
        ).strip()
    except Exception:
        return default


def resolve_dataset_roots(candidates: Sequence[str]) -> List[pathlib.Path]:
    roots: List[pathlib.Path] = []
    for candidate in candidates:
        path = resolve_repo_path(candidate)
        if path.exists():
            roots.append(path)
    return roots


def track_progress(iterable: Iterable, description: str, total: int | None = None) -> Iterable:
    iterator = iter(iterable)
    if not _HAS_RICH:
        for idx, item in enumerate(iterator, 1):
            if idx == 1 and total is not None:
                print(f"{description}: {total} items")
            elif total is None and idx % 500 == 0:
                print(f"{description}: processed {idx}")
            yield item
        return

    progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        transient=True,
    )
    with progress:
        task = progress.add_task(description, total=total)
        for item in iterator:
            yield item
            progress.advance(task)
