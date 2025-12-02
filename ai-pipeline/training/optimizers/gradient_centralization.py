"""
Gradient Centralization Optimizer Wrapper

Gradient Centralization (GC) is a simple yet effective optimization technique
that centralizes gradients to have zero mean before applying updates. This
provides implicit regularization and can improve generalization by 0.5-1%.

Paper: "Gradient Centralization: A New Optimization Technique for DNNs" (ECCV 2020)
       https://arxiv.org/abs/2004.01461

Key Benefits:
1. Zero additional memory cost
2. Negligible computational overhead
3. Compatible with any optimizer (SGD, Adam, AdamW, SAM, etc.)
4. Consistent improvements across architectures
5. Acts as implicit regularization

How it works:
- For weight gradients (not biases): subtract mean across columns
- This constrains weight updates to lie in a hyperplane
- Prevents gradient explosion and improves conditioning

Why it helps for drum classification:
- More stable training with spectrograms
- Better generalization to unseen recordings
- Works synergistically with SAM, SWA, and other optimizers

Usage:
    from training.optimizers.gradient_centralization import centralize_gradient, GC_SGD, GC_Adam
    
    # Option 1: Use pre-wrapped optimizers
    optimizer = GC_Adam(model.parameters(), lr=1e-3)
    
    # Option 2: Wrap any optimizer
    base_optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    optimizer = GradientCentralization(base_optimizer)
    
    # Option 3: Manual application (for custom training loops)
    loss.backward()
    centralize_gradient(model.parameters(), use_gc=True)
    optimizer.step()

References:
    - Original Paper: https://arxiv.org/abs/2004.01461
    - Official Implementation: https://github.com/Yonghongwei/Gradient-Centralization
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torch.optim import Optimizer
from typing import Any, Callable, Dict, Iterable, Optional


def centralize_gradient(
    parameters: Iterable[torch.Tensor],
    use_gc: bool = True,
    gc_conv_only: bool = False
) -> None:
    """
    Apply gradient centralization to parameter gradients in-place.
    
    For each weight tensor (not bias), subtracts the mean gradient
    across output features, centralizing the gradient.
    
    Args:
        parameters: Model parameters to centralize
        use_gc: Whether to apply centralization (for easy toggling)
        gc_conv_only: Only apply to conv layers (dim >= 4)
        
    Note:
        - Only applies to weights, not biases (1D tensors)
        - For conv weights: centralize across (in_ch, kH, kW)
        - For linear weights: centralize across (in_features)
    """
    if not use_gc:
        return
    
    for param in parameters:
        if param.grad is None:
            continue
        
        grad = param.grad.data
        
        # Skip biases (1D tensors) and very small tensors
        if grad.dim() <= 1:
            continue
        
        # If gc_conv_only, skip non-conv layers (< 4 dims)
        if gc_conv_only and grad.dim() < 4:
            continue
        
        # Centralize: subtract mean across all dimensions except the first (output channels)
        # For Linear [out, in]: mean over dim=1 (in_features)
        # For Conv2d [out, in, kH, kW]: mean over dims=(1,2,3)
        if grad.dim() == 2:
            # Linear layer: [out_features, in_features]
            grad.add_(-grad.mean(dim=1, keepdim=True))
        elif grad.dim() >= 3:
            # Conv layer: [out_channels, in_channels, ...]
            # Compute mean across all dims except first
            dims_to_reduce = tuple(range(1, grad.dim()))
            grad.add_(-grad.mean(dim=dims_to_reduce, keepdim=True))


class GradientCentralization(Optimizer):
    """
    Optimizer wrapper that applies gradient centralization before updates.
    
    This wraps any PyTorch optimizer and applies GC to gradients
    before the optimization step. Inherits from Optimizer for compatibility
    with PyTorch LR schedulers.
    
    Args:
        optimizer: Base optimizer to wrap
        use_gc: Whether to apply gradient centralization
        gc_conv_only: Only apply to convolutional layers
        
    Usage:
        base_opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
        optimizer = GradientCentralization(base_opt)
        
        # Training loop
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()  # GC applied automatically
    """
    
    def __init__(
        self,
        optimizer: Optimizer,
        use_gc: bool = True,
        gc_conv_only: bool = False
    ):
        # Store the base optimizer
        self.optimizer = optimizer
        self.use_gc = use_gc
        self.gc_conv_only = gc_conv_only
        
        # Collect parameters for centralization
        self._params = []
        for group in optimizer.param_groups:
            self._params.extend(group['params'])
        
        # Initialize Optimizer base class with the same param_groups and defaults
        # This is required for LR scheduler compatibility
        self._param_groups = optimizer.param_groups
        self._defaults = getattr(optimizer, 'defaults', {})
    
    @property
    def param_groups(self):
        return self.optimizer.param_groups
    
    @param_groups.setter
    def param_groups(self, value):
        self.optimizer.param_groups = value
    
    @property
    def defaults(self):
        return self._defaults
    
    @defaults.setter
    def defaults(self, value):
        self._defaults = value
    
    @property
    def state(self):
        return self.optimizer.state
    
    @state.setter
    def state(self, value):
        self.optimizer.state = value
    
    def zero_grad(self, set_to_none: bool = False):
        self.optimizer.zero_grad(set_to_none=set_to_none)
    
    def step(self, closure: Optional[Callable] = None):
        """Apply gradient centralization and then step."""
        centralize_gradient(self._params, self.use_gc, self.gc_conv_only)
        return self.optimizer.step(closure)
    
    def state_dict(self) -> Dict[str, Any]:
        """
        Return state dict that captures both the wrapper and underlying optimizer state.
        
        Returns a dict with:
            - 'optimizer': The underlying optimizer's state dict (has 'state' and 'param_groups')
            - 'gc_config': GradientCentralization configuration (use_gc, gc_conv_only)
        """
        return {
            'optimizer': self.optimizer.state_dict(),
            'gc_config': {
                'use_gc': self.use_gc,
                'gc_conv_only': self.gc_conv_only
            }
        }
    
    def load_state_dict(self, state_dict: Dict[str, Any]) -> None:
        """
        Load state dict, handling multiple formats for backward compatibility.
        
        Supported formats:
            1. GradientCentralization format: {'optimizer': {...}, 'gc_config': {...}}
            2. Raw optimizer format: {'state': {...}, 'param_groups': [...]}
            3. Lookahead wrapper format: {'optimizer': {...}, 'slow_state': {...}, ...}
               (When resuming without Lookahead from a checkpoint saved with Lookahead)
            4. Legacy format (for old checkpoints that directly saved underlying optimizer)
        """
        # Format 1: New GradientCentralization wrapper format
        if 'optimizer' in state_dict and 'gc_config' in state_dict:
            self.optimizer.load_state_dict(state_dict['optimizer'])
            gc_config = state_dict.get('gc_config', {})
            self.use_gc = gc_config.get('use_gc', self.use_gc)
            self.gc_conv_only = gc_config.get('gc_conv_only', self.gc_conv_only)
            return
        
        # Format 2: Standard PyTorch optimizer format (has 'state' and 'param_groups')
        if 'param_groups' in state_dict and 'state' in state_dict:
            self.optimizer.load_state_dict(state_dict)
            return
        
        # Format 3: Lookahead wrapper format - extract inner optimizer state
        # This happens when resuming without Lookahead from a checkpoint saved with Lookahead
        if 'optimizer' in state_dict and 'slow_state' in state_dict:
            print("[GC] Note: Loading from Lookahead checkpoint (Lookahead state will be ignored)")
            inner_state = state_dict['optimizer']
            # The inner state should be a standard optimizer format or GC format
            self.load_state_dict(inner_state)
            return
        
        # Format 3b: Just has 'optimizer' key without gc_config (old GC format or partial Lookahead)
        if 'optimizer' in state_dict and 'gc_config' not in state_dict and 'slow_state' not in state_dict:
            inner_state = state_dict['optimizer']
            if isinstance(inner_state, dict):
                self.load_state_dict(inner_state)
                return
        
        # Format 4: Legacy - might just have 'state' without 'param_groups' 
        # This can happen if someone accidentally saved partial state
        # Try to reconstruct a valid state dict
        if 'state' in state_dict and 'param_groups' not in state_dict:
            # Create a minimal valid state dict using current param_groups
            reconstructed = {
                'state': state_dict['state'],
                'param_groups': self.optimizer.param_groups
            }
            try:
                self.optimizer.load_state_dict(reconstructed)
                print("[GC] Warning: Loaded partial state dict (missing param_groups), "
                      "using current param_groups. LR may have been reset.")
                return
            except Exception as e:
                print(f"[GC] Warning: Could not reconstruct state dict: {e}")
        
        # Format 5: Possibly the entire checkpoint was passed instead of just optimizer state
        # This shouldn't happen, but let's be defensive
        if 'optimizer_state' in state_dict:
            print("[GC] Warning: Received full checkpoint instead of optimizer state, extracting...")
            self.load_state_dict(state_dict['optimizer_state'])
            return
        
        # Last resort: try to load directly and hope for the best
        try:
            self.optimizer.load_state_dict(state_dict)
        except Exception as e:
            raise ValueError(
                f"[GC] Could not load optimizer state dict. "
                f"Expected format with 'param_groups' and 'state' keys, "
                f"but got keys: {list(state_dict.keys())}. Error: {e}"
            )
    
    def add_param_group(self, param_group: dict):
        self.optimizer.add_param_group(param_group)
        self._params.extend(param_group['params'])


class GC_SGD(torch.optim.SGD):
    """
    SGD optimizer with built-in Gradient Centralization.
    
    Usage:
        optimizer = GC_SGD(model.parameters(), lr=0.1, momentum=0.9, use_gc=True)
    """
    
    def __init__(
        self,
        params,
        lr: float = 0.01,
        momentum: float = 0,
        dampening: float = 0,
        weight_decay: float = 0,
        nesterov: bool = False,
        use_gc: bool = True,
        gc_conv_only: bool = False
    ):
        super().__init__(
            params, lr=lr, momentum=momentum, dampening=dampening,
            weight_decay=weight_decay, nesterov=nesterov
        )
        self.use_gc = use_gc
        self.gc_conv_only = gc_conv_only
    
    def step(self, closure: Optional[Callable] = None):
        # Collect all parameters
        all_params = []
        for group in self.param_groups:
            all_params.extend(group['params'])
        
        # Apply gradient centralization
        centralize_gradient(all_params, self.use_gc, self.gc_conv_only)
        
        # Standard SGD step
        return super().step(closure)


class GC_Adam(torch.optim.Adam):
    """
    Adam optimizer with built-in Gradient Centralization.
    
    Usage:
        optimizer = GC_Adam(model.parameters(), lr=1e-3, use_gc=True)
    """
    
    def __init__(
        self,
        params,
        lr: float = 1e-3,
        betas: tuple = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 0,
        amsgrad: bool = False,
        use_gc: bool = True,
        gc_conv_only: bool = False
    ):
        super().__init__(
            params, lr=lr, betas=betas, eps=eps,
            weight_decay=weight_decay, amsgrad=amsgrad
        )
        self.use_gc = use_gc
        self.gc_conv_only = gc_conv_only
    
    def step(self, closure: Optional[Callable] = None):
        all_params = []
        for group in self.param_groups:
            all_params.extend(group['params'])
        
        centralize_gradient(all_params, self.use_gc, self.gc_conv_only)
        return super().step(closure)


class GC_AdamW(torch.optim.AdamW):
    """
    AdamW optimizer with built-in Gradient Centralization.
    
    This is the recommended optimizer for transformers and modern CNNs.
    
    Usage:
        optimizer = GC_AdamW(model.parameters(), lr=1e-3, weight_decay=0.01, use_gc=True)
    """
    
    def __init__(
        self,
        params,
        lr: float = 1e-3,
        betas: tuple = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 0.01,
        amsgrad: bool = False,
        use_gc: bool = True,
        gc_conv_only: bool = False
    ):
        super().__init__(
            params, lr=lr, betas=betas, eps=eps,
            weight_decay=weight_decay, amsgrad=amsgrad
        )
        self.use_gc = use_gc
        self.gc_conv_only = gc_conv_only
    
    def step(self, closure: Optional[Callable] = None):
        all_params = []
        for group in self.param_groups:
            all_params.extend(group['params'])
        
        centralize_gradient(all_params, self.use_gc, self.gc_conv_only)
        return super().step(closure)


def wrap_optimizer_with_gc(
    optimizer: Optimizer,
    use_gc: bool = True,
    gc_conv_only: bool = False
) -> GradientCentralization:
    """
    Convenience function to wrap any optimizer with gradient centralization.
    
    Args:
        optimizer: Any PyTorch optimizer
        use_gc: Whether to enable gradient centralization
        gc_conv_only: Only apply to convolutional layers
        
    Returns:
        Wrapped optimizer with GC
    
    Example:
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        optimizer = wrap_optimizer_with_gc(optimizer)
    """
    return GradientCentralization(optimizer, use_gc, gc_conv_only)


# =============================================================================
# Integration with SAM (Sharpness-Aware Minimization)
# =============================================================================

def apply_gc_to_sam_optimizer(sam_optimizer, use_gc: bool = True, gc_conv_only: bool = False):
    """
    Apply gradient centralization to a SAM optimizer.
    
    SAM has a custom training loop with first_step() and second_step().
    This function patches the SAM optimizer to apply GC before each step.
    
    Usage:
        from training.optimizers.sam import SAM
        optimizer = SAM(model.parameters(), torch.optim.SGD, lr=0.1, rho=0.05)
        apply_gc_to_sam_optimizer(optimizer, use_gc=True)
        
        # Training loop (unchanged)
        loss.backward()
        optimizer.first_step(zero_grad=True)
        criterion(model(x), y).backward()
        optimizer.second_step(zero_grad=True)
    """
    if not use_gc:
        return sam_optimizer
    
    # Store original methods
    original_first_step = sam_optimizer.first_step
    original_second_step = sam_optimizer.second_step
    
    def gc_first_step(zero_grad: bool = False):
        # Collect params
        all_params = []
        for group in sam_optimizer.param_groups:
            all_params.extend(group['params'])
        centralize_gradient(all_params, use_gc=True, gc_conv_only=gc_conv_only)
        return original_first_step(zero_grad)
    
    def gc_second_step(zero_grad: bool = False):
        all_params = []
        for group in sam_optimizer.param_groups:
            all_params.extend(group['params'])
        centralize_gradient(all_params, use_gc=True, gc_conv_only=gc_conv_only)
        return original_second_step(zero_grad)
    
    # Monkey-patch
    sam_optimizer.first_step = gc_first_step
    sam_optimizer.second_step = gc_second_step
    
    return sam_optimizer


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing Gradient Centralization...")
    
    # Create a simple model
    model = nn.Sequential(
        nn.Conv2d(1, 32, 3, padding=1),
        nn.ReLU(),
        nn.Conv2d(32, 64, 3, padding=1),
        nn.ReLU(),
        nn.AdaptiveAvgPool2d(1),
        nn.Flatten(),
        nn.Linear(64, 10)
    )
    
    # Test GC_AdamW
    optimizer = GC_AdamW(model.parameters(), lr=1e-3, use_gc=True)
    
    # Forward pass
    x = torch.randn(4, 1, 32, 32)
    y = torch.randint(0, 10, (4,))
    
    loss = nn.CrossEntropyLoss()(model(x), y)
    loss.backward()
    
    # Check gradients before GC
    conv1_grad_before = model[0].weight.grad.clone()
    
    # Step (applies GC internally)
    optimizer.step()
    
    print("✅ GC_AdamW working!")
    print(f"   Conv1 gradient shape: {conv1_grad_before.shape}")
    print(f"   Mean before GC (dim=1,2,3): {conv1_grad_before.mean(dim=(1,2,3)).abs().mean():.6f}")
    
    # Test wrapper
    model2 = nn.Linear(10, 5)
    base_opt = torch.optim.Adam(model2.parameters())
    wrapped_opt = wrap_optimizer_with_gc(base_opt)
    
    x2 = torch.randn(4, 10)
    y2 = torch.randint(0, 5, (4,))
    loss2 = nn.CrossEntropyLoss()(model2(x2), y2)
    loss2.backward()
    wrapped_opt.step()
    
    print("✅ Wrapped optimizer working!")
