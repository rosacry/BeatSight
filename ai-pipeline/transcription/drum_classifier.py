"""
Drum component classification utilities.

Provides both the legacy heuristic classifier and integration points for the
optional ML-based classifier, automatically falling back when a trained model
is unavailable.
"""

import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import librosa
import numpy as np

from .onset_detector import DetectedOnset


DEFAULT_MODEL_FILENAME = "best_drum_classifier.pth"

# Updated after each call to ``classify_drums`` to expose telemetry for callers.
last_classifier_mode: Optional[str] = None
last_classifier_model_path: Optional[str] = None


def _interpret_bool(value: str) -> Optional[bool]:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _should_use_ml(user_preference: Optional[bool]) -> bool:
    if user_preference is not None:
        return user_preference

    env_value = os.getenv("BEATSIGHT_USE_ML_CLASSIFIER")
    if env_value is not None:
        interpreted = _interpret_bool(env_value)
        if interpreted is not None:
            return interpreted

    return True


def _resolve_model_path(explicit_path: Optional[str]) -> Tuple[Optional[str], bool]:
    if explicit_path:
        resolved = Path(explicit_path).expanduser()
        return str(resolved), resolved.exists()

    env_path = os.getenv("BEATSIGHT_ML_MODEL_PATH")
    if env_path:
        resolved = Path(env_path).expanduser()
        return str(resolved), resolved.exists()

    default_path = Path(__file__).resolve().parent.parent / "models" / DEFAULT_MODEL_FILENAME
    if default_path.exists():
        return str(default_path), True

    return None, False


# Simplified heuristic classifier (placeholder for ML model)
class SimpleDrumClassifier:
    """
    Heuristic-based drum classifier using spectral features.
    
    This is a simplified implementation. In production, this should be
    replaced with a trained neural network (e.g., ResNet or Transformer).
    """
    
    DRUM_COMPONENTS = [
        "kick",
        "snare",
        "hihat_closed",
        "hihat_open",
        "crash",
        "ride",
        "tom_high",
        "tom_mid",
        "tom_low",
    ]
    
    def classify_onset(
        self,
        audio: np.ndarray,
        sr: int,
        onset_time: float,
        window_ms: float = 100.0,
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
        # Extract window around onset
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio), center + window_samples)
        
        if end - start < 10:  # Too short
            return "unknown", 0.0
        
        window = audio[start:end]
        
        # Compute spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=window, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=window, sr=sr)[0]
        zero_crossing_rate = librosa.feature.zero_crossing_rate(window)[0]
        rms = librosa.feature.rms(y=window)[0]
        
        # Simplified heuristic classification
        avg_centroid = np.mean(spectral_centroid)
        avg_zcr = np.mean(zero_crossing_rate)
        avg_rms = np.mean(rms)
        avg_rolloff = np.mean(spectral_rolloff)
        
        # Kick drum: Low frequency, high energy
        if avg_centroid < 200 and avg_rms > 0.05:
            return "kick", 0.7
        
        # Snare: Mid frequency, moderate energy, high ZCR
        elif 150 <= avg_centroid < 2000 and avg_zcr > 0.08 and avg_rms > 0.03:
            return "snare", 0.65
        
        # Hi-hat: High frequency, lower energy
        elif avg_centroid >= 2500 and avg_rms < 0.2:
            if avg_rms < 0.08:
                return "hihat_closed", 0.6
            else:
                return "hihat_open", 0.6
        
        # Crash: High frequency, high energy, wide spectrum
        elif avg_centroid >= 1800 and avg_rms > 0.1 and avg_rolloff > 4000:
            return "crash", 0.55
        
        # Ride: High frequency, moderate energy
        elif avg_centroid >= 1500 and 0.05 < avg_rms < 0.15:
            return "ride", 0.5
        
        # Toms: Mid-low frequency, moderate energy
        elif 200 <= avg_centroid < 1200 and avg_rms > 0.04:
            if avg_centroid < 500:
                return "tom_low", 0.5
            elif avg_centroid < 800:
                return "tom_mid", 0.5
            else:
                return "tom_high", 0.5
        
        # Generic drum hit - classify as snare for anything else with energy
        elif avg_rms > 0.02:
            return "snare", 0.4
        
        # Very weak hit - might be noise
        return "unknown", 0.3


