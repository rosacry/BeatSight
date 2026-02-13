#!/usr/bin/env python3
"""
Ensemble Evaluator for Drum Classifier

Combines predictions from multiple models for improved accuracy.
Supports:
1. Simple averaging (best for diverse models)
2. Weighted averaging (based on validation performance)
3. Voting (majority vote)
4. Temperature-scaled averaging

Usage:
    python evaluate_ensemble.py \
        --checkpoints model1.pth model2.pth model3.pth \
        --dataset F:/datasets/prod_v5_cleaned \
        --feature-cache-dir F:/feature_cache

Expected improvement: +0.5-1.5% over best single model
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from tqdm import tqdm
from sklearn.metrics import balanced_accuracy_score, classification_report

# Add ai-pipeline to path for proper module resolution
AI_PIPELINE_ROOT = Path(__file__).resolve().parents[2]
TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(AI_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_PIPELINE_ROOT))
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))


def load_model(
    checkpoint_path: Path,
    num_classes: int,
    v5_size: str,
    device: torch.device,
) -> nn.Module:
    """Load a V5 model from checkpoint."""
    from training.models.cnn_v5 import cnn_v5_small, cnn_v5_medium, cnn_v5_large
    
    if v5_size == "small":
        model = cnn_v5_small(num_classes=num_classes)
    elif v5_size == "large":
        model = cnn_v5_large(num_classes=num_classes)
    else:
        model = cnn_v5_medium(num_classes=num_classes)
    
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    if isinstance(checkpoint, dict) and "model_state" in checkpoint:
        state_dict = checkpoint["model_state"]
    elif isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    
    return model


def evaluate_single_model(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Evaluate a single model, return probabilities and labels."""
    model.eval()
    all_probs = []
    all_labels = []
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(dataloader, desc="Evaluating", leave=False):
            features, labels = batch
            features = features.to(device)
            
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            probs = F.softmax(outputs, dim=1)
            all_probs.append(probs.cpu().numpy())
            all_labels.append(labels.numpy())
    
    probs = np.concatenate(all_probs, axis=0)
    labels = np.concatenate(all_labels, axis=0)
    
    preds = probs.argmax(axis=1)
    balanced_acc = balanced_accuracy_score(labels, preds)
    
    return probs, labels, balanced_acc


