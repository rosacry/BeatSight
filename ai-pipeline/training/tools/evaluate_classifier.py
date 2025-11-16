"""Evaluate trained drum classifier checkpoints and emit QA artifacts."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from torch.amp import autocast
from sklearn.metrics import classification_report, confusion_matrix
from torch.utils.data import DataLoader, Subset

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.common_paths import dataset_root as default_dataset_root
from training.common_paths import feature_cache_root as default_feature_cache_root
from training.train_classifier import (  # noqa: E402
    DrumSampleDataset,
    stratified_sample_indices,
)
from transcription.ml_drum_classifier import DrumClassifierCNN  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a drum classifier checkpoint")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_dataset_root(),
        help=(
            "Path to dataset root (train/val). Defaults to BEATSIGHT_DATASET_DIR or "
            "BEATSIGHT_DATA_ROOT/prod_combined_profile_run"
        ),
    )
    parser.add_argument("--split", choices=["train", "val"], default="val", help="Dataset split to evaluate")
    parser.add_argument("--checkpoint", required=True, type=Path, help="Model checkpoint (.pth)")
    parser.add_argument("--batch-size", type=int, default=128, help="Evaluation batch size")
    parser.add_argument("--device", default=None, help="Device to run evaluation on")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--prefetch-factor", type=int, default=2, help="Prefetch factor for DataLoader workers")
    parser.add_argument("--pin-memory", action="store_true", help="Pin DataLoader memory (recommended on CUDA)")
    parser.add_argument(
        "--feature-cache-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing cached features. Defaults to "
            "BEATSIGHT_CACHE_DIR or BEATSIGHT_DATA_ROOT/feature_cache/prod_combined_warmup"
        ),
    )
    parser.add_argument("--fraction", type=float, default=1.0, help="Evaluate on a stratified subset of this fraction")
    parser.add_argument("--subset-seed", type=int, default=42, help="RNG seed for subset selection")
    parser.add_argument("--output-json", type=Path, required=True, help="Where to write evaluation summary JSON")
    parser.add_argument(
        "--misclassified-report",
        type=Path,
        help="Optional path to write a JSON list of misclassified examples",
    )
    parser.add_argument(
        "--max-misclassified",
        type=int,
        default=200,
        help="Maximum number of misclassified samples to record",
    )
    parser.add_argument(
        "--confusion-matrix",
        type=Path,
        help="Optional path to store the confusion matrix as .npy",
    )
    parser.add_argument(
        "--components",
        type=Path,
        default=None,
        help="Optional path to components.json when not found inside dataset root",
    )
    parser.add_argument(
        "--amp",
        action="store_true",
        help="Use autocast mixed precision during evaluation",
    )
    parser.add_argument(
        "--amp-dtype",
        choices=["float16", "bfloat16"],
        default="float16",
        help="Autocast dtype when --amp is enabled",
    )
    parser.add_argument("--progress", action="store_true", help="Display progress bar")
    args = parser.parse_args()
    args.dataset = Path(args.dataset).expanduser().resolve()
    if args.feature_cache_dir is None:
        args.feature_cache_dir = default_feature_cache_root()
    else:
        args.feature_cache_dir = Path(args.feature_cache_dir).expanduser().resolve()
    return args


def load_components(dataset_root: Path, explicit_path: Optional[Path]) -> Tuple[List[str], Dict[int, str]]:
    candidate_paths = []
    if explicit_path:
        candidate_paths.append(explicit_path)
    candidate_paths.append(dataset_root / "components.json")

    components_data: Optional[Dict[str, Any]] = None
    for path in candidate_paths:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                components_data = json.load(handle)
            break
    if not components_data:
        raise FileNotFoundError("Could not locate components.json for class names")

    components = components_data.get("components")
    if not components:
        raise ValueError("components.json missing 'components' list")
    index_map = components_data.get("component_index") or {
        name: idx for idx, name in enumerate(components)
    }
    inverse_index = {int(idx): name for name, idx in index_map.items()}
    ordered_names = [inverse_index[i] for i in range(len(components))]
    return ordered_names, inverse_index


def resolve_labels(dataset_root: Path, split: str, filename: str) -> Path:
    direct = dataset_root / filename
    if direct.exists():
        return direct
    nested = dataset_root / split / filename
    if nested.exists():
        return nested
    raise FileNotFoundError(f"Could not find labels file '{filename}' for split '{split}'")


def load_dataset_metadata(dataset_root: Path) -> Dict[str, Any]:
    metadata_path = dataset_root / "metadata.json"
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def build_dataset(args: argparse.Namespace, components: Sequence[str]) -> Tuple[torch.utils.data.Dataset, List[int], DrumSampleDataset]:
    dataset_root = args.dataset
    cache_root = None
    if args.feature_cache_dir:
        cache_root = args.feature_cache_dir / args.split
        cache_root.mkdir(parents=True, exist_ok=True)

    metadata = load_dataset_metadata(dataset_root)
    sample_rate = int(metadata.get("sample_rate", 44100))

    base_dataset = DrumSampleDataset(
        dataset_root / args.split,
        resolve_labels(dataset_root, args.split, f"{args.split}_labels.json"),
        sr=sample_rate,
        cache_dir=cache_root,
        prefer_torchaudio=True,
    )

    indices: Optional[List[int]] = None
    if args.fraction < 1.0:
        if args.fraction <= 0.0:
            raise ValueError("--fraction must be > 0 when provided")
        indices = stratified_sample_indices(base_dataset.labels, args.fraction, args.subset_seed)
        dataset = Subset(base_dataset, indices)
    else:
        dataset = base_dataset
        indices = list(range(len(base_dataset)))
    return dataset, indices, base_dataset


def collate_metadata(indices: List[int], base_dataset: DrumSampleDataset) -> List[Dict[str, Any]]:
    return [base_dataset.labels[i] for i in indices]


def load_model(checkpoint_path: Path, num_classes: int, device: torch.device) -> torch.nn.Module:
    model = DrumClassifierCNN(num_classes=num_classes)
    checkpoint = torch.load(checkpoint_path, map_location=device)
    state_dict: Optional[Dict[str, torch.Tensor]] = None

    if isinstance(checkpoint, dict):
        if "model_state" in checkpoint:
            state_dict = checkpoint["model_state"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        elif all(isinstance(v, torch.Tensor) for v in checkpoint.values()):
            state_dict = checkpoint  # plain state dict persisted with torch.save(model.state_dict())
    if state_dict is None:
        raise ValueError(f"Unrecognised checkpoint format at {checkpoint_path}")

    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    return model


def evaluate(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    *,
    use_amp: bool,
    autocast_dtype: torch.dtype,
    collect_progress: bool,
) -> Tuple[List[int], List[int], List[torch.Tensor]]:
    predictions: List[int] = []
    targets: List[int] = []
    logits: List[torch.Tensor] = []

    iterator: Iterable = dataloader
    if collect_progress:
        from tqdm import tqdm

        iterator = tqdm(dataloader, desc="Evaluating")

    with torch.no_grad():
        for features, labels in iterator:
            features = features.to(device, non_blocking=device.type == "cuda")
            labels = labels.to(device, non_blocking=device.type == "cuda")
            with autocast(device_type=device.type, enabled=use_amp, dtype=autocast_dtype):
                output = model(features)
            predictions.extend(output.argmax(dim=1).cpu().tolist())
            targets.extend(labels.cpu().tolist())
            logits.append(output.detach().cpu())
    return predictions, targets, logits


def compute_metrics(
    predictions: List[int],
    targets: List[int],
    class_names: Sequence[str],
) -> Dict[str, Any]:
    cm = confusion_matrix(targets, predictions, labels=list(range(len(class_names))))
    report = classification_report(
        targets,
        predictions,
        labels=list(range(len(class_names))),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    per_class_accuracy = {
        class_names[i]: float(cm[i, i]) / max(cm[i].sum(), 1)
        for i in range(len(class_names))
    }
    return {
        "confusion_matrix": cm.tolist(),
        "classification_report": report,
        "per_class_accuracy": per_class_accuracy,
    }


def top_misclassified(
    predictions: List[int],
    targets: List[int],
    logits: List[torch.Tensor],
    metadata: Sequence[Dict[str, Any]],
    *,
    class_names: Sequence[str],
    limit: int,
) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []

    flat_logits = torch.cat(logits, dim=0)
    confidences = F.softmax(flat_logits, dim=1)

    misclassified: List[Tuple[float, Dict[str, Any]]] = []
    for idx, (pred, target) in enumerate(zip(predictions, targets)):
        if pred == target:
            continue
        info = metadata[idx]
        file_path = info.get("file")
        instrument = info.get("component") or info.get("component_label")
        entry = {
            "index": idx,
            "file": file_path,
            "true_label": class_names[target] if target < len(class_names) else target,
            "predicted_label": class_names[pred] if pred < len(class_names) else pred,
            "true_index": int(target),
            "predicted_index": int(pred),
            "confidence": float(confidences[idx, pred].item()),
            "top3": [
                {
                    "label": class_names[class_idx],
                    "index": int(class_idx),
                    "probability": float(confidences[idx, class_idx].item()),
                }
                for class_idx in torch.topk(confidences[idx], k=min(3, confidences.size(1)))[1].tolist()
            ],
        }
        if instrument is not None:
            entry["instrument"] = instrument
        misclassified.append((entry["confidence"], entry))

    misclassified.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in misclassified[:limit]]


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive")
    if args.fraction <= 0 or math.isinf(args.fraction) or math.isnan(args.fraction):
        raise SystemExit("--fraction must be a finite positive value")

    dataset_root = args.dataset
    class_names, inverse_index = load_components(dataset_root, args.components)
    dataset, subset_indices, base_dataset = build_dataset(args, class_names)

    device_name = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_name)

    model = load_model(args.checkpoint, num_classes=len(class_names), device=device)

    pin_memory = args.pin_memory or device.type == "cuda"
    loader_kwargs = {
        "dataset": dataset,
        "batch_size": args.batch_size,
        "shuffle": False,
        "num_workers": max(args.num_workers, 0),
        "pin_memory": pin_memory,
        "drop_last": False,
    }
    if args.num_workers > 0 and args.prefetch_factor:
        loader_kwargs["prefetch_factor"] = args.prefetch_factor
    if args.num_workers > 0:
        loader_kwargs["persistent_workers"] = True
    dataloader = DataLoader(**loader_kwargs)

    use_amp = bool(args.amp and device.type == "cuda")
    autocast_dtype = torch.bfloat16 if args.amp_dtype == "bfloat16" else torch.float16
    if use_amp and autocast_dtype == torch.bfloat16:
        if not getattr(torch.cuda, "is_bf16_supported", lambda: False)():
            print("Warning: GPU does not support bfloat16; falling back to float16")
            autocast_dtype = torch.float16

    predictions, targets, logits = evaluate(
        model,
        dataloader,
        device,
        use_amp=use_amp,
        autocast_dtype=autocast_dtype,
        collect_progress=args.progress,
    )

    metrics = compute_metrics(predictions, targets, class_names)
    correct = sum(int(p == t) for p, t in zip(predictions, targets))
    accuracy = correct / max(len(targets), 1)
    summary = {
        "dataset_root": str(dataset_root),
        "split": args.split,
        "checkpoint": str(args.checkpoint),
        "num_samples": len(targets),
        "accuracy": float(accuracy),
        "top1_accuracy": float(accuracy),
        "class_coverage": {class_names[idx]: count for idx, count in Counter(targets).items()},
    }
    summary.update(metrics)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    if args.confusion_matrix:
        args.confusion_matrix.parent.mkdir(parents=True, exist_ok=True)
        np.save(args.confusion_matrix, np.array(metrics["confusion_matrix"], dtype=np.int64))

    metadata = collate_metadata(subset_indices, base_dataset)
    if args.misclassified_report:
        args.misclassified_report.parent.mkdir(parents=True, exist_ok=True)
        errors = top_misclassified(
            predictions,
            targets,
            logits,
            metadata,
            class_names=class_names,
            limit=args.max_misclassified,
        )
        with args.misclassified_report.open("w", encoding="utf-8") as handle:
            json.dump(errors, handle, indent=2)

    print(f"Evaluated {len(targets)} samples. Accuracy: {summary['top1_accuracy']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
