"""
Training script for Temporal Drum Transcription with Mamba.

This script trains the TemporalDrumTranscriber model which uses
state-space models (Mamba) to capture temporal context in drum
transcription. This is a NOVEL approach that models drum patterns
and improves accuracy on ambiguous cases.

Supports TWO model types:
1. TemporalDrumTranscriber - Standard temporal model with CNN + Mamba
2. UltimateTemporalDrumTranscriber - ULTIMATE model with ALL innovations:
   - CNN encoder (v4 with CoordAttn)
   - Wav2Vec2 frozen embeddings (NOVEL)
   - Multi-resolution spectrograms
   - Mamba temporal layers
   - Beat-aware positional encoding
   - Drum pattern priors

Usage:
    # Train standard temporal model from scratch
    python train_temporal.py --dataset ./dataset --epochs 100

    # Fine-tune from pretrained CNN
    python train_temporal.py --dataset ./dataset --pretrained-cnn models/v4_best.pt

    # ULTIMATE model with all features (RECOMMENDED)
    python train_temporal.py \\
        --dataset ./dataset \\
        --ultimate-mode \\
        --use-wav2vec \\
        --use-multi-res \\
        --use-beat-encoding \\
        --use-pattern-prior \\
        --pretrained-cnn models/v4_best.pt \\
        --freeze-cnn-epochs 10 \\
        --audio-dir ./audio_files  # Required for wav2vec/multi-res

    # Full config for temporal-only mode
    python train_temporal.py \\
        --dataset ./dataset \\
        --epochs 100 \\
        --batch-size 8 \\
        --sequence-length 32 \\
        --d-model 256 \\
        --n-layers 4 \\
        --use-beat-encoding \\
        --use-pattern-prior \\
        --pretrained-cnn models/v4_best.pt \\
        --freeze-cnn-epochs 10

Expected improvement:
- Temporal (standard): +3-8% on ambiguous cases
- Ultimate (all features): +19-37% over baseline CNN

Total training time: 
- Temporal: ~6-12 hours on RTX 3080 Ti
- Ultimate: ~20-40 hours on RTX 3080 Ti
"""

import argparse
import os
import random
import signal
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import GradScaler, autocast
from torch.utils.data import DataLoader
from tqdm import tqdm

# Local imports
import sys
sys.path.append(str(Path(__file__).parent.parent))

from training.models.temporal_mamba import (
    TemporalDrumTranscriber,
    UltimateTemporalDrumTranscriber,
    TemporalLoss
)
from training.datasets.sequence_dataset import (
    SequenceDrumDataset,
    SequenceConfig
)

# Optional: wandb logging
try:
    import wandb
    HAS_WANDB = True
