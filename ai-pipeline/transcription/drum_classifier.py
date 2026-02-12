"""
Drum component classification utilities.

Provides both the legacy heuristic classifier and integration points for the
optional ML-based classifier, automatically falling back when a trained model
is unavailable.
"""

import logging
import os
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import librosa
import numpy as np

from .onset_detector import DetectedOnset

logger = logging.getLogger(__name__)


DEFAULT_MODEL_FILENAME = "best_drum_classifier.pth"

# Updated after each call to ``classify_drums`` to expose telemetry for callers.
last_classifier_mode: Optional[str] = None
last_classifier_model_path: Optional[str] = None

# Lock for thread-safe updates to the classifier mode globals
_classifier_mode_lock = threading.Lock()


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

    default_path = (
        Path(__file__).resolve().parent.parent / "models" / DEFAULT_MODEL_FILENAME
    )
    if default_path.exists():
        return str(default_path), True

    return None, False


def _auto_discover_multilabel_model(
    explicit_model_path: Optional[str],
    explicit_thresholds_path: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """
    Auto-discover the multilabel model and thresholds in standard locations.
    
    Search order:
    1. Explicit paths if provided and exist
    2. Environment variables BEATSIGHT_MULTILABEL_MODEL_PATH and BEATSIGHT_MULTILABEL_THRESHOLDS_PATH
    3. runs/v5_multilabel_final_v3/ (latest trained model)
    4. models/ directory
    
    Returns:
        Tuple of (model_path, thresholds_path) or (None, None) if not found.
    """
    ai_pipeline_root = Path(__file__).resolve().parent.parent
    
    # Check explicit paths first
    if explicit_model_path and Path(explicit_model_path).exists():
        # If model specified but not thresholds, look for thresholds in same dir
        if not explicit_thresholds_path:
            model_dir = Path(explicit_model_path).parent
            auto_thresholds = model_dir / "thresholds.json"
            if auto_thresholds.exists():
                explicit_thresholds_path = str(auto_thresholds)
        return explicit_model_path, explicit_thresholds_path
    
    # Check environment variables
    env_model = os.getenv("BEATSIGHT_MULTILABEL_MODEL_PATH")
    env_thresholds = os.getenv("BEATSIGHT_MULTILABEL_THRESHOLDS_PATH")
    if env_model and Path(env_model).exists():
        if not env_thresholds:
            auto_thresholds = Path(env_model).parent / "thresholds.json"
            if auto_thresholds.exists():
                env_thresholds = str(auto_thresholds)
        return env_model, env_thresholds
    
    # Search standard locations
    search_locations = [
        # Latest trained model
        ai_pipeline_root / "runs" / "v5_multilabel_final_v3",
        # Models directory
        ai_pipeline_root / "models",
        # Alternative run directories
        ai_pipeline_root / "runs" / "v5_multilabel_final_v2",
        ai_pipeline_root / "runs" / "v5_multilabel_final",
    ]
    
    model_filenames = [
        "best_multilabel_model_ema.pt",
        "best_multilabel_model.pt",
        "best_model.pt",
    ]
    
    for location in search_locations:
        if not location.exists():
            continue
        for model_name in model_filenames:
            model_path = location / model_name
            if model_path.exists():
                thresholds_path = location / "thresholds.json"
                logger.info(f"Auto-discovered multilabel model: {model_path}")
                return str(model_path), str(thresholds_path) if thresholds_path.exists() else None
    
    return None, None


class SimpleDrumClassifier:
    """
    Heuristic-based drum classifier using spectral features.

    This classifier uses hand-tuned frequency and energy thresholds
    to identify drum components. While not as accurate as the ML
    classifier (MLDrumClassifier), it serves critical roles:

    1. **Fallback Mode**: When ML model is unavailable or fails to load,
       the system automatically falls back to this heuristic classifier
       to ensure the pipeline never crashes.

    2. **Low-Confidence Regions**: Can be used to fill gaps in ML predictions
       where confidence is too low.

    3. **Testing & Development**: Provides deterministic behavior for
       unit tests and rapid iteration without GPU dependencies.

    4. **Baseline Comparison**: Establishes minimum performance floor
       to validate ML improvements against.

    Classification is based on:
    - Spectral centroid (frequency content)
    - Zero crossing rate (noisiness/brightness)
    - RMS energy (loudness)
    - Spectral rolloff (frequency distribution)

    Typical accuracy: ~60-70% on clean isolated drums
    ML accuracy target: ~85-95% with proper training data

    See Also:
        MLDrumClassifier: The preferred ML-based classifier
        classify_drums(): Main entry point that auto-selects classifier
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
    use_multilabel: bool = False,
    multilabel_model_path: Optional[str] = None,
    multilabel_thresholds_path: Optional[str] = None,
    enable_count_estimation: bool = True,
    # NEW: Adaptive threshold options
    use_adaptive_thresholds: bool = False,
    adaptive_threshold_method: str = "otsu",
    # Domain gap threshold scaling
    threshold_scale: float = 1.0,
    # Ensemble classification: second audio source
    ensemble_audio: Optional[Tuple[np.ndarray, int]] = None,
    # Dual-model ensemble: separate Demucs model
    ensemble_demucs_model_path: Optional[str] = None,
    ensemble_demucs_thresholds_path: Optional[str] = None,
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
        use_multilabel: If True, use multi-label classifier that can detect
            multiple simultaneous drum hits (e.g., kick + hi-hat, snare + crash).
            This enables detecting when 2 crashes or 2 toms hit simultaneously.
        multilabel_model_path: Path to the multi-label model checkpoint.
            Required when use_multilabel=True.
        multilabel_thresholds_path: Optional path to per-class thresholds JSON.
            If not provided, uses default threshold of 0.5.
        enable_count_estimation: If True (default), estimates count when
            multiple same-class instruments hit simultaneously (e.g., 2 crashes).
            Only applies when use_multilabel=True.
        ensemble_audio: Optional second audio source as (audio_data, sample_rate)
            for ensemble classification. When provided, body drums are classified
            from the primary audio and cymbals from ensemble_audio (Demucs), or
            vice versa depending on the pipeline mode.
        ensemble_demucs_model_path: Optional path to a separate model checkpoint
            for the Demucs cymbal path in dual-model ensemble mode. When provided
            with ensemble_audio, this model is used for crash/china/splash
            classification on Demucs audio while the primary model handles body
            drums on clean audio.
        ensemble_demucs_thresholds_path: Optional path to thresholds JSON for
            the Demucs model. Should be thresholds calibrated on Demucs-only
            validation data.

    Returns:
        List of classified hits with metadata.
        
    Multi-label Mode:
        When use_multilabel=True, each onset may produce multiple hits in the
        output list (one per detected class). For example, a kick + hi-hat
        combination at time 0.5s would produce:
        [
            {"time": 0.5, "component": "kick", "confidence": 0.95, ...},
            {"time": 0.5, "component": "hihat_closed", "confidence": 0.82, ...}
        ]
        
        Additionally, count estimation may detect multiple instances of the
        same class (e.g., 2 crashes) and produce multiple entries for that class.
    """

    global last_classifier_mode, last_classifier_model_path

    # Handle multi-label mode
    if use_multilabel:
        return _classify_drums_multilabel(
            audio=audio,
            onsets=onsets,
            multilabel_model_path=multilabel_model_path,
            multilabel_thresholds_path=multilabel_thresholds_path,
            confidence_threshold=confidence_threshold,
            device=device,
            enable_count_estimation=enable_count_estimation,
            use_adaptive_thresholds=use_adaptive_thresholds,
            adaptive_threshold_method=adaptive_threshold_method,
            threshold_scale=threshold_scale,
            ensemble_audio=ensemble_audio,
            ensemble_demucs_model_path=ensemble_demucs_model_path,
            ensemble_demucs_thresholds_path=ensemble_demucs_thresholds_path,
        )

    ml_enabled = _should_use_ml(use_ml)
    resolved_model_path, model_exists = _resolve_model_path(model_path)

    if ml_enabled and model_exists:
        from . import ml_drum_classifier

        # Thread-safe update of telemetry globals
        with _classifier_mode_lock:
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

    # Thread-safe update of telemetry globals
    with _classifier_mode_lock:
        last_classifier_mode = "heuristic"
        last_classifier_model_path = None
        classify_drums.last_classifier_mode = last_classifier_mode
        classify_drums.last_classifier_model_path = last_classifier_model_path

    return _classify_drums_heuristic(audio, onsets, confidence_threshold)


def _classify_drums_multilabel(
    audio: Tuple[np.ndarray, int],
    onsets: Iterable[Tuple[float, float] | DetectedOnset],
    multilabel_model_path: Optional[str],
    multilabel_thresholds_path: Optional[str],
    confidence_threshold: float,
    device: Optional[str],
    enable_count_estimation: bool,
    use_adaptive_thresholds: bool = False,
    adaptive_threshold_method: str = "otsu",
    threshold_scale: float = 1.0,
    ensemble_audio: Optional[Tuple[np.ndarray, int]] = None,
    ensemble_demucs_model_path: Optional[str] = None,
    ensemble_demucs_thresholds_path: Optional[str] = None,
) -> List[Dict]:
    """
    Internal function for multi-label classification.
    
    Uses the multi-label classifier to detect multiple simultaneous instruments,
    and optionally applies count estimation to detect when 2+ of the same
    instrument hit together.
    """
    global last_classifier_mode, last_classifier_model_path
    
    audio_data, sr = audio
    
    # Auto-discover model if path not provided
    if not multilabel_model_path or not Path(multilabel_model_path).exists():
        multilabel_model_path, multilabel_thresholds_path = _auto_discover_multilabel_model(
            multilabel_model_path, multilabel_thresholds_path
        )
    
    if not multilabel_model_path or not Path(multilabel_model_path).exists():
        raise ValueError(
            f"Multi-label model not found at '{multilabel_model_path}'. "
            "Provide a valid path with multilabel_model_path parameter."
        )
    
    # Import multi-label components
    from .multilabel_inference import MultiLabelDrumClassifier
    
    # Update telemetry
    with _classifier_mode_lock:
        last_classifier_mode = "multilabel"
        last_classifier_model_path = multilabel_model_path
        classify_drums.last_classifier_mode = last_classifier_mode
        classify_drums.last_classifier_model_path = last_classifier_model_path
    
    # Initialize classifier
    classifier = MultiLabelDrumClassifier.get_cached(
        model_path=multilabel_model_path,
        threshold=confidence_threshold,
        thresholds_file=multilabel_thresholds_path,
        device=device,
        threshold_scale=threshold_scale,
    )
    
    # Initialize count estimator if enabled
    count_estimator = None
    if enable_count_estimation:
        try:
            from .count_estimation import CountEstimator
            count_estimator = CountEstimator()
        except ImportError:
            pass
    
    # Convert onsets to list with times and confidences
    onset_list = []
    for onset in onsets:
        if isinstance(onset, DetectedOnset):
            onset_list.append((onset.time, onset.confidence))
        else:
            onset_list.append((onset[0], onset[1]))
    
    if not onset_list:
        return []
    
    # Batch classify all onsets
    onset_times = [t for t, _ in onset_list]
    onset_confidences = {t: c for t, c in onset_list}
    
    # Use adaptive thresholds if enabled
    adaptive_thresholds_used = None
    if ensemble_audio is not None:
        # Ensemble mode: body drums from primary audio, cymbals from ensemble_audio
        ensemble_data, ensemble_sr = ensemble_audio

        # Create second classifier for Demucs path if separate model provided
        demucs_classifier = None
        if ensemble_demucs_model_path and Path(ensemble_demucs_model_path).exists():
            print(f"   Dual-model ensemble: loading Demucs model from {ensemble_demucs_model_path}")
            demucs_classifier = MultiLabelDrumClassifier.get_cached(
                model_path=ensemble_demucs_model_path,
                threshold=confidence_threshold,
                thresholds_file=ensemble_demucs_thresholds_path,
                device=device,
                threshold_scale=threshold_scale,
            )

        if use_adaptive_thresholds:
            print(f"   Using adaptive thresholds with ensemble (method: {adaptive_threshold_method})")
            detections, adaptive_thresholds_used = classifier.classify_batch_ensemble_with_adaptive_thresholds(
                hybrid_audio=audio_data,
                demucs_audio=ensemble_data,
                sr=sr,
                onset_times=onset_times,
                demucs_threshold_scale=threshold_scale,
                demucs_classifier=demucs_classifier,
                method=adaptive_threshold_method,
            )
        else:
            detections = classifier.classify_batch_ensemble(
                hybrid_audio=audio_data,
                demucs_audio=ensemble_data,
                sr=sr,
                onset_times=onset_times,
                demucs_threshold_scale=threshold_scale,
                demucs_classifier=demucs_classifier,
            )
    elif use_adaptive_thresholds:
        print(f"   Using adaptive thresholds (method: {adaptive_threshold_method})")
        detections, adaptive_thresholds_used = classifier.classify_batch_with_adaptive_thresholds(
            audio_data, sr, onset_times,
            method=adaptive_threshold_method,
        )
    else:
        detections = classifier.classify_batch(audio_data, sr, onset_times)
    
    # Build output list
    classified_hits: List[Dict] = []
    
    for onset_time, detected_classes in zip(onset_times, detections):
        onset_conf = onset_confidences[onset_time]
        
        if not detected_classes:
            continue
        
        # Extract audio segment for count estimation
        window_ms = 100.0
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(audio_data), start + window_samples)
        segment = audio_data[start:end]
        
        for class_name, class_confidence in detected_classes.items():
            # Estimate count if enabled
            if count_estimator:
                count = count_estimator.estimate_count(segment, sr, class_name)
            else:
                count = 1
            
            # Add entry for each detected hit
            for hit_idx in range(count):
                combined_confidence = (onset_conf + class_confidence) / 2.0
                
                entry: Dict[str, object] = {
                    "time": onset_time,
                    "component": class_name,
                    "confidence": combined_confidence,
                    "onset_confidence": onset_conf,
                    "class_confidence": class_confidence,
                    "ml_based": True,
                    "multilabel": True,
                    "count_at_onset": count,
                    "hit_index": hit_idx,
                }
                
                classified_hits.append(entry)
    
    return classified_hits


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

        component, class_confidence = classifier.classify_onset(
            audio_data, sr, onset_time
        )

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
