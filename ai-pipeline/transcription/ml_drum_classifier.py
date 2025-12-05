"""
ML-Based Drum Classifier using PyTorch

This module provides a neural network-based drum classifier that can be
trained on labeled drum samples.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa
import numpy as np
from typing import List, Tuple, Dict, Optional
import os


class DrumClassifierCNN(nn.Module):
    """
    Convolutional Neural Network for drum sound classification.

    Architecture:
    - Input: 128x128 mel-spectrogram
    - 4 convolutional blocks with batch normalization
    - Global average pooling
    - Dropout for regularization
    - Fully connected output layer
    """

    # Note: This is a reference list. The actual class list is determined by
    # components.json in the dataset. Classes like 'shaker', 'tambourine',
    # 'drum_mix', 'crash_1', 'crash_2' are excluded (see excluded_classes.py).
    # Multi-cymbal distinction is handled via pitch-based post-processing.
    DRUM_COMPONENTS = [
        "aux_percussion",
        "china",
        "crash",
        "cross_stick",
        "cymbal_choke",  # NEW: Choked crash/china/ride detection
        "hihat_closed",
        "hihat_foot_splash",
        "hihat_open",
        "hihat_pedal",
        "hihat_splash",
        "kick",
        "ride_bell",
        "ride_bow",
        "rimshot",
        "snare",
        "snare_center",
        "snare_cross_stick",
        "snare_rimshot",
        "splash",
        "tom_high",
        "tom_low",
        "tom_mid",
    ]

    def __init__(self, num_classes: int = 21, dropout: float = 0.3):
        super().__init__()

        # Convolutional blocks
        self.conv1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )

        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )

        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )

        self.conv4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
        )

        # Fully connected layers
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(256, num_classes)

    def forward(self, x):
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, 1, height, width)

        Returns:
            Logits of shape (batch, num_classes)
        """
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)

        x = x.view(x.size(0), -1)  # Flatten
        x = self.dropout(x)
        x = self.fc(x)

        return x


