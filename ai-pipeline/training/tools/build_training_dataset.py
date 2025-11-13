#!/usr/bin/env python3
"""Materialize per-event audio slices from a BeatSight manifest.

The production manifests reference source audio files spread across multiple
raw datasets.  This helper reads each manifest event, slices the referenced
audio using the stored onset/context windows, and writes normalised training
clips into a dataset bundle compatible with :mod:`train_classifier.py`.

Example usage:

    python ai-pipeline/training/tools/build_training_dataset.py \
        ai-pipeline/training/data/manifests/prod_combined_events.jsonl \
        ai-pipeline/training/datasets/prod_combined_20251109 \
        --audio-root-map slakh2100=data/raw/slakh2100 \
        --audio-root-map groove_mididataset=data/raw/groove_midi \
        --audio-root-map enst_drums=data/raw/ENST-Drums \
        --audio-root-map cambridge_multitrack=data/raw/cambridge \
        --audio-root-map idmt_smt_drums_v2=data/raw/idmt_smt_drums_v2

The tool streams the manifest, assigns deterministic splits per session, and
emits three label files (``train_labels.json``, ``val_labels.json``, and
``components.json``) alongside the sliced ``.wav`` clips.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import csv
from contextlib import nullcontext
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import (
    Any,
    DefaultDict,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

try:  # Optional rich summary rendering.
    from rich import box  # type: ignore[import]
    from rich.console import Group  # type: ignore[import]
    from rich.live import Live  # type: ignore[import]
    from rich.panel import Panel  # type: ignore[import]
    from rich.table import Table  # type: ignore[import]
except ImportError:  # pragma: no cover - optional enhancement only
    box = None  # type: ignore[assignment]
    Group = None  # type: ignore[assignment]
    Live = None  # type: ignore[assignment]
    Panel = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]

_THIS_FILE = Path(__file__).resolve()
_PACKAGE_ROOT = _THIS_FILE.parents[2]
if str(_PACKAGE_ROOT) not in sys.path:  # pragma: no cover - runtime import convenience
    sys.path.insert(0, str(_PACKAGE_ROOT))

from training.tools.console_utils import (  # type: ignore[import]
    HAS_RICH as HAS_RICH_DISPLAY,
    OutputLogger,
    ProgressAdapter,
)

import librosa  # type: ignore[import]
import numpy as np
import soundfile as sf

DEFAULT_SAMPLE_RATE = 44_100
DEFAULT_PRE_ROLL_MS = 80.0
DEFAULT_POST_TAIL_MS = 200.0
FALLBACK_DURATION_SECONDS = 0.5
MAX_PENDING_WRITES = 4_096  # Upper bound on outstanding writer futures before we block and flush
FILE_FIELD_PATTERN = re.compile(r'"file"\s*:\s*"([^\"]+)"')
DEFAULT_CLIP_FANOUT = 0


def _normalise_clip_id(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch.isalnum()).lower()


def _compute_fanout_prefix(clip_id: str, fanout: int) -> Optional[str]:
    if fanout <= 0:
        return None
    normalised = _normalise_clip_id(clip_id)
    if not normalised:
        return None
    if len(normalised) < fanout:
        normalised = (normalised + "0" * fanout)[:fanout]
    else:
        normalised = normalised[:fanout]
    return normalised


def _construct_clip_relative_path(
    clip_id: str,
    label: str,
    *,
    fanout: int,
) -> Path:
    safe_label = label.replace("/", "-")
    clip_name = f"{clip_id}__{safe_label}.wav"
    components = ["audio"]
    prefix = _compute_fanout_prefix(clip_id, fanout)
    if prefix:
        components.append(prefix)
    components.append(clip_name)
    return Path(*components)


def _default_write_worker_count() -> int:
    cpu_estimate = os.cpu_count() or 8
    return max(4, min(16, cpu_estimate))


DEFAULT_WRITE_WORKERS = _default_write_worker_count()


@dataclass(frozen=True)
class SliceRequest:
    """Parameters that describe how to extract a window from an audio file."""

    audio_path: Path
    onset_seconds: float
    preroll_seconds: float
    duration_seconds: float


@dataclass
class ExportStats:
    """Counters collected during export."""

    total_events: int = 0
    sliced_events: int = 0
    written_clips: int = 0
    skipped_missing_audio: int = 0
    skipped_no_components: int = 0
    train_clips: int = 0
    val_clips: int = 0
    written_seconds: float = 0.0
    train_seconds: float = 0.0
    val_seconds: float = 0.0
    healed_clips: int = 0
    healed_seconds: float = 0.0

    @property
    def skipped_total(self) -> int:
        return self.skipped_missing_audio + self.skipped_no_components

    def as_dict(self) -> Dict[str, int]:
        return {
            "total_events": self.total_events,
            "sliced_events": self.sliced_events,
            "written_clips": self.written_clips,
            "skipped_missing_audio": self.skipped_missing_audio,
            "skipped_no_components": self.skipped_no_components,
            "skipped_total": self.skipped_total,
            "train_clips": self.train_clips,
            "val_clips": self.val_clips,
            "written_seconds": self.written_seconds,
            "train_seconds": self.train_seconds,
            "val_seconds": self.val_seconds,
            "healed_clips": self.healed_clips,
            "healed_seconds": self.healed_seconds,
        }


def _coerce_number(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> Optional[int]:
    number = _coerce_number(value)
    if number is None:
        return None
    return int(round(number))


def _merge_stat(target: Dict[str, Union[int, float]], key: str, value: object) -> None:
    number = _coerce_number(value)
    if number is None:
        return
    if key.endswith("_seconds"):
        target[key] = float(target.get(key, 0.0)) + float(number)
    else:
        target[key] = int(target.get(key, 0)) + int(round(number))


def _format_duration(value: object) -> str:
    seconds = _coerce_number(value)
    if seconds is None:
        return "-"
    total = float(seconds)
    if total < 1e-3:
        return "0 ms"
    if total < 1:
        return f"{total * 1000:.0f} ms"
    hours = int(total // 3600)
    remainder = total - hours * 3600
    minutes = int(remainder // 60)
    seconds_rem = remainder - minutes * 60
    if hours:
        return f"{hours}h {minutes:02d}m {seconds_rem:05.2f}s"
    if minutes:
        return f"{minutes}m {seconds_rem:05.2f}s"
    return f"{seconds_rem:,.2f} s"


def _format_count(value: object) -> str:
    number = _coerce_number(value)
    if number is None:
        return "-"
    if abs(number - round(number)) < 1e-6:
        return f"{int(round(number)):,}"
    return f"{number:,.2f}"


def _format_eta(value: object) -> str:
    seconds = _coerce_number(value)
    if seconds is None or seconds < 0:
        return "-"
    if seconds < 1:
        return "<1s"
    return _format_duration(seconds)


def _write_duration_csv(
    path: Path,
    datasets: Sequence[Tuple[str, Mapping[str, object]]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Tuple[int, str, str, float, str]] = []
    for idx, (label, mapping) in enumerate(datasets):
        if not isinstance(mapping, Mapping):
            continue
        for source, value in mapping.items():
            seconds = _coerce_number(value) or 0.0
            rows.append(
                (idx, label, str(source), float(seconds), _format_duration(seconds))
            )

    rows.sort(key=lambda item: (item[0], -item[3], item[2]))

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "source_set", "seconds", "formatted_duration"])
        for _, label, source, seconds, formatted in rows:
            writer.writerow([label, source, f"{seconds:.6f}", formatted])


class DatasetProgressDisplay:
    """Optional rich live dashboard to surface export progress."""

    def __init__(
        self,
        logger: OutputLogger,
        *,
        total: Optional[int] = None,
        event_offset: int = 0,
        refresh_interval: float = 0.25,
    ) -> None:
        self._logger = logger
        self._console = logger.rich_console if logger.enable_rich else None
        self._live: Optional[Any] = None
        self._snapshot: Dict[str, object] = {}
        self._total_events = total
        self._event_offset = max(event_offset, 0)
        self._refresh_interval = max(refresh_interval, 0.05)
        self._last_refresh: float = 0.0
        self._start_time: Optional[float] = None

    @property
    def enabled(self) -> bool:
        return bool(
            self._console
            and HAS_RICH_DISPLAY
            and Live is not None
            and Table is not None
        )

    def __enter__(self) -> "DatasetProgressDisplay":
        if self.enabled:
            self._start_time = monotonic()
            self._last_refresh = 0.0
            refresh_rate = 4.0
            if self._refresh_interval > 0:
                refresh_rate = max(min(1.0 / self._refresh_interval, 24.0), 1.0)
            self._live = Live(
                self._render(),
                console=self._console,
                refresh_per_second=refresh_rate,
                transient=False,
            )
            self._live.__enter__()
            self._refresh(force=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._live is not None:
            # Ensure the final snapshot is rendered before closing live context.
            self._refresh(force=True)
            self._live.__exit__(exc_type, exc, tb)
            self._live = None
        return False

    def update(
        self,
        *,
        stats: ExportStats,
        split_counts: Mapping[str, int],
        split_durations: Mapping[str, float],
        run_split_durations: Mapping[str, float],
        duration_by_source: Mapping[str, float],
        run_duration_by_source: Mapping[str, float],
        resume_total_units: Optional[int],
        resume_units_completed: int,
        missing_clips: Optional[int] = None,
        missing_clips_total: Optional[int] = None,
    ) -> None:
        if not self.enabled:
            return

        now = monotonic()
        if self._start_time is None:
            self._start_time = now
        elapsed = now - self._start_time if self._start_time is not None else 0.0

        eta_seconds: Optional[float] = None
        effective_processed = self._event_offset + stats.total_events
        if (
            self._total_events
            and self._total_events > 0
            and effective_processed > 0
            and elapsed > 0
        ):
            remaining = max(self._total_events - effective_processed, 0)
            if remaining == 0:
                eta_seconds = 0.0
            else:
                rate = effective_processed / elapsed
                if rate > 0:
                    eta_seconds = remaining / rate

        resume_eta_seconds: Optional[float] = None
        resume_units_remaining: Optional[int] = None
        if resume_total_units is not None and resume_total_units > 0:
            completed = min(resume_units_completed, resume_total_units)
            remaining_units = max(resume_total_units - completed, 0)
            resume_units_remaining = remaining_units
            if remaining_units == 0:
                resume_eta_seconds = 0.0
            elif completed > 0 and elapsed > 0:
                unit_rate = completed / elapsed
                if unit_rate > 0:
                    resume_eta_seconds = remaining_units / unit_rate

        heal_eta_seconds: Optional[float] = None
        healed_so_far: Optional[int] = None
        if missing_clips_total is not None and missing_clips_total >= 0:
            healed_so_far = missing_clips_total - (missing_clips or 0)
        elif missing_clips is not None:
            healed_so_far = stats.healed_clips if stats.healed_clips >= 0 else None
        if missing_clips is not None and missing_clips <= 0:
            heal_eta_seconds = 0.0
        elif (
            missing_clips is not None
            and missing_clips > 0
            and healed_so_far is not None
            and healed_so_far > 0
            and elapsed > 0
        ):
            heal_rate = healed_so_far / elapsed
            if heal_rate > 0:
                heal_eta_seconds = missing_clips / heal_rate

        overall_eta_seconds: Optional[float] = None
        for candidate in (eta_seconds, resume_eta_seconds, heal_eta_seconds):
            if candidate is None:
                continue
            candidate = max(candidate, 0.0)
            if overall_eta_seconds is None:
                overall_eta_seconds = candidate
            else:
                overall_eta_seconds = max(overall_eta_seconds, candidate)

        self._snapshot = {
            "events_processed": stats.total_events,
            "sliced_events": stats.sliced_events,
            "clips_written": stats.written_clips,
            "healed_clips": stats.healed_clips,
            "train_clips": split_counts.get("train", 0),
            "val_clips": split_counts.get("val", 0),
            "skipped_missing_audio": stats.skipped_missing_audio,
            "skipped_no_components": stats.skipped_no_components,
            "written_seconds": stats.written_seconds,
            "train_seconds": stats.train_seconds,
            "val_seconds": stats.val_seconds,
            "healed_seconds": stats.healed_seconds,
            "split_durations": dict(split_durations),
            "run_split_durations": dict(run_split_durations),
            "duration_by_source": dict(duration_by_source),
            "run_duration_by_source": dict(run_duration_by_source),
            "eta_seconds": eta_seconds,
            "resume_eta_seconds": resume_eta_seconds,
            "resume_units_remaining": resume_units_remaining,
            "missing_clips": missing_clips,
            "missing_clips_total": missing_clips_total,
            "heal_eta_seconds": heal_eta_seconds,
            "overall_eta_seconds": overall_eta_seconds,
            "resume_total_units": resume_total_units,
        }

        self._refresh()

    def _refresh(self, *, force: bool = False) -> None:
        if self._live is None:
            return

        now = monotonic()
        if not force and self._last_refresh:
            if now - self._last_refresh < self._refresh_interval:
                return

        self._live.update(self._render(), refresh=True)
        self._last_refresh = now

    def _render(self):  # type: ignore[override]
        if not self.enabled or Table is None:
            return ""

        data = self._snapshot

        table_kwargs: Dict[str, object] = {"title": "Dataset Export Progress", "expand": True}
        if box is not None:
            table_kwargs["box"] = box.SIMPLE_HEAD
        summary_table = Table(**table_kwargs)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right", style="magenta")
        summary_table.add_row("Events processed", _format_count(data.get("events_processed")))
        summary_table.add_row("Audio slices", _format_count(data.get("sliced_events")))
        summary_table.add_row("Clips written", _format_count(data.get("clips_written")))
        healed_clips_val = data.get("healed_clips")
        if healed_clips_val:
            summary_table.add_row("Healed clips", _format_count(healed_clips_val))
        summary_table.add_row("Train clips", _format_count(data.get("train_clips")))
        summary_table.add_row("Val clips", _format_count(data.get("val_clips")))
        summary_table.add_row(
            "Skipped (missing audio)", _format_count(data.get("skipped_missing_audio"))
        )
        summary_table.add_row(
            "Skipped (no components)", _format_count(data.get("skipped_no_components"))
        )
        summary_table.add_row("Written audio", _format_duration(data.get("written_seconds")))
        summary_table.add_row("Train audio", _format_duration(data.get("train_seconds")))
        summary_table.add_row("Val audio", _format_duration(data.get("val_seconds")))
        healed_seconds_val = data.get("healed_seconds")
        if healed_seconds_val:
            summary_table.add_row("Healed audio", _format_duration(healed_seconds_val))
        overall_eta_value = data.get("overall_eta_seconds")
        if overall_eta_value is not None:
            summary_table.add_row("Overall ETA", _format_eta(overall_eta_value))
        event_eta_value = data.get("eta_seconds")
        if event_eta_value is not None:
            summary_table.add_row("Scan ETA", _format_eta(event_eta_value))
        resume_total_units = data.get("resume_total_units")
        resume_eta_value = data.get("resume_eta_seconds")
        if resume_eta_value is not None:
            summary_table.add_row("Resume ETA", _format_eta(resume_eta_value))
            summary_table.add_row(
                "Resume units remaining", _format_count(data.get("resume_units_remaining"))
            )
        missing_clips_val = data.get("missing_clips")
        if missing_clips_val is not None and missing_clips_val > 0:
            summary_table.add_row("Missing clips to heal", _format_count(missing_clips_val))
            total_missing_number = _coerce_number(data.get("missing_clips_total"))
            if total_missing_number is not None:
                healed_this_run = max(total_missing_number - float(missing_clips_val), 0.0)
                summary_table.add_row("Healed this run", _format_count(healed_this_run))
            heal_eta = data.get("heal_eta_seconds")
            if heal_eta is not None:
                summary_table.add_row("Heal ETA", _format_eta(heal_eta))

        tables: List[object] = [summary_table]

        split_durations = data.get("split_durations")
        run_split = data.get("run_split_durations")
        if isinstance(split_durations, Mapping) and split_durations:
            split_kwargs: Dict[str, object] = {"title": "Per-split Audio Seconds", "expand": True}
            if box is not None:
                split_kwargs["box"] = box.SIMPLE
            split_table = Table(**split_kwargs)
            split_table.add_column("Split", style="cyan")
            split_table.add_column("Total", justify="right", style="magenta")
            split_table.add_column("Run", justify="right", style="green")
            for split in sorted(split_durations):
                total_seconds = split_durations.get(split, 0.0)
                run_seconds = 0.0
                if isinstance(run_split, Mapping):
                    run_seconds = float(run_split.get(split, 0.0))
                split_table.add_row(
                    str(split),
                    _format_duration(total_seconds),
                    _format_duration(run_seconds),
                )
            tables.append(split_table)

        total_sources = data.get("duration_by_source")
        run_sources = data.get("run_duration_by_source")
        if isinstance(total_sources, Mapping) and total_sources:
            source_kwargs: Dict[str, object] = {"title": "Top Audio Sources", "expand": True}
            if box is not None:
                source_kwargs["box"] = box.SIMPLE
            source_table = Table(**source_kwargs)
            source_table.add_column("Source", style="cyan")
            source_table.add_column("Total", justify="right", style="magenta")
            source_table.add_column("Run", justify="right", style="green")

            run_map = dict(run_sources) if isinstance(run_sources, Mapping) else {}
            combined_sources = set(total_sources.keys()) | set(run_map.keys())
            sorted_sources = sorted(
                combined_sources,
                key=lambda name: float(total_sources.get(name, 0.0)),
                reverse=True,
            )[:8]
            for source in sorted_sources:
                total_seconds = float(total_sources.get(source, 0.0))
                run_seconds = float(run_map.get(source, 0.0))
                label = source or "<unknown>"
                source_table.add_row(
                    label,
                    _format_duration(total_seconds),
                    _format_duration(run_seconds if run_seconds else 0.0),
                )
            tables.append(source_table)

        if not tables:
            return ""

        if Panel is not None:
            if Group is not None and len(tables) > 1:
                content = Group(*tables)
            else:
                content = tables[0]
            return Panel(content, title="Training Export Status", border_style="bright_blue")

        if len(tables) == 1:
            return tables[0]
        if Group is not None:
            return Group(*tables)
        return "\n\n".join(str(table) for table in tables)

def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Path to events JSONL manifest")
    parser.add_argument("output", type=Path, help="Destination dataset directory")
    parser.add_argument(
        "--audio-root",
        type=Path,
        help="Optional fallback root used to resolve relative audio paths",
    )
    parser.add_argument(
        "--audio-root-map",
        action="append",
        default=[],
        metavar="SOURCE=PATH",
        help="Override audio root per source_set (repeatable)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help="Target sample rate for exported clips (default: 44100)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Fraction of sessions allocated to the validation split (default: 0.1)",
    )
    parser.add_argument(
        "--clip-fanout",
        type=int,
        help=(
            "Number of leading characters (after removing hyphens) from the clip_id used to "
            "create fanout directories under split/audio. Default reuses the value from an "
            "existing dataset or falls back to 0 (flat structure)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional cap on processed events (useful for smoke tests)",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=10_000,
        help="Emit a status update every N processed events when rich is unavailable (default: 10000)",
    )
    parser.add_argument(
        "--pad-to",
        type=float,
        help="Optionally zero-pad slices to at least this many seconds",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow rewriting an existing dataset directory",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip clips that already exist on disk (useful for restarts)",
    )
    parser.add_argument(
        "--manifest-total",
        type=int,
        help="Optional hint for total manifest events to improve progress estimates",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write a copy of console output to this file",
    )
    parser.add_argument(
        "--disable-rich",
        action="store_true",
        help="Disable rich console enhancements even if the dependency is installed",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate manifest paths and labels without writing any dataset artifacts",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        help="Write verification or export summary to this JSON file",
    )
    parser.add_argument(
        "--expected-duration-csv",
        type=Path,
        help="Write per-source duration breakdown to this CSV (verification: expected, export: actual)",
    )
    parser.add_argument(
        "--force-rich",
        action="store_true",
        help="Force-enable rich console rendering even when stdout is not a TTY",
    )
    parser.add_argument(
        "--write-workers",
        type=int,
        help=(
            "Number of background writer threads to use. Default chooses an auto-tuned value; "
            "set to 0 or a negative number to disable the writer thread pool."
        ),
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=0,
        help=(
            "Write metadata and label checkpoints every N processed events. "
            "Use 0 to disable mid-run checkpoints."
        ),
    )
    parser.add_argument(
        "--heal-missing-clips",
        action="store_true",
        help=(
            "When resuming, rewrite clips whose audio files are missing. This may perform many disk checks."
        ),
    )
    return parser.parse_args(argv)


def parse_audio_root_map(entries: Iterable[str]) -> Dict[str, List[Path]]:
    mapping: Dict[str, List[Path]] = {}
    for entry in entries:
        if not entry:
            continue
        if "=" not in entry:
            raise SystemExit("--audio-root-map entries must use SOURCE=PATH syntax")
        source, raw_path = entry.split("=", 1)
        source = source.strip()
        if not source:
            raise SystemExit("--audio-root-map entries must define a SOURCE preceding '='")
        path_obj = Path(raw_path.strip()).expanduser().resolve()
        # Preserve user-provided order so the first entry remains the primary lookup.
        mapping.setdefault(source, []).append(path_obj)
    return mapping


def estimate_manifest_event_count(manifest_path: Path) -> Optional[int]:
    try:
        with manifest_path.open("rb") as handle:
            count = 0
            last_byte = b"\n"
            while True:
                chunk = handle.read(4_194_304)
                if not chunk:
                    break
                count += chunk.count(b"\n")
                last_byte = chunk[-1:]
            if count == 0:
                if last_byte and last_byte != b"\n":
                    return 1
                return 0
            if last_byte != b"\n":
                count += 1
            return count
    except OSError:
        return None


def iter_manifest_events(manifest_path: Path) -> Iterator[Mapping[str, object]]:
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse JSON on line {line_number}: {exc}") from exc
            yield event


def resolve_audio_path(
    audio_value: str,
    *,
    source_set: str,
    default_root: Optional[Path],
    overrides: Mapping[str, Sequence[Path]],
) -> Optional[Path]:
    candidate = Path(audio_value)
    if candidate.is_file():
        return candidate
    override_roots = overrides.get(source_set)
    if override_roots:
        for override_root in override_roots:
            joined = override_root / audio_value
            if joined.is_file():
                return joined
    if default_root is not None:
        joined = default_root / audio_value
        if joined.is_file():
            return joined
    return None


def _compute_slice_parameters(
    event: Mapping[str, object],
    *,
    default_preroll: float,
    default_post: float,
) -> Tuple[float, float, float]:
    onset_val = _coerce_number(event.get("onset_time"))
    onset_seconds = float(onset_val) if onset_val is not None else 0.0

    context = event.get("context_ms") or {}
    if isinstance(context, Mapping):
        preroll_raw = _coerce_number(context.get("pre"))
        post_raw = _coerce_number(context.get("post"))
        preroll_ms = float(preroll_raw) if preroll_raw is not None else float(default_preroll)
        post_ms = float(post_raw) if post_raw is not None else float(default_post)
    else:
        preroll_ms = float(default_preroll)
        post_ms = float(default_post)

    preroll_seconds = max(preroll_ms / 1000.0, 0.0)
    post_seconds = max(post_ms / 1000.0, 0.0)
    duration_seconds = preroll_seconds + post_seconds

    if duration_seconds <= 0:
        duration_override = _coerce_number(event.get("duration_seconds"))
        if duration_override is not None and duration_override > 0:
            duration_seconds = float(duration_override)

    if duration_seconds <= 0:
        duration_seconds = FALLBACK_DURATION_SECONDS

    return onset_seconds, preroll_seconds, duration_seconds


def determine_slice_request(
    event: Mapping[str, object],
    *,
    resolved_path: Path,
    default_preroll: float,
    default_post: float,
) -> SliceRequest:
    onset_seconds, preroll_seconds, duration_seconds = _compute_slice_parameters(
        event,
        default_preroll=default_preroll,
        default_post=default_post,
    )

    return SliceRequest(
        audio_path=resolved_path,
        onset_seconds=onset_seconds,
        preroll_seconds=preroll_seconds,
        duration_seconds=duration_seconds,
    )


def _hash_relative_path(rel_path: str) -> int:
    digest = hashlib.blake2b(rel_path.encode("utf-8"), digest_size=8)
    return int.from_bytes(digest.digest(), "big")


def _load_existing_clip_hashes(labels_path: Path, split_root: Path) -> Tuple[Set[int], Set[str]]:
    hashes: Set[int] = set()
    missing: Set[str] = set()
    if not labels_path.exists():
        return hashes, missing
    with labels_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = FILE_FIELD_PATTERN.search(line)
            if match is None:
                continue
            rel_path = match.group(1)
            hashes.add(_hash_relative_path(rel_path))
            clip_path = split_root / rel_path
            if not clip_path.exists():
                missing.add(rel_path)
    return hashes, missing


def _format_label_entry(entry: Mapping[str, object]) -> str:
    serialized = json.dumps(entry, indent=2, ensure_ascii=False)
    indented_lines = ["  " + line for line in serialized.splitlines()]
    return "\n".join(indented_lines)


def _append_json_array(path: Path, entries: Sequence[Mapping[str, object]]) -> None:
    if not entries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    formatted = ",\n".join(_format_label_entry(entry) for entry in entries)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", encoding="utf-8") as handle:
            handle.write("[\n")
            handle.write(formatted)
            handle.write("\n]\n")
        return

    with path.open("r+", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        pos = handle.tell() - 1
        # Seek backwards to the closing bracket
        while pos >= 0:
            handle.seek(pos)
            ch = handle.read(1)
            if ch not in " \t\r\n":
                break
            pos -= 1
        if pos < 0:
            handle.seek(0)
            handle.write("[\n")
            handle.write(formatted)
            handle.write("\n]\n")
            return

        if ch != "]":
            raise RuntimeError(f"Unexpected JSON terminator in {path}")

        # Determine whether existing array already has content
        prev_pos = pos - 1
        has_entries = False
        while prev_pos >= 0:
            handle.seek(prev_pos)
            prev_ch = handle.read(1)
            if prev_ch in " \t\r\n":
                prev_pos -= 1
                continue
            has_entries = prev_ch != "["
            break

        handle.seek(pos)
        if has_entries:
            handle.write(",\n")
        else:
            handle.write("\n")
        handle.write(formatted)
        handle.write("\n]\n")
        handle.truncate()


def _ensure_json_array_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("[]\n")


# LRU cache of open SoundFile read handles to reduce repeated open/close/stat calls.
# Key: resolved Path -> value: open sf.SoundFile
MAX_OPEN_SF_HANDLES = 16
_sf_handle_cache: "OrderedDict[Path, sf.SoundFile]" = OrderedDict()


def _get_soundfile_handle(path: Path) -> sf.SoundFile:
    """Return an open sf.SoundFile for `path`, using an LRU cache.

    The handle is left open for reuse. If the cache grows beyond
    MAX_OPEN_SF_HANDLES the least-recently-used handle is closed.
    """
    # Use the Path object directly as the cache key to avoid calling
    # Path.resolve() (which performs expensive realpath/lstat calls).
    key = path
    # Move existing handle to the end (most-recently-used)
    handle = _sf_handle_cache.get(key)
    if handle is not None:
        try:
            # Touch the key to update LRU ordering
            _sf_handle_cache.pop(key)
            _sf_handle_cache[key] = handle
        except Exception:
            pass
        return handle

    try:
        handle = sf.SoundFile(str(key), mode="r")
    except Exception as exc:  # keep error mapping minimal
        raise RuntimeError(f"Failed to open audio file {key}: {exc}") from exc

    _sf_handle_cache[key] = handle
    # Evict oldest if over the limit
    try:
        while len(_sf_handle_cache) > MAX_OPEN_SF_HANDLES:
            old_key, old_handle = _sf_handle_cache.popitem(last=False)
            try:
                old_handle.close()
            except Exception:
                pass
    except Exception:
        # Best-effort: ignore cache housekeeping failures
        pass

    return handle


def read_audio_slice(
    request: SliceRequest,
    *,
    target_sample_rate: int,
    pad_to_seconds: Optional[float] = None,
) -> np.ndarray:
    path = request.audio_path
    # Use the Path object itself, avoid resolve() to reduce filesystem syscalls
    key = path
    try:
        sf_file = _get_soundfile_handle(key)
        source_sr = sf_file.samplerate

        start = max(request.onset_seconds - request.preroll_seconds, 0.0)
        start_frame = int(math.floor(start * source_sr))
        if request.duration_seconds <= 0:
            frames = -1
        else:
            frames = int(math.ceil(request.duration_seconds * source_sr))

        if start_frame > 0:
            try:
                sf_file.seek(start_frame)
            except Exception:
                # If seek fails (corrupted handle), evict and reopen once
                try:
                    _sf_handle_cache.pop(key)
                except Exception:
                    pass
                sf_file = _get_soundfile_handle(key)
                sf_file.seek(start_frame)

        data = sf_file.read(frames, dtype="float32", always_2d=False)
    except RuntimeError as exc:
        # Evict problematic handle and re-raise for the caller to handle
        try:
            old = _sf_handle_cache.pop(key, None)
            if old is not None:
                try:
                    old.close()
                except Exception:
                    pass
        except Exception:
            pass
        raise RuntimeError(f"Failed to read audio slice for {path}: {exc}") from exc

    if data is None:
        data = np.array([], dtype=np.float32)

    if getattr(data, "ndim", 1) > 1:
        data = np.mean(data, axis=1)

    # The sample rate used for padding is the source rate (source_sr)
    if pad_to_seconds is not None and pad_to_seconds > 0:
        target_frames = int(math.ceil(pad_to_seconds * source_sr))
        if data.shape[0] < target_frames:
            padded = np.zeros(target_frames, dtype=np.float32)
            padded[: data.shape[0]] = data
            data = padded

    if source_sr != target_sample_rate and data.size > 0:
        data = librosa.resample(data, orig_sr=source_sr, target_sr=target_sample_rate)

    return data.astype(np.float32, copy=False)


def ensure_output_dirs(dataset_root: Path, *, overwrite: bool, resume: bool) -> None:
    """Prepare the dataset directory while respecting overwrite/resume semantics."""

    if overwrite and resume:
        raise SystemExit("--overwrite and --resume are mutually exclusive")

    if dataset_root.exists():
        if overwrite:
            shutil.rmtree(dataset_root)
        elif resume:
            for split in ("train", "val"):
                (dataset_root / split / "audio").mkdir(parents=True, exist_ok=True)
            return
        else:
            raise SystemExit(
                f"Destination {dataset_root} already exists. Pass --overwrite to rebuild the bundle or --resume to append."
            )

    dataset_root.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val"):
        (dataset_root / split / "audio").mkdir(parents=True, exist_ok=True)


def assign_split(session_id: str, *, val_ratio: float) -> str:
    digest = hashlib.sha1(session_id.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    return "val" if value < val_ratio else "train"


def build_dataset(
    *,
    manifest_path: Path,
    dataset_root: Path,
    audio_root: Optional[Path],
    audio_root_overrides: Mapping[str, Sequence[Path]],
    target_sample_rate: int,
    val_ratio: float,
    limit: Optional[int],
    pad_to_seconds: Optional[float],
    progress_interval: int,
    resume: bool,
    logger: OutputLogger,
    progress_total: Optional[int],
    write_workers: Optional[int] = None,
    heal_missing_clips: bool = False,
    checkpoint_every: Optional[int] = None,
    clip_fanout: Optional[int] = None,
) -> Dict[str, object]:
    requested_clip_fanout = clip_fanout
    clip_fanout = DEFAULT_CLIP_FANOUT if clip_fanout is None else max(0, int(clip_fanout))
    if clip_fanout > 8:
        clip_fanout = 8
    stats = ExportStats()
    component_index: Dict[str, int] = {}
    components: List[str] = []
    label_entries: Dict[str, List[Dict[str, object]]] = {"train": [], "val": []}
    per_label_counts: Counter[str] = Counter()
    run_label_counts: Counter[str] = Counter()
    split_counts: Dict[str, int] = {"train": 0, "val": 0}
    new_split_counts: Dict[str, int] = {"train": 0, "val": 0}
    split_durations: Dict[str, float] = {"train": 0.0, "val": 0.0}
    run_split_durations: Dict[str, float] = {"train": 0.0, "val": 0.0}
    duration_by_source: DefaultDict[str, float] = defaultdict(float)
    run_duration_by_source: DefaultDict[str, float] = defaultdict(float)
    total_healed_split_counts: Dict[str, int] = {"train": 0, "val": 0}
    run_healed_split_counts: Dict[str, int] = {"train": 0, "val": 0}
    total_healed_split_durations: Dict[str, float] = {"train": 0.0, "val": 0.0}
    run_healed_split_durations: Dict[str, float] = {"train": 0.0, "val": 0.0}
    total_healed_duration_by_source: DefaultDict[str, float] = defaultdict(float)
    run_healed_duration_by_source: DefaultDict[str, float] = defaultdict(float)
    duration_by_source_initialized = False
    existing_file_hashes: Dict[str, Set[int]] = {"train": set(), "val": set()}
    missing_clip_paths: Dict[str, Set[str]] = {"train": set(), "val": set()}
    missing_clip_units_remaining = 0
    missing_clip_units_total: Optional[int] = None
    previous_events_processed = 0
    resume_total_units: Optional[int] = None
    resume_units_completed = 0
    previous_metadata: Optional[Mapping[str, object]] = None
    audio_resolution_cache: Dict[Tuple[str, str], Optional[Path]] = {}
    checkpoint_interval = checkpoint_every if checkpoint_every and checkpoint_every > 0 else None
    checkpoint_dirty = False

    if resume:
        metadata_path_existing = dataset_root / "metadata.json"
        if metadata_path_existing.exists():
            try:
                with metadata_path_existing.open("r", encoding="utf-8") as handle:
                    loaded_metadata = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse {metadata_path_existing}: {exc}") from exc
            if isinstance(loaded_metadata, Mapping):
                previous_metadata = loaded_metadata
                prev_fanout = _coerce_int(loaded_metadata.get("clip_fanout"))
                if prev_fanout is not None:
                    prev_fanout = max(prev_fanout, 0)
                    if requested_clip_fanout is not None and prev_fanout != max(0, requested_clip_fanout):
                        raise ValueError(
                            "Clip fanout mismatch: existing dataset was exported with fanout "
                            f"{prev_fanout} but --clip-fanout={requested_clip_fanout} was requested."
                        )
                    clip_fanout = min(prev_fanout, 8)
                prev_total_events = _coerce_int(loaded_metadata.get("total_events_processed"))
                if prev_total_events is not None:
                    previous_events_processed = max(previous_events_processed, prev_total_events)
                prev_split_durations = loaded_metadata.get("split_durations_seconds")
                if isinstance(prev_split_durations, Mapping):
                    for split in ("train", "val"):
                        duration_val = _coerce_number(prev_split_durations.get(split))
                        if duration_val is not None:
                            split_durations[split] = duration_val
                prev_duration_by_source = loaded_metadata.get("duration_seconds_by_source")
                if isinstance(prev_duration_by_source, Mapping):
                    for source, value in prev_duration_by_source.items():
                        number = _coerce_number(value)
                        if number is not None:
                            duration_by_source[str(source)] = float(number)
                    if duration_by_source:
                        duration_by_source_initialized = True
                prev_split_counts = loaded_metadata.get("split_counts")
                if isinstance(prev_split_counts, Mapping):
                    for split in ("train", "val"):
                        count_val = _coerce_int(prev_split_counts.get(split))
                        if count_val is not None:
                            split_counts[split] = count_val
                prev_label_counts = loaded_metadata.get("label_counts")
                if isinstance(prev_label_counts, Mapping):
                    for label, value in prev_label_counts.items():
                        count_val = _coerce_int(value)
                        if count_val is not None:
                            per_label_counts[str(label)] = count_val
                prev_healed_counts = loaded_metadata.get("healed_split_counts")
                if isinstance(prev_healed_counts, Mapping):
                    for split in ("train", "val"):
                        healed_val = _coerce_int(prev_healed_counts.get(split))
                        if healed_val is not None:
                            total_healed_split_counts[split] = healed_val
                prev_healed_durations = loaded_metadata.get("healed_split_durations_seconds")
                if isinstance(prev_healed_durations, Mapping):
                    for split in ("train", "val"):
                        healed_duration = _coerce_number(prev_healed_durations.get(split))
                        if healed_duration is not None:
                            total_healed_split_durations[split] = healed_duration
                prev_healed_sources = loaded_metadata.get("healed_duration_seconds_by_source")
                if isinstance(prev_healed_sources, Mapping):
                    for source, value in prev_healed_sources.items():
                        number = _coerce_number(value)
                        if number is not None:
                            total_healed_duration_by_source[str(source)] = float(number)

        components_path = dataset_root / "components.json"
        if components_path.exists():
            try:
                with components_path.open("r", encoding="utf-8") as handle:
                    existing_components = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse {components_path}: {exc}") from exc
            if isinstance(existing_components, Mapping):
                raw_components = existing_components.get("components")
                if isinstance(raw_components, list):
                    components = [str(item) for item in raw_components]
                raw_index = existing_components.get("component_index")
                if isinstance(raw_index, Mapping):
                    for label, idx in raw_index.items():
                        try:
                            component_index[str(label)] = int(idx)
                        except (TypeError, ValueError):
                            continue
            if not component_index and components:
                component_index = {label: idx for idx, label in enumerate(components)}

        if per_label_counts and components:
            for label in per_label_counts:
                if label not in component_index:
                    component_index[label] = len(components)
                    components.append(label)

        for split in ("train", "val"):
            labels_path = dataset_root / split / f"{split}_labels.json"
            if not labels_path.exists():
                continue
            logger.print(f"Indexing existing {split} clips for resume...")
            split_root = dataset_root / split
            hashes, missing = _load_existing_clip_hashes(labels_path, split_root)
            existing_file_hashes[split] = hashes
            missing_clip_paths[split] = missing
            missing_clip_units_remaining += len(missing)
            logger.print(
                f"Indexed {len(hashes):,} {split} clips from previous run; {len(missing):,} missing on disk."
            )
            if split_counts[split] == 0:
                split_counts[split] = len(hashes)

    logger.print(f"Effective clip directory fanout: {clip_fanout}")

    if resume:
        missing_clip_units_total = missing_clip_units_remaining

    if resume:
        # Use remaining manifest events as the primary "resume" work unit.
        # Missing clips to heal are shown separately so we don't mix per-event
        # and per-clip granularities (which produced misleading ETAs).
        base_remaining_events = 0
        if limit is not None:
            base_remaining_events = max(limit, 0)
        elif progress_total is not None:
            base_remaining_events = max(progress_total - previous_events_processed, 0)
        resume_units = base_remaining_events
        resume_total_units = resume_units if resume_units > 0 else None
    else:
        missing_clip_units_remaining = 0

    initial_split_counts = dict(split_counts)

    if duration_by_source and not duration_by_source_initialized:
        duration_by_source_initialized = True

    if limit is not None:
        progress_target_total: Optional[int] = previous_events_processed + max(limit, 0)
    else:
        progress_target_total = progress_total

    event_offset = previous_events_processed if resume else 0

    manifest_sha1 = hashlib.sha1()
    if limit is not None:
        task_total = max(limit, 0)
    elif progress_target_total is not None:
        remaining_hint = max(progress_target_total - event_offset, 0)
        task_total = remaining_hint if remaining_hint > 0 else None
    else:
        task_total = None
    progress_fields = {
        "clips": stats.written_clips + stats.healed_clips,
        "healed": stats.healed_clips,
        "train": split_counts["train"],
        "val": split_counts["val"],
        "skipped": 0,
        "heal_remaining": missing_clip_units_remaining,
        "eta": "-",
    }

    class _ProgressStub:
        enabled = False

        def update(self, *args, **kwargs) -> None:  # type: ignore[override]
            return None

    live_display = DatasetProgressDisplay(
        logger,
        total=progress_target_total,
        event_offset=event_offset,
    )

    # Background writer pool: submit WAV write tasks to a thread pool so the
    # main loop can continue slicing while disk writes complete in parallel.
    writer_executor: Optional[ThreadPoolExecutor]
    if write_workers and write_workers > 0:
        writer_executor = ThreadPoolExecutor(
            max_workers=write_workers,
            thread_name_prefix="dataset-writer",
        )
    else:
        writer_executor = None
    writer_futures: List[Future[object]] = []
    writer_error: Optional[BaseException] = None

    def wait_for_writer_futures() -> None:
        nonlocal writer_error
        if writer_executor is None or not writer_futures:
            return
        for fut in as_completed(list(writer_futures)):
            try:
                fut.result()
            except Exception as exc:
                logger.print(f"Background write failed: {exc}")
                if writer_error is None:
                    writer_error = exc
        writer_futures.clear()
        if writer_error is not None:
            raise RuntimeError("Background writer failed; export aborted.") from writer_error

    run_start_time = monotonic()
    current_overall_eta: Optional[float] = None
    current_event_eta: Optional[float] = None
    current_resume_eta: Optional[float] = None
    current_heal_eta: Optional[float] = None

    def _compute_eta_metrics() -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        elapsed = monotonic() - run_start_time
        if elapsed < 0:
            elapsed = 0.0

        event_eta: Optional[float] = None
        total_target = progress_target_total
        effective_processed = event_offset + stats.total_events
        if total_target is not None and total_target > 0:
            remaining_events = max(total_target - effective_processed, 0)
            if remaining_events == 0:
                event_eta = 0.0
            elif effective_processed > 0 and elapsed > 0:
                rate = effective_processed / elapsed
                if rate > 0:
                    event_eta = remaining_events / rate

        resume_eta: Optional[float] = None
        if resume_total_units is not None and resume_total_units > 0:
            completed_units = min(resume_units_completed, resume_total_units)
            remaining_units = max(resume_total_units - completed_units, 0)
            if remaining_units == 0:
                resume_eta = 0.0
            elif completed_units > 0 and elapsed > 0:
                unit_rate = completed_units / elapsed
                if unit_rate > 0:
                    resume_eta = remaining_units / unit_rate

        heal_eta: Optional[float] = None
        healed_so_far: Optional[float] = None
        if missing_clip_units_total is not None:
            healed_so_far = float(missing_clip_units_total - missing_clip_units_remaining)
        elif missing_clip_units_remaining > 0:
            healed_so_far = float(stats.healed_clips)

        if missing_clip_units_remaining <= 0:
            heal_eta = 0.0 if missing_clip_units_total is not None else None
        elif (
            healed_so_far is not None
            and healed_so_far > 0
            and elapsed > 0
        ):
            heal_rate = healed_so_far / elapsed
            if heal_rate > 0:
                heal_eta = missing_clip_units_remaining / heal_rate

        overall_eta: Optional[float] = None
        for candidate in (event_eta, resume_eta, heal_eta):
            if candidate is None:
                continue
            candidate = max(candidate, 0.0)
            if overall_eta is None:
                overall_eta = candidate
            else:
                overall_eta = max(overall_eta, candidate)

        return overall_eta, event_eta, resume_eta, heal_eta

    def refresh_eta_metrics() -> None:
        nonlocal current_overall_eta, current_event_eta, current_resume_eta, current_heal_eta
        current_overall_eta, current_event_eta, current_resume_eta, current_heal_eta = _compute_eta_metrics()

    def update_run_stat_fields() -> None:
        stats.train_clips = new_split_counts["train"]
        stats.val_clips = new_split_counts["val"]
        stats.train_seconds = run_split_durations["train"] + run_healed_split_durations["train"]
        stats.val_seconds = run_split_durations["val"] + run_healed_split_durations["val"]
        stats.written_seconds = stats.train_seconds + stats.val_seconds

    def _combined_run_split_durations() -> Dict[str, float]:
        return {
            "train": run_split_durations["train"] + run_healed_split_durations["train"],
            "val": run_split_durations["val"] + run_healed_split_durations["val"],
        }

    def _combined_run_duration_by_source() -> Dict[str, float]:
        combined: Dict[str, float] = dict(run_duration_by_source)
        for source, value in run_healed_duration_by_source.items():
            combined[source] = combined.get(source, 0.0) + value
        return combined

    def build_metadata_dict() -> Dict[str, object]:
        run_stats = stats.as_dict()
        aggregate_stats: Dict[str, Union[int, float]] = {}
        if previous_metadata is not None:
            prev_stats_raw = previous_metadata.get("statistics")
            if isinstance(prev_stats_raw, Mapping):
                for key, value in prev_stats_raw.items():
                    _merge_stat(aggregate_stats, key, value)

        for key, value in run_stats.items():
            _merge_stat(aggregate_stats, key, value)

        aggregate_stats["train_clips"] = split_counts["train"]
        aggregate_stats["val_clips"] = split_counts["val"]
        aggregate_stats["written_clips"] = split_counts["train"] + split_counts["val"]
        aggregate_stats["train_seconds"] = split_durations["train"]
        aggregate_stats["val_seconds"] = split_durations["val"]
        aggregate_stats["written_seconds"] = split_durations["train"] + split_durations["val"]
        aggregate_stats["skipped_total"] = aggregate_stats.get("skipped_missing_audio", 0) + aggregate_stats.get(
            "skipped_no_components", 0
        )

        total_events_processed = stats.total_events
        if previous_metadata is not None:
            prev_total = _coerce_int(previous_metadata.get("total_events_processed"))
            if prev_total is not None:
                total_events_processed += prev_total

        metadata = {
            "manifest": manifest_path.as_posix(),
            "dataset_root": dataset_root.as_posix(),
            "manifest_sha1": manifest_sha1.hexdigest(),
            "sample_rate": target_sample_rate,
            "clip_fanout": clip_fanout,
            "val_ratio": val_ratio,
            "limit": limit,
            "total_events_processed": total_events_processed,
            "statistics": aggregate_stats,
            "run_statistics": run_stats,
            "split_counts": dict(split_counts),
            "split_durations_seconds": {k: float(v) for k, v in split_durations.items()},
            "label_counts": dict(per_label_counts),
            "run_label_counts": dict(run_label_counts),
            "run_split_durations_seconds": {k: float(v) for k, v in run_split_durations.items()},
            "duration_seconds_by_source": {k: float(v) for k, v in duration_by_source.items()},
            "run_duration_seconds_by_source": {k: float(v) for k, v in run_duration_by_source.items()},
            "healed_split_counts": dict(total_healed_split_counts),
            "healed_split_durations_seconds": {
                k: float(v) for k, v in total_healed_split_durations.items()
            },
            "healed_duration_seconds_by_source": {
                k: float(v) for k, v in total_healed_duration_by_source.items()
            },
            "run_healed_split_counts": dict(run_healed_split_counts),
            "run_healed_split_durations_seconds": {
                k: float(v) for k, v in run_healed_split_durations.items()
            },
            "run_healed_duration_seconds_by_source": {
                k: float(v) for k, v in run_healed_duration_by_source.items()
            },
        }
        return metadata

    def write_artifacts(*, final: bool, reason: Optional[str] = None) -> Dict[str, object]:
        nonlocal checkpoint_dirty
        wait_for_writer_futures()
        update_run_stat_fields()

        components_info = {
            "components": components,
            "num_classes": len(components),
            "component_index": component_index,
            "counts": dict(per_label_counts),
        }

        for split, entries in label_entries.items():
            labels_path = dataset_root / split / f"{split}_labels.json"
            if entries:
                _append_json_array(labels_path, entries)
                entries.clear()
            elif final:
                _ensure_json_array_file(labels_path)

        components_path = dataset_root / "components.json"
        with components_path.open("w", encoding="utf-8") as handle:
            json.dump(components_info, handle, indent=2)

        metadata = build_metadata_dict()
        metadata_path = dataset_root / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

        if not final:
            if reason:
                logger.print(
                    f"Checkpoint saved ({reason}) at {stats.total_events:,} events ({stats.written_clips:,} clips)."
                )
            else:
                logger.print(
                    f"Checkpoint saved at {stats.total_events:,} events ({stats.written_clips:,} clips)."
                )

        checkpoint_dirty = False
        return metadata

    def flush_checkpoint(reason: str, *, force: bool = False) -> None:
        if not checkpoint_dirty:
            return
        if checkpoint_interval is None and not force:
            return
        write_artifacts(final=False, reason=reason)

    def _schedule_write(path: Path, data: np.ndarray, sr: int) -> None:
        if writer_error is not None:
            raise RuntimeError("Cannot schedule additional writes after a background failure.") from writer_error
        if writer_executor is None:
            sf.write(path, data, sr, subtype="PCM_16")
            return
        fut = writer_executor.submit(sf.write, path, data, sr, "PCM_16")
        writer_futures.append(fut)
        if len(writer_futures) >= MAX_PENDING_WRITES:
            wait_for_writer_futures()

    progress_context = (
        ProgressAdapter(
            logger,
            "Processing manifest events",
            total=task_total,
            fields=progress_fields,
        )
        if not live_display.enabled
        else nullcontext(_ProgressStub())
    )

    with progress_context as progress_tracker, live_display as live_display_manager:
        live_display_manager.update(
            stats=stats,
            split_counts=split_counts,
            split_durations=split_durations,
            run_split_durations=_combined_run_split_durations(),
            duration_by_source=duration_by_source,
            run_duration_by_source=_combined_run_duration_by_source(),
            resume_total_units=resume_total_units,
            resume_units_completed=resume_units_completed,
            missing_clips=missing_clip_units_remaining,
            missing_clips_total=missing_clip_units_total,
        )
        refresh_eta_metrics()

        live_enabled = live_display_manager.enabled
        progress_updates_enabled = progress_tracker.enabled

        refresh_eta_metrics()
        if progress_updates_enabled:
            progress_tracker.update(
                advance=0,
                clips=stats.written_clips + stats.healed_clips,
                healed=stats.healed_clips,
                train=split_counts["train"],
                val=split_counts["val"],
                skipped=stats.skipped_total,
                heal_remaining=missing_clip_units_remaining,
                eta=_format_eta(current_overall_eta),
            )
        elif not live_enabled:
            logger.print(
                "Streaming manifest events... the first update will appear once audio slices begin."
            )

        first_progress_message_sent = False
        text_update_interval = max(min(progress_interval, 1_000), 1)

        def report_progress() -> None:
            nonlocal first_progress_message_sent
            skipped = stats.skipped_total
            refresh_eta_metrics()
            if progress_updates_enabled:
                progress_tracker.update(
                    advance=1,
                    clips=stats.written_clips + stats.healed_clips,
                    healed=stats.healed_clips,
                    train=split_counts["train"],
                    val=split_counts["val"],
                    skipped=skipped,
                    heal_remaining=missing_clip_units_remaining,
                    eta=_format_eta(current_overall_eta),
                )
            if live_enabled:
                if not first_progress_message_sent and stats.total_events > 0:
                    logger.print(
                        "First manifest event processed; live dashboard above will refresh continuously."
                    )
                    first_progress_message_sent = True
            elif (not progress_updates_enabled) and progress_interval and stats.total_events % progress_interval == 0:
                clip_summary = f"{stats.written_clips:,} new"
                if stats.healed_clips:
                    clip_summary += f", {stats.healed_clips:,} healed"
                heal_status = ""
                if missing_clip_units_total:
                    healed_so_far = missing_clip_units_total - missing_clip_units_remaining
                    heal_status = (
                        f", heal_remaining={missing_clip_units_remaining:,}"
                        f" ({max(healed_so_far, 0):,} healed this run)"
                    )
                elif missing_clip_units_remaining:
                    heal_status = f", heal_remaining={missing_clip_units_remaining:,}"
                eta_status = ""
                if current_overall_eta is not None:
                    eta_status = f", overall_eta={_format_eta(current_overall_eta)}"
                logger.print(
                    f"Processed {stats.total_events:,} events -> {clip_summary} clips "
                    f"(train={split_counts['train']:,}, val={split_counts['val']:,}, skipped={skipped:,}{heal_status}{eta_status})"
                )
            elif progress_updates_enabled and stats.total_events % text_update_interval == 0:
                clip_summary = f"{stats.written_clips:,} new"
                if stats.healed_clips:
                    clip_summary += f", {stats.healed_clips:,} healed"
                heal_status = ""
                if missing_clip_units_total:
                    healed_so_far = missing_clip_units_total - missing_clip_units_remaining
                    heal_status = (
                        f", heal_remaining={missing_clip_units_remaining:,}"
                        f" ({max(healed_so_far, 0):,} healed this run)"
                    )
                elif missing_clip_units_remaining:
                    heal_status = f", heal_remaining={missing_clip_units_remaining:,}"
                eta_status = ""
                if current_overall_eta is not None:
                    eta_status = f", overall_eta={_format_eta(current_overall_eta)}"
                logger.print(
                    f"Processed {stats.total_events:,} events -> {clip_summary} clips "
                    f"(train={split_counts['train']:,}, val={split_counts['val']:,}, skipped={skipped:,}{heal_status}{eta_status})"
                )

            live_display_manager.update(
                stats=stats,
                split_counts=split_counts,
                split_durations=split_durations,
                run_split_durations=_combined_run_split_durations(),
                duration_by_source=duration_by_source,
                run_duration_by_source=_combined_run_duration_by_source(),
                resume_total_units=resume_total_units,
                resume_units_completed=resume_units_completed,
                missing_clips=missing_clip_units_remaining,
                missing_clips_total=missing_clip_units_total,
            )
            refresh_eta_metrics()

        for event in iter_manifest_events(manifest_path):
            if limit is not None and stats.total_events >= limit:
                break

            raw_line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
            manifest_sha1.update(raw_line.encode("utf-8"))
            stats.total_events += 1
            if resume_total_units is not None:
                resume_units_completed += 1

            components_data = event.get("components")
            if not isinstance(components_data, list) or not components_data:
                stats.skipped_no_components += 1
                report_progress()
                continue

            audio_value = event.get("audio_path")
            if not isinstance(audio_value, str) or not audio_value:
                stats.skipped_missing_audio += 1
                report_progress()
                continue

            source_set = str(event.get("source_set") or "")
            resolution_key = (audio_value, source_set)
            if resolution_key in audio_resolution_cache:
                resolved_path = audio_resolution_cache[resolution_key]
            else:
                resolved_path = resolve_audio_path(
                    audio_value,
                    source_set=source_set,
                    default_root=audio_root,
                    overrides=audio_root_overrides,
                )
                audio_resolution_cache[resolution_key] = resolved_path
            if resolved_path is None:
                stats.skipped_missing_audio += 1
                report_progress()
                continue

            slice_request = determine_slice_request(
                event,
                resolved_path=resolved_path,
                default_preroll=DEFAULT_PRE_ROLL_MS,
                default_post=DEFAULT_POST_TAIL_MS,
            )

            try:
                audio_slice = read_audio_slice(
                    slice_request,
                    target_sample_rate=target_sample_rate,
                    pad_to_seconds=pad_to_seconds,
                )
            except Exception:
                stats.skipped_missing_audio += 1
                report_progress()
                continue

            if audio_slice.size == 0:
                stats.skipped_missing_audio += 1
                report_progress()
                continue

            stats.sliced_events += 1
            clip_duration_seconds = float(audio_slice.shape[0]) / float(target_sample_rate)

            session_id = str(event.get("session_id") or "")
            split = assign_split(session_id, val_ratio=val_ratio)

            for component_entry in components_data:
                if not isinstance(component_entry, dict):
                    continue
                label = str(component_entry.get("label") or "").strip()
                if not label:
                    continue

                if label not in component_index:
                    component_index[label] = len(components)
                    components.append(label)

                clip_id = str(event.get("event_id") or "")
                if not clip_id:
                    clip_id = hashlib.sha1(
                        f"{session_id}:{stats.total_events}:{label}".encode("utf-8")
                    ).hexdigest()

                clip_relative_path = _construct_clip_relative_path(
                    clip_id,
                    label,
                    fanout=clip_fanout,
                )
                clip_path = dataset_root / split / clip_relative_path

                relative_path = clip_relative_path.as_posix()
                clip_hash = _hash_relative_path(relative_path)
                already_recorded = clip_hash in existing_file_hashes[split]
                clip_exists = clip_path.exists()

                if already_recorded:
                    if heal_missing_clips and not clip_exists:
                        clip_path.parent.mkdir(parents=True, exist_ok=True)
                        _schedule_write(clip_path, audio_slice, target_sample_rate)
                        stats.healed_clips += 1
                        stats.healed_seconds += clip_duration_seconds
                        run_healed_split_counts[split] += 1
                        total_healed_split_counts[split] += 1
                        run_healed_split_durations[split] += clip_duration_seconds
                        total_healed_split_durations[split] += clip_duration_seconds
                        run_healed_duration_by_source[source_set] += clip_duration_seconds
                        total_healed_duration_by_source[source_set] += clip_duration_seconds
                        checkpoint_dirty = True
                        if relative_path in missing_clip_paths[split]:
                            missing_clip_paths[split].remove(relative_path)
                            if missing_clip_units_remaining > 0:
                                missing_clip_units_remaining -= 1
                    continue

                clip_path.parent.mkdir(parents=True, exist_ok=True)
                _schedule_write(clip_path, audio_slice, target_sample_rate)
                existing_file_hashes[split].add(clip_hash)

                label_entry = {
                    "file": relative_path,
                    "label": label,
                    "component_idx": component_index[label],
                    "event_id": event.get("event_id"),
                    "session_id": session_id,
                    "source_set": source_set,
                    "duration_seconds": clip_duration_seconds,
                }
                label_entries[split].append(label_entry)
                per_label_counts[label] += 1
                run_label_counts[label] += 1
                stats.written_clips += 1
                split_counts[split] += 1
                new_split_counts[split] += 1
                split_durations[split] += clip_duration_seconds
                run_split_durations[split] += clip_duration_seconds
                duration_by_source[source_set] += clip_duration_seconds
                run_duration_by_source[source_set] += clip_duration_seconds
                stats.written_seconds += clip_duration_seconds
                if split == "train":
                    stats.train_seconds += clip_duration_seconds
                else:
                    stats.val_seconds += clip_duration_seconds
                checkpoint_dirty = True

            report_progress()

            if checkpoint_interval and stats.total_events % checkpoint_interval == 0:
                flush_checkpoint("interval")

        if progress_updates_enabled:
            progress_tracker.update(
                advance=0,
                clips=stats.written_clips + stats.healed_clips,
                healed=stats.healed_clips,
                train=split_counts["train"],
                val=split_counts["val"],
                skipped=stats.skipped_total,
                heal_remaining=missing_clip_units_remaining,
                eta=_format_eta(current_overall_eta),
            )

        live_display_manager.update(
            stats=stats,
            split_counts=split_counts,
            split_durations=split_durations,
            run_split_durations=_combined_run_split_durations(),
            duration_by_source=duration_by_source,
            run_duration_by_source=_combined_run_duration_by_source(),
            resume_total_units=resume_total_units,
            resume_units_completed=resume_units_completed,
            missing_clips=missing_clip_units_remaining,
            missing_clips_total=missing_clip_units_total,
        )
        refresh_eta_metrics()

    metadata: Dict[str, object]
    try:
        metadata = write_artifacts(final=True)
    finally:
        if writer_executor is not None:
            writer_executor.shutdown(wait=True)

        # Close any cached open SoundFile handles (best-effort cleanup).
        try:
            for handle in list(_sf_handle_cache.values()):
                try:
                    handle.close()
                except Exception:
                    pass
            _sf_handle_cache.clear()
        except Exception:
            pass

    return metadata


def verify_manifest(
    *,
    manifest_path: Path,
    audio_root: Optional[Path],
    audio_root_overrides: Mapping[str, Sequence[Path]],
    limit: Optional[int],
    progress_interval: int,
    logger: OutputLogger,
    progress_total: Optional[int],
) -> Dict[str, object]:
    stats = {
        "total_events": 0,
        "missing_audio": 0,
        "missing_components": 0,
        "resolved_audio": 0,
        "with_components": 0,
        "expected_seconds": 0.0,
    }
    per_label_counts: Counter[str] = Counter()
    missing_examples: List[Dict[str, object]] = []
    missing_sources: Counter[str] = Counter()
    expected_seconds_by_source: Dict[str, float] = defaultdict(float)

    task_total = limit if limit is not None else progress_total

    with ProgressAdapter(
        logger,
        "Verifying manifest",
        total=task_total,
        fields={
            "resolved": 0,
            "missing": 0,
        },
    ) as progress_tracker:

        def emit_progress() -> None:
            if progress_tracker.enabled:
                progress_tracker.update(
                    advance=1,
                    resolved=stats["resolved_audio"],
                    missing=stats["missing_audio"],
                )
            elif progress_interval and stats["total_events"] % progress_interval == 0:
                logger.print(
                    f"Checked {stats['total_events']:,} events -> resolved {stats['resolved_audio']:,}, missing {stats['missing_audio']:,}"
                )

        for event in iter_manifest_events(manifest_path):
            if limit is not None and stats["total_events"] >= limit:
                break

            stats["total_events"] += 1

            source_set = str(event.get("source_set") or "")

            components_data = event.get("components")
            valid_component_count = 0
            if isinstance(components_data, list) and components_data:
                stats["with_components"] += 1
                for component_entry in components_data:
                    if isinstance(component_entry, Mapping):
                        label = component_entry.get("label")
                        if isinstance(label, str) and label:
                            per_label_counts[label.strip()] += 1
                            valid_component_count += 1
            else:
                stats["missing_components"] += 1

            if valid_component_count:
                _, _, duration_seconds = _compute_slice_parameters(
                    event,
                    default_preroll=DEFAULT_PRE_ROLL_MS,
                    default_post=DEFAULT_POST_TAIL_MS,
                )
                clip_seconds = duration_seconds * valid_component_count
                stats["expected_seconds"] += clip_seconds
                expected_seconds_by_source[source_set] += clip_seconds

            audio_value = event.get("audio_path")
            if not isinstance(audio_value, str) or not audio_value:
                stats["missing_audio"] += 1
                missing_sources[source_set] += 1
                if len(missing_examples) < 20:
                    missing_examples.append(
                        {
                            "event_id": event.get("event_id"),
                            "audio_path": audio_value,
                            "source_set": event.get("source_set"),
                        }
                    )
                emit_progress()
                continue

            resolved_path = resolve_audio_path(
                audio_value,
                source_set=source_set,
                default_root=audio_root,
                overrides=audio_root_overrides,
            )
            if resolved_path is None:
                stats["missing_audio"] += 1
                missing_sources[source_set] += 1
                if len(missing_examples) < 20:
                    missing_examples.append(
                        {
                            "event_id": event.get("event_id"),
                            "audio_path": audio_value,
                            "source_set": source_set,
                        }
                    )
            else:
                stats["resolved_audio"] += 1

            emit_progress()

        if progress_tracker.enabled:
            progress_tracker.update(
                advance=0,
                resolved=stats["resolved_audio"],
                missing=stats["missing_audio"],
            )

    return {
        "manifest": manifest_path.as_posix(),
        "statistics": stats,
        "label_counts": dict(per_label_counts),
        "missing_examples": missing_examples,
        "missing_sources": dict(missing_sources),
        "expected_seconds_by_source": dict(expected_seconds_by_source),
    }


def render_verification_summary(report: Mapping[str, object], *, logger: OutputLogger) -> None:
    stats_raw = report.get("statistics")
    stats = stats_raw if isinstance(stats_raw, Mapping) else {}
    label_raw = report.get("label_counts")
    label_counts = dict(label_raw) if isinstance(label_raw, Mapping) else {}
    manifest = str(report.get("manifest", "-"))
    expected_duration = _format_duration(stats.get("expected_seconds"))
    duration_by_source_raw = report.get("expected_seconds_by_source")
    duration_by_source = (
        dict(duration_by_source_raw) if isinstance(duration_by_source_raw, Mapping) else {}
    )
    top_duration_sources = sorted(
        duration_by_source.items(), key=lambda item: item[1], reverse=True
    )[:10]

    def fmt(value: object) -> str:
        try:
            if isinstance(value, float) and not value.is_integer():
                return f"{value:,.2f}"
            return f"{int(value):,}"
        except (TypeError, ValueError):
            try:
                return f"{float(value):,.2f}"
            except (TypeError, ValueError):
                return str(value)

    top_missing_sources = sorted(
        (report.get("missing_sources") or {}).items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    if logger.enable_rich and Table is not None:
        summary_kwargs = {"title": "Manifest Verification"}
        if box is not None:
            summary_kwargs["box"] = box.SIMPLE_HEAD
        summary_table = Table(**summary_kwargs)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right", style="magenta")
        summary_table.add_row("Manifest", manifest)
        summary_table.add_row("Events inspected", fmt(stats.get("total_events", 0)))
        summary_table.add_row("Components present", fmt(stats.get("with_components", 0)))
        summary_table.add_row("Missing components", fmt(stats.get("missing_components", 0)))
        summary_table.add_row("Audio resolved", fmt(stats.get("resolved_audio", 0)))
        summary_table.add_row("Missing audio", fmt(stats.get("missing_audio", 0)))
        summary_table.add_row("Unique labels", fmt(len(label_counts)))
        summary_table.add_row("Expected duration", expected_duration)
        logger.print(summary_table)

        if top_duration_sources:
            duration_kwargs = {"title": "Expected Duration By Source"}
            if box is not None:
                duration_kwargs["box"] = box.SIMPLE
            duration_table = Table(**duration_kwargs)
            duration_table.add_column("Source", style="cyan")
            duration_table.add_column("Expected", justify="right", style="magenta")
            for source, seconds in top_duration_sources:
                duration_table.add_row(source or "<unknown>", _format_duration(seconds))
            logger.print(duration_table)

        if top_missing_sources:
            source_kwargs = {"title": "Missing Audio By Source"}
            if box is not None:
                source_kwargs["box"] = box.SIMPLE
            source_table = Table(**source_kwargs)
            source_table.add_column("Source", style="cyan")
            source_table.add_column("Missing", justify="right", style="magenta")
            for source, count in top_missing_sources:
                label = source or "<unknown>"
                source_table.add_row(label, fmt(count))
            logger.print(source_table)

        missing_examples = report.get("missing_examples")
        if isinstance(missing_examples, list) and missing_examples:
            example_kwargs = {"title": "Missing Audio Examples"}
            if box is not None:
                example_kwargs["box"] = box.MINIMAL
            example_table = Table(**example_kwargs)
            example_table.add_column("Event ID", style="cyan")
            example_table.add_column("Source", style="magenta")
            example_table.add_column("Audio Path", style="yellow")
            for entry in missing_examples:
                if isinstance(entry, Mapping):
                    example_table.add_row(
                        str(entry.get("event_id") or "-"),
                        str(entry.get("source_set") or ""),
                        str(entry.get("audio_path") or ""),
                    )
            logger.print(example_table)
    else:
        logger.print("Manifest verification complete.")
        logger.print(f"Manifest: {manifest}")
        logger.print(
            "Events: {total} | components present: {with_components} | missing components: {missing_components}".format(
                total=fmt(stats.get("total_events", 0)),
                with_components=fmt(stats.get("with_components", 0)),
                missing_components=fmt(stats.get("missing_components", 0)),
            )
        )
        logger.print(
            "Audio resolved: {resolved} | missing: {missing}".format(
                resolved=fmt(stats.get("resolved_audio", 0)),
                missing=fmt(stats.get("missing_audio", 0)),
            )
        )
        logger.print(f"Unique labels: {fmt(len(label_counts))}")
        logger.print(f"Expected duration: {expected_duration}")
        if top_duration_sources:
            logger.print("Expected duration by source:")
            for source, seconds in top_duration_sources[:5]:
                logger.print(f"  {source or '<unknown>'}: {_format_duration(seconds)}")
        if top_missing_sources:
            logger.print("Top missing sources:")
            for source, count in top_missing_sources:
                label = source or "<unknown>"
                logger.print(f"  {label}: {fmt(count)}")
        missing_examples = report.get("missing_examples")
        if isinstance(missing_examples, list) and missing_examples:
            logger.print("Missing audio examples:")
            for entry in missing_examples:
                if isinstance(entry, Mapping):
                    logger.print(
                        "  event={event} source={source} path={path}".format(
                            event=entry.get("event_id"),
                            source=entry.get("source_set"),
                            path=entry.get("audio_path"),
                        )
                    )


def render_summary(metadata: Mapping[str, object], *, logger: OutputLogger) -> None:
    stats_raw = metadata.get("statistics")
    stats = stats_raw if isinstance(stats_raw, Mapping) else {}
    run_stats_raw = metadata.get("run_statistics")
    run_stats = run_stats_raw if isinstance(run_stats_raw, Mapping) else {}
    split_raw = metadata.get("split_counts")
    split_counts = split_raw if isinstance(split_raw, Mapping) else {}
    label_raw = metadata.get("label_counts")
    label_counts = dict(label_raw) if isinstance(label_raw, Mapping) else {}
    run_label_raw = metadata.get("run_label_counts")
    run_label_counts = dict(run_label_raw) if isinstance(run_label_raw, Mapping) else {}
    duration_source_raw = metadata.get("duration_seconds_by_source")
    duration_by_source = dict(duration_source_raw) if isinstance(duration_source_raw, Mapping) else {}
    run_duration_source_raw = metadata.get("run_duration_seconds_by_source")
    run_duration_by_source = (
        dict(run_duration_source_raw) if isinstance(run_duration_source_raw, Mapping) else {}
    )
    healed_split_raw = metadata.get("healed_split_counts")
    healed_split_counts = dict(healed_split_raw) if isinstance(healed_split_raw, Mapping) else {}
    run_healed_split_raw = metadata.get("run_healed_split_counts")
    run_healed_split_counts = (
        dict(run_healed_split_raw) if isinstance(run_healed_split_raw, Mapping) else {}
    )
    healed_split_duration_raw = metadata.get("healed_split_durations_seconds")
    healed_split_durations = (
        {k: float(v) for k, v in healed_split_duration_raw.items()}
        if isinstance(healed_split_duration_raw, Mapping)
        else {"train": 0.0, "val": 0.0}
    )
    run_healed_split_duration_raw = metadata.get("run_healed_split_durations_seconds")
    run_healed_split_durations = (
        {k: float(v) for k, v in run_healed_split_duration_raw.items()}
        if isinstance(run_healed_split_duration_raw, Mapping)
        else {"train": 0.0, "val": 0.0}
    )
    healed_duration_source_raw = metadata.get("healed_duration_seconds_by_source")
    healed_duration_by_source = (
        dict(healed_duration_source_raw) if isinstance(healed_duration_source_raw, Mapping) else {}
    )
    run_healed_duration_source_raw = metadata.get("run_healed_duration_seconds_by_source")
    run_healed_duration_by_source = (
        dict(run_healed_duration_source_raw)
        if isinstance(run_healed_duration_source_raw, Mapping)
        else {}
    )

    manifest = str(metadata.get("manifest", "-"))
    dataset_root = str(metadata.get("dataset_root", "-"))
    sample_rate = metadata.get("sample_rate")
    manifest_sha1 = metadata.get("manifest_sha1")
    limit = metadata.get("limit")
    metadata_path = Path(dataset_root) / "metadata.json" if dataset_root != "-" else None

    def fmt(value: object) -> str:
        try:
            if isinstance(value, float) and not value.is_integer():
                return f"{value:,.2f}"
            return f"{int(value):,}"
        except (TypeError, ValueError):
            try:
                return f"{float(value):,.2f}"
            except (TypeError, ValueError):
                return str(value)

    top_components = sorted(
        label_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]
    top_duration_sources = sorted(
        duration_by_source.items(),
        key=lambda item: _coerce_number(item[1]) or 0.0,
        reverse=True,
    )[:10]
    top_healed_sources = sorted(
        healed_duration_by_source.items(),
        key=lambda item: _coerce_number(item[1]) or 0.0,
        reverse=True,
    )[:10]
    top_run_healed_sources = sorted(
        run_healed_duration_by_source.items(),
        key=lambda item: _coerce_number(item[1]) or 0.0,
        reverse=True,
    )[:10]

    total_duration = _format_duration(stats.get("written_seconds"))
    train_duration = _format_duration(stats.get("train_seconds"))
    val_duration = _format_duration(stats.get("val_seconds"))
    healed_total_duration = _format_duration(stats.get("healed_seconds"))

    if logger.enable_rich and Table is not None:
        summary_kwargs = {"title": "Dataset Export Summary"}
        if box is not None:
            summary_kwargs["box"] = box.SIMPLE_HEAD
        summary_table = Table(**summary_kwargs)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", justify="right", style="magenta")
        summary_table.add_row("Manifest", manifest)
        summary_table.add_row("Output", dataset_root)
        if manifest_sha1:
            summary_table.add_row("Manifest SHA1", str(manifest_sha1))
        if sample_rate:
            summary_table.add_row("Sample rate", f"{fmt(sample_rate)} Hz")
        if limit is not None:
            summary_table.add_row("Limit", fmt(limit))
        summary_table.add_row("Events processed", fmt(stats.get("total_events", 0)))
        summary_table.add_row("Events sliced", fmt(stats.get("sliced_events", 0)))
        summary_table.add_row("Clips written", fmt(stats.get("written_clips", 0)))
        if _coerce_int(stats.get("healed_clips")):
            summary_table.add_row("Clips healed", fmt(stats.get("healed_clips", 0)))
        summary_table.add_row("Train clips", fmt(stats.get("train_clips", 0)))
        summary_table.add_row("Val clips", fmt(stats.get("val_clips", 0)))
        summary_table.add_row("Audio duration", total_duration)
        summary_table.add_row("Train duration", train_duration)
        summary_table.add_row("Val duration", val_duration)
        if _coerce_number(stats.get("healed_seconds")):
            summary_table.add_row("Healed audio", healed_total_duration)
        summary_table.add_row(
            "Skipped (missing audio)", fmt(stats.get("skipped_missing_audio", 0))
        )
        summary_table.add_row(
            "Skipped (no components)", fmt(stats.get("skipped_no_components", 0))
        )
        summary_table.add_row("Skipped (total)", fmt(stats.get("skipped_total", 0)))
        summary_table.add_row("Train split", fmt(split_counts.get("train", 0)))
        summary_table.add_row("Val split", fmt(split_counts.get("val", 0)))
        summary_table.add_row("Unique labels", fmt(len(label_counts)))
        logger.print(summary_table)

        if top_duration_sources:
            duration_kwargs = {"title": "Duration By Source"}
            if box is not None:
                duration_kwargs["box"] = box.SIMPLE
            duration_table = Table(**duration_kwargs)
            duration_table.add_column("Source", style="cyan")
            duration_table.add_column("Duration", justify="right", style="magenta")
            for source, seconds in top_duration_sources:
                duration_table.add_row(source or "<unknown>", _format_duration(seconds))
            logger.print(duration_table)

        if top_healed_sources:
            healed_kwargs = {"title": "Healed Duration By Source"}
            if box is not None:
                healed_kwargs["box"] = box.SIMPLE
            healed_table = Table(**healed_kwargs)
            healed_table.add_column("Source", style="cyan")
            healed_table.add_column("Duration", justify="right", style="magenta")
            for source, seconds in top_healed_sources:
                healed_table.add_row(source or "<unknown>", _format_duration(seconds))
            logger.print(healed_table)

        if run_stats:
            delta_kwargs = {"title": "Run Contribution"}
            if box is not None:
                delta_kwargs["box"] = box.SIMPLE
            run_table = Table(**delta_kwargs)
            run_table.add_column("Metric", style="cyan")
            run_table.add_column("Value", justify="right", style="magenta")
            run_total_duration = _format_duration(run_stats.get("written_seconds"))
            run_train_duration = _format_duration(run_stats.get("train_seconds"))
            run_val_duration = _format_duration(run_stats.get("val_seconds"))
            run_table.add_row("Events processed", fmt(run_stats.get("total_events", 0)))
            run_table.add_row("Events sliced", fmt(run_stats.get("sliced_events", 0)))
            run_table.add_row("New clips", fmt(run_stats.get("written_clips", 0)))
            run_table.add_row("New train clips", fmt(run_stats.get("train_clips", 0)))
            run_table.add_row("New val clips", fmt(run_stats.get("val_clips", 0)))
            run_table.add_row("Total audio duration", run_total_duration)
            run_table.add_row("Total train duration", run_train_duration)
            run_table.add_row("Total val duration", run_val_duration)
            run_table.add_row(
                "Skipped (missing audio)", fmt(run_stats.get("skipped_missing_audio", 0))
            )
            run_table.add_row(
                "Skipped (no components)", fmt(run_stats.get("skipped_no_components", 0))
            )
            run_table.add_row("Skipped (total)", fmt(run_stats.get("skipped_total", 0)))
            if run_label_counts:
                run_table.add_row("New labels", fmt(len(run_label_counts)))
            logger.print(run_table)

            combined_run_duration_sources: Dict[str, float] = dict(run_duration_by_source)
            for source, value in run_healed_duration_by_source.items():
                combined_run_duration_sources[source] = combined_run_duration_sources.get(source, 0.0) + float(
                    value
                )
            run_duration_sources = sorted(
                combined_run_duration_sources.items(),
                key=lambda item: _coerce_number(item[1]) or 0.0,
                reverse=True,
            )[:10]
            if run_duration_sources:
                run_duration_kwargs = {"title": "Run Duration By Source"}
                if box is not None:
                    run_duration_kwargs["box"] = box.MINIMAL
                run_duration_table = Table(**run_duration_kwargs)
                run_duration_table.add_column("Source", style="cyan")
                run_duration_table.add_column("Duration", justify="right", style="magenta")
                for source, seconds in run_duration_sources:
                    run_duration_table.add_row(source or "<unknown>", _format_duration(seconds))
                logger.print(run_duration_table)

            if _coerce_int(run_stats.get("healed_clips")):
                healed_kwargs = {"title": "Healed Contribution"}
                if box is not None:
                    healed_kwargs["box"] = box.MINIMAL
                healed_table = Table(**healed_kwargs)
                healed_table.add_column("Metric", style="cyan")
                healed_table.add_column("Value", justify="right", style="magenta")
                healed_total_duration = _format_duration(run_stats.get("healed_seconds"))
                healed_train_duration = _format_duration(run_healed_split_durations.get("train", 0.0))
                healed_val_duration = _format_duration(run_healed_split_durations.get("val", 0.0))
                healed_table.add_row("Healed clips", fmt(run_stats.get("healed_clips", 0)))
                healed_table.add_row(
                    "Healed train clips", fmt(run_healed_split_counts.get("train", 0))
                )
                healed_table.add_row(
                    "Healed val clips", fmt(run_healed_split_counts.get("val", 0))
                )
                healed_table.add_row("Healed audio", healed_total_duration)
                healed_table.add_row("Healed train audio", healed_train_duration)
                healed_table.add_row("Healed val audio", healed_val_duration)
                logger.print(healed_table)

                if top_run_healed_sources:
                    healed_source_kwargs = {"title": "Healed Duration By Source"}
                    if box is not None:
                        healed_source_kwargs["box"] = box.MINIMAL
                    healed_source_table = Table(**healed_source_kwargs)
                    healed_source_table.add_column("Source", style="cyan")
                    healed_source_table.add_column("Duration", justify="right", style="magenta")
                    for source, seconds in top_run_healed_sources:
                        healed_source_table.add_row(
                            source or "<unknown>", _format_duration(seconds)
                        )
                    logger.print(healed_source_table)

            if run_label_counts:
                delta_components = sorted(
                    run_label_counts.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:10]
                if delta_components:
                    new_kwargs = {"title": "Top New Labels"}
                    if box is not None:
                        new_kwargs["box"] = box.MINIMAL
                    new_table = Table(**new_kwargs)
                    new_table.add_column("Label", style="cyan")
                    new_table.add_column("Count", justify="right", style="magenta")
                    for label, count in delta_components:
                        new_table.add_row(label, fmt(count))
                    logger.print(new_table)

        if top_components:
            component_kwargs = {"title": "Top Components"}
            if box is not None:
                component_kwargs["box"] = box.SIMPLE
            component_table = Table(**component_kwargs)
            component_table.add_column("Label", style="cyan")
            component_table.add_column("Count", justify="right", style="magenta")
            for label, count in top_components:
                component_table.add_row(label, fmt(count))
            logger.print(component_table)

        if metadata_path is not None:
            logger.print(f"Metadata: {metadata_path.as_posix()}")
    else:
        logger.print("Dataset export complete.")
        logger.print(f"Manifest: {manifest}")
        logger.print(f"Output: {dataset_root}")
        if manifest_sha1:
            logger.print(f"Manifest SHA1: {manifest_sha1}")
        if sample_rate:
            logger.print(f"Sample rate: {fmt(sample_rate)} Hz")
        if limit is not None:
            logger.print(f"Limit: {fmt(limit)} events")
        clip_summary = "new={clips}".format(clips=fmt(stats.get("written_clips", 0)))
        if _coerce_int(stats.get("healed_clips")):
            clip_summary += ", healed={healed}".format(healed=fmt(stats.get("healed_clips", 0)))
        logger.print(
            "Events processed: {processed} | sliced: {sliced} | clips: {summary}".format(
                processed=fmt(stats.get("total_events", 0)),
                sliced=fmt(stats.get("sliced_events", 0)),
                summary=clip_summary,
            )
        )
        train_clip_summary = "new={train}".format(train=fmt(stats.get("train_clips", 0)))
        if run_healed_split_counts.get("train"):
            train_clip_summary += ", healed={healed}".format(
                healed=fmt(run_healed_split_counts.get("train", 0))
            )
        val_clip_summary = "new={val}".format(val=fmt(stats.get("val_clips", 0)))
        if run_healed_split_counts.get("val"):
            val_clip_summary += ", healed={healed}".format(
                healed=fmt(run_healed_split_counts.get("val", 0))
            )
        logger.print(
            "Train clips: {train} | Val clips: {val}".format(
                train=train_clip_summary,
                val=val_clip_summary,
            )
        )
        duration_summary = "total: {total}, train: {train}, val: {val}".format(
            total=total_duration,
            train=train_duration,
            val=val_duration,
        )
        if _coerce_number(stats.get("healed_seconds")):
            duration_summary += ", healed: {healed}".format(
                healed=_format_duration(stats.get("healed_seconds"))
            )
        logger.print(f"Duration -> {duration_summary}")
        logger.print(
            "Skipped -> missing audio: {missing}, no components: {components}, total: {total}".format(
                missing=fmt(stats.get("skipped_missing_audio", 0)),
                components=fmt(stats.get("skipped_no_components", 0)),
                total=fmt(stats.get("skipped_total", 0)),
            )
        )
        logger.print(
            "Split sizes -> train: {train}, val: {val}".format(
                train=fmt(split_counts.get("train", 0)),
                val=fmt(split_counts.get("val", 0)),
            )
        )
        logger.print(f"Unique labels: {fmt(len(label_counts))}")
        if top_duration_sources:
            duration_plain = ", ".join(
                f"{source or '<unknown>'}: {_format_duration(seconds)}"
                for source, seconds in top_duration_sources[:5]
            )
            logger.print(f"Duration by source: {duration_plain}")
        if top_healed_sources:
            healed_plain = ", ".join(
                f"{source or '<unknown>'}: {_format_duration(seconds)}"
                for source, seconds in top_healed_sources[:5]
            )
            logger.print(f"Healed duration by source: {healed_plain}")
        if run_stats:
            run_total_duration = _format_duration(run_stats.get("written_seconds"))
            run_train_duration = _format_duration(run_stats.get("train_seconds"))
            run_val_duration = _format_duration(run_stats.get("val_seconds"))
            run_clip_summary = "new={clips}".format(clips=fmt(run_stats.get("written_clips", 0)))
            if _coerce_int(run_stats.get("healed_clips")):
                run_clip_summary += ", healed={healed}".format(
                    healed=fmt(run_stats.get("healed_clips", 0))
                )
            logger.print(
                "Run contribution -> events: {events}, clips: {clips}, train: new={train}, val: new={val}".format(
                    events=fmt(run_stats.get("total_events", 0)),
                    clips=run_clip_summary,
                    train=fmt(run_stats.get("train_clips", 0)),
                    val=fmt(run_stats.get("val_clips", 0)),
                )
            )
            healed_train = run_healed_split_counts.get("train")
            healed_val = run_healed_split_counts.get("val")
            if healed_train or healed_val:
                logger.print(
                    "Run healed clips -> train: {train}, val: {val}".format(
                        train=fmt(healed_train or 0),
                        val=fmt(healed_val or 0),
                    )
                )
            logger.print(
                "Run duration -> total: {total}, train: {train}, val: {val}".format(
                    total=run_total_duration,
                    train=run_train_duration,
                    val=run_val_duration,
                )
            )
            if _coerce_number(run_stats.get("healed_seconds")):
                logger.print(
                    "Run healed duration -> total: {total}, train: {train}, val: {val}".format(
                        total=_format_duration(run_stats.get("healed_seconds")),
                        train=_format_duration(run_healed_split_durations.get("train", 0.0)),
                        val=_format_duration(run_healed_split_durations.get("val", 0.0)),
                    )
                )
            combined_run_duration_sources: Dict[str, float] = dict(run_duration_by_source)
            for source, value in run_healed_duration_by_source.items():
                combined_run_duration_sources[source] = combined_run_duration_sources.get(source, 0.0) + float(
                    value
                )
            run_duration_sources = sorted(
                combined_run_duration_sources.items(),
                key=lambda item: _coerce_number(item[1]) or 0.0,
                reverse=True,
            )
            if run_duration_sources:
                run_duration_plain = ", ".join(
                    f"{source or '<unknown>'}: {_format_duration(seconds)}"
                    for source, seconds in run_duration_sources[:5]
                )
                logger.print(f"Run duration by source: {run_duration_plain}")
            if top_run_healed_sources:
                healed_run_plain = ", ".join(
                    f"{source or '<unknown>'}: {_format_duration(seconds)}"
                    for source, seconds in top_run_healed_sources[:5]
                )
                logger.print(f"Run healed duration by source: {healed_run_plain}")
        if run_label_counts:
            new_labels = [
                (label, count)
                for label, count in sorted(
                    run_label_counts.items(), key=lambda item: item[1], reverse=True
                )
                if count
            ]
            if new_labels:
                new_labels_str = ", ".join(f"{label} ({fmt(count)})" for label, count in new_labels[:10])
                logger.print(f"New labels this run: {new_labels_str}")
        if metadata_path is not None:
            logger.print(f"Metadata: {metadata_path.as_posix()}")
        if top_components:
            logger.print("Top components:")
            for label, count in top_components:
                logger.print(f"  {label}: {fmt(count)}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    manifest_path: Path = args.manifest.expanduser().resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    dataset_root: Path = args.output.expanduser().resolve()

    if args.force_rich and not HAS_RICH_DISPLAY:
        raise SystemExit(
            "--force-rich requested but the optional 'rich' dependency is unavailable. "
            "Install it with 'pip install rich' or drop the flag."
        )

    logger = OutputLogger(
        enable_rich=not args.disable_rich,
        log_file=args.log_file,
        force_terminal=args.force_rich,
    )

    if args.force_rich and not logger.enable_rich:
        logger.close()
        raise SystemExit(
            "--force-rich requested but rich rendering could not be initialised for this console. "
            "Ensure stdout accepts ANSI control codes or rerun without the flag."
        )

    if not logger.enable_rich and not args.disable_rich and HAS_RICH_DISPLAY:
        print(
            "Rich UI support detected but could not attach to the current console. "
            "Use --force-rich to override or --disable-rich to silence this warning.",
            file=sys.stderr,
        )

    manifest_total_hint = args.manifest_total

    def ensure_manifest_total_hint() -> Optional[int]:
        nonlocal manifest_total_hint
        if manifest_total_hint is not None or args.limit is not None:
            return manifest_total_hint
        with logger.status("Estimating manifest length for ETA..."):
            manifest_total_hint = estimate_manifest_event_count(manifest_path)
        return manifest_total_hint

    try:
        audio_root = args.audio_root.expanduser().resolve() if args.audio_root else None
        audio_overrides = parse_audio_root_map(args.audio_root_map)
        summary_path = args.summary_json.expanduser().resolve() if args.summary_json else None
        duration_csv_path = (
            args.expected_duration_csv.expanduser().resolve()
            if args.expected_duration_csv
            else None
        )
        write_workers_arg = args.write_workers
        if write_workers_arg is None:
            write_worker_count = DEFAULT_WRITE_WORKERS
        else:
            write_worker_count = max(0, write_workers_arg)
        write_worker_count = min(write_worker_count, 32)
        effective_write_workers: Optional[int] = (
            None if write_worker_count <= 0 else write_worker_count
        )

        if args.verify_only:
            logger.rule("Verify Training Dataset Manifest")
            logger.print(f"Manifest: {manifest_path.as_posix()}")
            if audio_root:
                logger.print(f"Default audio root: {audio_root.as_posix()}")
            if audio_overrides:
                override_parts = []
                for source, paths in audio_overrides.items():
                    joined_paths = " | ".join(p.as_posix() for p in paths)
                    override_parts.append(f"{source}={joined_paths}")
                logger.print("Audio overrides: " + ", ".join(override_parts))
            if args.limit is not None:
                logger.print(f"Verification limit: {args.limit:,} events")

            report = verify_manifest(
                manifest_path=manifest_path,
                audio_root=audio_root,
                audio_root_overrides=audio_overrides,
                limit=args.limit,
                progress_interval=args.progress_interval,
                logger=logger,
                progress_total=ensure_manifest_total_hint(),
            )
            render_verification_summary(report, logger=logger)
            if summary_path is not None:
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                with summary_path.open("w", encoding="utf-8") as handle:
                    json.dump(report, handle, indent=2)
                logger.print(f"Verification summary saved to {summary_path.as_posix()}")
            if duration_csv_path is not None:
                _write_duration_csv(
                    duration_csv_path,
                    [
                        ("expected", report.get("expected_seconds_by_source") or {}),
                    ],
                )
                logger.print(
                    f"Expected duration breakdown saved to {duration_csv_path.as_posix()}"
                )
            return

        overwriting_existing = args.overwrite and dataset_root.exists()
        if overwriting_existing:
            logger.print(
                "Preparing overwrite: removing existing dataset directory (this can take a minute)..."
            )

        ensure_output_dirs(dataset_root, overwrite=args.overwrite, resume=args.resume)

        if overwriting_existing:
            logger.print("Existing dataset directory cleared. Starting fresh export.")
        elif args.resume:
            logger.print("Resume mode enabled: reusing existing clips and metadata.")

        logger.rule("Build Training Dataset")
        logger.print(f"Manifest: {manifest_path.as_posix()}")
        logger.print(f"Output directory: {dataset_root.as_posix()}")
        logger.print(
            f"Sample rate: {args.sample_rate} Hz | validation ratio: {args.val_ratio:.2f}"
        )
        if args.clip_fanout is not None:
            logger.print(f"Clip directory fanout: {max(args.clip_fanout, 0)}")
        else:
            logger.print("Clip directory fanout: auto (reuse existing metadata or flat)")
        if args.limit is not None:
            logger.print(f"Processing limit: {args.limit:,} events")
        total_hint_for_export = ensure_manifest_total_hint()
        if args.limit is None and total_hint_for_export:
            logger.print(f"Manifest events (estimated): {total_hint_for_export:,}")

        metadata = build_dataset(
            manifest_path=manifest_path,
            dataset_root=dataset_root,
            audio_root=audio_root,
            audio_root_overrides=audio_overrides,
            target_sample_rate=args.sample_rate,
            val_ratio=args.val_ratio,
            limit=args.limit,
            pad_to_seconds=args.pad_to,
            progress_interval=args.progress_interval,
            resume=args.resume,
            logger=logger,
            progress_total=total_hint_for_export,
            write_workers=effective_write_workers,
            heal_missing_clips=args.heal_missing_clips,
            checkpoint_every=args.checkpoint_every,
            clip_fanout=args.clip_fanout,
        )

        render_summary(metadata, logger=logger)
        if summary_path is not None:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with summary_path.open("w", encoding="utf-8") as handle:
                json.dump(metadata, handle, indent=2)
            logger.print(f"Export summary saved to {summary_path.as_posix()}")
        if duration_csv_path is not None:
            _write_duration_csv(
                duration_csv_path,
                [
                    ("total", metadata.get("duration_seconds_by_source") or {}),
                    ("run", metadata.get("run_duration_seconds_by_source") or {}),
                    ("run_healed", metadata.get("run_healed_duration_seconds_by_source") or {}),
                ],
            )
            logger.print(
                f"Duration breakdown saved to {duration_csv_path.as_posix()}"
            )
    finally:
        logger.close()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
