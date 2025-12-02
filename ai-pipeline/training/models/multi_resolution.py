"""
Multi-Resolution Spectrogram Module for Drum Transcription

This module provides multi-scale time-frequency representations for
enhanced drum transcription. Different frequency resolutions capture
different aspects of drum sounds:

- Low resolution (large FFT): Bass drum resonance, room acoustics
- High resolution (small FFT): Transient attacks, stick sounds
- Standard resolution: Balanced for most drum types

Why Multi-Resolution for Drums?
1. Drums have both sharp transients (need high time resolution)
   and low-frequency content (need high frequency resolution)
2. Single spectrogram can't optimize for both
3. Multi-res lets the model learn to attend to appropriate scale

Novel Contribution:
    Multi-scale spectrograms combined with Mamba temporal modeling
    - Each scale captures different drum characteristics
    - Attention-based fusion learns optimal weighting
    
Expected Improvement: +1-3% on transient detection (ghost notes, rimshots)

Architecture:
    Audio → [Mel_Low, Mel_Mid, Mel_High] → CNN per scale → Fuse → Features
    
    Mel_Low:  n_fft=4096, hop=1024, n_mels=64  (bass, resonance)
    Mel_Mid:  n_fft=2048, hop=512,  n_mels=128 (balanced)
    Mel_High: n_fft=1024, hop=256,  n_mels=128 (transients)

Usage:
    from training.models.multi_resolution import (
        MultiResolutionMelSpectrogram,
        MultiResEncoder
    )
    
    # Create multi-res spectrograms
    mel_transform = MultiResolutionMelSpectrogram(sample_rate=22050)
    specs = mel_transform(audio)  # Dict of spectrograms
    
    # Or use the full encoder
    encoder = MultiResEncoder(output_dim=256)
    features = encoder(audio)  # [B, T, 256]
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Try to import torchaudio for efficient transforms
try:
    import torchaudio
    import torchaudio.transforms as T
    HAS_TORCHAUDIO = True
except ImportError:
    HAS_TORCHAUDIO = False

# Fallback to librosa-style computation
try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


@dataclass
class ResolutionConfig:
    """Configuration for a single resolution."""
    name: str
    n_fft: int
    hop_length: int
    n_mels: int
    fmin: float = 20.0
    fmax: Optional[float] = None  # None = sr/2


@dataclass
class MultiResConfig:
    """Configuration for multi-resolution spectrograms."""
    sample_rate: int = 22050
    
    # Default resolutions optimized for drums
    resolutions: Tuple[ResolutionConfig, ...] = (
        ResolutionConfig(
            name="low",
            n_fft=4096,
            hop_length=1024,
            n_mels=64,
            fmin=20.0,
            fmax=2000.0  # Focus on bass
        ),
        ResolutionConfig(
            name="mid",
            n_fft=2048,
            hop_length=512,
            n_mels=128,
            fmin=20.0,
            fmax=None  # Full range
        ),
        ResolutionConfig(
            name="high",
            n_fft=1024,
            hop_length=256,
            n_mels=128,
            fmin=1000.0,
            fmax=None  # Focus on high frequencies
        ),
    )
    
    # Fusion settings
    fusion_method: str = "attention"  # "attention", "concat", "sum"
    normalize_specs: bool = True
    target_time_frames: Optional[int] = 128  # Align all specs to this length


class MultiResolutionMelSpectrogram(nn.Module):
    """
    Compute mel spectrograms at multiple resolutions.
    
    Returns a dictionary of spectrograms, each optimized for
    different frequency ranges and time resolutions.
    """
    
    def __init__(
        self,
        config: Optional[MultiResConfig] = None,
        sample_rate: int = 22050
    ):
        super().__init__()
        
        if config is None:
            config = MultiResConfig(sample_rate=sample_rate)
        
        self.config = config
        self.sample_rate = config.sample_rate
        
        # Create mel transforms for each resolution
        self.transforms = nn.ModuleDict()
        
        for res in config.resolutions:
            fmax = res.fmax or (config.sample_rate // 2)
            
            if HAS_TORCHAUDIO:
                self.transforms[res.name] = T.MelSpectrogram(
                    sample_rate=config.sample_rate,
                    n_fft=res.n_fft,
                    hop_length=res.hop_length,
                    n_mels=res.n_mels,
                    f_min=res.fmin,
                    f_max=fmax,
                    power=2.0,
                    normalized=True
                )
            else:
                # Store config for librosa fallback
                self.transforms[res.name] = None
                
        self._res_configs = {r.name: r for r in config.resolutions}
        
    def forward(self, audio: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Compute multi-resolution mel spectrograms.
        
        Args:
            audio: Raw audio waveform [batch, samples]
            
        Returns:
            Dictionary mapping resolution name to spectrogram
            Each spectrogram has shape [batch, 1, n_mels, time]
        """
        specs = {}
        
        for name, transform in self.transforms.items():
            if transform is not None:
                # Use torchaudio
                spec = transform(audio)  # [B, n_mels, T]
                
                # Convert to log scale
                spec = torch.log(spec + 1e-8)
                
                # Normalize if requested
                if self.config.normalize_specs:
                    spec = (spec - spec.mean(dim=(-2, -1), keepdim=True)) / \
                           (spec.std(dim=(-2, -1), keepdim=True) + 1e-8)
                
                # Add channel dimension
                spec = spec.unsqueeze(1)  # [B, 1, n_mels, T]
                
            else:
                # Librosa fallback (slower, CPU only)
                spec = self._librosa_mel(audio, self._res_configs[name])
            
            specs[name] = spec
        
        return specs
    
    def _librosa_mel(
        self, 
        audio: torch.Tensor, 
        res: ResolutionConfig
    ) -> torch.Tensor:
        """Fallback using librosa."""
        if not HAS_LIBROSA:
            raise ImportError("Neither torchaudio nor librosa available")
        
        device = audio.device
        audio_np = audio.cpu().numpy()
        
        specs = []
        for a in audio_np:
            S = librosa.feature.melspectrogram(
                y=a,
                sr=self.sample_rate,
                n_fft=res.n_fft,
                hop_length=res.hop_length,
                n_mels=res.n_mels,
                fmin=res.fmin,
                fmax=res.fmax or (self.sample_rate // 2)
            )
            S = librosa.power_to_db(S, ref=np.max)
            specs.append(S)
        
        specs = torch.from_numpy(np.stack(specs)).to(device)
        specs = specs.unsqueeze(1)  # [B, 1, n_mels, T]
        
        return specs


class ResolutionCNN(nn.Module):
    """
    Small CNN to encode a single resolution spectrogram.
    
    Produces a sequence of feature vectors for temporal modeling.
    """
    
    def __init__(
        self,
        n_mels: int,
        output_dim: int = 128,
        channels: List[int] = [32, 64, 128]
    ):
        super().__init__()
        
        layers = []
        in_channels = 1
        
        for out_channels in channels:
            layers.extend([
                nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
                nn.BatchNorm2d(out_channels),
                nn.GELU(),
                nn.MaxPool2d(kernel_size=(2, 1))  # Pool frequency, preserve time
            ])
            in_channels = out_channels
        
        self.conv = nn.Sequential(*layers)
        
        # Calculate output frequency dimension after pooling
        freq_dim = n_mels // (2 ** len(channels))
        self.fc = nn.Linear(channels[-1] * freq_dim, output_dim)
        
        self.output_dim = output_dim
        
    def forward(self, spec: torch.Tensor) -> torch.Tensor:
        """
        Encode spectrogram to feature sequence.
        
        Args:
            spec: Spectrogram [batch, 1, n_mels, time]
            
        Returns:
            Features [batch, time, output_dim]
        """
        # Conv expects [B, C, H, W] = [B, 1, n_mels, time]
        x = self.conv(spec)  # [B, C, H', T]
        
        B, C, H, T = x.shape
        
        # Reshape for linear: merge channels and remaining frequency
        x = x.permute(0, 3, 1, 2)  # [B, T, C, H']
        x = x.reshape(B, T, -1)  # [B, T, C*H']
        
        # Project to output dimension
        x = self.fc(x)  # [B, T, output_dim]
        
        return x


class MultiResFusion(nn.Module):
    """
    Fuse features from multiple resolutions.
    
    Uses attention to learn optimal weighting of different scales
    for each time step.
    """
    
    def __init__(
        self,
        input_dims: Dict[str, int],
        output_dim: int = 256,
        fusion_method: str = "attention"
    ):
        super().__init__()
        
        self.input_dims = input_dims
        self.output_dim = output_dim
        self.fusion_method = fusion_method
        self.num_scales = len(input_dims)
        
        # Project each scale to same dimension for fusion
        self.projections = nn.ModuleDict({
            name: nn.Linear(dim, output_dim)
            for name, dim in input_dims.items()
        })
        
        if fusion_method == "attention":
            # Attention-based fusion
            self.scale_attention = nn.Sequential(
                nn.Linear(output_dim * self.num_scales, output_dim),
                nn.GELU(),
                nn.Linear(output_dim, self.num_scales),
                nn.Softmax(dim=-1)
            )
        elif fusion_method == "concat":
            # Simple concatenation with projection
            self.concat_proj = nn.Linear(output_dim * self.num_scales, output_dim)
    
    def forward(self, features: Dict[str, torch.Tensor]) -> torch.Tensor:
        """
        Fuse multi-resolution features.
        
        Args:
            features: Dict mapping resolution name to features [B, T, D]
            
        Returns:
            Fused features [batch, time, output_dim]
        """
        # Project all scales to same dimension
        projected = {
            name: self.projections[name](feat)
            for name, feat in features.items()
        }
        
        # Stack for fusion
        names = sorted(projected.keys())
        stacked = torch.stack([projected[n] for n in names], dim=2)  # [B, T, num_scales, D]
        
        B, T, S, D = stacked.shape
        
        if self.fusion_method == "attention":
            # Compute attention weights per time step
            flat = stacked.reshape(B, T, -1)  # [B, T, S*D]
            weights = self.scale_attention(flat)  # [B, T, S]
            
            # Weighted sum
            weighted = (stacked * weights.unsqueeze(-1)).sum(dim=2)  # [B, T, D]
            return weighted
            
        elif self.fusion_method == "concat":
            flat = stacked.reshape(B, T, -1)
            return self.concat_proj(flat)
            
        else:  # sum
            return stacked.mean(dim=2)


class MultiResEncoder(nn.Module):
    """
    Full multi-resolution encoder for audio.
    
    Computes spectrograms at multiple resolutions, encodes each
    with a small CNN, and fuses them with attention.
    
    This is the main module to use in the temporal drum transcriber.
    
    Args:
        sample_rate: Audio sample rate
        output_dim: Output feature dimension
        fusion_method: How to combine resolutions
        
    Usage:
        encoder = MultiResEncoder(sample_rate=22050, output_dim=256)
        audio = torch.randn(4, 22050)  # 1 second
        features = encoder(audio)  # [4, T, 256]
    """
    
    def __init__(
        self,
        sample_rate: int = 22050,
        output_dim: int = 256,
        per_scale_dim: int = 128,
        fusion_method: str = "attention",
        target_time_frames: Optional[int] = None
    ):
        super().__init__()
        
        self.config = MultiResConfig(
            sample_rate=sample_rate,
            fusion_method=fusion_method,
            target_time_frames=target_time_frames
        )
        
        # Multi-resolution spectrogram computation
        self.mel_transform = MultiResolutionMelSpectrogram(self.config)
        
        # Per-resolution CNNs
        self.encoders = nn.ModuleDict()
        input_dims = {}
        
        for res in self.config.resolutions:
            self.encoders[res.name] = ResolutionCNN(
                n_mels=res.n_mels,
                output_dim=per_scale_dim
            )
            input_dims[res.name] = per_scale_dim
        
        # Fusion layer
        self.fusion = MultiResFusion(
            input_dims=input_dims,
            output_dim=output_dim,
            fusion_method=fusion_method
        )
        
        self.output_dim = output_dim
        self.target_time_frames = target_time_frames
        
    def forward(self, audio: torch.Tensor) -> torch.Tensor:
        """
        Encode audio to multi-resolution features.
        
        Args:
            audio: Raw waveform [batch, samples]
            
        Returns:
            Fused features [batch, time, output_dim]
        """
        # Compute spectrograms
        specs = self.mel_transform(audio)
        
        # Encode each resolution
        encoded = {}
        for name, spec in specs.items():
            encoded[name] = self.encoders[name](spec)
        
        # Align time dimensions if they differ
        if self.target_time_frames is not None:
            aligned = {}
            for name, feat in encoded.items():
                if feat.shape[1] != self.target_time_frames:
                    feat = F.interpolate(
                        feat.transpose(1, 2),
                        size=self.target_time_frames,
                        mode='linear',
                        align_corners=False
                    ).transpose(1, 2)
                aligned[name] = feat
            encoded = aligned
        else:
            # Align to shortest
            min_len = min(f.shape[1] for f in encoded.values())
            encoded = {n: f[:, :min_len] for n, f in encoded.items()}
        
        # Fuse resolutions
        fused = self.fusion(encoded)
        
        return fused


class PrecomputedMultiResDataset:
    """
    Helper to precompute multi-resolution spectrograms for training.
    
    Computing spectrograms on-the-fly is expensive. For training,
    it's faster to precompute and cache them.
    """
    
    def __init__(
        self,
        audio_dir: str,
        cache_dir: str,
        sample_rate: int = 22050
    ):
        self.audio_dir = audio_dir
        self.cache_dir = cache_dir
        self.transform = MultiResolutionMelSpectrogram(
            config=MultiResConfig(sample_rate=sample_rate)
        )
    
    def precompute(self):
        """Precompute all spectrograms and save to cache."""
        from pathlib import Path
        from tqdm import tqdm
        
        audio_dir = Path(self.audio_dir)
        cache_dir = Path(self.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        audio_files = list(audio_dir.rglob("*.wav"))
        
        for audio_file in tqdm(audio_files, desc="Precomputing multi-res specs"):
            # Load audio
            if HAS_TORCHAUDIO:
                audio, sr = torchaudio.load(audio_file)
            else:
                import soundfile as sf
                audio, sr = sf.read(audio_file)
                audio = torch.from_numpy(audio).float()
                if audio.dim() == 1:
                    audio = audio.unsqueeze(0)
            
            # Compute spectrograms
            with torch.no_grad():
                specs = self.transform(audio)
            
            # Save
            rel_path = audio_file.relative_to(audio_dir)
            save_path = cache_dir / rel_path.with_suffix('.pt')
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            torch.save({
                name: spec.cpu() for name, spec in specs.items()
            }, save_path)


# =============================================================================
# Convenience functions
# =============================================================================

def create_multi_res_encoder(
    sample_rate: int = 22050,
    output_dim: int = 256
) -> MultiResEncoder:
    """Create a multi-resolution encoder with sensible defaults."""
    return MultiResEncoder(
        sample_rate=sample_rate,
        output_dim=output_dim,
        per_scale_dim=128,
        fusion_method="attention"
    )


# =============================================================================
# Test/Demo
# =============================================================================

if __name__ == "__main__":
    print("Testing Multi-Resolution Encoder...")
    
    # Test with random audio
    batch_size = 2
    sample_rate = 22050
    audio_length = sample_rate  # 1 second
    
    audio = torch.randn(batch_size, audio_length)
    
    # Create encoder
    encoder = MultiResEncoder(
        sample_rate=sample_rate,
        output_dim=256
    )
    
    # Forward pass
    try:
        features = encoder(audio)
        print(f"Input shape: {audio.shape}")
        print(f"Output shape: {features.shape}")
        print("✅ Multi-resolution encoder working!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
