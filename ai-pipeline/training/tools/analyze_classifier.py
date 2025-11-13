#!/usr/bin/env python3
"""Evaluate a trained drum classifier checkpoint on a dataset split.

Produces summary metrics, a confusion matrix, and a list of misclassified
examples to help with targeted data curation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch
from tqdm import tqdm

from training.train_classifier import DrumSampleDataset  # type: ignore
from transcription.ml_drum_classifier import DrumClassifierCNN


def load_components(dataset_root: Path) -> Dict[str, int]:
    with (dataset_root / "components.json").open("r", encoding="utf-8") as handle:
        components = json.load(handle)
    names = components.get("class_names")
    if isinstance(names, list):
        return {name: idx for idx, name in enumerate(names)}
    num_classes = int(components["num_classes"])
    # Default to CNN ordering when explicit list missing
    return {name: idx for idx, name in enumerate(DrumClassifierCNN.DRUM_COMPONENTS[:num_classes])}


def resolve_labels(dataset_root: Path, split: str) -> Path:
    candidate = dataset_root / split / f"{split}_labels.json"
    if candidate.exists():
        return candidate
    fallback = dataset_root / f"{split}_labels.json"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Could not locate labels for split '{split}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze drum classifier checkpoints")
    parser.add_argument("--dataset", type=Path, required=True, help="Dataset root used for training")
    parser.add_argument("--split", choices=["train", "val", "test"], default="val", help="Dataset split to evaluate")
    parser.add_argument("--model-path", type=Path, required=True, help="Checkpoint (.pth) to evaluate")
    parser.add_argument("--output-dir", type=Path, required=True, help="Where to write analysis artifacts")
    parser.add_argument("--sample-rate", type=int, default=44100)
    parser.add_argument("--n-fft", type=int, default=2048)
    parser.add_argument("--hop-length", type=int, default=512)
    parser.add_argument("--n-mels", type=int, default=128)
    parser.add_argument("--fmax", type=int, default=8000)
    parser.add_argument("--target-frames", type=int, default=128)
    parser.add_argument("--cache-dir", type=Path, help="Optional feature cache to reuse")
    parser.add_argument("--device", default=None, help="Inference device (cuda/cpu)")
    parser.add_argument("--no-torchaudio", action="store_true", help="Force librosa extraction")
    parser.add_argument("--channels-last", action="store_true", help="Use channels-last tensors during eval")
    parser.add_argument("--topk-misclassified", type=int, default=50, help="How many misclassified items to record")

    args = parser.parse_args()

    device_str = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(device_str)
    print(f"Evaluating on device: {device_str}")

    dataset_root = args.dataset.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    fmax = None if args.fmax <= 0 else args.fmax

    dataset = DrumSampleDataset(
        dataset_root / args.split,
        resolve_labels(dataset_root, args.split),
        sr=args.sample_rate,
        cache_dir=(args.cache_dir / args.split) if args.cache_dir else None,
        prefer_torchaudio=not args.no_torchaudio,
        n_fft=args.n_fft,
        hop_length=args.hop_length,
        n_mels=args.n_mels,
        fmax=fmax,
        target_frames=args.target_frames,
    )

    components = load_components(dataset_root)
    idx_to_name = {idx: name for name, idx in components.items()}
    num_classes = len(idx_to_name)

    model = DrumClassifierCNN(num_classes=num_classes)
    checkpoint = torch.load(args.model_path, map_location="cpu")
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    else:
        state_dict = checkpoint
    model.load_state_dict(state_dict)
    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)
    model.to(device)
    model.eval()

    confusion = torch.zeros((num_classes, num_classes), dtype=torch.long)
    total = 0
    correct = 0
    per_class_counts = torch.zeros(num_classes, dtype=torch.long)
    per_class_correct = torch.zeros(num_classes, dtype=torch.long)
    misclassified: List[Dict[str, object]] = []

    with torch.no_grad():
        for idx in tqdm(range(len(dataset)), desc=f"Evaluating {args.split}"):
            features, label = dataset[idx]
            label_tensor = torch.tensor([label])
            features = features.unsqueeze(0)  # add batch
            if args.channels_last:
                features = features.to(memory_format=torch.channels_last)
            features = features.to(device)
            label_tensor = label_tensor.to(device)

            logits = model(features)
            pred = torch.argmax(logits, dim=1)

            total += 1
            per_class_counts[label] += 1
            confusion[label, pred.item()] += 1
            if pred.item() == label:
                correct += 1
                per_class_correct[label] += 1
            else:
                misclassified.append(
                    {
                        "index": int(idx),
                        "file": dataset.labels[idx]["file"],
                        "ground_truth": idx_to_name.get(label, str(label)),
                        "predicted": idx_to_name.get(pred.item(), str(pred.item())),
                        "confidence": torch.softmax(logits, dim=1)[0, pred.item()].item(),
                    }
                )

    misclassified.sort(key=lambda item: item["confidence"], reverse=True)
    topk = misclassified[: max(0, args.topk_misclassified)]

    accuracy = correct / max(total, 1)
    per_class_accuracy = {}
    for class_idx, count in enumerate(per_class_counts):
        name = idx_to_name.get(class_idx, str(class_idx))
        if count == 0:
            per_class_accuracy[name] = None
        else:
            per_class_accuracy[name] = per_class_correct[class_idx].item() / count.item()

    results = {
        "total_samples": total,
        "accuracy": accuracy,
        "per_class_accuracy": per_class_accuracy,
        "confusion_matrix": confusion.tolist(),
        "class_order": [idx_to_name[idx] for idx in range(num_classes)],
        "misclassified_topk": topk,
        "model_path": str(args.model_path),
        "dataset": str(dataset_root),
        "split": args.split,
    }

    summary_path = output_dir / f"analysis_{args.split}.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    conf_csv = output_dir / f"confusion_{args.split}.csv"
    np.savetxt(conf_csv, confusion.cpu().numpy(), fmt="%d", delimiter=",", header=",".join(results["class_order"]), comments="")

    print(f"Analysis complete. Results saved to {summary_path}")


if __name__ == "__main__":
    main()