class MLDrumClassifier:
    """
    ML-based drum classifier with inference capabilities.

    Features:
    - Automatic device detection (CUDA/CPU)
    - Model warm-up for optimal first-inference latency
    - Batch processing for efficient GPU utilization
    - Thread-safe inference (eval mode with torch.inference_mode)
    """

    # Class-level model cache for reuse across instances
    _model_cache: Dict[str, "MLDrumClassifier"] = {}
    _cache_lock = None  # Will be initialized lazily

    @classmethod
    def get_cached(
        cls, model_path: str, device: Optional[str] = None
    ) -> "MLDrumClassifier":
        """Get a cached classifier instance, creating one if needed.

        This avoids reloading the model for every inference call.
        """
        import threading

        if cls._cache_lock is None:
            cls._cache_lock = threading.Lock()

        cache_key = f"{model_path}:{device or 'auto'}"

        with cls._cache_lock:
            if cache_key not in cls._model_cache:
                cls._model_cache[cache_key] = cls(model_path, device)
            return cls._model_cache[cache_key]

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize classifier.

        Args:
            model_path: Path to trained model weights (.pth file)
            device: Device to run inference on ('cuda' or 'cpu')
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = DrumClassifierCNN()

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

        self.model.to(self.device)
        self.model.eval()

        # Warm up the model with a dummy inference
        self._warm_up()

    def _warm_up(self):
        """Warm up the model with a dummy inference to compile CUDA kernels."""
        dummy_input = torch.zeros(1, 1, 128, 128, device=self.device)
        with torch.inference_mode():
            _ = self.model(dummy_input)
        # Synchronize to ensure warm-up is complete
        if self.device == "cuda":
            torch.cuda.synchronize()

    def load_model(self, model_path: str):
        """Load trained model weights."""
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        print(f"Loaded model from {model_path}")

    def save_model(self, model_path: str):
        """Save model weights."""
        torch.save(self.model.state_dict(), model_path)
        print(f"Saved model to {model_path}")

    def _extract_single_feature(
        self, audio: np.ndarray, sr: int, onset_time: float, window_ms: float = 100.0
    ) -> np.ndarray:
        """
        Extract mel-spectrogram features for a single onset (CPU, no tensor).

        Returns:
            Numpy array of shape (128, 128) or None if invalid window
        """
        # Extract window around onset
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)

        if end - start < 10:
            return None  # Invalid window marker

        window = audio[start:end]

        # Compute mel-spectrogram
        mel_spec = librosa.feature.melspectrogram(
            y=window, sr=sr, n_mels=128, fmax=8000, hop_length=len(window) // 128 + 1
        )

        # Convert to log scale
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)

        # Normalize to [0, 1]
        mel_spec_norm = (mel_spec_db - mel_spec_db.min()) / (
            mel_spec_db.max() - mel_spec_db.min() + 1e-8
        )

        # Resize to 128x128
        if mel_spec_norm.shape[1] != 128:
            mel_spec_norm = np.resize(mel_spec_norm, (128, 128))

        return mel_spec_norm

    def extract_features(
        self, audio: np.ndarray, sr: int, onset_time: float, window_ms: float = 100.0
    ) -> torch.Tensor:
        """
        Extract mel-spectrogram features around an onset.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds

        Returns:
            Mel-spectrogram tensor of shape (1, 1, 128, 128)
        """
        feat = self._extract_single_feature(audio, sr, onset_time, window_ms)
        if feat is None:
            return torch.zeros(1, 1, 128, 128, device=self.device)

        features = torch.from_numpy(feat).float()
        features = features.unsqueeze(0).unsqueeze(0)  # Add batch and channel dims
        return features.to(self.device)

    def extract_features_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
    ) -> Tuple[torch.Tensor, List[int]]:
        """
        Extract mel-spectrogram features for multiple onsets efficiently.

        This extracts all features on CPU first, then transfers to GPU in one batch,
        which is MUCH faster than transferring one at a time.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds

        Returns:
            Tuple of:
                - Batched tensor of shape (N, 1, 128, 128)
                - List of valid indices (indices where features were successfully extracted)
        """
        features_list = []
        valid_indices = []

        for i, onset_time in enumerate(onset_times):
            feat = self._extract_single_feature(audio, sr, onset_time, window_ms)
            if feat is not None:
                features_list.append(feat)
                valid_indices.append(i)

        if not features_list:
            return torch.zeros(0, 1, 128, 128, device=self.device), []

        # Stack all features and transfer to GPU in one operation
        batch_np = np.stack(features_list, axis=0)  # (N, 128, 128)
        batch_tensor = torch.from_numpy(batch_np).float()
        batch_tensor = batch_tensor.unsqueeze(1)  # (N, 1, 128, 128)

        return batch_tensor.to(self.device), valid_indices

    def classify_onset_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
    ) -> List[Tuple[str, float]]:
        """
        Classify multiple drum hits in a single batch inference.

        This is 10-50x faster than calling classify_onset repeatedly because:
        1. Feature extraction can be parallelized
        2. GPU batch inference is massively more efficient
        3. Only one CPU->GPU transfer instead of N transfers

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds

        Returns:
            List of (component name, confidence) tuples, one per onset_time.
            Invalid windows return ("unknown", 0.0)
        """
        if not onset_times:
            return []

        # Initialize results with default values
        results: List[Tuple[str, float]] = [("unknown", 0.0)] * len(onset_times)

        # Extract features in batch
        features_batch, valid_indices = self.extract_features_batch(
            audio, sr, onset_times, window_ms
        )

        if len(valid_indices) == 0:
            return results

        # Batch inference - single forward pass for all onsets!
        # Using inference_mode for ~10% faster inference than no_grad
        with torch.inference_mode():
            logits = self.model(features_batch)  # (N, num_classes)
            probs = F.softmax(logits, dim=1)
            confidences, pred_indices = torch.max(probs, dim=1)

        # Map results back to original indices
        confidences_cpu = confidences.cpu().numpy()
        pred_indices_cpu = pred_indices.cpu().numpy()

        for i, valid_idx in enumerate(valid_indices):
            component = DrumClassifierCNN.DRUM_COMPONENTS[pred_indices_cpu[i]]
            results[valid_idx] = (component, float(confidences_cpu[i]))

        return results

    def classify_onset(
        self, audio: np.ndarray, sr: int, onset_time: float, window_ms: float = 100.0
    ) -> Tuple[str, float]:
        """
        Classify a single drum hit.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds

        Returns:
            Tuple of (component name, confidence)
        """
        features = self.extract_features(audio, sr, onset_time, window_ms)

        with torch.inference_mode():
            logits = self.model(features)
            probs = F.softmax(logits, dim=1)
            confidence, pred_idx = torch.max(probs, dim=1)

        component = DrumClassifierCNN.DRUM_COMPONENTS[pred_idx.item()]
        confidence_score = confidence.item()

        return component, confidence_score


