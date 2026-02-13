#!/usr/bin/env python3
"""
Multi-Label Drum Classifier Training Script

This script trains a drum classifier that can detect multiple simultaneous
drum hits (e.g., kick + hi-hat, snare + crash).

Key differences from single-label training:
1. Uses BCEWithLogitsLoss instead of CrossEntropyLoss
2. Model outputs sigmoid probabilities per class (not softmax)
3. Metrics use multi-label F1, hamming loss, subset accuracy
4. Positive class weighting handles imbalanced data

Usage:
    python train_multilabel.py --dataset ./dataset --epochs 50

    # With focal loss for better handling of rare classes
    python train_multilabel.py --dataset ./dataset --loss-type focal --gamma 2.0

    # Resume from single-label checkpoint
    python train_multilabel.py --dataset ./dataset --pretrained-checkpoint model.pt
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.amp import GradScaler, autocast
from torch.nn.utils import clip_grad_norm_
from torch.utils.data import DataLoader, random_split, WeightedRandomSampler
from tqdm import tqdm

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multilabel.dataset import MultiLabelDrumDataset, CachedMultiLabelDataset, BatchedMultiLabelDataset, DEFAULT_DRUM_COMPONENTS
from multilabel.loss import get_multilabel_loss
from multilabel.metrics import (
    MultiLabelMetricTracker,
    compute_all_metrics,
    find_optimal_thresholds,
)

# Import models
try:
    from models.cnn_v5 import DrumClassifierCNNv5, cnn_v5_small, cnn_v5_medium, cnn_v5_large
    HAS_V5_MODEL = True
except ImportError:
    HAS_V5_MODEL = False
    DrumClassifierCNNv5 = None

try:
    from models.coord_attention import DrumClassifierCNNv4
    HAS_V4_MODEL = True
except ImportError:
    HAS_V4_MODEL = False
    DrumClassifierCNNv4 = None

try:
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
    HAS_V2_MODEL = True
except ImportError:
    HAS_V2_MODEL = False
    DrumClassifierCNNv2 = None

from transcription.ml_drum_classifier import DrumClassifierCNN

# Optional SpecAugment
try:
    from training.augmentation.specaugment import SpecAugment, get_specaugment
    HAS_SPECAUGMENT = True
except ImportError:
    HAS_SPECAUGMENT = False
    SpecAugment = None
    get_specaugment = None

# Optional EMA (Exponential Moving Average)
try:
    from training.utils.ema import ModelEMA, get_ema_decay
    HAS_EMA = True
except ImportError:
    HAS_EMA = False
    ModelEMA = None
    get_ema_decay = None

# Optional SAM Optimizer
try:
    from training.optimizers.sam import SAM
    HAS_SAM = True
except ImportError:
    HAS_SAM = False
    SAM = None

# Optional SWA (Stochastic Weight Averaging)
try:
    from torch.optim.swa_utils import AveragedModel, SWALR
    HAS_SWA = True
except ImportError:
    HAS_SWA = False
    AveragedModel = None
    SWALR = None

try:
    import wandb
    HAS_WANDB = True
except ImportError:
    wandb = None
    HAS_WANDB = False


class MultiLabelDrumClassifier(nn.Module):
    """
    Wrapper that adapts single-label classifiers for multi-label output.
    
    The key change is removing any final softmax (if present) since
    we use sigmoid per-class for multi-label classification.
    """
    
    def __init__(
        self,
        backbone: nn.Module,
        num_classes: int = 21,
    ):
        super().__init__()
        self.backbone = backbone
        self.num_classes = num_classes
        
        # The backbone's classifier outputs raw logits
        # For multi-label, we apply sigmoid at inference time
        # (BCEWithLogitsLoss handles sigmoid during training)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass returning raw logits.
        
        Args:
            x: Input mel spectrogram, shape (B, 1, H, W)
        
        Returns:
            Logits of shape (B, num_classes)
        """
        return self.backbone(x)
    
    def predict(
        self,
        x: torch.Tensor,
        threshold: float = 0.5,
        per_class_thresholds: Optional[Dict[int, float]] = None
    ) -> torch.Tensor:
        """
        Predict with thresholding.
        
        Args:
            x: Input mel spectrogram
            threshold: Global classification threshold
            per_class_thresholds: Optional per-class thresholds
        
        Returns:
            Binary predictions of shape (B, num_classes)
        """
        logits = self.forward(x)
        probs = torch.sigmoid(logits)
        
        if per_class_thresholds is not None:
            predictions = torch.zeros_like(probs)
            for i in range(self.num_classes):
                t = per_class_thresholds.get(i, threshold)
                predictions[:, i] = (probs[:, i] >= t).float()
        else:
            predictions = (probs >= threshold).float()
        
        return predictions
    
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        """Return per-class probabilities."""
        logits = self.forward(x)
        return torch.sigmoid(logits)


def create_model(
    model_version: str,
    num_classes: int,
    pretrained_checkpoint: Optional[str] = None,
    v5_size: str = "medium",
    drop_path_rate: float = 0.1,
    **kwargs
) -> MultiLabelDrumClassifier:
    """
    Create a multi-label drum classifier.
    
    Args:
        model_version: "v1", "v2", "v4", "v5"
        num_classes: Number of drum classes
        pretrained_checkpoint: Optional path to pretrained single-label model
        v5_size: Size preset for V5 model ("small", "medium", "large")
        drop_path_rate: Drop path rate for V5 model
    
    Returns:
        MultiLabelDrumClassifier instance
    """
    # Create backbone
    if model_version == "v5" and HAS_V5_MODEL:
        # V5 ULTIMATE model - best single-model architecture
        size_configs = {
            "small": cnn_v5_small,
            "medium": cnn_v5_medium,
            "large": cnn_v5_large,
        }
        config_fn = size_configs.get(v5_size, cnn_v5_medium)
        backbone = config_fn(
            num_classes=num_classes,
            drop_path_rate=drop_path_rate,
            use_deep_supervision=False,  # Disable for multi-label (different loss structure)
            use_multi_task=False,  # Multi-label already handles multiple outputs
        )
        print(f"Created V5 {v5_size} backbone with {sum(p.numel() for p in backbone.parameters()):,} parameters")
    elif model_version == "v4" and HAS_V4_MODEL:
        backbone = DrumClassifierCNNv4(
            num_classes=num_classes,
            use_coord_attention=True,
            **kwargs
        )
    elif model_version == "v2" and HAS_V2_MODEL:
        backbone = DrumClassifierCNNv2(
            num_classes=num_classes,
            use_se=True,
            **kwargs
        )
    else:
        backbone = DrumClassifierCNN(num_classes=num_classes)
    
    # Load pretrained weights if provided
    if pretrained_checkpoint is not None:
        checkpoint = torch.load(pretrained_checkpoint, map_location='cpu', weights_only=False)
        
        # Handle different checkpoint formats
        if 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
        elif 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        else:
            state_dict = checkpoint
        
        # Handle backbone. prefix mismatch
        # If checkpoint has backbone. prefix but model doesn't (or vice versa)
        sample_key = next(iter(state_dict.keys()))
        model_sample_key = next(iter(backbone.state_dict().keys()))
        
        if sample_key.startswith('backbone.') and not model_sample_key.startswith('backbone.'):
            # Remove backbone. prefix from checkpoint keys
            print("Removing 'backbone.' prefix from checkpoint keys...")
            state_dict = {k.replace('backbone.', '', 1): v for k, v in state_dict.items()}
        elif not sample_key.startswith('backbone.') and model_sample_key.startswith('backbone.'):
            # Add backbone. prefix to checkpoint keys
            print("Adding 'backbone.' prefix to checkpoint keys...")
            state_dict = {f'backbone.{k}': v for k, v in state_dict.items()}
        
        # Load weights (may have some mismatches for classifier head)
        missing, unexpected = backbone.load_state_dict(state_dict, strict=False)
        if missing:
            # Filter out expected missing keys (num_batches_tracked, etc.)
            important_missing = [k for k in missing if 'num_batches_tracked' not in k]
            if important_missing:
                print(f"Warning: Missing {len(important_missing)} important keys")
        if unexpected:
            print(f"Note: {len(unexpected)} unexpected keys (will be ignored)")
        
        print(f"Loaded pretrained weights from {pretrained_checkpoint}")
    
    return MultiLabelDrumClassifier(backbone, num_classes)


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
    scaler: Optional[GradScaler] = None,
    use_amp: bool = False,
) -> Tuple[float, float]:
    """
    Train for one epoch.
    
    Returns:
        Tuple of (average_loss, micro_f1)
    """
    model.train()
    total_loss = 0.0
    tracker = MultiLabelMetricTracker()
    
    pbar = tqdm(dataloader, desc="Training", leave=False, dynamic_ncols=False)
    for features, labels in pbar:
        features = features.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        
        if use_amp and scaler is not None:
            with autocast(device_type='cuda'):
                logits = model(features)
                loss = criterion(logits, labels)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(features)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
        
        total_loss += loss.item()
        tracker.update(logits, labels)
        
        pbar.set_postfix(loss=f"{loss.item():.4f}")
    
    avg_loss = total_loss / len(dataloader)
    metrics = tracker.compute()
    
    return avg_loss, metrics.micro_f1


@torch.no_grad()
def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    class_names: Optional[List[str]] = None,
) -> Tuple[float, Any]:
    """
    Evaluate model on validation set.
    
    Returns:
        Tuple of (average_loss, MultiLabelMetrics)
    """
    model.eval()
    total_loss = 0.0
    all_logits = []
    all_labels = []
    
    # Track running per-label accuracy (like training)
    running_correct = 0
    running_total = 0
    
    pbar = tqdm(dataloader, desc="Validating", leave=False, dynamic_ncols=False)
    for features, labels in pbar:
        features = features.to(device)
        labels = labels.to(device)
        
        logits = model(features)
        loss = criterion(logits, labels)
        
        total_loss += loss.item()
        all_logits.append(logits.cpu())
        all_labels.append(labels.cpu())
        
        # Update running per-label accuracy
        pred_binary = (torch.sigmoid(logits) >= 0.5).float()
        running_correct += (pred_binary == labels).sum().item()
        running_total += labels.numel()
        cur_acc = 100.0 * running_correct / max(running_total, 1)
        pbar.set_postfix(loss=f"{loss.item():.4f}", acc=f"{cur_acc:.2f}%")
    
    avg_loss = total_loss / len(dataloader)
    
    # Compute metrics
    logits = torch.cat(all_logits, dim=0)
    labels = torch.cat(all_labels, dim=0)
    metrics = compute_all_metrics(logits, labels, class_names=class_names)
    
    return avg_loss, metrics


