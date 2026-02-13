"""
Ensemble Inference for Drum Classification

This module provides ensemble methods for combining predictions from multiple
trained models to improve accuracy and calibration.

Key benefits:
- 2-3% accuracy boost over single model (typical for 3-5 model ensemble)
- Better calibrated confidence scores
- Reduced variance in predictions
- More robust to individual model biases

Ensemble strategies:
1. Simple averaging (default): Average logits or probabilities
2. Weighted averaging: Weight models by validation performance
3. Majority voting: For discrete predictions

Usage:
    from transcription.ensemble import EnsembleClassifier

    # Load multiple trained models
    ensemble = EnsembleClassifier(
        model_paths=[
            "runs/seed_1337/best_drum_classifier.pth",
            "runs/seed_42/best_drum_classifier.pth",
            "runs/seed_2024/best_drum_classifier.pth",
        ],
        weights=[0.4, 0.35, 0.25],  # Optional: weight by val accuracy
    )

    # Single prediction
    component, confidence = ensemble.classify_onset(audio, sr, onset_time)

    # Batch inference
    results = ensemble.classify_batch(audio, sr, onset_times)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Import model classes - support both v1 and v2
try:
    from transcription.ml_drum_classifier import DrumClassifierCNN
except ImportError:
    DrumClassifierCNN = None

try:
    from transcription.ml_drum_classifier_v2 import DrumClassifierCNNv2
except ImportError:
    DrumClassifierCNNv2 = None


class EnsembleClassifier:
    """
    Ensemble classifier combining multiple drum classification models.

    Supports:
    - Multiple model architectures (v1 CNN, v2 with SE)
    - Weighted and unweighted averaging
    - Logit-level or probability-level fusion
    - GPU and CPU inference

    Args:
        model_paths: List of paths to trained model checkpoints
        weights: Optional weights for each model (should sum to 1.0)
        model_classes: Optional list of model class names ("v1" or "v2")
        device: Device for inference ("cuda", "cpu", or None for auto)
        fusion_method: "logit" (average logits) or "prob" (average probabilities)
        temperature: Temperature for probability calibration (1.0 = no change)
    """

    # Post-processed output class list (21 classes after articulation expansion)
    # The trained MODEL outputs 12 base classes (from components.json), then
    # post-processors expand to these 21 output classes for detailed notation.
    # For model loading, num_classes should match the checkpoint (typically 12).
    DRUM_COMPONENTS = [
        "aux_percussion",
        "china",
        "crash",
        "cross_stick",
        "hihat_closed",
        "hihat_foot_splash",
        "hihat_open",
        "hihat_pedal",
        "hihat_splash",
        "kick",
        "ride_bell",
        "ride_bow",
        "rimshot",       # Detected by post-processing, not model output
        "snare",
        "snare_center",
        "snare_cross_stick",
        "snare_rimshot",  # Detected by post-processing (RimshotDetector)
        "splash",
        "tom_high",
        "tom_low",
        "tom_mid",
    ]

    def __init__(
        self,
        model_paths: List[Union[str, Path]],
        weights: Optional[List[float]] = None,
        model_classes: Optional[List[str]] = None,
        device: Optional[str] = None,
        fusion_method: str = "logit",
        temperature: float = 1.0,
        num_classes: int = 12,  # Base model outputs 12 classes (rimshot merged into snare)
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.torch_device = torch.device(self.device)
        self.fusion_method = fusion_method
        self.temperature = temperature
        self.num_classes = num_classes

        # Validate inputs
        if len(model_paths) == 0:
            raise ValueError("At least one model path is required")

        if weights is not None:
            if len(weights) != len(model_paths):
                raise ValueError("Number of weights must match number of models")
            weight_sum = sum(weights)
            if abs(weight_sum - 1.0) > 0.01:
                print(f"Warning: weights sum to {weight_sum}, normalizing to 1.0")
                weights = [w / weight_sum for w in weights]
        else:
            # Equal weights
            weights = [1.0 / len(model_paths)] * len(model_paths)

        self.weights = weights
        self.model_paths = [Path(p) for p in model_paths]

        # Default model classes to v1
        if model_classes is None:
            model_classes = ["v1"] * len(model_paths)
        self.model_classes = model_classes

        # Load models
        self.models: List[nn.Module] = []
        self._load_models()

    def _load_models(self):
        """Load all models from checkpoints."""
        for path, model_class in zip(self.model_paths, self.model_classes):
            if not path.exists():
                raise FileNotFoundError(f"Model not found: {path}")

            # Create model instance
            if model_class == "v2":
                if DrumClassifierCNNv2 is None:
                    raise ImportError("DrumClassifierCNNv2 not available")
                model = DrumClassifierCNNv2(num_classes=self.num_classes)
            else:
                if DrumClassifierCNN is None:
                    raise ImportError("DrumClassifierCNN not available")
                model = DrumClassifierCNN(num_classes=self.num_classes)

            # Load weights
            state_dict = torch.load(path, map_location=self.torch_device)

            # Handle torch.compile prefix
            if any(k.startswith("_orig_mod.") for k in state_dict.keys()):
                state_dict = {
                    k.replace("_orig_mod.", ""): v for k, v in state_dict.items()
                }

            model.load_state_dict(state_dict)
            model.to(self.torch_device)
            model.eval()

            self.models.append(model)
            print(f"Loaded {model_class} model from {path}")

        print(f"Ensemble initialized with {len(self.models)} models")

    @torch.no_grad()
    def predict(self, features: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get ensemble predictions for a batch of features.

        Args:
            features: Input tensor of shape (batch, 1, height, width)

        Returns:
            Tuple of (predicted_classes, confidences) both of shape (batch,)
        """
        features = features.to(self.torch_device)

        # Collect predictions from all models
        all_logits = []
        for model in self.models:
            logits = model(features)
            all_logits.append(logits)

        # Stack: (num_models, batch, num_classes)
        stacked = torch.stack(all_logits, dim=0)

        # Apply weights: (num_models, 1, 1)
        weights_tensor = torch.tensor(
            self.weights, device=self.torch_device, dtype=stacked.dtype
        ).view(-1, 1, 1)

        # Fusion
        if self.fusion_method == "logit":
            # Weighted average of logits
            fused_logits = (stacked * weights_tensor).sum(dim=0)
            fused_logits = fused_logits / self.temperature
            probs = F.softmax(fused_logits, dim=-1)
        else:
            # Weighted average of probabilities
            all_probs = F.softmax(stacked / self.temperature, dim=-1)
            probs = (all_probs * weights_tensor).sum(dim=0)

        confidences, predictions = probs.max(dim=-1)
        return predictions, confidences

    @torch.no_grad()
    def predict_with_uncertainty(
        self, features: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Get predictions with uncertainty estimates.

        Uncertainty is estimated as the disagreement between ensemble members.

        Args:
            features: Input tensor of shape (batch, 1, height, width)

        Returns:
            Dictionary with:
                - predictions: Predicted class indices
                - confidences: Mean confidence scores
                - uncertainty: Standard deviation of predictions (higher = more disagreement)
                - individual_preds: Predictions from each model
        """
        features = features.to(self.torch_device)

        # Collect predictions from all models
        all_probs = []
        all_preds = []

        for model in self.models:
            logits = model(features)
            probs = F.softmax(logits / self.temperature, dim=-1)
            all_probs.append(probs)
            all_preds.append(probs.argmax(dim=-1))

        # Stack: (num_models, batch, num_classes)
        stacked_probs = torch.stack(all_probs, dim=0)
        stacked_preds = torch.stack(all_preds, dim=0)

        # Mean and std of probabilities
        mean_probs = stacked_probs.mean(dim=0)
        std_probs = stacked_probs.std(dim=0)

        # Ensemble prediction
        confidences, predictions = mean_probs.max(dim=-1)

        # Uncertainty: mean std across classes, higher = more disagreement
        uncertainty = std_probs.mean(dim=-1)

        # Agreement: fraction of models agreeing with ensemble prediction
        agreement = (stacked_preds == predictions.unsqueeze(0)).float().mean(dim=0)

        return {
            "predictions": predictions,
            "confidences": confidences,
            "uncertainty": uncertainty,
            "agreement": agreement,
            "individual_preds": stacked_preds,
        }

    def extract_features(
        self, audio: np.ndarray, sr: int, onset_time: float, window_ms: float = 100.0
    ) -> torch.Tensor:
        """
        Extract mel-spectrogram features around an onset.

        Args:
            audio: Audio data as numpy array
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds

        Returns:
            Mel-spectrogram tensor of shape (1, 1, 128, 128)
        """
        try:
            import librosa
        except ImportError:
            raise ImportError("librosa required for feature extraction")

        # Extract window around onset
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)

        if end - start < 10:
            return torch.zeros(1, 1, 128, 128, device=self.torch_device)

        window = audio[start:end]

        # Compute mel-spectrogram
        mel_spec = librosa.feature.melspectrogram(
            y=window, sr=sr, n_mels=128, fmax=8000, hop_length=len(window) // 128 + 1
        )

        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)

        # Normalize
        mel_min, mel_max = mel_spec_db.min(), mel_spec_db.max()
        mel_spec_norm = (mel_spec_db - mel_min) / (mel_max - mel_min + 1e-8)

        # Resize to 128x128
        if mel_spec_norm.shape[1] != 128:
            mel_spec_norm = np.resize(mel_spec_norm, (128, 128))

        features = torch.from_numpy(mel_spec_norm).float()
        features = features.unsqueeze(0).unsqueeze(0)

        return features.to(self.torch_device)

    def classify_onset(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0,
        return_uncertainty: bool = False,
    ) -> Union[Tuple[str, float], Dict]:
        """
        Classify a single drum hit using the ensemble.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds
            return_uncertainty: If True, return full uncertainty info

        Returns:
            If return_uncertainty=False: Tuple of (component_name, confidence)
            If return_uncertainty=True: Dict with component, confidence, uncertainty, agreement
        """
        features = self.extract_features(audio, sr, onset_time, window_ms)

        if return_uncertainty:
            result = self.predict_with_uncertainty(features)
            pred_idx = result["predictions"].item()
            return {
                "component": self.DRUM_COMPONENTS[pred_idx],
                "confidence": result["confidences"].item(),
                "uncertainty": result["uncertainty"].item(),
                "agreement": result["agreement"].item(),
            }
        else:
            predictions, confidences = self.predict(features)
            pred_idx = predictions.item()
            return self.DRUM_COMPONENTS[pred_idx], confidences.item()

    def classify_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        confidence_threshold: float = 0.0,
    ) -> List[Dict]:
        """
        Classify multiple drum hits efficiently.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds
            confidence_threshold: Minimum confidence to include in results

        Returns:
            List of dicts with time, component, confidence, uncertainty, agreement
        """
        if len(onset_times) == 0:
            return []

        # Extract all features
        features_list = [
            self.extract_features(audio, sr, t, window_ms) for t in onset_times
        ]
        features_batch = torch.cat(features_list, dim=0)

        # Get predictions with uncertainty
        results = self.predict_with_uncertainty(features_batch)

        # Build output
        output = []
        for i, onset_time in enumerate(onset_times):
            confidence = results["confidences"][i].item()

            if confidence >= confidence_threshold:
                pred_idx = results["predictions"][i].item()
                output.append(
                    {
                        "time": onset_time,
                        "component": self.DRUM_COMPONENTS[pred_idx],
                        "confidence": confidence,
                        "uncertainty": results["uncertainty"][i].item(),
                        "agreement": results["agreement"][i].item(),
                    }
                )

        return output

    def get_model_info(self) -> Dict:
        """Get information about ensemble configuration."""
        return {
            "num_models": len(self.models),
            "model_paths": [str(p) for p in self.model_paths],
            "model_classes": self.model_classes,
            "weights": self.weights,
            "fusion_method": self.fusion_method,
            "temperature": self.temperature,
            "device": self.device,
            "num_classes": self.num_classes,
        }


def create_ensemble_from_directory(
    run_dir: Union[str, Path],
    pattern: str = "seed_*/best_drum_classifier.pth",
    max_models: int = 5,
    device: Optional[str] = None,
) -> EnsembleClassifier:
    """
    Create an ensemble from a directory of training runs.

    Expects directory structure like:
        run_dir/
            seed_1337/best_drum_classifier.pth
            seed_42/best_drum_classifier.pth
            seed_2024/best_drum_classifier.pth

    Args:
        run_dir: Directory containing training runs
        pattern: Glob pattern for finding model files
        max_models: Maximum number of models to include
        device: Device for inference

    Returns:
        Configured EnsembleClassifier
    """
    run_dir = Path(run_dir)
    model_paths = sorted(run_dir.glob(pattern))[:max_models]

    if len(model_paths) == 0:
        raise ValueError(f"No models found matching {run_dir / pattern}")

    print(f"Found {len(model_paths)} models for ensemble")
    return EnsembleClassifier(model_paths, device=device)


def train_ensemble(
    dataset_path: Union[str, Path],
    output_dir: Union[str, Path],
    num_models: int = 5,
    base_seed: int = 1337,
    **train_kwargs,
) -> EnsembleClassifier:
    """
    Train multiple models with different seeds for ensembling.

    This is a convenience function that trains multiple models
    sequentially with different random seeds.

    Args:
        dataset_path: Path to training dataset
        output_dir: Directory to save trained models
        num_models: Number of models to train
        base_seed: Starting seed (will use base_seed, base_seed+1, ...)
        **train_kwargs: Additional arguments passed to train_classifier

    Returns:
        EnsembleClassifier with all trained models
    """
    output_dir = Path(output_dir)
    model_paths = []

    for i in range(num_models):
        seed = base_seed + i
        run_dir = output_dir / f"seed_{seed}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 60}")
        print(f"Training model {i + 1}/{num_models} with seed {seed}")
        print(f"{'=' * 60}\n")

        # This helper currently does not invoke the training loop directly.
        # It emits reproducible commands and expects an external trainer to
        # produce model artifacts at the expected path.
        model_path = run_dir / "best_drum_classifier.pth"

        if model_path.exists():
            print(f"Model already exists at {model_path}, skipping training")
        else:
            print(f"[INFO] Missing model artifact for seed={seed}: {model_path}")
            print(
                f"  Suggested command: python train_classifier.py --seed {seed} "
                f"--output \"{run_dir}\""
            )

        model_paths.append(model_path)

    # Return ensemble of trained models
    existing_paths = [p for p in model_paths if p.exists()]
    if existing_paths:
        return EnsembleClassifier(existing_paths)
    else:
        raise RuntimeError("No trained models found. Train models first.")


if __name__ == "__main__":
    print("Ensemble Inference Module")
    print("=" * 50)

    # Demo: Show how ensemble would be used
    print("\nUsage example:")
    print("""
    # Create ensemble from multiple trained models
    ensemble = EnsembleClassifier(
        model_paths=[
            "runs/prod_combined_warmup/best_drum_classifier.pth",
            "runs/prod_combined_quick/best_drum_classifier.pth",
        ],
        weights=[0.6, 0.4],  # Weight by validation performance
        fusion_method="logit",
    )
    
    # Classify a single hit
    component, confidence = ensemble.classify_onset(audio, sr, onset_time=0.5)
    
    # Classify with uncertainty
    result = ensemble.classify_onset(audio, sr, 0.5, return_uncertainty=True)
    print(f"Component: {result['component']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Uncertainty: {result['uncertainty']:.3f}")
    print(f"Agreement: {result['agreement']:.1%}")
    
    # Batch inference
    results = ensemble.classify_batch(audio, sr, onset_times=[0.5, 1.0, 1.5])
    """)

    # Test with dummy data if models exist
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, help="Directory with trained models")
    args = parser.parse_args()

    if args.model_dir and args.model_dir.exists():
        try:
            ensemble = create_ensemble_from_directory(args.model_dir)
            print(f"\nEnsemble info: {ensemble.get_model_info()}")

            # Test with random input
            dummy_features = torch.randn(4, 1, 128, 128)
            preds, confs = ensemble.predict(dummy_features)
            print(f"\nTest predictions: {preds.tolist()}")
            print(f"Test confidences: {[f'{c:.2%}' for c in confs.tolist()]}")
        except Exception as e:
            print(f"Error loading models: {e}")
