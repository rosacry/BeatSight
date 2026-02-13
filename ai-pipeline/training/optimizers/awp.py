"""
Adversarial Weight Perturbation (AWP)

AWP is an advanced regularization technique that improves generalization by
adversarially perturbing model weights during training. Unlike SAM which seeks
flat minima, AWP explicitly makes the model robust to weight perturbations.

Paper: "Adversarial Weight Perturbation Helps Robust Generalization" (NeurIPS 2020)
       https://arxiv.org/abs/2004.05884

Key insight: By training the model to be robust against worst-case weight
perturbations, we get a model that generalizes better and is more stable.

How it works:
1. Compute gradients at current weights
2. Find adversarial weight perturbation that maximizes loss
3. Add perturbation to weights
4. Compute gradients at perturbed weights
5. Restore original weights and apply update

Difference from SAM:
- SAM perturbs in the direction of the gradient (worst-case in input space)
- AWP perturbs to find worst-case weights (worst-case in weight space)
- AWP uses a more sophisticated perturbation strategy with per-layer normalization
- AWP typically provides stronger regularization

Benefits for drum classification:
- Superior robustness to distribution shift (new songs, genres, recording quality)
- Works synergistically with SAM (can combine both!)
- Especially effective when combined with data augmentation
- Better calibrated predictions (important for confidence thresholds)

Usage:
    from training.optimizers.awp import AWP
    
    awp = AWP(model, optimizer, adv_lr=0.01, adv_eps=0.01)
    
    # Training loop
    for inputs, targets in dataloader:
        # Standard forward-backward
        predictions = model(inputs)
        loss = criterion(predictions, targets)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        
        # AWP step (optional, typically every N iterations or after warmup)
        awp_loss = awp.attack_step(inputs, targets, criterion)
        awp.restore_step()
"""

from __future__ import annotations

import torch
import torch.nn as nn
from typing import Dict, Optional, Any, Callable, List
from contextlib import contextmanager


