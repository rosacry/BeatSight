#!/usr/bin/env python3
"""Simple grid-search driver for drum classifier training.

Example:
    python training/tools/hparam_sweep.py \
        --dataset training/dev_dataset \
        --batch-sizes 8 16 \
        --epochs 3 5 \
        --learning-rates 0.001 0.0005 \
        --device cuda \
        --output-root training/hparam_runs \
        --report training/reports/hparam_sweep.json

The script iterates over the Cartesian product of the provided hyperparameter
lists, launches ``train_classifier.py`` for each combination, and aggregates the
resulting metrics JSON files. Runs are skipped when a prior metrics file exists
unless ``--rerun`` is specified.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class SweepConfig:
    dataset: Path
    batch_sizes: List[int]
    epochs: List[int]
    learning_rates: List[float]
    device: str | None
    output_root: Path
    report_path: Path | None
    rerun: bool


TRAIN_SCRIPT = Path(__file__).resolve().parents[1] / "train_classifier.py"


def parse_args() -> SweepConfig:
    parser = argparse.ArgumentParser(description="Grid search for drum classifier")
    parser.add_argument("--dataset", required=True, type=Path, help="Dataset root passed to train_classifier.py")
    parser.add_argument(
        "--batch-sizes",
        nargs="+",
        type=int,
        default=[32],
        help="List of batch sizes to evaluate",
    )
    parser.add_argument(
        "--epochs",
        nargs="+",
        type=int,
        default=[50],
        help="List of epoch counts to evaluate",
    )
    parser.add_argument(
        "--learning-rates",
        nargs="+",
        type=float,
        default=[0.001],
        help="Learning rates to evaluate",
    )
    parser.add_argument("--device", help="Device to pass through (cuda/cpu)")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("training/hparam_runs"),
        help="Root directory for sweep outputs",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write aggregated metrics JSON",
    )
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Re-run combinations even if metrics already exist",
    )
    args = parser.parse_args()

    return SweepConfig(
        dataset=args.dataset,
        batch_sizes=args.batch_sizes,
        epochs=args.epochs,
        learning_rates=args.learning_rates,
        device=args.device,
        output_root=args.output_root,
        report_path=args.report,
        rerun=args.rerun,
    )


def run_training(config: SweepConfig) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    combinations = list(
        itertools.product(config.batch_sizes, config.epochs, config.learning_rates)
    )
    if not combinations:
        return results

    config.output_root.mkdir(parents=True, exist_ok=True)

    for batch_size, epochs, lr in combinations:
        run_dir = config.output_root / f"bs{batch_size}_ep{epochs}_lr{lr}".replace(".", "p")
        metrics_path = run_dir / "metrics.json"

        if metrics_path.exists() and not config.rerun:
            with metrics_path.open("r", encoding="utf-8") as handle:
                results.append(json.load(handle))
            print(f"Skipping existing run: batch={batch_size}, epochs={epochs}, lr={lr}")
            continue

        run_dir.mkdir(parents=True, exist_ok=True)

        cmd: list[str] = [
            sys.executable,
            str(TRAIN_SCRIPT),
            "--dataset",
            str(config.dataset),
            "--batch-size",
            str(batch_size),
            "--epochs",
            str(epochs),
            "--lr",
            str(lr),
            "--output",
            str(run_dir),
            "--metrics-json",
            str(metrics_path),
        ]

        if config.device:
            cmd.extend(["--device", config.device])

        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True)

        with metrics_path.open("r", encoding="utf-8") as handle:
            metrics = json.load(handle)
        results.append(metrics)

    return results


def summarise(results: Iterable[dict[str, object]]) -> dict[str, object]:
    best = None
    for entry in results:
        if entry is None:
            continue
        if best is None or entry.get("best_validation_accuracy", -1) > best.get(
            "best_validation_accuracy", -1
        ):
            best = entry

    summary = {
        "runs": list(results),
        "best": best,
    }
    return summary


def main() -> None:
    config = parse_args()
    results = run_training(config)
    summary = summarise(results)

    if config.report_path:
        config.report_path.parent.mkdir(parents=True, exist_ok=True)
        with config.report_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        print(f"Wrote summary to {config.report_path}")

    best = summary.get("best")
    if best:
        print(
            "Best run:",
            f"batch_size={best['batch_size']}, epochs={best['epochs']}, lr={best['learning_rate']},",
            f"best_val_acc={best['best_validation_accuracy']:.2f}%",
        )
    else:
        print("No runs executed.")


if __name__ == "__main__":
    main()
