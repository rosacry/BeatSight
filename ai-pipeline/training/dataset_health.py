#!/usr/bin/env python3
"""Dataset health reporting for BeatSight drum events.

This script inspects an `events.jsonl` file and emits a JSON report covering
per-class coverage, synthetic vs real counts, dynamic bucket distributions,
hi-hat openness histograms, duplicate detection, and other readiness signals.

Usage example:

```
python dataset_health.py \
    --events annotations/events.jsonl \
    --output reports/health/latest_health.json
```
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

# Bin boundaries for openness histogram (inclusive of upper bound on last bin).
_OPENNESS_BIN_EDGES: Tuple[float, ...] = tuple(i / 10 for i in range(11))

CRASH_LABEL_PREFIX = "crash"
CRASH_DUAL_LABEL_TAG = "crash_dual_label"


@dataclass
class HealthOptions:
    events_path: Path
    output_path: Optional[Path]
    html_output_path: Optional[Path]
    metadata_path: Optional[Path]
    components_path: Optional[Path]
    max_duplication_rate: Optional[float]
    min_class_count: Optional[int]
    min_counts_path: Optional[Path]
    require_labels: List[str]
    max_unknown_labels: Optional[int]
    require_techniques: List[str]


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


def parse_args() -> HealthOptions:
    parser = argparse.ArgumentParser(description="Generate dataset health report")
    parser.add_argument(
        "--events",
        required=True,
        type=Path,
        help="Path to events JSONL file to analyse",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write JSON report (stdout when omitted)",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        help="Optional path to write an HTML summary alongside JSON",
    )
    parser.add_argument(
        "--dataset-metadata",
        type=Path,
        help=(
            "Optional metadata.json produced by build_training_dataset.py. "
            "When provided, duration telemetry is merged into the report."
        ),
    )
    parser.add_argument(
        "--components",
        type=Path,
        help="Optional components taxonomy JSON for validation",
    )
    parser.add_argument(
        "--max-duplication-rate",
        type=float,
        help=(
            "Optional hard gate on duplicate sample id rate (0-1). "
            "Fails with exit code 2 when exceeded."
        ),
    )
    parser.add_argument(
        "--min-class-count",
        type=int,
        help=(
            "Optional minimum total examples required per instrument label. "
            "Applied to taxonomy classes when provided, otherwise all observed labels."
        ),
    )
    parser.add_argument(
        "--min-counts-json",
        type=Path,
        help=(
            "Optional JSON mapping of label → minimum count. "
            "Fails when any label falls below its threshold."
        ),
    )
    parser.add_argument(
        "--require-label",
        action="append",
        default=[],
        help="Ensure specific labels appear at least once (repeat flag to add more).",
    )
    parser.add_argument(
        "--require-labels-file",
        action="append",
        type=Path,
        default=[],
        help="Path to file listing required labels (one per line). Repeatable.",
    )
    parser.add_argument(
        "--max-unknown-labels",
        type=int,
        help="Maximum total count of unknown labels allowed before failing",
    )
    parser.add_argument(
        "--require-technique",
        action="append",
        default=[],
        help="Ensure specific techniques appear at least once (repeat flag to add more).",
    )
    parser.add_argument(
        "--require-techniques-file",
        action="append",
        type=Path,
        default=[],
        help="Path to file listing required techniques (one per line). Repeatable.",
    )
    args = parser.parse_args()

    require_labels = list(args.require_label or [])
    for file_path in args.require_labels_file or []:
        for label in load_required_labels(file_path):
            if label not in require_labels:
                require_labels.append(label)

    require_techniques = list(args.require_technique or [])
    for file_path in args.require_techniques_file or []:
        for technique in load_required_labels(file_path):
            if technique not in require_techniques:
                require_techniques.append(technique)

    return HealthOptions(
        events_path=args.events,
        output_path=args.output,
        html_output_path=args.html_output,
        metadata_path=args.dataset_metadata,
        components_path=args.components,
        max_duplication_rate=args.max_duplication_rate,
        min_class_count=args.min_class_count,
        min_counts_path=args.min_counts_json,
        require_labels=require_labels,
        max_unknown_labels=args.max_unknown_labels,
        require_techniques=require_techniques,
    )


def load_taxonomy(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def allowed_labels_from_taxonomy(taxonomy: Optional[Dict[str, Any]]) -> Set[str]:
    labels: Set[str] = set()
    if not taxonomy:
        return labels
    for entry in taxonomy.get("classes", []):
        label = entry.get("id")
        if label:
            labels.add(label)
    return labels


def load_class_thresholds(path: Optional[Path]) -> Dict[str, int]:
    if not path:
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object mapping labels to minimum counts")
    thresholds: Dict[str, int] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise ValueError("Threshold keys must be strings (label names)")
        if not isinstance(value, int):
            raise ValueError(f"Threshold for '{key}' must be an integer")
        thresholds[key] = value
    return thresholds


def load_required_labels(path: Path) -> List[str]:
    labels: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            labels.append(stripped)
    return labels


def empty_histogram() -> List[Dict[str, Any]]:
    bins: List[Dict[str, Any]] = []
    for idx in range(len(_OPENNESS_BIN_EDGES) - 1):
        start = _OPENNESS_BIN_EDGES[idx]
        end = _OPENNESS_BIN_EDGES[idx + 1]
        bins.append({"range": f"{start:.1f}-{end:.1f}", "count": 0})
    return bins


def bin_openness(value: float) -> int:
    if math.isnan(value):
        return -1
    clamped = max(0.0, min(0.999999, value))
    return int(clamped * 10)


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


def _format_duration(value: float) -> str:
    seconds = max(float(value), 0.0)
    if seconds < 1e-3:
        return "0 s"
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    hours = int(seconds // 3600)
    remainder = seconds - hours * 3600
    minutes = int(remainder // 60)
    seconds_rem = remainder - minutes * 60
    if hours:
        return f"{hours}h {minutes:02d}m {seconds_rem:05.2f}s"
    if minutes:
        return f"{minutes}m {seconds_rem:05.2f}s"
    return f"{seconds_rem:,.2f} s"


def analyse_events(
    events_path: Path, taxonomy: Optional[Dict[str, Any]]
) -> Tuple[Dict[str, Any], float]:
    allowed_labels = allowed_labels_from_taxonomy(taxonomy)

    class_counts: Counter[str] = Counter()
    class_counts_real: Counter[str] = Counter()
    class_counts_synth: Counter[str] = Counter()
    crash_variant_counts: Counter[str] = Counter()
    per_class_dynamic: Dict[str, Counter[str]] = defaultdict(Counter)
    dynamic_bucket_counts: Counter[str] = Counter()
    bleed_level_counts: Counter[str] = Counter()
    mix_context_counts: Counter[str] = Counter()
    negative_counts: Counter[bool] = Counter()
    session_counts: Counter[str] = Counter()
    drummer_counts: Counter[str] = Counter()

    sample_id_counts: Counter[str] = Counter()
    audio_path_counts: Counter[str] = Counter()

    openness_values: List[float] = []
    loudness_lufs: List[float] = []
    loudness_peak: List[float] = []

    unknown_labels: Counter[str] = Counter()
    technique_counts: Counter[str] = Counter()
    crash_dual_label_assignments = 0

    total_events = 0
    synthetic_events = 0

    with events_path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSON parse error on line {line_number}: {exc.msg}"
                ) from exc

            total_events += 1

            sample_id = event.get("sample_id")
            if sample_id:
                sample_id_counts[sample_id] += 1

            audio_path = event.get("audio_path")
            if audio_path:
                audio_path_counts[audio_path] += 1

            session_id = event.get("session_id")
            if session_id:
                session_counts[session_id] += 1

            drummer_id = event.get("drummer_id")
            if drummer_id:
                drummer_counts[drummer_id] += 1

            is_synth = bool(event.get("is_synthetic", False))
            if is_synth:
                synthetic_events += 1

            bleed_level = event.get("bleed_level")
            if bleed_level:
                bleed_level_counts[bleed_level] += 1

            mix_context = event.get("mix_context")
            if mix_context:
                mix_context_counts[mix_context] += 1

            negative_example = bool(event.get("negative_example", False))
            negative_counts[negative_example] += 1

            loudness = event.get("loudness") or {}
            lufs = loudness.get("LUFS_i")
            if isinstance(lufs, (float, int)):
                loudness_lufs.append(float(lufs))
            peak_dbfs = loudness.get("peak_dbfs")
            if isinstance(peak_dbfs, (float, int)):
                loudness_peak.append(float(peak_dbfs))

            for component in event.get("components", []):
                label = component.get("label")
                if not label:
                    continue

                class_counts[label] += 1
                if isinstance(label, str) and label.startswith(CRASH_LABEL_PREFIX):
                    crash_variant_counts[label] += 1
                if is_synth:
                    class_counts_synth[label] += 1
                else:
                    class_counts_real[label] += 1

                dynamic_bucket = component.get("dynamic_bucket")
                if dynamic_bucket:
                    dynamic_bucket_counts[dynamic_bucket] += 1
                    per_class_dynamic[label][dynamic_bucket] += 1

                openness_value = component.get("openness")
                if isinstance(openness_value, (float, int)):
                    openness_values.append(float(openness_value))

                if allowed_labels and label not in allowed_labels:
                    unknown_labels[label] += 1

            for technique in event.get("techniques", []) or []:
                if isinstance(technique, str) and technique:
                    technique_counts[technique] += 1
                    if technique == CRASH_DUAL_LABEL_TAG:
                        crash_dual_label_assignments += 1

    duplicate_sample_ids = {
        sid: count for sid, count in sample_id_counts.items() if count > 1
    }
    duplicate_audio = {
        path: count for path, count in audio_path_counts.items() if count > 1
    }

    duplication_rate = (
        sum(count - 1 for count in sample_id_counts.values() if count > 1)
        / total_events
        if total_events
        else 0.0
    )

    openness_histogram = empty_histogram()
    for value in openness_values:
        idx = bin_openness(value)
        if idx >= 0:
            openness_histogram[idx]["count"] += 1

    def aggregate(values: List[float]) -> Optional[Dict[str, float]]:
        if not values:
            return None
        return {
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "mean": round(statistics.fmean(values), 4),
            "median": round(statistics.median(values), 4),
        }

    report: Dict[str, Any] = {
        "summary": {
            "events_total": total_events,
            "events_synthetic": synthetic_events,
            "events_real": total_events - synthetic_events,
            "unique_sessions": len(session_counts),
            "unique_drummers": len(drummer_counts),
            "duplication_rate": round(duplication_rate, 6),
            "negative_examples": {
                "positive": negative_counts[True],
                "non_negative": negative_counts[False],
            },
        },
        "per_class_counts": {},
        "dynamic_bucket_counts": dict(dynamic_bucket_counts),
        "per_class_dynamic": {
            label: dict(counts) for label, counts in per_class_dynamic.items()
        },
        "bleed_level_distribution": dict(bleed_level_counts),
        "mix_context_distribution": dict(mix_context_counts),
        "openness_histogram": openness_histogram,
        "duplicates": {
            "sample_ids": duplicate_sample_ids,
            "audio_paths": duplicate_audio,
        },
        "loudness": {
            "LUFS_i": aggregate(loudness_lufs),
            "peak_dbfs": aggregate(loudness_peak),
        },
        "unknown_labels": dict(unknown_labels),
        "crash_variant_counts": dict(crash_variant_counts),
        "crash_dual_label_assignments": crash_dual_label_assignments,
        "technique_counts": dict(technique_counts),
    }

    for label in sorted(class_counts):
        report["per_class_counts"][label] = {
            "total": class_counts[label],
            "real": class_counts_real.get(label, 0),
            "synthetic": class_counts_synth.get(label, 0),
        }

    return report, duplication_rate


def _parse_float_mapping(raw: Any) -> Dict[str, float]:
    result: Dict[str, float] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            number = _coerce_number(value)
            if number is None:
                continue
            result[str(key)] = float(number)
    return result


def merge_metadata_durations(report: Dict[str, Any], metadata: Mapping[str, Any]) -> None:
    """Augment report with duration telemetry sourced from dataset metadata."""

    split_durations = _parse_float_mapping(metadata.get("split_durations_seconds"))
    run_split_durations = _parse_float_mapping(metadata.get("run_split_durations_seconds"))
    duration_by_source = _parse_float_mapping(metadata.get("duration_seconds_by_source"))
    run_duration_by_source = _parse_float_mapping(metadata.get("run_duration_seconds_by_source"))

    if split_durations:
        report["split_durations_seconds"] = split_durations
    if run_split_durations:
        report["run_split_durations_seconds"] = run_split_durations
    if duration_by_source:
        report["duration_seconds_by_source"] = duration_by_source
    if run_duration_by_source:
        report["run_duration_seconds_by_source"] = run_duration_by_source

    if not split_durations and not duration_by_source:
        return

    summary = report.setdefault("summary", {})

    if split_durations:
        total_seconds = float(sum(split_durations.values()))
        summary["duration_seconds_total"] = round(total_seconds, 6)
        summary["duration_hours_total"] = round(total_seconds / 3600.0, 6)


def load_metadata(path: Optional[Path]) -> Optional[Mapping[str, Any]]:
    if not path:
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Dataset metadata file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse dataset metadata {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ValueError("Dataset metadata must be a JSON object")
    return data


def collect_gate_failures(
    report: Dict[str, Any],
    duplication_rate: float,
    options: HealthOptions,
    allowed_labels: Set[str],
    class_thresholds: Dict[str, int],
) -> Tuple[List[str], List[GateResult]]:
    failures: List[str] = []
    gate_results: List[GateResult] = []

    if options.max_duplication_rate is not None:
        passed = duplication_rate <= options.max_duplication_rate
        detail = (
            f"duplication_rate {duplication_rate:.6f} <= "
            f"{options.max_duplication_rate:.6f}"
        )
        if not passed:
            failures.append(
                (
                    "Duplicate gating failed: duplication rate "
                    f"{duplication_rate:.6f} exceeds limit {options.max_duplication_rate:.6f}."
                )
            )
        gate_results.append(GateResult("duplication_rate", passed, detail))

    per_class_counts = report.get("per_class_counts", {})
    class_totals = {
        label: counts.get("total", 0) for label, counts in per_class_counts.items()
    }

    labels_to_check: Set[str]
    if allowed_labels:
        labels_to_check = set(allowed_labels)
    else:
        labels_to_check = set(class_totals.keys())

    if options.min_class_count is not None:
        for label in sorted(labels_to_check):
            total = class_totals.get(label, 0)
            passed = total >= options.min_class_count
            detail = f"{label}: {total} >= {options.min_class_count}"
            if not passed:
                failures.append(
                    (
                        f"Coverage gating failed: label '{label}' has {total} examples "
                        f"(< required {options.min_class_count})."
                    )
                )
            gate_results.append(
                GateResult(f"min_class_count[{label}]", passed, detail)
            )

    for label, threshold in sorted(class_thresholds.items()):
        total = class_totals.get(label, 0)
        passed = total >= threshold
        detail = f"{label}: {total} >= {threshold}"
        if not passed:
            failures.append(
                (
                    f"Coverage gating failed: label '{label}' has {total} examples "
                    f"(< required {threshold})."
                )
            )
        gate_results.append(
            GateResult(f"min_counts[{label}]", passed, detail)
        )

    for label in options.require_labels:
        total = class_totals.get(label, 0)
        passed = total > 0
        detail = f"{label}: present={bool(total)}"
        if not passed:
            failures.append(
                f"Coverage gating failed: required label '{label}' is missing."
            )
        gate_results.append(
            GateResult(f"require_label[{label}]", passed, detail)
        )

    technique_totals = report.get("technique_counts", {})

    for technique in options.require_techniques:
        total = technique_totals.get(technique, 0)
        passed = total > 0
        detail = f"{technique}: present={bool(total)}"
        if not passed:
            failures.append(
                f"Coverage gating failed: required technique '{technique}' is missing."
            )
        gate_results.append(
            GateResult(f"require_technique[{technique}]", passed, detail)
        )

    if options.max_unknown_labels is not None:
        unknown_total = sum(report.get("unknown_labels", {}).values())
        passed = unknown_total <= options.max_unknown_labels
        detail = f"unknown_labels {unknown_total} <= {options.max_unknown_labels}"
        if not passed:
            failures.append(
                (
                    "Unknown label gating failed: "
                    f"{unknown_total} unseen labels exceed limit {options.max_unknown_labels}."
                )
            )
        gate_results.append(
            GateResult("max_unknown_labels", passed, detail)
        )

    return failures, gate_results


def write_report(report: Dict[str, Any], output_path: Optional[Path]) -> None:
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    else:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


def write_html_report(
    report: Dict[str, Any],
    html_path: Optional[Path],
    gate_results: Optional[List[GateResult]] = None,
) -> None:
    if not html_path:
        return

    html_path.parent.mkdir(parents=True, exist_ok=True)

    summary = report.get("summary", {})
    per_class = report.get("per_class_counts", {})
    duplicates = report.get("duplicates", {})
    technique_counts = report.get("technique_counts", {})
    openness = report.get("openness_histogram", [])
    split_durations = report.get("split_durations_seconds", {})
    run_split_durations = report.get("run_split_durations_seconds", {})
    duration_by_source = report.get("duration_seconds_by_source", {})
    run_duration_by_source = report.get("run_duration_seconds_by_source", {})

    lines: List[str] = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>BeatSight Dataset Health</title>",
        "  <style>",
        "    body { font-family: Arial, sans-serif; margin: 1.5rem; }",
        "    h1, h2 { color: #222; }",
        "    table { border-collapse: collapse; margin-bottom: 1.5rem; }",
        "    th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }",
        "    th { background: #f3f3f3; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>BeatSight Dataset Health Report</h1>",
    "  <h2>Summary</h2>",
        "  <table>",
        "    <tbody>",
    ]

    for key in [
        "events_total",
        "events_real",
        "events_synthetic",
        "unique_sessions",
        "unique_drummers",
        "duplication_rate",
        "duration_seconds_total",
        "duration_hours_total",
    ]:
        if key in summary:
            lines.append(
                f"      <tr><th>{escape(key)}</th><td>{escape(str(summary[key]))}</td></tr>"
            )

    negatives = summary.get("negative_examples")
    if isinstance(negatives, dict):
        pieces = [f"{escape(k)}: {escape(str(v))}" for k, v in sorted(negatives.items())]
        lines.append("      <tr><th>negative_examples</th><td>" + ", ".join(pieces) + "</td></tr>")

    lines.extend([
        "    </tbody>",
        "  </table>",
        "  <h2>Per-class Coverage</h2>",
        "  <table>",
        "    <thead>",
        "      <tr><th>Label</th><th>Total</th><th>Real</th><th>Synthetic</th></tr>",
        "    </thead>",
        "    <tbody>",
    ])

    for label in sorted(per_class):
        counts = per_class[label]
        lines.append(
            "      <tr><td>{label}</td><td>{total}</td><td>{real}</td><td>{synthetic}</td></tr>".format(
                label=escape(label),
                total=escape(str(counts.get("total", 0))),
                real=escape(str(counts.get("real", 0))),
                synthetic=escape(str(counts.get("synthetic", 0))),
            )
        )

    lines.extend([
        "    </tbody>",
        "  </table>",
    ])

    def append_duration_table(title: str, mapping: Any) -> None:
        if not isinstance(mapping, dict) or not mapping:
            return
        rows: List[Tuple[str, float]] = []
        for key, value in mapping.items():
            seconds_val = _coerce_number(value)
            if seconds_val is None:
                continue
            rows.append((str(key), float(seconds_val)))
        if not rows:
            return
        rows.sort(key=lambda item: (-item[1], item[0]))
        lines.extend([
            f"  <h2>{escape(title)}</h2>",
            "  <table>",
            "    <thead><tr><th>Key</th><th>Seconds</th><th>Formatted</th></tr></thead>",
            "    <tbody>",
        ])
        for key, seconds_val in rows:
            lines.append(
                "      <tr><td>{name}</td><td>{seconds:.6f}</td><td>{formatted}</td></tr>".format(
                    name=escape(str(key)),
                    seconds=seconds_val,
                    formatted=escape(_format_duration(seconds_val)),
                )
            )
        lines.extend([
            "    </tbody>",
            "  </table>",
        ])

    append_duration_table("Duration by Split", split_durations)
    append_duration_table("Run Duration by Split", run_split_durations)
    append_duration_table("Duration by Source", duration_by_source)
    append_duration_table("Run Duration by Source", run_duration_by_source)

    if technique_counts:
        lines.extend([
            "  <h2>Technique Counts</h2>",
            "  <table>",
            "    <thead><tr><th>Technique</th><th>Count</th></tr></thead>",
            "    <tbody>",
        ])
        for technique in sorted(technique_counts):
            lines.append(
                "      <tr><td>{technique}</td><td>{count}</td></tr>".format(
                    technique=escape(str(technique)),
                    count=escape(str(technique_counts[technique])),
                )
            )
        lines.extend([
            "    </tbody>",
            "  </table>",
        ])

    if gate_results:
        lines.extend([
            "  <h2>Gating Results</h2>",
            "  <table>",
            "    <thead><tr><th>Gate</th><th>Status</th><th>Detail</th></tr></thead>",
            "    <tbody>",
        ])
        for result in gate_results:
            status_text = "PASS" if result.passed else "FAIL"
            lines.append(
                "      <tr><td>{name}</td><td>{status}</td><td>{detail}</td></tr>".format(
                    name=escape(result.name),
                    status=escape(status_text),
                    detail=escape(result.detail),
                )
            )
        lines.extend([
            "    </tbody>",
            "  </table>",
        ])

    if openness:
        lines.extend([
            "  <h2>Hi-hat Openness Histogram</h2>",
            "  <table>",
            "    <thead><tr><th>Range</th><th>Count</th></tr></thead>",
            "    <tbody>",
        ])
        for bucket in openness:
            lines.append(
                "      <tr><td>{rng}</td><td>{count}</td></tr>".format(
                    rng=escape(str(bucket.get("range", ""))),
                    count=escape(str(bucket.get("count", 0))),
                )
            )
        lines.extend([
            "    </tbody>",
            "  </table>",
        ])

    if duplicates:
        lines.extend([
            "  <h2>Duplicates</h2>",
            "  <pre>",
            escape(json.dumps(duplicates, indent=2, sort_keys=True)),
            "  </pre>",
        ])

    unknown_labels = report.get("unknown_labels")
    if unknown_labels:
        lines.extend([
            "  <h2>Unknown Labels</h2>",
            "  <pre>",
            escape(json.dumps(unknown_labels, indent=2, sort_keys=True)),
            "  </pre>",
        ])

    lines.extend([
        "</body>",
        "</html>",
    ])

    html_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    options = parse_args()
    taxonomy = load_taxonomy(options.components_path)
    allowed_labels = allowed_labels_from_taxonomy(taxonomy)
    class_thresholds = load_class_thresholds(options.min_counts_path)

    report, duplication_rate = analyse_events(options.events_path, taxonomy)

    metadata = load_metadata(options.metadata_path)
    if metadata:
        merge_metadata_durations(report, metadata)

    failures, gate_results = collect_gate_failures(
        report,
        duplication_rate,
        options,
        allowed_labels,
        class_thresholds,
    )

    if gate_results:
        report["gating_results"] = [result.to_dict() for result in gate_results]

    write_report(report, options.output_path)
    write_html_report(report, options.html_output_path, gate_results)

    if failures:
        for message in failures:
            print(message, file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
