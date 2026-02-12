#!/usr/bin/env python3
"""
Generate optimal per-class thresholds for a multilabel model.

Runs the model on the validation set and finds the threshold per class
that maximizes F1. Saves the result to thresholds.json in the model
directory (overwriting any existing one).

Usage:
    cd ai-pipeline
    PYTHONPATH=. python scripts/generate_thresholds.py \
        --model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
        --dataset F:/datasets/multilabel_real_v3

    # Or specify manifests explicitly:
    PYTHONPATH=. python scripts/generate_thresholds.py \
        --model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
        --manifests F:/datasets/multilabel_real_v3/enst_drums/enst_drums_manifest.json \
                    F:/datasets/multilabel_real_v3/acoustic_synth/acoustic_synth_manifest.json

    # Cap samples for speed:
    PYTHONPATH=. python scripts/generate_thresholds.py \
        --model runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt \
        --dataset F:/datasets/multilabel_real_v3 \
        --max-samples 50000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import ConcatDataset, DataLoader

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.multilabel.dataset import (
    BatchedMultiLabelDataset,
    DEFAULT_DRUM_COMPONENTS,
)

CLASS_NAMES = DEFAULT_DRUM_COMPONENTS


# ── Model loading (reuses inference loader) ────────────────────────────

def load_model(model_path: Path, device: torch.device, num_classes: int = 12):
    from transcription.multilabel_inference import load_model_checkpoint

    model = load_model_checkpoint(
        str(model_path),
        device=str(device),
        num_classes=num_classes,
    )
    model.eval()
    return model


# ── Dataset loading ────────────────────────────────────────────────────

def discover_manifests(dataset_root: Path) -> List[Path]:
    """Find all *_manifest.json files under the dataset root."""
    manifests = sorted(dataset_root.rglob("*_manifest.json"))
    return manifests


def load_val_dataset(
    manifests: List[Path],
) -> ConcatDataset:
    """Build a ConcatDataset from val splits of the given manifests."""
    datasets = []

    for manifest_path in manifests:
        try:
            ds = BatchedMultiLabelDataset(
                manifest_path=str(manifest_path),
                is_train=False,
                shuffle_before_split=True,
            )
        except Exception as e:
            print(f"  [SKIP] {manifest_path.name}: {e}")
            continue

        if len(ds) == 0:
            print(f"  [SKIP] {manifest_path.name}: 0 val samples")
            continue

        print(f"  [OK]   {manifest_path.name}: {len(ds):,} val samples")
        datasets.append(ds)

    if not datasets:
        raise RuntimeError("No validation data found!")

    return ConcatDataset(datasets)


# ── Threshold optimisation ─────────────────────────────────────────────

def collect_predictions(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    max_samples: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Run model on data and return (probs, labels)."""
    all_probs, all_labels = [], []
    n = 0

    for features, labels in loader:
        x = features.to(device)
        with torch.inference_mode():
            logits = model(x)
            probs = torch.sigmoid(logits)

        all_probs.append(probs.cpu().numpy())
        all_labels.append(labels.numpy())

        n += len(features)
        print(f"\r   Predicted {n:,} samples...", end="", flush=True)

        if max_samples and n >= max_samples:
            break

    print()
    return np.concatenate(all_probs), np.concatenate(all_labels)


