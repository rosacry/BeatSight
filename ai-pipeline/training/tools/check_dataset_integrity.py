#!/usr/bin/env python3
"""Validate dataset presence and optional checksum manifests prior to exports.

This helper replaces the manual folder spot-checks we used to run before kicking
off a full `build_training_dataset.py` job. It reads a configuration file that
lists dataset roots and (optionally) checksum manifests. The script then
confirms that at least one root for each dataset exists, and when requested it
walks the checksum manifest to ensure every referenced file is present. A
`--recompute-digests` option is available for deeper audits, though it is much
slower because it hashes each file from disk.

Example usage
-------------

    python ai-pipeline/training/tools/check_dataset_integrity.py \
        --config ai-pipeline/training/configs/dataset_integrity.json \
        --verify-manifests --max-checks 1000

The above command verifies that every dataset root exists and spot-checks the
first 1,000 checksum entries for each dataset. Run without `--max-checks` to
walk an entire manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from training.tools import ingest_utils


@dataclass
class DatasetConfig:
    name: str
    roots: List[Path]
    checksum_manifest: Optional[Path]


@dataclass
class DatasetResult:
    config: DatasetConfig
    resolved_root: Optional[Path]
    errors: List[str]
    warnings: List[str]
    files_checked: int = 0
    digests_recomputed: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_config(path: Path) -> List[DatasetConfig]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    datasets: List[DatasetConfig] = []
    for entry in payload.get("datasets", []):
        name = entry.get("name")
        roots_raw = entry.get("roots") or []
        if not name or not roots_raw:
            raise ValueError(f"Invalid dataset entry in {path}: {entry}")
        roots = [ingest_utils.resolve_repo_path(str(root)) for root in roots_raw]
        manifest_raw = entry.get("checksum_manifest")
        manifest = (
            ingest_utils.resolve_repo_path(str(manifest_raw))
            if manifest_raw
            else None
        )
        datasets.append(DatasetConfig(name=name, roots=roots, checksum_manifest=manifest))
    return datasets


def choose_existing_root(candidates: Iterable[Path]) -> Optional[Path]:
    for path in candidates:
        if path.exists():
            return path
    return None


def sha256_path(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(
    dataset: DatasetConfig,
    root: Path,
    manifest: Path,
    *,
    recompute: bool,
    max_checks: Optional[int],
    verbose: bool,
) -> tuple[List[str], int, int]:
    errors: List[str] = []
    files_checked = 0
    digests_recomputed = 0

    if not manifest.exists():
        errors.append(f"checksum manifest is missing: {manifest}")
        return errors, files_checked, digests_recomputed

    try:
        handle = manifest.open("r", encoding="utf-8")
    except OSError as exc:
        errors.append(f"unable to open checksum manifest {manifest}: {exc}")
        return errors, files_checked, digests_recomputed

    with handle:
        for line_number, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) < 2:
                errors.append(
                    f"{dataset.name}: malformed manifest line {line_number} in {manifest}: {raw!r}"
                )
                continue
            digest = parts[0]
            rel_path = " ".join(parts[1:])
            candidate = root / rel_path
            files_checked += 1

            if not candidate.exists():
                errors.append(
                    f"{dataset.name}: missing file referenced by manifest ({rel_path})"
                )
                if max_checks and files_checked >= max_checks:
                    break
                continue

            if recompute:
                actual = sha256_path(candidate)
                digests_recomputed += 1
                if actual.lower() != digest.lower():
                    errors.append(
                        f"{dataset.name}: checksum mismatch for {rel_path} (expected {digest}, got {actual})"
                    )

            if verbose and files_checked % 1000 == 0:
                print(
                    f"[{dataset.name}] verified {files_checked} entries...",
                    file=sys.stderr,
                )

            if max_checks and files_checked >= max_checks:
                break

    return errors, files_checked, digests_recomputed


def run_checks(
    datasets: List[DatasetConfig],
    *,
    verify_manifests: bool,
    recompute: bool,
    max_checks: Optional[int],
    verbose: bool,
) -> List[DatasetResult]:
    results: List[DatasetResult] = []
    for dataset in datasets:
        errors: List[str] = []
        warnings: List[str] = []
        selected_root = choose_existing_root(dataset.roots)
        if selected_root is None:
            errors.append(
                "no dataset root found; checked: "
                + ", ".join(str(path) for path in dataset.roots)
            )
        else:
            if verbose:
                print(f"[{dataset.name}] using root {selected_root}")

        files_checked = 0
        digests_recomputed = 0

        if verify_manifests and selected_root is not None:
            manifest = dataset.checksum_manifest
            if manifest is None:
                warnings.append("no checksum manifest defined; skipping manifest verification")
            else:
                manifest_errors, files_checked, digests_recomputed = verify_manifest(
                    dataset,
                    selected_root,
                    manifest,
                    recompute=recompute,
                    max_checks=max_checks,
                    verbose=verbose,
                )
                errors.extend(manifest_errors)

        results.append(
            DatasetResult(
                config=dataset,
                resolved_root=selected_root,
                errors=errors,
                warnings=warnings,
                files_checked=files_checked,
                digests_recomputed=digests_recomputed,
            )
        )
    return results


def format_summary(results: List[DatasetResult]) -> str:
    lines: List[str] = []
    lines.append("\nDataset integrity summary")
    lines.append("================================")
    for result in results:
        status = "OK" if result.ok else "ERROR"
        lines.append(f"* {result.config.name}: {status}")
        if result.resolved_root is not None:
            lines.append(f"    root: {result.resolved_root}")
        else:
            lines.append("    root: <missing>")
        if result.files_checked:
            lines.append(
                f"    manifest entries checked: {result.files_checked}"
            )
            if result.digests_recomputed:
                lines.append(
                    f"    digests recomputed: {result.digests_recomputed}"
                )
        for warning in result.warnings:
            lines.append(f"    warning: {warning}")
        for error in result.errors:
            lines.append(f"    error: {error}")
    return "\n".join(lines)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("ai-pipeline/training/configs/dataset_integrity.json"),
        help="Path to dataset integrity configuration JSON",
    )
    parser.add_argument(
        "--verify-manifests",
        action="store_true",
        help="Walk checksum manifests and ensure referenced files exist",
    )
    parser.add_argument(
        "--recompute-digests",
        action="store_true",
        help="Recompute SHA256 for each manifest entry (slow)",
    )
    parser.add_argument(
        "--max-checks",
        type=int,
        help="Optional limit on the number of manifest entries to inspect per dataset",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress information to stderr",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    config_path = ingest_utils.resolve_repo_path(str(args.config))
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        datasets = parse_config(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Failed to parse config {config_path}: {exc}", file=sys.stderr)
        return 2

    results = run_checks(
        datasets,
        verify_manifests=args.verify_manifests,
        recompute=args.recompute_digests,
        max_checks=args.max_checks,
        verbose=args.verbose,
    )

    print(format_summary(results))

    failures = sum(1 for result in results if not result.ok)
    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