def classify_drums(
    audio: Tuple[np.ndarray, int],
    onsets: Iterable[Tuple[float, float] | DetectedOnset],
    confidence_threshold: float = 0.7,
    *,
    use_ml: Optional[bool] = None,
    model_path: Optional[str] = None,
    device: Optional[str] = None,
) -> List[Dict]:
    """
    Classify drum components for all onsets.

    Args:
        audio: Tuple of (audio data, sample rate)
        onsets: Iterable of (time, onset_confidence) tuples or DetectedOnset objects
        confidence_threshold: Minimum confidence to include
        use_ml: Force-enable or disable the ML classifier. Defaults to environment
            variable ``BEATSIGHT_USE_ML_CLASSIFIER`` or ``True`` when unspecified.
        model_path: Optional override for the ML model weights (.pth). If not
            provided, falls back to ``BEATSIGHT_ML_MODEL_PATH`` or
            ``ai-pipeline/models/best_drum_classifier.pth`` when present.
        device: Optional device string (e.g. ``"cuda"``) passed to the ML
            classifier.

    Returns:
        List of classified hits with metadata.
    """

    global last_classifier_mode, last_classifier_model_path

    ml_enabled = _should_use_ml(use_ml)
    resolved_model_path, model_exists = _resolve_model_path(model_path)

    if ml_enabled and model_exists:
        from . import ml_drum_classifier

        last_classifier_mode = "ml"
        last_classifier_model_path = resolved_model_path
        classify_drums.last_classifier_mode = last_classifier_mode
        classify_drums.last_classifier_model_path = last_classifier_model_path

        return ml_drum_classifier.classify_drums_ml(
            audio,
            onsets,
            model_path=resolved_model_path,
            confidence_threshold=confidence_threshold,
            device=device,
        )

    if ml_enabled:
        if resolved_model_path:
            print(
                f"Warning: ML classifier disabled (model not found at {resolved_model_path}). "
                "Falling back to heuristic classifier."
            )
        else:
            print(
                "Warning: ML classifier disabled (no model path configured). Falling back to heuristic classifier."
            )

    last_classifier_mode = "heuristic"
    last_classifier_model_path = None
    classify_drums.last_classifier_mode = last_classifier_mode
    classify_drums.last_classifier_model_path = last_classifier_model_path

    return _classify_drums_heuristic(audio, onsets, confidence_threshold)


def _classify_drums_heuristic(
    audio: Tuple[np.ndarray, int],
    onsets: Iterable[Tuple[float, float] | DetectedOnset],
    confidence_threshold: float,
) -> List[Dict]:
    audio_data, sr = audio
    classifier = SimpleDrumClassifier()

    effective_threshold = confidence_threshold
    classified_hits: List[Dict] = []

    for onset in onsets:
        if isinstance(onset, DetectedOnset):
            onset_time = onset.time
            onset_confidence = onset.confidence
        else:
            onset_time, onset_confidence = onset

        component, class_confidence = classifier.classify_onset(audio_data, sr, onset_time)

        combined_confidence = (onset_confidence + class_confidence) / 2.0

        if combined_confidence >= effective_threshold:
            if component == "unknown" and effective_threshold < 0.4:
                component = "hihat_closed"
                class_confidence = 0.4
                combined_confidence = (onset_confidence + class_confidence) / 2.0

            if component != "unknown":
                entry: Dict[str, object] = {
                    "time": onset_time,
                    "component": component,
                    "confidence": combined_confidence,
                    "onset_confidence": onset_confidence,
                    "class_confidence": class_confidence,
                    "ml_based": False,
                }

                if isinstance(onset, DetectedOnset):
                    entry["band_energy"] = onset.band_energies.astype(float).tolist()

                classified_hits.append(entry)

    return classified_hits


# Default telemetry values exposed via function attributes.
classify_drums.last_classifier_mode = None
classify_drums.last_classifier_model_path = None
