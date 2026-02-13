"""
Audio Spectrogram Transformer (AST) for Drum Classification

The Audio Spectrogram Transformer applies the Vision Transformer (ViT) architecture
to audio spectrograms, treating them as images. AST has achieved state-of-the-art
results on multiple audio classification benchmarks.

Key Benefits:
- Global attention: Can capture long-range dependencies in spectrograms
- Transfer learning: Leverages pre-trained vision transformers
- Scalable: Larger models consistently improve performance
- Interpretable: Attention maps show what the model focuses on

Architecture:
- Patch Embedding: Split spectrogram into 16x16 patches
- Position Embedding: Learnable or sinusoidal positional encodings
- Transformer Encoder: Multi-head self-attention + FFN layers
- Classification Head: Mean pooling + linear classifier

Reference: "AST: Audio Spectrogram Transformer" (Gong et al., 2021)
           https://arxiv.org/abs/2104.01778

Expected Improvement: 2-5% over CNN baselines when properly trained

Usage:
    from training.models.ast import AudioSpectrogramTransformer
    
    # Standard AST for drum classification
    model = AudioSpectrogramTransformer(
        num_classes=21,
        patch_size=16,
        embed_dim=384,
        num_heads=6,
        num_layers=6,
    )
    
    # Forward pass with mel spectrogram
    logits = model(mel_spectrogram)  # [B, 1, 128, 128] -> [B, 21]
"""

from __future__ import annotations

from functools import partial
from typing import Callable, List, Optional, Tuple, Union

import torch
import torch.nn as nn


class PatchEmbed(nn.Module):
    """
    Split spectrogram into non-overlapping patches and project to embedding dimension.
    
    For a 128x128 spectrogram with 16x16 patches:
    - Number of patches: (128/16) * (128/16) = 64
    - Each patch is flattened and projected to embed_dim
    
    Args:
        img_size: Input spectrogram size (height, width) or single int for square
        patch_size: Size of each patch
        in_channels: Number of input channels (1 for mono spectrogram)
        embed_dim: Embedding dimension for each patch
        norm_layer: Optional normalization layer after projection
    """
    
    def __init__(
        self,
        img_size: Union[int, Tuple[int, int]] = 128,
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dim: int = 384,
        norm_layer: Optional[Callable] = None,
    ):
        super().__init__()
        
        if isinstance(img_size, int):
            img_size = (img_size, img_size)
        
        self.img_size = img_size
        self.patch_size = patch_size
        self.grid_size = (img_size[0] // patch_size, img_size[1] // patch_size)
        self.num_patches = self.grid_size[0] * self.grid_size[1]
        
        # Convolution is an efficient way to implement patch projection
        self.proj = nn.Conv2d(
            in_channels, 
            embed_dim, 
            kernel_size=patch_size, 
            stride=patch_size
        )
        
        self.norm = norm_layer(embed_dim) if norm_layer else nn.Identity()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input spectrogram [B, C, H, W]
            
        Returns:
            Patch embeddings [B, num_patches, embed_dim]
        """
        B, C, H, W = x.shape
        
        # Project patches: [B, embed_dim, H/patch_size, W/patch_size]
        x = self.proj(x)
        
        # Flatten to sequence: [B, embed_dim, num_patches] -> [B, num_patches, embed_dim]
        x = x.flatten(2).transpose(1, 2)
        
        x = self.norm(x)
        return x


class Attention(nn.Module):
    """
    Multi-Head Self-Attention module.
    
    Computes attention over all patches, allowing global information flow.
    This is crucial for audio where a drum hit's characteristics span
    multiple frequency bands and time frames.
    
    Args:
        dim: Input embedding dimension
        num_heads: Number of attention heads
        qkv_bias: Whether to include bias in Q, K, V projections
        attn_drop: Dropout rate for attention weights
        proj_drop: Dropout rate for output projection
    """
    
    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        qkv_bias: bool = True,
        attn_drop: float = 0.0,
        proj_drop: float = 0.0,
    ):
        super().__init__()
        self.num_heads = num_heads
        head_dim = dim // num_heads
        self.scale = head_dim ** -0.5
        
        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Linear(dim, dim)
        self.proj_drop = nn.Dropout(proj_drop)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input [B, N, D] where N is sequence length (num_patches + 1 for cls token)
            
        Returns:
            Output [B, N, D]
        """
        B, N, D = x.shape
        
        # Compute Q, K, V
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, D // self.num_heads)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # [3, B, num_heads, N, head_dim]
        q, k, v = qkv.unbind(0)
        
        # Scaled dot-product attention
        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)
        attn = self.attn_drop(attn)
        
        # Apply attention to values
        x = (attn @ v).transpose(1, 2).reshape(B, N, D)
        
        x = self.proj(x)
        x = self.proj_drop(x)
        return x


