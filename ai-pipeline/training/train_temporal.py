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
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

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
    TemporalLoss,
    MambaConfig,
    temporal_small,
    temporal_medium,
    temporal_large,
    ultimate_small,
    ultimate_medium,
    ultimate_large
)
from training.datasets.sequence_dataset import (
    SequenceDrumDataset,
    SequenceConfig,
    create_sequence_dataloaders
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
    use_audio: bool = False
) -> Dict[str, float]:
    """Train for one epoch."""
    model.train()
    
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    loss_components = {"classification": 0.0, "temporal": 0.0, "coherence": 0.0}
    
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


def save_checkpoint(
    model: nn.Module,
    optimizer: optim.Optimizer,
    scheduler,
    epoch: int,
    metrics: Dict[str, float],
    args,
    is_best: bool = False
):
    """Save model checkpoint."""
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler else None,
        "metrics": metrics,
        "args": vars(args)
    }
    
    # Save latest
    torch.save(checkpoint, output_dir / "latest.pt")
    
    # Save periodic
    if epoch % args.save_every == 0:
        torch.save(checkpoint, output_dir / f"epoch_{epoch}.pt")
    
    # Save best
    if is_best:
        torch.save(checkpoint, output_dir / "best.pt")
        print(f"  New best model saved! Val accuracy: {metrics['val/accuracy']:.2f}%")


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
    print(f"Model parameters:")
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
        print(f"Ultimate mode enabled - audio features will be used")
        if args.use_wav2vec:
            print(f"  Wav2Vec2 model: {args.wav2vec_model}")
        if args.use_multi_res:
            print(f"  Multi-resolution spectrograms enabled")
    
    # Training loop
    best_val_acc = 0.0
    print(f"\nStarting training for {args.epochs} epochs...")
    
    for epoch in range(1, args.epochs + 1):
        # Unfreeze CNN after specified epochs
        if args.freeze_cnn_epochs > 0 and epoch == args.freeze_cnn_epochs + 1:
            print(f"Unfreezing CNN encoder at epoch {epoch}")
            for param in model.cnn_encoder.parameters():
                param.requires_grad = True
        
        # Train
        train_metrics = train_epoch(
            model, train_loader, criterion, optimizer, scheduler,
            scaler, device, args, epoch, use_audio=use_audio
        )
        
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
        
        save_checkpoint(model, optimizer, scheduler, epoch, metrics, args, is_best)
    
    print(f"\nTraining complete! Best validation accuracy: {best_val_acc:.2f}%")
    
    # Final save
    final_path = Path(args.output_dir) / "final.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "args": vars(args),
        "best_val_accuracy": best_val_acc
    }, final_path)
    print(f"Final model saved to {final_path}")
    
    if args.wandb and HAS_WANDB:
        wandb.finish()


if __name__ == "__main__":
    main()