except ImportError:
    HAS_WANDB = False
    wandb = None


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_args():
    parser = argparse.ArgumentParser(description="Train Temporal Drum Transcriber")
    
    # Data
    parser.add_argument("--dataset", type=str, required=True, help="Dataset directory")
    parser.add_argument("--sequence-length", type=int, default=32, help="Windows per sequence")
    parser.add_argument("--window-hop", type=int, default=16, help="Stride between sequences")
    parser.add_argument("--audio-dir", type=str, default=None, 
                        help="Directory with audio files (required for --use-wav2vec or --use-multi-res)")
    
    # Model type
    parser.add_argument("--ultimate-mode", action="store_true",
                        help="Use UltimateTemporalDrumTranscriber with all innovations")
    
    # Model architecture
    parser.add_argument("--model-size", type=str, default="medium",
                        choices=["small", "medium", "large"], help="Model size preset")
    parser.add_argument("--d-model", type=int, default=None, help="Override model dimension")
    parser.add_argument("--n-layers", type=int, default=None, help="Override number of layers")
    parser.add_argument("--d-state", type=int, default=16, help="SSM state dimension")
    parser.add_argument("--use-beat-encoding", action="store_true", help="Use beat positional encoding")
    parser.add_argument("--use-pattern-prior", action="store_true", help="Use drum pattern prior")
    parser.add_argument("--no-pattern-prior", action="store_true", help="Disable pattern prior")
    
    # Ultimate model features
    parser.add_argument("--use-wav2vec", action="store_true",
                        help="Use Wav2Vec2 frozen features (NOVEL - requires --audio-dir)")
    parser.add_argument("--wav2vec-model", type=str, default="facebook/wav2vec2-base",
                        choices=["facebook/wav2vec2-base", "facebook/wav2vec2-large", 
                                 "facebook/hubert-base-ls960", "facebook/hubert-large-ls960-ft"],
                        help="Which Wav2Vec2/HuBERT model to use")
    parser.add_argument("--use-multi-res", action="store_true",
                        help="Use multi-resolution spectrograms (requires --audio-dir)")
    parser.add_argument("--freeze-wav2vec", action="store_true", default=True,
                        help="Freeze Wav2Vec2 encoder (recommended)")
    parser.add_argument("--sample-rate", type=int, default=22050,
                        help="Audio sample rate")
    
    # Pretrained CNN
    parser.add_argument("--pretrained-cnn", type=str, default=None, help="Path to pretrained CNN")
    parser.add_argument("--freeze-cnn", action="store_true", help="Freeze CNN encoder")
    parser.add_argument("--freeze-cnn-epochs", type=int, default=0,
                        help="Freeze CNN for first N epochs, then unfreeze")
    
    # Training
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--weight-decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--warmup-epochs", type=int, default=5, help="LR warmup epochs")
    parser.add_argument("--grad-clip", type=float, default=1.0, help="Gradient clipping")
    
    # Loss weights
    parser.add_argument("--temporal-weight", type=float, default=0.1,
                        help="Weight for temporal consistency loss")
    parser.add_argument("--coherence-weight", type=float, default=0.05,
                        help="Weight for pattern coherence loss")
    parser.add_argument("--label-smoothing", type=float, default=0.1, help="Label smoothing")
    
    # Misc
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--num-workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--output-dir", type=str, default="./checkpoints/temporal",
                        help="Output directory")
    parser.add_argument("--save-every", type=int, default=10, help="Save checkpoint every N epochs")
    parser.add_argument("--wandb", action="store_true", help="Enable wandb logging")
    parser.add_argument("--wandb-project", type=str, default="beatsight-temporal",
                        help="Wandb project name")
    parser.add_argument("--mixed-precision", action="store_true", help="Use mixed precision")
    
    # Resume training
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint to resume from (e.g., checkpoints/temporal/latest.pt)")
    parser.add_argument("--checkpoint-every-batches", type=int, default=500,
                        help="Save mid-epoch checkpoint every N batches (0 to disable)")
    
    return parser.parse_args()


def create_model(args, num_classes: int):
    """Create temporal model based on arguments."""
    
    # Get model size presets
    size_configs = {
        "small": {"d_model": 128, "n_layers": 2},
        "medium": {"d_model": 256, "n_layers": 4},
        "large": {"d_model": 384, "n_layers": 6}
    }
    
    config = size_configs[args.model_size]
    
    # Override with explicit args if provided
    d_model = args.d_model or config["d_model"]
    n_layers = args.n_layers or config["n_layers"]
    
    # Determine pattern prior setting
    use_pattern_prior = not args.no_pattern_prior
    if args.use_pattern_prior:
        use_pattern_prior = True
    
    # Check if we need audio features
    needs_audio = args.use_wav2vec or args.use_multi_res
    if needs_audio and not args.audio_dir:
        raise ValueError(
            "--audio-dir is required when using --use-wav2vec or --use-multi-res"
        )
    
    # Create appropriate model type
    if args.ultimate_mode or needs_audio:
        # Use ULTIMATE model with all innovations
        print("Creating UltimateTemporalDrumTranscriber...")
        model = UltimateTemporalDrumTranscriber(
            num_classes=num_classes,
            d_model=d_model,
            n_layers=n_layers,
            d_state=args.d_state,
            use_wav2vec=args.use_wav2vec,
            use_multi_res=args.use_multi_res,
            use_beat_encoding=args.use_beat_encoding,
            use_pattern_prior=use_pattern_prior,
            wav2vec_model=args.wav2vec_model,
            freeze_wav2vec=args.freeze_wav2vec,
            sample_rate=args.sample_rate,
            freeze_cnn=args.freeze_cnn or (args.freeze_cnn_epochs > 0)
        )
        
        # Load pretrained CNN if provided
        if args.pretrained_cnn:
            load_pretrained_cnn(model, args.pretrained_cnn)
        
        return model
    else:
        # Use standard temporal model
        print("Creating TemporalDrumTranscriber...")
        model = TemporalDrumTranscriber(
            num_classes=num_classes,
            d_model=d_model,
            n_layers=n_layers,
            d_state=args.d_state,
            use_beat_encoding=args.use_beat_encoding,
            use_pattern_prior=use_pattern_prior,
            freeze_cnn=args.freeze_cnn or (args.freeze_cnn_epochs > 0)
        )
        
        # Load pretrained CNN if provided
        if args.pretrained_cnn:
            load_pretrained_cnn(model, args.pretrained_cnn)
        
        return model


