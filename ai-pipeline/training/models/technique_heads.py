#!/usr/bin/env python3
"""
Technique Detection Heads for Multi-Task Drum Transcription

This module provides auxiliary prediction heads for detecting drumming techniques
beyond basic instrument classification. These techniques include:

- Flams (grace note + primary)
- Rolls (sustained repeated strokes)  
- Cymbal chokes (abrupt sustain cutoff)
- Ghost notes (very soft hits)
- Rimshots (head + rim strikes)
- Accents (emphasized hits within a pattern)
- Double strokes (RR/LL diddles)

These heads attach to the feature extractor of the main classifier and provide
multi-label technique predictions alongside the primary instrument class.

Architecture:
    Main CNN/Transformer → Feature Vector (512-d) 
                          ↓
                    ┌─────┼─────┐
                    ↓     ↓     ↓
              [Instrument] [Velocity] [Technique]
                 Head        Head       Heads
                  ↓           ↓          ↓
               21 classes   scalar   multi-label

Usage:
    from training.models.technique_heads import TechniqueHeads, TechniqueConfig
    
    # Create technique heads
    config = TechniqueConfig(input_dim=512, techniques=["flam", "roll", "choke"])
    heads = TechniqueHeads(config)
    
    # Forward pass
    features = backbone(mel_spec)  # [B, 512]
    technique_logits = heads(features)  # [B, num_techniques]

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ============================================================================
# DETECTABLE TECHNIQUES
# ============================================================================

# Core techniques that have distinct acoustic signatures
CORE_TECHNIQUES = [
    "flam",           # Grace note before main hit - detectable by double transient
    "roll",           # Sustained repeated strokes - detectable by tremolo envelope
    "buzz_roll",      # Press roll with multiple bounces - distinct from open roll
    "cymbal_choke",   # Abrupt sustain cutoff - detectable by sudden amplitude drop
    "ghost_note",     # Very soft hit (velocity < 0.2) - detectable by low amplitude
    "accent",         # Emphasized hit (velocity > 0.8) - detectable by high amplitude
    "double_stroke",  # RR/LL diddle - detectable by paired transients
    "drag",           # Multiple grace notes - similar to flam but more
]

# Supporting techniques (harder to detect but valuable)
SUPPORTING_TECHNIQUES = [
    "rimshot",        # Head + rim strike - has distinct harmonic content
    "cross_stick",    # Stick on head, tip clicks rim - woody timbre
    "dead_stroke",    # Stick stays on head - short decay envelope
    "mallet_hit",     # Soft mallet attack - rounded transient
    "brush_sweep",    # Brush motion - noise-like sustained sound
    "crash_ride",     # Riding on crash cymbal - specific decay pattern
]

# All detectable techniques
ALL_TECHNIQUES = CORE_TECHNIQUES + SUPPORTING_TECHNIQUES


@dataclass
class TechniqueConfig:
    """Configuration for technique detection heads."""
    
    # Input feature dimension from backbone
    input_dim: int = 512
    
    # Hidden dimension for technique heads
    hidden_dim: int = 256
    
    # Techniques to detect (subset of ALL_TECHNIQUES)
    techniques: List[str] = field(default_factory=lambda: CORE_TECHNIQUES)
    
    # Dropout rate
    dropout: float = 0.3
    
    # Use attention-based head (vs simple MLP)
    use_attention: bool = True
    
    # Number of attention heads (if use_attention=True)
    num_attention_heads: int = 4
    
    # Technique detection threshold for inference
    detection_threshold: float = 0.5
    
    # Per-technique class weights (for imbalanced data)
    class_weights: Optional[Dict[str, float]] = None
    
    # Multi-label loss type: "bce" or "focal"
    loss_type: str = "focal"
    
    # Focal loss gamma (if loss_type="focal")
    focal_gamma: float = 2.0


class TechniqueAttention(nn.Module):
    """
    Attention mechanism for technique detection.
    
    Each technique has a learnable query vector that attends to the
    input features, allowing the model to focus on technique-specific
    patterns in the spectrogram encoding.
    """
    
    def __init__(
        self,
        input_dim: int,
        num_techniques: int,
        num_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.num_techniques = num_techniques
        self.num_heads = num_heads
        self.head_dim = input_dim // num_heads
        
        # Learnable technique queries - each technique has its own query
        self.technique_queries = nn.Parameter(
            torch.randn(num_techniques, input_dim) * 0.02
        )
        
        # Key/Value projections for features
        self.key_proj = nn.Linear(input_dim, input_dim)
        self.value_proj = nn.Linear(input_dim, input_dim)
        
        # Output projection
        self.output_proj = nn.Linear(input_dim, 1)
        
        self.dropout = nn.Dropout(dropout)
        self.scale = self.head_dim ** -0.5
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            features: Input features [batch_size, input_dim]
        
        Returns:
            Technique logits [batch_size, num_techniques]
        """
        batch_size = features.size(0)
        
        # Project features to keys and values
        # [B, D] -> [B, D]
        keys = self.key_proj(features)
        values = self.value_proj(features)
        
        # Expand technique queries for batch
        # [T, D] -> [B, T, D]
        queries = self.technique_queries.unsqueeze(0).expand(batch_size, -1, -1)
        
        # Reshape for multi-head attention
        # [B, T, D] -> [B, T, H, D/H] -> [B, H, T, D/H]
        queries = queries.view(batch_size, self.num_techniques, self.num_heads, self.head_dim)
        queries = queries.transpose(1, 2)
        
        # [B, D] -> [B, H, 1, D/H]
        keys = keys.view(batch_size, self.num_heads, 1, self.head_dim)
        values = values.view(batch_size, self.num_heads, 1, self.head_dim)
        
        # Attention scores: [B, H, T, 1]
        attn_scores = torch.matmul(queries, keys.transpose(-2, -1)) * self.scale
        attn_probs = F.softmax(attn_scores, dim=-1)
        attn_probs = self.dropout(attn_probs)
        
        # Weighted values: [B, H, T, D/H]
        context = torch.matmul(attn_probs, values)
        
        # Reshape back: [B, H, T, D/H] -> [B, T, D]
        context = context.transpose(1, 2).contiguous()
        context = context.view(batch_size, self.num_techniques, self.input_dim)
        
        # Project to logits: [B, T, D] -> [B, T, 1] -> [B, T]
        logits = self.output_proj(context).squeeze(-1)
        
        return logits


