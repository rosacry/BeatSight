"""
Coordinate Attention for Drum Classification

Coordinate Attention is an evolution of channel attention that decomposes
positional information into two separate 1D feature encodings along the
horizontal and vertical directions. This is particularly effective for
audio spectrograms where time (horizontal) and frequency (vertical) have
distinct semantic meanings.

Paper: "Coordinate Attention for Efficient Mobile Network Design" (CVPR 2021)
       https://arxiv.org/abs/2103.02907

Benefits over SE and CBAM:
- SE: Only models channel importance, ignores positional info
- CBAM: Models channel and spatial separately, loses positional info in pooling
- CoordAttn: Preserves precise positional information in both directions

For drum classification:
- Vertical (frequency): Which frequencies are important (kick=low, hat=high)
- Horizontal (time): Where the transient attack is located

Expected improvement: +0.5-1.5% over SE/CBAM, especially for timing-sensitive drums.

Usage:
    from training.models.coord_attention import CoordinateAttention, DrumClassifierCNNv4
    
    # As a module
    coord_attn = CoordinateAttention(in_channels=64, reduction=32)
    x = coord_attn(x)  # [B, C, H, W] -> [B, C, H, W]
    
    # Full model
    model = DrumClassifierCNNv4(num_classes=21, use_coord_attention=True)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple


class CoordinateAttention(nn.Module):
    """
    Coordinate Attention Module.
    
    Captures long-range dependencies with precise positional information
    by encoding channel relationships along two spatial directions.
    
    Args:
        in_channels: Number of input channels
        reduction: Channel reduction ratio (default: 32)
    """
    
    def __init__(self, in_channels: int, reduction: int = 32):
        super().__init__()
        
        self.in_channels = in_channels
        mid_channels = max(8, in_channels // reduction)
        
        # Shared transform for coordinate features
        self.conv_shared = nn.Sequential(
            nn.Conv2d(in_channels, mid_channels, 1, bias=False),
            nn.BatchNorm2d(mid_channels),
            nn.Hardswish(inplace=True),  # More efficient than ReLU for this
        )
        
        # Separate transforms for height (frequency) and width (time)
        self.conv_h = nn.Conv2d(mid_channels, in_channels, 1, bias=False)
        self.conv_w = nn.Conv2d(mid_channels, in_channels, 1, bias=False)
        
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply Coordinate Attention.
        
        Args:
            x: Input tensor [B, C, H, W]
            
        Returns:
            Attention-weighted tensor [B, C, H, W]
        """
        B, C, H, W = x.shape
        
        # Pool along width (time axis) to get [B, C, H, 1]
        x_h = F.adaptive_avg_pool2d(x, (H, 1))
        
        # Pool along height (frequency axis) to get [B, C, 1, W]
        x_w = F.adaptive_avg_pool2d(x, (1, W))
        # Transpose to [B, C, W, 1] for concatenation
        x_w = x_w.permute(0, 1, 3, 2)
        
        # Concatenate: [B, C, H+W, 1]
        y = torch.cat([x_h, x_w], dim=2)
        
        # Shared transform: [B, C/r, H+W, 1]
        y = self.conv_shared(y)
        
        # Split back into h and w components
        y_h, y_w = torch.split(y, [H, W], dim=2)
        
        # Transpose y_w back: [B, C/r, 1, W]
        y_w = y_w.permute(0, 1, 3, 2)
        
        # Expand to attention maps
        attn_h = self.sigmoid(self.conv_h(y_h))  # [B, C, H, 1]
        attn_w = self.sigmoid(self.conv_w(y_w))  # [B, C, 1, W]
        
        # Apply attention (element-wise multiplication broadcasts correctly)
        out = x * attn_h * attn_w
        
        return out


