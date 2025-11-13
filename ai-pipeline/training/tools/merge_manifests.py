#!/usr/bin/env python3
"""Stream multiple event manifests into a single JSONL file."""

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Iterable

_THIS_FILE = pathlib.Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[3]


def _resolve(path: str) -> pathlib.Path:
    raw = pathlib.Path(path)
    if not raw.is_absolute():
        raw = _REPO_ROOT / raw
    return raw.expanduser().resolve()


def _iter_events(paths: Iterable[pathlib.Path], validate: bool = False):
    for index, path in enumerate(paths, start=1):
        if not path.exists():
            print(f"[merge_manifests] Skipping missing manifest #{index}: {path}", file=sys.stderr)
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                if validate:
                    try:
                        import json  # local import to avoid global dependency when unused

                        json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        raise ValueError(
                            f"Malformed JSON in {path} at line {line_number}: {exc}"
                        ) from exc
                yield stripped


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concatenate JSONL manifests with minimal memory usage")
    parser.add_argument(
        "--input",
        "-i",
        action="append",
        required=True,
        help="Path to an events JSONL manifest. Repeat to include multiple files.",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Destination JSONL file that receives the merged events.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Parse each line as JSON before writing to guard against malformed input (slower).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    inputs = [_resolve(path) for path in args.input]
    output_path = _resolve(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_events = 0
    with output_path.open("w", encoding="utf-8") as writer:
        for payload in _iter_events(inputs, validate=args.validate):
            writer.write(payload)
            writer.write("\n")
            total_events += 1

    print(f"Merged {len(inputs)} manifests -> {output_path} ({total_events:,} events)")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
