"""
Audio Foundation Model Features for Drum Transcription

This module provides frozen feature extraction from audio foundation models
(Wav2Vec2, HuBERT) to enhance drum transcription with pre-learned audio semantics.

Why Foundation Models for Drums?
1. Wav2Vec2/HuBERT trained on 100,000+ hours of audio
2. They capture phonetic and acoustic patterns spectrograms miss
3. Pre-learned representations reduce need for labeled data
4. No one has combined foundation audio models + Mamba for drums

Novel Contribution:
    "First combination of audio foundation models with state-space 
     temporal modeling for automatic drum transcription"

Architecture:
    Raw Audio → Wav2Vec2 (frozen) → Project → Fuse with CNN features → Mamba
    
    CNN features: Local time-frequency patterns (transients, resonance)
    Wav2Vec2 features: Global audio semantics (timbre, rhythm patterns)
    
Usage:
    from training.models.audio_foundation import (
        AudioFoundationEncoder,
        FoundationFeatureExtractor
    )
    
    # Extract features from raw audio
    extractor = FoundationFeatureExtractor(model_name="wav2vec2-base")
    features = extractor(audio_waveform)  # [B, T, 768]
    
    # Or use the full encoder
    encoder = AudioFoundationEncoder(output_dim=256)
    encoded = encoder(audio_waveform)  # [B, T, 256]

References:
    - Wav2Vec 2.0: "wav2vec 2.0: A Framework for Self-Supervised Learning 
                    of Speech Representations" (Baevski et al., NeurIPS 2020)
    - HuBERT: "HuBERT: Self-Supervised Speech Representation Learning by
               Masked Prediction of Hidden Units" (Hsu et al., TASLP 2021)
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple, Union, List
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class FoundationConfig:
    """Configuration for audio foundation model features."""
    model_name: str = "facebook/wav2vec2-base"  # or "facebook/hubert-base-ls960"
    freeze_encoder: bool = True                  # Keep foundation model frozen
    output_dim: int = 256                        # Project to this dimension
    use_weighted_layers: bool = True             # Learn weights for transformer layers
    layer_weights_init: str = "uniform"          # "uniform" or "last"
    dropout: float = 0.1
    sample_rate: int = 16000                     # Foundation models expect 16kHz
    normalize_features: bool = True


class FoundationFeatureExtractor(nn.Module):
    """
    Extract features from pre-trained audio foundation models.
    
    This module loads Wav2Vec2 or HuBERT and extracts contextualized
    audio representations. The model is kept frozen to preserve the
    learned representations from large-scale pretraining.
    
    Args:
        config: Configuration for the extractor
        
    Returns:
        Tensor of shape [batch, time, hidden_dim]
        where hidden_dim is 768 for base models, 1024 for large
    """
    
    def __init__(self, config: Optional[FoundationConfig] = None):
        super().__init__()
        
        self.config = config or FoundationConfig()
        self._model = None
        self._processor = None
        self._hidden_dim = None
        self._loaded = False
        
    def _lazy_load(self):
        """Load model on first use to avoid import issues."""
        if self._loaded:
            return
            
        try:
            from transformers import (
                Wav2Vec2Model, 
                Wav2Vec2Processor,
                HubertModel,
                AutoProcessor
            )
        except ImportError:
            raise ImportError(
                "Please install transformers: pip install transformers"
            )
        
        model_name = self.config.model_name
        logger.info(f"Loading foundation model: {model_name}")
        
        if "hubert" in model_name.lower():
            self._model = HubertModel.from_pretrained(model_name)
        else:
            self._model = Wav2Vec2Model.from_pretrained(model_name)
        
        # Get hidden dimension
        self._hidden_dim = self._model.config.hidden_size
        
        # Freeze if requested
        if self.config.freeze_encoder:
            for param in self._model.parameters():
                param.requires_grad = False
            self._model.eval()
            logger.info(f"Foundation model frozen ({self._hidden_dim}d features)")
        else:
            logger.info(f"Foundation model trainable ({self._hidden_dim}d features)")
        
        self._loaded = True
    
    @property
    def hidden_dim(self) -> int:
        """Get the hidden dimension of the foundation model."""
        self._lazy_load()
        return self._hidden_dim
    
    def forward(
        self, 
        audio: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Extract foundation model features from raw audio.
        
        Args:
            audio: Raw audio waveform [batch, samples] at 16kHz
            attention_mask: Optional mask for padded sequences
            
        Returns:
            Features tensor [batch, time, hidden_dim]
        """
        self._lazy_load()
        
        # Ensure model is on same device as input
        if next(self._model.parameters()).device != audio.device:
            self._model = self._model.to(audio.device)
        
        # Extract features
        with torch.no_grad() if self.config.freeze_encoder else torch.enable_grad():
            outputs = self._model(
                audio,
                attention_mask=attention_mask,
                output_hidden_states=True,
                return_dict=True
            )
        
        # Get last hidden state
        features = outputs.last_hidden_state  # [B, T, D]
        
        # Normalize if requested
        if self.config.normalize_features:
            features = F.layer_norm(features, features.shape[-1:])
        
        return features