class AWP:
    """
    Adversarial Weight Perturbation for improved generalization.
    
    This class manages weight perturbations to make training more robust.
    It's designed to be used alongside any optimizer, including SAM.
    
    Args:
        model: The neural network model
        optimizer: The optimizer (can be SAM, AdamW, etc.)
        adv_lr: Learning rate for adversarial perturbation (default: 0.01)
        adv_eps: Maximum perturbation magnitude (default: 0.01)
        adv_step: Number of adversarial steps (default: 1)
        start_epoch: Epoch to start AWP (default: 0, warmup recommended)
        param_names_to_perturb: Parameter name patterns to perturb 
                                (default: all except bn/bias/norm)
        device: Device for computation (auto-detected if None)
    
    Example:
        >>> awp = AWP(model, optimizer, adv_lr=0.01, adv_eps=0.01, start_epoch=5)
        >>> 
        >>> for epoch in range(epochs):
        >>>     for batch in dataloader:
        >>>         # Standard training step
        >>>         loss = model(batch).loss
        >>>         loss.backward()
        >>>         optimizer.step()
        >>>         optimizer.zero_grad()
        >>>         
        >>>         # AWP step (after warmup)
        >>>         if epoch >= 5:
        >>>             awp_loss = awp.attack_step(batch.inputs, batch.targets, criterion)
        >>>             awp.restore_step()
    """
    
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        adv_lr: float = 0.01,
        adv_eps: float = 0.01,
        adv_step: int = 1,
        start_epoch: int = 0,
        param_names_to_perturb: Optional[List[str]] = None,
        device: Optional[torch.device] = None,
    ):
        self.model = model
        self.optimizer = optimizer
        self.adv_lr = adv_lr
        self.adv_eps = adv_eps
        self.adv_step = adv_step
        self.start_epoch = start_epoch
        self.param_names_to_perturb = param_names_to_perturb
        
        # Auto-detect device
        if device is None:
            for p in model.parameters():
                device = p.device
                break
        self.device = device
        
        # Storage for original weights
        self.backup: Dict[str, torch.Tensor] = {}
        self.backup_eps: Dict[str, torch.Tensor] = {}
        
        # Initialize perturbation targets
        self._init_perturbation_params()
    
    def _init_perturbation_params(self):
        """Identify which parameters to perturb."""
        self.perturb_params = {}
        
        for name, param in self.model.named_parameters():
            if param.requires_grad:
                # Skip batch norm, layer norm, and bias by default
                if self.param_names_to_perturb is not None:
                    # Use provided patterns
                    should_perturb = any(
                        pattern in name for pattern in self.param_names_to_perturb
                    )
                else:
                    # Default: skip normalization and bias
                    skip_patterns = ['bn', 'bias', 'norm', 'gamma', 'beta']
                    should_perturb = not any(
                        pattern in name.lower() for pattern in skip_patterns
                    )
                
                if should_perturb:
                    self.perturb_params[name] = param
    
    def _save_weights(self):
        """Save current weights before perturbation."""
        for name, param in self.perturb_params.items():
            self.backup[name] = param.data.clone()
    
    def _restore_weights(self):
        """Restore original weights after perturbation."""
        for name, param in self.perturb_params.items():
            if name in self.backup:
                param.data = self.backup[name]
        self.backup = {}
        self.backup_eps = {}
    
    def _compute_perturbation(self) -> Dict[str, torch.Tensor]:
        """
        Compute adversarial perturbation for each parameter.
        
        Uses per-layer normalized perturbation with gradient direction.
        """
        perturbations = {}
        
        for name, param in self.perturb_params.items():
            if param.grad is None:
                continue
            
            # Compute per-layer perturbation scale
            # Using L2 normalization for stability
            grad = param.grad.data
            grad_norm = torch.norm(grad)
            
            if grad_norm > 1e-8:
                # Normalized gradient direction
                grad_dir = grad / grad_norm
                
                # Scale by parameter magnitude for adaptive perturbation
                param_norm = torch.norm(param.data)
                
                # Perturbation = adv_lr * (grad_dir * param_norm)
                # Clipped to adv_eps * param_norm
                perturbation = self.adv_lr * grad_dir * param_norm
                
                # Clip perturbation magnitude
                perturbation = torch.clamp(
                    perturbation,
                    -self.adv_eps * param_norm,
                    self.adv_eps * param_norm
                )
                
                perturbations[name] = perturbation
            else:
                perturbations[name] = torch.zeros_like(param.data)
        
        return perturbations
    
    def _apply_perturbation(self, perturbations: Dict[str, torch.Tensor]):
        """Apply perturbations to weights."""
        for name, param in self.perturb_params.items():
            if name in perturbations:
                self.backup_eps[name] = perturbations[name]
                param.data.add_(perturbations[name])
    
    @torch.no_grad()
    def perturb_weights(self):
        """
        Compute and apply adversarial weight perturbation.
        
        Call this after loss.backward() to find worst-case weights.
        """
        self._save_weights()
        perturbations = self._compute_perturbation()
        self._apply_perturbation(perturbations)
    
    @torch.no_grad()
    def restore_weights(self):
        """
        Restore original weights after adversarial step.
        
        Call this after computing gradients at perturbed weights.
        """
        self._restore_weights()
    
    def attack_step(
        self,
        inputs: torch.Tensor,
        targets: torch.Tensor,
        criterion: Callable,
        amp_enabled: bool = False,
        scaler: Optional[Any] = None,
    ) -> torch.Tensor:
        """
        Perform a complete AWP attack step.
        
        This:
        1. Saves current weights
        2. Perturbs weights adversarially
        3. Computes loss at perturbed weights
        4. Backpropagates through perturbed weights
        5. (Does NOT restore - call restore_step separately)
        
        Args:
            inputs: Input tensor
            targets: Target tensor
            criterion: Loss function
            amp_enabled: Whether AMP is enabled
            scaler: GradScaler for AMP
        
        Returns:
            Loss value at perturbed weights
        """
        # Save and perturb
        self.perturb_weights()
        
        # Forward pass at perturbed weights
        if amp_enabled:
            with torch.amp.autocast('cuda'):
                outputs = self.model(inputs)
                loss = criterion(outputs, targets)
        else:
            outputs = self.model(inputs)
            loss = criterion(outputs, targets)
        
        # Backward pass
        self.optimizer.zero_grad()
        if scaler is not None:
            scaler.scale(loss).backward()
        else:
            loss.backward()
        
        return loss
    
    def restore_step(self):
        """
        Complete the AWP step by restoring original weights.
        
        Call this after attack_step() and optimizer.step().
        """
        self.restore_weights()
    
    @contextmanager
    def adversarial_context(self):
        """
        Context manager for AWP perturbation.
        
        Usage:
            with awp.adversarial_context():
                loss = model(inputs)
                loss.backward()
        """
        self.perturb_weights()
        try:
            yield
        finally:
            self.restore_weights()
    
    def should_attack(self, epoch: int, iteration: Optional[int] = None, 
                      attack_freq: int = 1) -> bool:
        """
        Determine if AWP should be applied this iteration.
        
        Args:
            epoch: Current epoch
            iteration: Current iteration within epoch (optional)
            attack_freq: Apply AWP every N iterations (default: 1 = every iteration)
        
        Returns:
            True if AWP should be applied
        """
        if epoch < self.start_epoch:
            return False
        
        if iteration is not None and attack_freq > 1:
            return iteration % attack_freq == 0
        
        return True
    
    def state_dict(self) -> Dict[str, Any]:
        """Return state for checkpointing."""
        return {
            'adv_lr': self.adv_lr,
            'adv_eps': self.adv_eps,
            'adv_step': self.adv_step,
            'start_epoch': self.start_epoch,
        }
    
    def load_state_dict(self, state_dict: Dict[str, Any]):
        """Load state from checkpoint."""
        self.adv_lr = state_dict.get('adv_lr', self.adv_lr)
        self.adv_eps = state_dict.get('adv_eps', self.adv_eps)
        self.adv_step = state_dict.get('adv_step', self.adv_step)
        self.start_epoch = state_dict.get('start_epoch', self.start_epoch)


