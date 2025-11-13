#!/usr/bin/env python3
"""Run BeatSight's standard post-ingest checklist.

This helper script bundles the validation steps we normally trigger after
regenerating manifest files:

* Dataset health analysis (`training/dataset_health.py`)
* Event loader regression test (`pytest ai-pipeline/tests/test_event_loader.py`)
* Sampling weight derivation (`training/tools/derive_sampling_weights.py`)

Each step can be toggled via CLI flags, and additional arguments can be
forwarded to the underlying tools when needed.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


def _as_shell(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(token) for token in cmd)


def run_command(cmd: Sequence[str], *, description: str, keep_going: bool) -> None:
    print(f"\n>>> {description}: {_as_shell(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        message = f"[{description}] exited with code {result.returncode}"
        print(message, file=sys.stderr)
        if not keep_going:
            raise SystemExit(result.returncode)


def default_health_reports(events_path: Path) -> tuple[Path, Path]:
    stem = events_path.stem or "events"
    base_dir = Path("ai-pipeline/training/reports/health")
    json_report = base_dir / f"{stem}_health.json"
    html_report = base_dir / f"{stem}_health.html"
    json_report.parent.mkdir(parents=True, exist_ok=True)
    html_report.parent.mkdir(parents=True, exist_ok=True)
    return json_report, html_report


def default_weights_path(manifest_path: Path) -> Path:
    stem = manifest_path.stem or "events"
    base_dir = Path("ai-pipeline/training/reports/sampling")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{stem}_weights.json"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, type=Path, help="Events JSONL manifest to validate")
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Manifest to pass to derive_sampling_weights (defaults to --events)",
    )
    parser.add_argument(
        "--weights-output",
        type=Path,
        help="Destination JSON for sampling weights (defaults to <manifest>_weights.json)",
    )
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="Python interpreter used to spawn child steps",
    )
    parser.add_argument(
        "--sampling-profile",
        help="Optional sampling profile key forwarded to derive_sampling_weights",
    )
    parser.add_argument(
        "--derive-arg",
        dest="derive_args",
        action="append",
        default=[],
        help="Additional argument to append when invoking derive_sampling_weights (repeatable)",
    )
    parser.add_argument(
        "--health-report",
        type=Path,
        help="Explicit JSON report path for dataset_health (default derives from --events)",
    )
    parser.add_argument(
        "--health-html",
        type=Path,
        help="Explicit HTML report path for dataset_health (default derives from --events)",
    )
    parser.add_argument(
        "--health-arg",
        dest="health_args",
        action="append",
        default=[],
        help="Additional argument forwarded to dataset_health.py (repeatable)",
    )
    parser.add_argument(
        "--pytest-arg",
        dest="pytest_args",
        action="append",
        default=[],
        help="Extra pytest argument when running event loader regression (repeatable)",
    )
    parser.add_argument("--skip-dataset-health", action="store_true", help="Skip dataset health analysis")
    parser.add_argument("--skip-event-loader", action="store_true", help="Skip pytest event loader regression")
    parser.add_argument(
        "--skip-sampling-weights",
        action="store_true",
        help="Skip derive_sampling_weights invocation",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue running remaining steps even if one fails",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    events_path = args.events.resolve()
    manifest_path = (args.manifest or events_path).resolve()
    weights_path = (args.weights_output or default_weights_path(manifest_path)).resolve()
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    python_exe = str(args.python)

    default_health_json, default_health_html = default_health_reports(events_path)
    health_json = (args.health_report or default_health_json).resolve()
    health_json.parent.mkdir(parents=True, exist_ok=True)
    health_html = (args.health_html or default_health_html).resolve()
    health_html.parent.mkdir(parents=True, exist_ok=True)

    steps: List[tuple[str, List[str]]] = []

    if not args.skip_dataset_health:
        cmd = [
            python_exe,
            "ai-pipeline/training/dataset_health.py",
            "--events",
            str(events_path),
            "--output",
            str(health_json),
            "--html-output",
            str(health_html),
        ]
        for token in args.health_args:
            cmd.append(token)
        steps.append(("dataset_health", cmd))

    if not args.skip_event_loader:
        cmd = [python_exe, "-m", "pytest", "ai-pipeline/tests/test_event_loader.py"]
        cmd.extend(args.pytest_args)
        steps.append(("pytest_event_loader", cmd))

    if not args.skip_sampling_weights:
        cmd = [
            python_exe,
            "ai-pipeline/training/tools/derive_sampling_weights.py",
            str(manifest_path),
            "--output",
            str(weights_path),
        ]
        if args.sampling_profile:
            cmd.extend(["--profile", args.sampling_profile])
        for token in args.derive_args:
            cmd.append(token)
        steps.append(("derive_sampling_weights", cmd))

    if not steps:
        print("No steps requested; exiting.")
        return 0

    for description, command in steps:
        run_command(command, description=description, keep_going=args.keep_going)

    print("\nPost-ingest checklist completed.")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
