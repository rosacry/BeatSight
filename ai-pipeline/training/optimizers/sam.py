"""
Sharpness-Aware Minimization (SAM) Optimizer

SAM is a revolutionary optimizer that explicitly seeks flat minima in the loss
landscape, leading to significantly better generalization.

Paper: "Sharpness-Aware Minimization for Efficiently Improving Generalization" (2020)
       https://arxiv.org/abs/2010.01412

Key insight: Models at "sharp" minima generalize poorly, while models at "flat"
minima generalize well. SAM explicitly optimizes for flatness.

How it works:
1. Compute gradient at current weights
2. Take a step in gradient direction to find worst-case perturbation
3. Compute gradient at perturbed weights
4. Use this "sharpness-aware" gradient to update original weights

Benefits for drum classification:
- Better generalization to new songs/genres
- More robust to recording quality variations
- Consistently outperforms SGD/Adam on many benchmarks (0.5-2% improvement)
- Especially effective with augmentation (multiplicative gains)

Usage:
    from training.optimizers.sam import SAM
    
    base_optimizer = torch.optim.SGD
    optimizer = SAM(model.parameters(), base_optimizer, lr=0.1, momentum=0.9, rho=0.05)
    
    # Training loop
    for inputs, targets in dataloader:
        # First forward-backward pass
        predictions = model(inputs)
        loss = criterion(predictions, targets)
        loss.backward()
        optimizer.first_step(zero_grad=True)
        
        # Second forward-backward pass
        criterion(model(inputs), targets).backward()
        optimizer.second_step(zero_grad=True)
"""

import torch
from typing import Type, Any, Dict, Callable


class SAM(torch.optim.Optimizer):
    """
    Sharpness-Aware Minimization optimizer wrapper.
    
    This wraps any base optimizer (SGD, Adam, AdamW) and adds sharpness-aware
    gradient computation.
    
    Args:
        params: Model parameters to optimize
        base_optimizer: Base optimizer class (e.g., torch.optim.SGD)
        rho: Neighborhood size for perturbation (default: 0.05)
              - Higher rho = more regularization, potentially slower convergence
              - Lower rho = closer to base optimizer behavior
              - 0.05 is the recommended default from the paper
        adaptive: If True, use adaptive SAM which normalizes perturbations per-parameter
        **kwargs: Arguments passed to base optimizer (lr, momentum, weight_decay, etc.)
    
    Example:
        >>> optimizer = SAM(model.parameters(), torch.optim.SGD, lr=0.1, momentum=0.9, rho=0.05)
        >>> for batch in dataloader:
        >>>     loss = model(batch).loss
        >>>     loss.backward()
        >>>     optimizer.first_step(zero_grad=True)
        >>>     model(batch).loss.backward()
        >>>     optimizer.second_step(zero_grad=True)
    """
    
    def __init__(
        self,
        params,
        base_optimizer: Type[torch.optim.Optimizer],
        rho: float = 0.05,
        adaptive: bool = False,
        **kwargs
    ):
        assert rho >= 0.0, f"Invalid rho value: {rho}"
        
        defaults = dict(rho=rho, adaptive=adaptive, **kwargs)
        super(SAM, self).__init__(params, defaults)
        
        self.base_optimizer = base_optimizer(self.param_groups, **kwargs)
        self.param_groups = self.base_optimizer.param_groups
        self.defaults.update(self.base_optimizer.defaults)
        
    @torch.no_grad()
    def first_step(self, zero_grad: bool = False):
        """
        Compute the perturbation (epsilon) and apply it to weights.
        
        This moves weights to the "worst-case" direction within the neighborhood.
        """
        grad_norm = self._grad_norm()
        
        for group in self.param_groups:
            scale = group["rho"] / (grad_norm + 1e-12)
            
            for p in group["params"]:
                if p.grad is None:
                    continue
                    
                # Store original weights
                self.state[p]["old_p"] = p.data.clone()
                
                # Compute perturbation
                if group["adaptive"]:
                    # Adaptive SAM: normalize by parameter magnitude
                    e_w = (torch.pow(p, 2)) * p.grad * scale
                else:
                    e_w = p.grad * scale
                
                # Apply perturbation (move to worst case)
                p.add_(e_w)
        
        if zero_grad:
            self.zero_grad()
    
    @torch.no_grad()
    def second_step(self, zero_grad: bool = False):
        """
        Apply the actual update using gradients computed at perturbed weights.
        
        This uses the sharpness-aware gradient to update the original weights.
        """
        # Restore original weights
        for group in self.param_groups:
            for p in group["params"]:
                if p.grad is None:
                    continue
                p.data = self.state[p]["old_p"]
        
        # Apply base optimizer step with sharpness-aware gradients
        self.base_optimizer.step()
        
        if zero_grad:
            self.zero_grad()
    
    @torch.no_grad()
    def step(self, closure: Callable = None):
        """
        Perform a single optimization step.
        
        Note: For proper SAM usage, use first_step() and second_step() separately.
        This method is provided for compatibility but uses a closure pattern.
        """
        assert closure is not None, "SAM requires a closure for proper operation"
        
        # First forward-backward
        closure()
        self.first_step(zero_grad=True)
        
        # Second forward-backward
        closure()
        self.second_step(zero_grad=True)
    
    def _grad_norm(self) -> torch.Tensor:
        """Compute the gradient norm across all parameters."""
        shared_device = self.param_groups[0]["params"][0].device
        
        norm = torch.norm(
            torch.stack([
                ((torch.abs(p) if group["adaptive"] else 1.0) * p.grad).norm(p=2).to(shared_device)
                for group in self.param_groups
                for p in group["params"]
                if p.grad is not None
            ]),
            p=2
        )
        
        return norm
    
    def load_state_dict(self, state_dict: Dict[str, Any]):
        """Load optimizer state."""
        super().load_state_dict(state_dict)
        self.base_optimizer.param_groups = self.param_groups