def evaluate_with_tta(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    num_augmentations: int = 3,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """Evaluate with test-time augmentation."""
    from training.augmentation.specaugment import SpecAugment
    
    model.eval()
    augmenter = SpecAugment(
        freq_mask_param=10,
        time_mask_param=20,
        n_freq_masks=1,
        n_time_masks=1,
        prob=1.0,
    )
    augmenter.train()  # Enable augmentation
    
    all_probs = []
    all_labels = []
    
    with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        for batch in tqdm(dataloader, desc="Evaluating (TTA)", leave=False):
            features, labels = batch
            features = features.to(device)
            
            # Original prediction
            outputs = model(features)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            probs_list = [F.softmax(outputs, dim=1)]
            
            # Augmented predictions
            for _ in range(num_augmentations):
                aug_features = augmenter(features.clone())
                aug_outputs = model(aug_features)
                if isinstance(aug_outputs, tuple):
                    aug_outputs = aug_outputs[0]
                probs_list.append(F.softmax(aug_outputs, dim=1))
            
            # Average probabilities
            avg_probs = torch.stack(probs_list, dim=0).mean(dim=0)
            all_probs.append(avg_probs.cpu().numpy())
            all_labels.append(labels.numpy())
    
    probs = np.concatenate(all_probs, axis=0)
    labels = np.concatenate(all_labels, axis=0)
    
    preds = probs.argmax(axis=1)
    balanced_acc = balanced_accuracy_score(labels, preds)
    
    return probs, labels, balanced_acc


def ensemble_average(
    probs_list: List[np.ndarray],
    weights: Optional[List[float]] = None,
) -> np.ndarray:
    """Average probabilities from multiple models."""
    if weights is None:
        weights = [1.0 / len(probs_list)] * len(probs_list)
    else:
        weights = [w / sum(weights) for w in weights]
    
    ensemble_probs = sum(w * p for w, p in zip(weights, probs_list))
    return ensemble_probs


def ensemble_vote(probs_list: List[np.ndarray]) -> np.ndarray:
    """Majority voting from multiple models."""
    preds_list = [p.argmax(axis=1) for p in probs_list]
    preds_stack = np.stack(preds_list, axis=1)  # [N, num_models]
    
    # Mode voting
    from scipy import stats
    ensemble_preds, _ = stats.mode(preds_stack, axis=1, keepdims=False)
    
    # Convert back to probabilities (one-hot for voting)
    num_classes = probs_list[0].shape[1]
    ensemble_probs = np.zeros_like(probs_list[0])
    ensemble_probs[np.arange(len(ensemble_preds)), ensemble_preds] = 1.0
    
    return ensemble_probs


def main():
    parser = argparse.ArgumentParser(description="Ensemble evaluation")
    parser.add_argument("--checkpoints", type=Path, nargs="+", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--feature-cache-dir", type=Path, required=True)
    parser.add_argument("--v5-size", choices=["small", "medium", "large"], default="large")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--fraction", type=float, default=1.0)
    parser.add_argument("--use-tta", action="store_true")
    parser.add_argument("--tta-augmentations", type=int, default=3)
    parser.add_argument("--ensemble-method", choices=["average", "vote", "weighted"], default="average")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    
    device = torch.device(args.device)
    
    # Load class names
    components_file = args.dataset / "components.json"
    if components_file.exists():
        with open(components_file, 'r') as f:
            data = json.load(f)
        class_names = data.get("components", [])
    else:
        class_names = [f"class_{i}" for i in range(12)]
    
    num_classes = len(class_names)
    print(f"Classes ({num_classes}): {class_names}")
    
    # Load validation dataset
    print("\nLoading validation dataset...")
    # Import the dataset class from train_classifier
    from training.train_classifier import DrumSampleDataset
    
    # Find labels file
    val_dir = args.dataset / "val"
    labels_file = val_dir / "labels.json"
    if not labels_file.exists():
        labels_file = val_dir / "labels.npy"
    if not labels_file.exists():
        labels_file = val_dir / "labels.pkl"
    if not labels_file.exists():
        raise FileNotFoundError(f"Could not find labels file in {val_dir}")
    
    val_dataset = DrumSampleDataset(
        data_dir=val_dir,
        labels_file=labels_file,
        cache_dir=args.feature_cache_dir / "val",
    )
    
    total = len(val_dataset)
    subset_size = int(total * args.fraction)
    if args.fraction < 1.0:
        indices = np.random.RandomState(42).choice(total, subset_size, replace=False)
        val_subset = Subset(val_dataset, indices)
    else:
        val_subset = val_dataset
    
    print(f"Evaluating on {subset_size:,} / {total:,} samples ({args.fraction*100:.0f}%)")
    
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )
    
    # Load and evaluate each model
    print(f"\nLoading {len(args.checkpoints)} models...")
    models = []
    probs_list = []
    single_accs = []
    labels = None
    
    for i, ckpt_path in enumerate(args.checkpoints):
        print(f"\n[Model {i+1}] {ckpt_path.name}")
        model = load_model(ckpt_path, num_classes, args.v5_size, device)
        models.append(model)
        
        if args.use_tta:
            probs, labels, acc = evaluate_with_tta(
                model, val_loader, device, args.tta_augmentations
            )
        else:
            probs, labels, acc = evaluate_single_model(model, val_loader, device)
        
        probs_list.append(probs)
        single_accs.append(acc)
        print(f"  Balanced Accuracy: {acc*100:.2f}%")
    
    # Ensemble
    print("\n" + "=" * 60)
    print(f"ENSEMBLE RESULTS ({args.ensemble_method})")
    print("=" * 60)
    
    if args.ensemble_method == "average":
        ensemble_probs = ensemble_average(probs_list)
    elif args.ensemble_method == "weighted":
        # Weight by single model accuracy
        ensemble_probs = ensemble_average(probs_list, weights=single_accs)
    else:  # vote
        ensemble_probs = ensemble_vote(probs_list)
    
    ensemble_preds = ensemble_probs.argmax(axis=1)
    ensemble_acc = balanced_accuracy_score(labels, ensemble_preds)
    
    print(f"\nSingle Model Accuracies:")
    for i, acc in enumerate(single_accs):
        print(f"  Model {i+1}: {acc*100:.2f}%")
    
    print(f"\nBest Single Model: {max(single_accs)*100:.2f}%")
    print(f"Ensemble ({args.ensemble_method}): {ensemble_acc*100:.2f}%")
    print(f"Improvement: +{(ensemble_acc - max(single_accs))*100:.2f}%")
    
    # Per-class report
    print("\n" + "-" * 60)
    print("Per-Class Results (Ensemble)")
    print("-" * 60)
    
    report = classification_report(
        labels, ensemble_preds,
        labels=list(range(num_classes)),
        target_names=class_names,
        output_dict=True,
    )
    
    for cls_name in class_names:
        if cls_name in report:
            cls_report = report[cls_name]
            print(f"{cls_name:<15} Precision: {cls_report['precision']*100:5.1f}% "
                  f"Recall: {cls_report['recall']*100:5.1f}% "
                  f"F1: {cls_report['f1-score']*100:5.1f}%")
    
    # Save results
    if args.output:
        results = {
            "single_model_accuracies": [float(a) for a in single_accs],
            "best_single_model": float(max(single_accs)),
            "ensemble_accuracy": float(ensemble_acc),
            "improvement": float(ensemble_acc - max(single_accs)),
            "ensemble_method": args.ensemble_method,
            "num_models": len(args.checkpoints),
            "use_tta": args.use_tta,
            "samples_evaluated": subset_size,
        }
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    return ensemble_acc


if __name__ == "__main__":
    main()
