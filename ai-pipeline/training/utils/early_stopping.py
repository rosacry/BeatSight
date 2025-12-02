"""
Early Stopping with Patience

Implements early stopping to prevent overfitting by monitoring validation metrics
and stopping training when no improvement is observed for a specified number of epochs.

Features:
- Monitor any metric (accuracy, loss, F1, etc.)
- Configurable patience (epochs to wait before stopping)
- Delta threshold for minimum improvement
- Best model tracking and restoration
- Warmup period support (don't early stop during warmup)
- Verbose logging with detailed status

Usage:
    from training.utils.early_stopping import EarlyStopping
    
    early_stopper = EarlyStopping(
        patience=20,
        min_delta=0.001,
        mode='max',  # 'max' for accuracy, 'min' for loss
        warmup_epochs=10,
        verbose=True,
    )
    
    for epoch in range(epochs):
        train_loss = train_one_epoch(...)
        val_acc = validate(...)
        
        # Check if we should stop
        if early_stopper(val_acc, epoch):
            print(f"Early stopping triggered at epoch {epoch}")
            break
        
        # Save best model
        if early_stopper.is_best:
            save_model(model)
    
    # Get final stats
    print(f"Best value: {early_stopper.best_value} at epoch {early_stopper.best_epoch}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Literal, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class EarlyStoppingState:
    """Serializable state for checkpointing."""
    best_value: float
    best_epoch: int
    counter: int
    stopped_epoch: Optional[int]
    should_stop: bool


class EarlyStopping:
    """
    Early stopping handler to prevent overfitting.
    
    Monitors a validation metric and stops training when no improvement
    is observed for a specified number of epochs (patience).
    
    Args:
        patience: Number of epochs to wait for improvement before stopping.
                  Higher patience = more training, but may overfit.
                  Recommended: 10-30 epochs (20 is a good default).
        min_delta: Minimum change to qualify as improvement.
                   Helps avoid stopping on tiny fluctuations.
                   Recommended: 0.001 for accuracy, 0.0001 for loss.
        mode: 'max' if higher metric is better (accuracy, F1)
              'min' if lower metric is better (loss)
        warmup_epochs: Number of epochs to skip early stopping checks.
                       Allows model to stabilize before monitoring.
                       Recommended: 5-10 epochs.
        restore_best_weights: If True, restore best weights when stopped.
                              Requires model to be passed via set_model().
        baseline: Optional baseline value. Training stops if best
                  value doesn't exceed baseline.
        verbose: Print status messages during training.
    
    Example:
        >>> early_stopper = EarlyStopping(patience=20, mode='max')
        >>> for epoch in range(100):
        >>>     val_acc = train_and_validate(...)
        >>>     if early_stopper(val_acc, epoch):
        >>>         print("Early stopping!")
        >>>         break
    """
    
    def __init__(
        self,
        patience: int = 20,
        min_delta: float = 0.001,
        mode: Literal['min', 'max'] = 'max',
        warmup_epochs: int = 0,
        restore_best_weights: bool = False,
        baseline: Optional[float] = None,
        verbose: bool = True,
    ):
        if patience <= 0:
            raise ValueError(f"patience must be positive, got {patience}")
        if mode not in ('min', 'max'):
            raise ValueError(f"mode must be 'min' or 'max', got {mode}")
        
        self.patience = patience
        self.min_delta = abs(min_delta)
        self.mode = mode
        self.warmup_epochs = warmup_epochs
        self.restore_best_weights = restore_best_weights
        self.baseline = baseline
        self.verbose = verbose
        
        # Set comparison function based on mode
        if mode == 'min':
            self.compare = lambda curr, best: curr < best - self.min_delta
            self.best_value = float('inf')
        else:
            self.compare = lambda curr, best: curr > best + self.min_delta
            self.best_value = float('-inf')
        
        # State
        self.counter = 0
        self.best_epoch = -1
        self.stopped_epoch: Optional[int] = None
        self.should_stop = False
        self.is_best = False
        
        # Model reference for weight restoration
        self._model = None
        self._best_state_dict = None
    
    def __call__(
        self,
        value: float,
        epoch: int,
    ) -> bool:
        """
        Check if training should stop.
        
        Args:
            value: Current validation metric value
            epoch: Current epoch number
        
        Returns:
            True if training should stop, False otherwise
        """
        self.is_best = False
        
        # Skip during warmup
        if epoch < self.warmup_epochs:
            if self.verbose:
                logger.debug(f"Early stopping warmup: epoch {epoch}/{self.warmup_epochs}")
            return False
        
        # Check baseline
        if self.baseline is not None:
            if self.mode == 'max' and value <= self.baseline:
                pass  # Continue training, haven't exceeded baseline
            elif self.mode == 'min' and value >= self.baseline:
                pass  # Continue training, haven't gone below baseline
        
        # Check for improvement
        if self.compare(value, self.best_value):
            # Improvement found
            self.best_value = value
            self.best_epoch = epoch
            self.counter = 0
            self.is_best = True
            
            # Save best weights if model is registered
            if self.restore_best_weights and self._model is not None:
                self._best_state_dict = {
                    k: v.cpu().clone() for k, v in self._model.state_dict().items()
                }
            
            if self.verbose:
                direction = "↑" if self.mode == 'max' else "↓"
                print(f"  📈 Early stopping: new best {value:.4f} {direction} (epoch {epoch})")
        else:
            # No improvement
            self.counter += 1
            
            if self.verbose:
                remaining = self.patience - self.counter
                if remaining <= 5:  # Warn when close to stopping
                    print(f"  ⏳ Early stopping: no improvement for {self.counter} epochs "
                          f"(patience: {remaining} remaining)")
            
            # Check if patience exhausted
            if self.counter >= self.patience:
                self.should_stop = True
                self.stopped_epoch = epoch
                
                if self.verbose:
                    print(f"\n  🛑 Early stopping triggered at epoch {epoch}")
                    print(f"     Best value: {self.best_value:.4f} at epoch {self.best_epoch}")
                    print(f"     Epochs without improvement: {self.counter}")
                
                # Restore best weights if requested
                if self.restore_best_weights and self._best_state_dict is not None:
                    self._model.load_state_dict(self._best_state_dict)
                    if self.verbose:
                        print(f"     ✓ Restored best weights from epoch {self.best_epoch}")
                
                return True
        
        return False
    
    def set_model(self, model) -> 'EarlyStopping':
        """
        Register model for weight restoration.
        
        Args:
            model: PyTorch model
        
        Returns:
            Self for chaining
        """
        self._model = model
        return self
    
    def reset(self):
        """Reset early stopping state (useful for multiple training runs)."""
        if self.mode == 'min':
            self.best_value = float('inf')
        else:
            self.best_value = float('-inf')
        
        self.counter = 0
        self.best_epoch = -1
        self.stopped_epoch = None
        self.should_stop = False
        self.is_best = False
        self._best_state_dict = None
    
    def state_dict(self) -> Dict[str, Any]:
        """
        Return state for checkpointing.
        
        Returns:
            Dictionary with serializable state
        """
        return {
            'best_value': self.best_value,
            'best_epoch': self.best_epoch,
            'counter': self.counter,
            'stopped_epoch': self.stopped_epoch,
            'should_stop': self.should_stop,
            'patience': self.patience,
            'min_delta': self.min_delta,
            'mode': self.mode,
            'warmup_epochs': self.warmup_epochs,
        }
    
    def load_state_dict(self, state_dict: Dict[str, Any]):
        """
        Load state from checkpoint.
        
        Args:
            state_dict: State dictionary from state_dict()
        """
        self.best_value = state_dict.get('best_value', self.best_value)
        self.best_epoch = state_dict.get('best_epoch', self.best_epoch)
        self.counter = state_dict.get('counter', self.counter)
        self.stopped_epoch = state_dict.get('stopped_epoch', self.stopped_epoch)
        self.should_stop = state_dict.get('should_stop', self.should_stop)
        
        # Optionally update configuration
        if 'patience' in state_dict:
            self.patience = state_dict['patience']
        if 'min_delta' in state_dict:
            self.min_delta = state_dict['min_delta']
    
    @property
    def improvement_ratio(self) -> float:
        """
        Return how much of patience has been used.
        
        Returns:
            Float between 0 (just improved) and 1 (about to stop)
        """
        return self.counter / self.patience
    
    def status_message(self) -> str:
        """
        Return a status message for logging.
        
        Returns:
            Human-readable status string
        """
        if self.should_stop:
            return f"STOPPED at epoch {self.stopped_epoch} (best: {self.best_value:.4f} @ epoch {self.best_epoch})"
        elif self.best_epoch < 0:
            return "WAITING (no valid epochs yet)"
        else:
            remaining = self.patience - self.counter
            return f"MONITORING (best: {self.best_value:.4f} @ epoch {self.best_epoch}, patience: {remaining}/{self.patience})"


class EarlyStoppingWithWarmup(EarlyStopping):
    """
    Early stopping with learning rate warmup awareness.
    
    This variant is aware of learning rate warmup and won't start
    monitoring until after warmup is complete. This prevents
    early stopping during the unstable warmup phase.
    """
    
    def __init__(
        self,
        patience: int = 20,
        min_delta: float = 0.001,
        mode: Literal['min', 'max'] = 'max',
        lr_warmup_epochs: int = 5,
        additional_warmup: int = 5,
        **kwargs
    ):
        """
        Args:
            patience: Epochs to wait for improvement
            min_delta: Minimum improvement threshold
            mode: 'max' or 'min'
            lr_warmup_epochs: Number of LR warmup epochs
            additional_warmup: Extra epochs after LR warmup before monitoring
            **kwargs: Additional arguments for EarlyStopping
        """
        total_warmup = lr_warmup_epochs + additional_warmup
        super().__init__(
            patience=patience,
            min_delta=min_delta,
            mode=mode,
            warmup_epochs=total_warmup,
            **kwargs
        )
        self.lr_warmup_epochs = lr_warmup_epochs
        self.additional_warmup = additional_warmup


def get_early_stopping(
    patience: int = 20,
    monitor: str = 'val_acc',
    min_delta: float = 0.001,
    warmup_epochs: int = 10,
    verbose: bool = True,
) -> EarlyStopping:
    """
    Factory function to create early stopping instance.
    
    Args:
        patience: Number of epochs to wait
        monitor: What to monitor ('val_acc', 'val_loss', 'train_loss')
        min_delta: Minimum improvement
        warmup_epochs: Epochs before monitoring starts
        verbose: Print messages
    
    Returns:
        Configured EarlyStopping instance
    """
    # Determine mode from metric name
    if 'loss' in monitor.lower():
        mode = 'min'
    else:
        mode = 'max'  # accuracy, f1, etc.
    
    return EarlyStopping(
        patience=patience,
        min_delta=min_delta,
        mode=mode,
        warmup_epochs=warmup_epochs,
        verbose=verbose,
    )
