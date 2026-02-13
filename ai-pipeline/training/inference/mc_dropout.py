"""
Monte Carlo Dropout Inference for Uncertainty Estimation

This module provides Bayesian uncertainty estimation at inference time
using Monte Carlo Dropout - running multiple forward passes with dropout
enabled to get a distribution of predictions.

Benefits:
1. Epistemic uncertainty - How uncertain is the model about its knowledge?
2. Out-of-distribution detection - Identify non-drum sounds or unusual samples
3. Confidence calibration - More reliable confidence scores
4. "I don't know" capability - System can abstain on uncertain predictions

For BeatSight, this enables:
- Telling users "I'm 95% confident this is a snare" vs "This might be a rimshot or snare"
- Flagging samples that need human review
- Premium tier feature: uncertainty-aware transcription

Reference:
- "Dropout as a Bayesian Approximation" (Gal & Ghahramani, 2016)
- "What Uncertainties Do We Need in Bayesian Deep Learning?" (Kendall & Gal, 2017)

Usage:
    from training.inference.mc_dropout import MCDropoutInference
    
    inference = MCDropoutInference(model, num_samples=10)
    
    # Get predictions with uncertainty
    result = inference.predict(mel_spectrogram)
    print(f"Class: {result.class_name}, Confidence: {result.confidence:.1%}")
    print(f"Uncertainty: {result.uncertainty:.3f}")
    
    if result.is_uncertain:
        print("⚠️ Model is uncertain - consider human review")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class MCDropoutResult:
    """Result from Monte Carlo Dropout inference."""
    
    predicted_class: int
    class_name: str
    confidence: float
    
    # Uncertainty metrics
    predictive_entropy: float  # Total uncertainty (epistemic + aleatoric)
    mutual_information: float  # Epistemic uncertainty (model uncertainty)
    prediction_variance: float  # Variance across MC samples
    
    # Derived flags
    is_uncertain: bool  # Should this be flagged for review?
    is_ood: bool  # Likely out-of-distribution?
    
    # Top-K alternatives
    top_k_classes: List[int]
    top_k_names: List[str]
    top_k_confidences: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_class": self.predicted_class,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "predictive_entropy": self.predictive_entropy,
            "mutual_information": self.mutual_information,
            "prediction_variance": self.prediction_variance,
            "is_uncertain": self.is_uncertain,
            "is_ood": self.is_ood,
            "top_k_classes": self.top_k_classes,
            "top_k_names": self.top_k_names,
            "top_k_confidences": self.top_k_confidences,
        }
    
    @property
    def uncertainty(self) -> float:
        """Simplified uncertainty score (0-1, higher = more uncertain)."""
        # Normalize predictive entropy to [0, 1] assuming max ~log(num_classes)
        return min(1.0, self.predictive_entropy / 3.0)


class MCDropoutInference:
    """
    Monte Carlo Dropout inference for uncertainty-aware predictions.
    
    Performs multiple forward passes with dropout enabled to estimate
    prediction uncertainty using Bayesian approximation.
    
    Args:
        model: Neural network with dropout layers
        num_samples: Number of MC samples (default: 10)
        uncertainty_threshold: Threshold for flagging uncertain predictions
        ood_threshold: Threshold for out-of-distribution detection
        class_names: List of class names
        temperature: Temperature scaling for calibration
    """
    
    # Default drum class names
    DRUM_CLASSES = [
        "aux_percussion", "china", "crash", "cross_stick",
        "hihat_closed", "hihat_foot_splash", "hihat_open", "hihat_pedal",
        "hihat_splash", "kick", "ride_bell", "ride_bow", "rimshot",
        "snare", "snare_center", "snare_cross_stick", "snare_rimshot",
        "splash", "tom_high", "tom_low", "tom_mid",
    ]
    
    def __init__(
        self,
        model: nn.Module,
        num_samples: int = 10,
        uncertainty_threshold: float = 0.5,
        ood_threshold: float = 0.7,
        class_names: Optional[List[str]] = None,
        temperature: float = 1.0,
        device: Optional[str] = None
    ):
        self.model = model
        self.num_samples = num_samples
        self.uncertainty_threshold = uncertainty_threshold
        self.ood_threshold = ood_threshold
        self.class_names = class_names or self.DRUM_CLASSES
        self.temperature = temperature
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        self.model.to(self.device)
        
        # Verify model has dropout
        self._has_dropout = self._check_dropout()
        if not self._has_dropout:
            logger.warning(
                "Model has no dropout layers - MC Dropout will produce "
                "deterministic predictions. Consider using TTA instead."
            )
    
    def _check_dropout(self) -> bool:
        """Check if model has dropout layers."""
        for module in self.model.modules():
            if isinstance(module, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
                return True
        return False
    
    def _enable_dropout(self):
        """Enable dropout during inference."""
        for module in self.model.modules():
            if isinstance(module, (nn.Dropout, nn.Dropout2d, nn.Dropout3d)):
                module.train()
    
    def _disable_dropout(self):
        """Disable dropout (return to eval mode)."""
        self.model.eval()
    
    @torch.no_grad()
    def _compute_mc_samples(
        self,
        x: torch.Tensor
    ) -> torch.Tensor:
        """
        Run multiple forward passes with dropout enabled.
        
        Returns:
            samples: [num_samples, B, num_classes] probabilities
        """
        self.model.eval()  # BN in eval, dropout will be enabled separately
        self._enable_dropout()
        
        samples = []
        for _ in range(self.num_samples):
            logits = self.model(x)
            
            # Apply temperature scaling
            if self.temperature != 1.0:
                logits = logits / self.temperature
            
            probs = F.softmax(logits, dim=-1)
            samples.append(probs)
        
        self._disable_dropout()
        return torch.stack(samples, dim=0)
    
    def _compute_uncertainties(
        self,
        mc_samples: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Compute uncertainty metrics from MC samples.
        
        Args:
            mc_samples: [num_samples, B, num_classes]
            
        Returns:
            predictive_entropy: Total uncertainty
            mutual_information: Epistemic uncertainty
            prediction_variance: Per-class variance
        """
        # Mean prediction across samples
        mean_probs = mc_samples.mean(dim=0)  # [B, C]
        
        # Predictive entropy: H[E[p(y|x)]]
        # Total uncertainty (epistemic + aleatoric)
        predictive_entropy = -(mean_probs * torch.log(mean_probs + 1e-10)).sum(dim=-1)
        
        # Expected entropy: E[H[p(y|x)]]
        # Average entropy of each sample
        sample_entropies = -(mc_samples * torch.log(mc_samples + 1e-10)).sum(dim=-1)
        expected_entropy = sample_entropies.mean(dim=0)  # [B]
        
        # Mutual information: I(y; θ|x) = H[E[p]] - E[H[p]]
        # This is the epistemic (model) uncertainty
        mutual_information = predictive_entropy - expected_entropy
        
        # Prediction variance per class
        prediction_variance = mc_samples.var(dim=0)  # [B, C]
        
        return predictive_entropy, mutual_information, prediction_variance
    
    @torch.no_grad()
    def predict(
        self,
        x: torch.Tensor,
        top_k: int = 5
    ) -> List[MCDropoutResult]:
        """
        Make predictions with uncertainty estimates.
        
        Args:
            x: Input mel spectrograms [B, C, H, W]
            top_k: Number of top classes to return
            
        Returns:
            List of MCDropoutResult for each sample in batch
        """
        x = x.to(self.device)
        
        # Get MC samples
        mc_samples = self._compute_mc_samples(x)  # [S, B, C]
        
        # Mean prediction
        mean_probs = mc_samples.mean(dim=0)  # [B, C]
        
        # Compute uncertainties
        pred_entropy, mutual_info, pred_var = self._compute_uncertainties(mc_samples)
        
        # Get predictions
        confidences, predictions = mean_probs.max(dim=-1)
        
        # Get top-K
        top_k_probs, top_k_classes = mean_probs.topk(top_k, dim=-1)
        
        # Build results
        results = []
        B = x.shape[0]
        
        for i in range(B):
            pred_class = predictions[i].item()
            entropy = pred_entropy[i].item()
            mi = mutual_info[i].item()
            variance = pred_var[i].mean().item()  # Mean variance across classes
            
            # Determine flags
            is_uncertain = entropy > self.uncertainty_threshold
            is_ood = mi > self.ood_threshold
            
            result = MCDropoutResult(
                predicted_class=pred_class,
                class_name=self.class_names[pred_class] if pred_class < len(self.class_names) else f"class_{pred_class}",
                confidence=confidences[i].item(),
                predictive_entropy=entropy,
                mutual_information=mi,
                prediction_variance=variance,
                is_uncertain=is_uncertain,
                is_ood=is_ood,
                top_k_classes=top_k_classes[i].tolist(),
                top_k_names=[
                    self.class_names[c] if c < len(self.class_names) else f"class_{c}"
                    for c in top_k_classes[i].tolist()
                ],
                top_k_confidences=top_k_probs[i].tolist(),
            )
            results.append(result)
        
        return results
    
    def predict_single(
        self,
        x: torch.Tensor,
        top_k: int = 5
    ) -> MCDropoutResult:
        """Predict single sample."""
        if x.dim() == 3:
            x = x.unsqueeze(0)  # Add batch dim
        return self.predict(x, top_k)[0]
    
    def get_confidence_level(self, result: MCDropoutResult) -> str:
        """
        Get human-readable confidence level.
        
        Returns:
            "high", "medium", "low", or "very_low"
        """
        if result.is_ood:
            return "very_low"
        elif result.is_uncertain:
            return "low"
        elif result.confidence > 0.9 and result.uncertainty < 0.2:
            return "high"
        else:
            return "medium"
    
    def format_result(self, result: MCDropoutResult) -> str:
        """Format result as human-readable string."""
        confidence_level = self.get_confidence_level(result)
        
        lines = [
            f"Prediction: {result.class_name}",
            f"Confidence: {result.confidence:.1%} ({confidence_level})",
            f"Uncertainty: {result.uncertainty:.2f}",
        ]
        
        if result.is_ood:
            lines.append("⚠️ WARNING: Likely out-of-distribution sample")
        elif result.is_uncertain:
            lines.append("⚠️ Note: Model is uncertain")
        
        if len(result.top_k_names) > 1:
            alternatives = ", ".join(
                f"{name} ({conf:.1%})"
                for name, conf in zip(result.top_k_names[1:3], result.top_k_confidences[1:3])
            )
            lines.append(f"Alternatives: {alternatives}")
        
        return "\n".join(lines)


