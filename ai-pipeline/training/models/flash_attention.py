"""
Flash Attention v2 for BeatSight V5 Model

=============================================================================
OPTIMIZATION 3: Flash Attention v2 (for future transformer blocks)
=============================================================================

Flash Attention v2 provides 2-4x speedup for attention operations by:
1. Reducing memory I/O through tiling and recomputation
2. Fusing multiple operations into single CUDA kernels
3. Eliminating materialization of large attention matrices

This module provides:
1. FlashAttention - Drop-in replacement for standard attention
2. FlashTransformerBlock - Transformer block using Flash Attention
3. FlashMultiHeadAttention - Multi-head attention with Flash

Benefits:
- 2-4x faster than standard attention
- O(N) memory instead of O(N²)
- Enables longer sequence lengths
- Compatible with FP16/BF16

When to use:
- V5 model with transformer blocks (future enhancement)
- Attention pooling layers
- Self-attention for temporal modeling

Requirements:
- PyTorch >= 2.0 (has flash_attn in torch.nn.functional)
- OR flash-attn package (pip install flash-attn)
- CUDA compute capability >= 8.0 (Ampere+)

Usage:
    from training.models.flash_attention import FlashMultiHeadAttention
    
    # Replace standard attention
    attn = FlashMultiHeadAttention(
        embed_dim=256,
        num_heads=8,
        use_flash=True  # Falls back gracefully if unavailable
    )
    
    output = attn(query, key, value)

Reference:
- "FlashAttention: Fast and Memory-Efficient Exact Attention" (Dao et al., 2022)
- "FlashAttention-2: Faster Attention with Better Parallelism" (Dao, 2023)
"""

from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# Check for Flash Attention availability
def _check_flash_attention_available() -> Tuple[bool, str]:
    """
    Check if Flash Attention is available.
    
    Returns:
        Tuple of (is_available, implementation_type)
        implementation_type: "native", "flash_attn_package", or "fallback"
    """
    # Check for native PyTorch 2.0+ implementation
    if hasattr(F, "scaled_dot_product_attention"):
        # Check if flash attention backend is available
        try:
            # PyTorch 2.0+ has SDPA with optional flash backend
            if torch.cuda.is_available():
                # Test with small tensor
                with torch.no_grad():
                    test_q = torch.randn(1, 1, 8, 64, device="cuda", dtype=torch.float16)
                    test_k = torch.randn(1, 1, 8, 64, device="cuda", dtype=torch.float16)
                    test_v = torch.randn(1, 1, 8, 64, device="cuda", dtype=torch.float16)
                    _ = F.scaled_dot_product_attention(test_q, test_k, test_v)
                return True, "native"
        except Exception:
            pass
    
    # Check for flash-attn package
    try:
        from flash_attn import flash_attn_func
        return True, "flash_attn_package"
    except ImportError:
        pass
    
    return False, "fallback"


FLASH_AVAILABLE, FLASH_IMPL = _check_flash_attention_available()


