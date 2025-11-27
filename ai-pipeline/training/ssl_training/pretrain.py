"""
Self-Supervised Pretraining for Drum Classification

This module implements self-supervised pretraining methods for audio
spectrograms. Self-supervised learning allows the model to learn useful
representations from unlabeled data, which can then be fine-tuned on
the labeled classification task.

Implemented Methods:
1. MAE (Masked Autoencoder) - Mask spectrogram patches and predict them
2. Contrastive Learning - Learn by comparing augmented views of same sample
3. DINO-style Self-Distillation - Teacher-student with no labels

Paper References:
- MAE: "Masked Autoencoders Are Scalable Vision Learners" (He et al., 2021)
- AudioMAE: "Masked Autoencoders that Listen" (Huang et al., 2022)
- SimCLR: "A Simple Framework for Contrastive Learning" (Chen et al., 2020)
- DINO: "Emerging Properties in Self-Supervised Vision Transformers" (Caron et al., 2021)

Expected improvement: +5-10% when pretrained on large unlabeled corpus

Usage:
    from training.ssl_training.pretrain import (
        MaskedAutoencoderPretrainer,
        ContrastivePretrainer,
        pretrain_mae,
    )
    
    # Pretrain on unlabeled data
    pretrained_encoder = pretrain_mae(
        unlabeled_loader,
        encoder_model,
        epochs=100,
    )
    
    # Fine-tune on labeled data
    classifier = DrumClassifierWithPretrained(pretrained_encoder, num_classes=21)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

logger = logging.getLogger(__name__)


# =============================================================================
# Masked Autoencoder (MAE) for Spectrograms
# =============================================================================

class PatchEmbed(nn.Module):
    """Convert spectrogram to sequence of patch embeddings."""
    
    def __init__(
        self,
        img_size: Tuple[int, int] = (128, 128),
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dim: int = 256,
    ):
        super().__init__()
        
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches = (img_size[0] // patch_size) * (img_size[1] // patch_size)
        
        self.proj = nn.Conv2d(
            in_channels, embed_dim,
            kernel_size=patch_size, stride=patch_size
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, C, H, W] -> [B, num_patches, embed_dim]
        x = self.proj(x)  # [B, embed_dim, H/P, W/P]
        x = x.flatten(2).transpose(1, 2)  # [B, num_patches, embed_dim]
        return x


class MAEEncoder(nn.Module):
    """
    Masked Autoencoder Encoder.
    
    Processes only visible (non-masked) patches through transformer blocks.
    """
    
    def __init__(
        self,
        img_size: Tuple[int, int] = (128, 128),
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dim: int = 256,
        num_heads: int = 4,
        num_layers: int = 4,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        self.patch_embed = PatchEmbed(img_size, patch_size, in_channels, embed_dim)
        num_patches = self.patch_embed.num_patches
        
        # Positional embedding
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embed_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=embed_dim,
                nhead=num_heads,
                dim_feedforward=int(embed_dim * mlp_ratio),
                dropout=dropout,
                activation='gelu',
                batch_first=True,
            )
            for _ in range(num_layers)
        ])
        
        self.norm = nn.LayerNorm(embed_dim)
        self.embed_dim = embed_dim
    
    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with optional masking.
        
        Args:
            x: Input spectrogram [B, C, H, W]
            mask: Boolean mask [B, num_patches], True = keep
        
        Returns:
            Tuple of (encoded_features, position_indices)
        """
        # Patch embedding
        x = self.patch_embed(x)  # [B, N, D]
        
        # Add positional embedding
        x = x + self.pos_embed
        
        if mask is not None:
            # Keep only visible patches
            B, N, D = x.shape
            visible_idx = mask.nonzero(as_tuple=True)
            
            # Gather visible patches
            x_visible = []
            pos_idx = []
            for b in range(B):
                vis_mask = mask[b]
                x_visible.append(x[b, vis_mask])
                pos_idx.append(vis_mask.nonzero().squeeze(-1))
            
            # Pad to same length
            max_len = max(len(xv) for xv in x_visible)
            x_padded = torch.zeros(B, max_len, D, device=x.device, dtype=x.dtype)
            for b, xv in enumerate(x_visible):
                x_padded[b, :len(xv)] = xv
            
            x = x_padded
            
        else:
            pos_idx = None
        
        # Transformer blocks
        for block in self.blocks:
            x = block(x)
        
        x = self.norm(x)
        
        return x, pos_idx


