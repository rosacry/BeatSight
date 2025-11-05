"""Bootstrap confidence intervals for BeatSight dataset metrics.

Supports multi-label classification metrics (macro/micro F1, example-based F1)
plus regression metrics (openness MAE, velocity MAE). Resamples samples with
replacement to estimate 95% confidence intervals, enabling release gating on
statistical significance as described in the dataset readiness plan.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

import numpy as np


@dataclass
class SampleRecord:
    sample_id: str
    labels: Set[str]
    pred_labels: Set[str]
    openness_true: Optional[float] = None
    openness_pred: Optional[float] = None
    velocity_true: Optional[float] = None
    velocity_pred: Optional[float] = None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap evaluation")
    parser.add_argument("--ground-truth", required=True, help="JSONL with sample metadata and labels")
    parser.add_argument("--predictions", required=True, help="JSONL with predicted scores/labels and optional regressions")
    parser.add_argument("--threshold", type=float, default=0.5, help="Score threshold when binarising predictions")
    parser.add_argument("--top-k", type=int, help="Optional top-K selection instead of thresholding")
    parser.add_argument("--iterations", type=int, default=1000, help="Bootstrap iterations")
    parser.add_argument("--seed", type=int, default=2025, help="Bootstrap RNG seed")
    parser.add_argument("--report", required=True, help="Output JSON with base metrics and CIs")
    parser.add_argument("--metrics", nargs="*", default=["macro_f1", "micro_f1", "example_f1", "openness_mae"], help="Metrics to compute")
    return parser.parse_args(argv)


def load_ground_truth(path: Path) -> Dict[str, Dict]:
    records: Dict[str, Dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            records[sample_id] = payload
    if not records:
        raise ValueError(f"No ground-truth samples found in {path}")
    return records


def load_predictions(path: Path) -> Dict[str, Dict]:
    records: Dict[str, Dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            records[sample_id] = payload
    if not records:
        raise ValueError(f"No prediction entries found in {path}")
    return records


def build_sample_records(
    ground: Dict[str, Dict],
    preds: Dict[str, Dict],
    threshold: float,
    top_k: Optional[int],
) -> List[SampleRecord]:
    samples: List[SampleRecord] = []
    missing = []
    for sample_id, payload in ground.items():
        if sample_id not in preds:
            missing.append(sample_id)
            continue
        pred_payload = preds[sample_id]

        true_labels = set(payload.get("labels") or payload.get("components") or [])

        if "scores" in pred_payload:
            scores_dict = pred_payload["scores"]
            scored_labels = sorted(scores_dict.items(), key=lambda item: item[1], reverse=True)
            if top_k is not None:
                pred_labels = {label for label, _ in scored_labels[:top_k]}
            else:
                pred_labels = {label for label, score in scored_labels if score >= threshold}
        elif "labels" in pred_payload:
            pred_labels = set(pred_payload["labels"])
        else:
            pred_labels = set()

        pred_labels = {label for label in pred_labels if label}

        record = SampleRecord(
            sample_id=sample_id,
            labels=true_labels,
            pred_labels=pred_labels,
            openness_true=payload.get("openness"),
            openness_pred=pred_payload.get("openness_pred"),
            velocity_true=payload.get("velocity"),
            velocity_pred=pred_payload.get("velocity_pred"),
        )
        samples.append(record)

    if missing:
        raise ValueError(f"Missing predictions for sample_ids: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    if not samples:
        raise ValueError("No aligned samples built")
    return samples


def macro_micro_f1(samples: Iterable[SampleRecord]) -> Dict[str, float]:
    classes: Set[str] = set()
    for sample in samples:
        classes.update(sample.labels)
        classes.update(sample.pred_labels)

    tp = {label: 0.0 for label in classes}
    fp = {label: 0.0 for label in classes}
    fn = {label: 0.0 for label in classes}

    for sample in samples:
        for label in classes:
            in_true = label in sample.labels
            in_pred = label in sample.pred_labels
            if in_true and in_pred:
                tp[label] += 1.0
            elif in_true and not in_pred:
                fn[label] += 1.0
            elif not in_true and in_pred:
                fp[label] += 1.0

    per_class_f1 = []
    macro_precision = []
    macro_recall = []
    total_tp = 0.0
    total_fp = 0.0
    total_fn = 0.0

    for label in classes:
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) > 0 else 0.0
        recall = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) > 0 else 0.0
        macro_precision.append(precision)
        macro_recall.append(recall)
        if (precision + recall) > 0:
            per_class_f1.append((2 * precision * recall) / (precision + recall))
        else:
            per_class_f1.append(0.0)
        total_tp += tp[label]
        total_fp += fp[label]
        total_fn += fn[label]

    macro_precision_score = sum(macro_precision) / len(classes) if classes else 0.0
    macro_recall_score = sum(macro_recall) / len(classes) if classes else 0.0
    macro_f1_score = sum(per_class_f1) / len(classes) if classes else 0.0

    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (
        (2 * micro_precision * micro_recall) / (micro_precision + micro_recall)
        if (micro_precision + micro_recall) > 0
        else 0.0
    )

    return {
        "macro_precision": macro_precision_score,
        "macro_recall": macro_recall_score,
        "macro_f1": macro_f1_score,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
    }


def example_f1(samples: Iterable[SampleRecord]) -> float:
    scores = []
    for sample in samples:
        labels = sample.labels
        preds = sample.pred_labels
        if not labels and not preds:
            scores.append(1.0)
            continue
        intersection = len(labels & preds)
        precision = intersection / len(preds) if preds else 0.0
        recall = intersection / len(labels) if labels else 0.0
        if (precision + recall) > 0:
            f1 = (2 * precision * recall) / (precision + recall)
        else:
            f1 = 0.0
        scores.append(f1)
    return float(sum(scores) / len(scores)) if scores else 0.0


def regression_mae(samples: Iterable[SampleRecord], attr_true: str, attr_pred: str) -> Optional[float]:
    errors = []
    for sample in samples:
        y_true = getattr(sample, attr_true)
        y_pred = getattr(sample, attr_pred)
        if y_true is None or y_pred is None:
            continue
        errors.append(abs(float(y_true) - float(y_pred)))
    if not errors:
        return None
    return float(sum(errors) / len(errors))


def compute_metrics(samples: List[SampleRecord], selected: Sequence[str]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    f1_stats = macro_micro_f1(samples)
    if "macro_f1" in selected:
        result["macro_f1"] = f1_stats["macro_f1"]
    if "micro_f1" in selected:
        result["micro_f1"] = f1_stats["micro_f1"]
    if "macro_precision" in selected:
        result["macro_precision"] = f1_stats["macro_precision"]
    if "macro_recall" in selected:
        result["macro_recall"] = f1_stats["macro_recall"]
    if "micro_precision" in selected:
        result["micro_precision"] = f1_stats["micro_precision"]
    if "micro_recall" in selected:
        result["micro_recall"] = f1_stats["micro_recall"]

    if "example_f1" in selected:
        result["example_f1"] = example_f1(samples)

    if "openness_mae" in selected:
        mae = regression_mae(samples, "openness_true", "openness_pred")
        if mae is not None:
            result["openness_mae"] = mae

    if "velocity_mae" in selected:
        mae = regression_mae(samples, "velocity_true", "velocity_pred")
        if mae is not None:
            result["velocity_mae"] = mae

    return result


def bootstrap_metrics(
    samples: List[SampleRecord],
    metrics: Sequence[str],
    iterations: int,
    rng: random.Random,
) -> Dict[str, Dict[str, float]]:
    n = len(samples)
    if n == 0:
        raise ValueError("No samples provided for bootstrap")

    base_metrics = compute_metrics(samples, metrics)
    collected: Dict[str, List[float]] = {name: [] for name in base_metrics.keys()}

    for _ in range(iterations):
        indices = [rng.randrange(n) for _ in range(n)]
        resample = [samples[idx] for idx in indices]
        metric_values = compute_metrics(resample, base_metrics.keys())
        for name, value in metric_values.items():
            collected[name].append(value)

    summary: Dict[str, Dict[str, float]] = {}
    for name, values in collected.items():
        arr = sorted(values)
        lower_idx = int(0.025 * len(arr))
        upper_idx = int(0.975 * len(arr)) - 1
        lower = arr[max(0, lower_idx)]
        upper = arr[min(len(arr) - 1, max(upper_idx, 0))]
        summary[name] = {
            "point_estimate": base_metrics[name],
            "mean": float(sum(values) / len(values)) if values else base_metrics[name],
            "ci_lower": float(lower),
            "ci_upper": float(upper),
        }
    return summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        ground = load_ground_truth(Path(args.ground_truth))
        preds = load_predictions(Path(args.predictions))
        samples = build_sample_records(ground, preds, args.threshold, args.top_k)
    except Exception as exc:
        print(f"[bootstrap_eval] Input error: {exc}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)

    try:
        summary = bootstrap_metrics(samples, args.metrics, args.iterations, rng)
    except Exception as exc:
        print(f"[bootstrap_eval] Bootstrap failed: {exc}", file=sys.stderr)
        return 3

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(f"Bootstrap report written to {report_path}")
    for name, values in summary.items():
        print(
            f"  {name}: point={values['point_estimate']:.4f} ci95=[{values['ci_lower']:.4f}, {values['ci_upper']:.4f}]"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
