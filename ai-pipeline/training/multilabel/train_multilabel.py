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
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.amp import GradScaler, autocast
from torch.utils.data import DataLoader, random_split
from tqdm import tqdm

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multilabel.dataset import MultiLabelDrumDataset
from multilabel.loss import get_multilabel_loss, MultiLabelLoss, FocalBCELoss
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
        checkpoint = torch.load(pretrained_checkpoint, map_location='cpu')
        
        # Handle different checkpoint formats
        if 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
        elif 'state_dict' in checkpoint:
            state_dict = checkpoint['state_dict']
        else:
            state_dict = checkpoint
        
        # Load weights (may have some mismatches for classifier head)
        missing, unexpected = backbone.load_state_dict(state_dict, strict=False)
        if missing:
            print(f"Missing keys (expected for multi-label adaptation): {missing}")
        if unexpected:
            print(f"Unexpected keys: {unexpected}")
        
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
    
    pbar = tqdm(dataloader, desc="Training", leave=False)
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
    
    for features, labels in tqdm(dataloader, desc="Evaluating", leave=False):
        features = features.to(device)
        labels = labels.to(device)
        
        logits = model(features)
        loss = criterion(logits, labels)
        
        total_loss += loss.item()
        all_logits.append(logits.cpu())
        all_labels.append(labels.cpu())
    
    avg_loss = total_loss / len(dataloader)
    
    # Compute metrics
    logits = torch.cat(all_logits, dim=0)
    labels = torch.cat(all_labels, dim=0)
    metrics = compute_all_metrics(logits, labels, class_names=class_names)
    
    return avg_loss, metrics


