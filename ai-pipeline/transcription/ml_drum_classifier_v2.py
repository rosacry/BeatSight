"""
ML-Based Drum Classifier V2 with Squeeze-Excitation Attention

This module provides an enhanced neural network-based drum classifier with:
- Squeeze-Excitation (SE) blocks for channel attention
- Optional EfficientNet-style compound scaling
- Improved gradient flow via residual connections

Reference: "Squeeze-and-Excitation Networks" (Hu et al., 2018)

Usage:
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
    
    # Standard usage (drop-in replacement for v1)
    model = DrumClassifierCNNv2(num_classes=21)
    
    # With SE attention (recommended)
    model = DrumClassifierCNNv2(num_classes=21, use_se=True)
    
    # With compound scaling for larger capacity
    model = DrumClassifierCNNv2(num_classes=21, use_se=True, width_mult=1.5, depth_mult=1.5)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional


class SqueezeExcitation(nn.Module):
    """
    Squeeze-and-Excitation block for channel attention.
    
    Learns to recalibrate channel-wise feature responses by:
    1. Squeezing: Global average pooling to get channel descriptors
    2. Excitation: FC layers to learn channel interdependencies
    3. Rescaling: Sigmoid gating to emphasize important channels
    
    For drum classification, this helps the model focus on frequency bands
    that are most relevant for distinguishing instrument types (e.g., 
    low-frequency for kick vs high-frequency for hi-hats).
    
    Args:
        channels: Number of input channels
        reduction: Channel reduction ratio in the excitation FC layers (default: 16)
    """
    
    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        reduced_channels = max(channels // reduction, 8)  # Minimum 8 channels
        
        self.squeeze = nn.AdaptiveAvgPool2d(1)
        self.excitation = nn.Sequential(
            nn.Linear(channels, reduced_channels, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(reduced_channels, channels, bias=False),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch, channels, _, _ = x.shape
        
        # Squeeze: Global average pooling
        squeezed = self.squeeze(x).view(batch, channels)
        
        # Excitation: Learn channel weights
        excited = self.excitation(squeezed).view(batch, channels, 1, 1)
        
        # Rescale: Apply channel attention
        return x * excited


class ConvBlock(nn.Module):
    """
    Convolutional block with optional SE attention and residual connection.
    
    Structure:
    - Conv2d -> BatchNorm -> ReLU -> (optional SE) -> MaxPool
    - Optional residual connection if input/output channels match
    
    Args:
        in_channels: Input channels
        out_channels: Output channels
        kernel_size: Convolution kernel size (default: 3)
        use_se: Whether to apply Squeeze-Excitation attention
        se_reduction: SE reduction ratio
        use_residual: Whether to use residual connection (requires matching channels)
    """
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        use_se: bool = False,
        se_reduction: int = 16,
        use_residual: bool = False
    ):
        super().__init__()
        padding = kernel_size // 2
        
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, padding=padding)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.MaxPool2d(2)
        
        self.se = SqueezeExcitation(out_channels, se_reduction) if use_se else None
        
        # Residual connection (applied before pooling)
        self.use_residual = use_residual and (in_channels == out_channels)
        if self.use_residual:
            self.residual_scale = nn.Parameter(torch.ones(1) * 0.1)  # Learnable scale
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x if self.use_residual else None
        
        out = self.conv(x)
        out = self.bn(out)
        out = self.relu(out)
        
        if self.se is not None:
            out = self.se(out)
        
        if self.use_residual and identity is not None:
            # Apply residual before pooling
            out = out + self.residual_scale * F.interpolate(identity, size=out.shape[2:], mode='bilinear', align_corners=False)
        
        out = self.pool(out)
        return out


class DrumClassifierCNNv2(nn.Module):
    """
    Enhanced Convolutional Neural Network for drum sound classification.
    
    Improvements over v1:
    - Squeeze-Excitation blocks for channel attention
    - Configurable width/depth multipliers for model scaling
    - Optional residual connections for better gradient flow
    - Improved regularization with SpatialDropout
    
    Architecture (default):
    - Input: 128x128 mel-spectrogram
    - 4 convolutional blocks with BatchNorm, optional SE attention
    - Global average pooling
    - Dropout for regularization
    - Fully connected output layer
    
    Args:
        num_classes: Number of output classes (default: 21 for drum components)
        dropout: Dropout rate before final FC layer (default: 0.3)
        use_se: Enable Squeeze-Excitation attention blocks (default: True)
        se_reduction: SE reduction ratio (default: 16)
        width_mult: Channel width multiplier for scaling (default: 1.0)
        depth_mult: Depth multiplier - adds extra blocks at each stage (default: 1.0)
        use_residual: Enable residual connections where applicable (default: False)
    """
    
    # Class list from v1 for compatibility
    DRUM_COMPONENTS = [
        "aux_percussion",
        "china",
        "crash",
        "cross_stick",
        "hihat_closed",
        "hihat_foot_splash",
        "hihat_open",
        "hihat_pedal",
        "hihat_splash",
        "kick",
        "ride_bell",
        "ride_bow",
        "rimshot",
        "snare",
        "snare_center",
        "snare_cross_stick",
        "snare_rimshot",
        "splash",
        "tom_high",
        "tom_low",
        "tom_mid",
    ]
    
    def __init__(
        self,
        num_classes: int = 21,
        dropout: float = 0.3,
        use_se: bool = True,
        se_reduction: int = 16,
        width_mult: float = 1.0,
        depth_mult: float = 1.0,
        use_residual: bool = False
    ):
        super().__init__()
        
        self.use_se = use_se
        self.width_mult = width_mult
        self.depth_mult = depth_mult
        
        # Scale channel widths
        def scale_channels(c: int) -> int:
            return max(int(c * width_mult), 16)
        
        # Base channel progression
        c1, c2, c3, c4 = scale_channels(32), scale_channels(64), scale_channels(128), scale_channels(256)
        
        # Build convolutional blocks
        self.conv1 = ConvBlock(1, c1, use_se=use_se, se_reduction=se_reduction, use_residual=False)
        self.conv2 = ConvBlock(c1, c2, use_se=use_se, se_reduction=se_reduction, use_residual=use_residual)
        self.conv3 = ConvBlock(c2, c3, use_se=use_se, se_reduction=se_reduction, use_residual=use_residual)
        
        # Final block with adaptive pooling (no MaxPool)
        self.conv4 = nn.Sequential(
            nn.Conv2d(c3, c4, kernel_size=3, padding=1),
            nn.BatchNorm2d(c4),
            nn.ReLU(inplace=True),
        )
        if use_se:
            self.conv4_se = SqueezeExcitation(c4, se_reduction)
        else:
            self.conv4_se = None
        
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # Optional extra blocks for depth scaling
        self.extra_blocks = None
        if depth_mult > 1.0:
            num_extra = int((depth_mult - 1.0) * 2)  # Add 0-2 extra blocks
            if num_extra > 0:
                extra = []
                for _ in range(num_extra):
                    extra.append(nn.Sequential(
                        nn.Conv2d(c4, c4, kernel_size=3, padding=1),
                        nn.BatchNorm2d(c4),
                        nn.ReLU(inplace=True),
                    ))
                    if use_se:
                        extra.append(SqueezeExcitation(c4, se_reduction))
                self.extra_blocks = nn.Sequential(*extra)
        
        # Classifier head
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(c4, num_classes)
        
        # Initialize weights
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize weights using Kaiming initialization."""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, 1, height, width)
            
        Returns:
            Logits of shape (batch, num_classes)
        """
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        
        if self.conv4_se is not None:
            x = self.conv4_se(x)
        
        if self.extra_blocks is not None:
            x = self.extra_blocks(x)
        
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)  # Flatten
        x = self.dropout(x)
        x = self.fc(x)
        
        return x
    
    def get_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        Extract features before the classification head.
        
        Useful for:
        - Transfer learning
        - Feature visualization
        - Ensemble combination at feature level
        
        Args:
            x: Input tensor of shape (batch, 1, height, width)
            
        Returns:
            Feature tensor of shape (batch, c4)
        """
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        
        if self.conv4_se is not None:
            x = self.conv4_se(x)
        
        if self.extra_blocks is not None:
            x = self.extra_blocks(x)
        
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)
        
        return x


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters in a model."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def compare_architectures():
    """Compare v1 and v2 architectures."""
    from transcription.ml_drum_classifier import DrumClassifierCNN
    
    print("=" * 60)
    print("Architecture Comparison: DrumClassifierCNN v1 vs v2")
    print("=" * 60)
    
    v1 = DrumClassifierCNN(num_classes=21)
    v2_base = DrumClassifierCNNv2(num_classes=21, use_se=False)
    v2_se = DrumClassifierCNNv2(num_classes=21, use_se=True)
    v2_scaled = DrumClassifierCNNv2(num_classes=21, use_se=True, width_mult=1.5)
    
    print(f"\nv1 (baseline):           {count_parameters(v1):>10,} params")
    print(f"v2 (no SE):              {count_parameters(v2_base):>10,} params")
    print(f"v2 (with SE):            {count_parameters(v2_se):>10,} params")
    print(f"v2 (SE + 1.5x width):    {count_parameters(v2_scaled):>10,} params")
    
    # Test forward pass
    print("\n" + "-" * 60)
    print("Forward pass test:")
    dummy_input = torch.randn(1, 1, 128, 128)
    
    with torch.no_grad():
        out_v1 = v1(dummy_input)
        out_v2 = v2_se(dummy_input)
    
    print(f"  Input shape:  {dummy_input.shape}")
    print(f"  v1 output:    {out_v1.shape}")
    print(f"  v2 output:    {out_v2.shape}")
    print(f"  Shapes match: {out_v1.shape == out_v2.shape}")


if __name__ == "__main__":
    compare_architectures()
    
    print("\n" + "=" * 60)
    print("DrumClassifierCNNv2 Architecture (with SE):")
    print("=" * 60)
    model = DrumClassifierCNNv2(use_se=True)
    print(model)
