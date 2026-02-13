"""
Stochastic Depth (DropPath) for CNN Regularization

Stochastic Depth randomly drops entire layers during training, forcing the
network to learn more robust features at every level. This is a powerful
regularization technique that consistently improves generalization.

Paper: "Deep Networks with Stochastic Depth" (ECCV 2016)
       https://arxiv.org/abs/1603.09382

Key Benefits:
1. +0.5-1.5% accuracy improvement on classification tasks
2. Reduces training time (fewer layers computed on average)
3. Acts as implicit ensemble (exponentially many sub-networks)
4. Synergizes with other regularization (dropout, mixup, etc.)

How it works:
- During training: each residual block is randomly skipped with probability p
- During inference: all blocks are used, but outputs are scaled by (1-p)
- Typically use linear decay: early blocks dropped less, later blocks more

For drum classification:
- Forces model to learn good features at all levels
- Prevents over-reliance on specific frequency/time patterns
- Reduces overfitting on limited training data

Usage:
    from training.utils.stochastic_depth import DropPath, StochasticDepthBlock
    
    # As a module in residual blocks
    self.drop_path = DropPath(drop_prob=0.1)
    
    # In forward:
    x = x + self.drop_path(self.block(x))
    
    # Or use the full block wrapper
    block = StochasticDepthBlock(conv_block, drop_prob=0.1)

References:
    - Original Paper: https://arxiv.org/abs/1603.09382
    - Vision Transformer: https://arxiv.org/abs/2010.11929 (uses this extensively)
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import List


class DropPath(nn.Module):
    """
    Drop paths (Stochastic Depth) per sample during training.
    
    This module drops the entire residual branch with probability `drop_prob`.
    During inference, outputs are scaled by (1 - drop_prob).
    
    Args:
        drop_prob: Probability of dropping the path (default: 0.1)
        scale_by_keep: Whether to scale outputs during training (default: True)
        
    Usage:
        self.drop_path = DropPath(0.1)
        # In forward:
        x = x + self.drop_path(residual)
    """
    
    def __init__(self, drop_prob: float = 0.0, scale_by_keep: bool = True):
        super().__init__()
        self.drop_prob = drop_prob
        self.scale_by_keep = scale_by_keep
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.drop_prob == 0.0 or not self.training:
            return x
        
        keep_prob = 1 - self.drop_prob
        
        # Create random tensor of shape (batch_size, 1, 1, ...) for broadcasting
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = x.new_empty(shape).bernoulli_(keep_prob)
        
        if self.scale_by_keep:
            random_tensor.div_(keep_prob)
        
        return x * random_tensor
    
    def extra_repr(self) -> str:
        return f"drop_prob={self.drop_prob}"


def drop_path(
    x: torch.Tensor,
    drop_prob: float = 0.0,
    training: bool = False,
    scale_by_keep: bool = True
) -> torch.Tensor:
    """
    Functional version of DropPath.
    
    Args:
        x: Input tensor
        drop_prob: Probability of dropping
        training: Whether in training mode
        scale_by_keep: Whether to scale by keep probability
        
    Returns:
        Possibly dropped tensor
    """
    if drop_prob == 0.0 or not training:
        return x
    
    keep_prob = 1 - drop_prob
    shape = (x.shape[0],) + (1,) * (x.ndim - 1)
    random_tensor = x.new_empty(shape).bernoulli_(keep_prob)
    
    if scale_by_keep:
        random_tensor.div_(keep_prob)
    
    return x * random_tensor


class StochasticDepthBlock(nn.Module):
    """
    Wrapper that adds stochastic depth to any residual block.
    
    Usage:
        conv_block = nn.Sequential(...)
        block = StochasticDepthBlock(conv_block, drop_prob=0.1)
        
        # Forward pass
        x = block(x)  # Automatically handles residual + drop path
    """
    
    def __init__(
        self,
        block: nn.Module,
        drop_prob: float = 0.0,
        residual_scale: float = 1.0
    ):
        super().__init__()
        self.block = block
        self.drop_path = DropPath(drop_prob) if drop_prob > 0.0 else nn.Identity()
        self.residual_scale = residual_scale
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.block(x)
        residual = self.drop_path(residual)
        return x + self.residual_scale * residual


def get_stochastic_depth_rates(
    num_blocks: int,
    drop_rate: float = 0.1,
    mode: str = "linear"
) -> List[float]:
    """
    Generate drop rates for each block using a schedule.
    
    Args:
        num_blocks: Number of blocks in the network
        drop_rate: Maximum drop rate (for last block)
        mode: "linear" (default), "constant", or "cosine"
        
    Returns:
        List of drop probabilities for each block
    """
    if mode == "constant":
        return [drop_rate] * num_blocks
    
    elif mode == "linear":
        # Linear increase: 0 -> drop_rate
        return [drop_rate * i / (num_blocks - 1) for i in range(num_blocks)]
    
    elif mode == "cosine":
        import math
        # Cosine schedule: starts slow, increases faster
        return [
            drop_rate * (1 - math.cos(math.pi * i / (num_blocks - 1))) / 2
            for i in range(num_blocks)
        ]
    
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'linear', 'constant', or 'cosine'")


class StochasticDepthSequential(nn.Module):
    """
    Sequential container with stochastic depth applied to each block.
    
    Automatically assigns linearly increasing drop rates to each block.
    
    Usage:
        blocks = [ConvBlock(32, 64), ConvBlock(64, 128), ConvBlock(128, 256)]
        model = StochasticDepthSequential(blocks, drop_rate=0.2)
    """
    
    def __init__(
        self,
        blocks: List[nn.Module],
        drop_rate: float = 0.1,
        mode: str = "linear"
    ):
        super().__init__()
        
        drop_rates = get_stochastic_depth_rates(len(blocks), drop_rate, mode)
        
        self.blocks = nn.ModuleList([
            StochasticDepthBlock(block, dp) 
            for block, dp in zip(blocks, drop_rates)
        ])
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for block in self.blocks:
            x = block(x)
        return x


# =============================================================================
# Integration with Coordinate Attention (v4) blocks
# =============================================================================

class CoordAttentionBlockWithDropPath(nn.Module):
    """
    Coordinate Attention block with integrated DropPath.
    
    This extends the standard CoordAttentionConvBlock with stochastic depth
    for additional regularization.
    
    Args:
        in_channels: Input channels
        out_channels: Output channels
        kernel_size: Convolution kernel size
        stride: Convolution stride
        use_coord_attention: Whether to apply CoordAttention
        reduction: Attention reduction ratio
        drop_path: Drop path probability
    """
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        use_coord_attention: bool = True,
        reduction: int = 32,
        drop_path: float = 0.0
    ):
        super().__init__()
        
        # Import here to avoid circular imports
        from training.models.coord_attention import CoordinateAttention
        
        padding = kernel_size // 2
        
        # Main branch
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
        
        # DropPath for stochastic depth
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()
        
        # Shortcut for residual (if dimensions change)
        self.has_residual = (in_channels == out_channels) and (stride == 1)
        if not self.has_residual and stride == 1:
            self.shortcut = nn.Conv2d(in_channels, out_channels, 1, bias=False)
        else:
            self.shortcut = None
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        identity = x
        
        out = self.conv(x)
        out = self.bn(out)
        out = self.act(out)
        out = self.attention(out)
        
        # Apply drop path if we have residual connection
        if self.has_residual:
            out = self.drop_path(out)
            out = out + identity
        elif self.shortcut is not None:
            out = self.drop_path(out)
            out = out + self.shortcut(identity)
        else:
            out = self.drop_path(out)
        
        return out


def add_drop_path_to_model(
    model: nn.Module,
    drop_rate: float = 0.1,
    mode: str = "linear"
) -> None:
    """
    Retroactively add DropPath to an existing model's blocks.
    
    This modifies the model in-place by wrapping residual connections
    with DropPath modules.
    
    Args:
        model: Model to modify
        drop_rate: Maximum drop rate
        mode: Drop rate schedule ("linear", "constant", "cosine")
        
    Note:
        This is a best-effort function. It works for standard architectures
        but may not handle all custom architectures correctly.
    """
    # Find all blocks that might be residual blocks
    blocks = []
    for name, module in model.named_modules():
        # Common residual block names
        if any(keyword in name.lower() for keyword in ['block', 'layer', 'stage']):
            if hasattr(module, 'forward') and not isinstance(module, (nn.Sequential, nn.ModuleList)):
                blocks.append((name, module))
    
    if not blocks:
        print("Warning: No residual blocks found. DropPath not applied.")
        return
    
    drop_rates = get_stochastic_depth_rates(len(blocks), drop_rate, mode)
    
    for (name, module), dp in zip(blocks, drop_rates):
        # Add drop_path attribute to each block
        module.drop_path = DropPath(dp)
        
    print(f"Added DropPath to {len(blocks)} blocks with rates: {drop_rates[0]:.3f} -> {drop_rates[-1]:.3f}")


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing Stochastic Depth / DropPath...")
    
    # Test basic DropPath
    drop_path = DropPath(0.2)
    x = torch.randn(4, 64, 32, 32)
    
    # Training mode
    drop_path.train()
    out_train = drop_path(x)
    
    # Eval mode
    drop_path.eval()
    out_eval = drop_path(x)
    
    print(f"Input shape: {x.shape}")
    print(f"Training output shape: {out_train.shape}")
    print(f"Eval output shape: {out_eval.shape}")
    print(f"Training: some samples zeroed: {(out_train.sum(dim=(1,2,3)) == 0).any()}")
    print(f"Eval: all samples preserved: {torch.allclose(x, out_eval)}")
    
    # Test rate schedule
    rates = get_stochastic_depth_rates(8, drop_rate=0.2, mode="linear")
    print(f"\nLinear drop rates for 8 blocks: {[f'{r:.3f}' for r in rates]}")
    
    # Test with simple CNN
    from torch import nn
    
    class SimpleBlock(nn.Module):
        def __init__(self, channels):
            super().__init__()
            self.conv = nn.Conv2d(channels, channels, 3, padding=1)
            self.bn = nn.BatchNorm2d(channels)
        
        def forward(self, x):
            return self.bn(self.conv(x))
    
    blocks = [SimpleBlock(64) for _ in range(4)]
    model = StochasticDepthSequential(blocks, drop_rate=0.2)
    
    x = torch.randn(2, 64, 16, 16)
    model.train()
    out = model(x)
    print(f"\n[OK] StochasticDepthSequential working! Output shape: {out.shape}")