def main():
    parser = argparse.ArgumentParser(
        description="Train multi-label drum classifier"
    )
    
    # Data
    parser.add_argument('--dataset', type=str, required=True,
                        help='Path to dataset directory')
    parser.add_argument('--labels-file', type=str, default='labels.json',
                        help='Labels file name (relative to dataset)')
    parser.add_argument('--cache-dir', type=str, default=None,
                        help='Feature cache directory')
    
    # Model
    parser.add_argument('--model-version', type=str, default='v5',
                        choices=['v1', 'v2', 'v4', 'v5'],
                        help='Model architecture version (v5 recommended)')
    parser.add_argument('--v5-size', type=str, default='medium',
                        choices=['small', 'medium', 'large'],
                        help='V5 model size preset')
    parser.add_argument('--drop-path-rate', type=float, default=0.1,
                        help='Drop path rate for V5 model')
    parser.add_argument('--num-classes', type=int, default=21,
                        help='Number of drum classes')
    parser.add_argument('--pretrained-checkpoint', type=str, default=None,
                        help='Path to pretrained single-label checkpoint (e.g., from v5-full)')
    
    # Loss
    parser.add_argument('--loss-type', type=str, default='focal',
                        choices=['bce', 'focal', 'asymmetric'],
                        help='Loss function type')
    parser.add_argument('--gamma', type=float, default=2.0,
                        help='Focal loss gamma parameter')
    parser.add_argument('--label-smoothing', type=float, default=0.05,
                        help='Label smoothing factor')
    parser.add_argument('--use-pos-weight', action='store_true',
                        help='Use positive class weighting')
    
    # Training
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-4,
                        help='Learning rate')
    parser.add_argument('--weight-decay', type=float, default=1e-4,
                        help='Weight decay')
    parser.add_argument('--val-split', type=float, default=0.1,
                        help='Validation split ratio')
    parser.add_argument('--use-amp', action='store_true',
                        help='Use automatic mixed precision')
    
    # Output
    parser.add_argument('--output-dir', type=str, default='./checkpoints',
                        help='Directory for saving checkpoints')
    parser.add_argument('--wandb-project', type=str, default=None,
                        help='Weights & Biases project name')
    parser.add_argument('--wandb-run-name', type=str, default=None,
                        help='Weights & Biases run name')
    
    args = parser.parse_args()
    
    # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load dataset
    print(f"\nLoading dataset from {args.dataset}...")
    dataset_path = Path(args.dataset)
    labels_path = dataset_path / args.labels_file
    
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    
    full_dataset = MultiLabelDrumDataset(
        data_dir=dataset_path,
        labels_file=labels_path,
        num_classes=args.num_classes,
        cache_dir=cache_dir,
    )
    
    # Print statistics
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
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True,
    )
    
    # Create model
    print(f"\nCreating {args.model_version} model...")
    model = create_model(
        model_version=args.model_version,
        num_classes=args.num_classes,
        pretrained_checkpoint=args.pretrained_checkpoint,
        v5_size=args.v5_size,
        drop_path_rate=args.drop_path_rate,
    )
    model = model.to(device)
    
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameters: {num_params:,}")
    
    # Create loss function
    pos_weight = None
    if args.use_pos_weight:
        pos_weight = full_dataset.get_pos_weights(method="sqrt_inverse").to(device)
        print(f"Using positive class weights (sqrt_inverse)")
    
    criterion = get_multilabel_loss(
        loss_type=args.loss_type,
        pos_weight=pos_weight,
        gamma=args.gamma,
        label_smoothing=args.label_smoothing,
    )
    print(f"Loss function: {args.loss_type}")
    
    # Create optimizer
    optimizer = optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    
    # Learning rate scheduler
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=args.lr * 0.01,
    )
    
    # Mixed precision
    scaler = GradScaler() if args.use_amp else None
    
    # Weights & Biases
    if HAS_WANDB and args.wandb_project:
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_run_name,
            config=vars(args),
        )
        wandb.watch(model)
    
    # Training loop
    best_val_f1 = 0.0
    best_epoch = 0
    
    print(f"\nStarting training for {args.epochs} epochs...")
    
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        
        # Train
        train_loss, train_f1 = train_epoch(
            model, train_loader, criterion, optimizer, device,
            scaler=scaler, use_amp=args.use_amp,
        )
        
        # Evaluate
        val_loss, val_metrics = evaluate(
            model, val_loader, criterion, device,
            class_names=full_dataset.class_names,
        )
        
        # Update scheduler
        scheduler.step()
        
        epoch_time = time.time() - epoch_start
        
        # Print progress
        print(
            f"Epoch {epoch:3d}/{args.epochs} | "
            f"Train Loss: {train_loss:.4f}, F1: {train_f1:.4f} | "
            f"Val Loss: {val_loss:.4f}, F1: {val_metrics.micro_f1:.4f}, "
            f"Subset Acc: {val_metrics.subset_accuracy:.4f} | "
            f"Time: {epoch_time:.1f}s"
        )
        
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
                "lr": scheduler.get_last_lr()[0],
            }
            # Add per-class F1
            for name, f1 in val_metrics.per_class_f1.items():
                log_dict[f"val/f1_{name}"] = f1
            wandb.log(log_dict)
        
        # Save best model
        if val_metrics.micro_f1 > best_val_f1:
            best_val_f1 = val_metrics.micro_f1
            best_epoch = epoch
            
            checkpoint = {
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_metrics': val_metrics.to_dict(),
                'args': vars(args),
            }
            torch.save(checkpoint, output_dir / 'best_multilabel_model.pt')
            print(f"  → New best model saved (F1: {best_val_f1:.4f})")
        
        # Save periodic checkpoint
        if epoch % 10 == 0:
            checkpoint = {
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_metrics': val_metrics.to_dict(),
                'args': vars(args),
            }
            torch.save(checkpoint, output_dir / f'checkpoint_epoch_{epoch}.pt')
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"Best validation F1: {best_val_f1:.4f} at epoch {best_epoch}")
    print(f"Best model saved to: {output_dir / 'best_multilabel_model.pt'}")
    
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