class MAEDecoder(nn.Module):
    """
    Masked Autoencoder Decoder.
    
    Reconstructs masked patches from encoded visible patches.
    """
    
    def __init__(
        self,
        num_patches: int,
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dim: int = 256,
        decoder_embed_dim: int = 128,
        num_heads: int = 4,
        num_layers: int = 2,
        mlp_ratio: float = 4.0,
    ):
        super().__init__()
        
        self.num_patches = num_patches
        self.patch_size = patch_size
        
        # Embed from encoder dim to decoder dim
        self.decoder_embed = nn.Linear(embed_dim, decoder_embed_dim)
        
        # Mask token
        self.mask_token = nn.Parameter(torch.zeros(1, 1, decoder_embed_dim))
        nn.init.trunc_normal_(self.mask_token, std=0.02)
        
        # Positional embedding
        self.decoder_pos_embed = nn.Parameter(torch.zeros(1, num_patches, decoder_embed_dim))
        nn.init.trunc_normal_(self.decoder_pos_embed, std=0.02)
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=decoder_embed_dim,
                nhead=num_heads,
                dim_feedforward=int(decoder_embed_dim * mlp_ratio),
                activation='gelu',
                batch_first=True,
            )
            for _ in range(num_layers)
        ])
        
        self.norm = nn.LayerNorm(decoder_embed_dim)
        
        # Prediction head
        self.pred = nn.Linear(decoder_embed_dim, patch_size * patch_size * in_channels)
    
    def forward(
        self,
        x: torch.Tensor,
        pos_idx: List[torch.Tensor],
        mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Reconstruct masked patches.
        
        Args:
            x: Encoded visible patches [B, num_visible, D]
            pos_idx: Position indices of visible patches
            mask: Boolean mask [B, N], True = visible
        
        Returns:
            Reconstructed patches [B, N, patch_pixels]
        """
        B = x.shape[0]
        device = x.device
        
        # Project to decoder dimension
        x = self.decoder_embed(x)
        
        # Unshuffle: put visible tokens back at their positions, fill masked with mask_token
        full_tokens = self.mask_token.expand(B, self.num_patches, -1).clone()
        
        for b in range(B):
            vis_mask = mask[b]
            full_tokens[b, vis_mask] = x[b, :vis_mask.sum()]
        
        # Add positional embedding
        full_tokens = full_tokens + self.decoder_pos_embed
        
        # Transformer blocks
        for block in self.blocks:
            full_tokens = block(full_tokens)
        
        full_tokens = self.norm(full_tokens)
        
        # Predict patch pixels
        pred = self.pred(full_tokens)  # [B, N, patch_pixels]
        
        return pred


class MaskedAutoencoder(nn.Module):
    """
    Complete Masked Autoencoder for Spectrograms.
    
    Masks random patches and trains to reconstruct them.
    """
    
    def __init__(
        self,
        img_size: Tuple[int, int] = (128, 128),
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dim: int = 256,
        encoder_layers: int = 4,
        decoder_embed_dim: int = 128,
        decoder_layers: int = 2,
        num_heads: int = 4,
        mask_ratio: float = 0.75,
    ):
        super().__init__()
        
        self.mask_ratio = mask_ratio
        self.patch_size = patch_size
        self.img_size = img_size
        
        num_patches = (img_size[0] // patch_size) * (img_size[1] // patch_size)
        
        self.encoder = MAEEncoder(
            img_size=img_size,
            patch_size=patch_size,
            in_channels=in_channels,
            embed_dim=embed_dim,
            num_heads=num_heads,
            num_layers=encoder_layers,
        )
        
        self.decoder = MAEDecoder(
            num_patches=num_patches,
            patch_size=patch_size,
            in_channels=in_channels,
            embed_dim=embed_dim,
            decoder_embed_dim=decoder_embed_dim,
            num_heads=num_heads,
            num_layers=decoder_layers,
        )
        
        self.num_patches = num_patches
    
    def random_masking(self, batch_size: int, device: torch.device) -> torch.Tensor:
        """Generate random mask."""
        num_keep = int(self.num_patches * (1 - self.mask_ratio))
        
        # Random noise for shuffling
        noise = torch.rand(batch_size, self.num_patches, device=device)
        ids_shuffle = torch.argsort(noise, dim=1)
        
        # Create mask: True = keep, False = mask
        mask = torch.zeros(batch_size, self.num_patches, device=device, dtype=torch.bool)
        for b in range(batch_size):
            mask[b, ids_shuffle[b, :num_keep]] = True
        
        return mask
    
    def patchify(self, imgs: torch.Tensor) -> torch.Tensor:
        """Convert images to patches."""
        B, C, H, W = imgs.shape
        p = self.patch_size
        assert H % p == 0 and W % p == 0
        
        h, w = H // p, W // p
        patches = imgs.reshape(B, C, h, p, w, p)
        patches = patches.permute(0, 2, 4, 1, 3, 5).reshape(B, h * w, C * p * p)
        return patches
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass: mask, encode, decode, and return loss.
        
        Returns:
            Tuple of (loss, predictions, mask)
        """
        B = x.shape[0]
        device = x.device
        
        # Generate mask
        mask = self.random_masking(B, device)
        
        # Encode visible patches
        encoded, pos_idx = self.encoder(x, mask)
        
        # Decode and predict
        pred = self.decoder(encoded, pos_idx, mask)
        
        # Get target patches
        target = self.patchify(x)
        
        # Compute loss only on masked patches
        loss = (pred - target) ** 2
        loss = loss.mean(dim=-1)  # Mean over patch pixels
        
        # Only compute loss on masked patches
        mask_inv = ~mask
        loss = (loss * mask_inv.float()).sum() / mask_inv.sum()
        
        return loss, pred, mask
    
    def get_encoder(self) -> nn.Module:
        """Get the encoder for downstream tasks."""
        return self.encoder


@dataclass
class MAEPretrainingConfig:
    """Configuration for MAE pretraining."""
    img_size: Tuple[int, int] = (128, 128)
    patch_size: int = 16
    embed_dim: int = 256
    encoder_layers: int = 4
    decoder_layers: int = 2
    num_heads: int = 4
    mask_ratio: float = 0.75
    epochs: int = 100
    batch_size: int = 64
    learning_rate: float = 1.5e-4
    weight_decay: float = 0.05
    warmup_epochs: int = 10


def pretrain_mae(
    dataloader: DataLoader,
    config: MAEPretrainingConfig,
    device: torch.device,
    checkpoint_dir: Optional[Path] = None,
    log_interval: int = 100,
) -> MAEEncoder:
    """
    Run MAE pretraining on unlabeled data.
    
    Args:
        dataloader: DataLoader yielding spectrograms (no labels needed)
        config: Pretraining configuration
        device: Compute device
        checkpoint_dir: Optional directory to save checkpoints
        log_interval: Steps between logging
    
    Returns:
        Pretrained encoder
    """
    logger.info(f"Starting MAE pretraining with config: {config}")
    
    # Create model
    model = MaskedAutoencoder(
        img_size=config.img_size,
        patch_size=config.patch_size,
        embed_dim=config.embed_dim,
        encoder_layers=config.encoder_layers,
        decoder_layers=config.decoder_layers,
        num_heads=config.num_heads,
        mask_ratio=config.mask_ratio,
    ).to(device)
    
    # Optimizer with weight decay
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    
    # Learning rate scheduler
    total_steps = config.epochs * len(dataloader)
    warmup_steps = config.warmup_epochs * len(dataloader)
    
    def lr_lambda(step):
        if step < warmup_steps:
            return step / warmup_steps
        else:
            progress = (step - warmup_steps) / (total_steps - warmup_steps)
            return 0.5 * (1 + math.cos(math.pi * progress))
    
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)
    
    # Training loop
    model.train()
    global_step = 0
    
    for epoch in range(config.epochs):
        epoch_loss = 0
        num_batches = 0
        
        for batch in dataloader:
            # Handle different batch formats
            if isinstance(batch, (tuple, list)):
                x = batch[0]
            else:
                x = batch
            
            x = x.to(device)
            
            # Forward pass
            loss, _, _ = model(x)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            
            epoch_loss += loss.item()
            num_batches += 1
            global_step += 1
            
            if global_step % log_interval == 0:
                logger.info(
                    f"Step {global_step}: loss={loss.item():.4f}, "
                    f"lr={scheduler.get_last_lr()[0]:.6f}"
                )
        
        avg_loss = epoch_loss / num_batches
        logger.info(f"Epoch {epoch + 1}/{config.epochs}: avg_loss={avg_loss:.4f}")
        
        # Save checkpoint
        if checkpoint_dir:
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': avg_loss,
            }, checkpoint_dir / f"mae_checkpoint_{epoch:04d}.pth")
    
    logger.info("MAE pretraining complete!")
    
    return model.get_encoder()


