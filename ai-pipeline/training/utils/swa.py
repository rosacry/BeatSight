"""
Stochastic Weight Averaging (SWA) Utilities

SWA is a simple averaging scheme that leads to better generalization
than conventional training. It's now built into PyTorch.

Paper: "Averaging Weights Leads to Wider Optima and Better Generalization" (2018)
       https://arxiv.org/abs/1803.05407

How it works:
1. Train normally for most of training
2. In the last N epochs, average the weights at the end of each epoch
3. At the end, update batch norm statistics with the averaged weights

Benefits:
- 0.5-1.5% accuracy improvement
- More stable final weights
- Better calibration
- Especially effective with cyclic learning rates

Key difference from EMA:
- EMA: Continuous exponential averaging throughout training
- SWA: Average discrete snapshots in the final training phase
- They can be combined for maximum benefit!

Usage:
    from training.utils.swa import SWAManager, configure_swa
    
    # Method 1: Using PyTorch's built-in SWALR
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    swa_model = AveragedModel(model)
    swa_scheduler = SWALR(optimizer, swa_lr=0.01)
    
    for epoch in range(100):
        if epoch >= 75:  # Start SWA at epoch 75
            update_bn(train_loader, swa_model)
            swa_model.update_parameters(model)
            swa_scheduler.step()
    
    # Method 2: Using our wrapper
    swa_manager = SWAManager(model, swa_start=0.75)
    for epoch in range(100):
        swa_manager.update(model, epoch, total_epochs=100)
    final_model = swa_manager.get_averaged_model()
"""

import torch
import torch.nn as nn
from torch.optim.swa_utils import AveragedModel, SWALR, update_bn
from typing import Optional, List
import copy


class SWAManager:
    """
    Manages Stochastic Weight Averaging during training.
    
    This provides a simple interface for SWA that integrates with
    any training loop.
    
    Args:
        model: The model to average
        swa_start: When to start SWA (as fraction of training, e.g., 0.75 = last 25%)
        swa_lr: Learning rate to use during SWA phase (if using SWALR)
        anneal_epochs: Number of epochs to anneal LR (if using SWALR)
        
    Example:
        >>> swa = SWAManager(model, swa_start=0.75)
        >>> for epoch in range(100):
        >>>     train_one_epoch(...)
        >>>     swa.update(model, epoch, 100)
        >>> final_model = swa.get_averaged_model()
    """
    
    def __init__(
        self,
        model: nn.Module,
        swa_start: float = 0.75,
        swa_lr: Optional[float] = None,
        anneal_epochs: int = 10,
        device: Optional[torch.device] = None
    ):
        self.swa_start = swa_start
        self.swa_lr = swa_lr
        self.anneal_epochs = anneal_epochs
        self.device = device or next(model.parameters()).device
        
        # Initialize averaged model
        self.swa_model = AveragedModel(model, device=self.device)
        self.n_averaged = 0
        self.started = False
    
    def should_start_swa(self, current_epoch: int, total_epochs: int) -> bool:
        """Check if we should start SWA at this epoch."""
        return current_epoch >= int(total_epochs * self.swa_start)
    
    def update(self, model: nn.Module, current_epoch: int, total_epochs: int):
        """
        Update SWA model if we're in the SWA phase.
        
        Args:
            model: Current model to potentially add to average
            current_epoch: Current training epoch (0-indexed)
            total_epochs: Total number of training epochs
        """
        if self.should_start_swa(current_epoch, total_epochs):
            self.swa_model.update_parameters(model)
            self.n_averaged += 1
            self.started = True
    
    def get_averaged_model(self) -> nn.Module:
        """Get the averaged model (returns copy, original preserved)."""
        return self.swa_model.module
    
    def update_batch_norm(self, dataloader: torch.utils.data.DataLoader):
        """
        Update batch normalization statistics for the averaged model.
        
        IMPORTANT: Must be called after training is complete!
        SWA averaging can corrupt batch norm running statistics,
        so we need to recalculate them.
        
        Args:
            dataloader: Training dataloader to use for BN update
        """
        update_bn(dataloader, self.swa_model, device=self.device)
    
    def save(self, path: str):
        """Save the SWA model."""
        torch.save({
            'swa_model_state_dict': self.swa_model.module.state_dict(),
            'n_averaged': self.n_averaged,
        }, path)
    
    @classmethod
    def load(cls, path: str, model: nn.Module):
        """Load a saved SWA model."""
        checkpoint = torch.load(path, weights_only=True)
        model.load_state_dict(checkpoint['swa_model_state_dict'])
        return model