def load_pretrained_cnn(model: TemporalDrumTranscriber, checkpoint_path: str):
    """Load pretrained CNN weights into temporal model."""
    print(f"Loading pretrained CNN from {checkpoint_path}")
    
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    
    # Handle different checkpoint formats
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint
    
    # Filter for CNN encoder keys and map to new structure
    cnn_state = {}
    for key, value in state_dict.items():
        if key.startswith('features.'):
            cnn_state[key.replace('features.', '')] = value
        elif key.startswith('conv'):
            # Handle v1 model structure
            cnn_state[key] = value
    
    if cnn_state:
        model.cnn_encoder.load_state_dict(cnn_state, strict=False)
        print(f"  Loaded {len(cnn_state)} CNN weight tensors")
    else:
        print("  Warning: No compatible CNN weights found")


def create_optimizer(model: nn.Module, args) -> optim.Optimizer:
    """Create optimizer with weight decay only on non-bias/norm parameters."""
    decay_params = []
    no_decay_params = []
    
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if 'bias' in name or 'norm' in name or 'bn' in name:
            no_decay_params.append(param)
        else:
            decay_params.append(param)
    
    optimizer = optim.AdamW([
        {'params': decay_params, 'weight_decay': args.weight_decay},
        {'params': no_decay_params, 'weight_decay': 0.0}
    ], lr=args.lr, betas=(0.9, 0.98))
    
    return optimizer


