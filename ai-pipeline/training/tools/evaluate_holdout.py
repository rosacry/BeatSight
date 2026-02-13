#!/usr/bin/env python3
"""
Holdout Test Set Evaluation

Evaluates a trained model on holdout test sources (ENST, MDB-Drums) that were
NEVER used during training or validation. This provides true generalization metrics.

Why this matters:
- Validation accuracy can be optimistic if train/val share the same distribution
- Holdout sources have different recording conditions, microphones, drummers
- This is the true measure of how the model will perform on real-world data

Usage:
    python evaluate_holdout.py --checkpoint path/to/model.pth --output results/

    # With TTA for paid tier simulation
    python evaluate_holdout.py --checkpoint model.pth --tta --tta-augmentations 5

Reference:
    Training data: Groove MIDI, E-GMD, Slakh, IDMT, Cambridge
    Holdout data:  ENST-Drums, MDB-Drums (never seen during training)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import tqdm

# Add training directory to path
SCRIPT_DIR = Path(__file__).parent
TRAINING_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(TRAINING_DIR.parent))

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Metrics from holdout evaluation."""
    accuracy: float
    top3_accuracy: float
    per_class_accuracy: Dict[str, float]
    per_class_f1: Dict[str, float]
    confusion_matrix: np.ndarray
    calibration_error: float
    num_samples: int
    inference_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "top3_accuracy": self.top3_accuracy,
            "per_class_accuracy": self.per_class_accuracy,
            "per_class_f1": self.per_class_f1,
            "calibration_error": self.calibration_error,
            "num_samples": self.num_samples,
            "inference_time_ms": self.inference_time_ms,
        }


def apply_tta_augmentation(features: torch.Tensor, aug_idx: int) -> torch.Tensor:
    """Apply test-time augmentation."""
    if aug_idx == 0:
        # Time shift (roll along time axis)
        shift = torch.randint(-5, 6, (1,)).item()
        return torch.roll(features, shifts=shift, dims=-1)
    elif aug_idx == 1:
        # Frequency masking
        mask_width = torch.randint(1, 8, (1,)).item()
        mask_start = torch.randint(0, features.shape[-2] - mask_width, (1,)).item()
        augmented = features.clone()
        augmented[..., mask_start:mask_start+mask_width, :] = 0
        return augmented
    elif aug_idx == 2:
        # Time masking
        mask_width = torch.randint(1, 8, (1,)).item()
        mask_start = torch.randint(0, features.shape[-1] - mask_width, (1,)).item()
        augmented = features.clone()
        augmented[..., mask_start:mask_start+mask_width] = 0
        return augmented
    elif aug_idx == 3:
        # Amplitude scaling
        scale = 0.8 + torch.rand(1).item() * 0.4  # 0.8 to 1.2
        return features * scale
    else:
        # Horizontal flip (time reversal)
        return torch.flip(features, dims=[-1])


def compute_calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Compute Expected Calibration Error (ECE)."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    
    confidences = probs.max(axis=1)
    predictions = probs.argmax(axis=1)
    accuracies = (predictions == labels).astype(float)
    
    for i in range(n_bins):
        in_bin = (confidences > bin_boundaries[i]) & (confidences <= bin_boundaries[i + 1])
        prop_in_bin = in_bin.mean()
        
        if prop_in_bin > 0:
            avg_confidence = confidences[in_bin].mean()
            avg_accuracy = accuracies[in_bin].mean()
            ece += np.abs(avg_accuracy - avg_confidence) * prop_in_bin
    
    return float(ece)