class AWPWithSAM:
    """
    Combined AWP + SAM training for maximum generalization.
    
    This combines both adversarial weight perturbation (AWP) and 
    sharpness-aware minimization (SAM) for the ultimate regularization.
    
    The training loop looks like:
    1. SAM first step (find sharpness direction)
    2. SAM second step (update with sharpness-aware gradient)
    3. AWP attack (find adversarial weights)
    4. AWP gradient (backprop at adversarial weights)  
    5. AWP restore (restore original weights)
    
    This provides both:
    - Flat minima (from SAM) - better generalization
    - Adversarial robustness (from AWP) - better stability
    
    Usage:
        from training.optimizers.awp import AWPWithSAM
        from training.optimizers.sam import SAM
        
        sam = SAM(model.parameters(), torch.optim.AdamW, lr=1e-3, rho=0.05)
        awp_sam = AWPWithSAM(model, sam, adv_lr=0.01, adv_eps=0.01)
        
        for inputs, targets in dataloader:
            loss = awp_sam.training_step(inputs, targets, criterion)
    """
    
    def __init__(
        self,
        model: nn.Module,
        sam_optimizer: Any,  # SAM or ESAM
        adv_lr: float = 0.01,
        adv_eps: float = 0.01,
        awp_start_epoch: int = 5,
        awp_freq: int = 1,  # Apply AWP every N iterations
    ):
        self.model = model
        self.sam = sam_optimizer
        self.awp = AWP(model, sam_optimizer, adv_lr, adv_eps, start_epoch=awp_start_epoch)
        self.awp_freq = awp_freq
        self.iteration = 0
    
    def training_step(
        self,
        inputs: torch.Tensor,
        targets: torch.Tensor,
        criterion: Callable,
        epoch: int = 0,
        amp_enabled: bool = False,
        scaler: Optional[Any] = None,
    ) -> torch.Tensor:
        """
        Complete training step with SAM + AWP.
        
        Args:
            inputs: Input tensor
            targets: Target tensor  
            criterion: Loss function
            epoch: Current epoch
            amp_enabled: Whether AMP is enabled
            scaler: GradScaler for AMP
        
        Returns:
            Final loss value
        """
        # === SAM First Pass ===
        if amp_enabled:
            with torch.amp.autocast('cuda'):
                outputs = self.model(inputs)
                loss = criterion(outputs, targets)
            if scaler:
                scaler.scale(loss).backward()
                scaler.unscale_(self.sam)
        else:
            outputs = self.model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
        
        self.sam.first_step(zero_grad=True)
        
        # === SAM Second Pass ===
        if amp_enabled:
            with torch.amp.autocast('cuda'):
                outputs = self.model(inputs)
                loss2 = criterion(outputs, targets)
            if scaler:
                scaler.scale(loss2).backward()
                scaler.step(self.sam)
                scaler.update()
        else:
            outputs = self.model(inputs)
            loss2 = criterion(outputs, targets)
            loss2.backward()
            self.sam.second_step(zero_grad=True)
        
        # === AWP Attack (after warmup, every N iterations) ===
        self.iteration += 1
        if self.awp.should_attack(epoch, self.iteration, self.awp_freq):
            awp_loss = self.awp.attack_step(inputs, targets, criterion, amp_enabled, scaler)
            
            # Apply gradients from adversarial weights
            if scaler:
                scaler.step(self.sam.base_optimizer)
                scaler.update()
            else:
                self.sam.base_optimizer.step()
            
            self.awp.restore_step()
        
        return loss


def get_awp(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    adv_lr: float = 0.01,
    adv_eps: float = 0.01,
    start_epoch: int = 0,
) -> AWP:
    """
    Factory function to create AWP instance.
    
    Args:
        model: Neural network model
        optimizer: Optimizer to use
        adv_lr: Adversarial learning rate
        adv_eps: Maximum perturbation
        start_epoch: Epoch to start AWP
    
    Returns:
        Configured AWP instance
    """
    return AWP(
        model=model,
        optimizer=optimizer,
        adv_lr=adv_lr,
        adv_eps=adv_eps,
        start_epoch=start_epoch,
    )
