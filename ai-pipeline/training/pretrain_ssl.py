#!/usr/bin/env python3
"""
Self-Supervised Pretraining Script for Drum Classification

This script runs self-supervised pretraining on unlabeled audio data
using Masked Autoencoder (MAE) or Contrastive learning approaches.

Usage:
    python pretrain_ssl.py --audio-dir ./unlabeled_audio --method mae --epochs 100
    
    # Then fine-tune on labeled data
    python train_classifier.py --dataset ./dataset --pretrained-backbone backbone.pt

Expected benefits:
- 5-10% improvement in accuracy from pretraining on unlabeled data
- Better feature representations for rare drum sounds
- Reduced overfitting on small labeled datasets
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    import torchaudio
    import torchaudio.transforms as T
    HAS_TORCHAUDIO = True
except ImportError:
    HAS_TORCHAUDIO = False
    
try:
    import wandb
    HAS_WANDB = True
except ImportError:
    HAS_WANDB = False


class UnlabeledAudioDataset(Dataset):
    """Dataset for unlabeled audio files."""
    
    AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac'}
    
    def __init__(
        self,
        audio_dir: Path,
        sr: int = 44100,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
        target_frames: int = 128,
        segment_duration: float = 0.5,  # seconds
    ):
        self.audio_dir = Path(audio_dir)
        self.sr = sr
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.target_frames = target_frames
        self.segment_duration = segment_duration
        self.segment_samples = int(segment_duration * sr)
        
        # Find all audio files
        self.audio_files: List[Path] = []
        for ext in self.AUDIO_EXTENSIONS:
            self.audio_files.extend(self.audio_dir.rglob(f"*{ext}"))
        
        logger.info(f"Found {len(self.audio_files)} audio files in {audio_dir}")
        
        # Setup transforms
        if HAS_TORCHAUDIO:
            self.mel_transform = T.MelSpectrogram(
                sample_rate=sr,
                n_fft=n_fft,
                hop_length=hop_length,
                n_mels=n_mels,
                power=2.0,
            )
            self.db_transform = T.AmplitudeToDB()
    
    def __len__(self) -> int:
        return len(self.audio_files)
    
    def __getitem__(self, idx: int):
        audio_path = self.audio_files[idx]
        
        try:
            # Load audio
            if HAS_TORCHAUDIO:
                waveform, sr = torchaudio.load(str(audio_path))
                if sr != self.sr:
                    waveform = torchaudio.functional.resample(waveform, sr, self.sr)
                waveform = waveform.mean(dim=0)  # Mono
            elif HAS_LIBROSA:
                waveform, _ = librosa.load(audio_path, sr=self.sr, mono=True)
                waveform = torch.from_numpy(waveform)
            else:
                raise RuntimeError("No audio backend available")
            
            # Extract random segment
            if waveform.shape[0] > self.segment_samples:
                start = random.randint(0, waveform.shape[0] - self.segment_samples)
                waveform = waveform[start:start + self.segment_samples]
            else:
                # Pad if too short
                pad_len = self.segment_samples - waveform.shape[0]
                waveform = torch.nn.functional.pad(waveform, (0, pad_len))
            
            # Extract mel spectrogram
            if HAS_TORCHAUDIO:
                mel = self.mel_transform(waveform.unsqueeze(0))
                mel = self.db_transform(mel)
                mel = mel.squeeze(0)
            else:
                mel_np = librosa.feature.melspectrogram(
                    y=waveform.numpy(),
                    sr=self.sr,
                    n_fft=self.n_fft,
                    hop_length=self.hop_length,
                    n_mels=self.n_mels,
                )
                mel_np = librosa.power_to_db(mel_np, ref=np.max)
                mel = torch.from_numpy(mel_np)
            
            # Normalize
            mel = torch.nan_to_num(mel, nan=0.0)
            mel = mel.unsqueeze(0)  # Add channel dimension
            mel = torch.nn.functional.interpolate(
                mel.unsqueeze(0),
                size=(self.n_mels, self.target_frames),
                mode='bilinear',
                align_corners=False,
            ).squeeze(0)
            
            # Normalize to [0, 1]
            mel_min = mel.min()
            mel_max = mel.max()
            if mel_max > mel_min:
                mel = (mel - mel_min) / (mel_max - mel_min)
            
            return mel.float()
            
        except Exception as e:
            logger.warning(f"Error loading {audio_path}: {e}")
            # Return random noise as fallback
            return torch.rand(1, self.n_mels, self.target_frames)


class MAEEncoder(nn.Module):
    """Simple CNN encoder for MAE pretraining."""
    
    def __init__(
        self,
        in_channels: int = 1,
        embed_dim: int = 256,
    ):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.GELU(),
            nn.Conv2d(32, 64, 3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.GELU(),
            nn.Conv2d(64, 128, 3, stride=2, padding=1),
            nn.BatchNorm2d(128),
            nn.GELU(),
            nn.Conv2d(128, embed_dim, 3, stride=2, padding=1),
            nn.BatchNorm2d(embed_dim),
            nn.GELU(),
        )
        
        self.embed_dim = embed_dim
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)


class MAEDecoder(nn.Module):
    """Simple CNN decoder for MAE pretraining."""
    
    def __init__(
        self,
        embed_dim: int = 256,
        out_channels: int = 1,
        out_size: tuple = (128, 128),
    ):
        super().__init__()
        
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(embed_dim, 128, 4, stride=2, padding=1),
            nn.BatchNorm2d(128),
            nn.GELU(),
            nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.GELU(),
            nn.ConvTranspose2d(64, 32, 4, stride=2, padding=1),
            nn.BatchNorm2d(32),
            nn.GELU(),
            nn.ConvTranspose2d(32, out_channels, 4, stride=2, padding=1),
        )
        
        self.out_size = out_size
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.decoder(x)
        # Ensure output matches input size
        x = torch.nn.functional.interpolate(
            x, size=self.out_size, mode='bilinear', align_corners=False
        )
        return x


class MaskedAutoencoder(nn.Module):
    """
    Masked Autoencoder for self-supervised pretraining.
    
    Masks random patches of the spectrogram and learns to reconstruct them.
    """
    
    def __init__(
        self,
        embed_dim: int = 256,
        mask_ratio: float = 0.75,
        input_size: tuple = (128, 128),
    ):
        super().__init__()
        
        self.mask_ratio = mask_ratio
        self.input_size = input_size
        
        self.encoder = MAEEncoder(embed_dim=embed_dim)
        self.decoder = MAEDecoder(embed_dim=embed_dim, out_size=input_size)
        
        # Learnable mask token
        self.mask_token = nn.Parameter(torch.randn(1, embed_dim, 1, 1) * 0.02)
    
    def random_mask(self, x: torch.Tensor) -> tuple:
        """Generate random mask for input."""
        B, C, H, W = x.shape
        
        # Create patch mask (8x8 patches)
        patch_h, patch_w = 8, 8
        num_patches_h = H // patch_h
        num_patches_w = W // patch_w
        num_patches = num_patches_h * num_patches_w
        
        num_mask = int(num_patches * self.mask_ratio)
        
        # Generate mask
        mask = torch.zeros(B, num_patches, device=x.device)
        for i in range(B):
            mask_indices = torch.randperm(num_patches, device=x.device)[:num_mask]
            mask[i, mask_indices] = 1
        
        # Reshape mask to spatial dimensions
        mask = mask.view(B, 1, num_patches_h, num_patches_w)
        mask = torch.nn.functional.interpolate(
            mask, size=(H, W), mode='nearest'
        )
        
        return mask
    
    def forward(self, x: torch.Tensor) -> tuple:
        """
        Forward pass with masking.
        
        Returns:
            pred: Reconstructed spectrogram
            mask: Binary mask (1 = masked, 0 = visible)
        """
        mask = self.random_mask(x)
        
        # Apply mask (replace with zeros for masked regions)
        x_masked = x * (1 - mask)
        
        # Encode
        z = self.encoder(x_masked)
        
        # Decode
        pred = self.decoder(z)
        
        return pred, mask
    
    def compute_loss(self, pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Compute reconstruction loss only on masked regions."""
        # MSE loss on masked patches
        loss = (pred - target) ** 2
        loss = (loss * mask).sum() / (mask.sum() + 1e-6)
        return loss
    
    def get_encoder_weights(self) -> dict:
        """Extract encoder weights for transfer learning."""
        return self.encoder.state_dict()