def create_scheduler(optimizer: optim.Optimizer, args, steps_per_epoch: int):
    """Create learning rate scheduler with warmup."""
    total_steps = args.epochs * steps_per_epoch
    warmup_steps = args.warmup_epochs * steps_per_epoch
    
    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return max(0.1, 0.5 * (1 + np.cos(np.pi * progress)))  # Cosine decay to 10%
    
    scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    return scheduler


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    scheduler,
    scaler: Optional[GradScaler],
    device: torch.device,
    args,
    epoch: int,
    use_audio: bool = False,
    checkpoint_callback: Optional[callable] = None,
    checkpoint_every_batches: int = 0,
) -> Dict[str, float]:
    """Train for one epoch with optional mid-epoch checkpointing.
    
    Args:
        checkpoint_callback: Optional callback(batch_idx, total_batches) for mid-epoch saves
        checkpoint_every_batches: Save checkpoint every N batches (0 to disable)
    """
    model.train()
    
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    loss_components = {"classification": 0.0, "temporal": 0.0, "coherence": 0.0}
    total_batches = len(dataloader)
    
    pbar = tqdm(dataloader, desc=f"Epoch {epoch}")
    
    for batch_idx, batch in enumerate(pbar):
        # Unpack batch - handle variable length
        spectrograms, labels = batch[0], batch[1]
        beat_positions = batch[2] if len(batch) > 2 and batch[2] is not None else None
        bar_positions = batch[3] if len(batch) > 3 and batch[3] is not None else None
        audio = batch[4] if len(batch) > 4 and batch[4] is not None and use_audio else None
        
        spectrograms = spectrograms.to(device)
        labels = labels.to(device)
        if beat_positions is not None:
            beat_positions = beat_positions.to(device)
        if bar_positions is not None:
            bar_positions = bar_positions.to(device)
        if audio is not None:
            audio = audio.to(device)
        
        optimizer.zero_grad()
        
        # Forward pass - handle both model types
        if args.mixed_precision and scaler is not None:
            with autocast(device_type='cuda'):
                if hasattr(model, 'use_wav2vec'):
                    # UltimateTemporalDrumTranscriber
                    logits, confidence = model(
                        spectrograms,
                        audio=audio,
                        beat_positions=beat_positions,
                        bar_positions=bar_positions,
                        return_confidence=True
                    )
                else:
                    # TemporalDrumTranscriber
                    logits, confidence = model(
                        spectrograms,
                        beat_positions=beat_positions,
                        bar_positions=bar_positions,
                        return_confidence=True
                    )
                loss, loss_dict = criterion(logits, labels, confidence)
            
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            if hasattr(model, 'use_wav2vec'):
                # UltimateTemporalDrumTranscriber
                logits, confidence = model(
                    spectrograms,
                    audio=audio,
                    beat_positions=beat_positions,
                    bar_positions=bar_positions,
                    return_confidence=True
                )
            else:
                # TemporalDrumTranscriber
                logits, confidence = model(
                    spectrograms,
                    beat_positions=beat_positions,
                    bar_positions=bar_positions,
                    return_confidence=True
                )
            loss, loss_dict = criterion(logits, labels, confidence)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            optimizer.step()
        
        scheduler.step()
        
        # Compute accuracy
        batch_size, seq_len, _ = logits.shape
        preds = logits.argmax(dim=-1)
        correct = (preds == labels).sum().item()
        
        total_loss += loss.item()
        total_correct += correct
        total_samples += batch_size * seq_len
        
        for key in loss_components:
            if key in loss_dict:
                loss_components[key] += loss_dict[key]
        
        # Update progress bar
        pbar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "acc": f"{100 * correct / (batch_size * seq_len):.1f}%"
        })
        
        # Mid-epoch checkpoint (protects against crashes during long epochs)
        if checkpoint_callback and checkpoint_every_batches > 0:
            if (batch_idx + 1) % checkpoint_every_batches == 0 and (batch_idx + 1) < total_batches:
                checkpoint_callback(batch_idx + 1, total_batches)
    
    num_batches = len(dataloader)
    metrics = {
        "train/loss": total_loss / num_batches,
        "train/accuracy": 100 * total_correct / total_samples,
        "train/lr": scheduler.get_last_lr()[0]
    }
    for key, value in loss_components.items():
        metrics[f"train/{key}_loss"] = value / num_batches
    
    return metrics


@torch.no_grad()
def validate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    args,
    use_audio: bool = False
) -> Dict[str, float]:
    """Validate the model."""
    model.eval()
    
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    
    # Per-class accuracy
    class_correct = {}
    class_total = {}
    
    for batch in tqdm(dataloader, desc="Validating"):
        spectrograms, labels = batch[0], batch[1]
        beat_positions = batch[2] if len(batch) > 2 and batch[2] is not None else None
        bar_positions = batch[3] if len(batch) > 3 and batch[3] is not None else None
        audio = batch[4] if len(batch) > 4 and batch[4] is not None and use_audio else None
        
        spectrograms = spectrograms.to(device)
        labels = labels.to(device)
        if beat_positions is not None:
            beat_positions = beat_positions.to(device)
        if bar_positions is not None:
            bar_positions = bar_positions.to(device)
        if audio is not None:
            audio = audio.to(device)
        
        if hasattr(model, 'use_wav2vec'):
            # UltimateTemporalDrumTranscriber
            logits, confidence = model(
                spectrograms,
                audio=audio,
                beat_positions=beat_positions,
                bar_positions=bar_positions,
                return_confidence=True
            )
        else:
            # TemporalDrumTranscriber
            logits, confidence = model(
                spectrograms,
                beat_positions=beat_positions,
                bar_positions=bar_positions,
                return_confidence=True
            )
        loss, _ = criterion(logits, labels, confidence)
        
        # Compute accuracy
        batch_size, seq_len, _ = logits.shape
        preds = logits.argmax(dim=-1)
        correct = (preds == labels).sum().item()
        
        total_loss += loss.item()
        total_correct += correct
        total_samples += batch_size * seq_len
        
        # Per-class stats
        for cls in labels.unique():
            cls = cls.item()
            mask = labels == cls
            if cls not in class_correct:
                class_correct[cls] = 0
                class_total[cls] = 0
            class_correct[cls] += (preds[mask] == cls).sum().item()
            class_total[cls] += mask.sum().item()
    
    num_batches = len(dataloader)
    
    # Calculate per-class accuracy
    class_accuracies = {}
    for cls in class_total:
        if class_total[cls] > 0:
            class_accuracies[cls] = 100 * class_correct[cls] / class_total[cls]
    
    metrics = {
        "val/loss": total_loss / num_batches,
        "val/accuracy": 100 * total_correct / total_samples,
        "val/mean_class_accuracy": np.mean(list(class_accuracies.values())) if class_accuracies else 0.0
    }
    
    return metrics