class CoordAttentionConvBlock(nn.Module):
    """
    Convolutional block with Coordinate Attention.
    
    Conv → BatchNorm → ReLU → CoordAttention
    
    Args:
        in_channels: Input channels
        out_channels: Output channels
        kernel_size: Convolution kernel size
        stride: Convolution stride
        use_coord_attention: Whether to apply CoordAttention
        reduction: Attention reduction ratio
    """
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        use_coord_attention: bool = True,
        reduction: int = 32
    ):
        super().__init__()
        
        padding = kernel_size // 2
        
        self.conv = nn.Conv2d(
            in_channels, out_channels,
            kernel_size, stride, padding,
            bias=False
        )
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.ReLU(inplace=True)
        
        self.attention = (
            CoordinateAttention(out_channels, reduction) 
            if use_coord_attention 
            else nn.Identity()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.bn(x)
        x = self.act(x)
        x = self.attention(x)
        return x


class DrumClassifierCNNv4(nn.Module):
    """
    Drum Classifier CNN v4 with Coordinate Attention.
    
    This model uses Coordinate Attention which is particularly well-suited
    for spectrograms because it preserves and utilizes positional information
    in both time (horizontal) and frequency (vertical) dimensions.
    
    Architecture:
        Input (1, H, W) → Conv Blocks with CoordAttn → Global Pool → FC → Classes
    
    Optional multi-task heads:
    - velocity_head: Predicts hit velocity (0.0-1.0)
    - openness_head: Predicts hi-hat openness (0.0-1.0)
    
    Args:
        num_classes: Number of drum hit types
        in_channels: Input channels (1 for mono spectrogram)
        base_channels: Base channel count (doubled each block)
        use_coord_attention: Whether to use CoordAttention
        use_multi_task: Whether to enable auxiliary prediction heads
        dropout: Dropout rate for classifier
    """
    
    def __init__(
        self,
        num_classes: int = 21,
        in_channels: int = 1,
        base_channels: int = 32,
        use_coord_attention: bool = True,
        use_multi_task: bool = False,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.use_coord_attention = use_coord_attention
        self.use_multi_task = use_multi_task
        
        # Progressive channel scaling
        channels = [base_channels, base_channels * 2, base_channels * 4, base_channels * 8]
        
        # Build conv blocks
        layers = []
        prev_ch = in_channels
        
        for i, ch in enumerate(channels):
            layers.append(CoordAttentionConvBlock(
                prev_ch, ch, 
                use_coord_attention=use_coord_attention
            ))
            layers.append(nn.MaxPool2d(2, 2))
            prev_ch = ch
        
        self.features = nn.Sequential(*layers)
        
        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        
        # Feature dimension after pooling
        self.feature_dim = channels[-1]
        
        # Main classifier head
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim, self.feature_dim // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim // 2, num_classes)
        )
        
        # Auxiliary heads for multi-task learning
        if use_multi_task:
            # Velocity prediction head (0.0-1.0)
            self.velocity_head = nn.Sequential(
                nn.Linear(self.feature_dim, 64),
                nn.ReLU(inplace=True),
                nn.Linear(64, 1),
                nn.Sigmoid()
            )
            
            # Hi-hat openness prediction head (0.0-1.0)
            self.openness_head = nn.Sequential(
                nn.Linear(self.feature_dim, 64),
                nn.ReLU(inplace=True),
                nn.Linear(64, 1),
                nn.Sigmoid()
            )
        else:
            self.velocity_head = None
            self.openness_head = None
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass returning class logits.
        
        For multi-task output, use forward_multi_task() instead.
        """
        features = self.features(x)
        pooled = self.global_pool(features)
        logits = self.classifier(pooled)
        return logits
    
    def forward_multi_task(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor], Optional[torch.Tensor]]:
        """
        Forward pass with multi-task outputs.
        
        Returns:
            Tuple of (class_logits, velocity, openness)
            velocity and openness are None if use_multi_task=False
        """
        features = self.features(x)
        pooled = self.global_pool(features)
        flat = pooled.flatten(1)
        
        logits = self.classifier(pooled)
        
        velocity = None
        openness = None
        
        if self.use_multi_task:
            velocity = self.velocity_head(flat).squeeze(-1)
            openness = self.openness_head(flat).squeeze(-1)
        
        return logits, velocity, openness
    
    def count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class MultiTaskLoss(nn.Module):
    """
    Multi-task loss combining classification, velocity, and openness.
    
    Args:
        classification_weight: Weight for classification loss (default: 1.0)
        velocity_weight: Weight for velocity regression loss (default: 0.3)
        openness_weight: Weight for openness regression loss (default: 0.2)
        openness_class_indices: List of class indices for hi-hat (where openness applies)
    """
    
    def __init__(
        self,
        classification_weight: float = 1.0,
        velocity_weight: float = 0.3,
        openness_weight: float = 0.2,
        openness_class_indices: Optional[list] = None,
        base_criterion: Optional[nn.Module] = None,
    ):
        super().__init__()
        
        self.classification_weight = classification_weight
        self.velocity_weight = velocity_weight
        self.openness_weight = openness_weight
        
        # Hi-hat related classes (indices where openness is meaningful)
        # Default: hihat_closed, hihat_open, hihat_pedal, hihat_splash, hihat_foot_splash
        self.openness_class_indices = openness_class_indices or [4, 5, 6, 7, 8]
        
        self.base_criterion = base_criterion or nn.CrossEntropyLoss()
        self.velocity_criterion = nn.MSELoss()
        self.openness_criterion = nn.MSELoss()
    
    def forward(
        self,
        logits: torch.Tensor,
        velocity_pred: Optional[torch.Tensor],
        openness_pred: Optional[torch.Tensor],
        class_targets: torch.Tensor,
        velocity_targets: Optional[torch.Tensor] = None,
        openness_targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, dict]:
        """
        Compute multi-task loss.
        
        Args:
            logits: Class predictions [B, num_classes]
            velocity_pred: Velocity predictions [B] or None
            openness_pred: Openness predictions [B] or None
            class_targets: Ground truth class indices [B]
            velocity_targets: Ground truth velocities [B] or None
            openness_targets: Ground truth openness [B] or None
        
        Returns:
            Tuple of (total_loss, loss_dict with individual losses)
        """
        # Classification loss (always computed)
        class_loss = self.base_criterion(logits, class_targets)
        total_loss = self.classification_weight * class_loss
        
        loss_dict = {"classification": class_loss.item()}
        
        # Velocity loss (if targets provided)
        if velocity_pred is not None and velocity_targets is not None:
            velocity_loss = self.velocity_criterion(velocity_pred, velocity_targets)
            total_loss = total_loss + self.velocity_weight * velocity_loss
            loss_dict["velocity"] = velocity_loss.item()
        
        # Openness loss (only for hi-hat samples)
        if openness_pred is not None and openness_targets is not None:
            # Create mask for hi-hat samples
            hihat_mask = torch.zeros_like(class_targets, dtype=torch.bool)
            for idx in self.openness_class_indices:
                hihat_mask = hihat_mask | (class_targets == idx)
            
            if hihat_mask.any():
                openness_loss = self.openness_criterion(
                    openness_pred[hihat_mask], 
                    openness_targets[hihat_mask]
                )
                total_loss = total_loss + self.openness_weight * openness_loss
                loss_dict["openness"] = openness_loss.item()
        
        loss_dict["total"] = total_loss.item()
        return total_loss, loss_dict


# Convenience functions for easy instantiation
def coord_attention_small(num_classes: int = 21, use_multi_task: bool = False):
    """Small Coordinate Attention model (~400K params)."""
    return DrumClassifierCNNv4(
        num_classes=num_classes,
        base_channels=32,
        use_coord_attention=True,
        use_multi_task=use_multi_task,
    )


def coord_attention_medium(num_classes: int = 21, use_multi_task: bool = False):
    """Medium Coordinate Attention model (~1.6M params)."""
    return DrumClassifierCNNv4(
        num_classes=num_classes,
        base_channels=48,
        use_coord_attention=True,
        use_multi_task=use_multi_task,
    )


def coord_attention_large(num_classes: int = 21, use_multi_task: bool = False):
    """Large Coordinate Attention model (~3.2M params)."""
    return DrumClassifierCNNv4(
        num_classes=num_classes,
        base_channels=64,
        use_coord_attention=True,
        use_multi_task=use_multi_task,
    )
