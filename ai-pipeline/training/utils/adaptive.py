"""
Adaptive Hyperparameter Scheduling for Training

This module implements adaptive/scheduled hyperparameters that automatically
adjust during training to minimize the risk of suboptimal fixed values.

Key Techniques:
1. Progressive Augmentation - Start weak, increase strength as training progresses
2. Adaptive Mixup - Reduce mixup when validation loss stops improving
3. Focal Loss Gamma Scheduling - Start high, reduce as model improves
4. Automatic Hyperparameter Search via Population Based Training (simplified)

Why Adaptive is Better:
- Early training: Model needs to learn basic patterns (light augmentation)
- Mid training: Model can handle harder examples (stronger augmentation)
- Late training: Fine-tuning on harder examples (maintain or reduce slightly)

Usage:
    from training.utils.adaptive import AdaptiveAugmentation, ProgressiveSchedule
    
    scheduler = ProgressiveSchedule(
        start_value=0.1,
        end_value=0.4,
        warmup_epochs=10,
        total_epochs=100
    )
    
    for epoch in range(100):
        current_mixup_alpha = scheduler.get_value(epoch)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProgressiveSchedule:
    """
    Linearly or cosine-interpolate a hyperparameter from start to end value.
    
    This is useful for augmentation strength, label smoothing, etc.
    
    Args:
        start_value: Initial value (typically lower/weaker)
        end_value: Final value (typically higher/stronger)
        warmup_epochs: Epochs to reach end_value (or ramp up period)
        total_epochs: Total training epochs
        schedule: 'linear', 'cosine', or 'step'
        hold_epochs: Epochs to hold at end_value before optional decay
    """
    start_value: float
    end_value: float
    warmup_epochs: int = 10
    total_epochs: int = 100
    schedule: str = "linear"
    hold_epochs: int = 0
    
    def get_value(self, epoch: int) -> float:
        """Get the scheduled value for a given epoch."""
        if epoch < 0:
            return self.start_value
        
        if self.schedule == "linear":
            if epoch >= self.warmup_epochs:
                return self.end_value
            progress = epoch / max(self.warmup_epochs, 1)
            return self.start_value + (self.end_value - self.start_value) * progress
        
        elif self.schedule == "cosine":
            if epoch >= self.warmup_epochs:
                return self.end_value
            progress = epoch / max(self.warmup_epochs, 1)
            # Cosine interpolation (smoother than linear)
            cosine_progress = (1 - math.cos(math.pi * progress)) / 2
            return self.start_value + (self.end_value - self.start_value) * cosine_progress
        
        elif self.schedule == "step":
            # Step function: jump to end_value after warmup
            return self.end_value if epoch >= self.warmup_epochs else self.start_value
        
        else:
            raise ValueError(f"Unknown schedule: {self.schedule}")


@dataclass
class AdaptiveValue:
    """
    A hyperparameter that adapts based on training metrics.
    
    This implements a simplified form of population-based training:
    - If validation loss improves, keep current value
    - If validation loss stagnates, try increasing/decreasing the value
    
    Args:
        initial_value: Starting value
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        patience: Epochs without improvement before adapting
        factor: Multiplicative factor for adjustment
    """
    initial_value: float
    min_value: float = 0.0
    max_value: float = 1.0
    patience: int = 5
    factor: float = 1.2
    
    _current_value: float = field(init=False)
    _best_loss: float = field(init=False, default=float('inf'))
    _epochs_without_improvement: int = field(init=False, default=0)
    _direction: int = field(init=False, default=1)  # 1 = increase, -1 = decrease
    
    def __post_init__(self):
        self._current_value = self.initial_value
    
    @property
    def value(self) -> float:
        return self._current_value
    
    def step(self, val_loss: float) -> float:
        """
        Update the value based on validation loss.
        
        Args:
            val_loss: Current epoch's validation loss
            
        Returns:
            New value after potential adaptation
        """
        if val_loss < self._best_loss:
            self._best_loss = val_loss
            self._epochs_without_improvement = 0
        else:
            self._epochs_without_improvement += 1
        
        if self._epochs_without_improvement >= self.patience:
            # Try adjusting the value
            if self._direction == 1:
                new_value = self._current_value * self.factor
            else:
                new_value = self._current_value / self.factor
            
            # Clamp to range
            new_value = max(self.min_value, min(self.max_value, new_value))
            
            # If we hit a boundary, reverse direction
            if new_value == self._current_value:
                self._direction *= -1
            else:
                self._current_value = new_value
            
            self._epochs_without_improvement = 0
        
        return self._current_value


class ProgressiveAugmentation:
    """
    Manages progressive augmentation schedules for multiple hyperparameters.
    
    Implements the "start weak, end strong" principle that minimizes
    the risk of suboptimal fixed hyperparameters.
    
    Default schedules are research-validated:
    - Mixup: 0.1 → 0.4 over first 20% of training
    - CutMix: 0.3 → 1.0 over first 30% of training
    - SpecAugment: Start at 50% strength, ramp to 100%
    - Label Smoothing: Fixed (already a form of progressive regularization)
    
    Usage:
        aug = ProgressiveAugmentation(total_epochs=100)
        
        for epoch in range(100):
            mixup_alpha = aug.get_mixup_alpha(epoch)
            cutmix_alpha = aug.get_cutmix_alpha(epoch)
            specaug_prob = aug.get_specaugment_prob(epoch)
    """
    
    def __init__(
        self,
        total_epochs: int,
        mixup_start: float = 0.1,
        mixup_end: float = 0.4,
        mixup_warmup_fraction: float = 0.2,
        cutmix_start: float = 0.3,
        cutmix_end: float = 1.0,
        cutmix_warmup_fraction: float = 0.3,
        specaug_start_prob: float = 0.3,
        specaug_end_prob: float = 0.8,
        specaug_warmup_fraction: float = 0.25,
    ):
        self.total_epochs = total_epochs
        
        self.mixup_schedule = ProgressiveSchedule(
            start_value=mixup_start,
            end_value=mixup_end,
            warmup_epochs=int(total_epochs * mixup_warmup_fraction),
            total_epochs=total_epochs,
            schedule="cosine"
        )
        
        self.cutmix_schedule = ProgressiveSchedule(
            start_value=cutmix_start,
            end_value=cutmix_end,
            warmup_epochs=int(total_epochs * cutmix_warmup_fraction),
            total_epochs=total_epochs,
            schedule="cosine"
        )
        
        self.specaug_schedule = ProgressiveSchedule(
            start_value=specaug_start_prob,
            end_value=specaug_end_prob,
            warmup_epochs=int(total_epochs * specaug_warmup_fraction),
            total_epochs=total_epochs,
            schedule="linear"
        )
    
    def get_mixup_alpha(self, epoch: int) -> float:
        return self.mixup_schedule.get_value(epoch)
    
    def get_cutmix_alpha(self, epoch: int) -> float:
        return self.cutmix_schedule.get_value(epoch)
    
    def get_specaugment_prob(self, epoch: int) -> float:
        return self.specaug_schedule.get_value(epoch)
    
    def get_all(self, epoch: int) -> Dict[str, float]:
        """Get all scheduled values for an epoch."""
        return {
            "mixup_alpha": self.get_mixup_alpha(epoch),
            "cutmix_alpha": self.get_cutmix_alpha(epoch),
            "specaugment_prob": self.get_specaugment_prob(epoch),
        }
    
    def log_schedule(self, epochs_to_show: Optional[List[int]] = None) -> str:
        """Print a summary of the augmentation schedule."""
        if epochs_to_show is None:
            epochs_to_show = [0, self.total_epochs // 4, self.total_epochs // 2, 
                            3 * self.total_epochs // 4, self.total_epochs - 1]
        
        lines = ["Progressive Augmentation Schedule:"]
        lines.append("-" * 60)
        lines.append(f"{'Epoch':>8} | {'Mixup a':>10} | {'CutMix a':>10} | {'SpecAug P':>10}")
        lines.append("-" * 60)
        
        for epoch in epochs_to_show:
            if epoch < self.total_epochs:
                values = self.get_all(epoch)
                lines.append(
                    f"{epoch:>8} | {values['mixup_alpha']:>10.3f} | "
                    f"{values['cutmix_alpha']:>10.3f} | {values['specaugment_prob']:>10.3f}"
                )
        
        lines.append("-" * 60)
        return "\n".join(lines)


class FocalGammaScheduler:
    """
    Schedule focal loss gamma to adapt during training.
    
    Strategy:
    - Early training (high gamma): Focus heavily on hard examples
    - Late training (lower gamma): More balanced focus as model improves
    
    This prevents the model from ignoring easy examples entirely,
    which can hurt calibration.
    """
    
    def __init__(
        self,
        start_gamma: float = 3.0,
        end_gamma: float = 1.5,
        warmup_epochs: int = 20,
        total_epochs: int = 100,
    ):
        self.schedule = ProgressiveSchedule(
            start_value=start_gamma,
            end_value=end_gamma,
            warmup_epochs=warmup_epochs,
            total_epochs=total_epochs,
            schedule="cosine"
        )
    
    def get_gamma(self, epoch: int) -> float:
        return self.schedule.get_value(epoch)


class LabelSmoothingScheduler:
    """
    Optionally schedule label smoothing.
    
    One strategy: Start with higher smoothing, reduce as model becomes confident.
    Another: Keep constant (label smoothing is already a form of regularization).
    
    Default: Constant (research shows this works well)
    """
    
    def __init__(
        self,
        value: float = 0.1,
        schedule: str = "constant"  # "constant", "decay", or "warmup"
    ):
        self.value = value
        self.schedule_type = schedule
    
    def get_value(self, epoch: int, total_epochs: int) -> float:
        if self.schedule_type == "constant":
            return self.value
        elif self.schedule_type == "decay":
            # Decay from value to value/2 over training
            progress = epoch / max(total_epochs - 1, 1)
            return self.value * (1 - 0.5 * progress)
        elif self.schedule_type == "warmup":
            # Warmup from 0 to value over first 10% of training
            warmup_epochs = total_epochs // 10
            if epoch < warmup_epochs:
                return self.value * (epoch / warmup_epochs)
            return self.value
        else:
            return self.value


def get_recommended_schedules(total_epochs: int) -> Dict[str, any]:
    """
    Get recommended adaptive schedules for cutting-edge training.
    
    These schedules are designed to minimize hyperparameter sensitivity
    by starting conservative and adapting during training.
    
    Args:
        total_epochs: Total training epochs
        
    Returns:
        Dictionary of schedulers for each hyperparameter
    """
    return {
        "augmentation": ProgressiveAugmentation(
            total_epochs=total_epochs,
            # Conservative start, strong finish
            mixup_start=0.1,
            mixup_end=0.4,
            cutmix_start=0.3,
            cutmix_end=1.0,
            specaug_start_prob=0.3,
            specaug_end_prob=0.8,
        ),
        "focal_gamma": FocalGammaScheduler(
            start_gamma=2.5,  # Start focused
            end_gamma=1.5,    # End more balanced
            warmup_epochs=total_epochs // 3,
            total_epochs=total_epochs,
        ),
        "label_smoothing": LabelSmoothingScheduler(
            value=0.1,
            schedule="constant"
        ),
    }


# Convenience function for typical usage
def create_adaptive_config(total_epochs: int) -> Dict[str, float]:
    """
    Create initial config with adaptive-friendly defaults.
    
    These are conservative starting points that work well with
    progressive scheduling.
    """
    return {
        "mixup_alpha": 0.2,       # Will ramp up
        "cutmix_alpha": 0.5,      # Will ramp up
        "mixup_prob": 0.5,        # Fixed (applies to whether to use aug at all)
        "specaugment_prob": 0.5,  # Will ramp up
        "focal_gamma": 2.0,       # May be scheduled
        "label_smoothing": 0.1,   # Fixed
        "ema_decay": 0.999,       # Fixed (already adaptive by nature)
    }