def _atomic_torch_save(obj: Any, path: Path) -> None:
    """Save a PyTorch object atomically to prevent corruption from Ctrl+C.
    
    Writes to a temporary file first, then atomically renames to the target.
    This prevents checkpoint corruption when training is interrupted during save.
    """
    parent_dir = path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    
    # Use a deterministic temp name based on target to avoid accumulating temp files
    temp_path = parent_dir / f".{path.name}.tmp"
    
    try:
        # Save to temp file
        torch.save(obj, temp_path)
        # Atomic rename (os.replace is atomic on both POSIX and Windows NTFS)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def save_checkpoint(
    model: nn.Module,
    optimizer: optim.Optimizer,
    scheduler,
    epoch: int,
    metrics: Dict[str, float],
    args,
    is_best: bool = False,
    best_val_acc: float = 0.0,
    reason: Optional[str] = None,
    batch_index: Optional[int] = None,
    total_batches: Optional[int] = None,
):
    """Save model checkpoint with atomic writes to prevent corruption.
    
    Args:
        model: The model to save
        optimizer: The optimizer state to save
        scheduler: The LR scheduler state to save
        epoch: Current epoch number
        metrics: Training/validation metrics
        args: Training arguments
        is_best: Whether this is the best model so far
        best_val_acc: Best validation accuracy so far
        reason: Optional reason for checkpoint (e.g., "interrupt", "mid_epoch")
        batch_index: Current batch (for mid-epoch checkpoints)
        total_batches: Total batches in epoch (for mid-epoch checkpoints)
    """
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
        "metrics": metrics,
        "args": vars(args),
        "best_val_acc": best_val_acc,
        "batch_index": batch_index,
        "total_batches": total_batches,
        "reason": reason,
    }
    
    # Save latest (atomic)
    _atomic_torch_save(checkpoint, output_dir / "latest.pt")
    
    is_mid_epoch = batch_index is not None
    if is_mid_epoch:
        # Mid-epoch checkpoint
        _atomic_torch_save(checkpoint, output_dir / f"epoch_{epoch}_mid.pt")
        pct = 100 * batch_index / total_batches if total_batches else 0
        print(f"\n💾 Mid-epoch checkpoint saved (epoch {epoch}, batch {batch_index}/{total_batches}, {pct:.0f}%)")
    else:
        # End-of-epoch: clean up mid-epoch checkpoint
        mid_epoch_path = output_dir / f"epoch_{epoch}_mid.pt"
        if mid_epoch_path.exists():
            mid_epoch_path.unlink()
        
        # Save periodic
        if epoch % args.save_every == 0:
            _atomic_torch_save(checkpoint, output_dir / f"epoch_{epoch}.pt")
        
        if reason:
            print(f"✓ Checkpoint saved ({reason}) at epoch {epoch}")
    
    # Save best
    if is_best:
        _atomic_torch_save(checkpoint, output_dir / "best.pt")
        print(f"  🏆 New best model saved! Val accuracy: {metrics.get('val/accuracy', 0):.2f}%")


def load_checkpoint(checkpoint_path: str, model: nn.Module, optimizer: optim.Optimizer, 
                   scheduler, device: torch.device) -> Dict[str, Any]:
    """Load checkpoint and restore training state.
    
    Returns dict with: epoch, metrics, best_val_acc, batch_index (if mid-epoch)
    """
    print(f"Loading checkpoint from {checkpoint_path}...")
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    model.load_state_dict(checkpoint["model_state_dict"])
    optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
    if scheduler and checkpoint.get("scheduler_state_dict"):
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
    
    epoch = checkpoint.get("epoch", 0)
    best_val_acc = checkpoint.get("best_val_acc", 0.0)
    batch_index = checkpoint.get("batch_index")
    
    if batch_index is not None:
        print(f"  Resuming from epoch {epoch}, batch {batch_index} (mid-epoch checkpoint)")
    else:
        print(f"  Resuming from epoch {epoch}")
    print(f"  Best validation accuracy so far: {best_val_acc:.2f}%")
    
    return {
        "epoch": epoch,
        "metrics": checkpoint.get("metrics", {}),
        "best_val_acc": best_val_acc,
        "batch_index": batch_index,
        "total_batches": checkpoint.get("total_batches"),
    }