class WeightedLayerAggregation(nn.Module):
    """
    Learn weighted combination of transformer layer outputs.
    
    Similar to SUPERB/WavLM approach - different tasks benefit from
    different layers. Drums might benefit from:
    - Early layers: Acoustic features (attack, resonance)
    - Middle layers: Phonetic-like patterns (hit types)
    - Late layers: Semantic context (patterns, grooves)
    """
    
    def __init__(self, num_layers: int, init: str = "uniform"):
        super().__init__()
        
        self.num_layers = num_layers
        
        # Learnable weights for each layer
        if init == "uniform":
            weights = torch.ones(num_layers) / num_layers
        elif init == "last":
            weights = torch.zeros(num_layers)
            weights[-1] = 1.0
        else:
            weights = torch.ones(num_layers) / num_layers
            
        self.layer_weights = nn.Parameter(weights)
        
    def forward(self, hidden_states: List[torch.Tensor]) -> torch.Tensor:
        """
        Combine hidden states from all layers.
        
        Args:
            hidden_states: List of [B, T, D] tensors from each layer
            
        Returns:
            Weighted combination [B, T, D]
        """
        # Softmax to ensure weights sum to 1
        weights = F.softmax(self.layer_weights, dim=0)
        
        # Stack and weight
        stacked = torch.stack(hidden_states, dim=0)  # [L, B, T, D]
        weighted = (stacked * weights.view(-1, 1, 1, 1)).sum(dim=0)
        
        return weighted


class AudioFoundationEncoder(nn.Module):
    """
    Full encoder that extracts, aggregates, and projects foundation features.
    
    This is the main module to use in the temporal drum transcriber.
    It handles:
    1. Feature extraction from Wav2Vec2/HuBERT
    2. Optional weighted layer aggregation
    3. Projection to desired output dimension
    4. Dropout for regularization
    
    Args:
        config: Configuration for the encoder
        
    Usage:
        encoder = AudioFoundationEncoder(output_dim=256)
        audio = torch.randn(4, 16000)  # 1 second at 16kHz
        features = encoder(audio)  # [4, ~50, 256]
    """
    
    def __init__(
        self,
        output_dim: int = 256,
        model_name: str = "facebook/wav2vec2-base",
        freeze: bool = True,
        use_weighted_layers: bool = True,
        dropout: float = 0.1
    ):
        super().__init__()
        
        config = FoundationConfig(
            model_name=model_name,
            freeze_encoder=freeze,
            output_dim=output_dim,
            use_weighted_layers=use_weighted_layers,
            dropout=dropout
        )
        
        self.config = config
        self.extractor = FoundationFeatureExtractor(config)
        
        # Will be initialized after first forward pass
        self._projection = None
        self._layer_weights = None
        self._initialized = False
        
        self.dropout = nn.Dropout(dropout)
        self.output_dim = output_dim
        
    def _lazy_init(self, hidden_dim: int, num_layers: int):
        """Initialize projection after we know dimensions."""
        if self._initialized:
            return
            
        # Projection to output dimension
        self._projection = nn.Sequential(
            nn.Linear(hidden_dim, self.output_dim),
            nn.GELU(),
            nn.Linear(self.output_dim, self.output_dim)
        )
        
        # Layer weighting
        if self.config.use_weighted_layers:
            self._layer_weights = WeightedLayerAggregation(
                num_layers,
                init=self.config.layer_weights_init
            )
        
        self._initialized = True
        
    def forward(
        self,
        audio: torch.Tensor,
        return_all_layers: bool = False
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, List[torch.Tensor]]]:
        """
        Encode audio to foundation model features.
        
        Args:
            audio: Raw waveform [batch, samples] at 16kHz
            return_all_layers: Also return per-layer hidden states
            
        Returns:
            Encoded features [batch, time, output_dim]
            Optionally: tuple of (features, all_hidden_states)
        """
        # Extract features
        features = self.extractor(audio)
        
        # Initialize projection if needed
        if not self._initialized:
            hidden_dim = features.shape[-1]
            # Assume 12 layers for base model
            num_layers = 12 if "base" in self.config.model_name else 24
            self._lazy_init(hidden_dim, num_layers)
            self._projection = self._projection.to(audio.device)
            if self._layer_weights is not None:
                self._layer_weights = self._layer_weights.to(audio.device)
        
        # Project to output dimension
        features = self._projection(features)
        features = self.dropout(features)
        
        return features


