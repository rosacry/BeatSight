"""Open-set evaluation metrics for BeatSight drum models.

Computes AUROC, AUPRC, and FPR@95%TPR for distinguishing known vs unknown
samples based on prediction confidences. Supports either explicit rejection
scores or implicit max-probability confidence extracted from per-class
probabilities.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open-set evaluation")
    parser.add_argument("--ground-truth", required=True, help="JSONL with sample_id and is_known flag")
    parser.add_argument("--predictions", required=True, help="JSONL with scores/probabilities per sample")
    parser.add_argument(
        "--confidence-field",
        default="scores",
        help="Field containing per-class confidences (default: scores)",
    )
    parser.add_argument(
        "--rejection-field",
        help="Optional field providing explicit unknown score (higher => more unknown)",
    )
    parser.add_argument(
        "--report",
        help="Path to write metrics JSON (AUROC, AUPRC, FPR@95%TPR)",
    )
    parser.add_argument("--strict", action="store_true", help="Exit with 1 if AUROC < 0.90")
    parser.add_argument("--auroc-gate", type=float, default=0.90, help="Minimum AUROC threshold")
    parser.add_argument(
        "--fpr95-gate",
        type=float,
        default=0.10,
        help="Maximum allowable FPR at 95% TPR",
    )
    return parser.parse_args(argv)


def load_ground_truth(path: Path) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            is_known = bool(payload.get("is_known", not payload.get("is_unknown", False)))
            mapping[sample_id] = 1 if is_known else 0
    if not mapping:
        raise ValueError(f"No entries found in {path}")
    return mapping


def load_predictions(
    path: Path,
    confidence_field: str,
    rejection_field: Optional[str],
) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            sample_id = payload["sample_id"]
            if rejection_field and rejection_field in payload:
                rejection_score = float(payload[rejection_field])
                scores[sample_id] = -rejection_score  # higher implies more likely known
                continue

            if confidence_field not in payload:
                raise ValueError(f"Entry {sample_id} missing field '{confidence_field}'")

            confidences = payload[confidence_field]
            if isinstance(confidences, dict):
                max_conf = max((float(v) for v in confidences.values()), default=0.0)
            elif isinstance(confidences, list):
                max_conf = max((float(v) for v in confidences), default=0.0)
            else:
                max_conf = float(confidences)
            scores[sample_id] = max_conf
    if not scores:
        raise ValueError(f"No predictions found in {path}")
    return scores


def align_scores(ground: Dict[str, int], scores: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
    y_true: List[int] = []
    y_score: List[float] = []
    missing = []
    for sample_id, label in ground.items():
        if sample_id not in scores:
            missing.append(sample_id)
            continue
        y_true.append(label)
        y_score.append(scores[sample_id])
    if missing:
        raise ValueError(f"Predictions missing for sample_ids: {missing[:5]}{'...' if len(missing) > 5 else ''}")
    return np.asarray(y_true, dtype=np.int8), np.asarray(y_score, dtype=np.float32)


def compute_roc_curve(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(-y_score)
    y_score = y_score[order]
    y_true = y_true[order]
    distinct = np.where(np.diff(y_score))[0]
    threshold_idxs = np.r_[distinct, y_true.size - 1]

    tps = np.cumsum(y_true)[threshold_idxs]
    fps = 1 + threshold_idxs - tps

    tps = np.r_[0, tps]
    fps = np.r_[0, fps]

    fn_total = y_true.sum()
    tn_total = y_true.size - fn_total

    tpr = tps / fn_total if fn_total > 0 else np.zeros_like(tps, dtype=float)
    fpr = fps / tn_total if tn_total > 0 else np.zeros_like(fps, dtype=float)
    thresholds = np.r_[np.inf, y_score[threshold_idxs]]
    return fpr, tpr, thresholds


def auc(x: np.ndarray, y: np.ndarray) -> float:
    return float(np.trapezoid(y, x))


def compute_pr_curve(y_true: np.ndarray, y_score: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(-y_score)
    y_score = y_score[order]
    y_true = y_true[order]

    tp = np.cumsum(y_true)
    fp = np.cumsum(1 - y_true)
    precision = tp / (tp + fp)
    recall = tp / (tp[-1] if tp.size > 0 else 1)

    precision = np.r_[1.0, precision]
    recall = np.r_[0.0, recall]
    thresholds = np.r_[np.inf, y_score]
    return precision, recall, thresholds


def auc_pr(precision: np.ndarray, recall: np.ndarray) -> float:
    return float(np.trapezoid(precision, recall))


def fpr_at_tpr(fpr: np.ndarray, tpr: np.ndarray, target_tpr: float) -> float:
    indices = np.where(tpr >= target_tpr)[0]
    if indices.size == 0:
        return math.inf
    return float(np.min(fpr[indices]))


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        ground = load_ground_truth(Path(args.ground_truth))
        scores = load_predictions(Path(args.predictions), args.confidence_field, args.rejection_field)
        y_true, y_score = align_scores(ground, scores)
    except Exception as exc:
        print(f"[openset_eval] Input error: {exc}", file=sys.stderr)
        return 2

    fpr_curve, tpr_curve, _ = compute_roc_curve(y_true, y_score)
    auroc = auc(fpr_curve, tpr_curve)

    precision_curve, recall_curve, _ = compute_pr_curve(y_true, y_score)
    auprc = auc_pr(precision_curve, recall_curve)

    fpr95 = fpr_at_tpr(fpr_curve, tpr_curve, 0.95)

    print(f"Open-set AUROC: {auroc:.4f}")
    print(f"Open-set AUPRC: {auprc:.4f}")
    if math.isfinite(fpr95):
        print(f"FPR@95%TPR: {fpr95:.4f}")
    else:
        print("FPR@95%TPR: undefined (TPR never reaches 0.95)")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump({"auroc": auroc, "auprc": auprc, "fpr_at_95_tpr": fpr95}, handle, indent=2)
        print(f"Metrics written to {report_path}")

    exit_code = 0
    if args.strict:
        if auroc < args.auroc_gate or (math.isfinite(fpr95) and fpr95 > args.fpr95_gate):
            print(
                f"[openset_eval] Gate failed: AUROC {auroc:.4f} (gate {args.auroc_gate}) or "
                f"FPR@95 {fpr95:.4f} (gate {args.fpr95_gate})",
                file=sys.stderr,
            )
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
