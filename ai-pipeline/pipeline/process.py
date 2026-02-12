"""
BeatSight AI Pipeline - Main Processing Module

Orchestrates the entire audio-to-beatmap pipeline.
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import time

from .preprocessing import preprocess_audio
from .separation.demucs_separator import separate_drums
from .transcription.onset_detector import detect_onsets, refine_onsets
from .transcription import drum_classifier
from .beatmap_generator import generate_beatmap
from .metadata_detection import detect_song_metadata

# New structured decoding and readability modules
try:
    from .structured_decoder import (
        apply_structured_decoding,
        detect_time_signature,
        detect_swing_ratio,
    )

    HAS_STRUCTURED_DECODER = True
except ImportError:
    HAS_STRUCTURED_DECODER = False
    apply_structured_decoding = None

try:
    from .chart_readability import (
        filter_chart_for_readability,
        detect_sections,
        apply_difficulty_curve,
    )

    HAS_READABILITY_FILTER = True
except ImportError:
    HAS_READABILITY_FILTER = False
    filter_chart_for_readability = None

# Advanced structured decoding (beam search, transformer, CRF, ensemble)
try:
    from .advanced_structured_decoder import (
        apply_advanced_structured_decoding,
        BeamSearchDecoder,  # noqa: F401
        CRFDecoder,  # noqa: F401
        EnsembleDecoder,  # noqa: F401
    )

    HAS_ADVANCED_DECODER = True
except ImportError:
    HAS_ADVANCED_DECODER = False
    apply_advanced_structured_decoding = None

# Advanced quantization with tuplet/swing detection
try:
    from .advanced_quantization import (
        smart_quantize,
        analyze_subdivisions,
    )

    HAS_ADVANCED_QUANTIZATION = True
except ImportError:
    HAS_ADVANCED_QUANTIZATION = False
    smart_quantize = None

# Genre-aware decoding for style-specific transition probabilities
try:
    from .genre_aware_decoder import (
        apply_genre_aware_decoding,
        detect_genre,
        GENRE_PROFILES,
    )

    HAS_GENRE_DECODER = True
except ImportError:
    HAS_GENRE_DECODER = False
    apply_genre_aware_decoding = None
    detect_genre = None

# Pattern library for recognizing common drum patterns
try:
    from .pattern_library import (
        PatternLibrary,  # noqa: F401
        get_pattern_library,  # noqa: F401
        repair_with_patterns,
    )

    HAS_PATTERN_LIBRARY = True
except ImportError:
    HAS_PATTERN_LIBRARY = False
    repair_with_patterns = None


def process_audio_file(
    input_path: str,
    output_path: str,
    isolate_drums: bool = True,
    confidence_threshold: float = 0.7,
    detection_sensitivity: float = 60.0,
    quantization_grid: str = "sixteenth",
    max_snap_error_ms: float = 25.0,
    debug_output_path: str | None = None,
    forced_bpm: float | None = None,
    forced_offset: float | None = None,
    forced_step: float | None = None,
    force_quantization: bool = True,
    tempo_candidates_hint: List[float] | None = None,
    use_ml_classifier: Optional[bool] = None,
    ml_model_path: Optional[str] = None,
    ml_device: Optional[str] = None,
    # Multi-label classifier options
    use_multilabel: bool = True,
    multilabel_model_path: Optional[str] = None,
    multilabel_thresholds_path: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    # Parameters for structured decoding and readability
    use_structured_decoding: bool = True,
    use_readability_filter: bool = True,
    target_difficulty: str = "expert",
    apply_difficulty_shaping: bool = True,
    # NEW: Advanced decoding options
    decoder_type: str = "ensemble",  # 'viterbi', 'beam', 'transformer', 'crf', 'ensemble'
    use_advanced_quantization: bool = True,  # Smart tuplet/swing detection
    # NEW: Genre-aware decoding and pattern recognition
    use_genre_detection: bool = True,  # Detect genre and adapt transition probabilities
    use_pattern_repair: bool = True,  # Repair ambiguous hits using pattern library
    forced_genre: Optional[str] = None,  # Override auto-detected genre
    # Dynamic lane layout (always on for AI-generated beatmaps)
    num_lanes: int = 12,  # Maximum lanes available (12 for full kit support)
    # Ghost notes setting (experimental)
    include_ghost_notes: bool = True,  # Include ghost notes in beatmap (experimental)
    # NEW: Adaptive thresholds for per-song optimization
    use_adaptive_thresholds: bool = False,  # Compute optimal thresholds for this song
    adaptive_threshold_method: str = "otsu",  # "otsu", "percentile", "knee"
    # Domain gap threshold scaling for Demucs-separated audio
    threshold_scale: float = 0.7,  # Scale file thresholds (0.7 = 70% of calibrated values)
    # Hybrid classification: use Demucs for onset detection, original audio for classification
    hybrid_classification: bool = False,
    # Ensemble classification: body drums from original audio, cymbals from Demucs
    ensemble_classification: bool = False,
    # Dual-model ensemble: separate Demucs model for cymbals
    ensemble_demucs_model_path: Optional[str] = None,
    ensemble_demucs_thresholds_path: Optional[str] = None,
    # Force time signature override
    forced_time_signature: Optional[str] = None,  # e.g. "4/4", "3/4", "6/8"
    # Minimum inter-onset interval override
    min_ioi_ms: Optional[float] = None,  # Explicit min IOI in ms (None = auto from tempo)
    # Accuracy improvements
    use_tta: bool = False,  # Test-Time Augmentation
    tta_augmentations: int = 5,  # Number of TTA augmentations per onset
    use_multi_window: bool = False,  # Multi-window inference
    multi_window_sizes: Optional[List[float]] = None,  # Window sizes in ms
    checkpoint_ensemble_paths: Optional[List[str]] = None,  # Checkpoint paths for ensemble
    use_multi_pass: bool = False,  # Multi-pass onset refinement
    # Progress callback for external progress reporting (e.g., Modal deployment)
    progress_callback: Optional[
        callable
    ] = None,  # Callback(percent: float, message: str)
) -> Dict[str, Any]:
    """
    Process an audio file and generate a beatmap.

    Args:
        input_path: Path to input audio file
        output_path: Path for output .bsm file
        isolate_drums: Whether to perform source separation
        confidence_threshold: Minimum confidence for including hits
        detection_sensitivity: Onset detector sensitivity (0-100)
        quantization_grid: Target quantization grid label
        max_snap_error_ms: Maximum allowed timing error when quantizing
        debug_output_path: Optional path to write a debug JSON payload
        forced_bpm: Override detected BPM
        forced_offset: Override detected offset in seconds
        forced_step: Override quantization step size in seconds
        force_quantization: Force all events to the quantized grid
        tempo_candidates_hint: Optional tempo candidate list (BPM) from host for disambiguation
        use_ml_classifier: Optional override for ML classifier usage
        ml_model_path: Explicit path to trained ML model weights (.pth)
        ml_device: Torch device override for ML inference
        start_time: Start time in seconds for partial processing
        end_time: End time in seconds for partial processing
        progress_callback: Optional callback function(percent: float, message: str) for
            external progress reporting (e.g., Modal deployment). Percent is 0-100.

    Returns:
        Dictionary with processing results and statistics
    """

    # Helper function to report progress
    def _report_progress(percent: float, message: str):
        """Report progress if callback is provided."""
        if progress_callback is not None:
            try:
                progress_callback(percent, message)
            except Exception:
                pass  # Don't let callback errors break the pipeline

    input_path = Path(input_path)
    output_path = Path(output_path)
    debug_output_path = Path(debug_output_path) if debug_output_path else None

    print(f"[*] Processing: {input_path}")
    start_time_overall = time.time()

    # Step 1: Preprocessing
    print("[1/5] Preprocessing audio...")
    _report_progress(5, "Preprocessing audio...")
    duration = None
    if end_time is not None and end_time > 0:
        duration = end_time - start_time

    audio_data, sample_rate = preprocess_audio(
        str(input_path), offset=start_time, duration=duration
    )

    detected_metadata = detect_song_metadata(str(input_path))
    if detected_metadata.get("title") or detected_metadata.get("artist"):
        pretty_title = detected_metadata.get("title") or "?"
        pretty_artist = detected_metadata.get("artist") or "?"
        print(f"   📇 Metadata: {pretty_artist} — {pretty_title}")
    else:
        print("   📇 Metadata: no embedded tags found; will fall back to defaults")

    # Step 2: Source Separation (if requested)
    drum_audio = (audio_data, sample_rate)
    if isolate_drums:
        print("[2/5] Separating drum track (this may take a minute)...")
        _report_progress(10, "Separating drum track with Demucs...")
        drum_audio = separate_drums((audio_data, sample_rate))
        _report_progress(35, "Drum separation complete")
    else:
        print("[2/5] Skipping source separation")
        _report_progress(35, "Source separation skipped")

    # Step 3: Onset Detection
    print("[3/5] Detecting drum hits...")
    _report_progress(40, "Detecting drum onsets...")
    detection_result = detect_onsets(
        drum_audio,
        sensitivity=detection_sensitivity,
        min_ioi_ms=min_ioi_ms,
    )

    refined_onsets = refine_onsets(drum_audio, detection_result.onsets)
    print(f"   Found {len(refined_onsets)} potential hits")

    detection_tempo_candidates = list(detection_result.tempo_candidates or [])
    tempo_candidates = list(detection_tempo_candidates)
    if not tempo_candidates and detection_result.estimated_tempo:
        tempo_candidates = [float(detection_result.estimated_tempo)]

    tempo_hint_count = 0
    if tempo_candidates_hint:
        sanitized = [
            float(value)
            for value in tempo_candidates_hint
            if value and value > 0 and math.isfinite(value)
        ]
        if sanitized:
            hint_values: List[float] = []
            for value in sanitized:
                if all(abs(existing - value) > 1e-3 for existing in hint_values):
                    hint_values.append(value)

            if hint_values:
                tempo_hint_count = len(hint_values)
                combined: List[float] = list(hint_values)

                for value in tempo_candidates:
                    if all(abs(existing - value) > 1e-3 for existing in combined):
                        combined.append(value)

                tempo_candidates = combined
                print(
                    "   ⏱️  Using injected tempo candidates "
                    + ", ".join(f"{value:.3f}" for value in hint_values)
                )

    if not tempo_candidates:
        tempo_candidates = [120.0]

    # Step 4: Drum Classification
    print("[4/5] Classifying drum components...")
    _report_progress(50, "Classifying drum components...")

    # Determine effective multilabel model path
    effective_multilabel_model = multilabel_model_path or ml_model_path

    # Ensemble mode: body drums from original audio, cymbals from Demucs-separated
    if ensemble_classification and isolate_drums:
        if ensemble_demucs_model_path:
            print("   Dual-model ensemble: clean model for body drums, Demucs model for cymbals")
            print("   Both models run on Demucs-separated audio (closer to training domain)")
        else:
            print("   Ensemble mode: body drums + cymbals both on Demucs audio")
        if threshold_scale != 1.0:
            print(f"   Demucs cymbal threshold scale: {threshold_scale:.2f}")
        classified_hits = drum_classifier.classify_drums(
            drum_audio,  # primary: Demucs-separated (closer to clean training domain)
            refined_onsets,
            confidence_threshold,
            use_ml=use_ml_classifier,
            model_path=ml_model_path,
            device=ml_device,
            use_multilabel=use_multilabel,
            multilabel_model_path=effective_multilabel_model,
            multilabel_thresholds_path=multilabel_thresholds_path,
            use_adaptive_thresholds=use_adaptive_thresholds,
            adaptive_threshold_method=adaptive_threshold_method,
            threshold_scale=threshold_scale,
            ensemble_audio=drum_audio,  # secondary: same Demucs audio, different model for cymbals
            ensemble_demucs_model_path=ensemble_demucs_model_path,
            ensemble_demucs_thresholds_path=ensemble_demucs_thresholds_path,
        )
    # Hybrid mode: use original (pre-Demucs) audio for classification to avoid
    # domain gap artifacts. Onset detection still uses Demucs-separated stem.
    elif hybrid_classification and isolate_drums:
        classification_audio = (audio_data, sample_rate)
        effective_threshold_scale = 1.0  # No domain gap on original audio
        print("   Hybrid mode: classifying on original audio (onset detection used Demucs)")
        classified_hits = drum_classifier.classify_drums(
            classification_audio,
            refined_onsets,
            confidence_threshold,
            use_ml=use_ml_classifier,
            model_path=ml_model_path,
            device=ml_device,
            use_multilabel=use_multilabel,
            multilabel_model_path=effective_multilabel_model,
            multilabel_thresholds_path=multilabel_thresholds_path,
            use_adaptive_thresholds=use_adaptive_thresholds,
            adaptive_threshold_method=adaptive_threshold_method,
            threshold_scale=effective_threshold_scale,
        )
    else:
        classification_audio = drum_audio
        effective_threshold_scale = threshold_scale
        if effective_threshold_scale != 1.0:
            print(f"   Threshold scale: {effective_threshold_scale:.2f} (adjusting for Demucs domain gap)")
        classified_hits = drum_classifier.classify_drums(
            classification_audio,
            refined_onsets,
            confidence_threshold,
            use_ml=use_ml_classifier,
            model_path=ml_model_path,
            device=ml_device,
            use_multilabel=use_multilabel,
            multilabel_model_path=effective_multilabel_model,
            multilabel_thresholds_path=multilabel_thresholds_path,
            use_adaptive_thresholds=use_adaptive_thresholds,
            adaptive_threshold_method=adaptive_threshold_method,
            threshold_scale=effective_threshold_scale,
        )
    _report_progress(65, "Drum classification complete")

    # === ACCURACY ENHANCEMENTS (applied after base classification) ===
    # These re-classify using enhanced methods when enabled.
    # They operate directly on the MultiLabelDrumClassifier and require
    # the multilabel model to be available.
    accuracy_enhancements_applied = []
    if use_multilabel and effective_multilabel_model and (
        use_tta or use_multi_window or checkpoint_ensemble_paths or use_multi_pass
    ):
        try:
            from transcription.multilabel_inference import MultiLabelDrumClassifier

            # Get the classification audio
            if ensemble_classification and isolate_drums:
                classify_audio_data, classify_sr = drum_audio
            elif hybrid_classification and isolate_drums:
                classify_audio_data, classify_sr = audio_data, sample_rate
            else:
                classify_audio_data, classify_sr = drum_audio if isinstance(drum_audio, tuple) else (drum_audio[0] if hasattr(drum_audio, '__getitem__') else drum_audio, sample_rate)

            onset_times = [h.get("time", 0) for h in classified_hits]
            # Deduplicate onset times (multi-label may have dupes from same onset)
            unique_onset_times = sorted(set(onset_times))

            if unique_onset_times:
                acc_classifier = MultiLabelDrumClassifier.get_cached(
                    model_path=effective_multilabel_model,
                    threshold=confidence_threshold,
                    thresholds_file=multilabel_thresholds_path,
                    device=ml_device,
                    threshold_scale=threshold_scale,
                )

                enhanced_detections = None

                if use_multi_pass:
                    print("\n   [ACCURACY] Multi-pass onset refinement enabled")
                    enhanced_detections = acc_classifier.classify_batch_multipass(
                        classify_audio_data, classify_sr, unique_onset_times,
                        use_tta_for_uncertain=use_tta,
                        tta_augmentations=tta_augmentations,
                    )
                    accuracy_enhancements_applied.append("multi-pass")
                elif use_tta:
                    print(f"\n   [ACCURACY] TTA enabled ({tta_augmentations} augmentations)")
                    enhanced_detections = acc_classifier.classify_batch_tta(
                        classify_audio_data, classify_sr, unique_onset_times,
                        n_augmentations=tta_augmentations,
                    )
                    accuracy_enhancements_applied.append("TTA")
                elif use_multi_window:
                    window_sizes = multi_window_sizes or [80.0, 100.0, 120.0]
                    print(f"\n   [ACCURACY] Multi-window inference enabled ({window_sizes})")
                    enhanced_detections = acc_classifier.classify_batch_multiwindow(
                        classify_audio_data, classify_sr, unique_onset_times,
                        window_sizes_ms=window_sizes,
                    )
                    accuracy_enhancements_applied.append("multi-window")

                if checkpoint_ensemble_paths and not use_multi_pass:
                    print(f"\n   [ACCURACY] Checkpoint ensemble ({len(checkpoint_ensemble_paths)} models)")
                    enhanced_detections = acc_classifier.classify_batch_checkpoint_ensemble(
                        classify_audio_data, classify_sr, unique_onset_times,
                        checkpoint_paths=checkpoint_ensemble_paths,
                    )
                    accuracy_enhancements_applied.append("checkpoint-ensemble")

                # Rebuild classified_hits from enhanced detections
                if enhanced_detections is not None:
                    new_hits = []
                    for onset_time, detected_classes in zip(unique_onset_times, enhanced_detections):
                        if not detected_classes:
                            continue
                        for class_name, class_confidence in detected_classes.items():
                            new_hits.append({
                                "time": onset_time,
                                "component": class_name,
                                "confidence": class_confidence,
                                "onset_confidence": class_confidence,
                                "class_confidence": class_confidence,
                            })
                    classified_hits = new_hits
                    print(f"   [ACCURACY] Re-classified: {len(classified_hits)} hits "
                          f"(enhancements: {', '.join(accuracy_enhancements_applied)})")

        except Exception as e:
            print(f"   [ACCURACY] Enhancement failed (falling back to base classification): {e}")
            import traceback
            traceback.print_exc()

    # Read from function attribute (more reliable than module global)
    classifier_mode = drum_classifier.classify_drums.last_classifier_mode or "heuristic"
    if classifier_mode == "multilabel":
        model_label = None
        model_path = drum_classifier.classify_drums.last_classifier_model_path
        if model_path:
            model_label = Path(model_path).name
        label_suffix = f" ({model_label})" if model_label else ""
        print(f"   Classifier: Multi-label ML{label_suffix}")
    elif classifier_mode == "ml":
        model_label = None
        model_path = drum_classifier.classify_drums.last_classifier_model_path
        if model_path:
            model_label = Path(model_path).name
        label_suffix = f" ({model_label})" if model_label else ""
        print(f"   Classifier: ML model{label_suffix}")
    else:
        print("   Classifier: Heuristic rules")

    print(
        f"   Classified {len(classified_hits)} hits with confidence >= {confidence_threshold}"
    )

    if len(classified_hits) == 0:
        print(
            f"   [WARN] No hits passed confidence threshold {confidence_threshold}!"
        )
        print("   [WARN] This will trigger fallback pattern generation.")
        if len(refined_onsets) > 0:
            print(
                f"   [INFO] Try lowering --confidence threshold (detected {len(refined_onsets)} onsets)"
            )
    else:
        # Show breakdown of classified components
        component_counts = {}
        for hit in classified_hits:
            comp = hit["component"]
            component_counts[comp] = component_counts.get(comp, 0) + 1
        print(f"   Component breakdown: {component_counts}")

    # Step 4b: Structured Decoding (HMM/Viterbi/Beam/Transformer/CRF)
    detected_time_signature = None
    detected_swing = None
    detected_period_beats = None
    subdivision_analysis = None

    if use_structured_decoding and classified_hits:
        estimated_bpm = tempo_candidates[0] if tempo_candidates else 120.0
        hit_times = [h.get("time", 0) for h in classified_hits]

        # First: Detect time signature and swing (always available if base decoder exists)
        if HAS_STRUCTURED_DECODER:
            try:
                detected_ts = detect_time_signature(hit_times, estimated_bpm, hits=classified_hits)
                detected_time_signature = (
                    f"{detected_ts.numerator}/{detected_ts.denominator}"
                )
                detected_period_beats = detected_ts.detected_period_beats

                # Override with forced time signature if provided
                if forced_time_signature:
                    parts = forced_time_signature.strip().split("/")
                    if len(parts) == 2:
                        forced_num, forced_den = int(parts[0]), int(parts[1])
                        detected_ts = type(
                            "obj", (object,), {
                                "numerator": forced_num,
                                "denominator": forced_den,
                                "detected_period_beats": float(forced_num),
                                "confidence": 1.0,
                            }
                        )()
                        detected_time_signature = forced_time_signature
                        detected_period_beats = float(forced_num)
                        print("[4b] Analyzing musical structure...")
                        print(
                            f"   Forced time signature: {forced_time_signature}"
                        )
                    else:
                        print(f"   [WARN] Invalid --force-time-signature '{forced_time_signature}', using detected")
                        print("[4b] Analyzing musical structure...")
                        print(
                            f"   Detected time signature: {detected_time_signature} "
                            f"(period: {detected_period_beats:.2f} beats, confidence: {detected_ts.confidence:.2f})"
                        )
                else:
                    print("[4b] Analyzing musical structure...")
                    print(
                        f"   Detected time signature: {detected_time_signature} "
                        f"(period: {detected_period_beats:.2f} beats, confidence: {detected_ts.confidence:.2f})"
                    )

                swing_ratio, swing_conf = detect_swing_ratio(hit_times, estimated_bpm)
                detected_swing = {"ratio": swing_ratio, "confidence": swing_conf}
                if swing_conf > 0.3:
                    swing_type = (
                        "straight"
                        if abs(swing_ratio - 1.0) < 0.1
                        else "light swing"
                        if swing_ratio < 1.3
                        else "heavy swing"
                    )
                    print(f"   Detected feel: {swing_type} (ratio: {swing_ratio:.2f})")
            except Exception as e:
                print(f"   [WARN] Time signature detection failed: {e}")
                detected_ts = type(
                    "obj", (object,), {"numerator": 4, "denominator": 4}
                )()
        else:
            detected_ts = type("obj", (object,), {"numerator": 4, "denominator": 4})()

        # Advanced subdivision analysis (tuplets, polyrhythms)
        if use_advanced_quantization and HAS_ADVANCED_QUANTIZATION:
            try:
                subdivision_analysis = analyze_subdivisions(hit_times, estimated_bpm)
                best_grid = subdivision_analysis.best_grid
                print(
                    f"   Detected subdivision: {best_grid} (confidence: {subdivision_analysis.confidence:.2f})"
                )

                if subdivision_analysis.is_polyrhythmic:
                    print(
                        f"   ⚡ Polyrhythm detected: {best_grid} + {subdivision_analysis.secondary_grid}"
                    )

                # Check for tuplets
                if "triplet" in best_grid:
                    print("   Triplet feel detected")
                elif "quintuplet" in best_grid:
                    print(
                        "   Quintuplet (5-tuplet) detected - prog/math rock style!"
                    )
                elif "septuplet" in best_grid:
                    print(
                        "   Septuplet (7-tuplet) detected - jazz/experimental style!"
                    )

            except Exception as e:
                print(f"   [WARN] Advanced subdivision analysis failed: {e}")

        # Apply structured decoding
        try:
            # Use advanced decoder if available and requested
            if HAS_ADVANCED_DECODER and decoder_type in [
                "beam",
                "transformer",
                "crf",
                "ensemble",
            ]:
                print(f"   Applying {decoder_type} decoder...")
                classified_hits = apply_advanced_structured_decoding(
                    classified_hits,
                    bpm=estimated_bpm,
                    offset=0.0,
                    time_signature=(detected_ts.numerator, detected_ts.denominator),
                    decoder_type=decoder_type,
                )
            elif HAS_STRUCTURED_DECODER:
                print("   Applying Viterbi decoder...")
                classified_hits = apply_structured_decoding(
                    classified_hits,
                    bpm=estimated_bpm,
                    offset=0.0,
                    time_signature=(detected_ts.numerator, detected_ts.denominator),
                )

            # Count refined states
            refined_count = sum(
                1 for h in classified_hits if h.get("state_refined", False)
            )
            if refined_count > 0:
                print(f"   Refined {refined_count} ambiguous classifications")

        except Exception as e:
            print(f"   [WARN] Structured decoding failed: {e} (continuing without)")

    # Step 4b2: Genre-Aware Decoding (NEW)
    detected_genre_info = None

    if use_genre_detection and HAS_GENRE_DECODER and classified_hits:
        try:
            estimated_bpm = tempo_candidates[0] if tempo_candidates else 120.0
            swing_ratio = detected_swing.get("ratio", 1.0) if detected_swing else 1.0

            # Detect or use forced genre
            if forced_genre:
                from .genre_aware_decoder import Genre

                try:
                    genre = Genre(forced_genre.lower())
                    genre_confidence = 1.0
                    print(f"🎸 Step 4b2: Using forced genre: {forced_genre}")
                except ValueError:
                    genre, genre_confidence = detect_genre(
                        classified_hits, estimated_bpm, swing_ratio
                    )
                    print(
                        f"🎸 Step 4b2: Invalid forced genre '{forced_genre}', detected: {genre.value}"
                    )
            else:
                genre, genre_confidence = detect_genre(
                    classified_hits, estimated_bpm, swing_ratio
                )
                print("🎸 Step 4b2: Genre detection...")
                print(
                    f"   Detected genre: {genre.value} (confidence: {genre_confidence:.2f})"
                )

            # Apply genre-aware decoding
            classified_hits = apply_genre_aware_decoding(
                classified_hits,
                bpm=estimated_bpm,
                offset=0.0,
                time_signature=(detected_ts.numerator, detected_ts.denominator),
                swing_ratio=swing_ratio,
                genre=genre if forced_genre else None,  # None = auto-detect
            )

            detected_genre_info = {
                "genre": genre.value,
                "confidence": genre_confidence,
                "profile": GENRE_PROFILES.get(genre).name if genre else "Unknown",
            }

        except Exception as e:
            print(f"   [WARN] Genre-aware decoding failed: {e} (continuing without)")

    # Step 4b3: Pattern-Based Repair (NEW)
    pattern_repair_stats = None

    if use_pattern_repair and HAS_PATTERN_LIBRARY and classified_hits:
        try:
            estimated_bpm = tempo_candidates[0] if tempo_candidates else 120.0
            print("🎼 Step 4b3: Pattern library analysis...")

            _original_hits = classified_hits.copy()
            classified_hits = repair_with_patterns(
                classified_hits,
                bpm=estimated_bpm,
                confidence_threshold=0.6,  # Repair hits below this confidence
            )

            repaired_count = sum(
                1 for h in classified_hits if h.get("pattern_repaired", False)
            )
            if repaired_count > 0:
                print(
                    f"   Repaired {repaired_count} ambiguous hits using pattern library"
                )

                # Show which patterns were applied
                patterns_used = set(
                    h.get("pattern_id") for h in classified_hits if h.get("pattern_id")
                )
                if patterns_used:
                    print(f"   Patterns applied: {', '.join(patterns_used)}")

            pattern_repair_stats = {
                "repaired_count": repaired_count,
                "patterns_applied": list(patterns_used) if repaired_count > 0 else [],
            }

        except Exception as e:
            print(f"   [WARN] Pattern repair failed: {e} (continuing without)")

    # Step 4c: Readability Filtering (playability rules)
    readability_stats = None
    sections_info = None

    if use_readability_filter and HAS_READABILITY_FILTER and classified_hits:
        print(
            f"[4c] Applying readability filter (target: {target_difficulty})..."
        )
        try:
            estimated_bpm = tempo_candidates[0] if tempo_candidates else 120.0

            if apply_difficulty_shaping:
                # Detect musical sections
                sections_info = detect_sections(classified_hits, estimated_bpm)
                section_summary = {}
                for s in sections_info:
                    stype = s["section_type"]
                    section_summary[stype] = section_summary.get(stype, 0) + 1
                print(f"   Detected sections: {section_summary}")

                # Apply difficulty curve
                original_count = len(classified_hits)
                classified_hits = apply_difficulty_curve(
                    classified_hits,
                    sections_info,
                    target_difficulty=target_difficulty,
                )
                readability_stats = {
                    "original": original_count,
                    "filtered": len(classified_hits),
                    "difficulty_shaped": True,
                }
            else:
                # Just apply readability filter
                classified_hits, readability_stats = filter_chart_for_readability(
                    classified_hits,
                    difficulty=target_difficulty,
                    bpm=estimated_bpm,
                )

            removed = readability_stats.get("original", len(classified_hits)) - len(
                classified_hits
            )
            if removed > 0:
                print(f"   Filtered {removed} hits for playability")

            if readability_stats.get("impossible_patterns", 0) > 0:
                print(
                    f"   [WARN] Fixed {readability_stats['impossible_patterns']} impossible patterns"
                )

        except Exception as e:
            print(f"   [WARN] Readability filter failed: {e} (continuing without)")

    # Step 4d: Pitch Ranking (produces crash_1/crash_2, tom_1/tom_2 etc.)
    pitch_ranking_applied = False
    if classified_hits and use_multilabel:
        try:
            from transcription.instrument_pitch_ranker import InstrumentPitchRanker

            audio_data_for_ranking, sr_for_ranking = drum_audio
            pitch_ranker = InstrumentPitchRanker()

            # Convert to format expected by pitch ranker
            event_dicts_for_ranking = [
                {
                    "timestamp": h["time"],
                    "label": h["component"],
                    "confidence": h.get("class_confidence", h.get("confidence", 0.5)),
                }
                for h in classified_hits
            ]

            min_samples = 3  # Need at least 3 samples of a type to cluster
            rankable_types = {"crash", "china", "splash", "tom", "ride_bow", "ride_bell"}
            has_rankable = any(
                h["component"] in rankable_types for h in classified_hits
            )

            if has_rankable and len(event_dicts_for_ranking) >= min_samples:
                ranked_results = pitch_ranker.process_song(
                    event_dicts_for_ranking, audio_data_for_ranking, sr_for_ranking
                )

                # Update classified_hits with ranked labels
                for hit, ranked in zip(classified_hits, ranked_results):
                    ranked_label = ranked.get("ranked_label", hit["component"])
                    if ranked_label != hit["component"]:
                        hit["component"] = ranked_label
                        hit["base_component"] = ranked.get("label", hit.get("component"))
                        pitch_ranking_applied = True

                if pitch_ranking_applied:
                    # Show ranked breakdown
                    ranked_counts = {}
                    for h in classified_hits:
                        comp = h["component"]
                        ranked_counts[comp] = ranked_counts.get(comp, 0) + 1
                    ranked_comps = {k: v for k, v in ranked_counts.items()
                                    if "_" in k and k.rsplit("_", 1)[-1].isdigit()}
                    if ranked_comps:
                        print(f"[4d] Pitch ranking: {ranked_comps}")
        except ImportError:
            pass
        except Exception as e:
            print(f"   [WARN] Pitch ranking failed: {e} (continuing without)")

    # Step 5: Beatmap Generation
    print("[5/5] Generating beatmap...")
    _report_progress(85, "Generating beatmap file...")

    metadata_payload = {
        "creator": "BeatSight AI",
        "ai_version": "1.0.0",
        "tags": ["ai-generated"],
    }

    for key in ("title", "artist", "release_date"):
        value = detected_metadata.get(key)
        if value:
            metadata_payload[key] = value

    # Prefer explicit source if provided, otherwise fall back to album title.
    source_value = detected_metadata.get("source") or detected_metadata.get("album")
    if source_value:
        metadata_payload["source"] = source_value

    detected_tags = detected_metadata.get("tags") or []
    for tag in detected_tags:
        if tag and tag not in metadata_payload["tags"]:
            metadata_payload["tags"].append(str(tag))

    if detected_metadata.get("provider"):
        metadata_payload["metadata_provider"] = detected_metadata["provider"]
        if "metadata:detected" not in metadata_payload["tags"]:
            metadata_payload["tags"].append("metadata:detected")

    if detected_metadata.get("confidence") is not None:
        metadata_payload["metadata_confidence"] = float(detected_metadata["confidence"])

    description_parts = []
    if detected_metadata.get("provider"):
        provider = detected_metadata["provider"]
        confidence = detected_metadata.get("confidence")
        if confidence is not None:
            description_parts.append(
                f"Metadata via {provider} (confidence {confidence:.2f})"
            )
        else:
            description_parts.append(f"Metadata via {provider}")
    if detected_metadata.get("release_date"):
        description_parts.append(f"Release date: {detected_metadata['release_date']}")
    if description_parts:
        metadata_payload["description"] = " | ".join(description_parts)

    if forced_bpm is not None and forced_bpm > 0:
        print(f"   ⏱️  Forcing BPM to {forced_bpm:.2f}")

    if forced_offset is not None:
        print(f"   [*] Forcing beat offset to {forced_offset:.3f}s")

    if forced_step is not None and forced_step > 0:
        print(f"   📐 Forcing quantization step to {forced_step:.3f}s")

    if force_quantization:
        print(
            "   📌 Force quantization enabled; all notes will snap to the specified grid"
        )

    print(f"   [*] Dynamic lane detection enabled (max {num_lanes} lanes)")
    if include_ghost_notes:
        print("   👻 Ghost notes: ON (experimental)")
    else:
        print("   👻 Ghost notes: OFF")

    beatmap, debug_info = generate_beatmap(
        classified_hits,
        audio_path=str(input_path),
        drum_stem_path=None,
        metadata=metadata_payload,
        analysis_audio=audio_data,
        analysis_sr=sample_rate,
        tempo_candidates=tempo_candidates,
        tempo_hint_count=tempo_hint_count,
        quantization_grid=quantization_grid,
        max_snap_error_ms=max_snap_error_ms,
        detection_debug=detection_result.to_debug_payload(),
        forced_bpm=forced_bpm,
        forced_offset=forced_offset,
        forced_step=forced_step,
        force_quantization=force_quantization,
        start_time=start_time or 0.0,
        # Lane layout
        num_lanes=num_lanes,
        # Ghost notes (experimental setting)
        include_ghost_notes=include_ghost_notes,
    )

    # Save beatmap
    if output_path.parent:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        json.dump(beatmap, f, indent=2)

    if debug_output_path:
        if debug_output_path.parent:
            debug_output_path.parent.mkdir(parents=True, exist_ok=True)

        debug_payload = {
            "input": str(input_path),
            "generated_at": time.time(),
            "sensitivity": detection_sensitivity,
            "confidence_threshold": confidence_threshold,
            "quantization_grid": quantization_grid,
            "max_snap_error_ms": max_snap_error_ms,
            "forced_bpm": forced_bpm,
            "forced_offset": forced_offset,
            "forced_step": forced_step,
            "force_quantization": force_quantization,
            "detection": detection_result.to_debug_payload(),
            "tempo_candidates_hint": tempo_candidates_hint,
            "detected_tempo_candidates": detection_tempo_candidates,
            "tempo_hint_count": tempo_hint_count,
            "tempo_candidates": tempo_candidates,
            "generation": debug_info,
            # New structured decoding info
            "structured_decoding": {
                "enabled": use_structured_decoding and HAS_STRUCTURED_DECODER,
                "time_signature": detected_time_signature,
                "detected_period_beats": detected_period_beats,  # Raw autocorrelation result
                "swing": detected_swing,
            },
            # New readability filter info
            "readability_filter": {
                "enabled": use_readability_filter and HAS_READABILITY_FILTER,
                "target_difficulty": target_difficulty,
                "stats": readability_stats,
                "sections": sections_info,
            },
            # NEW: Genre-aware decoding info
            "genre_detection": {
                "enabled": use_genre_detection and HAS_GENRE_DECODER,
                "forced_genre": forced_genre,
                "detected": detected_genre_info,
            },
            # NEW: Pattern library repair info
            "pattern_repair": {
                "enabled": use_pattern_repair and HAS_PATTERN_LIBRARY,
                "stats": pattern_repair_stats,
            },
        }

        with debug_output_path.open("w") as debug_file:
            json.dump(debug_payload, debug_file, indent=2)

    elapsed = time.time() - start_time_overall

    print(f"[OK] Complete! Saved to: {output_path}")
    print(f"⏱️  Processing time: {elapsed:.2f}s")
    _report_progress(100, "Processing complete!")

    return {
        "success": True,
        "output_path": str(output_path),
        "total_hits": len(classified_hits),
        "processing_time": elapsed,
        "confidence_threshold": confidence_threshold,
        "debug_path": str(debug_output_path) if debug_output_path else None,
        "classifier": getattr(drum_classifier.classify_drums, 'last_classifier_mode', 'Unknown'),
        "classifier_model_path": getattr(drum_classifier.classify_drums, 'last_classifier_model_path', None),
    }


def main():
    parser = argparse.ArgumentParser(
        description="BeatSight AI - Audio to Beatmap Processor"
    )
    parser.add_argument("--input", "-i", required=True, help="Input audio file")
    parser.add_argument("--output", "-o", required=True, help="Output .bsm file")
    parser.add_argument(
        "--no-separation", action="store_true", help="Skip drum separation"
    )
    parser.add_argument(
        "--confidence", type=float, default=0.7, help="Confidence threshold (0.0-1.0)"
    )
    parser.add_argument(
        "--sensitivity", type=float, default=60.0, help="Detection sensitivity (0-100)"
    )
    parser.add_argument(
        "--quantization",
        type=str,
        default="sixteenth",
        choices=["quarter", "eighth", "triplet", "sixteenth", "thirtysecond"],
        help="Target quantization grid",
    )
    parser.add_argument(
        "--max-snap-error",
        type=float,
        default=25.0,
        help="Maximum snap error in milliseconds (default: 25)",
    )
    parser.add_argument(
        "--debug", type=str, help="Optional path for detailed debug JSON output"
    )
    parser.add_argument(
        "--force-bpm", type=float, help="Override detected BPM with explicit value"
    )
    parser.add_argument(
        "--force-offset", type=float, help="Override detected beat offset (seconds)"
    )
    parser.add_argument(
        "--force-step", type=float, help="Override quantization step size (seconds)"
    )
    parser.add_argument(
        "--force-time-signature", type=str, default=None,
        help="Override detected time signature (e.g. '4/4', '3/4', '6/8')"
    )
    parser.add_argument(
        "--force-quantization",
        action="store_true",
        default=True,
        help="Force all events onto the quantized grid even if outside tolerance (default: on)",
    )
    parser.add_argument(
        "--tempo-candidates", type=str, help="Comma-separated tempo candidates in BPM"
    )
    parser.add_argument(
        "--ml-model", type=str, help="Path to trained drum classifier model (.pth)"
    )
    parser.add_argument(
        "--ml-device", type=str, help="Torch device for ML classifier (e.g. cuda)"
    )
    parser.add_argument(
        "--ml",
        action="store_true",
        help="Force ML classifier usage (overrides environment)",
    )
    parser.add_argument(
        "--no-ml", action="store_true", help="Disable ML classifier and use heuristics"
    )
    parser.add_argument(
        "--multilabel",
        action="store_true",
        default=True,
        help="Use multi-label classifier (detects simultaneous drum hits). Enabled by default.",
    )
    parser.add_argument(
        "--no-multilabel",
        action="store_true",
        help="Disable multi-label classifier and fall back to single-label ML",
    )
    parser.add_argument(
        "--multilabel-model",
        type=str,
        help="Path to multi-label model checkpoint (.pt). If not set, uses --ml-model",
    )
    parser.add_argument(
        "--multilabel-thresholds",
        type=str,
        help="Path to per-class thresholds JSON for multi-label classifier",
    )
    parser.add_argument(
        "--adaptive-thresholds",
        action="store_true",
        help="Compute optimal per-class thresholds for this specific song (experimental)",
    )
    parser.add_argument(
        "--adaptive-threshold-method",
        type=str,
        default="otsu",
        choices=["otsu", "percentile", "knee"],
        help="Method for adaptive threshold estimation: otsu (bimodal), percentile (top-N%%), knee (elbow)",
    )
    parser.add_argument(
        "--threshold-scale",
        type=float,
        default=0.7,
        help="Scale factor for file thresholds (default 0.7). Accounts for domain gap "
             "between clean training data and Demucs-separated inference audio. "
             "Lower values detect more hits (e.g. 0.5 = aggressive, 0.7 = balanced, 1.0 = strict).",
    )
    parser.add_argument(
        "--start-time", type=float, help="Start time in seconds for partial processing"
    )
    parser.add_argument(
        "--end-time", type=float, help="End time in seconds for partial processing"
    )

    # NEW: Structured decoding and readability filter options
    parser.add_argument(
        "--no-structured-decoding",
        action="store_true",
        help="Disable HMM/Viterbi structured decoding",
    )
    parser.add_argument(
        "--no-readability-filter",
        action="store_true",
        help="Disable chart readability/playability filtering",
    )
    parser.add_argument(
        "--min-ioi",
        type=float,
        default=None,
        help="Minimum inter-onset interval in ms. Overrides automatic calculation. "
             "Lower values allow faster notes (e.g. 50 = 50ms = 32nd notes at 150 BPM). "
             "Default: auto (based on tempo and sensitivity).",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default="expert",
        choices=["easy", "normal", "hard", "expert", "master"],
        help="Target difficulty level for readability filter",
    )
    parser.add_argument(
        "--no-difficulty-shaping",
        action="store_true",
        help="Disable section-based difficulty curve shaping",
    )

    # NEW: Advanced decoder options
    parser.add_argument(
        "--decoder",
        type=str,
        default="ensemble",
        choices=["viterbi", "beam", "transformer", "crf", "ensemble"],
        help="Decoder type: viterbi (HMM), beam (multi-hypothesis), "
        "transformer (attention-based), crf (global), "
        "or ensemble (combines all)",
    )
    parser.add_argument(
        "--no-advanced-quantization",
        action="store_true",
        help="Disable smart tuplet/swing detection (use simple grid)",
    )

    # NEW: Genre-aware decoding and pattern library
    parser.add_argument(
        "--no-genre-detection",
        action="store_true",
        help="Disable automatic genre detection and style-aware decoding",
    )
    parser.add_argument(
        "--genre",
        type=str,
        default=None,
        choices=[
            "rock",
            "metal",
            "prog_metal",
            "jazz",
            "funk",
            "pop",
            "latin",
            "electronic",
            "progressive",
            "blues",
            "country",
        ],
        help="Force a specific genre instead of auto-detection",
    )
    parser.add_argument(
        "--no-pattern-repair",
        action="store_true",
        help="Disable pattern library repair for ambiguous hits",
    )

    # Accuracy improvement options
    parser.add_argument(
        "--tta",
        action="store_true",
        help="Enable Test-Time Augmentation for more robust classification (slower but more accurate)",
    )
    parser.add_argument(
        "--tta-augmentations",
        type=int,
        default=5,
        help="Number of augmented copies per onset for TTA (default: 5)",
    )
    parser.add_argument(
        "--multi-window",
        action="store_true",
        help="Enable multi-window inference (80ms, 100ms, 120ms) for averaged predictions",
    )
    parser.add_argument(
        "--multi-window-sizes",
        type=str,
        default="80,100,120",
        help="Comma-separated window sizes in ms for multi-window inference (default: 80,100,120)",
    )
    parser.add_argument(
        "--checkpoint-ensemble",
        type=str,
        nargs="+",
        default=None,
        help="Paths to additional checkpoint files for checkpoint ensemble (averages predictions across models)",
    )
    parser.add_argument(
        "--multi-pass",
        action="store_true",
        help="Enable multi-pass onset refinement (re-classifies uncertain onsets with wider window + TTA)",
    )

    # Lane layout options (always dynamic for AI beatmaps)
    parser.add_argument(
        "--num-lanes",
        type=int,
        default=7,
        choices=[4, 5, 6, 7, 8],
        help="Maximum number of lanes for dynamic layout (default: 7)",
    )

    # Ghost notes setting (experimental)
    parser.add_argument(
        "--no-ghost-notes",
        action="store_true",
        help="Disable ghost notes in beatmap (ghost note detection is experimental)",
    )

    # Hybrid classification: Demucs for onset detection, original audio for classification
    parser.add_argument(
        "--hybrid-classification",
        action="store_true",
        help="Use Demucs-separated audio for onset detection but classify on the "
             "original full-mix audio. Avoids Demucs domain gap artifacts that cause "
             "poor model discrimination. Automatically sets threshold-scale to 1.0.",
    )
    # Ensemble classification: body drums from original, cymbals from Demucs
    parser.add_argument(
        "--ensemble-classification",
        action="store_true",
        help="Classify body drums (kick, snare, hihat, tom, ride) on original "
             "full-mix audio and cymbals (crash, china, splash) on Demucs-separated "
             "audio. Combines strengths of both paths for best overall accuracy.",
    )
    # Dual-model ensemble: separate model for Demucs cymbal classification
    parser.add_argument(
        "--ensemble-demucs-model",
        type=str,
        default=None,
        help="Path to a separate model checkpoint for the Demucs cymbal path "
             "in ensemble mode. This model classifies crash/china/splash on "
             "Demucs-separated audio while the primary --multilabel-model handles "
             "body drums on clean audio. Enables dual-model ensemble for best "
             "per-domain accuracy.",
    )
    parser.add_argument(
        "--ensemble-demucs-thresholds",
        type=str,
        default=None,
        help="Path to thresholds JSON for the Demucs ensemble model. Should be "
             "thresholds calibrated on Demucs-only validation data.",
    )

    args = parser.parse_args()

    if args.ml and args.no_ml:
        parser.error("Cannot specify both --ml and --no-ml")

    if args.hybrid_classification and args.ensemble_classification:
        parser.error("Cannot specify both --hybrid-classification and --ensemble-classification")

    # Auto-enable ensemble mode when a Demucs model is provided
    if args.ensemble_demucs_model and not args.ensemble_classification:
        print("[INFO] --ensemble-demucs-model provided; auto-enabling --ensemble-classification")
        args.ensemble_classification = True

    ml_toggle: Optional[bool] = None
    if args.ml:
        ml_toggle = True
    elif args.no_ml:
        ml_toggle = False

    # Validate input
    if not Path(args.input).exists():
        print(f"[ERROR] Input file not found: {args.input}")
        return 1

    tempo_candidates_hint: List[float] | None = None
    if args.tempo_candidates:
        raw_candidates = [
            segment.strip() for segment in args.tempo_candidates.split(",")
        ]
        parsed_candidates: List[float] = []
        for candidate in raw_candidates:
            if not candidate:
                continue
            try:
                value = float(candidate)
            except ValueError:
                print(f"[WARN] ignoring invalid tempo candidate '{candidate}'")
                continue
            if value > 0 and math.isfinite(value):
                parsed_candidates.append(value)
        if parsed_candidates:
            tempo_candidates_hint = parsed_candidates

    # Process
    try:
        result = process_audio_file(
            args.input,
            args.output,
            isolate_drums=not args.no_separation,
            confidence_threshold=args.confidence,
            detection_sensitivity=args.sensitivity,
            quantization_grid=args.quantization,
            max_snap_error_ms=args.max_snap_error,
            debug_output_path=args.debug,
            forced_bpm=args.force_bpm,
            forced_offset=args.force_offset,
            forced_step=args.force_step,
            forced_time_signature=getattr(args, 'force_time_signature', None),
            force_quantization=args.force_quantization,
            tempo_candidates_hint=tempo_candidates_hint,
            use_ml_classifier=ml_toggle,
            ml_model_path=args.ml_model,
            ml_device=args.ml_device,
            # Multi-label classifier options
            use_multilabel=args.multilabel and not args.no_multilabel,
            multilabel_model_path=args.multilabel_model,
            multilabel_thresholds_path=args.multilabel_thresholds,
            # Adaptive thresholds for per-song optimization
            use_adaptive_thresholds=args.adaptive_thresholds,
            adaptive_threshold_method=args.adaptive_threshold_method,
            # Domain gap threshold scaling
            threshold_scale=args.threshold_scale,
            start_time=args.start_time,
            end_time=args.end_time,
            # Structured decoding and readability options
            use_structured_decoding=not args.no_structured_decoding,
            use_readability_filter=not args.no_readability_filter,
            target_difficulty=args.difficulty,
            apply_difficulty_shaping=not args.no_difficulty_shaping,
            # Advanced decoder and quantization options
            decoder_type=args.decoder,
            use_advanced_quantization=not args.no_advanced_quantization,
            # Genre-aware decoding and pattern library
            use_genre_detection=not args.no_genre_detection,
            use_pattern_repair=not args.no_pattern_repair,
            forced_genre=args.genre,
            # Lane layout (always dynamic)
            num_lanes=args.num_lanes,
            # Ghost notes (experimental)
            include_ghost_notes=not args.no_ghost_notes,
            # Hybrid classification
            hybrid_classification=args.hybrid_classification,
            # Ensemble classification
            ensemble_classification=args.ensemble_classification,
            # Dual-model ensemble
            ensemble_demucs_model_path=getattr(args, 'ensemble_demucs_model', None),
            ensemble_demucs_thresholds_path=getattr(args, 'ensemble_demucs_thresholds', None),
            min_ioi_ms=args.min_ioi,
            # Accuracy enhancements
            use_tta=getattr(args, 'tta', False),
            tta_augmentations=getattr(args, 'tta_augmentations', 5),
            use_multi_window=getattr(args, 'multi_window', False),
            multi_window_sizes=[float(x) for x in getattr(args, 'multi_window_sizes', '80,100,120').split(',')] if getattr(args, 'multi_window', False) else None,
            checkpoint_ensemble_paths=getattr(args, 'checkpoint_ensemble', None),
            use_multi_pass=getattr(args, 'multi_pass', False),
        )
        return 0 if result["success"] else 1
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