class Mlp(nn.Module):
    """
    Feed-Forward Network (MLP) with GELU activation.
    
    Standard Transformer FFN: Linear -> GELU -> Dropout -> Linear -> Dropout
    
    Args:
        in_features: Input dimension
        hidden_features: Hidden layer dimension (default: 4x input)
        out_features: Output dimension (default: same as input)
        act_layer: Activation function
        drop: Dropout rate
    """
    
    def __init__(
        self,
        in_features: int,
        hidden_features: Optional[int] = None,
        out_features: Optional[int] = None,
        act_layer: Callable = nn.GELU,
        drop: float = 0.0,
    ):
        super().__init__()
        out_features = out_features or in_features
        hidden_features = hidden_features or in_features * 4
        
        self.fc1 = nn.Linear(in_features, hidden_features)
        self.act = act_layer()
        self.fc2 = nn.Linear(hidden_features, out_features)
        self.drop = nn.Dropout(drop)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.act(x)
        x = self.drop(x)
        x = self.fc2(x)
        x = self.drop(x)
        return x


class TransformerBlock(nn.Module):
    """
    Transformer Encoder Block: Self-Attention + MLP with residual connections.
    
    Structure:
        x -> LayerNorm -> Attention -> + -> LayerNorm -> MLP -> + -> output
             |__________________________|    |__________________|
                    (residual)                   (residual)
    
    Args:
        dim: Embedding dimension
        num_heads: Number of attention heads
        mlp_ratio: MLP hidden dimension ratio
        qkv_bias: Include bias in attention
        drop: Dropout rate
        attn_drop: Attention dropout rate
        drop_path: Stochastic depth rate
    """
    
    def __init__(
        self,
        dim: int,
        num_heads: int,
        mlp_ratio: float = 4.0,
        qkv_bias: bool = True,
        drop: float = 0.0,
        attn_drop: float = 0.0,
        drop_path: float = 0.0,
        act_layer: Callable = nn.GELU,
        norm_layer: Callable = nn.LayerNorm,
    ):
        super().__init__()
        self.norm1 = norm_layer(dim)
        self.attn = Attention(
            dim=dim,
            num_heads=num_heads,
            qkv_bias=qkv_bias,
            attn_drop=attn_drop,
            proj_drop=drop,
        )
        
        # Stochastic depth for regularization
        self.drop_path = DropPath(drop_path) if drop_path > 0.0 else nn.Identity()
        
        self.norm2 = norm_layer(dim)
        mlp_hidden_dim = int(dim * mlp_ratio)
        self.mlp = Mlp(
            in_features=dim,
            hidden_features=mlp_hidden_dim,
            act_layer=act_layer,
            drop=drop,
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.drop_path(self.attn(self.norm1(x)))
        x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x


class DropPath(nn.Module):
    """
    Stochastic Depth (Drop Path) regularization.
    
    Randomly drops entire residual branches during training.
    This provides strong regularization and is key for training deep transformers.
    
    Reference: "Deep Networks with Stochastic Depth" (Huang et al., 2016)
    """
    
    def __init__(self, drop_prob: float = 0.0):
        super().__init__()
        self.drop_prob = drop_prob
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.drop_prob == 0.0 or not self.training:
            return x
        
        keep_prob = 1 - self.drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()  # Binarize
        output = x.div(keep_prob) * random_tensor
        return output


class AudioSpectrogramTransformer(nn.Module):
    """
    Audio Spectrogram Transformer for drum classification.
    
    This is a Vision Transformer (ViT) adapted for audio spectrograms.
    The key insight is that mel spectrograms are 2D representations that
    can be processed similarly to images.
    
    Architecture:
    1. Patch Embedding: Split spectrogram into 16x16 patches
    2. Add [CLS] token for classification
    3. Add positional embeddings
    4. Apply N transformer blocks
    5. Take [CLS] token output for classification
    
    Args:
        img_size: Input spectrogram size (default: 128x128)
        patch_size: Size of each patch (default: 16)
        in_channels: Input channels (default: 1 for mono)
        num_classes: Number of output classes (default: 21 for drums)
        embed_dim: Transformer embedding dimension
        num_heads: Number of attention heads per layer
        num_layers: Number of transformer blocks
        mlp_ratio: MLP hidden dimension ratio
        drop_rate: Dropout rate
        attn_drop_rate: Attention dropout rate
        drop_path_rate: Stochastic depth rate
        use_cls_token: Whether to use [CLS] token (alternative: mean pooling)
    
    Model Configurations:
        - Tiny: embed_dim=192, num_heads=3, num_layers=12 (~6M params)
        - Small: embed_dim=384, num_heads=6, num_layers=12 (~22M params)
        - Base: embed_dim=768, num_heads=12, num_layers=12 (~86M params)
    """
    
    # Drum component class names for compatibility
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
        img_size: int = 128,
        patch_size: int = 16,
        in_channels: int = 1,
        num_classes: int = 21,
        embed_dim: int = 384,
        num_heads: int = 6,
        num_layers: int = 6,
        mlp_ratio: float = 4.0,
        qkv_bias: bool = True,
        drop_rate: float = 0.0,
        attn_drop_rate: float = 0.0,
        drop_path_rate: float = 0.1,
        use_cls_token: bool = True,
        norm_layer: Callable = partial(nn.LayerNorm, eps=1e-6),
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.embed_dim = embed_dim
        self.use_cls_token = use_cls_token
        
        # Patch embedding
        self.patch_embed = PatchEmbed(
            img_size=img_size,
            patch_size=patch_size,
            in_channels=in_channels,
            embed_dim=embed_dim,
        )
        num_patches = self.patch_embed.num_patches
        
        # Class token
        if use_cls_token:
            self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
            self.pos_embed = nn.Parameter(torch.zeros(1, num_patches + 1, embed_dim))
        else:
            self.cls_token = None
            self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embed_dim))
        
        self.pos_drop = nn.Dropout(p=drop_rate)
        
        # Stochastic depth decay rule
        dpr = [x.item() for x in torch.linspace(0, drop_path_rate, num_layers)]
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(
                dim=embed_dim,
                num_heads=num_heads,
                mlp_ratio=mlp_ratio,
                qkv_bias=qkv_bias,
                drop=drop_rate,
                attn_drop=attn_drop_rate,
                drop_path=dpr[i],
                norm_layer=norm_layer,
            )
            for i in range(num_layers)
        ])
        
        self.norm = norm_layer(embed_dim)
        
        # Classification head
        self.head = nn.Linear(embed_dim, num_classes)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights with truncated normal distribution."""
        # Initialize positional embedding
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
        
        # Initialize cls token
        if self.cls_token is not None:
            nn.init.trunc_normal_(self.cls_token, std=0.02)
        
        # Initialize linear layers and layer norms
        self.apply(self._init_weights_module)
    
    def _init_weights_module(self, m):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.LayerNorm):
            nn.init.zeros_(m.bias)
            nn.init.ones_(m.weight)
    
    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        """
        Extract features before classification head.
        
        Args:
            x: Input spectrogram [B, C, H, W]
            
        Returns:
            Features [B, embed_dim]
        """
        B = x.shape[0]
        
        # Patch embedding: [B, num_patches, embed_dim]
        x = self.patch_embed(x)
        
        # Add class token
        if self.use_cls_token:
            cls_tokens = self.cls_token.expand(B, -1, -1)
            x = torch.cat((cls_tokens, x), dim=1)
        
        # Add positional embedding
        x = x + self.pos_embed
        x = self.pos_drop(x)
        
        # Apply transformer blocks
        for block in self.blocks:
            x = block(x)
        
        x = self.norm(x)
        
        # Extract features
        if self.use_cls_token:
            x = x[:, 0]  # [CLS] token
        else:
            x = x.mean(dim=1)  # Mean pooling
        
        return x
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input spectrogram [B, C, H, W]
            
        Returns:
            Logits [B, num_classes]
        """
        x = self.forward_features(x)
        x = self.head(x)
        return x
    
    def get_attention_maps(self, x: torch.Tensor) -> List[torch.Tensor]:
        """
        Extract attention maps from all layers for visualization.
        
        Useful for understanding what parts of the spectrogram
        the model focuses on for each drum class.
        
        Args:
            x: Input spectrogram [B, C, H, W]
            
        Returns:
            List of attention maps, one per layer [B, num_heads, N, N]
        """
        attention_maps = []
        
        B = x.shape[0]
        x = self.patch_embed(x)
        
        if self.use_cls_token:
            cls_tokens = self.cls_token.expand(B, -1, -1)
            x = torch.cat((cls_tokens, x), dim=1)
        
        x = x + self.pos_embed
        x = self.pos_drop(x)
        
        for block in self.blocks:
            # Store attention weights from this block
            with torch.no_grad():
                # Compute attention for visualization
                x_norm = block.norm1(x)
                B, N, D = x_norm.shape
                qkv = block.attn.qkv(x_norm).reshape(B, N, 3, block.attn.num_heads, D // block.attn.num_heads)
                qkv = qkv.permute(2, 0, 3, 1, 4)
                q, k, v = qkv.unbind(0)
                attn = (q @ k.transpose(-2, -1)) * block.attn.scale
                attn = attn.softmax(dim=-1)
                attention_maps.append(attn)
            
            # Apply block normally
            x = block(x)
        
        return attention_maps
    
    @property
    def num_parameters(self) -> int:
        """Get total number of parameters."""
        return sum(p.numel() for p in self.parameters())
    
    @property
    def num_trainable_parameters(self) -> int:
        """Get number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class ASTWithCNN(nn.Module):
    """
    Hybrid CNN + Transformer model.
    
    Uses a lightweight CNN for local feature extraction (capturing transients),
    then a transformer for global context (understanding drum kit structure).
    
    This hybrid approach often outperforms pure CNN or pure Transformer
    while being more efficient.
    
    Architecture:
    - CNN Stem: 2-3 conv layers to extract local features and reduce resolution
    - Transformer Body: Self-attention for global reasoning
    - Classification Head: Linear classifier
    
    Args:
        Same as AudioSpectrogramTransformer, plus:
        stem_channels: CNN stem channel progression (default: [32, 64])
    """
    
    DRUM_COMPONENTS = AudioSpectrogramTransformer.DRUM_COMPONENTS
    
    def __init__(
        self,
        img_size: int = 128,
        in_channels: int = 1,
        num_classes: int = 21,
        embed_dim: int = 256,
        num_heads: int = 4,
        num_layers: int = 4,
        mlp_ratio: float = 4.0,
        drop_rate: float = 0.1,
        attn_drop_rate: float = 0.0,
        drop_path_rate: float = 0.1,
        stem_channels: Tuple[int, ...] = (32, 64),
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.embed_dim = embed_dim
        
        # CNN Stem for local feature extraction
        stem_layers = []
        prev_ch = in_channels
        for ch in stem_channels:
            stem_layers.extend([
                nn.Conv2d(prev_ch, ch, kernel_size=3, stride=2, padding=1),
                nn.BatchNorm2d(ch),
                nn.GELU(),
            ])
            prev_ch = ch
        self.stem = nn.Sequential(*stem_layers)
        
        # Calculate feature map size after stem
        stem_stride = 2 ** len(stem_channels)
        feature_size = img_size // stem_stride
        num_patches = feature_size * feature_size
        
        # Project CNN features to transformer dimension
        self.proj = nn.Conv2d(stem_channels[-1], embed_dim, kernel_size=1)
        
        # Positional embedding
        self.pos_embed = nn.Parameter(torch.zeros(1, num_patches, embed_dim))
        self.pos_drop = nn.Dropout(p=drop_rate)
        
        # Stochastic depth
        dpr = [x.item() for x in torch.linspace(0, drop_path_rate, num_layers)]
        
        # Transformer blocks
        self.blocks = nn.ModuleList([
            TransformerBlock(
                dim=embed_dim,
                num_heads=num_heads,
                mlp_ratio=mlp_ratio,
                drop=drop_rate,
                attn_drop=attn_drop_rate,
                drop_path=dpr[i],
            )
            for i in range(num_layers)
        ])
        
        self.norm = nn.LayerNorm(embed_dim)
        self.head = nn.Linear(embed_dim, num_classes)
        
        # Initialize
        nn.init.trunc_normal_(self.pos_embed, std=0.02)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass."""
        # CNN stem
        x = self.stem(x)  # [B, C, H/4, W/4] for 2 stem layers
        
        # Project to transformer dimension
        x = self.proj(x)  # [B, embed_dim, H', W']
        
        # Flatten to sequence
        B, C, H, W = x.shape
        x = x.flatten(2).transpose(1, 2)  # [B, H*W, embed_dim]
        
        # Add positional embedding
        x = x + self.pos_embed
        x = self.pos_drop(x)
        
        # Transformer blocks
        for block in self.blocks:
            x = block(x)
        
        x = self.norm(x)
        x = x.mean(dim=1)  # Global average pooling
        x = self.head(x)
        
        return x


# Pre-defined model configurations
def ast_tiny(num_classes: int = 21, **kwargs) -> AudioSpectrogramTransformer:
    """Tiny AST: ~6M parameters, good for quick experiments."""
    return AudioSpectrogramTransformer(
        num_classes=num_classes,
        embed_dim=192,
        num_heads=3,
        num_layers=12,
        **kwargs
    )


def ast_small(num_classes: int = 21, **kwargs) -> AudioSpectrogramTransformer:
    """Small AST: ~22M parameters, good balance of speed and accuracy."""
    return AudioSpectrogramTransformer(
        num_classes=num_classes,
        embed_dim=384,
        num_heads=6,
        num_layers=12,
        **kwargs
    )


def ast_base(num_classes: int = 21, **kwargs) -> AudioSpectrogramTransformer:
    """Base AST: ~86M parameters, maximum accuracy."""
    return AudioSpectrogramTransformer(
        num_classes=num_classes,
        embed_dim=768,
        num_heads=12,
        num_layers=12,
        **kwargs
    )


def ast_lite(num_classes: int = 21, **kwargs) -> AudioSpectrogramTransformer:
    """Lite AST: ~2M parameters, designed for real-time inference."""
    return AudioSpectrogramTransformer(
        num_classes=num_classes,
        embed_dim=192,
        num_heads=3,
        num_layers=4,
        patch_size=16,
        **kwargs
    )


def ast_hybrid(num_classes: int = 21, **kwargs) -> ASTWithCNN:
    """Hybrid CNN+Transformer: Efficient and accurate."""
    return ASTWithCNN(
        num_classes=num_classes,
        embed_dim=256,
        num_heads=4,
        num_layers=4,
        **kwargs
    )


if __name__ == "__main__":
    print("Audio Spectrogram Transformer for Drum Classification")
    print("=" * 60)
    
    # Test different configurations
    configs = [
        ("AST-Lite (2M)", ast_lite),
        ("AST-Tiny (6M)", ast_tiny),
        ("AST-Hybrid", ast_hybrid),
        ("AST-Small (22M)", ast_small),
    ]
    
    for name, factory in configs:
        model = factory(num_classes=21)
        x = torch.randn(2, 1, 128, 128)
        y = model(x)
        
        print(f"\n{name}:")
        print(f"  Parameters: {model.num_parameters:,}")
        print(f"  Input: {x.shape}")
        print(f"  Output: {y.shape}")
    
    print("\n" + "=" * 60)
    print("Usage example:")
    print("""
    from training.models.ast import ast_small, ast_hybrid
    
    # Standard AST
    model = ast_small(num_classes=21, drop_rate=0.1)
    
    # Hybrid CNN+Transformer (recommended for drums)
    model = ast_hybrid(num_classes=21)
    
    # Forward pass
    mel_spec = torch.randn(32, 1, 128, 128)  # Batch of spectrograms
    logits = model(mel_spec)
    predictions = logits.argmax(dim=-1)
    """)
