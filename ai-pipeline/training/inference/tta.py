"""
Test-Time Augmentation (TTA) for Drum Classification

TTA applies augmentations at inference time and averages the predictions,
providing a free accuracy boost without any changes to training.

Key insight: Different augmented views of the same input should produce
similar predictions. By averaging over multiple views, we reduce variance
and get more confident predictions.

Benefits for drum classification:
- 0.5-2% accuracy improvement at zero training cost
- More robust predictions
- Better calibrated confidence scores
- Especially useful for edge cases and ambiguous samples

Augmentations used (audio-appropriate):
1. Time shift (small left/right shifts)
2. Pitch shift (subtle frequency adjustments)
3. Volume scaling
4. Horizontal flip of spectrogram (temporal reversal)
5. Spec augment style masking (test-time noise)

Usage:
    from training.inference.tta import TTAWrapper
    
    model = load_model(...)
    tta_model = TTAWrapper(model, num_augmentations=5)
    
    predictions = tta_model(mel_spectrogram)  # Averaged predictions
    predictions, uncertainty = tta_model(mel_spectrogram, return_uncertainty=True)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional, List
import random


class TTAWrapper(nn.Module):
    """
    Test-Time Augmentation wrapper for drum classification models.
    
    Applies multiple augmentations at inference and averages predictions.
    
    Args:
        model: The base classification model
        num_augmentations: Number of augmented versions to average (including original)
        augmentation_strength: How strong the augmentations are (0.0-1.0)
        use_geometric_mean: If True, use geometric mean instead of arithmetic mean
        
    Example:
        >>> model = DrumClassifierCNNv2.load(...)
        >>> tta = TTAWrapper(model, num_augmentations=5)
        >>> predictions = tta(mel_spectrogram)
    """
    
    def __init__(
        self,
        model: nn.Module,
        num_augmentations: int = 5,
        augmentation_strength: float = 0.5,
        use_geometric_mean: bool = False,
    ):
        super().__init__()
        self.model = model
        self.num_augmentations = num_augmentations
        self.augmentation_strength = augmentation_strength
        self.use_geometric_mean = use_geometric_mean
        
        # Define augmentation functions
        self.augmentations = [
            self._identity,  # Always include original
            self._time_shift,
            self._frequency_shift,
            self._volume_scale,
            self._temporal_flip,
            self._add_noise,
            self._freq_mask,
            self._time_mask,
        ]
    
    def _identity(self, x: torch.Tensor) -> torch.Tensor:
        """No augmentation - return original."""
        return x
    
    def _time_shift(self, x: torch.Tensor) -> torch.Tensor:
        """Shift spectrogram along time axis."""
        shift = int(x.shape[-1] * 0.1 * self.augmentation_strength * (random.random() * 2 - 1))
        return torch.roll(x, shifts=shift, dims=-1)
    
    def _frequency_shift(self, x: torch.Tensor) -> torch.Tensor:
        """Shift spectrogram along frequency axis."""
        shift = int(x.shape[-2] * 0.05 * self.augmentation_strength * (random.random() * 2 - 1))
        return torch.roll(x, shifts=shift, dims=-2)
    
    def _volume_scale(self, x: torch.Tensor) -> torch.Tensor:
        """Scale volume (amplitude) of spectrogram."""
        scale = 1.0 + self.augmentation_strength * 0.2 * (random.random() * 2 - 1)
        return x * scale
    
    def _temporal_flip(self, x: torch.Tensor) -> torch.Tensor:
        """Flip spectrogram along time axis."""
        return torch.flip(x, dims=[-1])
    
    def _add_noise(self, x: torch.Tensor) -> torch.Tensor:
        """Add small amount of Gaussian noise."""
        noise_level = 0.01 * self.augmentation_strength
        noise = torch.randn_like(x) * noise_level
        return x + noise
    
    def _freq_mask(self, x: torch.Tensor) -> torch.Tensor:
        """Apply frequency masking (SpecAugment style)."""
        num_freq = x.shape[-2]
        mask_width = int(num_freq * 0.1 * self.augmentation_strength)
        if mask_width > 0:
            start = random.randint(0, num_freq - mask_width)
            x = x.clone()
            x[..., start:start + mask_width, :] = 0
        return x
    
    def _time_mask(self, x: torch.Tensor) -> torch.Tensor:
        """Apply time masking (SpecAugment style)."""
        num_time = x.shape[-1]
        mask_width = int(num_time * 0.1 * self.augmentation_strength)
        if mask_width > 0:
            start = random.randint(0, num_time - mask_width)
            x = x.clone()
            x[..., start:start + mask_width] = 0
        return x
    
    @torch.no_grad()
    def forward(
        self,
        x: torch.Tensor,
        return_uncertainty: bool = False
    ) -> torch.Tensor | Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with test-time augmentation.
        
        Args:
            x: Input mel spectrogram [B, C, H, W]
            return_uncertainty: If True, also return prediction uncertainty
            
        Returns:
            predictions: Averaged predictions [B, num_classes]
            uncertainty: (optional) Uncertainty scores [B, num_classes]
        """
        self.model.eval()
        
        all_predictions = []
        
        for i in range(self.num_augmentations):
            # Select augmentation (always include identity first)
            if i == 0:
                augmented = x
            else:
                aug_fn = random.choice(self.augmentations[1:])  # Skip identity
                augmented = aug_fn(x)
            
            # Get predictions
            logits = self.model(augmented)
            probs = F.softmax(logits, dim=-1)
            all_predictions.append(probs)
        
        # Stack predictions: [num_aug, B, num_classes]
        stacked = torch.stack(all_predictions, dim=0)
        
        # Average predictions
        if self.use_geometric_mean:
            # Geometric mean (multiply then root)
            log_probs = torch.log(stacked + 1e-10)
            avg_log_probs = log_probs.mean(dim=0)
            avg_probs = torch.exp(avg_log_probs)
            avg_probs = avg_probs / avg_probs.sum(dim=-1, keepdim=True)
        else:
            # Arithmetic mean
            avg_probs = stacked.mean(dim=0)
        
        if return_uncertainty:
            # Uncertainty = variance of predictions across augmentations
            uncertainty = stacked.var(dim=0)
            return avg_probs, uncertainty
        
        return avg_probs
    
    def predict_with_ensemble(
        self,
        x: torch.Tensor,
        ensemble_models: Optional[List[nn.Module]] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Combine TTA with ensemble of multiple models.
        
        This provides maximum robustness by averaging over both
        augmentations AND multiple models.
        
        Args:
            x: Input mel spectrogram
            ensemble_models: List of additional models to ensemble with
            
        Returns:
            predictions: Ensemble + TTA averaged predictions
            uncertainty: Combined uncertainty estimate
        """
        if ensemble_models is None:
            ensemble_models = []
        
        all_models = [self.model] + ensemble_models
        all_predictions = []
        
        for model in all_models:
            model.eval()
            for i in range(self.num_augmentations):
                if i == 0:
                    augmented = x
                else:
                    aug_fn = random.choice(self.augmentations[1:])
                    augmented = aug_fn(x)
                
                with torch.no_grad():
                    logits = model(augmented)
                    probs = F.softmax(logits, dim=-1)
                    all_predictions.append(probs)
        
        stacked = torch.stack(all_predictions, dim=0)
        avg_probs = stacked.mean(dim=0)
        uncertainty = stacked.var(dim=0)
        
        return avg_probs, uncertainty


class MCDropoutTTA(nn.Module):
    """
    Monte Carlo Dropout for uncertainty estimation.
    
    Instead of augmenting inputs, this uses dropout at inference time
    to get multiple stochastic predictions. This provides a Bayesian
    approximation of uncertainty.
    
    Especially useful for identifying out-of-distribution samples
    (e.g., non-drum sounds, unusual recording conditions).
    
    Args:
        model: Model with dropout layers
        num_samples: Number of stochastic forward passes
    """
    
    def __init__(self, model: nn.Module, num_samples: int = 10):
        super().__init__()
        self.model = model
        self.num_samples = num_samples
    
    def _enable_dropout(self):
        """Enable dropout layers during inference."""
        for module in self.model.modules():
            if isinstance(module, nn.Dropout):
                module.train()
    
    @torch.no_grad()
    def forward(
        self,
        x: torch.Tensor,
        return_uncertainty: bool = True
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass with MC Dropout.
        
        Returns:
            predictions: Mean predictions
            uncertainty: Predictive uncertainty (epistemic + aleatoric)
        """
        self._enable_dropout()
        
        all_predictions = []
        for _ in range(self.num_samples):
            logits = self.model(x)
            probs = F.softmax(logits, dim=-1)
            all_predictions.append(probs)
        
        stacked = torch.stack(all_predictions, dim=0)
        mean_probs = stacked.mean(dim=0)
        
        if return_uncertainty:
            # Predictive entropy as uncertainty
            uncertainty = -(mean_probs * torch.log(mean_probs + 1e-10)).sum(dim=-1)
            return mean_probs, uncertainty
        
        return mean_probs


class CombinedTTA(nn.Module):
    """
    Combines standard TTA with MC Dropout for maximum uncertainty estimation.
    
    This gives you both:
    - Augmentation-based uncertainty (data uncertainty)
    - Dropout-based uncertainty (model uncertainty)
    """
    
    def __init__(
        self,
        model: nn.Module,
        num_augmentations: int = 5,
        num_dropout_samples: int = 5,
        augmentation_strength: float = 0.5
    ):
        super().__init__()
        self.tta = TTAWrapper(model, num_augmentations, augmentation_strength)
        self.mc_dropout = MCDropoutTTA(model, num_dropout_samples)
        self.num_augmentations = num_augmentations
        self.num_dropout_samples = num_dropout_samples
    
    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass with combined TTA and MC Dropout.
        
        Returns:
            predictions: Combined averaged predictions
            data_uncertainty: From TTA (augmentation variance)
            model_uncertainty: From MC Dropout (dropout variance)
        """
        # Get TTA predictions and uncertainty
        tta_probs, data_uncertainty = self.tta(x, return_uncertainty=True)
        
        # Get MC Dropout predictions and uncertainty
        mc_probs, model_uncertainty = self.mc_dropout(x, return_uncertainty=True)
        
        # Combine predictions (weighted average)
        combined_probs = (tta_probs + mc_probs) / 2
        
        return combined_probs, data_uncertainty, model_uncertainty
