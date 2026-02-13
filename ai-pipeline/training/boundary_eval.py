"""Boundary pack evaluation for streaming-window edge cases.

Computes recall/precision on samples that fall near streaming window boundaries,
using the predictions produced by the classifier. The dataset readiness plan
requires boundary recall ≥ 0.95, so this utility reports per-class and macro
metrics plus a pass/fail gate for CI integration.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


@dataclass
class BoundarySample:
    sample_id: str
    labels: Set[str]
    weight: float = 1.0


@dataclass
class BoundaryPred:
    sample_id: str
    scores: Dict[str, float]


@dataclass
class BoundaryMetrics:
    per_class_precision: Dict[str, float]
    per_class_recall: Dict[str, float]
    per_class_f1: Dict[str, float]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    micro_precision: float
    micro_recall: float
    micro_f1: float

    def to_dict(self) -> Dict[str, Dict[str, float]]:
        return {
            "per_class_precision": self.per_class_precision,
            "per_class_recall": self.per_class_recall,
            "per_class_f1": self.per_class_f1,
            "macro": {
                "precision": self.macro_precision,
                "recall": self.macro_recall,
                "f1": self.macro_f1,
            },
            "micro": {
                "precision": self.micro_precision,
                "recall": self.micro_recall,
                "f1": self.micro_f1,
            },
        }


def load_ground_truth(path: Path) -> Dict[str, BoundarySample]:
    samples: Dict[str, BoundarySample] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            labels = set(payload.get("labels") or payload.get("components") or [])
            weight = float(payload.get("weight", 1.0))
            samples[sample_id] = BoundarySample(sample_id=sample_id, labels=labels, weight=weight)
    if not samples:
        raise ValueError(f"No samples found in {path}")
    return samples


def load_predictions(path: Path) -> Dict[str, BoundaryPred]:
    preds: Dict[str, BoundaryPred] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            if "scores" in payload:
                scores = {k: float(v) for k, v in payload["scores"].items()}
            elif "probabilities" in payload:
                scores = {k: float(v) for k, v in payload["probabilities"].items()}
            elif "labels" in payload:
                labels = payload["labels"]
                scores = {label: 1.0 for label in labels}
            else:
                raise ValueError(f"Prediction entry {sample_id} missing scores/probabilities/labels")
            preds[sample_id] = BoundaryPred(sample_id=sample_id, scores=scores)
    if not preds:
        raise ValueError(f"No predictions found in {path}")
    return preds


def binarize_predictions(
    preds: Dict[str, BoundaryPred],
    classes: Iterable[str],
    threshold: float,
    top_k: Optional[int],
) -> Dict[str, Set[str]]:
    active: Dict[str, Set[str]] = {}
    class_set = list(classes)
    for sample_id, pred in preds.items():
        scores = pred.scores
        if top_k is not None:
            sorted_labels = sorted(scores.items(), key=lambda item: item[1], reverse=True)
            chosen = {label for label, _ in sorted_labels[:top_k]}
        else:
            chosen = {label for label, score in scores.items() if score >= threshold}
        # Ensure we only keep known classes
        filtered = {label for label in chosen if label in class_set}
        active[sample_id] = filtered
    return active


def compute_metrics(
    ground: Dict[str, BoundarySample],
    predictions: Dict[str, Set[str]],
) -> BoundaryMetrics:
    classes: Set[str] = set()
    for sample in ground.values():
        classes.update(sample.labels)
    for labels in predictions.values():
        classes.update(labels)

    tp = defaultdict(float)
    fp = defaultdict(float)
    fn = defaultdict(float)

    for sample_id, sample in ground.items():
        pred_labels = predictions.get(sample_id, set())
        w = sample.weight
        for label in classes:
            is_true = label in sample.labels
            is_pred = label in pred_labels
            if is_true and is_pred:
                tp[label] += w
            elif is_true and not is_pred:
                fn[label] += w
            elif not is_true and is_pred:
                fp[label] += w

    per_class_precision: Dict[str, float] = {}
    per_class_recall: Dict[str, float] = {}
    per_class_f1: Dict[str, float] = {}

    for label in sorted(classes):
        precision = tp[label] / (tp[label] + fp[label]) if (tp[label] + fp[label]) > 0 else 0.0
        recall = tp[label] / (tp[label] + fn[label]) if (tp[label] + fn[label]) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        per_class_precision[label] = precision
        per_class_recall[label] = recall
        per_class_f1[label] = f1

    macro_precision = sum(per_class_precision.values()) / len(classes) if classes else 0.0
    macro_recall = sum(per_class_recall.values()) / len(classes) if classes else 0.0
    macro_f1 = sum(per_class_f1.values()) / len(classes) if classes else 0.0

    total_tp = sum(tp.values())
    total_fp = sum(fp.values())
    total_fn = sum(fn.values())
    micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall) > 0
        else 0.0
    )

    return BoundaryMetrics(
        per_class_precision=per_class_precision,
        per_class_recall=per_class_recall,
        per_class_f1=per_class_f1,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        micro_precision=micro_precision,
        micro_recall=micro_recall,
        micro_f1=micro_f1,
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boundary recall evaluation")
    parser.add_argument("--ground-truth", required=True, help="JSONL with boundary pack labels")
    parser.add_argument("--predictions", required=True, help="JSONL with model predictions")
    parser.add_argument("--threshold", type=float, default=0.5, help="Score threshold for positive prediction")
    parser.add_argument("--top-k", type=int, help="Select top-K labels instead of thresholding")
    parser.add_argument("--gate", type=float, default=0.95, help="Required macro recall threshold")
    parser.add_argument("--report", help="Path to write metrics JSON")
    parser.add_argument("--strict", action="store_true", help="Exit with 1 if macro recall < gate")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    gt_path = Path(args.ground_truth)
    pred_path = Path(args.predictions)

    try:
        ground = load_ground_truth(gt_path)
        preds_raw = load_predictions(pred_path)
    except Exception as exc:
        print(f"[boundary_eval] Loading error: {exc}", file=sys.stderr)
        return 2

    classes = set()
    for sample in ground.values():
        classes.update(sample.labels)

    binarized = binarize_predictions(preds_raw, classes, threshold=args.threshold, top_k=args.top_k)
    metrics = compute_metrics(ground, binarized)

    print("Boundary metrics:")
    print(f"  Macro recall: {metrics.macro_recall:.4f}")
    print(f"  Macro precision: {metrics.macro_precision:.4f}")
    print(f"  Macro F1: {metrics.macro_f1:.4f}")
    print(f"  Micro recall: {metrics.micro_recall:.4f}")
    print(f"  Micro precision: {metrics.micro_precision:.4f}")
    print(f"  Micro F1: {metrics.micro_f1:.4f}")

    for label in sorted(metrics.per_class_recall):
        precision = metrics.per_class_precision[label]
        recall = metrics.per_class_recall[label]
        f1 = metrics.per_class_f1[label]
        print(f"    {label}: P={precision:.4f} R={recall:.4f} F1={f1:.4f}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(metrics.to_dict(), handle, indent=2)
        print(f"Metrics written to {report_path}")

    if args.strict and metrics.macro_recall < args.gate:
        print(
            f"[boundary_eval] Macro recall {metrics.macro_recall:.4f} below gate {args.gate:.4f}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
