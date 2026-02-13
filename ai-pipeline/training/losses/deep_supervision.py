"""
Deep Supervision for CNN Training

Deep Supervision adds auxiliary classification heads at intermediate layers,
forcing the network to learn good features throughout the entire architecture.
This improves gradient flow and acts as regularization.

Paper: "Deeply-Supervised Nets" (Lee et al., AISTATS 2015)
       https://arxiv.org/abs/1409.5185

Key Benefits:
1. +1-2% accuracy improvement
2. Better gradient flow through deep networks  
3. Forces all layers to learn discriminative features
4. Acts as implicit regularization
5. Helps with training stability

For drum classification:
- Early layers learn basic frequency patterns
- Middle layers learn transient shapes
- Deep layers learn drum identity
- All layers contribute to final prediction

Usage:
    from training.losses.deep_supervision import DeepSupervision, DeepSupervisionLoss
    
    # Wrap model with deep supervision
    model = DrumClassifierCNNv4(num_classes=21)
    ds_model = DeepSupervision(model, aux_layers=[1, 2, 3])
    
    # Training
    outputs = ds_model(x)  # Returns (main_logits, [aux1, aux2, aux3])
    loss = ds_loss(outputs, targets)

References:
    - Original Paper: https://arxiv.org/abs/1409.5185  
    - U-Net uses this: https://arxiv.org/abs/1505.04597
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Dict, List, Optional, Tuple, Union


class AuxiliaryHead(nn.Module):
    """
    Auxiliary classification head for intermediate features.
    
    Takes features from an intermediate layer and produces class predictions.
    Uses adaptive pooling to handle variable spatial sizes.
    
    Args:
        in_channels: Number of input channels from intermediate layer
        num_classes: Number of output classes
        hidden_dim: Hidden layer dimension (default: None = in_channels // 2)
        dropout: Dropout rate
    """
    
    def __init__(
        self,
        in_channels: int,
        num_classes: int,
        hidden_dim: Optional[int] = None,
        dropout: float = 0.3
    ):
        super().__init__()
        
        hidden_dim = hidden_dim or max(64, in_channels // 2)
        
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(in_channels, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool(x)
        return self.classifier(x)


class DeepSupervision(nn.Module):
    """
    Wrapper that adds deep supervision to a CNN model.
    
    Attaches auxiliary classification heads to intermediate layers
    and returns their outputs alongside the main prediction.
    
    Args:
        model: Base CNN model (must have 'features' as Sequential)
        num_classes: Number of output classes
        aux_indices: Indices of blocks to add auxiliary heads
        aux_weight: Weight for auxiliary losses (decreases with depth)
        aux_hidden: Hidden dimension for aux heads
        
    Usage:
        model = DrumClassifierCNNv4(num_classes=21)
        ds_model = DeepSupervision(model, num_classes=21, aux_indices=[2, 4, 6])
        
        main_out, aux_outs = ds_model(x)
        # main_out: [B, 21]
        # aux_outs: [[B, 21], [B, 21], [B, 21]]
    """
    
    def __init__(
        self,
        model: nn.Module,
        num_classes: int,
        aux_indices: Optional[List[int]] = None,
        aux_weight: float = 0.4,
        aux_hidden: Optional[int] = None,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.model = model
        self.num_classes = num_classes
        self.aux_weight = aux_weight
        
        # Find feature layers
        if hasattr(model, 'features') and isinstance(model.features, nn.Sequential):
            self.feature_layers = list(model.features.children())
        else:
            raise ValueError("Model must have 'features' attribute as nn.Sequential")
        
        num_layers = len(self.feature_layers)
        
        # Default: add aux heads at 1/3 and 2/3 of the network
        if aux_indices is None:
            aux_indices = [num_layers // 3, 2 * num_layers // 3]
        
        self.aux_indices = aux_indices
        
        # Create auxiliary heads
        self.aux_heads = nn.ModuleDict()
        
        # Run a forward pass to get channel dimensions
        with torch.no_grad():
            x = torch.zeros(1, 1, 128, 128)  # Dummy input
            for i, layer in enumerate(self.feature_layers):
                x = layer(x)
                if i in aux_indices:
                    channels = x.shape[1]
                    self.aux_heads[str(i)] = AuxiliaryHead(
                        channels, num_classes, aux_hidden, dropout
                    )
        
        # Weights for aux heads (decrease with depth)
        self.aux_weights = {}
        for i, idx in enumerate(sorted(aux_indices)):
            # Earlier layers get lower weight
            weight = aux_weight * (i + 1) / len(aux_indices)
            self.aux_weights[str(idx)] = weight
    
    def forward(
        self, 
        x: torch.Tensor,
        return_aux: bool = True
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, List[torch.Tensor]]]:
        """
        Forward pass with deep supervision.
        
        Args:
            x: Input tensor [B, C, H, W]
            return_aux: Whether to return auxiliary outputs
            
        Returns:
            If return_aux=False: main logits [B, num_classes]
            If return_aux=True: (main logits, [aux1, aux2, ...])
        """
        aux_outputs = []
        
        # Forward through feature layers
        for i, layer in enumerate(self.feature_layers):
            x = layer(x)
            
            if str(i) in self.aux_heads:
                aux_out = self.aux_heads[str(i)](x)
                aux_outputs.append(aux_out)
        
        # Main classifier (after features)
        if hasattr(self.model, 'global_pool'):
            x = self.model.global_pool(x)
        if hasattr(self.model, 'classifier'):
            main_out = self.model.classifier(x)
        else:
            main_out = x.flatten(1)
        
        if return_aux:
            return main_out, aux_outputs
        return main_out
    
    def get_aux_weights(self) -> Dict[str, float]:
        """Get weights for each auxiliary head."""
        return self.aux_weights


class DeepSupervisionLoss(nn.Module):
    """
    Loss function for deep supervision training.
    
    Combines main classification loss with weighted auxiliary losses.
    
    Args:
        base_criterion: Loss function for classification
        aux_weight_decay: How much to decay aux weights (closer to output = higher weight)
        aux_weight: Base weight for auxiliary losses
        
    Usage:
        criterion = DeepSupervisionLoss()
        main_out, aux_outs = ds_model(x)
        loss = criterion(main_out, aux_outs, targets)
    """
    
    def __init__(
        self,
        base_criterion: Optional[nn.Module] = None,
        aux_weight: float = 0.4,
        aux_weight_decay: str = "linear"  # "linear", "exponential", "constant"
    ):
        super().__init__()
        
        self.base_criterion = base_criterion or nn.CrossEntropyLoss()
        self.aux_weight = aux_weight
        self.aux_weight_decay = aux_weight_decay
    
    def forward(
        self,
        main_output: torch.Tensor,
        aux_outputs: List[torch.Tensor],
        targets: torch.Tensor,
        aux_weights: Optional[Dict[str, float]] = None
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute total loss with deep supervision.
        
        Args:
            main_output: Main classifier output [B, C]
            aux_outputs: List of auxiliary outputs [[B, C], ...]
            targets: Ground truth labels [B]
            aux_weights: Optional custom weights for each aux head
            
        Returns:
            total_loss: Combined loss scalar
            loss_dict: Individual loss components
        """
        # Main loss
        main_loss = self.base_criterion(main_output, targets)
        
        loss_dict = {"main": main_loss.item()}
        total_loss = main_loss
        
        # Auxiliary losses
        num_aux = len(aux_outputs)
        for i, aux_out in enumerate(aux_outputs):
            # Compute weight for this aux head
            if aux_weights and str(i) in aux_weights:
                weight = aux_weights[str(i)]
            else:
                if self.aux_weight_decay == "linear":
                    weight = self.aux_weight * (i + 1) / num_aux
                elif self.aux_weight_decay == "exponential":
                    weight = self.aux_weight * (0.5 ** (num_aux - i - 1))
                else:  # constant
                    weight = self.aux_weight
            
            aux_loss = self.base_criterion(aux_out, targets)
            total_loss = total_loss + weight * aux_loss
            loss_dict[f"aux_{i}"] = aux_loss.item()
        
        loss_dict["total"] = total_loss.item()
        return total_loss, loss_dict


class DeepSupervisionCNNv4(nn.Module):
    """
    DrumClassifierCNNv4 with built-in deep supervision.
    
    This extends v4 with auxiliary heads at intermediate blocks.
    
    Args:
        num_classes: Number of drum classes
        base_channels: Base channel count
        use_coord_attention: Whether to use CoordinateAttention
        use_deep_supervision: Whether to enable auxiliary heads
        aux_indices: Which blocks to add aux heads
        drop_path_rate: Stochastic depth rate
    """
    
    def __init__(
        self,
        num_classes: int = 21,
        in_channels: int = 1,
        base_channels: int = 32,
        use_coord_attention: bool = True,
        use_deep_supervision: bool = True,
        aux_indices: Optional[List[int]] = None,
        drop_path_rate: float = 0.1,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.num_classes = num_classes
        self.use_deep_supervision = use_deep_supervision
        
        # Import coord attention
        from training.models.coord_attention import CoordinateAttention
        from training.utils.stochastic_depth import DropPath
        
        # Channel progression: 32 -> 64 -> 128 -> 256
        channels = [base_channels, base_channels * 2, base_channels * 4, base_channels * 8]
        
        # Stochastic depth rates
        num_blocks = len(channels)
        drop_rates = [drop_path_rate * i / (num_blocks - 1) for i in range(num_blocks)]
        
        # Build blocks
        self.blocks = nn.ModuleList()
        prev_ch = in_channels
        
        for i, (ch, dp) in enumerate(zip(channels, drop_rates)):
            block = nn.Sequential(
                nn.Conv2d(prev_ch, ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(ch),
                nn.ReLU(inplace=True),
                CoordinateAttention(ch) if use_coord_attention else nn.Identity(),
                DropPath(dp) if dp > 0 else nn.Identity(),
                nn.MaxPool2d(2, 2)
            )
            self.blocks.append(block)
            prev_ch = ch
        
        # Auxiliary heads
        if aux_indices is None:
            aux_indices = [1, 2]  # After 2nd and 3rd blocks
        
        self.aux_indices = aux_indices
        self.aux_heads = nn.ModuleDict()
        
        if use_deep_supervision:
            for idx in aux_indices:
                ch = channels[idx]
                self.aux_heads[str(idx)] = AuxiliaryHead(ch, num_classes, dropout=dropout)
        
        # Main classifier
        self.global_pool = nn.AdaptiveAvgPool2d(1)
        self.feature_dim = channels[-1]
        
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim, self.feature_dim // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(self.feature_dim // 2, num_classes)
        )
    
    def forward(
        self, 
        x: torch.Tensor,
        return_aux: bool = True
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, List[torch.Tensor]]]:
        """Forward pass with optional deep supervision."""
        aux_outputs = []
        
        # Forward through blocks
        for i, block in enumerate(self.blocks):
            x = block(x)
            
            if self.use_deep_supervision and str(i) in self.aux_heads:
                aux_out = self.aux_heads[str(i)](x)
                aux_outputs.append(aux_out)
        
        # Main classifier
        pooled = self.global_pool(x)
        main_out = self.classifier(pooled)
        
        if return_aux and self.use_deep_supervision:
            return main_out, aux_outputs
        return main_out
    
    def forward_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract features without classification."""
        for block in self.blocks:
            x = block(x)
        return self.global_pool(x).flatten(1)


def add_deep_supervision_to_model(
    model: nn.Module,
    num_classes: int,
    aux_indices: Optional[List[int]] = None
) -> DeepSupervision:
    """
    Add deep supervision to an existing model.
    
    Args:
        model: Base model with 'features' Sequential
        num_classes: Number of classes
        aux_indices: Which layers to add aux heads
        
    Returns:
        Model wrapped with DeepSupervision
    """
    return DeepSupervision(model, num_classes, aux_indices)


# =============================================================================
# Integration with training loop
# =============================================================================

def train_step_with_deep_supervision(
    model: DeepSupervision,
    inputs: torch.Tensor,
    targets: torch.Tensor,
    criterion: DeepSupervisionLoss,
    optimizer: torch.optim.Optimizer
) -> Dict[str, float]:
    """
    Single training step with deep supervision.
    
    Example usage in training loop:
        for inputs, targets in dataloader:
            loss_dict = train_step_with_deep_supervision(
                model, inputs, targets, criterion, optimizer
            )
    """
    optimizer.zero_grad()
    
    main_out, aux_outs = model(inputs, return_aux=True)
    loss, loss_dict = criterion(main_out, aux_outs, targets, model.get_aux_weights())
    
    loss.backward()
    optimizer.step()
    
    # Add accuracy
    pred = main_out.argmax(dim=1)
    acc = (pred == targets).float().mean().item()
    loss_dict["accuracy"] = acc
    
    return loss_dict


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing Deep Supervision...")
    
    # Test AuxiliaryHead
    aux_head = AuxiliaryHead(in_channels=128, num_classes=21)
    x = torch.randn(4, 128, 16, 16)
    out = aux_head(x)
    print(f"AuxiliaryHead: {x.shape} -> {out.shape}")
    
    # Test DeepSupervisionCNNv4
    print("\nTesting DeepSupervisionCNNv4...")
    model = DeepSupervisionCNNv4(
        num_classes=21,
        use_deep_supervision=True,
        drop_path_rate=0.1
    )
    
    x = torch.randn(4, 1, 128, 128)
    main_out, aux_outs = model(x)
    
    print(f"Input: {x.shape}")
    print(f"Main output: {main_out.shape}")
    print(f"Aux outputs: {[a.shape for a in aux_outs]}")
    
    # Test loss
    print("\nTesting DeepSupervisionLoss...")
    criterion = DeepSupervisionLoss(aux_weight=0.4)
    targets = torch.randint(0, 21, (4,))
    
    loss, loss_dict = criterion(main_out, aux_outs, targets)
    print(f"Loss components: {loss_dict}")
    print(f"Total loss: {loss.item():.4f}")
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\nTotal parameters: {total_params:,}")
    
    print("\n✅ Deep Supervision working!")
