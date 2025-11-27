"""
Advanced Pooling and Attention Mechanisms for CNN v5

This module provides enhanced pooling strategies that go beyond simple
global average pooling:

1. Attentive Statistics Pooling (ASP) - Learn weighted mean + std
2. Multi-Head Attention Pooling - Transformer-style attention for aggregation

These can improve model quality by +0.3-0.5% by learning which spatial
locations are most important for classification.

Reference:
- "Attentive Statistics Pooling for Deep Speaker Embedding" (Okabe et al., 2018)
- "Attention Is All You Need" (Vaswani et al., 2017)
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentiveStatisticsPooling(nn.Module):
    """
    Attentive Statistics Pooling (ASP).
    
    Instead of simple global average pooling, this learns attention weights
    over spatial locations and computes weighted mean AND weighted standard
    deviation, providing richer feature aggregation.
    
    For drum classification, this helps the model:
    - Focus on the attack transient (most discriminative)
    - Ignore silent/noise regions
    - Capture both mean and variance of features
    
    Args:
        in_channels: Number of input channels
        attention_channels: Hidden dimension for attention (default: in_channels // 4)
        
    Input: [B, C, H, W]
    Output: [B, C * 2] (concatenated weighted mean and std)
    
    Expected improvement: +0.3-0.5%
    """
    
    def __init__(
        self,
        in_channels: int,
        attention_channels: Optional[int] = None
    ):
        super().__init__()
        
        attention_channels = attention_channels or max(32, in_channels // 4)
        
        # Attention network
        self.attention = nn.Sequential(
            nn.Conv2d(in_channels, attention_channels, kernel_size=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(attention_channels, 1, kernel_size=1),
        )
        
        self.in_channels = in_channels
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input features [B, C, H, W]
            
        Returns:
            Pooled features [B, C * 2] (mean || std)
        """
        B, C, H, W = x.shape
        
        # Compute attention weights
        attn = self.attention(x)  # [B, 1, H, W]
        attn = attn.view(B, 1, -1)  # [B, 1, H*W]
        attn = F.softmax(attn, dim=-1)  # [B, 1, H*W]
        
        # Reshape features
        x_flat = x.view(B, C, -1)  # [B, C, H*W]
        
        # Weighted mean
        mean = torch.bmm(x_flat, attn.transpose(1, 2))  # [B, C, 1]
        mean = mean.squeeze(-1)  # [B, C]
        
        # Weighted standard deviation
        # E[X^2] - E[X]^2
        x_sq = x_flat ** 2
        mean_sq = torch.bmm(x_sq, attn.transpose(1, 2)).squeeze(-1)  # [B, C]
        std = torch.sqrt(torch.clamp(mean_sq - mean ** 2, min=1e-6))
        
        # Concatenate mean and std
        out = torch.cat([mean, std], dim=1)  # [B, C * 2]
        
        return out
    
    @property
    def output_dim(self) -> int:
        return self.in_channels * 2


class MultiHeadAttentionPooling(nn.Module):
    """
    Multi-Head Attention Pooling.
    
    Uses transformer-style multi-head attention to aggregate spatial features
    into a fixed-size representation. A learnable query token attends to all
    spatial positions.
    
    For drum classification:
    - Different heads can focus on different aspects (attack, sustain, frequency bands)
    - More expressive than single attention
    - Captures complex spatial relationships
    
    Args:
        in_channels: Number of input channels
        num_heads: Number of attention heads (default: 4)
        head_dim: Dimension per head (default: in_channels // num_heads)
        dropout: Dropout rate
        
    Input: [B, C, H, W]
    Output: [B, num_heads * head_dim]
    
    Expected improvement: +0.2-0.5%
    """
    
    def __init__(
        self,
        in_channels: int,
        num_heads: int = 4,
        head_dim: Optional[int] = None,
        dropout: float = 0.1
    ):
        super().__init__()
        
        head_dim = head_dim or (in_channels // num_heads)
        inner_dim = num_heads * head_dim
        
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.scale = head_dim ** -0.5
        
        # Learnable query token
        self.query = nn.Parameter(torch.randn(1, 1, inner_dim))
        nn.init.trunc_normal_(self.query, std=0.02)
        
        # Projections
        self.to_kv = nn.Linear(in_channels, inner_dim * 2)
        self.to_out = nn.Sequential(
            nn.Linear(inner_dim, inner_dim),
            nn.Dropout(dropout)
        )
        
        self.output_dim = inner_dim
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input features [B, C, H, W]
            
        Returns:
            Pooled features [B, num_heads * head_dim]
        """
        B, C, H, W = x.shape
        
        # Flatten spatial dimensions
        x = x.view(B, C, -1).transpose(1, 2)  # [B, H*W, C]
        
        # Project to key and value
        kv = self.to_kv(x)  # [B, H*W, inner_dim * 2]
        k, v = kv.chunk(2, dim=-1)  # Each [B, H*W, inner_dim]
        
        # Reshape for multi-head attention
        q = self.query.expand(B, -1, -1)  # [B, 1, inner_dim]
        
        # Split heads
        q = q.view(B, 1, self.num_heads, self.head_dim).transpose(1, 2)  # [B, heads, 1, head_dim]
        k = k.view(B, -1, self.num_heads, self.head_dim).transpose(1, 2)  # [B, heads, H*W, head_dim]
        v = v.view(B, -1, self.num_heads, self.head_dim).transpose(1, 2)  # [B, heads, H*W, head_dim]
        
        # Attention
        attn = (q @ k.transpose(-2, -1)) * self.scale  # [B, heads, 1, H*W]
        attn = F.softmax(attn, dim=-1)
        
        # Aggregate
        out = attn @ v  # [B, heads, 1, head_dim]
        out = out.transpose(1, 2).contiguous().view(B, -1)  # [B, inner_dim]
        
        out = self.to_out(out)
        
        return out


class HybridPooling(nn.Module):
    """
    Hybrid pooling combining multiple strategies.
    
    Combines:
    1. Global Average Pooling (GAP) - baseline
    2. Global Max Pooling (GMP) - captures peaks
    3. Attentive Statistics Pooling (ASP) - learned weighting
    
    The outputs are concatenated and projected back to a smaller dimension.
    
    Args:
        in_channels: Number of input channels
        output_dim: Output dimension (default: in_channels)
        use_asp: Whether to include ASP
        
    Input: [B, C, H, W]
    Output: [B, output_dim]
    """
    
    def __init__(
        self,
        in_channels: int,
        output_dim: Optional[int] = None,
        use_asp: bool = True
    ):
        super().__init__()
        
        output_dim = output_dim or in_channels
        
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.gmp = nn.AdaptiveMaxPool2d(1)
        
        self.use_asp = use_asp
        if use_asp:
            self.asp = AttentiveStatisticsPooling(in_channels)
            total_dim = in_channels * 4  # GAP + GMP + ASP (mean + std)
        else:
            total_dim = in_channels * 2  # GAP + GMP
        
        # Projection layer
        self.projection = nn.Sequential(
            nn.Linear(total_dim, output_dim),
            nn.SiLU(inplace=True)
        )
        
        self.output_dim = output_dim
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input features [B, C, H, W]
            
        Returns:
            Pooled features [B, output_dim]
        """
        gap = self.gap(x).flatten(1)  # [B, C]
        gmp = self.gmp(x).flatten(1)  # [B, C]
        
        if self.use_asp:
            asp = self.asp(x)  # [B, C * 2]
            combined = torch.cat([gap, gmp, asp], dim=1)  # [B, C * 4]
        else:
            combined = torch.cat([gap, gmp], dim=1)  # [B, C * 2]
        
        return self.projection(combined)


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing Attention Pooling modules...")
    
    x = torch.randn(4, 256, 8, 8)
    
    # Test ASP
    asp = AttentiveStatisticsPooling(256)
    out = asp(x)
    print(f"ASP: input {x.shape} -> output {out.shape}")
    assert out.shape == (4, 512)
    
    # Test Multi-Head Attention Pooling
    mha = MultiHeadAttentionPooling(256, num_heads=4)
    out = mha(x)
    print(f"MHA Pooling: input {x.shape} -> output {out.shape}")
    assert out.shape == (4, 256)
    
    # Test Hybrid Pooling
    hybrid = HybridPooling(256, output_dim=128)
    out = hybrid(x)
    print(f"Hybrid Pooling: input {x.shape} -> output {out.shape}")
    assert out.shape == (4, 128)
    
    print("\n✅ All pooling modules working!")