class FlashMultiHeadAttention(nn.Module):
    """
    Multi-Head Attention with Flash Attention v2 support.
    
    Automatically uses Flash Attention when available, falling back to
    standard attention otherwise. Provides 2-4x speedup with O(N) memory.
    
    Args:
        embed_dim: Total dimension of the model
        num_heads: Number of attention heads
        dropout: Dropout probability (applied to attention weights)
        bias: Whether to add bias to projections
        use_flash: Whether to use Flash Attention (auto-detects if None)
        causal: Whether to use causal (autoregressive) attention
        
    Shape:
        - query: (batch, seq_len, embed_dim)
        - key: (batch, seq_len, embed_dim)
        - value: (batch, seq_len, embed_dim)
        - output: (batch, seq_len, embed_dim)
    """
    
    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.0,
        bias: bool = True,
        use_flash: Optional[bool] = None,
        causal: bool = False,
    ):
        super().__init__()
        
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.dropout = dropout
        self.causal = causal
        
        assert embed_dim % num_heads == 0, \
            f"embed_dim ({embed_dim}) must be divisible by num_heads ({num_heads})"
        
        # Determine whether to use Flash Attention
        if use_flash is None:
            use_flash = FLASH_AVAILABLE
        
        self.use_flash = use_flash and FLASH_AVAILABLE
        self._flash_impl = FLASH_IMPL if self.use_flash else "fallback"
        
        if self.use_flash:
            logger.info(f"FlashMultiHeadAttention using {self._flash_impl} implementation")
        else:
            logger.warning("Flash Attention not available, using standard attention")
        
        # Input projections
        self.q_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.k_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        
        # Output projection
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=bias)
        
        # Dropout
        self.attn_dropout = nn.Dropout(dropout)
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights with Xavier uniform."""
        for module in [self.q_proj, self.k_proj, self.v_proj, self.out_proj]:
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
    
    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
        need_weights: bool = False,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Compute multi-head attention.
        
        Args:
            query: Query tensor (batch, seq_len, embed_dim)
            key: Key tensor (batch, seq_len, embed_dim)
            value: Value tensor (batch, seq_len, embed_dim)
            attn_mask: Optional attention mask
            need_weights: Whether to return attention weights
            
        Returns:
            Tuple of (output, attention_weights)
            attention_weights is None when using Flash Attention
        """
        batch_size, seq_len, _ = query.shape
        
        # Project to Q, K, V
        q = self.q_proj(query)
        k = self.k_proj(key)
        v = self.v_proj(value)
        
        # Reshape for multi-head: (batch, seq, heads, head_dim)
        q = q.view(batch_size, -1, self.num_heads, self.head_dim)
        k = k.view(batch_size, -1, self.num_heads, self.head_dim)
        v = v.view(batch_size, -1, self.num_heads, self.head_dim)
        
        if self.use_flash and not need_weights:
            output = self._flash_attention(q, k, v, attn_mask)
            attn_weights = None
        else:
            output, attn_weights = self._standard_attention(q, k, v, attn_mask)
        
        # Reshape back: (batch, seq, embed_dim)
        output = output.reshape(batch_size, seq_len, self.embed_dim)
        
        # Output projection
        output = self.out_proj(output)
        
        return output, attn_weights
    
    def _flash_attention(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        attn_mask: Optional[torch.Tensor],
    ) -> torch.Tensor:
        """Compute attention using Flash Attention."""
        
        if self._flash_impl == "native":
            # PyTorch 2.0+ scaled_dot_product_attention
            # Expects shape: (batch, heads, seq, head_dim)
            q = q.transpose(1, 2)
            k = k.transpose(1, 2)
            v = v.transpose(1, 2)
            
            # Use memory-efficient attention via SDPA
            with torch.backends.cuda.sdp_kernel(
                enable_flash=True,
                enable_math=False,
                enable_mem_efficient=True,
            ):
                output = F.scaled_dot_product_attention(
                    q, k, v,
                    attn_mask=attn_mask,
                    dropout_p=self.dropout if self.training else 0.0,
                    is_causal=self.causal,
                )
            
            # Back to (batch, seq, heads, head_dim)
            output = output.transpose(1, 2)
            
        elif self._flash_impl == "flash_attn_package":
            # flash-attn package
            from flash_attn import flash_attn_func
            
            # flash_attn expects (batch, seq, heads, head_dim)
            output = flash_attn_func(
                q, k, v,
                dropout_p=self.dropout if self.training else 0.0,
                causal=self.causal,
            )
        else:
            # Fallback (shouldn't reach here if use_flash is True)
            output, _ = self._standard_attention(q, k, v, attn_mask)
        
        return output
    
    def _standard_attention(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        v: torch.Tensor,
        attn_mask: Optional[torch.Tensor],
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute attention using standard implementation."""
        # q, k, v: (batch, seq, heads, head_dim)
        
        # Transpose for attention: (batch, heads, seq, head_dim)
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        
        # Compute attention scores
        scale = 1.0 / math.sqrt(self.head_dim)
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * scale
        
        # Apply mask
        if attn_mask is not None:
            attn_weights = attn_weights + attn_mask
        
        if self.causal:
            # Apply causal mask
            seq_len = q.size(2)
            causal_mask = torch.triu(
                torch.ones(seq_len, seq_len, device=q.device) * float("-inf"),
                diagonal=1
            )
            attn_weights = attn_weights + causal_mask
        
        # Softmax and dropout
        attn_weights = F.softmax(attn_weights, dim=-1)
        attn_weights = self.attn_dropout(attn_weights)
        
        # Apply attention to values
        output = torch.matmul(attn_weights, v)
        
        # Back to (batch, seq, heads, head_dim)
        output = output.transpose(1, 2)
        
        return output, attn_weights


class FlashTransformerBlock(nn.Module):
    """
    Transformer block with Flash Attention.
    
    Provides a complete transformer layer with:
    - Flash Multi-Head Self-Attention
    - Feed-Forward Network
    - Layer Normalization (Pre-LN)
    - Residual Connections
    - DropPath (stochastic depth)
    
    Args:
        embed_dim: Embedding dimension
        num_heads: Number of attention heads
        mlp_ratio: MLP hidden dimension = embed_dim * mlp_ratio
        dropout: Dropout probability
        drop_path: DropPath probability
        use_flash: Whether to use Flash Attention
        
    Shape:
        - Input: (batch, seq_len, embed_dim)
        - Output: (batch, seq_len, embed_dim)
    """
    
    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        mlp_ratio: float = 4.0,
        dropout: float = 0.0,
        drop_path: float = 0.0,
        use_flash: Optional[bool] = None,
    ):
        super().__init__()
        
        self.embed_dim = embed_dim
        
        # Pre-LN
        self.norm1 = nn.LayerNorm(embed_dim)
        self.norm2 = nn.LayerNorm(embed_dim)
        
        # Flash attention
        self.attn = FlashMultiHeadAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            use_flash=use_flash,
        )
        
        # MLP
        mlp_hidden = int(embed_dim * mlp_ratio)
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, mlp_hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(mlp_hidden, embed_dim),
            nn.Dropout(dropout),
        )
        
        # DropPath
        from training.utils.stochastic_depth import DropPath
        self.drop_path = DropPath(drop_path) if drop_path > 0 else nn.Identity()
    
    def forward(
        self,
        x: torch.Tensor,
        attn_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (batch, seq_len, embed_dim)
            attn_mask: Optional attention mask
            
        Returns:
            Output tensor (batch, seq_len, embed_dim)
        """
        # Self-attention with residual
        residual = x
        x = self.norm1(x)
        x, _ = self.attn(x, x, x, attn_mask=attn_mask)
        x = residual + self.drop_path(x)
        
        # MLP with residual
        residual = x
        x = self.norm2(x)
        x = self.mlp(x)
        x = residual + self.drop_path(x)
        
        return x


class FlashAttentionPooling(nn.Module):
    """
    Attention-based pooling using Flash Attention.
    
    Replaces global average pooling with learned attention pooling,
    allowing the model to focus on important spatial locations.
    Uses Flash Attention for efficient computation.
    
    Args:
        in_channels: Number of input channels
        num_heads: Number of attention heads
        use_flash: Whether to use Flash Attention
        
    Shape:
        - Input: (batch, channels, height, width)
        - Output: (batch, channels)
    """
    
    def __init__(
        self,
        in_channels: int,
        num_heads: int = 4,
        use_flash: Optional[bool] = None,
    ):
        super().__init__()
        
        self.in_channels = in_channels
        self.num_heads = num_heads
        
        # Learnable query for pooling
        self.pool_query = nn.Parameter(torch.randn(1, 1, in_channels))
        
        # Flash attention for pooling
        self.attn = FlashMultiHeadAttention(
            embed_dim=in_channels,
            num_heads=num_heads,
            dropout=0.0,
            use_flash=use_flash,
        )
        
        self._init_weights()
    
    def _init_weights(self):
        nn.init.trunc_normal_(self.pool_query, std=0.02)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Pool spatial features using attention.
        
        Args:
            x: Input features (batch, channels, height, width)
            
        Returns:
            Pooled features (batch, channels)
        """
        batch_size, channels, height, width = x.shape
        
        # Flatten spatial dimensions: (batch, H*W, channels)
        x = x.flatten(2).transpose(1, 2)
        
        # Expand query for batch
        query = self.pool_query.expand(batch_size, -1, -1)
        
        # Attend to all spatial positions
        output, _ = self.attn(query, x, x)
        
        # Remove sequence dimension
        output = output.squeeze(1)
        
        return output


# Utility function to check if Flash Attention can be used
def is_flash_attention_available() -> bool:
    """Check if Flash Attention is available on this system."""
    return FLASH_AVAILABLE


def get_flash_attention_info() -> dict:
    """Get information about Flash Attention availability."""
    return {
        "available": FLASH_AVAILABLE,
        "implementation": FLASH_IMPL,
        "cuda_available": torch.cuda.is_available(),
        "pytorch_version": torch.__version__,
    }
