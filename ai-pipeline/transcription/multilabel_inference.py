#!/usr/bin/env python3
"""
Multi-Label Drum Classifier Inference Module

This module provides production inference for the multi-label drum classifier,
which can detect multiple simultaneous drum hits (e.g., kick + hi-hat, snare + crash).

Key differences from single-label inference (ml_drum_classifier.py):
1. Uses sigmoid instead of softmax (each class is independent)
2. Returns multiple classes per onset (not just the top-1)
3. Supports per-class thresholds for optimal F1
4. Integrates with count estimation for simultaneous same-class hits

Usage:
    from transcription.multilabel_inference import MultiLabelDrumClassifier
    
    # Initialize with model and optional per-class thresholds
    classifier = MultiLabelDrumClassifier(
        model_path="runs/v5_multilabel/best_model.pt",
        threshold=0.5,
        per_class_thresholds={"crash": 0.4, "hihat_closed": 0.6}
    )
    
    # Classify a single onset
    detections = classifier.classify_onset(audio, sr, onset_time)
    # Returns: {"kick": 0.95, "hihat_closed": 0.82}
    
    # Batch inference for efficiency
    all_detections = classifier.classify_batch(audio, sr, onset_times)
    # Returns: [{"kick": 0.95, "hihat_closed": 0.82}, {"snare": 0.91, "crash": 0.78}, ...]
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    librosa = None

logger = logging.getLogger(__name__)


# =============================================================================
# 12-Class Drum Component Mapping (Production Structure)
# =============================================================================
# Matches components.json in prod_v5_multilabel dataset

DEFAULT_DRUM_COMPONENTS = [
    "china",         # 0
    "crash",         # 1
    "cross_stick",   # 2
    "hihat_closed",  # 3
    "hihat_open",    # 4
    "hihat_pedal",   # 5
    "kick",          # 6
    "ride_bell",     # 7
    "ride_bow",      # 8
    "snare",         # 9
    "splash",        # 10
    "tom",           # 11
]


def load_model_checkpoint(
    model_path: str,
    device: str = "cpu",
    num_classes: int = 12,
    prefer_ema: bool = True,
) -> nn.Module:
    """
    Load a multi-label model checkpoint with flexible format handling.
    
    Args:
        model_path: Path to the model checkpoint
        device: Device to load the model on
        num_classes: Expected number of output classes
        prefer_ema: Whether to prefer EMA weights if available (default True)
        
    Returns:
        Loaded model in eval mode
    """
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    # Determine model architecture from checkpoint
    if 'config' in checkpoint:
        config = checkpoint['config']
        model_version = config.get('model_version', 'v5')
        v5_size = config.get('v5_size', 'large')
    else:
        model_version = 'v5'
        v5_size = 'large'
    
    # Create model based on architecture
    if model_version == 'v5':
        try:
            from training.models.cnn_v5 import (
                DrumClassifierCNNv5, 
                cnn_v5_small, 
                cnn_v5_medium, 
                cnn_v5_large
            )
            
            size_configs = {
                "small": cnn_v5_small,
                "medium": cnn_v5_medium,
                "large": cnn_v5_large,
            }
            config_fn = size_configs.get(v5_size, cnn_v5_large)
            backbone = config_fn(
                num_classes=num_classes,
                drop_path_rate=0.0,  # Disable for inference
                use_deep_supervision=False,
                use_multi_task=False,
            )
            logger.info(f"Created V5 {v5_size} model for multi-label inference")
        except ImportError:
            # Fallback to basic CNN
            from transcription.ml_drum_classifier import DrumClassifierCNN
            backbone = DrumClassifierCNN(num_classes=num_classes)
            logger.warning("V5 model not available, using basic CNN")
    else:
        from transcription.ml_drum_classifier import DrumClassifierCNN
        backbone = DrumClassifierCNN(num_classes=num_classes)
    
    # Extract state dict - prefer EMA weights if available
    if prefer_ema and 'ema_state_dict' in checkpoint:
        ema_state = checkpoint['ema_state_dict']
        # Handle nested EMA format: {'ema_model': {...}, 'ema_decay': ...}
        if isinstance(ema_state, dict) and 'ema_model' in ema_state:
            state_dict = ema_state['ema_model']
        else:
            state_dict = ema_state
        logger.info("Using EMA weights for inference")
    elif 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    elif 'model' in checkpoint:
        state_dict = checkpoint['model']
    else:
        state_dict = checkpoint
    
    # Handle backbone prefix in state dict
    cleaned_state_dict = {}
    for key, value in state_dict.items():
        # Remove 'backbone.' prefix if present (from MultiLabelDrumClassifier wrapper)
        if key.startswith('backbone.'):
            cleaned_key = key[len('backbone.'):]
        else:
            cleaned_key = key
        cleaned_state_dict[cleaned_key] = value
    
    # Load weights
    missing, unexpected = backbone.load_state_dict(cleaned_state_dict, strict=False)
    if missing:
        logger.debug(f"Missing keys (may be expected): {missing[:5]}...")
    if unexpected:
        logger.debug(f"Unexpected keys: {unexpected[:5]}...")
    
    backbone.to(device)
    backbone.eval()
    
    return backbone


class MultiLabelDrumClassifier:
    """
    Multi-label drum classifier for production inference.
    
    Unlike single-label classification (softmax, pick top-1), multi-label
    uses sigmoid per-class and thresholding to detect multiple active classes.
    
    Features:
    - Automatic device detection (CUDA/CPU)
    - Per-class thresholds for optimal precision/recall
    - Batch inference for efficiency
    - Model caching for reuse
    - Thread-safe inference
    """
    
    # Class-level model cache
    _model_cache: Dict[str, "MultiLabelDrumClassifier"] = {}
    _cache_lock: Optional[threading.Lock] = None
    
    @classmethod
    def get_cached(
        cls,
        model_path: str,
        threshold: float = 0.5,
        per_class_thresholds: Optional[Dict[str, float]] = None,
        thresholds_file: Optional[str] = None,
        device: Optional[str] = None,
        threshold_scale: float = 1.0,
    ) -> "MultiLabelDrumClassifier":
        """Get a cached classifier instance, creating one if needed."""
        if cls._cache_lock is None:
            cls._cache_lock = threading.Lock()
        
        cache_key = f"{model_path}:{device or 'auto'}:{threshold_scale}"
        
        with cls._cache_lock:
            if cache_key not in cls._model_cache:
                cls._model_cache[cache_key] = cls(
                    model_path=model_path,
                    threshold=threshold,
                    per_class_thresholds=per_class_thresholds,
                    thresholds_file=thresholds_file,
                    device=device,
                    threshold_scale=threshold_scale,
                )
            return cls._model_cache[cache_key]
    
    def __init__(
        self,
        model_path: str,
        threshold: float = 0.5,
        per_class_thresholds: Optional[Dict[str, float]] = None,
        thresholds_file: Optional[str] = None,
        device: Optional[str] = None,
        components: Optional[List[str]] = None,
        threshold_scale: float = 1.0,
    ):
        """
        Initialize the multi-label drum classifier.
        
        Args:
            model_path: Path to trained multi-label model checkpoint
            threshold: Global classification threshold (0.0-1.0)
            per_class_thresholds: Optional dict of class_name -> threshold
            thresholds_file: Optional path to JSON file with per-class thresholds
            device: Device for inference ('cuda', 'cpu', or None for auto)
            components: List of class names (default: DEFAULT_DRUM_COMPONENTS)
            threshold_scale: Scale factor for thresholds (0.0-1.0). Use <1.0
                to lower thresholds for inference on Demucs-separated audio,
                which produces systematically lower probabilities than clean
                training data due to domain gap. Default 1.0 (no scaling).
        """
        self.model_path = model_path
        self.threshold = threshold
        self.threshold_scale = threshold_scale
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.components = components or DEFAULT_DRUM_COMPONENTS
        self.num_classes = len(self.components)
        
        # Build class name to index mapping
        self.class_to_idx = {name: i for i, name in enumerate(self.components)}
        self.idx_to_class = {i: name for i, name in enumerate(self.components)}
        
        # Load per-class thresholds
        self.per_class_thresholds: Dict[str, float] = {}
        if thresholds_file and os.path.exists(thresholds_file):
            self._load_thresholds_from_file(thresholds_file)
        if per_class_thresholds:
            self.per_class_thresholds.update(per_class_thresholds)
        
        # Load model
        logger.info(f"Loading multi-label model from {model_path}")
        self.model = load_model_checkpoint(
            model_path, 
            device=self.device,
            num_classes=self.num_classes,
        )
        
        # Warm up
        self._warm_up()
        
        logger.info(
            f"Multi-label classifier ready on {self.device} "
            f"(threshold={threshold}, {len(self.per_class_thresholds)} per-class thresholds"
            f"{f', scale={threshold_scale}' if threshold_scale != 1.0 else ''})"
        )
    
    def _load_thresholds_from_file(self, thresholds_file: str):
        """Load per-class thresholds from a JSON file."""
        try:
            with open(thresholds_file, 'r') as f:
                data = json.load(f)
            
            # Handle nested formats: {thresholds: {...}} or {per_class_thresholds: {...}}
            if isinstance(data, dict):
                if 'thresholds' in data:
                    data = data['thresholds']
                elif 'per_class_thresholds' in data:
                    data = data['per_class_thresholds']
            
            if isinstance(data, dict):
                # Handle both {class: threshold} and {class: {threshold: X, ...}} formats
                for key, value in data.items():
                    if isinstance(value, (int, float)):
                        self.per_class_thresholds[key] = float(value)
                    elif isinstance(value, dict) and 'threshold' in value:
                        self.per_class_thresholds[key] = float(value['threshold'])
            
            logger.info(f"Loaded {len(self.per_class_thresholds)} thresholds from {thresholds_file}")
        except Exception as e:
            logger.warning(f"Failed to load thresholds from {thresholds_file}: {e}")
    
    def _warm_up(self):
        """Warm up the model with a dummy inference."""
        dummy_input = torch.zeros(1, 1, 128, 128, device=self.device)
        with torch.inference_mode():
            _ = self.model(dummy_input)
        if self.device == "cuda":
            torch.cuda.synchronize()
    
    # Domain gap scaling tiers for Demucs-separated audio.
    #
    # Real commercial audio through Demucs produces systematically lower
    # sigmoid probabilities than clean training data. Tiered scaling
    # compensates for this gap based on per-class severity.
    #
    # Per-class domain gaps (v5_finetune_demucs_v2, epoch 6):
    #   splash +0.687, china +0.668, crash +0.529 → Tier 3 (sensitive)
    #   ride_bell +0.431, cross_stick +0.327      → Tier 2 (moderate)
    #   kick +0.375, hihat_closed +0.379, etc.    → Tier 1 (common)
    #
    # Tier 1 (common): kick, snare, hihat_*, tom, ride_bow
    #   Small gap — these classes have abundant Demucs training data.
    #   scale^0.25 with threshold_scale=0.7 → ~8.5% threshold reduction
    #
    # Tier 2 (moderate): cross_stick, ride_bell
    #   Medium gap — fewer training examples, some spectral ambiguity.
    #   scale^0.5 with threshold_scale=0.7 → ~16% threshold reduction
    #
    # Tier 3 (sensitive): crash, china, splash
    #   Largest gaps. China and splash were moved here from the old
    #   "zero-Demucs" tier after slakh2100_demucs was added to training
    #   (236K china + 5.6K splash Demucs samples). The model CAN now
    #   produce meaningful probabilities for these on Demucs audio, but
    #   the domain gap remains large (>0.5).
    #   scale^0.75 with threshold_scale=0.7 → ~23% threshold reduction
    _MODERATE_DOMAIN_GAP_CLASSES = frozenset({
        'ride_bell', 'cross_stick',
    })
    _SENSITIVE_DOMAIN_GAP_CLASSES = frozenset({
        'crash', 'china', 'splash',
    })

    # Ensemble classification class groups.
    # Body drums are classified on full-mix (hybrid) audio where the model
    # has no domain gap. Cymbal classes are classified on Demucs-separated
    # audio — the only source that preserves enough cymbal isolation for
    # the model to detect china/crash/splash at all.
    _ENSEMBLE_HYBRID_CLASSES = frozenset({
        'kick', 'snare', 'hihat_closed', 'hihat_open', 'hihat_pedal',
        'tom', 'cross_stick', 'ride_bow', 'ride_bell',
    })
    _ENSEMBLE_DEMUCS_CLASSES = frozenset({
        'crash', 'china', 'splash',
    })

    def get_threshold(self, class_name: str) -> float:
        """Get the effective threshold for a specific class.

        Applies tiered domain gap scaling to compensate for the probability
        gap between pre-extracted validation data and real commercial audio
        through Demucs separation.

        With threshold_scale=1.0 (e.g. Demucs-only thresholds or hybrid
        classification), no scaling is applied — thresholds are used as-is.

        With threshold_scale=0.7 and mixed thresholds:
          kick:       0.39 * 0.915 = 0.357  (Tier 1, scale^0.25)
          ride_bell:  0.46 * 0.837 = 0.385  (Tier 2, scale^0.5)
          crash:      0.67 * 0.766 = 0.513  (Tier 3, scale^0.75)
          china:      0.53 * 0.766 = 0.406  (Tier 3, scale^0.75)
          splash:     0.82 * 0.766 = 0.628  (Tier 3, scale^0.75)
        """
        base = self.per_class_thresholds.get(class_name, self.threshold)

        if self.threshold_scale >= 1.0:
            return base

        # Tiered domain gap scaling
        if class_name in self._SENSITIVE_DOMAIN_GAP_CLASSES:
            return base * (self.threshold_scale ** 0.75)
        if class_name in self._MODERATE_DOMAIN_GAP_CLASSES:
            return base * (self.threshold_scale ** 0.5)
        # Common classes: gentle scaling
        return base * (self.threshold_scale ** 0.25)
    
    def set_threshold(self, class_name: str, threshold: float):
        """Set the threshold for a specific class."""
        self.per_class_thresholds[class_name] = threshold
    
    def _extract_spectrogram(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0,
    ) -> Optional[np.ndarray]:
        """
        Extract mel-spectrogram features for a single onset.
        
        Args:
            audio: Audio data (mono, 1D array)
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds
            
        Returns:
            Mel-spectrogram as numpy array (128, 128) or None if invalid
        """
        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return None
        
        # Handle stereo by converting to mono
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] == 2 else audio.mean(axis=1)
        
        # Resample to 22050 Hz to match training data
        # (all v3 training data was extracted at sr=22050)
        if sr != 22050:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=22050)
            sr = 22050
        
        # Asymmetric window around onset (matching training: extract_multilabel_from_midi.py)
        # Training uses 1/4 window BEFORE onset, full window AFTER onset.
        # This captures the attack transient + decay, which is the most discriminative part.
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)
        
        if end - start < 10:
            return None
        
        segment = audio[start:end]
        
        # Pad if segment is shorter than window (at audio boundaries)
        if len(segment) < window_samples:
            segment = np.pad(segment, (0, window_samples - len(segment)), mode='constant')
        
        # Match training pipeline exactly (extract_multilabel_from_midi.py):
        # Power mel spectrogram + power_to_db (NOT magnitude + amplitude_to_db!)
        hop_length = max(1, len(segment) // 128)
        mel_spec = librosa.feature.melspectrogram(
            y=segment.astype(np.float32), sr=sr, n_mels=128,
            fmax=8000, hop_length=hop_length,
        )
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)
        
        # Resize to 128 frames (matching training)
        if mel_db.shape[1] != 128:
            if mel_db.shape[1] < 128:
                pad_width = 128 - mel_db.shape[1]
                mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
            else:
                mel_db = mel_db[:, :128]
        
        # Normalize to [0, 1] (matching training data)
        mel_min, mel_max = mel_db.min(), mel_db.max()
        if mel_max - mel_min > 1e-8:
            mel_db = (mel_db - mel_min) / (mel_max - mel_min)
        else:
            mel_db = np.zeros_like(mel_db)
        
        return mel_db.astype(np.float32)
    
    # ----- Musical constraint groups for multi-label refinement -----
    # Hi-hat articulations are mutually exclusive — you can't play closed + open
    # at the same time on a single hi-hat. Only one should fire per onset.
    _HIHAT_EXCLUSIVE_GROUP = frozenset({'hihat_closed', 'hihat_open', 'hihat_pedal'})
    
    # Body drums (kick/snare) rarely co-occur. Genuine simultaneous kick+snare
    # (e.g., in a fill) produces very confident signals for BOTH. Low-confidence
    # co-occurrence is almost always Demucs domain gap artifact.
    _BODY_COOCCURRENCE_CLASSES = frozenset({'kick', 'snare'})
    _BODY_COOCCURRENCE_MIN_PROB = 0.40  # Both must exceed this for co-occurrence
    
    # Cymbal classes that naturally layer with body drums (no restriction needed)
    _CYMBAL_CLASSES = frozenset({
        'crash', 'china', 'splash', 'ride_bell', 'ride_bow',
    })
    
    # Minimum ratio of the weakest detection to the strongest detection at an
    # onset. Detections below this ratio relative to the peak are likely
    # Demucs bleed causing false multi-label activation.
    _RELATIVE_CONFIDENCE_RATIO = 0.35
    
    # Maximum number of instruments at a single onset. In complex drumming
    # (esp. prog metal), 4 simultaneous instruments is plausible:
    # e.g., kick + snare + crash + china, or kick + hihat + ride + tom.
    _MAX_COMPONENTS_PER_ONSET = 4

    def _apply_thresholds(
        self,
        probabilities: np.ndarray,
    ) -> Dict[str, float]:
        """
        Apply thresholds to probabilities and return detected classes.
        
        Args:
            probabilities: Array of shape (num_classes,) with sigmoid probabilities
            
        Returns:
            Dict of detected_class -> probability for classes above threshold
        """
        detections = {}
        
        for idx, prob in enumerate(probabilities):
            class_name = self.idx_to_class[idx]
            threshold = self.get_threshold(class_name)
            
            if prob >= threshold:
                detections[class_name] = float(prob)
        
        return detections
    
    def _refine_multilabel_detections(
        self,
        detections: Dict[str, float],
    ) -> Dict[str, float]:
        """
        Apply musical constraints to prevent implausible multi-label co-detections.
        
        The model was trained on clean isolated drum recordings but runs inference
        on Demucs-separated audio. Demucs domain gap causes sigmoid probabilities
        for multiple classes to cluster near their thresholds, producing false
        multi-label activations (e.g., kick+snare+hihat on a kick-only hit).
        
        This method enforces:
        1. Hi-hat mutual exclusion (closed/open/pedal — keep highest)
        2. Kick+snare co-occurrence requires HIGH confidence for both
        3. Relative confidence filter — weak secondary detections are removed
        4. Max 3 instruments per onset
        
        Cymbal classes (crash, china, splash, ride) are exempt from the relative
        confidence filter since they naturally layer with body drums.
        
        Args:
            detections: Dict of class_name -> probability from _apply_thresholds()
            
        Returns:
            Refined dict with implausible co-detections removed
        """
        if len(detections) <= 1:
            return detections
        
        refined = dict(detections)
        
        # --- 1. Hi-hat mutual exclusion ---
        # Only one hi-hat articulation can sound at a time. Keep the highest.
        detected_hihats = {
            cls: prob for cls, prob in refined.items()
            if cls in self._HIHAT_EXCLUSIVE_GROUP
        }
        if len(detected_hihats) > 1:
            best_hihat = max(detected_hihats, key=detected_hihats.get)
            for cls in detected_hihats:
                if cls != best_hihat:
                    del refined[cls]
        
        # --- 2. Kick + snare co-occurrence gate ---
        # These rarely co-occur except in fills/accents. Require BOTH to be
        # clearly above a co-occurrence threshold, not just above individual
        # thresholds (which are too permissive due to inflated Demucs probs).
        detected_body = {
            cls: prob for cls, prob in refined.items()
            if cls in self._BODY_COOCCURRENCE_CLASSES
        }
        if len(detected_body) > 1:
            # Both kick and snare detected — check if both are confident enough
            body_probs = sorted(detected_body.values())
            weakest = body_probs[0]
            if weakest < self._BODY_COOCCURRENCE_MIN_PROB:
                # Remove the weakest body drum — it's likely a false detection
                weakest_cls = min(detected_body, key=detected_body.get)
                del refined[weakest_cls]
        
        # --- 3. Relative confidence filter ---
        # On Demucs audio, the model gives moderate probability to many classes
        # simultaneously. If a secondary detection is much weaker than the peak,
        # it's almost certainly domain gap artifact, not a real instrument.
        # Cymbals are exempt because they genuinely layer (crash + kick is common).
        if len(refined) > 1:
            peak_prob = max(refined.values())
            min_acceptable = peak_prob * self._RELATIVE_CONFIDENCE_RATIO
            to_remove = []
            for cls, prob in refined.items():
                if cls in self._CYMBAL_CLASSES:
                    continue  # Don't filter cymbals — they layer naturally
                if prob < min_acceptable:
                    to_remove.append(cls)
            for cls in to_remove:
                del refined[cls]
        
        # --- 4. Hard cap on total instruments per onset ---
        if len(refined) > self._MAX_COMPONENTS_PER_ONSET:
            # Keep top N by confidence
            sorted_detections = sorted(refined.items(), key=lambda x: x[1], reverse=True)
            refined = dict(sorted_detections[:self._MAX_COMPONENTS_PER_ONSET])
        
        return refined
    
    def classify_spectrogram(
        self,
        spectrogram: np.ndarray,
    ) -> Dict[str, float]:
        """
        Classify a pre-extracted spectrogram.
        
        Args:
            spectrogram: Mel-spectrogram of shape (128, 128)
            
        Returns:
            Dict of class -> probability for detected classes
        """
        # Prepare input tensor
        x = torch.from_numpy(spectrogram).float()
        x = x.unsqueeze(0).unsqueeze(0)  # (1, 1, 128, 128)
        x = x.to(self.device)
        
        # Inference
        with torch.inference_mode():
            logits = self.model(x)
            probs = torch.sigmoid(logits)
        
        # Apply thresholds + multi-label refinement
        probs_np = probs.cpu().numpy()[0]
        raw = self._apply_thresholds(probs_np)
        return self._refine_multilabel_detections(raw)
    
    def classify_onset(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0,
    ) -> Dict[str, float]:
        """
        Classify a single onset, returning all detected classes.
        
        Args:
            audio: Audio data (1D or 2D array)
            sr: Sample rate
            onset_time: Time of onset in seconds
            window_ms: Window size in milliseconds
            
        Returns:
            Dict of class -> probability for all detected classes above threshold.
            Empty dict if no classes detected or feature extraction failed.
        """
        spectrogram = self._extract_spectrogram(audio, sr, onset_time, window_ms)
        
        if spectrogram is None:
            return {}
        
        return self.classify_spectrogram(spectrogram)
    
    def _extract_spectrograms_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        silence_gate: bool = True,
        label: str = "",
    ) -> tuple:
        """
        Extract mel-spectrograms for multiple onsets from a single audio source.

        Args:
            audio: Audio data (mono or stereo)
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds
            silence_gate: If True, skip onsets in near-silent sections
            label: Optional label for progress messages (e.g., "hybrid", "demucs")

        Returns:
            Tuple of (spectrograms, valid_indices, silence_skipped) where
            spectrograms is a list of (128, 128) float32 arrays and
            valid_indices maps each spectrogram back to its onset index.
        """
        # Handle stereo by converting to mono
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] == 2 else audio.mean(axis=1)

        # Resample to 22050 Hz to match training data
        if sr != 22050:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=22050)
            sr = 22050

        n_onsets = len(onset_times)
        prefix = f"[{label}] " if label else ""
        print(f"   {prefix}Extracting per-onset spectrograms (matching training pipeline)...")

        # Compute track-level energy for silence gating
        silence_threshold = 0.0
        if silence_gate:
            track_rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
            silence_threshold = track_rms * 0.02  # 2% of track RMS = noise floor
        silence_skipped = 0

        window_samples = int(window_ms * sr / 1000)

        spectrograms = []
        valid_indices = []

        for i, onset_time in enumerate(onset_times):
            if (i + 1) % 500 == 0 or i == 0:
                print(f"   {prefix}Processing onset {i + 1}/{n_onsets}...")

            # Asymmetric window (matching training: 1/4 before, full after)
            center = int(onset_time * sr)
            start = max(0, center - window_samples // 4)
            end = min(len(audio), center + window_samples)

            if end - start < 10:
                continue

            segment = audio[start:end]

            # Energy gating: skip onsets in very quiet sections (Demucs bleed artifacts)
            if silence_gate:
                segment_rms = np.sqrt(np.mean(segment.astype(np.float64) ** 2))
                if segment_rms < silence_threshold:
                    silence_skipped += 1
                    continue

            # Pad if needed (matching training)
            if len(segment) < window_samples:
                segment = np.pad(segment, (0, window_samples - len(segment)), mode='constant')

            # Power mel spectrogram + power_to_db (matching training)
            hop_length = max(1, len(segment) // 128)
            mel_spec = librosa.feature.melspectrogram(
                y=segment.astype(np.float32), sr=sr, n_mels=128,
                fmax=8000, hop_length=hop_length,
            )
            mel_db = librosa.power_to_db(mel_spec, ref=np.max)

            # Resize to 128 frames
            if mel_db.shape[1] != 128:
                if mel_db.shape[1] < 128:
                    pad_width = 128 - mel_db.shape[1]
                    mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
                else:
                    mel_db = mel_db[:, :128]

            # Normalize to [0, 1] (matching training data)
            mel_min, mel_max = mel_db.min(), mel_db.max()
            if mel_max - mel_min > 1e-8:
                mel_db = (mel_db - mel_min) / (mel_max - mel_min)
            else:
                mel_db = np.zeros_like(mel_db)

            spectrograms.append(mel_db.astype(np.float32))
            valid_indices.append(i)

        return spectrograms, valid_indices, silence_skipped

    def _run_batch_inference(
        self,
        spectrograms: List[np.ndarray],
        batch_size: int = 256,
    ) -> np.ndarray:
        """
        Run batch inference on pre-extracted spectrograms.

        Args:
            spectrograms: List of (128, 128) float32 spectrograms
            batch_size: Chunk size for GPU batching

        Returns:
            Array of shape (N, num_classes) with sigmoid probabilities
        """
        all_probs = []

        for batch_start in range(0, len(spectrograms), batch_size):
            batch_end = min(batch_start + batch_size, len(spectrograms))
            batch_specs = spectrograms[batch_start:batch_end]

            batch_np = np.stack(batch_specs, axis=0)
            batch_tensor = torch.from_numpy(batch_np).float()
            batch_tensor = batch_tensor.unsqueeze(1)  # (N, 1, 128, 128)
            batch_tensor = batch_tensor.to(self.device)

            with torch.inference_mode():
                logits = self.model(batch_tensor)
                probs = torch.sigmoid(logits)

            all_probs.append(probs.cpu().numpy())

        return np.concatenate(all_probs, axis=0)

    def classify_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
    ) -> List[Dict[str, float]]:
        """
        Classify multiple onsets in a single batch for efficiency.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds

        Returns:
            List of detection dicts, one per onset time.
            Failed extractions return empty dict.
        """
        if not onset_times:
            return []

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        logger.info(f"Classifying {n_onsets} onsets...")

        spectrograms, valid_indices, silence_skipped = self._extract_spectrograms_batch(
            audio, sr, onset_times, window_ms, silence_gate=True,
        )

        # Initialize results
        results: List[Dict[str, float]] = [{} for _ in onset_times]

        if not spectrograms:
            return results

        if silence_skipped > 0:
            print(f"   Skipped {silence_skipped} onsets in near-silent sections (Demucs bleed)")
        print(f"   Running batch inference on {len(spectrograms)} patches...")

        probs_np = self._run_batch_inference(spectrograms)

        # Apply thresholds and multi-label refinement, then map back to results
        refined_count = 0
        for i, valid_idx in enumerate(valid_indices):
            raw = self._apply_thresholds(probs_np[i])
            refined = self._refine_multilabel_detections(raw)
            if len(refined) < len(raw):
                refined_count += 1
            results[valid_idx] = refined

        if refined_count > 0:
            print(f"   Multi-label refinement: {refined_count} onsets had spurious co-detections removed")
        print(f"   Classification complete!")
        return results

    def classify_batch_ensemble(
        self,
        hybrid_audio: np.ndarray,
        demucs_audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        demucs_threshold_scale: float = 0.7,
        window_ms: float = 100.0,
        demucs_classifier: Optional["MultiLabelDrumClassifier"] = None,
    ) -> List[Dict[str, float]]:
        """
        Ensemble classification: body drums from primary model, cymbals from Demucs model.

        Runs inference on both audio sources and merges detections per-onset:
        - Body drums (kick, snare, hihat_*, tom, cross_stick, ride_*):
          classified using ``self`` (the primary/clean model)
          with threshold_scale=1.0 (no domain gap)
        - Cymbals (crash, china, splash):
          classified using ``demucs_classifier``
          (if provided) or ``self`` as fallback, with demucs_threshold_scale

        Both audio sources are typically Demucs-separated drum stems, which
        are closer to the clean training domain than full-mix audio. When a
        separate ``demucs_classifier`` is provided (dual-model mode), each
        model uses its own thresholds — the primary model's thresholds for
        body drums and the Demucs model's thresholds for cymbals.

        Args:
            hybrid_audio: Original full-mix audio data
            demucs_audio: Demucs-separated drum stem audio data
            sr: Sample rate (same for both sources)
            onset_times: List of onset times in seconds
            demucs_threshold_scale: Threshold scale for Demucs cymbal classes
            window_ms: Window size in milliseconds
            demucs_classifier: Optional second classifier for the Demucs path.
                If provided, uses this model + its thresholds for cymbal classes.
                If None, uses self for both paths (single-model ensemble).

        Returns:
            List of detection dicts, one per onset time.
        """
        if not onset_times:
            return []

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        demucs_cls = demucs_classifier or self
        dual_model = demucs_classifier is not None
        mode_str = "dual-model" if dual_model else "single-model"
        logger.info(f"Ensemble classifying {n_onsets} onsets ({mode_str}, hybrid + demucs)...")

        # Extract spectrograms from both audio sources
        # Hybrid: no silence gating (full-mix audio doesn't have Demucs bleed)
        hybrid_specs, hybrid_valid, _ = self._extract_spectrograms_batch(
            hybrid_audio, sr, onset_times, window_ms,
            silence_gate=False, label="hybrid",
        )
        # Demucs: with silence gating (Demucs bleed in quiet sections)
        demucs_specs, demucs_valid, demucs_silence_skipped = demucs_cls._extract_spectrograms_batch(
            demucs_audio, sr, onset_times, window_ms,
            silence_gate=True, label="demucs",
        )

        if demucs_silence_skipped > 0:
            print(f"   Skipped {demucs_silence_skipped} demucs onsets in near-silent sections")

        # Run inference on both sets
        hybrid_probs = None
        demucs_probs = None

        if hybrid_specs:
            print(f"   Running hybrid inference on {len(hybrid_specs)} patches...")
            hybrid_probs = self._run_batch_inference(hybrid_specs)

        if demucs_specs:
            print(f"   Running demucs inference on {len(demucs_specs)} patches"
                  f"{' (separate model)' if dual_model else ''}...")
            demucs_probs = demucs_cls._run_batch_inference(demucs_specs)

        # Build lookup: onset_index -> prob array for each source
        hybrid_prob_map = {}
        if hybrid_probs is not None:
            for i, valid_idx in enumerate(hybrid_valid):
                hybrid_prob_map[valid_idx] = hybrid_probs[i]

        demucs_prob_map = {}
        if demucs_probs is not None:
            for i, valid_idx in enumerate(demucs_valid):
                demucs_prob_map[valid_idx] = demucs_probs[i]

        # Merge detections per-onset
        results: List[Dict[str, float]] = [{} for _ in onset_times]
        refined_count = 0
        cymbal_hihat_suppressed = 0

        for onset_idx in range(n_onsets):
            merged = {}

            # Body drums from hybrid (threshold_scale=1.0)
            if onset_idx in hybrid_prob_map:
                probs = hybrid_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = self.idx_to_class[cls_idx]
                    if class_name not in self._ENSEMBLE_HYBRID_CLASSES:
                        continue
                    base_thresh = self.per_class_thresholds.get(class_name, self.threshold)
                    # No domain gap scaling for hybrid (1.0)
                    if prob >= base_thresh:
                        merged[class_name] = float(prob)

            # Cymbals from Demucs (with domain gap scaling)
            if onset_idx in demucs_prob_map:
                probs = demucs_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = self.idx_to_class[cls_idx]
                    if class_name not in self._ENSEMBLE_DEMUCS_CLASSES:
                        continue
                    # Use demucs classifier's thresholds in dual-model mode
                    base_thresh = demucs_cls.per_class_thresholds.get(
                        class_name, demucs_cls.threshold
                    )
                    if demucs_threshold_scale < 1.0:
                        # Cymbal classes are all Tier 3 (sensitive)
                        thresh = base_thresh * (demucs_threshold_scale ** 0.75)
                    else:
                        thresh = base_thresh
                    if prob >= thresh:
                        merged[class_name] = float(prob)

            # --- Ensemble-specific conflict resolution ---
            # When the Demucs model detects china/crash, the clean model often
            # false-fires hihat (similar spectral profile). Suppress hihat
            # when a confident cymbal detection exists at the same onset.
            _CONFLICTING_CYMBALS = {'china', 'crash'}
            if merged:
                detected_cymbals = {
                    cls: p for cls, p in merged.items()
                    if cls in _CONFLICTING_CYMBALS
                }
                if detected_cymbals:
                    # China/crash detected — hihat is very likely a false positive
                    # from spectral bleeding. Remove hihat unless it's much more
                    # confident than the cymbal (rare but possible during transitions).
                    cymbal_peak = max(detected_cymbals.values())
                    for hh_cls in ('hihat_closed', 'hihat_open'):
                        if hh_cls in merged:
                            # Only keep hihat if it's substantially more confident
                            # than the cymbal (>2x), indicating genuine co-occurrence
                            if merged[hh_cls] < cymbal_peak * 2.0:
                                del merged[hh_cls]
                                cymbal_hihat_suppressed += 1

            # Apply musical refinement on merged detections
            if merged:
                refined = self._refine_multilabel_detections(merged)
                if len(refined) < len(merged):
                    refined_count += 1
                results[onset_idx] = refined

        if refined_count > 0:
            print(f"   Ensemble refinement: {refined_count} onsets had spurious co-detections removed")
        if cymbal_hihat_suppressed > 0:
            print(f"   Cymbal-hihat conflict: suppressed {cymbal_hihat_suppressed} false hihat detections at china/crash onsets")

        # Summary stats
        total_detections = sum(len(d) for d in results)
        body_count = sum(
            1 for d in results for cls in d if cls in self._ENSEMBLE_HYBRID_CLASSES
        )
        cymbal_count = sum(
            1 for d in results for cls in d if cls in self._ENSEMBLE_DEMUCS_CLASSES
        )
        print(f"   Ensemble classification complete ({mode_str})! "
              f"{total_detections} total detections "
              f"({body_count} body from hybrid, {cymbal_count} cymbals from demucs)")
        return results

    def classify_batch_ensemble_with_adaptive_thresholds(
        self,
        hybrid_audio: np.ndarray,
        demucs_audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        demucs_threshold_scale: float = 0.7,
        window_ms: float = 100.0,
        demucs_classifier: Optional["MultiLabelDrumClassifier"] = None,
        method: str = "otsu",
        min_threshold: float = 0.15,
        max_threshold: float = 0.85,
        adaptation_range: float = 0.15,
    ) -> Tuple[List[Dict[str, float]], Dict[str, Dict[str, float]]]:
        """
        Ensemble classification with per-song adaptive threshold calibration.

        Two-pass approach:
        1. Extract spectrograms and run inference for both models (same as
           classify_batch_ensemble).
        2. Analyze the per-class probability distributions from each model
           to compute song-adapted thresholds that refine the base thresholds.
        3. Apply adapted thresholds during the ensemble merge.

        The adaptation is bounded: thresholds can only shift by
        ±adaptation_range from their base values, preventing catastrophic
        drift on unusual songs.

        Args:
            hybrid_audio: Primary audio (Demucs-separated) for body drums
            demucs_audio: Secondary audio (Demucs-separated) for cymbals
            sr: Sample rate
            onset_times: List of onset times in seconds
            demucs_threshold_scale: Threshold scale for Demucs cymbal classes
            window_ms: Window size in milliseconds
            demucs_classifier: Optional second classifier for cymbal path.
            method: Adaptive threshold method ("otsu", "knee", "percentile")
            min_threshold: Absolute minimum threshold
            max_threshold: Absolute maximum threshold
            adaptation_range: Max fraction to adjust base threshold (e.g. 0.15
                means thresholds can shift ±15% of their base value).

        Returns:
            Tuple of (detection_results, adapted_thresholds_info)
            where adapted_thresholds_info has keys "hybrid" and "demucs",
            each mapping class_name -> adapted threshold.
        """
        if not onset_times:
            return [], {"hybrid": {}, "demucs": {}}

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times], {"hybrid": {}, "demucs": {}}

        n_onsets = len(onset_times)
        demucs_cls = demucs_classifier or self
        dual_model = demucs_classifier is not None
        mode_str = "dual-model" if dual_model else "single-model"
        logger.info(
            f"Ensemble + adaptive classifying {n_onsets} onsets ({mode_str})..."
        )

        print(f"\n=== ADAPTIVE ENSEMBLE CLASSIFICATION ===")
        print(f"   Pass 1: Collecting raw probabilities from both models...")

        # ── PASS 1: Extract spectrograms & run inference (identical to
        #    classify_batch_ensemble) ──────────────────────────────────
        hybrid_specs, hybrid_valid, _ = self._extract_spectrograms_batch(
            hybrid_audio, sr, onset_times, window_ms,
            silence_gate=False, label="hybrid",
        )
        demucs_specs, demucs_valid, demucs_silence_skipped = (
            demucs_cls._extract_spectrograms_batch(
                demucs_audio, sr, onset_times, window_ms,
                silence_gate=True, label="demucs",
            )
        )

        if demucs_silence_skipped > 0:
            print(f"   Skipped {demucs_silence_skipped} demucs onsets in near-silent sections")

        hybrid_probs = None
        demucs_probs = None

        if hybrid_specs:
            print(f"   Running hybrid inference on {len(hybrid_specs)} patches...")
            hybrid_probs = self._run_batch_inference(hybrid_specs)
        if demucs_specs:
            print(
                f"   Running demucs inference on {len(demucs_specs)} patches"
                f"{' (separate model)' if dual_model else ''}..."
            )
            demucs_probs = demucs_cls._run_batch_inference(demucs_specs)

        # Build probability maps
        hybrid_prob_map: Dict[int, np.ndarray] = {}
        if hybrid_probs is not None:
            for i, valid_idx in enumerate(hybrid_valid):
                hybrid_prob_map[valid_idx] = hybrid_probs[i]

        demucs_prob_map: Dict[int, np.ndarray] = {}
        if demucs_probs is not None:
            for i, valid_idx in enumerate(demucs_valid):
                demucs_prob_map[valid_idx] = demucs_probs[i]

        # ── PASS 2: Analyze probability distributions and adapt
        #    thresholds ───────────────────────────────────────────────
        print(f"\n   Pass 2: Adapting thresholds from probability distributions (method={method})...")

        # Collect per-class probability distributions for each model domain
        hybrid_class_probs: Dict[str, List[float]] = {
            cls: [] for cls in self._ENSEMBLE_HYBRID_CLASSES
        }
        demucs_class_probs: Dict[str, List[float]] = {
            cls: [] for cls in self._ENSEMBLE_DEMUCS_CLASSES
        }

        for onset_idx in range(n_onsets):
            if onset_idx in hybrid_prob_map:
                probs = hybrid_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = self.idx_to_class[cls_idx]
                    if class_name in self._ENSEMBLE_HYBRID_CLASSES:
                        hybrid_class_probs[class_name].append(float(prob))

            if onset_idx in demucs_prob_map:
                probs = demucs_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = demucs_cls.idx_to_class[cls_idx]
                    if class_name in self._ENSEMBLE_DEMUCS_CLASSES:
                        demucs_class_probs[class_name].append(float(prob))

        # Compute adapted thresholds for hybrid (body drum) classes
        adapted_hybrid: Dict[str, float] = {}
        print(f"\n   --- Body drums (clean model) ---")
        print(f"   {'Class':<15} {'Base':>7} {'Adapted':>9} {'Delta':>7} {'Detect':>7}")
        print(f"   {'-'*50}")

        for class_name in sorted(self._ENSEMBLE_HYBRID_CLASSES):
            base_thresh = self.per_class_thresholds.get(class_name, self.threshold)
            probs_list = hybrid_class_probs[class_name]

            if not probs_list or max(probs_list) < min_threshold:
                adapted_hybrid[class_name] = base_thresh
                print(f"   {class_name:<15} {base_thresh:>7.3f} {base_thresh:>9.3f} {'N/A':>7} {'0':>7}")
                continue

            probs_arr = np.array(probs_list)
            raw_adapted = _compute_adaptive_threshold(
                probs_arr, method, min_threshold, max_threshold
            )

            # Clamp adaptation to ± adaptation_range of base
            delta_max = base_thresh * adaptation_range
            adapted = np.clip(raw_adapted, base_thresh - delta_max, base_thresh + delta_max)
            adapted = max(min_threshold, min(max_threshold, adapted))
            adapted_hybrid[class_name] = float(adapted)

            n_detect = int((probs_arr >= adapted).sum())
            delta = adapted - base_thresh
            print(f"   {class_name:<15} {base_thresh:>7.3f} {adapted:>9.3f} {delta:>+7.3f} {n_detect:>7d}")

        # Compute adapted thresholds for demucs (cymbal) classes
        adapted_demucs: Dict[str, float] = {}
        print(f"\n   --- Cymbals (Demucs model) ---")
        print(f"   {'Class':<15} {'Base':>7} {'Adapted':>9} {'Delta':>7} {'Detect':>7}")
        print(f"   {'-'*50}")

        for class_name in sorted(self._ENSEMBLE_DEMUCS_CLASSES):
            base_thresh = demucs_cls.per_class_thresholds.get(
                class_name, demucs_cls.threshold
            )
            probs_list = demucs_class_probs[class_name]

            if not probs_list or max(probs_list) < min_threshold:
                adapted_demucs[class_name] = base_thresh
                print(f"   {class_name:<15} {base_thresh:>7.3f} {base_thresh:>9.3f} {'N/A':>7} {'0':>7}")
                continue

            probs_arr = np.array(probs_list)
            raw_adapted = _compute_adaptive_threshold(
                probs_arr, method, min_threshold, max_threshold
            )

            delta_max = base_thresh * adaptation_range
            adapted = np.clip(raw_adapted, base_thresh - delta_max, base_thresh + delta_max)
            adapted = max(min_threshold, min(max_threshold, adapted))
            adapted_demucs[class_name] = float(adapted)

            n_detect = int((probs_arr >= adapted).sum())
            delta = adapted - base_thresh
            print(f"   {class_name:<15} {base_thresh:>7.3f} {adapted:>9.3f} {delta:>+7.3f} {n_detect:>7d}")

        # ── PASS 3: Apply adapted thresholds during ensemble merge ──
        print(f"\n   Pass 3: Applying adapted thresholds...")

        results: List[Dict[str, float]] = [{} for _ in onset_times]
        refined_count = 0
        cymbal_hihat_suppressed = 0

        for onset_idx in range(n_onsets):
            merged: Dict[str, float] = {}

            # Body drums from hybrid with adapted thresholds
            if onset_idx in hybrid_prob_map:
                probs = hybrid_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = self.idx_to_class[cls_idx]
                    if class_name not in self._ENSEMBLE_HYBRID_CLASSES:
                        continue
                    thresh = adapted_hybrid.get(
                        class_name,
                        self.per_class_thresholds.get(class_name, self.threshold),
                    )
                    if prob >= thresh:
                        merged[class_name] = float(prob)

            # Cymbals from Demucs with adapted thresholds
            if onset_idx in demucs_prob_map:
                probs = demucs_prob_map[onset_idx]
                for cls_idx, prob in enumerate(probs):
                    class_name = demucs_cls.idx_to_class[cls_idx]
                    if class_name not in self._ENSEMBLE_DEMUCS_CLASSES:
                        continue
                    thresh = adapted_demucs.get(
                        class_name,
                        demucs_cls.per_class_thresholds.get(
                            class_name, demucs_cls.threshold
                        ),
                    )
                    if prob >= thresh:
                        merged[class_name] = float(prob)

            # China/hihat conflict resolution (same as classify_batch_ensemble)
            _CONFLICTING_CYMBALS = {'china', 'crash'}
            if merged:
                detected_cymbals = {
                    cls: p for cls, p in merged.items()
                    if cls in _CONFLICTING_CYMBALS
                }
                if detected_cymbals:
                    cymbal_peak = max(detected_cymbals.values())
                    for hh_cls in ('hihat_closed', 'hihat_open'):
                        if hh_cls in merged:
                            if merged[hh_cls] < cymbal_peak * 2.0:
                                del merged[hh_cls]
                                cymbal_hihat_suppressed += 1

            # Musical refinement
            if merged:
                refined = self._refine_multilabel_detections(merged)
                if len(refined) < len(merged):
                    refined_count += 1
                results[onset_idx] = refined

        if refined_count > 0:
            print(f"   Ensemble refinement: {refined_count} onsets had spurious co-detections removed")
        if cymbal_hihat_suppressed > 0:
            print(f"   Cymbal-hihat conflict: suppressed {cymbal_hihat_suppressed} false hihat detections")

        # Summary stats
        total_detections = sum(len(d) for d in results)
        body_count = sum(
            1 for d in results for cls in d if cls in self._ENSEMBLE_HYBRID_CLASSES
        )
        cymbal_count = sum(
            1 for d in results for cls in d if cls in self._ENSEMBLE_DEMUCS_CLASSES
        )
        print(f"\n   Adaptive ensemble complete ({mode_str})! "
              f"{total_detections} total detections "
              f"({body_count} body, {cymbal_count} cymbals)")

        adapted_info = {"hybrid": adapted_hybrid, "demucs": adapted_demucs}
        return results, adapted_info

    def classify_batch_with_adaptive_thresholds(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        method: str = "otsu",
        min_threshold: float = 0.15,
        max_threshold: float = 0.85,
    ) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
        """
        Classify onsets using adaptive per-song thresholds.
        
        This performs a two-pass classification:
        1. First pass: Get raw probabilities for all onsets
        2. Compute optimal thresholds based on probability distributions
        3. Second pass: Apply adaptive thresholds
        
        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times
            window_ms: Window size in ms
            method: Threshold estimation method ("otsu", "percentile", "knee")
            min_threshold: Minimum allowed threshold
            max_threshold: Maximum allowed threshold
            
        Returns:
            Tuple of (detection_results, adaptive_thresholds_dict)
        """
        if not onset_times:
            return [], {}
        
        print(f"\n=== ADAPTIVE THRESHOLD CLASSIFICATION ===")
        print(f"   Computing raw probabilities for {len(onset_times)} onsets...")
        
        # Get raw probabilities (bypass thresholding)
        probs_matrix = self._get_raw_probabilities_batch(audio, sr, onset_times, window_ms, show_progress=True)
        
        if probs_matrix is None or len(probs_matrix) == 0:
            return [{} for _ in onset_times], {}
        
        # Compute adaptive thresholds
        adaptive_thresholds = estimate_adaptive_thresholds(
            probs_matrix,
            self.components,
            method=method,
            min_threshold=min_threshold,
            max_threshold=max_threshold,
        )
        
        # Apply adaptive thresholds
        print(f"\n   Applying adaptive thresholds...")
        results: List[Dict[str, float]] = []
        
        for probs in probs_matrix:
            detections = {}
            for idx, prob in enumerate(probs):
                class_name = self.idx_to_class[idx]
                threshold = adaptive_thresholds.get(class_name, self.threshold)
                if prob >= threshold:
                    detections[class_name] = float(prob)
            results.append(self._refine_multilabel_detections(detections))
        
        # Summary stats
        total_detections = sum(len(d) for d in results)
        class_counts = {}
        for det in results:
            for cls in det:
                class_counts[cls] = class_counts.get(cls, 0) + 1
        
        print(f"\n   === ADAPTIVE THRESHOLD SUMMARY ===")
        print(f"   Total detections: {total_detections}")
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
            print(f"     {cls}: {count}")
        
        return results, adaptive_thresholds
    
    @staticmethod
    def _print_progress_bar(current: int, total: int, prefix: str = "", width: int = 30):
        """Print a simple inline progress bar."""
        import sys
        fraction = current / max(total, 1)
        filled = int(width * fraction)
        bar = '#' * filled + '-' * (width - filled)
        pct = fraction * 100
        print(f"\r   {prefix} [{bar}] {pct:5.1f}% ({current}/{total})", end="", flush=True)
        if current >= total:
            print()  # newline when done

    # =========================================================================
    # TEST-TIME AUGMENTATION (TTA)
    # =========================================================================

    @staticmethod
    def _augment_spectrogram(spec: np.ndarray, rng: np.random.RandomState) -> np.ndarray:
        """
        Apply random augmentations to a spectrogram for TTA.

        Augmentations (designed to be inference-safe — no destructive transforms):
        - Time shift: roll along time axis by ±5 frames
        - Gain perturbation: multiply by random scalar in [0.85, 1.15]
        - Frequency masking: zero out 1-8 random mel bands
        - Time masking: zero out 1-5 random time frames

        Args:
            spec: (128, 128) float32 spectrogram
            rng: RandomState for reproducibility

        Returns:
            Augmented spectrogram copy
        """
        aug = spec.copy()

        # Time shift (±5 frames)
        shift = rng.randint(-5, 6)
        if shift != 0:
            aug = np.roll(aug, shift, axis=1)
            if shift > 0:
                aug[:, :shift] = 0
            else:
                aug[:, shift:] = 0

        # Gain perturbation
        gain = rng.uniform(0.85, 1.15)
        aug = np.clip(aug * gain, 0.0, 1.0)

        # Frequency masking (zero out 1-8 mel bands)
        n_mask = rng.randint(1, 9)
        for _ in range(n_mask):
            band = rng.randint(0, 128)
            width = rng.randint(1, 4)
            start = max(0, band - width // 2)
            end = min(128, band + width // 2 + 1)
            aug[start:end, :] = 0

        # Time masking (zero out 1-5 time frames)
        n_time_mask = rng.randint(1, 6)
        for _ in range(n_time_mask):
            frame = rng.randint(0, 128)
            width = rng.randint(1, 4)
            start = max(0, frame - width // 2)
            end = min(128, frame + width // 2 + 1)
            aug[:, start:end] = 0

        return aug

    def _run_batch_inference_tta(
        self,
        spectrograms: List[np.ndarray],
        n_augmentations: int = 5,
        batch_size: int = 256,
        seed: int = 42,
    ) -> np.ndarray:
        """
        Run TTA batch inference: for each spectrogram, create N augmented
        versions, run inference on all (original + augmented), and average
        the probabilities.

        Args:
            spectrograms: List of (128, 128) float32 spectrograms
            n_augmentations: Number of augmented copies per spectrogram
            batch_size: GPU batch size
            seed: Random seed for reproducibility

        Returns:
            Array of shape (N, num_classes) with averaged sigmoid probabilities
        """
        rng = np.random.RandomState(seed)
        n_orig = len(spectrograms)
        total_variants = n_orig * (1 + n_augmentations)
        print(f"   TTA: {n_orig} spectrograms × {1 + n_augmentations} variants = {total_variants} inferences")

        # Build expanded batch: [orig_0, aug_0_1, ..., aug_0_N, orig_1, aug_1_1, ...]
        expanded_specs = []
        for spec in spectrograms:
            expanded_specs.append(spec)  # Original
            for _ in range(n_augmentations):
                expanded_specs.append(self._augment_spectrogram(spec, rng))

        # Run inference on all variants
        all_probs = self._run_batch_inference(expanded_specs, batch_size)

        # Average probabilities per original spectrogram
        stride = 1 + n_augmentations
        result = np.zeros((n_orig, all_probs.shape[1]), dtype=np.float32)
        for i in range(n_orig):
            start = i * stride
            end = start + stride
            result[i] = all_probs[start:end].mean(axis=0)

        return result

    def classify_batch_tta(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        n_augmentations: int = 5,
    ) -> List[Dict[str, float]]:
        """
        Classify onsets using Test-Time Augmentation for more robust predictions.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Window size in milliseconds
            n_augmentations: Number of augmented copies per onset

        Returns:
            List of detection dicts, one per onset time.
        """
        if not onset_times:
            return []

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        logger.info(f"TTA classifying {n_onsets} onsets with {n_augmentations} augmentations...")

        spectrograms, valid_indices, silence_skipped = self._extract_spectrograms_batch(
            audio, sr, onset_times, window_ms, silence_gate=True,
        )

        results: List[Dict[str, float]] = [{} for _ in onset_times]
        if not spectrograms:
            return results

        if silence_skipped > 0:
            print(f"   Skipped {silence_skipped} onsets in near-silent sections")
        print(f"   Running TTA inference on {len(spectrograms)} patches ({n_augmentations} augmentations each)...")

        probs_np = self._run_batch_inference_tta(spectrograms, n_augmentations)

        refined_count = 0
        for i, valid_idx in enumerate(valid_indices):
            raw = self._apply_thresholds(probs_np[i])
            refined = self._refine_multilabel_detections(raw)
            if len(refined) < len(raw):
                refined_count += 1
            results[valid_idx] = refined

        if refined_count > 0:
            print(f"   Multi-label refinement: {refined_count} onsets had spurious co-detections removed")
        print(f"   TTA classification complete!")
        return results

    # =========================================================================
    # MULTI-WINDOW INFERENCE
    # =========================================================================

    def classify_batch_multiwindow(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_sizes_ms: Optional[List[float]] = None,
    ) -> List[Dict[str, float]]:
        """
        Classify onsets using multiple window sizes and average predictions.

        Different window sizes capture different temporal contexts:
        - Smaller windows: better for sharp transients (kick, snare)
        - Larger windows: better for resonant/sustained sounds (crash, ride, open hi-hat)

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_sizes_ms: List of window sizes (default: [80, 100, 120])

        Returns:
            List of detection dicts, one per onset time.
        """
        if not onset_times:
            return []

        if window_sizes_ms is None:
            window_sizes_ms = [80.0, 100.0, 120.0]

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        n_windows = len(window_sizes_ms)
        logger.info(f"Multi-window classifying {n_onsets} onsets with {n_windows} window sizes...")
        print(f"   Multi-window inference: {window_sizes_ms} ms")

        # Collect raw probabilities from each window size
        all_probs = []
        all_valid_sets = []

        for w_ms in window_sizes_ms:
            spectrograms, valid_indices, _ = self._extract_spectrograms_batch(
                audio, sr, onset_times, w_ms, silence_gate=True,
                label=f"{w_ms:.0f}ms",
            )
            valid_set = set(valid_indices)
            all_valid_sets.append(valid_set)

            if spectrograms:
                probs_np = self._run_batch_inference(spectrograms)
                # Map back to full array
                full_probs = np.zeros((n_onsets, probs_np.shape[1]), dtype=np.float32)
                for i, valid_idx in enumerate(valid_indices):
                    full_probs[valid_idx] = probs_np[i]
                all_probs.append(full_probs)
            else:
                num_classes = len(self.components)
                all_probs.append(np.zeros((n_onsets, num_classes), dtype=np.float32))

        # Average probabilities across window sizes (only for onsets valid in ALL windows)
        common_valid = set(range(n_onsets))
        for vs in all_valid_sets:
            common_valid &= vs

        stacked = np.stack(all_probs, axis=0)  # (n_windows, n_onsets, n_classes)
        avg_probs = stacked.mean(axis=0)  # (n_onsets, n_classes)

        # Apply thresholds
        results: List[Dict[str, float]] = [{} for _ in onset_times]
        refined_count = 0
        for idx in common_valid:
            raw = self._apply_thresholds(avg_probs[idx])
            refined = self._refine_multilabel_detections(raw)
            if len(refined) < len(raw):
                refined_count += 1
            results[idx] = refined

        if refined_count > 0:
            print(f"   Multi-label refinement: {refined_count} onsets had spurious co-detections removed")
        print(f"   Multi-window classification complete! ({len(common_valid)} valid onsets)")
        return results

    # =========================================================================
    # CHECKPOINT ENSEMBLE
    # =========================================================================

    def classify_batch_checkpoint_ensemble(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        checkpoint_paths: List[str],
        window_ms: float = 100.0,
    ) -> List[Dict[str, float]]:
        """
        Ensemble predictions from multiple model checkpoints.

        Loads each checkpoint, runs inference, and averages probabilities.
        Different training snapshots capture different aspects of the data.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            checkpoint_paths: List of checkpoint file paths to ensemble
            window_ms: Window size in milliseconds

        Returns:
            List of detection dicts, one per onset time.
        """
        if not onset_times:
            return []

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        n_checkpoints = len(checkpoint_paths)
        logger.info(f"Checkpoint ensemble: {n_onsets} onsets × {n_checkpoints} checkpoints...")
        print(f"   Checkpoint ensemble with {n_checkpoints} models")

        # Extract spectrograms once (shared across all checkpoints)
        spectrograms, valid_indices, silence_skipped = self._extract_spectrograms_batch(
            audio, sr, onset_times, window_ms, silence_gate=True,
        )

        results: List[Dict[str, float]] = [{} for _ in onset_times]
        if not spectrograms:
            return results

        if silence_skipped > 0:
            print(f"   Skipped {silence_skipped} onsets in near-silent sections")

        # Run inference with each checkpoint and collect probabilities
        all_probs = []
        original_model_state = {k: v.clone() for k, v in self.model.state_dict().items()}

        try:
            for ckpt_idx, ckpt_path in enumerate(checkpoint_paths):
                print(f"   [{ckpt_idx + 1}/{n_checkpoints}] Loading checkpoint: {os.path.basename(ckpt_path)}")
                ckpt_model = load_model_checkpoint(
                    ckpt_path, device=str(self.device),
                    num_classes=len(self.components),
                )
                # Temporarily swap model
                original_model = self.model
                self.model = ckpt_model
                probs_np = self._run_batch_inference(spectrograms)
                self.model = original_model
                all_probs.append(probs_np)
        finally:
            # Restore original model weights
            self.model.load_state_dict(original_model_state)

        # Average probabilities across checkpoints
        stacked = np.stack(all_probs, axis=0)
        avg_probs = stacked.mean(axis=0)

        # Apply thresholds
        refined_count = 0
        for i, valid_idx in enumerate(valid_indices):
            raw = self._apply_thresholds(avg_probs[i])
            refined = self._refine_multilabel_detections(raw)
            if len(refined) < len(raw):
                refined_count += 1
            results[valid_idx] = refined

        if refined_count > 0:
            print(f"   Multi-label refinement: {refined_count} onsets had spurious co-detections removed")
        print(f"   Checkpoint ensemble complete! ({n_checkpoints} models averaged)")
        return results

    # =========================================================================
    # MULTI-PASS ONSET REFINEMENT
    # =========================================================================

    def classify_batch_multipass(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        uncertainty_range: Tuple[float, float] = (0.3, 0.6),
        wider_window_ms: float = 150.0,
        use_tta_for_uncertain: bool = True,
        tta_augmentations: int = 7,
    ) -> List[Dict[str, float]]:
        """
        Multi-pass classification with refinement for uncertain onsets.

        Pass 1: Classify all onsets normally.
        Pass 2: Identify uncertain onsets (max probability in uncertainty_range).
        Pass 3: Re-classify uncertain onsets with wider window + optional TTA.

        Args:
            audio: Audio data
            sr: Sample rate
            onset_times: List of onset times in seconds
            window_ms: Normal window size in milliseconds
            uncertainty_range: (low, high) range of max probability that triggers refinement
            wider_window_ms: Window size for re-classification of uncertain onsets
            use_tta_for_uncertain: Whether to use TTA for uncertain onset re-classification
            tta_augmentations: Number of TTA augmentations for uncertain onsets

        Returns:
            List of detection dicts, one per onset time.
        """
        if not onset_times:
            return []

        if not HAS_LIBROSA:
            logger.error("librosa is required for feature extraction")
            return [{} for _ in onset_times]

        n_onsets = len(onset_times)
        logger.info(f"Multi-pass classifying {n_onsets} onsets...")

        # === PASS 1: Normal classification ===
        print(f"   Pass 1: Initial classification ({n_onsets} onsets)...")
        spectrograms, valid_indices, silence_skipped = self._extract_spectrograms_batch(
            audio, sr, onset_times, window_ms, silence_gate=True,
        )

        results: List[Dict[str, float]] = [{} for _ in onset_times]
        if not spectrograms:
            return results

        probs_np = self._run_batch_inference(spectrograms)

        # Track raw probabilities for uncertainty detection
        raw_max_probs = {}  # onset_index -> max probability

        for i, valid_idx in enumerate(valid_indices):
            raw = self._apply_thresholds(probs_np[i])
            refined = self._refine_multilabel_detections(raw)
            results[valid_idx] = refined
            raw_max_probs[valid_idx] = float(probs_np[i].max())

        # === PASS 2: Identify uncertain onsets ===
        uncertain_indices = []
        low, high = uncertainty_range
        for idx, max_prob in raw_max_probs.items():
            if low <= max_prob <= high:
                uncertain_indices.append(idx)

        if not uncertain_indices:
            print(f"   No uncertain onsets found (range {low:.2f}-{high:.2f}) — skipping pass 2")
            print(f"   Multi-pass classification complete!")
            return results

        uncertain_times = [onset_times[i] for i in uncertain_indices]
        print(f"   Pass 2: Found {len(uncertain_indices)} uncertain onsets "
              f"(max prob in {low:.2f}-{high:.2f}), re-classifying with {wider_window_ms}ms window...")

        # === PASS 3: Re-classify uncertain onsets with wider window ===
        if use_tta_for_uncertain:
            # Use TTA for uncertain onsets
            specs2, valid2, _ = self._extract_spectrograms_batch(
                audio, sr, uncertain_times, wider_window_ms, silence_gate=False,
            )
            if specs2:
                probs2 = self._run_batch_inference_tta(specs2, tta_augmentations)
                for i, v2 in enumerate(valid2):
                    original_idx = uncertain_indices[v2]
                    raw = self._apply_thresholds(probs2[i])
                    refined = self._refine_multilabel_detections(raw)
                    results[original_idx] = refined
        else:
            # Just wider window, no TTA
            specs2, valid2, _ = self._extract_spectrograms_batch(
                audio, sr, uncertain_times, wider_window_ms, silence_gate=False,
            )
            if specs2:
                probs2 = self._run_batch_inference(specs2)
                for i, v2 in enumerate(valid2):
                    original_idx = uncertain_indices[v2]
                    raw = self._apply_thresholds(probs2[i])
                    refined = self._refine_multilabel_detections(raw)
                    results[original_idx] = refined

        refined_in_pass2 = len(uncertain_indices)
        print(f"   Multi-pass classification complete! ({refined_in_pass2} onsets refined)")
        return results

    def _get_raw_probabilities_batch(
        self,
        audio: np.ndarray,
        sr: int,
        onset_times: List[float],
        window_ms: float = 100.0,
        show_progress: bool = False,
    ) -> Optional[np.ndarray]:
        """
        Get raw sigmoid probabilities for all onsets without applying thresholds.
        
        Returns:
            Array of shape (n_onsets, n_classes) or None
        """
        if not HAS_LIBROSA:
            return None
        
        # Handle stereo
        if audio.ndim > 1:
            audio = audio.mean(axis=0) if audio.shape[0] == 2 else audio.mean(axis=1)
        
        # Resample to 22050 Hz to match training data
        if sr != 22050:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=22050)
            sr = 22050
        
        # Extract per-onset spectrograms matching training exactly
        # (same as classify_batch — see comments there for rationale)
        if show_progress:
            print(f"   [1/2] Extracting {len(onset_times)} onset spectrograms...")
        window_samples = int(window_ms * sr / 1000)
        spectrograms = []
        
        # Energy gating for silence (same as classify_batch)
        track_rms = np.sqrt(np.mean(audio.astype(np.float64) ** 2))
        silence_threshold = track_rms * 0.02
        
        n_onsets = len(onset_times)
        for i, onset_time in enumerate(onset_times):
            if show_progress and (i % 200 == 0 or i == n_onsets - 1):
                self._print_progress_bar(i + 1, n_onsets, prefix="Spectrograms")
            
            # Asymmetric window (matching training: 1/4 before, full after)
            center = int(onset_time * sr)
            start = max(0, center - window_samples // 4)
            end = min(len(audio), center + window_samples)
            
            if end - start < 10:
                continue
            
            segment = audio[start:end]
            
            # Energy gating: skip near-silent segments
            segment_rms = np.sqrt(np.mean(segment.astype(np.float64) ** 2))
            if segment_rms < silence_threshold:
                continue
            
            # Pad if needed
            if len(segment) < window_samples:
                segment = np.pad(segment, (0, window_samples - len(segment)), mode='constant')
            
            # Power mel spectrogram + power_to_db (matching training)
            hop_length = max(1, len(segment) // 128)
            mel_spec = librosa.feature.melspectrogram(
                y=segment.astype(np.float32), sr=sr, n_mels=128,
                fmax=8000, hop_length=hop_length,
            )
            mel_db = librosa.power_to_db(mel_spec, ref=np.max)
            
            # Resize to 128 frames
            if mel_db.shape[1] != 128:
                if mel_db.shape[1] < 128:
                    pad_width = 128 - mel_db.shape[1]
                    mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
                else:
                    mel_db = mel_db[:, :128]
            
            # Normalize to [0, 1] (matching training data)
            mel_min, mel_max = mel_db.min(), mel_db.max()
            if mel_max - mel_min > 1e-8:
                mel_db = (mel_db - mel_min) / (mel_max - mel_min)
            else:
                mel_db = np.zeros_like(mel_db)
            
            spectrograms.append(mel_db.astype(np.float32))
        
        if not spectrograms:
            return None
        
        # Batch inference with progress
        if show_progress:
            print(f"   [2/2] Running model inference on {len(spectrograms)} patches...")
        
        batch_size = 256
        all_probs = []
        total_batches = (len(spectrograms) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, len(spectrograms))
            batch_specs = spectrograms[batch_start:batch_end]
            
            batch_np = np.stack(batch_specs, axis=0)
            batch_tensor = torch.from_numpy(batch_np).float().unsqueeze(1).to(self.device)
            
            with torch.inference_mode():
                logits = self.model(batch_tensor)
                probs = torch.sigmoid(logits)
            
            all_probs.append(probs.cpu().numpy())
            
            if show_progress:
                self._print_progress_bar(batch_idx + 1, total_batches, prefix="Inference")
        
        return np.concatenate(all_probs, axis=0)
    
    def classify_spectrograms_batch(
        self,
        spectrograms: List[np.ndarray],
    ) -> List[Dict[str, float]]:
        """
        Classify a batch of pre-extracted spectrograms.
        
        Args:
            spectrograms: List of spectrograms, each shape (128, 128)
            
        Returns:
            List of detection dicts
        """
        if not spectrograms:
            return []
        
        batch_np = np.stack(spectrograms, axis=0)
        batch_tensor = torch.from_numpy(batch_np).float()
        batch_tensor = batch_tensor.unsqueeze(1)
        batch_tensor = batch_tensor.to(self.device)
        
        with torch.inference_mode():
            logits = self.model(batch_tensor)
            probs = torch.sigmoid(logits)
        
        probs_np = probs.cpu().numpy()
        
        return [self._apply_thresholds(p) for p in probs_np]
    
    def get_all_probabilities(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0,
    ) -> Dict[str, float]:
        """
        Get probabilities for all classes (without thresholding).
        
        Useful for debugging or when you want to apply custom thresholds.
        
        Args:
            audio: Audio data
            sr: Sample rate
            onset_time: Onset time in seconds
            window_ms: Window size
            
        Returns:
            Dict of class -> probability for ALL classes
        """
        spectrogram = self._extract_spectrogram(audio, sr, onset_time, window_ms)
        
        if spectrogram is None:
            return {c: 0.0 for c in self.components}
        
        x = torch.from_numpy(spectrogram).float()
        x = x.unsqueeze(0).unsqueeze(0)
        x = x.to(self.device)
        
        with torch.inference_mode():
            logits = self.model(x)
            probs = torch.sigmoid(logits)
        
        probs_np = probs.cpu().numpy()[0]
        return {
            self.idx_to_class[i]: float(p)
            for i, p in enumerate(probs_np)
        }


def _compute_adaptive_threshold(
    probs: np.ndarray,
    method: str,
    min_t: float,
    max_t: float,
) -> float:
    """
    Compute an adaptive threshold for a single class from its probability
    distribution using the specified method.

    This is the core heuristic used by both the single-model and ensemble
    adaptive threshold paths.

    Args:
        probs: 1-D array of sigmoid probabilities for one class across all onsets
        method: "otsu", "knee", or "percentile"
        min_t: Minimum allowed threshold
        max_t: Maximum allowed threshold

    Returns:
        Optimal threshold for this class on this song
    """
    if len(probs) == 0 or probs.max() < min_t:
        return max_t

    if method == "otsu":
        return _otsu_threshold(probs, min_t, max_t)
    elif method == "knee":
        return _knee_threshold(probs, min_t, max_t)
    elif method == "percentile":
        # Keep top 10% for very common classes, top 5% for others.
        # Since we don't know the class identity here, use a conservative
        # top-5% (P95) as the threshold.
        threshold = float(np.percentile(probs, 95))
        return max(min_t, min(max_t, threshold))
    else:
        # Fallback: median of above-baseline probabilities
        above_baseline = probs[probs > 0.1]
        if len(above_baseline) > 10:
            return float(np.clip(np.percentile(above_baseline, 50), min_t, max_t))
        return 0.5


def estimate_adaptive_thresholds(
    probs_matrix: np.ndarray,
    class_names: List[str],
    method: str = "otsu",
    min_threshold: float = 0.15,
    max_threshold: float = 0.85,
    min_detections_per_class: int = 5,
    expected_counts: Optional[Dict[str, int]] = None,
) -> Dict[str, float]:
    """
    Estimate optimal per-class thresholds from probability distributions.
    
    This analyzes the distribution of predicted probabilities for each class
    across all onsets and finds optimal thresholds using statistical methods.
    
    Args:
        probs_matrix: Shape (n_onsets, n_classes) of sigmoid probabilities
        class_names: List of class names corresponding to columns
        method: Threshold estimation method:
            - "otsu": Otsu's method (finds bimodal valley)
            - "percentile": Use top N percentile
            - "knee": Find knee/elbow in sorted probabilities
            - "expected": Match expected detection counts
        min_threshold: Minimum allowed threshold
        max_threshold: Maximum allowed threshold
        min_detections_per_class: Minimum detections to consider class active
        expected_counts: For "expected" method, dict of class -> expected count
        
    Returns:
        Dict of class_name -> optimal threshold
    """
    n_onsets, n_classes = probs_matrix.shape
    thresholds = {}
    
    print(f"\n[ADAPTIVE THRESHOLDS] Analyzing {n_onsets} onsets, {n_classes} classes...")
    print(f"   Method: {method}")
    
    for class_idx, class_name in enumerate(class_names):
        probs = probs_matrix[:, class_idx]
        
        # Skip if class has very low activity
        if probs.max() < min_threshold:
            thresholds[class_name] = max_threshold
            print(f"   {class_name}: max_prob={probs.max():.3f} < {min_threshold}, using {max_threshold}")
            continue
        
        if method == "otsu":
            threshold = _otsu_threshold(probs, min_threshold, max_threshold)
        elif method == "percentile":
            # Keep top 10% of predictions for common classes
            target_percentile = 90 if class_name in ["hihat_closed", "kick", "snare"] else 95
            threshold = max(min_threshold, np.percentile(probs, target_percentile))
        elif method == "knee":
            threshold = _knee_threshold(probs, min_threshold, max_threshold)
        elif method == "expected" and expected_counts and class_name in expected_counts:
            # Find threshold that produces expected count
            target_count = expected_counts[class_name]
            sorted_probs = np.sort(probs)[::-1]
            if target_count < len(sorted_probs):
                threshold = sorted_probs[target_count]
            else:
                threshold = min_threshold
        else:
            # Default: use median of above-baseline probabilities
            above_baseline = probs[probs > 0.1]
            if len(above_baseline) > 10:
                threshold = np.percentile(above_baseline, 50)
            else:
                threshold = 0.5
        
        # Clamp to valid range
        threshold = max(min_threshold, min(max_threshold, threshold))
        thresholds[class_name] = threshold
        
        above_thr = (probs >= threshold).sum()
        print(f"   {class_name}: threshold={threshold:.3f}, detections={above_thr}, "
              f"max={probs.max():.3f}, mean={probs.mean():.3f}")
    
    return thresholds


def _otsu_threshold(probs: np.ndarray, min_t: float, max_t: float) -> float:
    """
    Compute Otsu's threshold for bimodal distribution.
    
    This finds the threshold that minimizes intra-class variance,
    effectively finding the valley between two modes (background vs foreground).
    """
    # Discretize probabilities into bins
    n_bins = 100
    hist, bin_edges = np.histogram(probs, bins=n_bins, range=(0, 1))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Compute cumulative sums
    total = hist.sum()
    if total == 0:
        return 0.5
    
    sum_total = (hist * bin_centers).sum()
    
    best_threshold = 0.5
    best_variance = 0
    
    sum_background = 0
    weight_background = 0
    
    for i in range(n_bins):
        weight_background += hist[i]
        if weight_background == 0:
            continue
        
        weight_foreground = total - weight_background
        if weight_foreground == 0:
            break
        
        sum_background += hist[i] * bin_centers[i]
        
        mean_background = sum_background / weight_background
        mean_foreground = (sum_total - sum_background) / weight_foreground
        
        # Between-class variance
        variance_between = weight_background * weight_foreground * (mean_background - mean_foreground) ** 2
        
        if variance_between > best_variance:
            best_variance = variance_between
            best_threshold = bin_centers[i]
    
    return max(min_t, min(max_t, best_threshold))


def _knee_threshold(probs: np.ndarray, min_t: float, max_t: float) -> float:
    """
    Find threshold using knee/elbow detection in sorted probabilities.
    
    This identifies where the probability curve transitions from
    high-confidence detections to noise.
    """
    sorted_probs = np.sort(probs)[::-1]  # Descending
    n = len(sorted_probs)
    
    if n < 10:
        return 0.5
    
    # Create line from first to last point
    start = np.array([0, sorted_probs[0]])
    end = np.array([n - 1, sorted_probs[-1]])
    line_vec = end - start
    line_len = np.sqrt(np.sum(line_vec ** 2))
    
    if line_len == 0:
        return sorted_probs[n // 2]
    
    line_unit = line_vec / line_len
    
    # Find point with maximum perpendicular distance
    max_dist = 0
    knee_idx = n // 2
    
    for i in range(n):
        point = np.array([i, sorted_probs[i]])
        point_vec = point - start
        proj_length = np.dot(point_vec, line_unit)
        proj_point = start + proj_length * line_unit
        dist = np.sqrt(np.sum((point - proj_point) ** 2))
        
        if dist > max_dist:
            max_dist = dist
            knee_idx = i
    
    threshold = sorted_probs[min(knee_idx, n - 1)]
    return max(min_t, min(max_t, threshold))


def classify_multilabel(
    audio: np.ndarray,
    sr: int,
    onset_times: List[float],
    model_path: str,
    threshold: float = 0.5,
    per_class_thresholds: Optional[Dict[str, float]] = None,
    window_ms: float = 100.0,
) -> List[Dict[str, float]]:
    """
    Convenience function for multi-label drum classification.
    
    Args:
        audio: Audio data
        sr: Sample rate
        onset_times: List of onset times
        model_path: Path to model checkpoint
        threshold: Global threshold
        per_class_thresholds: Per-class thresholds
        window_ms: Window size
        
    Returns:
        List of detection dicts per onset
    """
    classifier = MultiLabelDrumClassifier.get_cached(
        model_path=model_path,
        threshold=threshold,
        per_class_thresholds=per_class_thresholds,
    )
    
    return classifier.classify_batch(audio, sr, onset_times, window_ms)


if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Test multi-label drum classification on audio files"
    )
    parser.add_argument(
        "--audio",
        type=str,
        required=True,
        help="Path to audio file",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to multi-label model checkpoint",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Path to per-class thresholds JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Global threshold (default: 0.5)",
    )
    parser.add_argument(
        "--onset-times",
        type=str,
        default=None,
        help="Comma-separated onset times in seconds (e.g., '0.5,1.0,1.5')",
    )
    parser.add_argument(
        "--detect-onsets",
        action="store_true",
        help="Automatically detect onsets",
    )
    parser.add_argument(
        "--window-ms",
        type=float,
        default=100.0,
        help="Window size in milliseconds",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print all class probabilities",
    )
    
    args = parser.parse_args()
    
    if not HAS_LIBROSA:
        print("ERROR: librosa is required")
        sys.exit(1)
    
    # Load audio
    print(f"Loading audio: {args.audio}")
    audio, sr = librosa.load(args.audio, sr=None, mono=True)
    print(f"  Duration: {len(audio) / sr:.2f}s, SR: {sr}")
    
    # Get onset times
    if args.onset_times:
        onset_times = [float(t.strip()) for t in args.onset_times.split(',')]
    elif args.detect_onsets:
        from transcription.onset_detector import detect_onsets
        result = detect_onsets(audio, sr)
        onset_times = [o.time for o in result.onsets[:20]]  # Limit for testing
        print(f"  Detected {len(result.onsets)} onsets, using first {len(onset_times)}")
    else:
        # Use a few evenly spaced times
        duration = len(audio) / sr
        onset_times = [duration * i / 5 for i in range(1, 5)]
    
    print(f"  Testing {len(onset_times)} onset times")
    
    # Initialize classifier
    print(f"\nLoading model: {args.model}")
    classifier = MultiLabelDrumClassifier(
        model_path=args.model,
        threshold=args.threshold,
        thresholds_file=args.thresholds,
    )
    
    # Classify
    print(f"\n=== CLASSIFICATION RESULTS ===")
    print(f"Global threshold: {args.threshold}")
    if classifier.per_class_thresholds:
        print(f"Per-class thresholds: {classifier.per_class_thresholds}")
    print()
    
    results = classifier.classify_batch(audio, sr, onset_times, args.window_ms)
    
    for i, (time, detections) in enumerate(zip(onset_times, results)):
        print(f"Onset @ {time:.3f}s:")
        if detections:
            for cls, prob in sorted(detections.items(), key=lambda x: -x[1]):
                threshold = classifier.get_threshold(cls)
                print(f"  {cls}: {prob:.3f} (threshold: {threshold:.2f})")
        else:
            print("  (no detections)")
        
        if args.verbose:
            all_probs = classifier.get_all_probabilities(audio, sr, time, args.window_ms)
            print("  All probabilities:")
            for cls, prob in sorted(all_probs.items(), key=lambda x: -x[1]):
                marker = "***" if prob >= classifier.get_threshold(cls) else ""
                print(f"    {cls}: {prob:.3f} {marker}")
        print()
