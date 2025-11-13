#!/usr/bin/env python3
"""Annotate technique inferences for existing event manifests."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
from collections import Counter
from typing import Counter as CounterType, Optional, TextIO

_THIS_FILE = pathlib.Path(__file__).resolve()
_PACKAGE_ROOT = _THIS_FILE.parents[2]
if str(_PACKAGE_ROOT) not in sys.path:  # pragma: no cover - path shim when executed as script
    sys.path.insert(0, str(_PACKAGE_ROOT))

try:  # pragma: no cover - import shim for script/packaged usage
    from . import ingest_utils  # type: ignore
except ImportError:  # pragma: no cover - fallback when executed as a module
    from training.tools import ingest_utils  # type: ignore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply taxonomy-driven inference to an existing events JSONL manifest "
            "so downstream readiness gates (technique coverage, sampling boosts) "
            "do not require a full reingest."
        )
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the source events JSONL file (relative to repo root allowed).",
    )
    parser.add_argument(
        "--output",
        "-o",
        help=(
            "Optional output path for the annotated manifest. "
            "When omitted, --in-place must be provided."
        ),
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file atomically with the inferred technique annotations.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and print inferred technique counts without writing output.",
    )
    parser.add_argument(
        "--taxonomy",
        type=pathlib.Path,
        default=ingest_utils.TECHNIQUE_TAXONOMY_PATH,
        help=(
            "Optional path to the technique taxonomy JSON. Only used to verify the file exists; "
            "ingestion utilities load it automatically."
        ),
    )
    return parser.parse_args()


def _ensure_list(value) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, (set, tuple)):
        return list(value)
    return [value]


def _process_manifest(
    path: pathlib.Path,
    writer: Optional[TextIO] = None,
) -> CounterType[str]:
    counts: CounterType[str] = Counter()
    current_session: Optional[str] = None
    buffer: list[dict] = []

    def flush() -> None:
        nonlocal counts, buffer
        if not buffer:
            return
        ingest_utils.apply_taxonomy_inference(buffer)
        for event in buffer:
            techniques = _ensure_list(event.get("techniques"))
            unique = sorted({str(item) for item in techniques if item})
            event["techniques"] = unique
            for technique in unique:
                counts[technique] += 1
            if writer is not None:
                writer.write(json.dumps(event, separators=(",", ":")) + "\n")
        buffer.clear()

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"Failed to parse JSON on line {line_number} of {path}: {exc}") from exc

            session_id = str(event.get("session_id") or "__unknown_session__")
            if current_session is None:
                current_session = session_id
            elif session_id != current_session:
                flush()
                current_session = session_id

            if not isinstance(event.get("techniques"), list):
                event["techniques"] = _ensure_list(event.get("techniques"))
            buffer.append(event)

    flush()
    return counts


def _print_summary(counts: CounterType[str]) -> None:
    if not counts:
        print("No techniques present after inference.")
        return
    print("Technique counts (event-level):")
    for technique, total in counts.most_common():
        print(f"  {technique}: {total}")


def main() -> None:
    args = _parse_args()

    input_path = ingest_utils.resolve_repo_path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input manifest not found: {input_path}")

    taxonomy_path = ingest_utils.resolve_repo_path(str(args.taxonomy))
    if not taxonomy_path.exists():
        raise FileNotFoundError(
            f"Technique taxonomy missing at {taxonomy_path}. Generate it before annotating manifests."
        )

    if args.dry_run:
        counts = _process_manifest(input_path, writer=None)
        _print_summary(counts)
        return

    if args.output:
        output_path = ingest_utils.resolve_repo_path(args.output)
    elif args.in_place:
        output_path = input_path
    else:
        raise ValueError("Specify --output or --in-place to determine where to write results.")

    if args.in_place:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=input_path.parent) as tmp:
            temp_path = pathlib.Path(tmp.name)
            counts = _process_manifest(input_path, writer=tmp)
        temp_path.replace(input_path)
        output_display = input_path
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            counts = _process_manifest(input_path, writer=handle)
        output_display = output_path

    _print_summary(counts)
    print(f"Annotated manifest written to {output_display}")


if __name__ == "__main__":
    main()
