#!/usr/bin/env python3
"""Generate SHA256 checksums for a dataset directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys
from typing import Iterable

CHUNK_SIZE = 1 << 20  # 1 MiB


def sha256_path(path: pathlib.Path) -> str:
    h_obj = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            h_obj.update(chunk)
    return h_obj.hexdigest()


def iter_files(root: pathlib.Path, follow_symlinks: bool) -> Iterable[pathlib.Path]:
    for base, dirs, files in os.walk(root, followlinks=follow_symlinks):
        base_path = pathlib.Path(base)
        for name in sorted(files):
            yield base_path / name


def write_manifest(root: pathlib.Path, output: pathlib.Path, follow_symlinks: bool) -> None:
    root = root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for file_path in iter_files(root, follow_symlinks):
            digest = sha256_path(file_path)
            relative = file_path.relative_to(root)
            handle.write(f"{digest}  {relative.as_posix()}\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=pathlib.Path, help="Directory to hash")
    parser.add_argument("output", type=pathlib.Path, help="Output .sha256 file")
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symbolic links while traversing the directory"
    )
    args = parser.parse_args(argv)

    if not args.root.exists():
        print(f"error: root does not exist: {args.root}", file=sys.stderr)
        sys.exit(2)

    write_manifest(args.root, args.output, follow_symlinks=args.follow_symlinks)


if __name__ == "__main__":
    main()