@torch.no_grad()
def evaluate_by_source(
    model: nn.Module,
    val_dataset,
    criterion: nn.Module,
    device: torch.device,
    batch_size: int = 128,
    num_workers: int = 4,
    class_names: Optional[List[str]] = None,
) -> Tuple[float, Any, Dict[str, Any]]:
    """
    Evaluate model with metrics split by acoustic vs electric sources.
    
    This function tracks which samples come from which source datasets
    and computes separate metrics for:
    - Acoustic: ENST, IDMT, Cambridge, Telefunken, SignatureSounds, MedleyDB
    - Electronic: EGMD, Groove, Slakh, Lakh
    
    Returns:
        Tuple of (average_loss, combined_metrics, source_metrics_dict)
        where source_metrics_dict = {'acoustic': metrics, 'electronic': metrics, 'synthetic': metrics}
    """
    from torch.utils.data import ConcatDataset
    
    model.eval()
    
    # Define source categories
    acoustic_sources = {'enst_drums', 'idmt_smt_drums_v2', 'cambridge_multitrack', 
                        'telefunken', 'signaturesounds', 'medleydb', 'acoustic_synth'}
    electronic_sources = {'egmd', 'groove', 'groove_midi', 'slakh', 'lakh', 'lakh_midi', 'lakh_synth'}
    synthetic_sources = {'synthetic', 'multilabel_synthetic'}
    
    # Collect predictions by source category AND individual dataset
    source_logits = {'acoustic': [], 'electronic': [], 'synthetic': [], 'demucs': [], 'other': []}
    source_labels = {'acoustic': [], 'electronic': [], 'synthetic': [], 'demucs': [], 'other': []}
    source_counts = {'acoustic': 0, 'electronic': 0, 'synthetic': 0, 'demucs': 0, 'other': 0}

    # Per-individual-dataset tracking (e.g. egmd_demucs, slakh2100_demucs separately)
    per_dataset_logits: Dict[str, List] = {}
    per_dataset_labels: Dict[str, List] = {}
    per_dataset_counts: Dict[str, int] = {}
    
    all_logits = []
    all_labels = []
    total_loss = 0.0
    num_batches = 0
    
    # Check if val_dataset is a ConcatDataset with source-trackable sub-datasets
    if isinstance(val_dataset, ConcatDataset):
        # Compute total batches for progress bar
        total_val_batches = sum(
            (len(sub_ds) + batch_size - 1) // batch_size
            for sub_ds in val_dataset.datasets if len(sub_ds) > 0
        )
        running_correct = 0
        running_total = 0
        pbar = tqdm(total=total_val_batches, desc="Validating", leave=False, dynamic_ncols=False)

        # Process each sub-dataset separately to track source
        for sub_ds in val_dataset.datasets:
            ds_name = getattr(sub_ds, 'dataset_name', 'unknown').lower()

            # Categorize — check demucs suffix first (e.g. enst_drums_demucs, slakh2100_demucs)
            if ds_name.endswith('_demucs'):
                category = 'demucs'
            elif ds_name in acoustic_sources:
                category = 'acoustic'
            elif ds_name in electronic_sources:
                category = 'electronic'
            elif ds_name in synthetic_sources:
                category = 'synthetic'
            else:
                category = 'other'

            # Skip empty datasets
            if len(sub_ds) == 0:
                continue

            # Create loader for this sub-dataset
            sub_loader = DataLoader(
                sub_ds, batch_size=batch_size, shuffle=False,
                num_workers=num_workers, pin_memory=True
            )

            for features, labels in sub_loader:
                features = features.to(device)
                labels_gpu = labels.to(device)

                logits = model(features)
                loss = criterion(logits, labels_gpu)
                total_loss += loss.item()
                num_batches += 1

                logits_cpu = logits.cpu()

                source_logits[category].append(logits_cpu)
                source_labels[category].append(labels)
                source_counts[category] += len(labels)

                # Track per-individual-dataset (only for demucs datasets)
                if category == 'demucs':
                    if ds_name not in per_dataset_logits:
                        per_dataset_logits[ds_name] = []
                        per_dataset_labels[ds_name] = []
                        per_dataset_counts[ds_name] = 0
                    per_dataset_logits[ds_name].append(logits_cpu)
                    per_dataset_labels[ds_name].append(labels)
                    per_dataset_counts[ds_name] += len(labels)

                all_logits.append(logits_cpu)
                all_labels.append(labels)

                # Update progress bar with running accuracy
                with torch.no_grad():
                    pred_binary = (torch.sigmoid(logits) >= 0.5).float()
                    running_correct += (pred_binary == labels_gpu).sum().item()
                    running_total += labels_gpu.numel()
                cur_acc = 100.0 * running_correct / max(running_total, 1)
                pbar.update(1)
                pbar.set_postfix(src=ds_name[:15], acc=f"{cur_acc:.2f}%", loss=f"{loss.item():.4f}")

        pbar.close()
    else:
        # Single dataset - check if it has dataset_name
        ds_name = getattr(val_dataset, 'dataset_name', 'unknown').lower()
        
        if ds_name.endswith('_demucs'):
            category = 'demucs'
        elif ds_name in acoustic_sources:
            category = 'acoustic'
        elif ds_name in electronic_sources:
            category = 'electronic'
        elif ds_name in synthetic_sources:
            category = 'synthetic'
        else:
            category = 'other'
        
        loader = DataLoader(
            val_dataset, batch_size=batch_size, shuffle=False,
            num_workers=num_workers, pin_memory=True
        )
        
        for features, labels in tqdm(loader, desc="Validating", leave=False):
            features = features.to(device)
            labels_gpu = labels.to(device)
            
            logits = model(features)
            loss = criterion(logits, labels_gpu)
            total_loss += loss.item()
            num_batches += 1
            
            logits_cpu = logits.cpu()
            
            source_logits[category].append(logits_cpu)
            source_labels[category].append(labels)
            source_counts[category] += len(labels)
            
            all_logits.append(logits_cpu)
            all_labels.append(labels)
    
    avg_loss = total_loss / max(num_batches, 1)
    
    # Compute combined metrics
    combined_logits = torch.cat(all_logits, dim=0)
    combined_labels = torch.cat(all_labels, dim=0)
    combined_metrics = compute_all_metrics(combined_logits, combined_labels, class_names=class_names)
    
    # Compute per-source metrics
    source_metrics = {}
    for category in ['acoustic', 'electronic', 'synthetic', 'demucs', 'other']:
        if source_counts[category] > 0 and source_logits[category]:
            cat_logits = torch.cat(source_logits[category], dim=0)
            cat_labels = torch.cat(source_labels[category], dim=0)
            cat_metrics = compute_all_metrics(cat_logits, cat_labels, class_names=class_names)
            source_metrics[category] = {
                'count': source_counts[category],
                'micro_f1': cat_metrics.micro_f1,
                'macro_f1': cat_metrics.macro_f1,
                'per_class_f1': cat_metrics.per_class_f1,
                'per_class_recall': cat_metrics.per_class_recall,
                'per_class_precision': cat_metrics.per_class_precision,
            }

    # Compute clean aggregate (everything except demucs) for domain gap analysis
    clean_logits_list = []
    clean_labels_list = []
    for cat in ['acoustic', 'electronic', 'synthetic', 'other']:
        clean_logits_list.extend(source_logits[cat])
        clean_labels_list.extend(source_labels[cat])
    if clean_logits_list:
        clean_logits_cat = torch.cat(clean_logits_list, dim=0)
        clean_labels_cat = torch.cat(clean_labels_list, dim=0)
        clean_metrics = compute_all_metrics(clean_logits_cat, clean_labels_cat, class_names=class_names)
        clean_count = sum(source_counts[c] for c in ['acoustic', 'electronic', 'synthetic', 'other'])
        source_metrics['clean'] = {
            'count': clean_count,
            'micro_f1': clean_metrics.micro_f1,
            'macro_f1': clean_metrics.macro_f1,
            'per_class_f1': clean_metrics.per_class_f1,
            'per_class_recall': clean_metrics.per_class_recall,
            'per_class_precision': clean_metrics.per_class_precision,
        }

    # Compute per-individual-dataset metrics (for Demucs breakdown)
    per_dataset_metrics = {}
    for ds_name, logits_list in per_dataset_logits.items():
        if logits_list and per_dataset_counts[ds_name] > 0:
            ds_logits = torch.cat(logits_list, dim=0)
            ds_labels = torch.cat(per_dataset_labels[ds_name], dim=0)
            ds_metrics = compute_all_metrics(ds_logits, ds_labels, class_names=class_names)
            per_dataset_metrics[ds_name] = {
                'count': per_dataset_counts[ds_name],
                'micro_f1': ds_metrics.micro_f1,
                'macro_f1': ds_metrics.macro_f1,
                'per_class_f1': ds_metrics.per_class_f1,
            }
    if per_dataset_metrics:
        source_metrics['per_dataset'] = per_dataset_metrics

    return avg_loss, combined_metrics, source_metrics