class ESAM(SAM):
    """
    Efficient Sharpness-Aware Minimization.
    
    ESAM reduces the computational overhead of SAM by:
    1. Using stochastic weight perturbation (only perturb a subset of weights)
    2. Using gradient filtering (ignore small gradients)
    
    This makes SAM more practical for large models while retaining most benefits.
    
    Paper: "Efficient Sharpness-aware Minimization for Improved Training of
           Neural Networks" (2022)
    """
    
    def __init__(
        self,
        params,
        base_optimizer: Type[torch.optim.Optimizer],
        rho: float = 0.05,
        beta: float = 0.9,  # Gradient filtering threshold (top beta% of gradients)
        gamma: float = 0.9,  # Weight perturbation probability
        adaptive: bool = False,
        **kwargs
    ):
        self.beta = beta
        self.gamma = gamma
        super().__init__(params, base_optimizer, rho, adaptive, **kwargs)
    
    @torch.no_grad()
    def first_step(self, zero_grad: bool = False):
        """ESAM first step with gradient filtering and stochastic perturbation."""
        grad_norm = self._grad_norm()
        
        for group in self.param_groups:
            scale = group["rho"] / (grad_norm + 1e-12)
            
            for p in group["params"]:
                if p.grad is None:
                    continue
                
                self.state[p]["old_p"] = p.data.clone()
                
                # Gradient filtering: only use top beta% of gradients
                grad_flat = p.grad.abs().view(-1)
                threshold = torch.quantile(grad_flat, 1 - self.beta)
                mask = p.grad.abs() >= threshold
                
                # Stochastic perturbation
                if torch.rand(1).item() < self.gamma:
                    if group["adaptive"]:
                        e_w = (torch.pow(p, 2)) * p.grad * scale * mask.float()
                    else:
                        e_w = p.grad * scale * mask.float()
                    p.add_(e_w)
        
        if zero_grad:
            self.zero_grad()


def enable_running_stats(model):
    """
    Enable running statistics for BatchNorm layers during SAM perturbation.
    
    During SAM's first forward pass, we want BN to use batch statistics.
    """
    def _enable(module):
        if isinstance(module, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            module.backup_momentum = module.momentum
            module.momentum = 0
    
    model.apply(_enable)


def disable_running_stats(model):
    """
    Disable running statistics for BatchNorm layers during SAM perturbation.
    
    This prevents BN running stats from being polluted by perturbed weights.
    """
    def _disable(module):
        if isinstance(module, (torch.nn.BatchNorm1d, torch.nn.BatchNorm2d, torch.nn.BatchNorm3d)):
            module.momentum = module.backup_momentum
    
    model.apply(_disable)
