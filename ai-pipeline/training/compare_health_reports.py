#!/usr/bin/env python3
"""Compare dataset health reports to detect regressions.

The script takes a baseline (approved) dataset health JSON and compares it with a
candidate report. It flags class coverage regressions, unknown label increases,
and gating failures.

Example usage:

```
python compare_health_reports.py \
    --baseline reports/health/baseline.json \
    --candidate reports/health/latest_health.json \
    --max-drop 50 \
    --ignore-label aux_percussion
```
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


@dataclass
class CompareOptions:
    baseline_path: Path
    candidate_path: Path
    max_drop: int
    ignore_labels: Set[str]
    json_output: Optional[Path]


@dataclass
class ClassDelta:
    label: str
    baseline_total: int
    candidate_total: int
    delta: int
    real_delta: int
    synthetic_delta: int


@dataclass
class CompareResult:
    class_deltas: List[ClassDelta]
    gating_regressions: List[str]
    unknown_label_delta: int
    passes: bool


def parse_args(argv: Optional[List[str]] = None) -> CompareOptions:
    parser = argparse.ArgumentParser(description="Compare dataset health reports")
    parser.add_argument("--baseline", required=True, type=Path, help="Baseline report JSON")
    parser.add_argument("--candidate", required=True, type=Path, help="Candidate report JSON")
    parser.add_argument(
        "--max-drop",
        type=int,
        default=0,
        help="Maximum allowed drop in per-class totals (default: 0)",
    )
    parser.add_argument(
        "--ignore-label",
        action="append",
        default=[],
        help="Labels to ignore when checking for regressions (repeatable)",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path to write diff as JSON",
    )
    args = parser.parse_args(argv)

    return CompareOptions(
        baseline_path=args.baseline,
        candidate_path=args.candidate,
        max_drop=max(args.max_drop, 0),
        ignore_labels=set(args.ignore_label or []),
        json_output=args.json_output,
    )


def load_report(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_class_counts(report: Dict[str, object]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    per_class = report.get("per_class_counts", {})
    if not isinstance(per_class, dict):
        return result
    for label, metrics in per_class.items():
        if not isinstance(metrics, dict):
            continue
        total = int(metrics.get("total", 0))
        real = int(metrics.get("real", 0))
        synthetic = int(metrics.get("synthetic", 0))
        result[str(label)] = {
            "total": total,
            "real": real,
            "synthetic": synthetic,
        }
    return result


def extract_unknown_total(report: Dict[str, object]) -> int:
    unknown = report.get("unknown_labels", {})
    if not isinstance(unknown, dict):
        return 0
    return sum(int(value) for value in unknown.values())


def extract_failing_gates(report: Dict[str, object]) -> List[str]:
    gating = report.get("gating_results", [])
    failures: List[str] = []
    if not isinstance(gating, list):
        return failures
    for entry in gating:
        if not isinstance(entry, dict):
            continue
        if not entry.get("passed", True):
            failures.append(str(entry.get("name", "unknown_gate")))
    return failures


def compute_class_deltas(
    baseline_counts: Dict[str, Dict[str, int]],
    candidate_counts: Dict[str, Dict[str, int]],
    ignore_labels: Set[str],
) -> List[ClassDelta]:
    labels = set(baseline_counts.keys()) | set(candidate_counts.keys())
    deltas: List[ClassDelta] = []
    for label in sorted(labels):
        if label in ignore_labels:
            continue
        base_metrics = baseline_counts.get(label, {"total": 0, "real": 0, "synthetic": 0})
        cand_metrics = candidate_counts.get(label, {"total": 0, "real": 0, "synthetic": 0})
        delta = cand_metrics["total"] - base_metrics["total"]
        deltas.append(
            ClassDelta(
                label=label,
                baseline_total=base_metrics["total"],
                candidate_total=cand_metrics["total"],
                delta=delta,
                real_delta=cand_metrics["real"] - base_metrics["real"],
                synthetic_delta=cand_metrics["synthetic"] - base_metrics["synthetic"],
            )
        )
    return deltas


def compare_reports(options: CompareOptions) -> CompareResult:
    baseline = load_report(options.baseline_path)
    candidate = load_report(options.candidate_path)

    baseline_counts = extract_class_counts(baseline)
    candidate_counts = extract_class_counts(candidate)
    deltas = compute_class_deltas(baseline_counts, candidate_counts, options.ignore_labels)

    unknown_delta = extract_unknown_total(candidate) - extract_unknown_total(baseline)
    gating_regressions = extract_failing_gates(candidate)

    passes = True
    if gating_regressions:
        passes = False

    max_allowed_drop = options.max_drop * -1
    for delta in deltas:
        if delta.delta < max_allowed_drop:
            passes = False
            break

    if unknown_delta > 0:
        passes = False

    return CompareResult(
        class_deltas=deltas,
        gating_regressions=gating_regressions,
        unknown_label_delta=unknown_delta,
        passes=passes,
    )


def format_table(rows: List[Tuple[str, str, str, str]]) -> str:
    widths = [0, 0, 0, 0]
    for idx in range(4):
        widths[idx] = max(len(row[idx]) for row in rows)
    lines = []
    for i, row in enumerate(rows):
        padded = [row[idx].ljust(widths[idx]) for idx in range(4)]
        line = " | ".join(padded)
        lines.append(line)
        if i == 0:
            lines.append("-+-".join("-" * widths[idx] for idx in range(4)))
    return "\n".join(lines)


def write_json_diff(result: CompareResult, path: Path) -> None:
    data = {
        "passes": result.passes,
        "unknown_label_delta": result.unknown_label_delta,
        "gating_regressions": result.gating_regressions,
        "class_deltas": [
            {
                "label": delta.label,
                "baseline_total": delta.baseline_total,
                "candidate_total": delta.candidate_total,
                "delta": delta.delta,
                "real_delta": delta.real_delta,
                "synthetic_delta": delta.synthetic_delta,
            }
            for delta in result.class_deltas
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


def emit_summary(result: CompareResult) -> None:
    header = ("Label", "Baseline", "Candidate", "Δ")
    rows: List[Tuple[str, str, str, str]] = [header]
    for delta in result.class_deltas:
        rows.append(
            (
                delta.label,
                str(delta.baseline_total),
                str(delta.candidate_total),
                f"{delta.delta:+d}",
            )
        )
    print(format_table(rows))
    print()
    if result.unknown_label_delta != 0:
        print(f"Unknown labels delta: {result.unknown_label_delta:+d}")
    if result.gating_regressions:
        print("Gating regressions detected:")
        for gate in result.gating_regressions:
            print(f"  - {gate}")
    status = "PASSED" if result.passes else "FAILED"
    print(f"Comparison status: {status}")


def main(argv: Optional[List[str]] = None) -> int:
    options = parse_args(argv)
    result = compare_reports(options)

    emit_summary(result)
    if options.json_output:
        write_json_diff(result, options.json_output)

    return 0 if result.passes else 2


if __name__ == "__main__":
    sys.exit(main())