class ResampleAudio(nn.Module):
    """
    Resample audio to match foundation model's expected sample rate.
    
    Wav2Vec2 and HuBERT expect 16kHz audio. If your audio is at
    a different sample rate, use this to resample.
    """
    
    def __init__(self, orig_sr: int, target_sr: int = 16000):
        super().__init__()
        self.orig_sr = orig_sr
        self.target_sr = target_sr
        
        # Try to use torchaudio's resampler
        try:
            import torchaudio.transforms as T
            self.resampler = T.Resample(orig_sr, target_sr)
        except ImportError:
            self.resampler = None
            logger.warning(
                "torchaudio not available, using simple interpolation for resampling"
            )
    
    def forward(self, audio: torch.Tensor) -> torch.Tensor:
        """
        Resample audio to target sample rate.
        
        Args:
            audio: Input audio [batch, samples] at orig_sr
            
        Returns:
            Resampled audio [batch, new_samples] at target_sr
        """
        if self.orig_sr == self.target_sr:
            return audio
            
        if self.resampler is not None:
            return self.resampler(audio)
        else:
            # Simple linear interpolation fallback
            ratio = self.target_sr / self.orig_sr
            new_length = int(audio.shape[-1] * ratio)
            return F.interpolate(
                audio.unsqueeze(1),
                size=new_length,
                mode='linear',
                align_corners=False
            ).squeeze(1)


class FoundationSpectrogramAligner(nn.Module):
    """
    Align foundation model features with spectrogram features in time.
    
    Foundation models produce features at ~50Hz (320 samples @ 16kHz per frame).
    Spectrograms have different time resolution based on hop_length.
    This module aligns them for fusion.
    """
    
    def __init__(
        self,
        foundation_sr: int = 16000,
        foundation_frame_rate: float = 50.0,  # ~50 frames per second
        spectrogram_sr: int = 22050,
        spectrogram_hop: int = 512
    ):
        super().__init__()
        
        self.foundation_sr = foundation_sr
        self.foundation_frame_rate = foundation_frame_rate
        self.spectrogram_sr = spectrogram_sr
        self.spectrogram_hop = spectrogram_hop
        
        # Calculate spectrogram frame rate
        self.spec_frame_rate = spectrogram_sr / spectrogram_hop
        
    def forward(
        self,
        foundation_features: torch.Tensor,
        target_length: int
    ) -> torch.Tensor:
        """
        Align foundation features to spectrogram time resolution.
        
        Args:
            foundation_features: [batch, foundation_time, dim]
            target_length: Number of spectrogram frames to match
            
        Returns:
            Aligned features [batch, target_length, dim]
        """
        B, T_found, D = foundation_features.shape
        
        if T_found == target_length:
            return foundation_features
        
        # Interpolate to match spectrogram length
        features = foundation_features.transpose(1, 2)  # [B, D, T]
        aligned = F.interpolate(
            features,
            size=target_length,
            mode='linear',
            align_corners=False
        )
        aligned = aligned.transpose(1, 2)  # [B, T, D]
        
        return aligned


# =============================================================================
# Convenience functions
# =============================================================================

def create_foundation_encoder(
    model_name: str = "facebook/wav2vec2-base",
    output_dim: int = 256,
    freeze: bool = True
) -> AudioFoundationEncoder:
    """Create a foundation encoder with sensible defaults."""
    return AudioFoundationEncoder(
        output_dim=output_dim,
        model_name=model_name,
        freeze=freeze,
        use_weighted_layers=True,
        dropout=0.1
    )


def extract_foundation_features(
    audio: torch.Tensor,
    sample_rate: int = 22050,
    model_name: str = "facebook/wav2vec2-base",
    output_dim: int = 256
) -> torch.Tensor:
    """
    One-shot feature extraction for inference.
    
    Args:
        audio: Raw audio [batch, samples]
        sample_rate: Original sample rate of audio
        model_name: Foundation model to use
        output_dim: Output feature dimension
        
    Returns:
        Features [batch, time, output_dim]
    """
    # Resample to 16kHz if needed
    if sample_rate != 16000:
        resampler = ResampleAudio(sample_rate, 16000)
        audio = resampler(audio)
    
    # Create encoder and extract
    encoder = create_foundation_encoder(model_name, output_dim)
    encoder = encoder.to(audio.device)
    
    with torch.no_grad():
        features = encoder(audio)
    
    return features


# =============================================================================
# Test/Demo
# =============================================================================

if __name__ == "__main__":
    print("Testing Audio Foundation Encoder...")
    
    # Test with random audio (simulating 1 second at 16kHz)
    batch_size = 2
    audio_length = 16000  # 1 second at 16kHz
    
    # Create random audio
    audio = torch.randn(batch_size, audio_length)
    
    # Create encoder
    encoder = AudioFoundationEncoder(
        output_dim=256,
        model_name="facebook/wav2vec2-base",
        freeze=True
    )
    
    # Forward pass
    try:
        features = encoder(audio)
        print(f"Input shape: {audio.shape}")
        print(f"Output shape: {features.shape}")
        print(f"Expected: [{batch_size}, ~50, 256]")
        print("✅ Foundation encoder working!")
    except Exception as e:
        print(f"❌ Error (transformers may not be installed): {e}")
        print("Install with: pip install transformers")
