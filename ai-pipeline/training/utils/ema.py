"""
Exponential Moving Average (EMA) for Model Weights

EMA maintains a shadow copy of model weights that is updated as an exponential
moving average of the training weights. This typically improves final model
quality by 0.5-1% and provides smoother convergence.

Reference: Used in virtually all SOTA models (EfficientNet, Vision Transformers, etc.)

The update rule is:
    ema_weights = decay * ema_weights + (1 - decay) * model_weights

Why this helps:
- Smooths out noisy gradient updates
- Acts as implicit ensemble of weights across training
- Better generalization (flatter minima)
- Free improvement with minimal overhead

Usage:
    from training.utils.ema import ModelEMA
    
    model = DrumClassifierCNN(...)
    ema = ModelEMA(model, decay=0.999)
    
    for batch in dataloader:
        loss = train_step(model, batch)
        loss.backward()
        optimizer.step()
        ema.update()  # Update EMA weights
    
    # For evaluation, use EMA model
    ema_predictions = ema.ema_model(test_batch)
    
    # Or copy EMA weights to main model for saving
    ema.copy_to(model)
"""

from __future__ import annotations

import copy
from typing import Optional

import torch
import torch.nn as nn


class ModelEMA:
    """
    Exponential Moving Average of model weights.
    
    Maintains a shadow copy of the model that is updated with EMA.
    The EMA model typically performs better than the final training weights.
    
    Args:
        model: The model to track
        decay: EMA decay factor (0.999 = slow update, 0.99 = faster update)
            Higher decay = more smoothing, slower to adapt
            Typical values: 0.999 (stable), 0.9999 (very stable), 0.99 (adaptive)
        warmup_steps: Number of steps before reaching target decay (optional)
            Uses linear warmup from 0.5 to target decay
        device: Device to store EMA model (None = same as input model)
    """
    
    def __init__(
        self,
        model: nn.Module,
        decay: float = 0.999,
        warmup_steps: int = 0,
        device: Optional[torch.device] = None
    ):
        # Create a copy of the model for EMA
        self.ema_model = copy.deepcopy(model)
        self.ema_model.eval()
        self.ema_model.requires_grad_(False)
        
        if device is not None:
            self.ema_model.to(device)
        
        self.decay = decay
        self.warmup_steps = warmup_steps
        self.num_updates = 0
        
        # Store original decay for warmup
        self._target_decay = decay
    
    def _get_decay(self) -> float:
        """Get current decay value, with optional warmup."""
        if self.warmup_steps > 0 and self.num_updates < self.warmup_steps:
            # Linear warmup from 0.5 to target decay
            progress = self.num_updates / self.warmup_steps
            return 0.5 + (self._target_decay - 0.5) * progress
        return self.decay
    
    @torch.no_grad()
    def update(self, model: Optional[nn.Module] = None) -> None:
        """
        Update EMA weights.
        
        Call this after each training step (after optimizer.step()).
        
        Args:
            model: Model to update from (optional, uses model from __init__ if None)
        """
        if model is not None:
            source_model = model
        else:
            # This shouldn't happen in normal usage, but handle gracefully
            raise ValueError("Must provide model to update from")
        
        decay = self._get_decay()
        self.num_updates += 1
        
        # Update each parameter
        ema_params = dict(self.ema_model.named_parameters())
        model_params = dict(source_model.named_parameters())
        
        for name, param in model_params.items():
            if name in ema_params:
                ema_params[name].data.mul_(decay).add_(param.data, alpha=1 - decay)
        
        # Also update buffers (e.g., BatchNorm running stats)
        ema_buffers = dict(self.ema_model.named_buffers())
        model_buffers = dict(source_model.named_buffers())
        
        for name, buffer in model_buffers.items():
            if name in ema_buffers and buffer.dtype.is_floating_point:
                ema_buffers[name].data.mul_(decay).add_(buffer.data, alpha=1 - decay)
    
    @torch.no_grad()
    def copy_to(self, model: nn.Module) -> None:
        """
        Copy EMA weights to another model.
        
        Useful for:
        - Saving the EMA model as the final model
        - Evaluating with EMA weights on the main model
        
        Args:
            model: Target model to copy weights to
        """
        ema_params = dict(self.ema_model.named_parameters())
        model_params = dict(model.named_parameters())
        
        for name, param in model_params.items():
            if name in ema_params:
                param.data.copy_(ema_params[name].data)
        
        # Copy buffers too
        ema_buffers = dict(self.ema_model.named_buffers())
        model_buffers = dict(model.named_buffers())
        
        for name, buffer in model_buffers.items():
            if name in ema_buffers:
                buffer.data.copy_(ema_buffers[name].data)
    
    def state_dict(self) -> dict:
        """Get state dict for checkpointing."""
        return {
            "ema_model": self.ema_model.state_dict(),
            "decay": self.decay,
            "num_updates": self.num_updates,
            "warmup_steps": self.warmup_steps,
            "target_decay": self._target_decay
        }
    
    def load_state_dict(self, state_dict: dict) -> None:
        """Load state from checkpoint."""
        self.ema_model.load_state_dict(state_dict["ema_model"])
        self.decay = state_dict.get("decay", self.decay)
        self.num_updates = state_dict.get("num_updates", 0)
        self.warmup_steps = state_dict.get("warmup_steps", 0)
        self._target_decay = state_dict.get("target_decay", self.decay)
    
    def eval(self) -> nn.Module:
        """Return EMA model in eval mode."""
        self.ema_model.eval()
        return self.ema_model
    
    def train(self) -> None:
        """EMA model should always be in eval mode."""
        # Keep EMA in eval mode always - it's only for inference
        self.ema_model.eval()