def classify_drums_ml(
    audio: Tuple[np.ndarray, int],
    onsets: List[Tuple[float, float]],
    model_path: Optional[str] = None,
    confidence_threshold: float = 0.6,
    device: Optional[str] = None,
    batch_size: int = 256,
) -> List[Dict]:
    """
    Classify drum components using ML model with efficient batch processing.

    Args:
        audio: Tuple of (audio data, sample rate)
        onsets: List of (time, onset_confidence) tuples
        model_path: Path to trained model (if None, falls back to heuristics)
        confidence_threshold: Minimum confidence to include
        device: Device for inference
        batch_size: Number of onsets to process in each batch (for memory efficiency)

    Returns:
        List of classified hits with metadata
    """
    audio_data, sr = audio

    # Fall back to heuristic classifier if no model is available
    if model_path is None or not os.path.exists(model_path):
        print("Warning: No trained model found. Using heuristic classifier.")
        from .drum_classifier import SimpleDrumClassifier

        classifier = SimpleDrumClassifier()
        use_ml = False

        # Heuristic classifier doesn't support batch - use sequential
        classified_hits = []
        for onset_time, onset_confidence in onsets:
            component, class_confidence = classifier.classify_onset(
                audio_data, sr, onset_time
            )
            combined_confidence = (onset_confidence + class_confidence) / 2.0
            if combined_confidence >= confidence_threshold and component != "unknown":
                classified_hits.append(
                    {
                        "time": onset_time,
                        "component": component,
                        "confidence": combined_confidence,
                        "onset_confidence": onset_confidence,
                        "class_confidence": class_confidence,
                        "ml_based": use_ml,
                    }
                )
        return classified_hits

    # Use ML classifier with batch processing
    # Use cached classifier to avoid reloading model for each call
    classifier = MLDrumClassifier.get_cached(model_path, device)
    use_ml = True
    classified_hits = []

    # Process in batches for memory efficiency on very long tracks
    for batch_start in range(0, len(onsets), batch_size):
        batch_onsets = onsets[batch_start : batch_start + batch_size]
        onset_times = [onset_time for onset_time, _ in batch_onsets]
        onset_confidences = [onset_conf for _, onset_conf in batch_onsets]

        # Batch inference - MUCH faster than sequential!
        batch_results = classifier.classify_onset_batch(audio_data, sr, onset_times)

        for i, (component, class_confidence) in enumerate(batch_results):
            onset_confidence = onset_confidences[i]
            onset_time = onset_times[i]

            # Combine onset detection confidence and classification confidence
            combined_confidence = (onset_confidence + class_confidence) / 2.0

            if combined_confidence >= confidence_threshold and component != "unknown":
                classified_hits.append(
                    {
                        "time": onset_time,
                        "component": component,
                        "confidence": combined_confidence,
                        "onset_confidence": onset_confidence,
                        "class_confidence": class_confidence,
                        "ml_based": use_ml,
                    }
                )

    return classified_hits


if __name__ == "__main__":
    # Quick test
    print("DrumClassifierCNN architecture:")
    model = DrumClassifierCNN()
    print(model)

    # Test forward pass
    dummy_input = torch.randn(1, 1, 128, 128)
    output = model(dummy_input)
    print(f"\nInput shape: {dummy_input.shape}")
    print(f"Output shape: {output.shape}")
    print(f"Number of parameters: {sum(p.numel() for p in model.parameters())}")


# Backwards compatibility alias used by earlier pipeline integration code.
class DrumClassifierModel(MLDrumClassifier):
    """Alias for MLDrumClassifier kept for compatibility."""

    def classify_batch(self, audio, sr, onsets, **kwargs):
        """
        Classify multiple onsets efficiently using true batch processing.

        Args:
            audio: Audio data
            sr: Sample rate
            onsets: List of onset times in seconds
            **kwargs: Additional arguments (e.g., window_ms)

        Returns:
            List of (component, confidence) tuples
        """
        return self.classify_onset_batch(audio, sr, onsets, **kwargs)