class ContrastivePretrainer(nn.Module):
    """
    Contrastive self-supervised pretraining.
    
    Creates positive pairs through augmentation and learns to bring
    similar spectrograms closer in embedding space.
    """
    
    def __init__(
        self,
        embed_dim: int = 256,
        proj_dim: int = 128,
        temperature: float = 0.07,
    ):
        super().__init__()
        
        self.encoder = MAEEncoder(embed_dim=embed_dim)
        self.temperature = temperature
        
        # Projection head for contrastive learning
        self.projection = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(embed_dim, embed_dim),
            nn.GELU(),
            nn.Linear(embed_dim, proj_dim),
        )
    
    def augment(self, x: torch.Tensor) -> torch.Tensor:
        """Apply augmentations for contrastive pairs."""
        B, C, H, W = x.shape
        
        augmented = x.clone()
        
        for i in range(B):
            # Random time/frequency masking
            if random.random() > 0.5:
                mask_h = random.randint(0, H // 4)
                mask_start_h = random.randint(0, H - mask_h)
                augmented[i, :, mask_start_h:mask_start_h + mask_h, :] = 0
            
            if random.random() > 0.5:
                mask_w = random.randint(0, W // 4)
                mask_start_w = random.randint(0, W - mask_w)
                augmented[i, :, :, mask_start_w:mask_start_w + mask_w] = 0
            
            # Random gain adjustment
            if random.random() > 0.5:
                gain = random.uniform(0.8, 1.2)
                augmented[i] = augmented[i] * gain
        
        return augmented.clamp(0, 1)
    
    def forward(self, x: torch.Tensor) -> tuple:
        """Forward pass creating two views."""
        # Create two augmented views
        x1 = self.augment(x)
        x2 = self.augment(x)
        
        # Encode both views
        z1 = self.encoder(x1)
        z2 = self.encoder(x2)
        
        # Project to contrastive space
        p1 = self.projection(z1)
        p2 = self.projection(z2)
        
        # Normalize
        p1 = torch.nn.functional.normalize(p1, dim=1)
        p2 = torch.nn.functional.normalize(p2, dim=1)
        
        return p1, p2
    
    def compute_loss(self, p1: torch.Tensor, p2: torch.Tensor) -> torch.Tensor:
        """Compute NT-Xent (InfoNCE) loss."""
        B = p1.shape[0]
        
        # Concatenate projections
        projections = torch.cat([p1, p2], dim=0)
        
        # Compute similarity matrix
        sim = torch.mm(projections, projections.t()) / self.temperature
        
        # Create labels (positive pairs are diagonal shifted by B)
        labels = torch.cat([torch.arange(B) + B, torch.arange(B)]).to(sim.device)
        
        # Mask out self-similarity
        mask = torch.eye(2 * B, device=sim.device).bool()
        sim.masked_fill_(mask, float('-inf'))
        
        # Cross entropy loss
        loss = torch.nn.functional.cross_entropy(sim, labels)
        
        return loss
    
    def get_encoder_weights(self) -> dict:
        """Extract encoder weights for transfer learning."""
        return self.encoder.state_dict()


def pretrain_mae(
    model: MaskedAutoencoder,
    dataloader: DataLoader,
    epochs: int,
    device: torch.device,
    lr: float = 1e-3,
    weight_decay: float = 0.05,
    wandb_project: Optional[str] = None,
) -> dict:
    """Train MAE model."""
    model.to(device)
    model.train()
    
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    
    # Initialize wandb if available
    if wandb_project and HAS_WANDB:
        wandb.init(project=wandb_project, config={
            'method': 'mae',
            'epochs': epochs,
            'lr': lr,
            'mask_ratio': model.mask_ratio,
        })
    
    best_loss = float('inf')
    history = {'loss': []}
    
    for epoch in range(epochs):
        total_loss = 0.0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        
        for batch in pbar:
            x = batch.to(device)
            
            optimizer.zero_grad()
            
            pred, mask = model(x)
            loss = model.compute_loss(pred, x, mask)
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': f'{loss.item():.4f}'})
        
        avg_loss = total_loss / len(dataloader)
        history['loss'].append(avg_loss)
        scheduler.step()
        
        logger.info(f"Epoch {epoch+1}: loss={avg_loss:.4f}")
        
        if wandb_project and HAS_WANDB:
            wandb.log({'loss': avg_loss, 'lr': scheduler.get_last_lr()[0]})
        
        if avg_loss < best_loss:
            best_loss = avg_loss
    
    if wandb_project and HAS_WANDB:
        wandb.finish()
    
    return history


def pretrain_contrastive(
    model: ContrastivePretrainer,
    dataloader: DataLoader,
    epochs: int,
    device: torch.device,
    lr: float = 1e-3,
    weight_decay: float = 0.05,
    wandb_project: Optional[str] = None,
) -> dict:
    """Train contrastive model."""
    model.to(device)
    model.train()
    
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    
    if wandb_project and HAS_WANDB:
        wandb.init(project=wandb_project, config={
            'method': 'contrastive',
            'epochs': epochs,
            'lr': lr,
            'temperature': model.temperature,
        })
    
    best_loss = float('inf')
    history = {'loss': []}
    
    for epoch in range(epochs):
        total_loss = 0.0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        
        for batch in pbar:
            x = batch.to(device)
            
            optimizer.zero_grad()
            
            p1, p2 = model(x)
            loss = model.compute_loss(p1, p2)
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': f'{loss.item():.4f}'})
        
        avg_loss = total_loss / len(dataloader)
        history['loss'].append(avg_loss)
        scheduler.step()
        
        logger.info(f"Epoch {epoch+1}: loss={avg_loss:.4f}")
        
        if wandb_project and HAS_WANDB:
            wandb.log({'loss': avg_loss, 'lr': scheduler.get_last_lr()[0]})
        
        if avg_loss < best_loss:
            best_loss = avg_loss
    
    if wandb_project and HAS_WANDB:
        wandb.finish()
    
    return history


def main():
    parser = argparse.ArgumentParser(
        description="Self-supervised pretraining for drum classification"
    )
    
    parser.add_argument(
        '--audio-dir', '-d',
        type=Path,
        required=True,
        help='Directory containing unlabeled audio files'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default='pretrained_backbone.pt',
        help='Output path for pretrained backbone weights'
    )
    
    parser.add_argument(
        '--method',
        choices=['mae', 'contrastive'],
        default='mae',
        help='Pretraining method (mae or contrastive)'
    )
    
    parser.add_argument(
        '--epochs',
        type=int,
        default=100,
        help='Number of pretraining epochs'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=64,
        help='Batch size for pretraining'
    )
    
    parser.add_argument(
        '--lr',
        type=float,
        default=1e-3,
        help='Learning rate'
    )
    
    parser.add_argument(
        '--embed-dim',
        type=int,
        default=256,
        help='Embedding dimension'
    )
    
    parser.add_argument(
        '--mask-ratio',
        type=float,
        default=0.75,
        help='Mask ratio for MAE (default: 0.75)'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default=None,
        help='Device to use (cuda/cpu)'
    )
    
    parser.add_argument(
        '--num-workers',
        type=int,
        default=4,
        help='Number of dataloader workers'
    )
    
    parser.add_argument(
        '--wandb-project',
        type=str,
        default=None,
        help='Weights & Biases project for logging'
    )
    
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed'
    )
    
    args = parser.parse_args()
    
    # Set seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    
    # Device
    device = torch.device(args.device or ('cuda' if torch.cuda.is_available() else 'cpu'))
    logger.info(f"Using device: {device}")
    
    # Create dataset
    dataset = UnlabeledAudioDataset(args.audio_dir)
    
    if len(dataset) == 0:
        raise ValueError(f"No audio files found in {args.audio_dir}")
    
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=device.type == 'cuda',
    )
    
    logger.info(f"Pretraining on {len(dataset)} audio files")
    
    # Create model
    if args.method == 'mae':
        model = MaskedAutoencoder(
            embed_dim=args.embed_dim,
            mask_ratio=args.mask_ratio,
        )
        
        history = pretrain_mae(
            model, dataloader, args.epochs, device,
            lr=args.lr, wandb_project=args.wandb_project
        )
        
    else:  # contrastive
        model = ContrastivePretrainer(
            embed_dim=args.embed_dim,
        )
        
        history = pretrain_contrastive(
            model, dataloader, args.epochs, device,
            lr=args.lr, wandb_project=args.wandb_project
        )
    
    # Save backbone weights
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    encoder_weights = model.get_encoder_weights()
    torch.save({
        'encoder_state_dict': encoder_weights,
        'method': args.method,
        'embed_dim': args.embed_dim,
        'history': history,
    }, args.output)
    
    logger.info(f"Saved pretrained backbone to {args.output}")
    
    # Print summary
    final_loss = history['loss'][-1] if history['loss'] else float('inf')
    logger.info(f"\nPretraining complete!")
    logger.info(f"  Method: {args.method}")
    logger.info(f"  Epochs: {args.epochs}")
    logger.info(f"  Final loss: {final_loss:.4f}")
    logger.info(f"\nNext steps:")
    logger.info(f"  1. Fine-tune with: python train_classifier.py --pretrained-backbone {args.output}")


if __name__ == '__main__':
    main()