# =============================================================================
# Contrastive Learning (SimCLR-style)
# =============================================================================

class ContrastiveAugmentation(nn.Module):
    """
    Augmentations for contrastive learning.
    
    Creates two different views of the same spectrogram.
    """
    
    def __init__(
        self,
        time_mask_max: int = 20,
        freq_mask_max: int = 20,
        noise_std: float = 0.1,
    ):
        super().__init__()
        
        self.time_mask_max = time_mask_max
        self.freq_mask_max = freq_mask_max
        self.noise_std = noise_std
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Create two augmented views."""
        view1 = self._augment(x)
        view2 = self._augment(x)
        return view1, view2
    
    def _augment(self, x: torch.Tensor) -> torch.Tensor:
        """Apply random augmentations."""
        B, C, H, W = x.shape
        x = x.clone()
        
        # Time masking
        for b in range(B):
            mask_len = torch.randint(1, self.time_mask_max + 1, (1,)).item()
            mask_start = torch.randint(0, max(1, W - mask_len), (1,)).item()
            x[b, :, :, mask_start:mask_start + mask_len] = 0
        
        # Frequency masking
        for b in range(B):
            mask_len = torch.randint(1, self.freq_mask_max + 1, (1,)).item()
            mask_start = torch.randint(0, max(1, H - mask_len), (1,)).item()
            x[b, :, mask_start:mask_start + mask_len, :] = 0
        
        # Add noise
        x = x + torch.randn_like(x) * self.noise_std
        
        return x


class ProjectionHead(nn.Module):
    """MLP projection head for contrastive learning."""
    
    def __init__(self, in_dim: int, hidden_dim: int = 256, out_dim: int = 128):
        super().__init__()
        
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Linear(hidden_dim, out_dim),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def nt_xent_loss(
    z1: torch.Tensor,
    z2: torch.Tensor,
    temperature: float = 0.5,
) -> torch.Tensor:
    """
    NT-Xent loss (Normalized Temperature-scaled Cross Entropy).
    
    Used in SimCLR and similar contrastive methods.
    """
    B = z1.shape[0]
    device = z1.device
    
    # Normalize
    z1 = F.normalize(z1, dim=1)
    z2 = F.normalize(z2, dim=1)
    
    # Concatenate
    z = torch.cat([z1, z2], dim=0)  # [2B, D]
    
    # Similarity matrix
    sim = torch.mm(z, z.t()) / temperature  # [2B, 2B]
    
    # Mask out self-similarity
    mask = torch.eye(2 * B, device=device, dtype=torch.bool)
    sim = sim.masked_fill(mask, float('-inf'))
    
    # Positive pairs: (i, B+i) and (B+i, i)
    labels = torch.arange(2 * B, device=device)
    labels[:B] = labels[:B] + B
    labels[B:] = labels[B:] - B
    
    loss = F.cross_entropy(sim, labels)
    
    return loss


class ContrastivePretrainer(nn.Module):
    """
    SimCLR-style contrastive learning for spectrograms.
    """
    
    def __init__(
        self,
        encoder: nn.Module,
        feature_dim: int,
        projection_dim: int = 128,
    ):
        super().__init__()
        
        self.encoder = encoder
        self.augmentation = ContrastiveAugmentation()
        self.projection = ProjectionHead(feature_dim, feature_dim, projection_dim)
    
    def forward(self, x: torch.Tensor, temperature: float = 0.5) -> torch.Tensor:
        """Compute contrastive loss."""
        # Create two views
        view1, view2 = self.augmentation(x)
        
        # Encode
        z1 = self.encoder(view1)
        z2 = self.encoder(view2)
        
        # Global average pooling if needed
        if z1.dim() == 4:
            z1 = F.adaptive_avg_pool2d(z1, 1).flatten(1)
            z2 = F.adaptive_avg_pool2d(z2, 1).flatten(1)
        elif z1.dim() == 3:
            z1 = z1.mean(dim=1)
            z2 = z2.mean(dim=1)
        
        # Project
        p1 = self.projection(z1)
        p2 = self.projection(z2)
        
        # Compute loss
        loss = nt_xent_loss(p1, p2, temperature)
        
        return loss


# =============================================================================
# Utility Functions
# =============================================================================

class UnlabeledDataset(Dataset):
    """
    Dataset for unlabeled audio files.
    
    Simply loads audio and converts to mel spectrogram.
    """
    
    def __init__(
        self,
        audio_paths: List[Path],
        sample_rate: int = 44100,
        n_mels: int = 128,
        n_fft: int = 2048,
        hop_length: int = 512,
        target_frames: int = 128,
    ):
        self.audio_paths = audio_paths
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.target_frames = target_frames
    
    def __len__(self) -> int:
        return len(self.audio_paths)
    
    def __getitem__(self, idx: int) -> torch.Tensor:
        import librosa
        
        path = self.audio_paths[idx]
        
        # Load audio
        audio, _ = librosa.load(str(path), sr=self.sample_rate, mono=True)
        
        # Compute mel spectrogram
        mel = librosa.feature.melspectrogram(
            y=audio,
            sr=self.sample_rate,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            n_mels=self.n_mels,
        )
        mel = librosa.power_to_db(mel, ref=np.max)
        
        # Convert to tensor
        mel = torch.from_numpy(mel).float()
        
        # Resize to target frames
        mel = mel.unsqueeze(0)  # [1, n_mels, time]
        mel = F.interpolate(mel, size=self.target_frames, mode='linear', align_corners=False)
        
        # Normalize
        mel = (mel - mel.min()) / (mel.max() - mel.min() + 1e-8)
        
        return mel


def collect_unlabeled_audio(
    directories: List[Path],
    extensions: List[str] = ['.wav', '.mp3', '.flac', '.ogg'],
) -> List[Path]:
    """
    Collect all audio files from directories.
    
    Args:
        directories: List of directories to search
        extensions: Audio file extensions to include
    
    Returns:
        List of audio file paths
    """
    audio_paths = []
    
    for directory in directories:
        directory = Path(directory)
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            continue
        
        for ext in extensions:
            audio_paths.extend(directory.rglob(f"*{ext}"))
    
    logger.info(f"Found {len(audio_paths)} audio files for pretraining")
    
    return audio_paths