class TechniqueHeads(nn.Module):
    """
    Multi-task technique detection heads.
    
    Attaches to the feature extractor of the main classifier and provides
    multi-label technique predictions.
    """
    
    def __init__(self, config: Optional[TechniqueConfig] = None):
        super().__init__()
        
        self.config = config or TechniqueConfig()
        self.techniques = self.config.techniques
        self.num_techniques = len(self.techniques)
        
        # Technique name to index mapping
        self.technique_to_idx = {t: i for i, t in enumerate(self.techniques)}
        self.idx_to_technique = {i: t for t, i in self.technique_to_idx.items()}
        
        if self.config.use_attention:
            # Attention-based head
            self.head = nn.Sequential(
                nn.LayerNorm(self.config.input_dim),
                TechniqueAttention(
                    input_dim=self.config.input_dim,
                    num_techniques=self.num_techniques,
                    num_heads=self.config.num_attention_heads,
                    dropout=self.config.dropout,
                ),
            )
        else:
            # Simple MLP head
            self.head = nn.Sequential(
                nn.LayerNorm(self.config.input_dim),
                nn.Linear(self.config.input_dim, self.config.hidden_dim),
                nn.GELU(),
                nn.Dropout(self.config.dropout),
                nn.Linear(self.config.hidden_dim, self.num_techniques),
            )
        
        # Class weights for loss computation
        if self.config.class_weights:
            weights = torch.tensor([
                self.config.class_weights.get(t, 1.0) for t in self.techniques
            ])
            self.register_buffer("class_weights", weights)
        else:
            self.register_buffer("class_weights", torch.ones(self.num_techniques))
    
    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """
        Args:
            features: Backbone features [batch_size, input_dim]
        
        Returns:
            Technique logits [batch_size, num_techniques]
        """
        return self.head(features)
    
    def compute_loss(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        reduction: str = "mean",
    ) -> torch.Tensor:
        """
        Compute multi-label technique detection loss.
        
        Args:
            logits: Predicted logits [batch_size, num_techniques]
            targets: Ground truth labels [batch_size, num_techniques] (0 or 1)
            reduction: Loss reduction mode
        
        Returns:
            Loss tensor
        """
        if self.config.loss_type == "focal":
            # Focal loss for handling class imbalance
            probs = torch.sigmoid(logits)
            
            # Focal weights
            pt = targets * probs + (1 - targets) * (1 - probs)
            focal_weight = (1 - pt) ** self.config.focal_gamma
            
            # Binary cross-entropy
            bce = F.binary_cross_entropy_with_logits(
                logits, targets.float(), reduction="none"
            )
            
            # Apply focal and class weights
            loss = focal_weight * bce * self.class_weights
            
        else:  # BCE
            loss = F.binary_cross_entropy_with_logits(
                logits, targets.float(),
                weight=self.class_weights,
                reduction="none",
            )
        
        if reduction == "mean":
            return loss.mean()
        elif reduction == "sum":
            return loss.sum()
        else:
            return loss
    
    def predict(
        self,
        features: torch.Tensor,
        threshold: Optional[float] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Predict techniques from features.
        
        Args:
            features: Backbone features [batch_size, input_dim]
            threshold: Detection threshold (uses config default if None)
        
        Returns:
            Tuple of (probabilities, binary_predictions)
        """
        threshold = threshold or self.config.detection_threshold
        
        logits = self.forward(features)
        probs = torch.sigmoid(logits)
        preds = (probs >= threshold).long()
        
        return probs, preds
    
    def decode_predictions(
        self,
        predictions: torch.Tensor,
    ) -> List[List[str]]:
        """
        Convert binary predictions to technique names.
        
        Args:
            predictions: Binary predictions [batch_size, num_techniques]
        
        Returns:
            List of technique name lists for each sample
        """
        batch_size = predictions.size(0)
        results = []
        
        for i in range(batch_size):
            techniques = []
            for j in range(self.num_techniques):
                if predictions[i, j] == 1:
                    techniques.append(self.idx_to_technique[j])
            results.append(techniques)
        
        return results


class IntegratedTechniqueModel(nn.Module):
    """
    Wrapper that combines a backbone classifier with technique detection heads.
    
    This allows training the full model end-to-end with multi-task learning.
    """
    
    def __init__(
        self,
        backbone: nn.Module,
        technique_config: Optional[TechniqueConfig] = None,
        technique_loss_weight: float = 0.2,
    ):
        super().__init__()
        
        self.backbone = backbone
        self.technique_heads = TechniqueHeads(technique_config)
        self.technique_loss_weight = technique_loss_weight
        
        # Get feature dimension from backbone
        # Assumes backbone has a get_feature_dim() method or fc.in_features
        if hasattr(backbone, "get_feature_dim"):
            self.feature_dim = backbone.get_feature_dim()
        elif hasattr(backbone, "fc"):
            self.feature_dim = backbone.fc.in_features
        else:
            raise ValueError("Cannot determine feature dimension from backbone")
        
        # Verify dimensions match
        if self.feature_dim != technique_config.input_dim:
            # Add projection layer
            self.feature_proj = nn.Linear(self.feature_dim, technique_config.input_dim)
        else:
            self.feature_proj = nn.Identity()
    
    def forward(
        self,
        x: torch.Tensor,
        return_features: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass returning both classification and technique predictions.
        
        Args:
            x: Input spectrogram [batch_size, 1, freq, time]
            return_features: Whether to return intermediate features
        
        Returns:
            Dict with keys:
                - "class_logits": Instrument class logits
                - "technique_logits": Technique detection logits
                - "features": (optional) Intermediate features
        """
        # Get features from backbone
        if hasattr(self.backbone, "extract_features"):
            features = self.backbone.extract_features(x)
            class_logits = self.backbone.fc(features)
        else:
            # Fallback: run full forward and extract from intermediate
            class_logits = self.backbone(x)
            features = None  # Would need hooks to extract
        
        if features is None:
            raise ValueError(
                "Backbone must have extract_features() method for technique detection"
            )
        
        # Project features if needed
        technique_features = self.feature_proj(features)
        
        # Get technique predictions
        technique_logits = self.technique_heads(technique_features)
        
        output = {
            "class_logits": class_logits,
            "technique_logits": technique_logits,
        }
        
        if return_features:
            output["features"] = features
        
        return output
    
    def compute_loss(
        self,
        outputs: Dict[str, torch.Tensor],
        class_targets: torch.Tensor,
        technique_targets: torch.Tensor,
        class_criterion: nn.Module,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute combined loss for classification and technique detection.
        
        Returns:
            Dict with "total", "class", and "technique" losses
        """
        class_loss = class_criterion(outputs["class_logits"], class_targets)
        technique_loss = self.technique_heads.compute_loss(
            outputs["technique_logits"], technique_targets
        )
        
        total_loss = class_loss + self.technique_loss_weight * technique_loss
        
        return {
            "total": total_loss,
            "class": class_loss,
            "technique": technique_loss,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_technique_heads(
    preset: str = "core",
    input_dim: int = 512,
    **kwargs,
) -> TechniqueHeads:
    """
    Get pre-configured technique detection heads.
    
    Presets:
        core: 8 core techniques (flam, roll, choke, ghost, accent, etc.)
        full: All 14 detectable techniques
        minimal: Just ghost/accent/choke (3 techniques)
        articulation: Focus on articulation techniques (rimshot, cross_stick, etc.)
    """
    if preset == "full":
        techniques = ALL_TECHNIQUES
    elif preset == "minimal":
        techniques = ["ghost_note", "accent", "cymbal_choke"]
    elif preset == "articulation":
        techniques = ["rimshot", "cross_stick", "dead_stroke", "flam", "drag"]
    else:  # core
        techniques = CORE_TECHNIQUES
    
    config = TechniqueConfig(
        input_dim=input_dim,
        techniques=techniques,
        **kwargs,
    )
    
    return TechniqueHeads(config)


if __name__ == "__main__":
    print("🥁 Technique Detection Heads Test")
    print("=" * 50)
    
    # Test configuration
    config = TechniqueConfig(
        input_dim=512,
        techniques=CORE_TECHNIQUES,
        use_attention=True,
    )
    
    print(f"Detecting {len(config.techniques)} techniques:")
    for t in config.techniques:
        print(f"  - {t}")
    
    # Create heads
    heads = TechniqueHeads(config)
    print(f"\nModel parameters: {sum(p.numel() for p in heads.parameters()):,}")
    
    # Test forward pass
    batch_size = 4
    features = torch.randn(batch_size, 512)
    
    logits = heads(features)
    print(f"\nInput shape: {features.shape}")
    print(f"Output shape: {logits.shape}")
    
    # Test prediction
    probs, preds = heads.predict(features)
    decoded = heads.decode_predictions(preds)
    
    print(f"\nSample predictions:")
    for i, techniques in enumerate(decoded):
        print(f"  Sample {i}: {techniques if techniques else '(none)'}")
    
    # Test loss computation
    targets = torch.randint(0, 2, (batch_size, len(CORE_TECHNIQUES)))
    loss = heads.compute_loss(logits, targets)
    print(f"\nFocal loss: {loss.item():.4f}")
    
    print("\n✅ Technique Detection Heads working correctly!")
