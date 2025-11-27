"""
Temperature Scaling for Confidence Calibration

Temperature scaling is a simple post-hoc calibration technique that learns
a single temperature parameter to scale model logits, making predicted
probabilities better match actual accuracy.

Paper: "On Calibration of Modern Neural Networks" (Guo et al., ICML 2017)
       https://arxiv.org/abs/1706.04599

Problem:
- Modern neural networks are often overconfident
- A 95% predicted probability might only be correct 80% of the time
- This is problematic for downstream decision-making

Solution:
- Learn a temperature T > 1 to "soften" predictions
- calibrated_prob = softmax(logits / T)
- Higher T = less confident (more conservative)

Benefits for drum classification:
- BeatSight can make better decisions about when to show suggestions
- Users get more meaningful confidence scores
- Ensemble with TTA becomes more effective
- Better handling of ambiguous drum hits

Expected improvement: Not accuracy, but MUCH better confidence scores

Usage:
    from training.calibration.temperature_scaling import TemperatureScaler
    
    # After training, calibrate on validation set
    scaler = TemperatureScaler()
    scaler.fit(model, val_loader, device)
    
    # Save calibrated model
    scaler.save("calibration_params.json")
    
    # At inference time
    scaler = TemperatureScaler.load("calibration_params.json")
    calibrated_probs = scaler.calibrate(logits)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import numpy as np
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from tqdm import tqdm


class TemperatureScaler(nn.Module):
    """
    Temperature scaling for model calibration.
    
    Learns a single temperature parameter to calibrate model confidence.
    """
    
    def __init__(self, temperature: float = 1.5):
        super().__init__()
        self.temperature = nn.Parameter(torch.ones(1) * temperature)
        self._fitted = False
    
    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """Apply temperature scaling to logits."""
        return logits / self.temperature
    
    def calibrate(self, logits: torch.Tensor) -> torch.Tensor:
        """Get calibrated probabilities."""
        scaled_logits = self.forward(logits)
        return F.softmax(scaled_logits, dim=-1)
    
    @torch.no_grad()
    def fit(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        device: torch.device,
        lr: float = 0.01,
        max_iters: int = 100,
        verbose: bool = True,
    ) -> float:
        """
        Fit temperature parameter on validation data.
        
        Args:
            model: Trained model
            val_loader: Validation DataLoader
            device: Compute device
            lr: Learning rate for optimization
            max_iters: Maximum optimization iterations
            verbose: Print progress
            
        Returns:
            Final NLL loss after calibration
        """
        model.eval()
        self.to(device)
        
        # Collect all logits and labels from validation set
        all_logits = []
        all_labels = []
        
        for inputs, labels in tqdm(val_loader, desc="Collecting logits", disable=not verbose):
            inputs = inputs.to(device)
            logits = model(inputs)
            all_logits.append(logits.cpu())
            all_labels.append(labels)
        
        all_logits = torch.cat(all_logits).to(device)
        all_labels = torch.cat(all_labels).to(device)
        
        # Optimize temperature using LBFGS
        self.temperature.requires_grad_(True)
        optimizer = torch.optim.LBFGS([self.temperature], lr=lr, max_iter=max_iters)
        
        nll_criterion = nn.CrossEntropyLoss()
        
        def closure():
            optimizer.zero_grad()
            scaled_logits = all_logits / self.temperature
            loss = nll_criterion(scaled_logits, all_labels)
            loss.backward()
            return loss
        
        optimizer.step(closure)
        
        self.temperature.requires_grad_(False)
        self._fitted = True
        
        # Compute final loss
        with torch.no_grad():
            final_logits = all_logits / self.temperature
            final_loss = nll_criterion(final_logits, all_labels).item()
        
        if verbose:
            print(f"Calibration complete. Temperature: {self.temperature.item():.4f}")
            print(f"Calibrated NLL: {final_loss:.4f}")
        
        return final_loss
    
    def save(self, path: str) -> None:
        """Save calibration parameters to JSON."""
        data = {
            "temperature": self.temperature.item(),
            "fitted": self._fitted,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "TemperatureScaler":
        """Load calibration parameters from JSON."""
        with open(path, 'r') as f:
            data = json.load(f)
        scaler = cls(temperature=data["temperature"])
        scaler._fitted = data.get("fitted", True)
        return scaler


class VectorScaler(nn.Module):
    """
    Vector scaling: Learns per-class temperature and bias.
    
    More flexible than temperature scaling but requires more data.
    
    calibrated_logits = W * logits + b
    where W is diagonal (per-class scaling)
    """
    
    def __init__(self, num_classes: int):
        super().__init__()
        self.num_classes = num_classes
        self.weights = nn.Parameter(torch.ones(num_classes))
        self.bias = nn.Parameter(torch.zeros(num_classes))
        self._fitted = False
    
    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        """Apply vector scaling."""
        return logits * self.weights + self.bias
    
    def calibrate(self, logits: torch.Tensor) -> torch.Tensor:
        """Get calibrated probabilities."""
        scaled_logits = self.forward(logits)
        return F.softmax(scaled_logits, dim=-1)
    
    @torch.no_grad()
    def fit(
        self,
        model: nn.Module,
        val_loader: DataLoader,
        device: torch.device,
        lr: float = 0.01,
        max_iters: int = 200,
        verbose: bool = True,
    ) -> float:
        """Fit vector scaling parameters on validation data."""
        model.eval()
        self.to(device)
        
        # Collect all logits and labels
        all_logits = []
        all_labels = []
        
        for inputs, labels in tqdm(val_loader, desc="Collecting logits", disable=not verbose):
            inputs = inputs.to(device)
            logits = model(inputs)
            all_logits.append(logits.cpu())
            all_labels.append(labels)
        
        all_logits = torch.cat(all_logits).to(device)
        all_labels = torch.cat(all_labels).to(device)
        
        # Optimize using LBFGS
        self.weights.requires_grad_(True)
        self.bias.requires_grad_(True)
        optimizer = torch.optim.LBFGS([self.weights, self.bias], lr=lr, max_iter=max_iters)
        
        nll_criterion = nn.CrossEntropyLoss()
        
        def closure():
            optimizer.zero_grad()
            scaled_logits = all_logits * self.weights + self.bias
            loss = nll_criterion(scaled_logits, all_labels)
            loss.backward()
            return loss
        
        optimizer.step(closure)
        
        self.weights.requires_grad_(False)
        self.bias.requires_grad_(False)
        self._fitted = True
        
        # Compute final loss
        with torch.no_grad():
            final_logits = all_logits * self.weights + self.bias
            final_loss = nll_criterion(final_logits, all_labels).item()
        
        if verbose:
            print(f"Vector scaling complete.")
            print(f"Weight range: [{self.weights.min():.3f}, {self.weights.max():.3f}]")
            print(f"Calibrated NLL: {final_loss:.4f}")
        
        return final_loss
    
    def save(self, path: str) -> None:
        """Save calibration parameters."""
        data = {
            "num_classes": self.num_classes,
            "weights": self.weights.tolist(),
            "bias": self.bias.tolist(),
            "fitted": self._fitted,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "VectorScaler":
        """Load calibration parameters."""
        with open(path, 'r') as f:
            data = json.load(f)
        scaler = cls(num_classes=data["num_classes"])
        scaler.weights.data = torch.tensor(data["weights"])
        scaler.bias.data = torch.tensor(data["bias"])
        scaler._fitted = data.get("fitted", True)
        return scaler


def compute_calibration_metrics(
    probs: torch.Tensor,
    labels: torch.Tensor,
    n_bins: int = 15,
) -> Dict[str, float]:
    """
    Compute calibration metrics: ECE, MCE, Brier score.
    
    Args:
        probs: Predicted probabilities [N, C]
        labels: Ground truth labels [N]
        n_bins: Number of bins for ECE/MCE
        
    Returns:
        Dict with ECE, MCE, Brier score, and per-bin data
    """
    confidences, predictions = probs.max(dim=-1)
    accuracies = predictions.eq(labels)
    
    # Compute ECE and MCE
    bin_boundaries = torch.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]
    
    ece = 0.0
    mce = 0.0
    bin_data = []
    
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = in_bin.float().mean()
        
        if prop_in_bin > 0:
            accuracy_in_bin = accuracies[in_bin].float().mean()
            avg_confidence_in_bin = confidences[in_bin].mean()
            
            gap = abs(avg_confidence_in_bin - accuracy_in_bin)
            ece += prop_in_bin * gap
            mce = max(mce, gap.item())
            
            bin_data.append({
                "bin_lower": bin_lower.item(),
                "bin_upper": bin_upper.item(),
                "accuracy": accuracy_in_bin.item(),
                "confidence": avg_confidence_in_bin.item(),
                "count": in_bin.sum().item(),
            })
    
    # Brier score
    one_hot = F.one_hot(labels, num_classes=probs.shape[1]).float()
    brier = ((probs - one_hot) ** 2).sum(dim=-1).mean().item()
    
    return {
        "ece": ece.item(),
        "mce": mce,
        "brier": brier,
        "bins": bin_data,
    }


def calibrate_model(
    model: nn.Module,
    val_loader: DataLoader,
    device: torch.device,
    method: str = "temperature",
    save_path: Optional[str] = None,
    num_classes: Optional[int] = None,
) -> Tuple[nn.Module, Dict[str, float]]:
    """
    Full calibration pipeline: fit scaler and compute metrics.
    
    Args:
        model: Trained model
        val_loader: Validation DataLoader
        device: Compute device
        method: 'temperature' or 'vector'
        save_path: Optional path to save calibration parameters
        num_classes: Required for vector scaling
        
    Returns:
        (calibration_module, metrics_dict)
    """
    model.eval()
    
    # Collect uncalibrated predictions
    all_logits = []
    all_labels = []
    
    print("Collecting predictions for calibration...")
    for inputs, labels in tqdm(val_loader):
        inputs = inputs.to(device)
        with torch.no_grad():
            logits = model(inputs)
        all_logits.append(logits.cpu())
        all_labels.append(labels)
    
    all_logits = torch.cat(all_logits)
    all_labels = torch.cat(all_labels)
    
    # Compute uncalibrated metrics
    uncal_probs = F.softmax(all_logits, dim=-1)
    uncal_metrics = compute_calibration_metrics(uncal_probs, all_labels)
    print(f"\nBefore calibration:")
    print(f"  ECE: {uncal_metrics['ece']:.4f}")
    print(f"  MCE: {uncal_metrics['mce']:.4f}")
    print(f"  Brier: {uncal_metrics['brier']:.4f}")
    
    # Fit calibration
    if method == "temperature":
        scaler = TemperatureScaler()
    elif method == "vector":
        if num_classes is None:
            num_classes = all_logits.shape[1]
        scaler = VectorScaler(num_classes)
    else:
        raise ValueError(f"Unknown method: {method}")
    
    print(f"\nFitting {method} scaling...")
    scaler.fit(model, val_loader, device)
    
    # Compute calibrated metrics
    cal_logits = scaler(all_logits.to(device)).cpu()
    cal_probs = F.softmax(cal_logits, dim=-1)
    cal_metrics = compute_calibration_metrics(cal_probs, all_labels)
    print(f"\nAfter calibration:")
    print(f"  ECE: {cal_metrics['ece']:.4f} (was {uncal_metrics['ece']:.4f})")
    print(f"  MCE: {cal_metrics['mce']:.4f} (was {uncal_metrics['mce']:.4f})")
    print(f"  Brier: {cal_metrics['brier']:.4f} (was {uncal_metrics['brier']:.4f})")
    
    # Save if requested
    if save_path:
        scaler.save(save_path)
        print(f"\nCalibration saved to: {save_path}")
    
    return scaler, {
        "before": uncal_metrics,
        "after": cal_metrics,
        "improvement": {
            "ece_reduction": uncal_metrics['ece'] - cal_metrics['ece'],
            "mce_reduction": uncal_metrics['mce'] - cal_metrics['mce'],
            "brier_reduction": uncal_metrics['brier'] - cal_metrics['brier'],
        }
    }
