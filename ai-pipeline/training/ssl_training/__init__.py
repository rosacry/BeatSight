"""
Self-Supervised Learning (SSL) for Drum Classification

This package provides self-supervised pretraining methods for learning
powerful representations from unlabeled audio data.

Available Methods:
- MAE (Masked Autoencoder): Mask and reconstruct spectrogram patches
- Contrastive (SimCLR-style): Learn by comparing augmented views
- DINO: Self-distillation without labels (coming soon)

Usage:
    from training.ssl_training import pretrain_mae, MaskedAutoencoder, UnlabeledDataset
    
    # Collect unlabeled data
    audio_paths = collect_unlabeled_audio([Path("data/unlabeled")])
    dataset = UnlabeledDataset(audio_paths)
    loader = DataLoader(dataset, batch_size=64, shuffle=True)
    
    # Pretrain
    encoder = pretrain_mae(loader, config, device)
    
    # Use pretrained encoder for classification
    classifier = build_classifier_with_pretrained(encoder, num_classes=21)
"""

from .pretrain import (
    # MAE
    MaskedAutoencoder,
    MAEEncoder,
    MAEDecoder,
    MAEPretrainingConfig,
    pretrain_mae,
    
    # Contrastive
    ContrastivePretrainer,
    ContrastiveAugmentation,
    ProjectionHead,
    nt_xent_loss,
    
    # Utilities
    UnlabeledDataset,
    collect_unlabeled_audio,
)

__all__ = [
    # MAE
    'MaskedAutoencoder',
    'MAEEncoder',
    'MAEDecoder',
    'MAEPretrainingConfig',
    'pretrain_mae',
    
    # Contrastive
    'ContrastivePretrainer',
    'ContrastiveAugmentation',
    'ProjectionHead',
    'nt_xent_loss',
    
    # Utilities
    'UnlabeledDataset',
    'collect_unlabeled_audio',
]
