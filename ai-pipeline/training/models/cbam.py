"""
CBAM: Convolutional Block Attention Module

CBAM is an evolution of SE (Squeeze-and-Excitation) that adds spatial attention
on top of channel attention, providing even better feature recalibration.

Paper: "CBAM: Convolutional Block Attention Module" (ECCV 2018)
       https://arxiv.org/abs/1807.06521

Architecture:
    Input → Channel Attention → Spatial Attention → Output
    
    Channel Attention (like SE but with both max-pool and avg-pool):
        - MaxPool + AvgPool → MLP → Sigmoid → Channel weights
        
    Spatial Attention (new):
        - MaxPool + AvgPool along channel → Conv7x7 → Sigmoid → Spatial weights

Benefits over SE blocks:
- SE only models "what" (channel importance)
- CBAM models "what" AND "where" (spatial importance)
- Especially useful for drum classification where timing matters

Expected improvement: Additional 0.3-0.8% over SE blocks alone.

Usage:
    from training.models.cbam import CBAM, CBAMConvBlock
    
    # As a module
    cbam = CBAM(in_channels=64)
    x = cbam(x)  # Apply both channel and spatial attention
    
    # As part of a conv block
    block = CBAMConvBlock(in_channels=32, out_channels=64)
"""

import torch
import torch.nn as nn


class ChannelAttention(nn.Module):
    """
    Channel Attention Module - Enhanced version of SE block.
    
    Uses both max-pool and average-pool to capture different statistics,
    then combines them through a shared MLP.
    
    Args:
        in_channels: Number of input channels
        reduction: Channel reduction ratio for MLP (default: 16)
    """
    
    def __init__(self, in_channels: int, reduction: int = 16):
        super().__init__()
        
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        
        # Shared MLP
        mid_channels = max(in_channels // reduction, 8)
        self.mlp = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, 1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, in_channels, 1, bias=False),
        )
        
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply channel attention.
        
        Args:
            x: Input tensor [B, C, H, W]
            
        Returns:
            Channel-attended tensor [B, C, H, W]
        """
        # Dual pooling captures both average and max statistics
        avg_out = self.mlp(self.avg_pool(x))
        max_out = self.mlp(self.max_pool(x))
        
        # Combine and apply attention
        attention = self.sigmoid(avg_out + max_out)
        return x * attention


class SpatialAttention(nn.Module):
    """
    Spatial Attention Module - Models "where" to focus.
    
    Uses channel-wise max and avg pooling to create a spatial descriptor,
    then applies a large kernel convolution to model spatial relationships.
    
    Args:
        kernel_size: Size of the convolution kernel (default: 7)
                     Larger kernels capture longer-range spatial dependencies
    """
    
    def __init__(self, kernel_size: int = 7):
        super().__init__()
        
        # Padding to maintain spatial dimensions
        padding = kernel_size // 2
        
        # Input: 2 channels (avg + max), Output: 1 channel (attention map)
        self.conv = nn.Sequential(
            nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply spatial attention.
        
        Args:
            x: Input tensor [B, C, H, W]
            
        Returns:
            Spatially-attended tensor [B, C, H, W]
        """
        # Channel-wise pooling to create 2-channel descriptor
        avg_out = torch.mean(x, dim=1, keepdim=True)  # [B, 1, H, W]
        max_out, _ = torch.max(x, dim=1, keepdim=True)  # [B, 1, H, W]
        
        # Concatenate and compute attention
        descriptor = torch.cat([avg_out, max_out], dim=1)  # [B, 2, H, W]
        attention = self.conv(descriptor)  # [B, 1, H, W]
        
        return x * attention


class CBAM(nn.Module):
    """
    Convolutional Block Attention Module.
    
    Applies channel attention followed by spatial attention.
    
    Args:
        in_channels: Number of input channels
        reduction: Channel reduction ratio (default: 16)
        spatial_kernel: Kernel size for spatial attention (default: 7)
    """
    
    def __init__(
        self,
        in_channels: int,
        reduction: int = 16,
        spatial_kernel: int = 7
    ):
        super().__init__()
        
        self.channel_attention = ChannelAttention(in_channels, reduction)
        self.spatial_attention = SpatialAttention(spatial_kernel)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply CBAM: Channel Attention → Spatial Attention.
        """
        x = self.channel_attention(x)
        x = self.spatial_attention(x)
        return x


class CBAMConvBlock(nn.Module):
    """
    Convolutional block with CBAM attention.
    
    Conv → BatchNorm → ReLU → CBAM
    
    Args:
        in_channels: Input channels
        out_channels: Output channels
        kernel_size: Convolution kernel size
        stride: Convolution stride
        use_cbam: Whether to apply CBAM (for easy ablation)
        reduction: CBAM channel reduction ratio
    """
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        use_cbam: bool = True,
        reduction: int = 16
    ):
        super().__init__()
        
        padding = kernel_size // 2
        
        self.conv = nn.Conv2d(
            in_channels, out_channels,
            kernel_size, stride, padding,
            bias=False
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        
        self.cbam = CBAM(out_channels, reduction) if use_cbam else nn.Identity()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        x = self.cbam(x)
        return x


class DrumClassifierCNNv3(nn.Module):
    """
    Drum Classifier CNN v3 with CBAM attention.
    
    This is an upgrade from v2 (SE blocks) to v3 (CBAM blocks),
    adding spatial attention for better temporal modeling.
    
    Architecture:
        Input (1, H, W) → Conv Blocks with CBAM → Global Pool → FC → Classes
    
    Args:
        num_classes: Number of drum hit types
        in_channels: Input channels (1 for mono spectrogram)
        base_channels: Base channel count (doubled each block)
        use_cbam: Whether to use CBAM (True) or just SE (False)
    """
    
    def __init__(
        self,
        num_classes: int = 11,
        in_channels: int = 1,
        base_channels: int = 32,
        use_cbam: bool = True,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.use_cbam = use_cbam
        
        # Progressive channel scaling
        channels = [base_channels, base_channels * 2, base_channels * 4, base_channels * 8]
        
        # Build conv blocks
        layers = []
        prev_ch = in_channels
        
        for i, ch in enumerate(channels):
            layers.append(CBAMConvBlock(prev_ch, ch, use_cbam=use_cbam))
            layers.append(nn.MaxPool2d(2, 2))
            prev_ch = ch
        
        self.features = nn.Sequential(*layers)
        
        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        
        # Classifier head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(channels[-1], channels[-1] // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(channels[-1] // 2, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.global_pool(x)
        x = self.classifier(x)
        return x
    
    def count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class EfficientAttention(nn.Module):
    """
    Efficient Attention - Linear complexity alternative to CBAM.
    
    For very large spectrograms or when CBAM is too slow, this provides
    O(n) attention instead of O(n²).
    
    Uses depthwise separable convolutions for efficiency.
    """
    
    def __init__(self, in_channels: int, reduction: int = 8):
        super().__init__()
        
        mid_channels = max(in_channels // reduction, 4)
        
        # Depthwise channel attention
        self.channel_gate = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(in_channels, mid_channels, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid_channels, in_channels, 1),
            nn.Sigmoid()
        )
        
        # Efficient spatial attention using depthwise conv
        self.spatial_gate = nn.Sequential(
            nn.Conv2d(in_channels, in_channels, 3, padding=1, groups=in_channels),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(in_channels, 1, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        channel_att = self.channel_gate(x)
        spatial_att = self.spatial_gate(x)
        return x * channel_att * spatial_att