def find_optimal_thresholds(
    probs: np.ndarray,
    labels: np.ndarray,
    class_names: List[str],
    num_thresholds: int = 81,
) -> Tuple[Dict[str, dict], float, dict]:
    """
    Sweep thresholds per class and globally.

    Returns:
        (per_class_results, global_threshold, global_metrics)
    """
    thresholds = np.linspace(0.1, 0.9, num_thresholds)
    num_classes = probs.shape[1]

    per_class: Dict[str, dict] = {}

    print()
    print(f"{'Class':<15} {'Thresh':>8} {'Prec':>8} {'Recall':>8} {'F1':>8} {'Support':>10}")
    print("-" * 62)

    for c in range(num_classes):
        cp = probs[:, c]
        cl = labels[:, c]
        support = int(cl.sum())

        if support == 0:
            per_class[class_names[c]] = {
                "threshold": 0.5, "f1": 0.0, "precision": 0.0, "recall": 0.0,
                "tp": 0, "fp": 0, "fn": 0, "tn": len(cl), "support": 0,
            }
            print(f"{class_names[c]:<15} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8} {0:>10,}")
            continue

        best = {"f1": 0, "t": 0.5, "p": 0, "r": 0, "tp": 0, "fp": 0, "fn": 0}

        for t in thresholds:
            pred = (cp >= t).astype(np.int32)
            tp = int(np.sum((pred == 1) & (cl == 1)))
            fp = int(np.sum((pred == 1) & (cl == 0)))
            fn = int(np.sum((pred == 0) & (cl == 1)))
            p = tp / (tp + fp) if (tp + fp) else 0.0
            r = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * p * r / (p + r) if (p + r) else 0.0
            if f1 > best["f1"]:
                best = {"f1": f1, "t": t, "p": p, "r": r, "tp": tp, "fp": fp, "fn": fn}

        tn = int(len(cl) - best["tp"] - best["fp"] - best["fn"])
        per_class[class_names[c]] = {
            "threshold": round(best["t"], 4),
            "f1": round(best["f1"], 4),
            "precision": round(best["p"], 4),
            "recall": round(best["r"], 4),
            "tp": best["tp"], "fp": best["fp"], "fn": best["fn"], "tn": tn,
            "support": support,
        }
        print(f"{class_names[c]:<15} {best['t']:>8.3f} {best['p']:>8.3f} {best['r']:>8.3f} {best['f1']:>8.3f} {support:>10,}")

    print("-" * 62)

    # Global threshold (micro F1)
    best_g_f1 = 0
    best_g_t = 0.5

    for t in thresholds:
        pred = (probs >= t).astype(np.int32)
        tp = np.sum((pred == 1) & (labels == 1))
        fp = np.sum((pred == 1) & (labels == 0))
        fn = np.sum((pred == 0) & (labels == 1))
        p = tp / (tp + fp) if (tp + fp) else 0
        r = tp / (tp + fn) if (tp + fn) else 0
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        if f1 > best_g_f1:
            best_g_f1 = f1
            best_g_t = t

    global_metrics = {
        "threshold": round(best_g_t, 4),
        "micro_f1": round(best_g_f1, 4),
    }
    print(f"\nGlobal optimal threshold: {best_g_t:.3f}  (micro-F1: {best_g_f1:.4f})")

    return per_class, best_g_t, global_metrics


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate optimal per-class thresholds for a multilabel drum model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--model", type=Path, required=True,
        help="Path to model checkpoint (.pt)",
    )
    parser.add_argument(
        "--dataset", type=Path, default=None,
        help="Root of dataset (auto-discovers manifests under val/)",
    )
    parser.add_argument(
        "--manifests", type=Path, nargs="+", default=None,
        help="Explicit manifest paths to use",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path (default: <model_dir>/thresholds.json)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Cap number of val samples (for speed). Default: use all.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=256,
        help="Batch size for inference",
    )
    parser.add_argument(
        "--device", default=None,
        help="Device (default: cuda if available)",
    )
    args = parser.parse_args()

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))

    print("=" * 62)
    print("  GENERATE THRESHOLDS")
    print("=" * 62)
    print(f"  Model:  {args.model}")
    print(f"  Device: {device}")

    # Resolve manifests
    if args.manifests:
        manifests = args.manifests
    elif args.dataset:
        manifests = discover_manifests(args.dataset)
    else:
        parser.error("Provide either --dataset or --manifests")

    print(f"  Manifests: {len(manifests)} found")
    print()

    # Load val data
    print("[1/3] Loading validation data...")
    val_ds = load_val_dataset(manifests)
    total = len(val_ds)
    print(f"  Total val samples: {total:,}")
    if args.max_samples:
        print(f"  Capping to {args.max_samples:,}")

    loader = DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False,
        num_workers=4, pin_memory=True, persistent_workers=True,
    )

    # Load model
    print("\n[2/3] Loading model...")
    model = load_model(args.model, device)
    print("  Model loaded.")

    # Predict & optimise
    print("\n[3/3] Running inference on validation set...")
    t0 = time.time()
    probs, labels = collect_predictions(model, loader, device, max_samples=args.max_samples)
    elapsed = time.time() - t0
    print(f"  Inference done in {elapsed:.1f}s ({len(probs):,} samples)")

    per_class, global_thresh, global_metrics = find_optimal_thresholds(
        probs, labels, CLASS_NAMES,
    )

    # Build output
    output_path = args.output or (args.model.parent / "thresholds.json")

    result = {
        "model_path": str(args.model.resolve()),
        "manifests": [str(m) for m in manifests],
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(probs),
        "num_classes": len(CLASS_NAMES),
        "class_names": CLASS_NAMES,
        "global_threshold": global_thresh,
        "per_class_thresholds": {
            name: info["threshold"] for name, info in per_class.items()
        },
        "per_class_metrics": per_class,
        "baseline_metrics": {
            "threshold": 0.5,
            **_compute_micro_macro(probs, labels, 0.5),
        },
        "tuned_metrics": {
            **_compute_micro_macro(probs, labels, global_thresh, per_class),
        },
    }

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nThresholds saved to: {output_path}")
    print("=" * 62)
    print("Done. You can now use this file with --multilabel-thresholds")
    print("=" * 62)


def _compute_micro_macro(
    probs: np.ndarray,
    labels: np.ndarray,
    global_thresh: float,
    per_class: Optional[Dict] = None,
) -> dict:
    """Compute micro/macro F1 with either global or per-class thresholds."""
    num_classes = probs.shape[1]

    # Per-class thresholds
    if per_class:
        thresh_vec = np.array([
            per_class[CLASS_NAMES[c]]["threshold"]
            if CLASS_NAMES[c] in per_class else global_thresh
            for c in range(num_classes)
        ])
    else:
        thresh_vec = np.full(num_classes, global_thresh)

    pred = (probs >= thresh_vec).astype(np.int32)

    # Micro
    tp = np.sum((pred == 1) & (labels == 1))
    fp = np.sum((pred == 1) & (labels == 0))
    fn = np.sum((pred == 0) & (labels == 1))
    micro_p = tp / (tp + fp) if (tp + fp) else 0
    micro_r = tp / (tp + fn) if (tp + fn) else 0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0

    # Macro
    f1s = []
    for c in range(num_classes):
        tp_c = np.sum((pred[:, c] == 1) & (labels[:, c] == 1))
        fp_c = np.sum((pred[:, c] == 1) & (labels[:, c] == 0))
        fn_c = np.sum((pred[:, c] == 0) & (labels[:, c] == 1))
        p = tp_c / (tp_c + fp_c) if (tp_c + fp_c) else 0
        r = tp_c / (tp_c + fn_c) if (tp_c + fn_c) else 0
        f = 2 * p * r / (p + r) if (p + r) else 0
        f1s.append(f)

    return {
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(np.mean(f1s), 4),
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
    }


if __name__ == "__main__":
    main()