class CyclicSWA:
    """
    SWA with cyclic learning rate schedule.
    
    Uses a cyclic LR that restarts at high values, then captures
    snapshots at the low points for averaging.
    
    This is more effective than constant LR SWA because:
    1. High LR escapes sharp minima
    2. Low LR settles into good solutions
    3. Averaging over multiple cycles captures diverse minima
    
    Args:
        model: Model to average
        optimizer: Optimizer to use
        lr_high: High learning rate
        lr_low: Low learning rate  
        cycle_length: Epochs per cycle
    """
    
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        lr_high: float = 0.01,
        lr_low: float = 0.0001,
        cycle_length: int = 5,
        device: Optional[torch.device] = None
    ):
        self.model = model
        self.optimizer = optimizer
        self.lr_high = lr_high
        self.lr_low = lr_low
        self.cycle_length = cycle_length
        self.device = device or next(model.parameters()).device
        
        self.swa_model = AveragedModel(model, device=self.device)
        self.snapshots: List[dict] = []
        self.current_epoch = 0
    
    def get_lr(self, epoch: int) -> float:
        """Get cyclic learning rate for given epoch."""
        cycle_pos = epoch % self.cycle_length
        # Cosine annealing within cycle
        t = cycle_pos / self.cycle_length
        return self.lr_low + 0.5 * (self.lr_high - self.lr_low) * (1 + torch.cos(torch.tensor(t * 3.14159)))
    
    def step(self, epoch: int):
        """
        Step the cyclic SWA scheduler.
        
        Updates LR and captures snapshot at cycle end.
        """
        # Update learning rate
        lr = self.get_lr(epoch)
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        # Capture snapshot at end of cycle (low LR point)
        if (epoch + 1) % self.cycle_length == 0:
            self.swa_model.update_parameters(self.model)
            self.snapshots.append(copy.deepcopy(self.model.state_dict()))
        
        self.current_epoch = epoch
    
    def get_averaged_model(self) -> nn.Module:
        """Get the SWA averaged model."""
        return self.swa_model.module


def configure_swa(
    optimizer: torch.optim.Optimizer,
    swa_lr: float = 0.001,
    anneal_strategy: str = "cos"
) -> SWALR:
    """
    Configure PyTorch's SWALR scheduler.
    
    Args:
        optimizer: Base optimizer
        swa_lr: Target learning rate for SWA phase
        anneal_strategy: "cos" for cosine annealing, "linear" for linear
        
    Returns:
        SWALR scheduler
    """
    return SWALR(
        optimizer,
        swa_lr=swa_lr,
        anneal_strategy=anneal_strategy,
        anneal_epochs=10
    )


class SWAPlusEMA:
    """
    Combines SWA with EMA for maximum averaging benefit.
    
    - EMA provides continuous smoothing throughout training
    - SWA captures discrete snapshots in the final phase
    - Combining both gives the best of both worlds
    
    Args:
        model: Model to average
        ema_decay: EMA decay rate (0.999 recommended)
        swa_start: When to start SWA (fraction of training)
    """
    
    def __init__(
        self,
        model: nn.Module,
        ema_decay: float = 0.999,
        swa_start: float = 0.75,
        device: Optional[torch.device] = None
    ):
        self.device = device or next(model.parameters()).device
        
        # EMA model (runs throughout training)
        self.ema_model = copy.deepcopy(model)
        self.ema_model.eval()
        self.ema_decay = ema_decay
        
        # SWA model (runs in final phase)
        self.swa_manager = SWAManager(model, swa_start=swa_start, device=self.device)
        
        self.total_epochs = None
    
    @torch.no_grad()
    def update_ema(self, model: nn.Module):
        """Update EMA model."""
        for ema_param, model_param in zip(self.ema_model.parameters(), model.parameters()):
            ema_param.data.mul_(self.ema_decay).add_(model_param.data, alpha=1 - self.ema_decay)
    
    def update(self, model: nn.Module, epoch: int, total_epochs: int):
        """Update both EMA and SWA."""
        self.total_epochs = total_epochs
        
        # Always update EMA
        self.update_ema(model)
        
        # Update SWA in final phase
        self.swa_manager.update(model, epoch, total_epochs)
    
    def get_best_model(self) -> nn.Module:
        """
        Get the best averaged model.
        
        Returns SWA model if SWA was used, otherwise EMA model.
        """
        if self.swa_manager.started:
            return self.swa_manager.get_averaged_model()
        return self.ema_model
    
    def get_ensemble_models(self) -> List[nn.Module]:
        """Get both EMA and SWA models for ensemble."""
        models = [self.ema_model]
        if self.swa_manager.started:
            models.append(self.swa_manager.get_averaged_model())
        return models