class ModelEMAWithBackup:
    """
    EMA with ability to swap weights for evaluation.
    
    Useful when you want to evaluate with EMA weights during training
    without maintaining a separate model copy.
    
    Usage:
        ema = ModelEMAWithBackup(model, decay=0.999)
        
        # Training
        for batch in train_loader:
            train_step(model, batch)
            ema.update(model)
        
        # Evaluation with EMA weights
        with ema.swap_weights(model):
            val_accuracy = evaluate(model)  # Uses EMA weights
        # Model weights restored after context manager
    """
    
    def __init__(self, model: nn.Module, decay: float = 0.999):
        self.decay = decay
        self.num_updates = 0
        
        # Store EMA weights as a dict
        self.ema_state = {}
        for name, param in model.named_parameters():
            self.ema_state[name] = param.data.clone()
        for name, buffer in model.named_buffers():
            if buffer.dtype.is_floating_point:
                self.ema_state[f"buffer_{name}"] = buffer.data.clone()
    
    @torch.no_grad()
    def update(self, model: nn.Module) -> None:
        """Update EMA weights."""
        decay = self.decay
        self.num_updates += 1
        
        for name, param in model.named_parameters():
            if name in self.ema_state:
                self.ema_state[name].mul_(decay).add_(param.data, alpha=1 - decay)
        
        for name, buffer in model.named_buffers():
            key = f"buffer_{name}"
            if key in self.ema_state and buffer.dtype.is_floating_point:
                self.ema_state[key].mul_(decay).add_(buffer.data, alpha=1 - decay)
    
    class _WeightSwapContext:
        """Context manager for weight swapping."""
        def __init__(self, ema, model):
            self.ema = ema
            self.model = model
            self.backup = {}
        
        def __enter__(self):
            # Backup current weights and load EMA
            for name, param in self.model.named_parameters():
                self.backup[name] = param.data.clone()
                if name in self.ema.ema_state:
                    param.data.copy_(self.ema.ema_state[name])
            
            for name, buffer in self.model.named_buffers():
                key = f"buffer_{name}"
                if key in self.ema.ema_state:
                    self.backup[key] = buffer.data.clone()
                    buffer.data.copy_(self.ema.ema_state[key])
            
            return self.model
        
        def __exit__(self, *args):
            # Restore original weights
            for name, param in self.model.named_parameters():
                if name in self.backup:
                    param.data.copy_(self.backup[name])
            
            for name, buffer in self.model.named_buffers():
                key = f"buffer_{name}"
                if key in self.backup:
                    buffer.data.copy_(self.backup[key])
    
    def swap_weights(self, model: nn.Module):
        """Context manager to temporarily swap in EMA weights."""
        return self._WeightSwapContext(self, model)
    
    def state_dict(self) -> dict:
        """Get state dict for checkpointing."""
        return {
            "ema_state": self.ema_state,
            "decay": self.decay,
            "num_updates": self.num_updates
        }
    
    def load_state_dict(self, state_dict: dict) -> None:
        """Load state from checkpoint."""
        self.ema_state = state_dict["ema_state"]
        self.decay = state_dict.get("decay", self.decay)
        self.num_updates = state_dict.get("num_updates", 0)


def get_ema_decay(
    total_steps: int,
    strategy: str = "constant"
) -> float:
    """
    Get recommended EMA decay based on training length.
    
    Rules of thumb:
    - Longer training = higher decay (more averaging)
    - Shorter training = lower decay (more responsive)
    
    Args:
        total_steps: Total training steps
        strategy: 'constant', 'adaptive', or 'high_quality'
        
    Returns:
        Recommended decay value
    """
    if strategy == "constant":
        return 0.999
    elif strategy == "adaptive":
        # Scale decay based on training length
        if total_steps < 10000:
            return 0.99  # Short training - be responsive
        elif total_steps < 50000:
            return 0.999  # Medium training
        else:
            return 0.9999  # Long training - heavy smoothing
    elif strategy == "high_quality":
        # Very stable EMA for production models
        return 0.9999
    else:
        return 0.999
