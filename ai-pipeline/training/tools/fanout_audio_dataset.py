#!/usr/bin/env python3
"""Reorganise dataset audio clips into fanout subdirectories.

Large BeatSight training datasets historically stored every ``.wav`` clip flat under
``<split>/audio``. Once the directory contains millions of files, ext4 can begin to
fail individual creations with ``ENOSPC`` even though the filesystem still has ample
space. This helper migrates an existing dataset to a hierarchical layout by deriving
subdirectories from the leading characters of each clip's ``event_id``.

The script performs three steps for each ``train``/``val`` split:

1. Temporarily rename ``<split>/audio`` to ``audio_flat`` so we can stream files without
    duplicating the dataset.
2. Move audio files into ``audio/<fanout>/<filename>`` folders.
3. Rewrite ``*_labels.json`` entries so the ``file`` attribute points at the new path.
4. Update ``metadata.json`` with the effective fanout so future resume runs stay
   consistent.

The migration is idempotent and safe to re-run. Use ``--dry-run`` to inspect the
planned changes without modifying the dataset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple


@dataclass
class SplitSummary:
    name: str
    moved: int
    skipped: int
    label_updates: int


def _normalise_clip_id(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum()).lower()


def _fanout_prefix_from_filename(filename: str, fanout: int) -> Optional[str]:
    if fanout <= 0:
        return None
    clip_id = filename.split("__", 1)[0]
    normalised = _normalise_clip_id(clip_id)
    if not normalised:
        return None
    if len(normalised) < fanout:
        normalised = (normalised + "0" * fanout)[:fanout]
    else:
        normalised = normalised[:fanout]
    return normalised


def _move_audio_files(source_dir: Path, target_dir: Path, fanout: int, *, dry_run: bool) -> Tuple[int, int]:
    moved = 0
    skipped = 0
    if fanout <= 0:
        return moved, skipped
    try:
        iterator = os.scandir(source_dir)
    except FileNotFoundError:
        return moved, skipped

    with iterator as entries:
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                continue
            if not entry.is_file(follow_symlinks=False):
                skipped += 1
                continue
            filename = entry.name
            if "/" in filename or filename.count("__") == 0:
                skipped += 1
                continue
            prefix = _fanout_prefix_from_filename(filename, fanout)
            if not prefix:
                skipped += 1
                continue
            target_path = target_dir / prefix / filename
            if Path(entry.path) == target_path:
                continue
            if not dry_run:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    Path(entry.path).rename(target_path)
                except FileNotFoundError:
                    skipped += 1
                    continue
            moved += 1
    return moved, skipped


def _prepare_fanout_directories(split_dir: Path, fanout: int, *, dry_run: bool) -> Tuple[Path, Path]:
    target_dir = split_dir / "audio"
    if fanout <= 0:
        return target_dir, target_dir

    staging_dir = split_dir / "audio_flat"
    if staging_dir.exists():
        if not dry_run and not target_dir.exists():
            target_dir.mkdir()
        return staging_dir, target_dir

    if not target_dir.exists():
        return target_dir, target_dir

    if dry_run:
        print(f"[DRY-RUN] Would rename {target_dir} -> {staging_dir}")
        print(f"[DRY-RUN] Would create empty {target_dir} for fanout output")
        return target_dir, target_dir

    target_dir.rename(staging_dir)
    target_dir.mkdir()
    return staging_dir, target_dir


def _transform_label_line(line: str, fanout: int) -> Tuple[str, bool]:
    marker = '"file": "'
    idx = line.find(marker)
    if idx == -1:
        return line, False
    start = idx + len(marker)
    end = line.find('"', start)
    if end == -1:
        return line, False
    rel_path = line[start:end]
    prefix = "audio/"
    if not rel_path.startswith(prefix):
        return line, False
    suffix = rel_path[len(prefix):]
    if not suffix or "/" in suffix:
        return line, False
    fanout_prefix = _fanout_prefix_from_filename(suffix, fanout)
    if not fanout_prefix:
        return line, False
    new_rel = f"{prefix}{fanout_prefix}/{suffix}"
    if new_rel == rel_path:
        return line, False
    return line[:start] + new_rel + line[end:], True


def _rewrite_label_file(label_path: Path, fanout: int, *, dry_run: bool) -> int:
    if fanout <= 0 or not label_path.exists():
        return 0

    needs_update = False
    with label_path.open("r", encoding="utf-8") as probe:
        for idx, line in enumerate(probe):
            _, changed = _transform_label_line(line, fanout)
            if changed:
                needs_update = True
                break
            if idx >= 100_000:
                break
    if not needs_update:
        return 0

    updates = 0
    if dry_run:
        with label_path.open("r", encoding="utf-8") as src:
            for line in src:
                _, changed = _transform_label_line(line, fanout)
                if changed:
                    updates += 1
        return updates

    tmp_path = label_path.with_suffix(label_path.suffix + ".fanout_tmp")
    with label_path.open("r", encoding="utf-8") as src, tmp_path.open("w", encoding="utf-8") as dst:
        for line in src:
            new_line, changed = _transform_label_line(line, fanout)
            if changed:
                updates += 1
            dst.write(new_line)
    tmp_path.replace(label_path)
    return updates


def _update_metadata(dataset_root: Path, fanout: int, *, dry_run: bool) -> None:
    metadata_path = dataset_root / "metadata.json"
    if not metadata_path.exists():
        return
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[WARN] Skipping metadata update: failed to parse {metadata_path}", file=sys.stderr)
        return
    current = data.get("clip_fanout")
    if current == fanout:
        return
    data["clip_fanout"] = fanout
    if dry_run:
        print(f"[DRY-RUN] Would update clip_fanout to {fanout} in {metadata_path}")
        return
    metadata_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _process_split(split_dir: Path, fanout: int, *, dry_run: bool) -> Optional[SplitSummary]:
    source_dir, target_dir = _prepare_fanout_directories(split_dir, fanout, dry_run=dry_run)
    if fanout > 0 and not source_dir.exists():
        return None
    moved, skipped = _move_audio_files(source_dir, target_dir, fanout, dry_run=dry_run)
    label_path = split_dir / f"{split_dir.name}_labels.json"
    label_updates = _rewrite_label_file(label_path, fanout, dry_run=dry_run)
    if not dry_run and fanout > 0 and source_dir != target_dir and source_dir.exists():
        with os.scandir(source_dir) as probe:
            try:
                next(probe)
                has_entries = True
            except StopIteration:
                has_entries = False
        if not has_entries:
            source_dir.rmdir()
    return SplitSummary(split_dir.name, moved, skipped, label_updates)


def _iter_splits(dataset_root: Path) -> Iterable[Path]:
    for entry in sorted(dataset_root.iterdir()):
        if entry.is_dir() and (entry / "audio").exists():
            yield entry


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_root", type=Path, help="Existing dataset directory to reorganise")
    parser.add_argument(
        "--fanout",
        type=int,
        default=2,
        help=(
            "Number of leading alphanumeric characters from clip_id to use for directory fanout. "
            "Use 0 to keep the flat layout."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned changes without modifying any files",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    dataset_root = args.dataset_root.expanduser().resolve()
    if not dataset_root.exists():
        print(f"Dataset root not found: {dataset_root}", file=sys.stderr)
        return 1
    if args.fanout < 0:
        print("Fanout depth must be non-negative", file=sys.stderr)
        return 1

    summaries = []
    for split_dir in _iter_splits(dataset_root):
        summary = _process_split(split_dir, args.fanout, dry_run=args.dry_run)
        if summary is not None:
            summaries.append(summary)

    if not summaries:
        print("No audio splits discovered; nothing to do.")
    else:
        for summary in summaries:
            print(
                f"[{summary.name}] moved={summary.moved:,} skipped={summary.skipped:,} "
                f"label_updates={summary.label_updates:,}"
            )

    _update_metadata(dataset_root, args.fanout, dry_run=args.dry_run)
    if args.dry_run:
        print("Dry run complete; no files were modified.")
    else:
        print("Fanout migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