class UncertaintyAwareTranscriber:
    """
    Full transcription pipeline with uncertainty-aware predictions.
    
    This wraps the MC Dropout inference with:
    - Automatic flagging of uncertain predictions
    - Batch processing
    - Confidence thresholding
    - Human review queue
    
    Perfect for production use where you want to:
    - Show users confidence levels
    - Route uncertain samples to human review
    - Provide premium "verified transcription" service
    """
    
    def __init__(
        self,
        model: nn.Module,
        num_samples: int = 10,
        high_confidence_threshold: float = 0.85,
        review_threshold: float = 0.6,
        class_names: Optional[List[str]] = None,
        device: Optional[str] = None
    ):
        self.mc_inference = MCDropoutInference(
            model,
            num_samples=num_samples,
            class_names=class_names,
            device=device
        )
        self.high_confidence_threshold = high_confidence_threshold
        self.review_threshold = review_threshold
        
        # Track samples needing review
        self.review_queue: List[Dict[str, Any]] = []
    
    def transcribe(
        self,
        spectrograms: torch.Tensor,
        sample_ids: Optional[List[str]] = None
    ) -> Tuple[List[MCDropoutResult], List[int]]:
        """
        Transcribe batch with uncertainty awareness.
        
        Args:
            spectrograms: Batch of spectrograms
            sample_ids: Optional identifiers for samples
            
        Returns:
            results: All predictions
            review_indices: Indices of samples needing review
        """
        results = self.mc_inference.predict(spectrograms)
        
        review_indices = []
        
        for i, result in enumerate(results):
            # Check if needs review
            if result.confidence < self.review_threshold or result.is_uncertain:
                review_indices.append(i)
                
                # Add to review queue
                self.review_queue.append({
                    "index": i,
                    "sample_id": sample_ids[i] if sample_ids else f"sample_{i}",
                    "result": result.to_dict(),
                    "reason": "low_confidence" if result.confidence < self.review_threshold else "uncertain",
                })
        
        return results, review_indices
    
    def get_review_queue(self) -> List[Dict[str, Any]]:
        """Get samples queued for human review."""
        return self.review_queue
    
    def clear_review_queue(self):
        """Clear the review queue."""
        self.review_queue = []


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    print("Testing MC Dropout Inference...")
    
    # Create a simple test model with dropout
    model = nn.Sequential(
        nn.Flatten(),
        nn.Linear(128 * 128, 256),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(256, 128),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(128, 21),
    )
    
    # Create inference wrapper
    inference = MCDropoutInference(
        model,
        num_samples=10,
        uncertainty_threshold=0.5,
        device="cpu"
    )
    
    # Test prediction
    x = torch.randn(4, 1, 128, 128)
    results = inference.predict(x)
    
    print(f"\nResults for {len(results)} samples:")
    for i, result in enumerate(results):
        print(f"\nSample {i}:")
        print(inference.format_result(result))
    
    # Test uncertainty-aware transcriber
    print("\n" + "=" * 50)
    print("Testing UncertaintyAwareTranscriber...")
    
    transcriber = UncertaintyAwareTranscriber(
        model,
        num_samples=10,
        high_confidence_threshold=0.85,
        review_threshold=0.6,
        device="cpu"
    )
    
    results, review_indices = transcriber.transcribe(x)
    print(f"Samples needing review: {review_indices}")
    print(f"Review queue size: {len(transcriber.get_review_queue())}")
    
    print("\n✅ MC Dropout Inference working!")