def main():
    parser = argparse.ArgumentParser(
        description="Train multi-label drum classifier"
    )
    
    # Data
    parser.add_argument('--dataset', type=str, default=None,
                        help='Path to dataset directory (legacy, use --train-dir/--val-dir)')
    parser.add_argument('--train-dir', type=str, default=None,
                        help='Path to training data directory')
    parser.add_argument('--val-dir', type=str, default=None,
                        help='Path to validation data directory')
    parser.add_argument('--events-file', type=str, default='prod_combined_events.jsonl',
                        help='Events JSONL file name (relative to dataset)')
    parser.add_argument('--labels-file', type=str, default='labels.json',
                        help='Labels file name (relative to dataset)')
    parser.add_argument('--feature-cache-dir', type=str, default=None,
                        help='Feature cache directory (for consolidated cache)')
    parser.add_argument('--source-dataset', type=str, default=None,
                        help='Source dataset directory for synthetic multi-label (contains cache_mapping.npz)')
    parser.add_argument('--cache-dir', type=str, default=None,
                        help='Feature cache directory (legacy, use --feature-cache-dir)')
    parser.add_argument('--blending-strategy', type=str, default='max',
                        choices=['max', 'mean', 'weighted_sum', 'softmax'],
                        help='Spectrogram blending strategy for synthetic multi-label. '
                             'weighted_sum recommended for better weak class detection')
    parser.add_argument('--class-boost', type=str, default=None,
                        help='JSON dict of class_idx:boost_factor for weighted_sum blending. '
                             'Example: {"5":2.0,"2":1.8,"8":1.5} for hihat_pedal, cross_stick, ride_bow')
    
    # Model
    parser.add_argument('--model-version', type=str, default='v5',
                        choices=['v1', 'v2', 'v4', 'v5'],
                        help='Model architecture version (v5 recommended)')
    parser.add_argument('--v5-size', type=str, default='large',
                        choices=['small', 'medium', 'large'],
                        help='V5 model size preset (large for production)')
    parser.add_argument('--drop-path-rate', type=float, default=0.1,
                        help='Drop path rate for V5 model')
    parser.add_argument('--num-classes', type=int, default=12,
                        help='Number of drum classes (12 for production)')
    parser.add_argument('--pretrained-checkpoint', '--pretrained', type=str, default=None,
                        dest='pretrained_checkpoint',
                        help='Path to pretrained single-label checkpoint (e.g., from v5-full)')
    
    # Loss
    parser.add_argument('--loss-type', type=str, default='focal',
                        choices=['bce', 'focal', 'asymmetric', 'recall_boost', 'adaptive', 'ohem', 'cb_focal'],
                        help='Loss function type (cb_focal = class-balanced focal, the technique that got 95%% on single-label)')
    parser.add_argument('--gamma', type=float, default=2.0,
                        help='Focal loss gamma parameter')
    parser.add_argument('--cb-beta', type=float, default=0.999,
                        help='Class-balanced beta (0.999 for moderate, 0.9999 for extreme imbalance)')
    parser.add_argument('--recall-boost-weight', type=float, default=1.5,
                        help='Extra weight for positive samples to boost recall (recall_boost loss)')
    parser.add_argument('--use-per-class-gamma', action='store_true',
                        help='Use per-class gamma based on class difficulty (recall_boost loss)')
    parser.add_argument('--hard-fraction', type=float, default=0.5,
                        help='Fraction of batch treated as hard examples (ohem loss)')
    parser.add_argument('--hard-weight', type=float, default=3.0,
                        help='Weight multiplier for hard examples (ohem loss)')
    parser.add_argument('--label-smoothing', type=float, default=0.05,
                        help='Label smoothing factor (0.05 for 12-class multi-label)')
    parser.add_argument('--use-pos-weight', action='store_true',
                        help='Use positive class weighting')
    parser.add_argument('--class-loss-weight', type=str, action='append', default=None,
                        help='Per-class loss weight multiplier. Format: class_name=weight. '
                             'Applied on top of CB-focal weights. Use to boost specific classes '
                             'or zero out classes you don\'t care about. '
                             'Example: --class-loss-weight china=5.0 --class-loss-weight crash=5.0 '
                             '--class-loss-weight splash=5.0')
    
    # Training - Core
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=128,
                        help='Batch size')
    parser.add_argument('--grad-accum-steps', type=int, default=1,
                        help='Accumulate gradients over N mini-batches before optimizer step')
    parser.add_argument('--lr', type=float, default=1e-5,
                        help='Learning rate (lower for fine-tuning from pretrained)')
    parser.add_argument('--weight-decay', type=float, default=1e-4,
                        help='Weight decay')
    parser.add_argument('--val-split', type=float, default=0.1,
                        help='Validation split ratio')
    
    # Training - Mixed Precision
    parser.add_argument('--use-amp', action='store_true',
                        help='Use automatic mixed precision (legacy, use --amp-dtype)')
    parser.add_argument('--amp-dtype', type=str, default=None,
                        choices=['float16', 'bfloat16'],
                        help='AMP dtype (enables mixed precision with specified dtype)')
    
    # Training - Learning Rate Schedule
    parser.add_argument('--scheduler', type=str, default='cosine',
                        choices=['cosine', 'plateau', 'cosine_warm_restarts'],
                        help='Learning rate scheduler')
    parser.add_argument('--warmup-epochs', type=int, default=0,
                        help='Number of warmup epochs with linear LR ramp')
    parser.add_argument('--min-lr', type=float, default=None,
                        help='Minimum LR for cosine scheduler (default: 1%% of base LR)')
    parser.add_argument('--reset-scheduler', action='store_true',
                        help='Reset LR scheduler when resuming')
    
    # Training - Advanced Optimizers
    parser.add_argument('--use-sam', action='store_true',
                        help='Use SAM optimizer for better generalization')
    parser.add_argument('--sam-rho', type=float, default=0.05,
                        help='SAM neighborhood size')
    parser.add_argument('--sam-adaptive', action='store_true',
                        help='Use Adaptive SAM')
    
    # Training - Model Averaging
    parser.add_argument('--use-ema', action='store_true',
                        help='Use Exponential Moving Average of weights')
    parser.add_argument('--ema-decay', type=float, default=0.999,
                        help='EMA decay rate')
    parser.add_argument('--use-swa', action='store_true',
                        help='Use Stochastic Weight Averaging')
    parser.add_argument('--swa-start', type=float, default=0.75,
                        help='When to start SWA (fraction of total epochs)')
    parser.add_argument('--swa-lr', type=float, default=None,
                        help='SWA learning rate (default: 10%% of base LR)')
    
    # Training - Regularization
    parser.add_argument('--specaugment', type=str, default='none',
                        choices=['none', 'light', 'default', 'strong', 'drum'],
                        help='SpecAugment preset')
    parser.add_argument('--grad-clip-norm', type=float, default=None,
                        help='Max norm for gradient clipping')
    
    # Training - Memory Optimization
    parser.add_argument('--gradient-checkpointing', action='store_true',
                        help='Enable gradient checkpointing to reduce VRAM')
    parser.add_argument('--channels-last', action='store_true',
                        help='Use channels-last memory format')
    
    # Training - DataLoader
    parser.add_argument('--num-workers', type=int, default=4,
                        help='DataLoader worker processes')
    parser.add_argument('--prefetch-factor', type=int, default=2,
                        help='Samples prefetched per worker')
    parser.add_argument('--persistent-workers', action='store_true',
                        help='Keep DataLoader workers alive between epochs')
    parser.add_argument('--pin-memory', action='store_true',
                        help='Pin memory for DataLoader')
    
    # Training - Class Balancing
    parser.add_argument('--balanced-sampling', action='store_true',
                        help='Use class-balanced sampling to oversample rare classes')
    parser.add_argument('--balanced-method', type=str, default='rare_class',
                        choices=['rare_class', 'mean_class', 'max_class'],
                        help='Balancing method: rare_class (most aggressive), mean_class, max_class (least aggressive)')
    parser.add_argument('--acoustic-oversample', type=float, default=1.0,
                        help='Multiply sampling weights for acoustic datasets (e.g., 5.0). Only applies with --balanced-sampling.')
    parser.add_argument('--dataset-weight', action='append', default=[],
                        help='Per-dataset sampling weight override, format name=multiplier (repeatable).')
    parser.add_argument('--include-datasets', type=str, default=None,
                        help='Comma-separated list of dataset name prefixes to include '
                             '(e.g., "egmd_demucs,slakh2100_demucs"). All others excluded.')
    parser.add_argument('--exclude-datasets', type=str, default=None,
                        help='Comma-separated list of dataset name prefixes to exclude.')

    # Checkpointing
    parser.add_argument('--checkpoint-every', type=int, default=1,
                        help='Save checkpoint every N epochs')
    parser.add_argument('--checkpoint-every-batches', type=int, default=0,
                        help='Save mid-epoch checkpoint every N batches (0 disables)')
    parser.add_argument('--resume', type=str, default=None,
                        help='Path to checkpoint to resume from')
    
    # Output
    parser.add_argument('--output-dir', '--output', type=str, default='runs/v5_multilabel',
                        dest='output_dir',
                        help='Directory for saving checkpoints')
    parser.add_argument('--wandb-project', type=str, default=None,
                        help='Weights & Biases project name')
    parser.add_argument('--wandb-run-name', type=str, default=None,
                        help='Weights & Biases run name')
    
    args = parser.parse_args()

    # Parse dataset weight overrides
    dataset_weights = {}
    for item in args.dataset_weight:
        if '=' not in item:
            raise ValueError(f"Invalid --dataset-weight '{item}'. Use name=multiplier.")
        name, val = item.split('=', 1)
        try:
            dataset_weights[name.strip()] = float(val)
        except ValueError as exc:
            raise ValueError(f"Invalid multiplier for --dataset-weight '{item}'") from exc

    acoustic_datasets = {
        'enst_drums', 'idmt_smt_drums_v2', 'cambridge_multitrack',
        'telefunken', 'signaturesounds', 'medleydb', 'acoustic_synth'
    }
    
    # Handle dataset path arguments
    if args.train_dir:
        train_dir = Path(args.train_dir)
        val_dir = Path(args.val_dir) if args.val_dir else None
        dataset_path = train_dir.parent
    elif args.dataset:
        dataset_path = Path(args.dataset)
        train_dir = dataset_path / "train"
        val_dir = dataset_path / "val"
    else:
        parser.error("Either --dataset or --train-dir must be specified")
    
    # Handle AMP dtype
    use_amp = args.use_amp or args.amp_dtype is not None
    amp_dtype = torch.bfloat16 if args.amp_dtype == 'bfloat16' else torch.float16
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    if use_amp:
        print(f"Using AMP with dtype: {amp_dtype}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Handle feature cache directory (support both new and legacy args)
    feature_cache_dir = None
    if args.feature_cache_dir:
        feature_cache_dir = Path(args.feature_cache_dir)
    elif args.cache_dir:
        feature_cache_dir = Path(args.cache_dir)
    
    # Handle source dataset for synthetic multi-label training
    source_dataset_path = None
    if args.source_dataset:
        source_dataset_path = Path(args.source_dataset)
    
    # Load dataset
    print(f"\nLoading dataset...")
    print(f"  Train dir: {train_dir}")
    if val_dir:
        print(f"  Val dir: {val_dir}")
    
    # Detect whether this is a synthetic multi-label dataset (has source_indices.npy)
    is_synthetic = (train_dir / "source_indices.npy").exists()
    
    # Check for batched manifest format (from extract_multilabel_from_midi.py)
    # Look for manifest files like egmd_manifest.json, groove_manifest.json
    # Search recursively up to 3 levels deep
    manifest_files = []
    for pattern in ['*_manifest.json', '*/*_manifest.json', '*/*/*_manifest.json']:
        manifest_files.extend(list(dataset_path.glob(pattern)))
    # Deduplicate
    manifest_files = list(set(manifest_files))

    # Filter manifests by include/exclude lists
    if manifest_files and args.include_datasets:
        include_prefixes = [p.strip() for p in args.include_datasets.split(',')]
        before = len(manifest_files)
        manifest_files = [m for m in manifest_files
                          if any(m.stem.replace('_manifest', '').startswith(p)
                                 for p in include_prefixes)]
        print(f"  --include-datasets: kept {len(manifest_files)}/{before} manifests "
              f"matching {include_prefixes}")

    if manifest_files and args.exclude_datasets:
        exclude_prefixes = [p.strip() for p in args.exclude_datasets.split(',')]
        before = len(manifest_files)
        manifest_files = [m for m in manifest_files
                          if not any(m.stem.replace('_manifest', '').startswith(p)
                                     for p in exclude_prefixes)]
        print(f"  --exclude-datasets: removed {before - len(manifest_files)}/{before} manifests "
              f"matching {exclude_prefixes}")

    if manifest_files and not (train_dir / "features.npy").exists():
        # Use BatchedMultiLabelDataset for manifest-based loading
        print(f"Detected batched manifest format with {len(manifest_files)} manifest(s)")
        
        # Combine multiple manifests (e.g., egmd + groove)
        all_train_datasets = []
        all_val_datasets = []
        
        for manifest_path in manifest_files:
            print(f"  Loading from manifest: {manifest_path.name}")
            
            # Find batch directory (usually next to manifest or in subfolder)
            batch_dir = manifest_path.parent
            for subdir in ['batches', f'{manifest_path.stem.replace("_manifest", "")}_batches']:
                candidate = batch_dir / subdir
                if candidate.exists():
                    batch_dir = candidate
                    break
            
            # Create train and val datasets with 90/10 split
            train_ds = BatchedMultiLabelDataset(
                manifest_path=manifest_path,
                batch_dir=batch_dir,
                specaugment=None,  # Will add later
                num_classes=args.num_classes,
                is_train=True,
                train_ratio=1.0 - args.val_split,
            )
            all_train_datasets.append(train_ds)
            
            val_ds = BatchedMultiLabelDataset(
                manifest_path=manifest_path,
                batch_dir=batch_dir,
                specaugment=None,
                num_classes=args.num_classes,
                is_train=False,
                train_ratio=1.0 - args.val_split,
            )
            all_val_datasets.append(val_ds)
        
        # Combine datasets if multiple manifests
        if len(all_train_datasets) == 1:
            train_dataset = all_train_datasets[0]
            val_dataset = all_val_datasets[0]
        else:
            from torch.utils.data import ConcatDataset
            train_dataset = ConcatDataset(all_train_datasets)
            val_dataset = ConcatDataset(all_val_datasets)
            print(f"  Combined: {len(train_dataset):,} train + {len(val_dataset):,} val samples")
        
        full_dataset = train_dataset  # For pos_weight calculation
        
        # Get class counts from first dataset for loss weighting
        if hasattr(all_train_datasets[0], 'get_class_counts'):
            class_counts = all_train_datasets[0].get_class_counts()
        else:
            class_counts = None
    else:
        class_counts = None  # Will compute later if needed
        
        # Check for .npy format (CachedMultiLabelDataset)
        # Support multiple naming conventions:
        # 1. features.npy + labels.npy (simple_extract.py output)
        # 2. train_labels_labels.npy (older format)
        # 3. {split_name}_labels_labels.npy (split-specific naming)
        train_features_npy = train_dir / "features.npy"
        train_labels_npy = train_dir / "labels.npy"
        has_simple_format = train_features_npy.exists() and train_labels_npy.exists()
        
        if not has_simple_format:
            train_labels_npy = train_dir / "train_labels_labels.npy"
            if not train_labels_npy.exists():
                # Try split-specific naming
                split_name = train_dir.name
                train_labels_npy = train_dir / f"{split_name}_labels_labels.npy"
        
        if has_simple_format or train_labels_npy.exists():
            # New format: Use CachedMultiLabelDataset with pre-split train/val
            print(f"Using CachedMultiLabelDataset with pre-split train/val directories")
            if is_synthetic:
                print(f"Detected synthetic multi-label dataset - will blend spectrograms on-the-fly")
            
            # For synthetic datasets, BOTH train and val use source dataset's TRAIN cache mapping
            # because the source_indices in both splits point to training samples
            train_cache_mapping = None
            val_cache_mapping = None
            train_feature_cache = feature_cache_dir
            val_feature_cache = feature_cache_dir
            
            if source_dataset_path:
                # Both train and val multi-label datasets blend from the TRAIN source samples
                train_cache_mapping = source_dataset_path / "train" / "cache_mapping.npz"
                val_cache_mapping = source_dataset_path / "train" / "cache_mapping.npz"  # Same as train!
                train_feature_cache = feature_cache_dir / "train" if (feature_cache_dir / "train").exists() else feature_cache_dir
                val_feature_cache = train_feature_cache  # Use train cache for val too
            else:
                train_cache_mapping = train_dir / "cache_mapping.npz"
                if val_dir:
                    val_cache_mapping = val_dir / "cache_mapping.npz"
            
            train_dataset = CachedMultiLabelDataset(
                data_dir=train_dir,
                num_classes=args.num_classes,
                class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
                feature_cache_dir=train_feature_cache,
                cache_mapping_path=train_cache_mapping,
                is_multilabel=True,
            )
            
            # Configure blending strategy for synthetic multi-label datasets
            if is_synthetic and hasattr(args, 'blending_strategy'):
                train_dataset.blending_strategy = args.blending_strategy
                print(f"[Blending] Using strategy: {args.blending_strategy}")
                
                # Parse and apply class boost weights if provided
                if args.class_boost and args.blending_strategy == 'weighted_sum':
                    try:
                        boost_dict = json.loads(args.class_boost)
                        # Convert string keys to int
                        train_dataset.class_boost_weights = {int(k): float(v) for k, v in boost_dict.items()}
                        print(f"[Blending] Class boost weights: {train_dataset.class_boost_weights}")
                    except Exception as e:
                        print(f"[Blending] Warning: Failed to parse class-boost: {e}")
            
            train_dataset.print_statistics()
            
            # Check for val directory with supported naming conventions
            val_labels_exists = False
            if val_dir:
                val_labels_exists = (
                    (val_dir / "labels.npy").exists() or  # simple format
                    (val_dir / "val_labels_labels.npy").exists() or 
                    (val_dir / "train_labels_labels.npy").exists()
                )
            
            if val_labels_exists:
                val_dataset = CachedMultiLabelDataset(
                    data_dir=val_dir,
                    num_classes=args.num_classes,
                    class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
                    feature_cache_dir=val_feature_cache,
                    cache_mapping_path=val_cache_mapping,
                    is_multilabel=True,
                )
                
                # Apply same blending strategy to validation dataset
                if is_synthetic and hasattr(args, 'blending_strategy'):
                    val_dataset.blending_strategy = args.blending_strategy
                    if hasattr(train_dataset, 'class_boost_weights'):
                        val_dataset.class_boost_weights = train_dataset.class_boost_weights
            else:
                # Split training data for validation
                val_size = int(len(train_dataset) * args.val_split)
                train_size = len(train_dataset) - val_size
                train_dataset, val_dataset = random_split(
                    train_dataset,
                    [train_size, val_size],
                    generator=torch.Generator().manual_seed(42)
                )
            
            # Get class names from train dataset
            full_dataset = train_dataset  # For pos_weight calculation
        
        else:
            # Legacy format: Use MultiLabelDrumDataset with JSON/JSONL
            print(f"Using legacy MultiLabelDrumDataset with JSON labels")
        
        events_path = dataset_path / args.events_file
        if not events_path.exists():
            events_path = dataset_path / args.labels_file
        
        print(f"Events file: {events_path}")
        
        full_dataset = MultiLabelDrumDataset(
            data_dir=dataset_path,
            labels_file=events_path,
            num_classes=args.num_classes,
            cache_dir=feature_cache_dir,
        )
        
        full_dataset.print_statistics()
        
        # Split into train/val
        val_size = int(len(full_dataset) * args.val_split)
        train_size = len(full_dataset) - val_size
        train_dataset, val_dataset = random_split(
            full_dataset,
            [train_size, val_size],
            generator=torch.Generator().manual_seed(42)
        )
    
    print(f"Train: {len(train_dataset):,}, Val: {len(val_dataset):,}")
    
    # Create dataloaders with configurable options
    num_workers = args.num_workers
    prefetch_factor = args.prefetch_factor if num_workers > 0 else None
    persistent_workers = args.persistent_workers and num_workers > 0
    pin_memory = args.pin_memory if torch.cuda.is_available() else False
    
    # Class-balanced sampling setup
    train_sampler = None
    shuffle_train = True
    
    if args.balanced_sampling:
        print(f"\n[Balanced Sampling] Computing sample weights (method: {args.balanced_method})...")
        
        # Get the underlying dataset (handle random_split and ConcatDataset wrappers)
        underlying_dataset = train_dataset
        if hasattr(train_dataset, 'dataset'):
            underlying_dataset = train_dataset.dataset
        
        # Handle ConcatDataset - need to combine weights from all sub-datasets
        if hasattr(underlying_dataset, 'datasets'):
            # ConcatDataset of BatchedMultiLabelDataset
            print(f"[Balanced Sampling] ConcatDataset with {len(underlying_dataset.datasets)} sub-datasets")
            all_weights = []
            for sub_ds in underlying_dataset.datasets:
                if hasattr(sub_ds, 'get_sample_weights'):
                    weights = sub_ds.get_sample_weights(method=args.balanced_method)
                    # Skip empty datasets (e.g., MedleyDB with 0 train samples)
                    if len(weights) == 0:
                        continue
                    ds_name = getattr(sub_ds, 'dataset_name', None)
                    if ds_name in dataset_weights:
                        weights = weights * dataset_weights[ds_name]
                        print(f"[Balanced Sampling] Applied dataset weight {dataset_weights[ds_name]:.2f}x to {ds_name}")
                    elif ds_name in acoustic_datasets and args.acoustic_oversample != 1.0:
                        weights = weights * args.acoustic_oversample
                        print(f"[Balanced Sampling] Applied acoustic oversample {args.acoustic_oversample:.2f}x to {ds_name}")
                    all_weights.append(weights)
                else:
                    # Fallback: uniform weights (skip if empty)
                    if len(sub_ds) > 0:
                        all_weights.append(np.ones(len(sub_ds), dtype=np.float64))
            sample_weights = np.concatenate(all_weights)
            
            # Create sampler
            train_sampler = WeightedRandomSampler(
                weights=torch.from_numpy(sample_weights.astype(np.float64)),
                num_samples=len(sample_weights),
                replacement=True,
            )
            shuffle_train = False
            print(f"[Balanced Sampling] Created WeightedRandomSampler with {len(sample_weights):,} samples")
        elif hasattr(underlying_dataset, 'get_sample_weights'):
            sample_weights = underlying_dataset.get_sample_weights(method=args.balanced_method)

            ds_name = getattr(underlying_dataset, 'dataset_name', None)
            if ds_name in dataset_weights:
                sample_weights = sample_weights * dataset_weights[ds_name]
                print(f"[Balanced Sampling] Applied dataset weight {dataset_weights[ds_name]:.2f}x to {ds_name}")
            elif ds_name in acoustic_datasets and args.acoustic_oversample != 1.0:
                sample_weights = sample_weights * args.acoustic_oversample
                print(f"[Balanced Sampling] Applied acoustic oversample {args.acoustic_oversample:.2f}x to {ds_name}")
            
            # If using random_split, need to get weights for subset indices only
            if hasattr(train_dataset, 'indices'):
                sample_weights = sample_weights[train_dataset.indices]
            
            # Print weight statistics
            print(f"[Balanced Sampling] Weight stats: min={sample_weights.min():.3f}, "
                  f"max={sample_weights.max():.3f}, mean={sample_weights.mean():.3f}")
            
            # Show weights for each class
            if hasattr(underlying_dataset, 'get_class_counts') and hasattr(underlying_dataset, 'class_names'):
                counts = underlying_dataset.get_class_counts()
                total = len(underlying_dataset)
                class_weights = total / (counts + 1)
                class_weights = class_weights / class_weights.sum() * len(counts)
                print("[Balanced Sampling] Per-class effective weights:")
                for i, name in enumerate(underlying_dataset.class_names[:underlying_dataset.num_classes]):
                    print(f"  {name:<15} freq={100*counts[i]/total:>5.1f}% weight={class_weights[i]:>5.2f}x")
            
            # Create weighted sampler
            # replacement=True allows sampling same sample multiple times (needed for oversampling)
            train_sampler = WeightedRandomSampler(
                weights=torch.from_numpy(sample_weights.astype(np.float64)),
                num_samples=len(sample_weights),
                replacement=True,
            )
            shuffle_train = False  # Sampler handles sampling, not shuffle
            print(f"[Balanced Sampling] Created WeightedRandomSampler with {len(sample_weights):,} samples")
        else:
            print("[Balanced Sampling] Warning: Dataset doesn't support get_sample_weights(), using regular shuffle")
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=shuffle_train,
        sampler=train_sampler,
        num_workers=num_workers,
        prefetch_factor=prefetch_factor,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
        drop_last=True,  # For stable gradient accumulation
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=num_workers,
        prefetch_factor=prefetch_factor,
        pin_memory=pin_memory,
        persistent_workers=persistent_workers,
    )
    
    print(f"\nDataLoader Configuration:")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Effective batch size: {args.batch_size * args.grad_accum_steps}")
    print(f"  Workers: {num_workers}")
    print(f"  Persistent workers: {persistent_workers}")
    print(f"  Pin memory: {pin_memory}")
    print(f"  Balanced sampling: {args.balanced_sampling}")
    if args.balanced_sampling:
        print(f"  Balanced method: {args.balanced_method}")
    
    # Initialize SpecAugment if enabled
    spec_augment = None
    if args.specaugment != 'none' and HAS_SPECAUGMENT:
        spec_augment = get_specaugment(args.specaugment)
        print(f"  SpecAugment: {args.specaugment}")
    elif args.specaugment != 'none':
        print(f"  SpecAugment: requested but not available (install training.augmentation.specaugment)")
    
    # Create model
    print(f"\nCreating {args.model_version} model...")
    model = create_model(
        model_version=args.model_version,
        num_classes=args.num_classes,
        pretrained_checkpoint=args.pretrained_checkpoint,
        v5_size=args.v5_size,
        drop_path_rate=args.drop_path_rate,
    )
    
    # Memory optimization: channels last
    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)
        print("Using channels-last memory format")
    
    model = model.to(device)
    
    # Enable gradient checkpointing if requested
    if args.gradient_checkpointing:
        if hasattr(model.backbone, 'gradient_checkpointing_enable'):
            model.backbone.gradient_checkpointing_enable()
            print("Gradient checkpointing enabled (native support)")
        elif hasattr(model.backbone, 'set_grad_checkpointing'):
            model.backbone.set_grad_checkpointing(enable=True)
            print("Gradient checkpointing enabled")
        else:
            print("Warning: Gradient checkpointing requested but model doesn't support it")
    
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameters: {num_params:,}")
    
    # Create loss function
    pos_weight = None
    if args.use_pos_weight:
        if hasattr(full_dataset, 'get_pos_weights'):
            pos_weight = full_dataset.get_pos_weights(method="sqrt_inverse").to(device)
        print("Using positive class weights (sqrt_inverse)")
    
    # Get per-class gamma if using recall_boost or ohem loss with per-class weights
    per_class_gamma = None
    if args.loss_type in ('recall_boost', 'ohem'):
        if args.use_per_class_gamma:
            from multilabel.loss import DEFAULT_PER_CLASS_GAMMA
            per_class_gamma = DEFAULT_PER_CLASS_GAMMA
            print(f"Using per-class gamma/weights: {per_class_gamma}")
        if args.loss_type == 'recall_boost':
            print(f"Recall boost weight: {args.recall_boost_weight}")
    
    # Get class counts for cb_focal loss
    class_counts = None
    if args.loss_type == 'cb_focal':
        # Handle various dataset wrappers to get class counts
        if hasattr(train_dataset, 'datasets'):
            # ConcatDataset - sum counts from all sub-datasets
            total_counts = None
            for sub_ds in train_dataset.datasets:
                if hasattr(sub_ds, 'get_class_counts'):
                    counts = sub_ds.get_class_counts()
                    if total_counts is None:
                        total_counts = counts.copy()
                    else:
                        total_counts += counts
            class_counts = total_counts
            if class_counts is not None:
                print(f"[CB-Focal] Class counts from ConcatDataset ({len(train_dataset.datasets)} sources): {class_counts}")
        elif hasattr(train_dataset, 'dataset') and hasattr(train_dataset.dataset, 'get_class_counts'):
            # Subset wrapper
            class_counts = train_dataset.dataset.get_class_counts()
            print(f"[CB-Focal] Class counts from wrapped dataset: {class_counts}")
        elif hasattr(train_dataset, 'get_class_counts'):
            # Direct dataset
            class_counts = train_dataset.get_class_counts()
            print(f"[CB-Focal] Class counts from dataset: {class_counts}")
        
        if class_counts is None:
            raise ValueError("cb_focal loss requires a dataset with get_class_counts() method")
    
    # Parse --class-loss-weight arguments into a tensor
    extra_class_weights = None
    if getattr(args, 'class_loss_weight', None):
        class_name_to_idx = {name: i for i, name in enumerate(DEFAULT_DRUM_COMPONENTS[:args.num_classes])}
        weight_tensor = torch.ones(args.num_classes)
        for entry in args.class_loss_weight:
            if '=' not in entry:
                print(f"Warning: ignoring malformed --class-loss-weight '{entry}' (expected name=weight)")
                continue
            name, val = entry.split('=', 1)
            name = name.strip()
            if name not in class_name_to_idx:
                print(f"Warning: unknown class '{name}' in --class-loss-weight (valid: {list(class_name_to_idx.keys())})")
                continue
            weight_tensor[class_name_to_idx[name]] = float(val)
        extra_class_weights = weight_tensor
        print(f"[Class Loss Weights] Per-class multipliers:")
        for i, name in enumerate(DEFAULT_DRUM_COMPONENTS[:args.num_classes]):
            if weight_tensor[i] != 1.0:
                print(f"  {name}: {weight_tensor[i]:.1f}x")

    criterion = get_multilabel_loss(
        loss_type=args.loss_type,
        pos_weight=pos_weight,
        gamma=args.gamma,
        label_smoothing=args.label_smoothing,
        per_class_gamma=per_class_gamma,
        recall_boost_weight=getattr(args, 'recall_boost_weight', 1.5),
        num_classes=args.num_classes,
        hard_fraction=getattr(args, 'hard_fraction', 0.5),
        hard_weight=getattr(args, 'hard_weight', 3.0),
        class_counts=class_counts,
        cb_beta=getattr(args, 'cb_beta', 0.999),
        extra_class_weights=extra_class_weights,
    )
    # Move criterion to device (important for losses with learnable parameters or buffers like cb_focal)
    criterion = criterion.to(device)
    print(f"Loss function: {args.loss_type}")
    if args.loss_type == 'ohem':
        print(f"  OHEM: hard_fraction={args.hard_fraction}, hard_weight={args.hard_weight}")
        if per_class_gamma:
            print(f"  Per-class weights enabled for weak classes")
    if args.loss_type == 'cb_focal':
        print(f"  CB-Focal: beta={args.cb_beta}, gamma={args.gamma}")
    
    # Create optimizer (with optional SAM wrapper)
    base_optimizer = optim.AdamW
    if args.use_sam and HAS_SAM:
        optimizer = SAM(
            model.parameters(),
            base_optimizer,
            lr=args.lr,
            weight_decay=args.weight_decay,
            rho=args.sam_rho,
            adaptive=args.sam_adaptive,
        )
        print(f"Using SAM optimizer (rho={args.sam_rho}, adaptive={args.sam_adaptive})")
    else:
        optimizer = optim.AdamW(
            model.parameters(),
            lr=args.lr,
            weight_decay=args.weight_decay,
        )
        if args.use_sam and not HAS_SAM:
            print("Warning: SAM requested but not available")
    
    # Learning rate scheduler
    min_lr = args.min_lr if args.min_lr else args.lr * 0.01
    if args.scheduler == 'cosine':
        scheduler = optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=args.epochs,
            eta_min=min_lr,
        )
    elif args.scheduler == 'cosine_warm_restarts':
        scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer,
            T_0=10,
            T_mult=2,
            eta_min=min_lr,
        )
    else:  # plateau
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode='max',
            factor=0.5,
            patience=5,
            min_lr=min_lr,
        )
    print(f"LR scheduler: {args.scheduler}")
    
    # EMA model
    ema_model = None
    if args.use_ema and HAS_EMA:
        ema_model = ModelEMA(model, decay=args.ema_decay)
        print(f"Using EMA (decay={args.ema_decay})")
    elif args.use_ema:
        print("Warning: EMA requested but not available")
    
    # SWA model
    swa_model = None
    swa_scheduler = None
    swa_start_epoch = int(args.epochs * args.swa_start) if args.use_swa else args.epochs + 1
    if args.use_swa and HAS_SWA:
        swa_model = AveragedModel(model)
        swa_lr = args.swa_lr if args.swa_lr else args.lr * 0.1
        swa_scheduler = SWALR(optimizer, swa_lr=swa_lr)
        print(f"Using SWA (start={swa_start_epoch}, lr={swa_lr})")
    elif args.use_swa:
        print("Warning: SWA requested but not available")
    
    # Mixed precision
    scaler = GradScaler() if use_amp else None
    
    # Weights & Biases
    if HAS_WANDB and args.wandb_project:
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_run_name,
            config=vars(args),
        )
        wandb.watch(model)
    
    # =========================================================================
    # CHECKPOINT/RESUME SUPPORT WITH INTERRUPT HANDLING
    # =========================================================================
    
    def _atomic_torch_save(obj: Any, path: Path) -> None:
        """Save atomically to prevent corruption from Ctrl+C or OOM."""
        temp_path = path.parent / f".{path.name}.tmp"
        try:
            with open(temp_path, 'wb') as f:
                torch.save(obj, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def save_checkpoint(epoch: int, val_metrics, reason: str = None, batch_idx: int = None, total_batches: int = None) -> None:
        """Save full resumable checkpoint with RNG state for deterministic resume."""
        is_mid_epoch = batch_idx is not None
        
        checkpoint = {
            'epoch': epoch,
            'batch_idx': batch_idx,
            'total_batches': total_batches,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict() if hasattr(scheduler, 'state_dict') else None,
            'scaler_state_dict': scaler.state_dict() if scaler else None,
            'ema_state_dict': ema_model.state_dict() if ema_model else None,
            'swa_state_dict': swa_model.state_dict() if swa_model else None,
            'val_metrics': val_metrics.to_dict() if val_metrics else None,
            'best_val_f1': best_val_f1,
            'best_epoch': best_epoch,
            'args': vars(args),
            'reason': reason,
            # Cumulative training progress (prevents epoch inflation from repeated restarts)
            'cumulative_batches_trained': int(cumulative_batches_trained),
            'batches_per_epoch': int(batches_per_epoch) if batches_per_epoch > 0 else total_batches,
            # RNG state for deterministic resume
            'rng': {
                'python': random.getstate(),
                'numpy': np.random.get_state(),
                'torch': torch.get_rng_state(),
                'torch_cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            },
        }
        _atomic_torch_save(checkpoint, output_dir / 'latest_checkpoint.pt')

        # Save per-epoch checkpoints for rollback (keep last 3)
        if not is_mid_epoch:
            epoch_ckpt_path = output_dir / f"checkpoint_epoch_{epoch:04d}.pt"
            _atomic_torch_save(checkpoint, epoch_ckpt_path)
            MAX_KEEP = 3
            existing = sorted(output_dir.glob("checkpoint_epoch_*.pt"))
            for old_ckpt in existing[:-MAX_KEEP]:
                old_ckpt.unlink()

        if is_mid_epoch:
            pct = 100 * batch_idx / total_batches if total_batches else 0
            tqdm.write(f"\n[CHECKPOINT] Mid-epoch checkpoint SAVED (epoch {epoch}, batch {batch_idx:,}/{total_batches:,}, {pct:.0f}%)")
            tqdm.write(f"   -> latest_checkpoint.pt")
            # Clean up CUDA memory after checkpoint to reduce OOM risk
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        elif reason:
            print(f"✓ Checkpoint saved ({reason}) at epoch {epoch}")
    
    def save_best_checkpoint(epoch: int, val_f1: float) -> Path:
        """Save a FULL resumable checkpoint when we achieve best validation F1.
        
        This is separate from best_multilabel_model.pt (weights only) - this saves
        the complete training state so we can resume from the best point if needed.
        """
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'scheduler_state_dict': scheduler.state_dict() if hasattr(scheduler, 'state_dict') else None,
            'scaler_state_dict': scaler.state_dict() if scaler else None,
            'ema_state_dict': ema_model.state_dict() if ema_model else None,
            'best_val_f1': val_f1,
            'best_epoch': epoch,
            'args': vars(args),
            'batch_idx': None,
            'total_batches': None,
            'rng': {
                'python': random.getstate(),
                'numpy': np.random.get_state(),
                'torch': torch.get_rng_state(),
                'torch_cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            },
        }
        
        best_checkpoint_path = output_dir / "best_checkpoint.pt"
        _atomic_torch_save(checkpoint, best_checkpoint_path)
        print(f"  ✓ Saved best FULL checkpoint (F1: {val_f1:.4f}) - can resume from here")
        return best_checkpoint_path
    
    # Initialize best tracking
    best_val_f1 = 0.0
    best_epoch = 0
    prev_val_loss = None  # Track epoch-over-epoch val loss for spike detection
    start_epoch = 1
    
    # Track ACTUAL training progress across all resumes
    # This prevents epoch inflation from repeated mid-epoch restarts
    cumulative_batches_trained: int = 0
    batches_per_epoch: int = len(train_loader)  # Will be used for progress tracking
    
    # Resume from checkpoint if specified or auto-resume
    resume_path = None
    resume_batch_idx = 0  # For mid-epoch resume
    if args.resume:
        resume_path = Path(args.resume)
    elif (output_dir / 'latest_checkpoint.pt').exists() and not args.pretrained_checkpoint:
        resume_path = output_dir / 'latest_checkpoint.pt'
        print(f"Found existing checkpoint, auto-resuming...")
    
    if resume_path and resume_path.exists():
        print(f"Resuming from {resume_path}...")
        # weights_only=False needed for checkpoints containing numpy RNG state (PyTorch 2.6+)
        ckpt = torch.load(resume_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt['model_state_dict'])
        optimizer.load_state_dict(ckpt['optimizer_state_dict'])
        if not args.reset_scheduler and ckpt.get('scheduler_state_dict'):
            try:
                scheduler.load_state_dict(ckpt['scheduler_state_dict'])
            except Exception as e:
                print(f"  Warning: Could not load scheduler state: {e}")
        if scaler and ckpt.get('scaler_state_dict'):
            scaler.load_state_dict(ckpt['scaler_state_dict'])
        if ema_model and ckpt.get('ema_state_dict'):
            ema_model.load_state_dict(ckpt['ema_state_dict'])
        if swa_model and ckpt.get('swa_state_dict'):
            swa_model.load_state_dict(ckpt['swa_state_dict'])
        
        # Check for mid-epoch checkpoint
        ckpt_batch_idx = ckpt.get('batch_idx')
        ckpt_total_batches = ckpt.get('total_batches')
        
        if ckpt_batch_idx is not None and ckpt_total_batches is not None and ckpt_batch_idx < ckpt_total_batches - 1:
            # Mid-epoch checkpoint - resume same epoch, skip to batch
            start_epoch = ckpt['epoch']
            resume_batch_idx = ckpt_batch_idx + 1  # Start from next batch
            print(f"  Mid-epoch resume: epoch {start_epoch}, batch {resume_batch_idx:,}/{ckpt_total_batches:,}")
        else:
            # End-of-epoch checkpoint - start next epoch
            start_epoch = ckpt['epoch'] + 1
        
        best_val_f1 = ckpt.get('best_val_f1', 0.0)
        best_epoch = ckpt.get('best_epoch', 0)
        
        # Restore cumulative training progress tracking
        ckpt_cumulative_batches = ckpt.get('cumulative_batches_trained', 0)
        ckpt_batches_per_epoch = ckpt.get('batches_per_epoch', 0)
        if ckpt_cumulative_batches > 0:
            cumulative_batches_trained = int(ckpt_cumulative_batches)
            if ckpt_batches_per_epoch > 0:
                actual_epochs = cumulative_batches_trained / ckpt_batches_per_epoch
                print(f"  [PROGRESS] Cumulative batches trained: {cumulative_batches_trained:,} (~{actual_epochs:.1f} full epochs)")
        
        # Restore RNG state if present (enables deterministic resume)
        rng = ckpt.get('rng')
        if isinstance(rng, dict):
            try:
                if rng.get('python') is not None:
                    random.setstate(rng['python'])
                if rng.get('numpy') is not None:
                    np.random.set_state(rng['numpy'])
                if rng.get('torch') is not None:
                    rng_tensor = rng['torch']
                    # Must be a CPU ByteTensor — checkpoint loaded with map_location=cuda
                    # moves RNG tensors to GPU, which torch.set_rng_state rejects
                    if isinstance(rng_tensor, torch.Tensor):
                        rng_tensor = rng_tensor.cpu().byte()
                    else:
                        rng_tensor = torch.ByteTensor(rng_tensor)
                    torch.set_rng_state(rng_tensor)
                if torch.cuda.is_available() and rng.get('torch_cuda') is not None:
                    cuda_states = rng['torch_cuda']
                    # CUDA RNG states also need to be CPU ByteTensors
                    for i, state in enumerate(cuda_states):
                        if isinstance(state, torch.Tensor):
                            cuda_states[i] = state.cpu().byte()
                        else:
                            cuda_states[i] = torch.ByteTensor(state)
                    torch.cuda.set_rng_state_all(cuda_states)
                print(f"  RNG state restored for deterministic resume")
            except Exception as e:
                print(f"  [WARN] Failed to restore RNG state: {e}")
                print(f"  [WARN] Training will continue with new random state — data order may differ")
        
        print(f"  Resuming from epoch {start_epoch}, best F1: {best_val_f1:.4f}")

        # POST-RESUME SANITY CHECK: verify model isn't corrupted
        print("\n[SANITY CHECK] Running post-resume validation...")
        eval_model = ema_model.ema_model if ema_model else model
        eval_model.eval()
        sanity_loss, sanity_metrics = evaluate(
            eval_model, val_loader, criterion, device,
            class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
        )
        print(f"  Post-resume val loss: {sanity_loss:.4f}, Micro-F1: {sanity_metrics.micro_f1:.4f}")

        if best_val_f1 > 0.5:
            f1_degradation = (best_val_f1 - sanity_metrics.micro_f1) / best_val_f1
            if f1_degradation > 0.10:
                print(f"\n{'='*60}")
                print(f"[CRITICAL] POST-RESUME REGRESSION DETECTED!")
                print(f"  Best known F1: {best_val_f1:.4f}")
                print(f"  Current F1:    {sanity_metrics.micro_f1:.4f}")
                print(f"  Degradation:   {f1_degradation*100:.1f}%")
                print(f"{'='*60}")
                print(f"\nThis checkpoint may be corrupted.")
                print(f"RECOMMENDED: Resume from best_checkpoint.pt instead:")
                print(f"  --resume {output_dir / 'best_checkpoint.pt'}")
                try:
                    response = input("Continue training anyway? [y/N]: ").strip().lower()
                except EOFError:
                    response = 'n'
                if response != 'y':
                    print("Aborting. Resume from a known-good checkpoint.")
                    return
    
    # Signal handler for graceful shutdown
    _shutdown_requested = False
    
    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        print(f"\n⚠️  Received {sig_name} - will save checkpoint and exit...")
        _shutdown_requested = True
    
    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)
    
    # Training loop
    last_completed_epoch = start_epoch - 1
    
    print(f"\nStarting training from epoch {start_epoch} to {args.epochs}...")
    print(f"  Grad accumulation steps: {args.grad_accum_steps}")
    if args.warmup_epochs > 0:
        print(f"  Warmup epochs: {args.warmup_epochs}")
    if args.grad_clip_norm:
        print(f"  Gradient clipping: {args.grad_clip_norm}")
    
    try:
        for epoch in range(start_epoch, args.epochs + 1):
            # === MEMORY CLEANUP BETWEEN EPOCHS ===
            # Prevent CUDA OOM from memory fragmentation on long runs
            if epoch > start_epoch and torch.cuda.is_available():
                import gc
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            if _shutdown_requested:
                print(f"\n🛑 Shutdown requested before epoch {epoch}")
                save_checkpoint(last_completed_epoch, None, "shutdown_signal")
                break
            
            # Calculate actual training progress
            actual_full_epochs = cumulative_batches_trained / max(batches_per_epoch, 1)
            print(f"\nEpoch {epoch}/{args.epochs} (actual training: ~{actual_full_epochs:.1f} full epochs)")
            
            epoch_start = time.time()
            
            # === TRAINING EPOCH ===
            model.train()
            total_loss = 0.0
            tracker = MultiLabelMetricTracker()
            optimizer.zero_grad()
            
            # Warmup LR
            warmup_lr = None
            if epoch <= args.warmup_epochs and args.warmup_epochs > 0:
                warmup_lr = args.lr * (epoch / args.warmup_epochs)
                for param_group in optimizer.param_groups:
                    param_group['lr'] = warmup_lr
            
            total_batches = len(train_loader)
            
            # Mid-epoch resume: restart the full epoch with proper DataLoader
            # NOTE: We intentionally DO NOT skip batches or create a Subset.
            # The old approach (Subset + shuffle=False) caused catastrophic forgetting
            # because ConcatDataset sequential ordering exposed the model to millions
            # of samples from a single dataset (e.g., 8.77M EGMD with zero china/splash)
            # without the WeightedRandomSampler's class balancing.
            # Re-training ~14% of an epoch is vastly preferable to model collapse.
            skip_batches = 0
            epoch_train_loader = train_loader
            if resume_batch_idx > 0 and epoch == start_epoch:
                print(f"  Mid-epoch checkpoint detected (batch {resume_batch_idx:,}/{total_batches:,}).")
                print(f"  Restarting full epoch with class-balanced sampling (weights preserved from checkpoint).")
                resume_batch_idx = 0  # Only handle once
            
            pbar = tqdm(
                enumerate(epoch_train_loader, start=skip_batches),
                desc=f"Epoch {epoch}",
                leave=False,
                initial=skip_batches,
                total=total_batches,
                dynamic_ncols=False,
            )
            
            # Track last batch for shutdown checkpoint
            last_batch_idx = skip_batches
            
            for batch_idx, (features, labels) in pbar:
                last_batch_idx = batch_idx  # Update for shutdown checkpoint
                if _shutdown_requested:
                    break
                
                features = features.to(device, non_blocking=True)
                labels = labels.to(device, non_blocking=True)
                
                # Channels last memory format
                if args.channels_last:
                    features = features.to(memory_format=torch.channels_last)
                
                # SpecAugment
                if spec_augment is not None:
                    features = spec_augment(features)
                
                # Forward pass with AMP
                if use_amp and scaler is not None:
                    with autocast(device_type='cuda', dtype=amp_dtype):
                        logits = model(features)
                        loss = criterion(logits, labels)
                        loss = loss / args.grad_accum_steps  # Scale for accumulation
                    
                    scaler.scale(loss).backward()
                    
                    # Optimizer step with gradient accumulation
                    if (batch_idx + 1) % args.grad_accum_steps == 0:
                        if args.grad_clip_norm:
                            scaler.unscale_(optimizer)
                            clip_grad_norm_(model.parameters(), args.grad_clip_norm)
                        
                        if args.use_sam and HAS_SAM:
                            # SAM first step
                            scaler.step(optimizer)
                            scaler.update()
                            optimizer.first_step(zero_grad=True)
                            
                            # SAM second step
                            with autocast(device_type='cuda', dtype=amp_dtype):
                                logits2 = model(features)
                                loss2 = criterion(logits2, labels)
                            scaler.scale(loss2).backward()
                            optimizer.second_step(zero_grad=True)
                        else:
                            scaler.step(optimizer)
                            scaler.update()
                            optimizer.zero_grad()
                else:
                    logits = model(features)
                    loss = criterion(logits, labels)
                    loss = loss / args.grad_accum_steps
                    loss.backward()
                    
                    if (batch_idx + 1) % args.grad_accum_steps == 0:
                        if args.grad_clip_norm:
                            clip_grad_norm_(model.parameters(), args.grad_clip_norm)
                        
                        if args.use_sam and HAS_SAM:
                            optimizer.first_step(zero_grad=True)
                            logits2 = model(features)
                            loss2 = criterion(logits2, labels)
                            loss2.backward()
                            optimizer.second_step(zero_grad=True)
                        else:
                            optimizer.step()
                            optimizer.zero_grad()
                
                # Update EMA
                if ema_model is not None:
                    ema_model.update(model)
                
                total_loss += loss.item() * args.grad_accum_steps
                tracker.update(logits.detach(), labels)
                
                # Show running metrics in progress bar (like train_classifier.py)
                # Compute simple per-label accuracy (more intuitive than subset accuracy)
                with torch.no_grad():
                    pred_binary = (torch.sigmoid(logits) >= 0.5).float()
                    correct_labels = (pred_binary == labels).sum().item()
                    total_labels = labels.numel()
                    # Track running totals
                    if not hasattr(pbar, '_correct'):
                        pbar._correct = 0
                        pbar._total = 0
                    pbar._correct += correct_labels
                    pbar._total += total_labels
                    cur_acc = 100.0 * pbar._correct / max(pbar._total, 1)
                
                pbar.set_postfix(
                    loss=f"{loss.item() * args.grad_accum_steps:.4f}",
                    acc=f"{cur_acc:.2f}%"
                )
                
                # Mid-epoch checkpoint
                if args.checkpoint_every_batches > 0 and (batch_idx + 1) % args.checkpoint_every_batches == 0:
                    save_checkpoint(epoch, None, f"batch_{batch_idx + 1}", batch_idx=batch_idx, total_batches=total_batches)
            
            train_loss = total_loss / len(train_loader)
            train_metrics = tracker.compute()
            train_f1 = train_metrics.micro_f1
            
            # Update cumulative batches trained
            # For mid-epoch resume, we only trained (total - resumed_from) batches
            if epoch == start_epoch and skip_batches > 0:
                batches_this_epoch = total_batches - skip_batches
            else:
                batches_this_epoch = total_batches
            cumulative_batches_trained += batches_this_epoch
            
            if _shutdown_requested:
                print(f"\n🛑 Shutdown during epoch {epoch} at batch {last_batch_idx:,}/{total_batches:,}")
                save_checkpoint(epoch, None, "shutdown_mid_epoch", batch_idx=last_batch_idx, total_batches=total_batches)
                print(f"✓ Resume with checkpoint at: {output_dir / 'latest_checkpoint.pt'}")
                break
            
            # === VALIDATION ===
            eval_model = ema_model.ema_model if ema_model else model
            
            # Use evaluate_by_source for per-domain metrics if we have a ConcatDataset
            from torch.utils.data import ConcatDataset
            val_underlying = val_dataset
            if hasattr(val_dataset, 'dataset'):
                val_underlying = val_dataset.dataset
            
            if isinstance(val_underlying, ConcatDataset) or hasattr(val_underlying, 'dataset_name'):
                val_loss, val_metrics, source_metrics = evaluate_by_source(
                    eval_model, val_underlying, criterion, device,
                    batch_size=args.batch_size,
                    num_workers=args.num_workers,
                    class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
                )
            else:
                val_loss, val_metrics = evaluate(
                    eval_model, val_loader, criterion, device,
                    class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
                )
                source_metrics = {}
            
            # Update SWA model
            if swa_model is not None and epoch >= swa_start_epoch:
                swa_model.update_parameters(model)
                swa_scheduler.step()
            
            # Update scheduler (after warmup)
            if epoch > args.warmup_epochs:
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_metrics.micro_f1)
                elif swa_model is None or epoch < swa_start_epoch:
                    scheduler.step()
        
            epoch_time = time.time() - epoch_start
            current_lr = optimizer.param_groups[0]['lr']
            
            # Compute per-label accuracy for display (more intuitive than F1)
            train_acc = train_metrics.per_label_accuracy * 100 if hasattr(train_metrics, 'per_label_accuracy') else train_f1 * 100
            val_acc = val_metrics.per_label_accuracy * 100 if hasattr(val_metrics, 'per_label_accuracy') else val_metrics.micro_f1 * 100
            
            # Print progress with both micro and macro F1
            print(
                f"Epoch {epoch:3d}/{args.epochs} | "
                f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.2f}% | "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.2f}%, "
                f"Micro-F1: {val_metrics.micro_f1:.4f}, Macro-F1: {val_metrics.macro_f1:.4f} | "
                f"LR: {current_lr:.2e} | "
                f"Time: {epoch_time:.1f}s"
            )
            
            # Print per-source metrics if available
            if source_metrics:
                source_parts = []
                for src_name in ['acoustic', 'electronic', 'synthetic']:
                    if src_name in source_metrics:
                        sm = source_metrics[src_name]
                        source_parts.append(f"{src_name[:4].upper()}: F1={sm['micro_f1']:.3f} ({sm['count']:,})")
                if source_parts:
                    print(f"  └─ By source: {' | '.join(source_parts)}")

                # Print clean vs demucs domain gap
                if 'clean' in source_metrics and 'demucs' in source_metrics:
                    clean_m = source_metrics['clean']
                    demucs_m = source_metrics['demucs']
                    gap = clean_m['micro_f1'] - demucs_m['micro_f1']
                    print(f"  └─ Domain gap: CLEAN F1={clean_m['micro_f1']:.3f} ({clean_m['count']:,}) | "
                          f"DEMUCS F1={demucs_m['micro_f1']:.3f} ({demucs_m['count']:,}) | "
                          f"Gap={gap:+.3f}")
                elif 'demucs' in source_metrics:
                    demucs_m = source_metrics['demucs']
                    print(f"  └─ DEMUCS F1={demucs_m['micro_f1']:.3f} ({demucs_m['count']:,})")

                # Print per-individual-Demucs-dataset breakdown
                if 'per_dataset' in source_metrics:
                    per_ds = source_metrics['per_dataset']
                    if per_ds:
                        parts = []
                        for ds_name in sorted(per_ds.keys()):
                            dm = per_ds[ds_name]
                            # Shorten names for readability
                            short = ds_name.replace('_demucs', '').replace('2100', '')
                            parts.append(f"{short}: {dm['micro_f1']:.3f} ({dm['count']:,})")
                        print(f"  └─ Demucs by source: {' | '.join(parts)}")

            # Print per-class metrics table (combined)
            class_names = DEFAULT_DRUM_COMPONENTS[:args.num_classes]
            print(f"\n{'Class':<15} {'Prec':>7} {'Recall':>7} {'F1':>7}")
            print("-" * 38)
            for name in class_names:
                prec = val_metrics.per_class_precision.get(name, 0)
                rec = val_metrics.per_class_recall.get(name, 0)
                f1 = val_metrics.per_class_f1.get(name, 0)
                # Mark weak classes
                marker = " <<<" if f1 < 0.85 else ""
                print(f"{name:<15} {prec:>7.3f} {rec:>7.3f} {f1:>7.3f}{marker}")
            print()

            # Print per-class Demucs F1 breakdown (shows exactly where the domain gap hurts)
            if source_metrics and 'demucs' in source_metrics and 'clean' in source_metrics:
                demucs_f1 = source_metrics['demucs'].get('per_class_f1', {})
                clean_f1 = source_metrics['clean'].get('per_class_f1', {})
                if demucs_f1:
                    print(f"{'Class':<15} {'Clean F1':>9} {'Demucs F1':>10} {'Gap':>7}")
                    print("-" * 43)
                    for name in DEFAULT_DRUM_COMPONENTS[:args.num_classes]:
                        cf1 = clean_f1.get(name, 0)
                        df1 = demucs_f1.get(name, 0)
                        gap = cf1 - df1
                        marker = " <<<" if gap > 0.15 else ""
                        print(f"{name:<15} {cf1:>9.3f} {df1:>10.3f} {gap:>+7.3f}{marker}")
                    print()

            # Val loss spike detection (epoch-over-epoch)
            if prev_val_loss is not None and prev_val_loss > 0:
                loss_ratio = val_loss / prev_val_loss
                if loss_ratio > 3.0:
                    print(f"\n{'='*60}")
                    print(f"[CRITICAL] VAL LOSS SPIKE: {prev_val_loss:.4f} -> {val_loss:.4f} ({loss_ratio:.1f}x increase)")
                    print(f"  This may indicate checkpoint corruption or catastrophic forgetting.")
                    print(f"  Consider rolling back to a previous checkpoint.")
                    print(f"{'='*60}")
                elif loss_ratio > 1.5:
                    print(f"  [WARN] Val loss increased {loss_ratio:.1f}x: {prev_val_loss:.4f} -> {val_loss:.4f}")
            prev_val_loss = val_loss

            # Log to wandb
            if HAS_WANDB and args.wandb_project:
                log_dict = {
                    "epoch": epoch,
                    "train/loss": train_loss,
                    "train/micro_f1": train_f1,
                    "val/loss": val_loss,
                    "val/micro_f1": val_metrics.micro_f1,
                    "val/macro_f1": val_metrics.macro_f1,
                    "val/hamming_loss": val_metrics.hamming_loss,
                    "val/subset_accuracy": val_metrics.subset_accuracy,
                    "lr": current_lr,
                }
                # Add per-class F1
                for name, f1 in val_metrics.per_class_f1.items():
                    log_dict[f"val/f1_{name}"] = f1
                wandb.log(log_dict)
            
            # Save best model (use EMA model if available)
            # First check for class collapse — prevent saving models with dead classes
            collapsed_classes = []
            if best_val_f1 > 0.5:  # Only after model has learned
                class_names = DEFAULT_DRUM_COMPONENTS[:args.num_classes]
                for name in class_names:
                    f1 = val_metrics.per_class_f1.get(name, 0)
                    if f1 < 0.01:
                        collapsed_classes.append(name)
                if collapsed_classes:
                    print(f"\n{'='*60}")
                    print(f"[CRITICAL] CLASS COLLAPSE: {len(collapsed_classes)} classes at F1 < 0.01:")
                    for cls in collapsed_classes:
                        f1_val = val_metrics.per_class_f1.get(cls, 0)
                        rec = val_metrics.per_class_recall.get(cls, 0)
                        print(f"  - {cls}: F1={f1_val:.4f}, Recall={rec:.4f}")
                    print(f"{'='*60}")

            if val_metrics.micro_f1 > best_val_f1 and not collapsed_classes:
                best_val_f1 = val_metrics.micro_f1
                best_epoch = epoch
                
                # Save the EMA model if available, otherwise the regular model
                save_model = ema_model.ema_model if ema_model else model
                checkpoint = {
                    'epoch': epoch,
                    'model_state_dict': save_model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'val_metrics': val_metrics.to_dict(),
                    'args': vars(args),
                }
                _atomic_torch_save(checkpoint, output_dir / 'best_multilabel_model.pt')
                print(f"  → New best model saved (F1: {best_val_f1:.4f})")
                
                # Save FULL resumable checkpoint at best point (like train_classifier.py)
                save_best_checkpoint(epoch, val_metrics.micro_f1)
                
                # Also save EMA model separately if enabled
                if ema_model is not None:
                    ema_path = output_dir / 'best_multilabel_model_ema.pt'
                    _atomic_torch_save({'model_state_dict': ema_model.ema_model.state_dict()}, ema_path)
                    print(f"  ✓ Saved best EMA model")
            
            # Save periodic checkpoint (resumable)
            if args.checkpoint_every > 0 and epoch % args.checkpoint_every == 0:
                save_checkpoint(epoch, val_metrics, reason=None)
            last_completed_epoch = epoch
            
            if _shutdown_requested:
                print(f"\n🛑 Clean shutdown after epoch {epoch}")
                print(f"✓ Resume with: {output_dir / 'latest_checkpoint.pt'}")
                break
        
        # === POST-TRAINING ===
        if not _shutdown_requested:
            # Update batch normalization for SWA model
            if swa_model is not None:
                print("\nUpdating SWA batch normalization statistics...")
                torch.optim.swa_utils.update_bn(train_loader, swa_model, device=device)
                
                # Evaluate SWA model
                swa_loss, swa_metrics = evaluate(
                    swa_model, val_loader, criterion, device,
                    class_names=DEFAULT_DRUM_COMPONENTS[:args.num_classes],
                )
                print(f"SWA Model - Val Loss: {swa_loss:.4f}, F1: {swa_metrics.micro_f1:.4f}")
                
                # Save SWA model if it's better
                if swa_metrics.micro_f1 > best_val_f1:
                    best_val_f1 = swa_metrics.micro_f1
                    checkpoint = {
                        'epoch': args.epochs,
                        'model_state_dict': swa_model.module.state_dict(),
                        'val_metrics': swa_metrics.to_dict(),
                        'args': vars(args),
                        'model_type': 'swa',
                    }
                    _atomic_torch_save(checkpoint, output_dir / 'best_multilabel_model.pt')
                    print(f"  → SWA model is best! Saved (F1: {best_val_f1:.4f})")
            
            # Final summary
            print(f"\n{'='*60}")
            print("Training complete!")
            print(f"Best validation F1: {best_val_f1:.4f} at epoch {best_epoch}")
            print(f"Best model saved to: {output_dir / 'best_multilabel_model.pt'}")
    
    except KeyboardInterrupt:
        print(f"\n🛑 Training interrupted (Ctrl+C). Saving checkpoint...")
        save_checkpoint(last_completed_epoch, None, "keyboard_interrupt")
        print(f"✓ Checkpoint saved. Resume with: {output_dir / 'latest_checkpoint.pt'}")
        print("Exiting gracefully (checkpoint is safe).")
        return
    
    # Skip post-training steps if shutdown was requested
    if _shutdown_requested:
        print("\nShutdown requested - skipping post-training steps.")
        print(f"Resume with: {output_dir / 'latest_checkpoint.pt'}")
        if HAS_WANDB and args.wandb_project:
            wandb.finish()
        return
    
    # Find optimal thresholds on validation set
    print("\nFinding optimal classification thresholds...")
    model.eval()
    all_logits = []
    all_labels = []
    
    with torch.no_grad():
        for features, labels in val_loader:
            logits = model(features.to(device))
            all_logits.append(logits.cpu())
            all_labels.append(labels.cpu())
    
    logits = torch.cat(all_logits, dim=0)
    labels = torch.cat(all_labels, dim=0)
    
    best_threshold, per_class_thresholds = find_optimal_thresholds(logits, labels)
    print(f"Optimal global threshold: {best_threshold:.2f}")
    
    # Save thresholds
    thresholds_file = output_dir / 'optimal_thresholds.json'
    with open(thresholds_file, 'w') as f:
        json.dump({
            'global': best_threshold,
            'per_class': per_class_thresholds,
        }, f, indent=2)
    print(f"Thresholds saved to: {thresholds_file}")
    
    if HAS_WANDB and args.wandb_project:
        wandb.finish()


if __name__ == '__main__':
    main()
