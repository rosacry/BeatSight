"""Convenience wrapper to invoke BeatSight dataset readiness checks.

This script runs the alignment, boundary, open-set, and bootstrap evaluations
with consistent gating. Any failed check returns a non-zero exit code, which
makes it easy to wire into CI pipelines.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dataset readiness checks")

    parser.add_argument("--alignment-manifest", help="JSON manifest for multi-mic alignment (passed to align_qc.py)")
    parser.add_argument("--alignment-session-dir", help="Alternative directory input for align_qc.py")
    parser.add_argument("--alignment-report", help="Where to write alignment_report.json")

    parser.add_argument("--boundary-ground-truth", help="Boundary pack ground-truth JSONL")
    parser.add_argument("--boundary-predictions", help="Boundary pack prediction JSONL")
    parser.add_argument("--boundary-report", help="Boundary metrics report path")
    parser.add_argument("--boundary-threshold", type=float, default=0.5, help="Boundary eval threshold")

    parser.add_argument("--openset-ground-truth", help="Open-set labels JSONL with is_known flag")
    parser.add_argument("--openset-predictions", help="Open-set predictions JSONL")
    parser.add_argument("--openset-report", help="Open-set metrics report path")

    parser.add_argument("--bootstrap-ground-truth", help="Evaluation split ground-truth JSONL")
    parser.add_argument("--bootstrap-predictions", help="Evaluation split predictions JSONL")
    parser.add_argument("--bootstrap-report", help="Bootstrap metrics report path")
    parser.add_argument("--bootstrap-iterations", type=int, default=1000, help="Bootstrap resample count")

    parser.add_argument(
        "--health-events",
        help="Events JSONL for dataset_health.py analysis",
    )
    parser.add_argument(
        "--health-components",
        help="Optional taxonomy JSON for dataset_health.py",
    )
    parser.add_argument(
        "--health-report",
        help="Optional path to write dataset health JSON report",
    )
    parser.add_argument(
        "--health-html-report",
        help="Optional path to write dataset health HTML summary",
    )
    parser.add_argument(
        "--health-max-duplication-rate",
        type=float,
        help="Optional duplication gate (0-1) for dataset health",
    )
    parser.add_argument(
        "--health-min-class-count",
        type=int,
        help="Minimum examples required per label when running dataset health",
    )
    parser.add_argument(
        "--health-min-counts-json",
        help="JSON mapping of label→minimum count for dataset health",
    )
    parser.add_argument(
        "--health-require-label",
        action="append",
        default=[],
        help="Ensure specific labels appear at least once in dataset health",
    )
    parser.add_argument(
        "--health-require-labels-file",
        action="append",
        help="File of required labels (one per line) for dataset health",
    )
    parser.add_argument(
        "--health-max-unknown-labels",
        type=int,
        help="Maximum total unknown label count allowed in dataset health",
    )

    parser.add_argument(
        "--checks",
        nargs="*",
        choices=["alignment", "boundary", "openset", "bootstrap", "health"],
        help="Restrict to specific checks",
    )
    parser.add_argument("--halt-on-first-failure", action="store_true", help="Stop after the first failed check")
    parser.add_argument("--python", default=sys.executable, help="Python executable to invoke child scripts")

    return parser.parse_args(argv)


def run_command(cmd: List[str], name: str) -> int:
    print(f"\n>>> Running {name}: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        print(f"[run_readiness_checks] {name} failed with exit code {result.returncode}", file=sys.stderr)
    return result.returncode


def ensure_report_path(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return str(out_path)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    checks = args.checks or ["alignment", "boundary", "openset", "bootstrap", "health"]

    failures: Dict[str, int] = {}

    if "alignment" in checks:
        if not (args.alignment_manifest or args.alignment_session_dir):
            print("[run_readiness_checks] Alignment check skipped (no manifest or session dir provided)")
        else:
            cmd = [args.python, str(Path(__file__).with_name("align_qc.py"))]
            if args.alignment_manifest:
                cmd.extend(["--manifest", args.alignment_manifest])
            if args.alignment_session_dir:
                cmd.extend(["--session-dir", args.alignment_session_dir])
            report_path = ensure_report_path(args.alignment_report)
            if report_path:
                cmd.extend(["--report", report_path])
            cmd.append("--strict")
            exit_code = run_command(cmd, "align_qc")
            if exit_code != 0:
                failures["alignment"] = exit_code
                if args.halt_on_first_failure:
                    return 1

    if "boundary" in checks:
        if not (args.boundary_ground_truth and args.boundary_predictions):
            print("[run_readiness_checks] Boundary check skipped (missing ground truth or predictions)")
        else:
            cmd = [
                args.python,
                str(Path(__file__).with_name("boundary_eval.py")),
                "--ground-truth",
                args.boundary_ground_truth,
                "--predictions",
                args.boundary_predictions,
                "--threshold",
                str(args.boundary_threshold),
                "--strict",
            ]
            report_path = ensure_report_path(args.boundary_report)
            if report_path:
                cmd.extend(["--report", report_path])
            exit_code = run_command(cmd, "boundary_eval")
            if exit_code != 0:
                failures["boundary"] = exit_code
                if args.halt_on_first_failure:
                    return 1

    if "openset" in checks:
        if not (args.openset_ground_truth and args.openset_predictions):
            print("[run_readiness_checks] Open-set check skipped (missing ground truth or predictions)")
        else:
            cmd = [
                args.python,
                str(Path(__file__).with_name("openset_eval.py")),
                "--ground-truth",
                args.openset_ground_truth,
                "--predictions",
                args.openset_predictions,
                "--strict",
            ]
            report_path = ensure_report_path(args.openset_report)
            if report_path:
                cmd.extend(["--report", report_path])
            exit_code = run_command(cmd, "openset_eval")
            if exit_code != 0:
                failures["openset"] = exit_code
                if args.halt_on_first_failure:
                    return 1

    if "bootstrap" in checks:
        if not (args.bootstrap_ground_truth and args.bootstrap_predictions and args.bootstrap_report):
            print("[run_readiness_checks] Bootstrap check skipped (missing ground truth, predictions, or report path)")
        else:
            cmd = [
                args.python,
                str(Path(__file__).with_name("bootstrap_eval.py")),
                "--ground-truth",
                args.bootstrap_ground_truth,
                "--predictions",
                args.bootstrap_predictions,
                "--report",
                ensure_report_path(args.bootstrap_report) or args.bootstrap_report,
                "--iterations",
                str(args.bootstrap_iterations),
            ]
            exit_code = run_command(cmd, "bootstrap_eval")
            if exit_code != 0:
                failures["bootstrap"] = exit_code
                if args.halt_on_first_failure:
                    return 1

    if "health" in checks:
        if not args.health_events:
            print("[run_readiness_checks] Dataset health check skipped (no events file provided)")
        else:
            cmd = [
                args.python,
                str(Path(__file__).with_name("dataset_health.py")),
                "--events",
                args.health_events,
            ]
            if args.health_components:
                cmd.extend(["--components", args.health_components])
            report_path = ensure_report_path(args.health_report)
            if report_path:
                cmd.extend(["--output", report_path])
            if args.health_max_duplication_rate is not None:
                cmd.extend([
                    "--max-duplication-rate",
                    str(args.health_max_duplication_rate),
                ])
            if args.health_html_report:
                cmd.extend(["--html-output", args.health_html_report])
            if args.health_min_class_count is not None:
                cmd.extend(["--min-class-count", str(args.health_min_class_count)])
            if args.health_min_counts_json:
                cmd.extend(["--min-counts-json", args.health_min_counts_json])
            for label in args.health_require_label or []:
                cmd.extend(["--require-label", label])
            for path in args.health_require_labels_file or []:
                cmd.extend(["--require-labels-file", path])
            if args.health_max_unknown_labels is not None:
                cmd.extend([
                    "--max-unknown-labels",
                    str(args.health_max_unknown_labels),
                ])
            exit_code = run_command(cmd, "dataset_health")
            if exit_code != 0:
                failures["health"] = exit_code
                if args.halt_on_first_failure:
                    return 1

    if failures:
        print("\nReadiness checks completed with failures:")
        for name, code in failures.items():
            print(f"  - {name}: exit code {code}")
        return 1

    print("\nAll requested readiness checks completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