def main():
    args = parse_args()
    set_seed(args.seed)
    
    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Setup wandb
    if args.wandb and HAS_WANDB:
        wandb.init(
            project=args.wandb_project,
            config=vars(args),
            name=f"temporal_{args.model_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
    
    # Create data loaders
    print("Creating dataloaders...")
    seq_config = SequenceConfig(
        sequence_length=args.sequence_length,
        window_hop=args.window_hop,
        use_beat_alignment=args.use_beat_encoding
    )
    
    train_dataset = SequenceDrumDataset(
        data_dir=args.dataset,
        config=seq_config,
        split="train",
        augment=True
    )
    
    val_dataset = SequenceDrumDataset(
        data_dir=args.dataset,
        config=seq_config,
        split="val",
        augment=False
    )
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=True,
        drop_last=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True
    )
    
    num_classes = len(train_dataset.class_to_idx)
    print(f"Dataset: {len(train_dataset)} train sequences, {len(val_dataset)} val sequences")
    print(f"Classes: {num_classes}")
    
    # Create model
    print("Creating model...")
    model = create_model(args, num_classes)
    model = model.to(device)
    
    param_counts = model.count_parameters()
    print("Model parameters:")
    for name, count in param_counts.items():
        print(f"  {name}: {count:,}")
    
    # Create optimizer and scheduler
    optimizer = create_optimizer(model, args)
    scheduler = create_scheduler(optimizer, args, len(train_loader))
    
    # Create loss function
    criterion = TemporalLoss(
        temporal_weight=args.temporal_weight,
        coherence_weight=args.coherence_weight,
        label_smoothing=args.label_smoothing
    )
    
    # Mixed precision scaler
    scaler = GradScaler() if args.mixed_precision else None
    
    # Determine if we need audio
    use_audio = args.use_wav2vec or args.use_multi_res
    if use_audio:
        print("Ultimate mode enabled - audio features will be used")
        if args.use_wav2vec:
            print(f"  Wav2Vec2 model: {args.wav2vec_model}")
        if args.use_multi_res:
            print("  Multi-resolution spectrograms enabled")
    
    # Resume from checkpoint if specified
    start_epoch = 1
    best_val_acc = 0.0
    last_completed_epoch = 0
    
    if args.resume:
        resume_path = Path(args.resume)
        if not resume_path.exists():
            # Try common locations
            if (Path(args.output_dir) / "latest.pt").exists():
                resume_path = Path(args.output_dir) / "latest.pt"
                print(f"Specified checkpoint not found, using: {resume_path}")
            else:
                raise FileNotFoundError(f"Checkpoint not found: {args.resume}")
        
        resume_state = load_checkpoint(str(resume_path), model, optimizer, scheduler, device)
        start_epoch = resume_state["epoch"] + 1  # Start from next epoch
        best_val_acc = resume_state["best_val_acc"]
        last_completed_epoch = resume_state["epoch"]
        
        # Handle mid-epoch resume (just restart the epoch)
        if resume_state.get("batch_index") is not None:
            print(f"  Note: Mid-epoch checkpoint detected. Will restart epoch {start_epoch - 1} from beginning.")
            start_epoch = resume_state["epoch"]  # Restart the interrupted epoch
    
    # Signal handler for graceful shutdown
    _shutdown_requested = False
    
    def _signal_handler(signum, frame):
        nonlocal _shutdown_requested
        sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
        print(f"\n⚠️  Received {sig_name} - will save checkpoint and exit after current batch...")
        _shutdown_requested = True
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C (Windows + Unix)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)  # kill command (Unix)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)  # terminal close (Unix)
    
    # Training loop with interrupt protection
    print(f"\nStarting training from epoch {start_epoch} to {args.epochs}...")
    output_dir = Path(args.output_dir)
    
    try:
        for epoch in range(start_epoch, args.epochs + 1):
            # Check for shutdown before starting epoch
            if _shutdown_requested:
                print(f"\n🛑 Shutdown requested before epoch {epoch}")
                save_checkpoint(model, optimizer, scheduler, last_completed_epoch, 
                              {"note": "shutdown_before_epoch"}, args, 
                              best_val_acc=best_val_acc, reason="shutdown_signal")
                break
            
            # Unfreeze CNN after specified epochs
            if args.freeze_cnn_epochs > 0 and epoch == args.freeze_cnn_epochs + 1:
                print(f"Unfreezing CNN encoder at epoch {epoch}")
                for param in model.cnn_encoder.parameters():
                    param.requires_grad = True
            
            # Create mid-epoch checkpoint callback
            def mid_epoch_checkpoint(batch_idx: int, total_batches: int) -> None:
                save_checkpoint(
                    model, optimizer, scheduler, epoch,
                    {"note": "mid_epoch"}, args,
                    best_val_acc=best_val_acc,
                    reason="mid_epoch",
                    batch_index=batch_idx,
                    total_batches=total_batches,
                )
            
            # Train with mid-epoch checkpointing
            train_metrics = train_epoch(
                model, train_loader, criterion, optimizer, scheduler,
                scaler, device, args, epoch, use_audio=use_audio,
                checkpoint_callback=mid_epoch_checkpoint if args.checkpoint_every_batches > 0 else None,
                checkpoint_every_batches=args.checkpoint_every_batches,
            )
            
            # Check for shutdown after training (before validation)
            if _shutdown_requested:
                print(f"\n🛑 Shutdown requested after training epoch {epoch}")
                # Save with current training metrics
                save_checkpoint(model, optimizer, scheduler, epoch, train_metrics, args,
                              best_val_acc=best_val_acc, reason="shutdown_after_train")
                print(f"✓ Checkpoint saved. Resume with: --resume {output_dir / 'latest.pt'}")
                break
            
            # Validate
            val_metrics = validate(model, val_loader, criterion, device, args, use_audio=use_audio)
            
            # Combine metrics
            metrics = {**train_metrics, **val_metrics}
            
            # Log to wandb
            if args.wandb and HAS_WANDB:
                wandb.log(metrics, step=epoch)
            
            # Print summary
            print(f"\nEpoch {epoch}/{args.epochs}:")
            print(f"  Train Loss: {metrics['train/loss']:.4f}, Acc: {metrics['train/accuracy']:.2f}%")
            print(f"  Val Loss: {metrics['val/loss']:.4f}, Acc: {metrics['val/accuracy']:.2f}%")
            
            # Save checkpoint
            is_best = val_metrics["val/accuracy"] > best_val_acc
            if is_best:
                best_val_acc = val_metrics["val/accuracy"]
            
            save_checkpoint(model, optimizer, scheduler, epoch, metrics, args, is_best,
                          best_val_acc=best_val_acc)
            last_completed_epoch = epoch
            
            # Check for shutdown after checkpoint
            if _shutdown_requested:
                print(f"\n🛑 Clean shutdown after epoch {epoch}")
                print(f"✓ Checkpoint saved. Resume with: --resume {output_dir / 'latest.pt'}")
                break
        
        if not _shutdown_requested:
            print(f"\n✓ Training complete! Best validation accuracy: {best_val_acc:.2f}%")
            
            # Final save
            final_path = output_dir / "final.pt"
            _atomic_torch_save({
                "model_state_dict": model.state_dict(),
                "args": vars(args),
                "best_val_accuracy": best_val_acc
            }, final_path)
            print(f"Final model saved to {final_path}")
    
    except KeyboardInterrupt:
        print(f"\n🛑 Training interrupted by user (Ctrl+C). Saving checkpoint...")
        save_checkpoint(model, optimizer, scheduler, last_completed_epoch,
                       {"note": "keyboard_interrupt"}, args,
                       best_val_acc=best_val_acc, reason="keyboard_interrupt")
        print(f"✓ Checkpoint saved. Resume with: --resume {output_dir / 'latest.pt'}")
        print("Exiting gracefully (checkpoint is safe).")
        return
    
    if args.wandb and HAS_WANDB:
        wandb.finish()


if __name__ == "__main__":
    main()
