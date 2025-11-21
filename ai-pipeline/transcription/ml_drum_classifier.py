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
import json
from pathlib import Path


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
    
    DRUM_COMPONENTS = [
        "kick",
        "snare_center",
        "snare_rimshot",
        "snare_cross_stick",
        "snare_off",
        "hihat_closed",
        "hihat_open",
        "hihat_half",
        "hihat_pedal",
        "hihat_splash",
        "tom_high",
        "tom_mid",
        "tom_low",
        "ride_bow",
        "ride_bell",
        "ride_edge",
        "crash_1",
        "crash_2",
        "china",
        "splash",
        "cowbell",
        "tambourine",
        "clap",
        "shaker"
    ]
    
    def __init__(self, num_classes: int = 24, dropout: float = 0.3):
        super().__init__()
        
        # Convolutional blocks
        self.conv1 = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        
        self.conv3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(2)
        )
        
        self.conv4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1))
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
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None
    ):
        """
        Initialize classifier.
        
        Args:
            model_path: Path to trained model weights (.pth file)
            device: Device to run inference on ('cuda' or 'cpu')
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = DrumClassifierCNN()
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        
        self.model.to(self.device)
        self.model.eval()
    
    def load_model(self, model_path: str):
        """Load trained model weights."""
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        print(f"Loaded model from {model_path}")
    
    def save_model(self, model_path: str):
        """Save model weights."""
        torch.save(self.model.state_dict(), model_path)
        print(f"Saved model to {model_path}")
    
    def extract_features(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0
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
        # Extract window around onset
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)
        
        if end - start < 10:
            # Return zeros for invalid windows
            return torch.zeros(1, 1, 128, 128, device=self.device)
        
        window = audio[start:end]
        
        # Compute mel-spectrogram
        mel_spec = librosa.feature.melspectrogram(
            y=window,
            sr=sr,
            n_mels=128,
            fmax=8000,
            hop_length=len(window) // 128 + 1
        )
        
        # Convert to log scale
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        # Normalize to [0, 1]
        mel_spec_norm = (mel_spec_db - mel_spec_db.min()) / (mel_spec_db.max() - mel_spec_db.min() + 1e-8)
        
        # Resize to 128x128
        if mel_spec_norm.shape[1] != 128:
            mel_spec_norm = np.resize(mel_spec_norm, (128, 128))
        
        # Convert to tensor
        features = torch.from_numpy(mel_spec_norm).float()
        features = features.unsqueeze(0).unsqueeze(0)  # Add batch and channel dimensions
        
        return features.to(self.device)
    
    def classify_onset(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0
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
        
        with torch.no_grad():
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
    device: Optional[str] = None
) -> List[Dict]:
    """
    Classify drum components using ML model.
    
    Args:
        audio: Tuple of (audio data, sample rate)
        onsets: List of (time, onset_confidence) tuples
        model_path: Path to trained model (if None, falls back to heuristics)
        confidence_threshold: Minimum confidence to include
        device: Device for inference
        
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
    else:
        classifier = MLDrumClassifier(model_path, device)
        use_ml = True
    
    classified_hits = []
    
    for onset_time, onset_confidence in onsets:
        component, class_confidence = classifier.classify_onset(
            audio_data, sr, onset_time
        )
        
        # Combine onset detection confidence and classification confidence
        combined_confidence = (onset_confidence + class_confidence) / 2.0
        
        if combined_confidence >= confidence_threshold and component != "unknown":
            classified_hits.append({
                "time": onset_time,
                "component": component,
                "confidence": combined_confidence,
                "onset_confidence": onset_confidence,
                "class_confidence": class_confidence,
                "ml_based": use_ml
            })
    
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
        results = []
        for onset in onsets:
            results.append(self.classify_onset(audio, sr, onset, **kwargs))
        return results