def compute_per_class_metrics(
    preds: np.ndarray,
    labels: np.ndarray,
    num_classes: int,
    class_names: Optional[List[str]] = None,
) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Compute per-class accuracy and F1."""
    per_class_acc = {}
    per_class_f1 = {}
    
    for c in range(num_classes):
        class_name = class_names[c] if class_names else str(c)
        
        # Per-class accuracy
        class_mask = labels == c
        if class_mask.sum() > 0:
            class_correct = (preds[class_mask] == c).sum()
            per_class_acc[class_name] = float(class_correct / class_mask.sum())
        else:
            per_class_acc[class_name] = 0.0
        
        # F1 score
        tp = ((preds == c) & (labels == c)).sum()
        fp = ((preds == c) & (labels != c)).sum()
        fn = ((preds != c) & (labels == c)).sum()
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        per_class_f1[class_name] = float(f1)
    
    return per_class_acc, per_class_f1


def evaluate_model(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    num_classes: int,
    class_names: Optional[List[str]] = None,
    use_tta: bool = False,
    tta_augmentations: int = 5,
    amp_dtype: torch.dtype = torch.float16,
) -> EvaluationMetrics:
    """
    Evaluate model on holdout test set.
    
    Args:
        model: Trained model
        dataloader: Holdout test data loader
        device: Compute device
        num_classes: Number of classes
        class_names: List of class names
        use_tta: Use test-time augmentation
        tta_augmentations: Number of TTA augmentations
        amp_dtype: AMP dtype
    
    Returns:
        EvaluationMetrics with all metrics
    """
    model.eval()
    
    all_preds = []
    all_labels = []
    all_probs = []
    total_inference_time = 0.0
    n_batches = 0
    
    with torch.no_grad():
        for features, labels in tqdm(dataloader, desc="Evaluating holdout"):
            features = features.to(device, non_blocking=True)
            labels_np = labels.numpy()
            
            start_time = time.perf_counter()
            
            with torch.amp.autocast("cuda", dtype=amp_dtype):
                if use_tta:
                    # Test-time augmentation
                    all_logits = []
                    
                    # Original
                    outputs = model(features)
                    if isinstance(outputs, tuple):
                        outputs = outputs[0]  # Handle multi-output models
                    all_logits.append(outputs)
                    
                    # Augmented views
                    for aug_idx in range(tta_augmentations):
                        aug_features = apply_tta_augmentation(features, aug_idx)
                        aug_outputs = model(aug_features)
                        if isinstance(aug_outputs, tuple):
                            aug_outputs = aug_outputs[0]
                        all_logits.append(aug_outputs)
                    
                    # Average in probability space
                    avg_probs = torch.stack([F.softmax(logits, dim=1) for logits in all_logits]).mean(dim=0)
                    probs = avg_probs
                else:
                    outputs = model(features)
                    if isinstance(outputs, tuple):
                        outputs = outputs[0]
                    probs = F.softmax(outputs, dim=1)
            
            total_inference_time += time.perf_counter() - start_time
            n_batches += 1
            
            preds = probs.argmax(dim=1).cpu().numpy()
            
            all_preds.append(preds)
            all_labels.append(labels_np)
            all_probs.append(probs.cpu().numpy())
    
    # Aggregate
    all_preds = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)
    all_probs = np.concatenate(all_probs)
    
    # Compute metrics
    accuracy = (all_preds == all_labels).mean()
    
    # Top-3 accuracy
    top3_preds = np.argsort(all_probs, axis=1)[:, -3:]
    top3_correct = np.array([label in top3 for label, top3 in zip(all_labels, top3_preds)])
    top3_accuracy = top3_correct.mean()
    
    # Per-class metrics
    per_class_acc, per_class_f1 = compute_per_class_metrics(
        all_preds, all_labels, num_classes, class_names
    )
    
    # Confusion matrix
    confusion_matrix = np.zeros((num_classes, num_classes), dtype=np.int64)
    for pred, label in zip(all_preds, all_labels):
        confusion_matrix[label, pred] += 1
    
    # Calibration error
    calibration_error = compute_calibration_error(all_probs, all_labels)
    
    # Inference time (average per sample)
    avg_inference_time = (total_inference_time / len(all_labels)) * 1000  # ms
    
    return EvaluationMetrics(
        accuracy=float(accuracy),
        top3_accuracy=float(top3_accuracy),
        per_class_accuracy=per_class_acc,
        per_class_f1=per_class_f1,
        confusion_matrix=confusion_matrix,
        calibration_error=calibration_error,
        num_samples=len(all_labels),
        inference_time_ms=avg_inference_time,
    )


def load_model(checkpoint_path: Path, device: torch.device):
    """Load model from checkpoint."""
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # Detect model version
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    
    # Try to infer model config
    model_config = checkpoint.get("model_config", {})
    model_version = model_config.get("version", "v5")
    num_classes = model_config.get("num_classes", 21)
    
    # Create model based on version
    if model_version == "v5":
        from training.models.cnn_v5 import DrumClassifierCNNv5
        model = DrumClassifierCNNv5(
            num_classes=num_classes,
            **{k: v for k, v in model_config.items() if k not in ["version", "num_classes"]}
        )
    elif model_version == "v2":
        # v2 is in transcription module
        from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
        model = DrumClassifierCNNv2(num_classes=num_classes)
    else:
        # v1 is in transcription module
        from transcription.ml_drum_classifier import DrumClassifierCNN
        model = DrumClassifierCNN(num_classes=num_classes)
    
    # Load weights
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    return model, num_classes


def main():
    parser = argparse.ArgumentParser(description="Holdout Test Set Evaluation")
    parser.add_argument("--model-path", type=str, required=True, help="Model checkpoint path")
    parser.add_argument("--dataset-dir", type=str, required=True, help="Path to dataset directory")
    parser.add_argument("--labels-cache-dir", type=str, required=True, help="Path to labels cache")
    parser.add_argument("--feature-cache-dir", type=str, help="Path to feature cache")
    parser.add_argument("--holdout-config", type=str, help="Path to holdout sources config JSON")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--device", type=str, default="cuda", help="Device")
    parser.add_argument("--use-tta", action="store_true", help="Use test-time augmentation")
    parser.add_argument("--tta-augmentations", type=int, default=5, help="Number of TTA augmentations")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load holdout config
    holdout_sources = ["enst_drums", "mdb_drums"]  # Default
    if args.holdout_config and Path(args.holdout_config).exists():
        with open(args.holdout_config) as f:
            holdout_config = json.load(f)
        holdout_sources = holdout_config.get("holdout_sources", holdout_sources)
        logger.info(f"Loaded holdout config: {holdout_sources}")
    
    # Load model
    logger.info(f"Loading model from {args.model_path}")
    model, num_classes = load_model(Path(args.model_path), device)
    
    # Load dataset from train_classifier
    from training.train_classifier import DrumSampleDataset
    
    dataset_dir = Path(args.dataset_dir)
    labels_cache_dir = Path(args.labels_cache_dir)
    
    # Check for holdout-specific labels, fall back to val
    holdout_labels = labels_cache_dir / "holdout_labels.json"
    if not holdout_labels.exists():
        # Fallback: filter val labels for holdout sources
        val_labels = labels_cache_dir / "val_labels.json"
        if not val_labels.exists():
            logger.error(f"No labels found. Need either {holdout_labels} or {val_labels}")
            logger.info("\nTo prepare holdout evaluation:")
            logger.info("1. Ensure ENST-Drums and MDB-Drums are in your dataset")
            logger.info("2. Generate labels with those sources marked for holdout")
            logger.info("3. Or manually create holdout_labels.json")
            return
        
        # Load and filter val labels for holdout sources
        logger.info(f"Filtering validation labels for holdout sources: {holdout_sources}")
        with open(val_labels) as f:
            all_val_labels = json.load(f)
        
        # Filter for holdout sources (check if source name matches)
        holdout_labels_data = []
        for label in all_val_labels:
            file_path = label.get("file", label.get("audio_path", ""))
            # Check if any holdout source is in the path
            for source in holdout_sources:
                source_patterns = [source.lower(), source.replace("_", "-"), source.replace("_", " ")]
                if any(p in file_path.lower() for p in source_patterns):
                    holdout_labels_data.append(label)
                    break
        
        if not holdout_labels_data:
            logger.warning(f"No samples found for holdout sources: {holdout_sources}")
            logger.info("Available sources in validation set:")
            sources_found = set()
            for label in all_val_labels[:100]:  # Sample first 100
                file_path = label.get("file", label.get("audio_path", ""))
                parts = Path(file_path).parts
                if len(parts) > 1:
                    sources_found.add(parts[0] if len(parts[0]) > 2 else parts[1])
            for s in sorted(sources_found):
                logger.info(f"  - {s}")
            return
        
        logger.info(f"Found {len(holdout_labels_data)} holdout samples")
        
        # Save filtered labels
        with open(holdout_labels, "w") as f:
            json.dump(holdout_labels_data, f)
        logger.info(f"Saved holdout labels to {holdout_labels}")
        labels_file = holdout_labels
    else:
        labels_file = holdout_labels
    
    # Load dataset
    cache_dir = Path(args.feature_cache_dir) / "val" if args.feature_cache_dir else None
    cache_mapping = labels_cache_dir / "val_cache_mapping.npz"
    
    try:
        dataset = DrumSampleDataset(
            data_dir=dataset_dir,
            labels_file=labels_file,
            cache_dir=cache_dir,
            cache_mapping=cache_mapping if cache_mapping.exists() else None,
        )
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        logger.info("Make sure the holdout data is prepared and cached.")
        return
    
    # Load class names from components.json
    components_file = dataset_dir / "components.json"
    class_names = None
    if components_file.exists():
        with open(components_file) as f:
            components_info = json.load(f)
        class_names = components_info.get("class_names")
    
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,  # Windows safe
        pin_memory=True,
    )
    
    # Evaluate
    logger.info(f"Running holdout evaluation on {len(dataset)} samples...")
    metrics = evaluate_model(
        model=model,
        dataloader=dataloader,
        device=device,
        num_classes=num_classes,
        class_names=class_names,
        use_tta=args.use_tta,
        tta_augmentations=args.tta_augmentations,
    )
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "model_path": str(args.model_path),
        "holdout_sources": holdout_sources,
        "use_tta": args.use_tta,
        "tta_augmentations": args.tta_augmentations if args.use_tta else 0,
        "num_samples": len(dataset),
        "metrics": metrics.to_dict(),
    }
    
    with open(output_dir / "holdout_evaluation_report.json", "w") as f:
        json.dump(results, f, indent=2)
    
    np.save(output_dir / "holdout_confusion_matrix.npy", metrics.confusion_matrix)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("HOLDOUT EVALUATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Sources: {holdout_sources}")
    logger.info(f"Samples: {len(dataset)}")
    logger.info(f"Accuracy: {metrics.accuracy*100:.2f}%")
    logger.info(f"Top-3 Accuracy: {metrics.top3_accuracy*100:.2f}%")
    logger.info(f"Calibration Error (ECE): {metrics.calibration_error:.4f}")
    logger.info(f"Inference time: {metrics.inference_time_ms:.2f} ms/sample")
    if args.use_tta:
        logger.info(f"TTA augmentations: {args.tta_augmentations}")
    logger.info(f"\nResults saved to: {output_dir}")
    
    # Per-class breakdown
    logger.info("\nPer-class accuracy (bottom 5):")
    sorted_classes = sorted(metrics.per_class_accuracy.items(), key=lambda x: x[1])
    for class_name, acc in sorted_classes[:5]:
        f1 = metrics.per_class_f1.get(class_name, 0)
        logger.info(f"  {class_name}: {acc*100:.1f}% (F1: {f1:.3f})")


if __name__ == "__main__":
    main()