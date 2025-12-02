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
    max_snap_error_ms: float = 12.0,
    debug_output_path: str | None = None,
    forced_bpm: float | None = None,
    forced_offset: float | None = None,
    forced_step: float | None = None,
    force_quantization: bool = False,
    tempo_candidates_hint: List[float] | None = None,
    use_ml_classifier: Optional[bool] = None,
    ml_model_path: Optional[str] = None,
    ml_device: Optional[str] = None,
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
    num_lanes: int = 7,  # Maximum lanes available (can be 4-8 depending on game mode)
    # Ghost notes setting (experimental)
    include_ghost_notes: bool = True,  # Include ghost notes in beatmap (experimental)
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

    Returns:
        Dictionary with processing results and statistics
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    debug_output_path = Path(debug_output_path) if debug_output_path else None

    print(f"🎵 Processing: {input_path}")
    start_time_overall = time.time()

    # Step 1: Preprocessing
    print("📊 Step 1/5: Preprocessing audio...")
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
        print("🎛️  Step 2/5: Separating drum track (this may take a minute)...")
        drum_audio = separate_drums((audio_data, sample_rate))
    else:
        print("⏭️  Step 2/5: Skipping source separation")

    # Step 3: Onset Detection
    print("🔍 Step 3/5: Detecting drum hits...")
    detection_result = detect_onsets(
        drum_audio,
        sensitivity=detection_sensitivity,
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
    print("🥁 Step 4/5: Classifying drum components...")
    classified_hits = drum_classifier.classify_drums(
        drum_audio,
        refined_onsets,
        confidence_threshold,
        use_ml=use_ml_classifier,
        model_path=ml_model_path,
        device=ml_device,
    )

    classifier_mode = drum_classifier.last_classifier_mode or "heuristic"
    if classifier_mode == "ml":
        model_label = None
        if drum_classifier.last_classifier_model_path:
            model_label = Path(drum_classifier.last_classifier_model_path).name
        label_suffix = f" ({model_label})" if model_label else ""
        print(f"   Classifier: ML model{label_suffix}")
    else:
        print("   Classifier: Heuristic rules")

    print(
        f"   Classified {len(classified_hits)} hits with confidence >= {confidence_threshold}"
    )

    if len(classified_hits) == 0:
        print(
            f"   ⚠️  WARNING: No hits passed confidence threshold {confidence_threshold}!"
        )
        print("   ⚠️  This will trigger fallback pattern generation.")
        if len(refined_onsets) > 0:
            print(
                f"   ℹ️  Try lowering --confidence threshold (detected {len(refined_onsets)} onsets)"
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
                detected_ts = detect_time_signature(hit_times, estimated_bpm)
                detected_time_signature = (
                    f"{detected_ts.numerator}/{detected_ts.denominator}"
                )
                detected_period_beats = detected_ts.detected_period_beats
                print("🔄 Step 4b: Analyzing musical structure...")
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
                print(f"   ⚠️ Time signature detection failed: {e}")
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
                    print("   🎵 Triplet feel detected")
                elif "quintuplet" in best_grid:
                    print(
                        "   🎵 Quintuplet (5-tuplet) detected - prog/math rock style!"
                    )
                elif "septuplet" in best_grid:
                    print(
                        "   🎵 Septuplet (7-tuplet) detected - jazz/experimental style!"
                    )

            except Exception as e:
                print(f"   ⚠️ Advanced subdivision analysis failed: {e}")

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
            print(f"   ⚠️ Structured decoding failed: {e} (continuing without)")

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
            print(f"   ⚠️ Genre-aware decoding failed: {e} (continuing without)")

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
            print(f"   ⚠️ Pattern repair failed: {e} (continuing without)")

    # Step 4c: Readability Filtering (playability rules)
    readability_stats = None
    sections_info = None

    if use_readability_filter and HAS_READABILITY_FILTER and classified_hits:
        print(
            f"🎯 Step 4c: Applying readability filter (target: {target_difficulty})..."
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
                    f"   ⚠️ Fixed {readability_stats['impossible_patterns']} impossible patterns"
                )

        except Exception as e:
            print(f"   ⚠️ Readability filter failed: {e} (continuing without)")

    # Step 5: Beatmap Generation
    print("📝 Step 5/5: Generating beatmap...")

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
        print(f"   🎯 Forcing beat offset to {forced_offset:.3f}s")

    if forced_step is not None and forced_step > 0:
        print(f"   📐 Forcing quantization step to {forced_step:.3f}s")

    if force_quantization:
        print(
            "   📌 Force quantization enabled; all notes will snap to the specified grid"
        )

    print(f"   🎯 Dynamic lane detection enabled (max {num_lanes} lanes)")
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

    print(f"✅ Complete! Saved to: {output_path}")
    print(f"⏱️  Processing time: {elapsed:.2f}s")

    return {
        "success": True,
        "output_path": str(output_path),
        "total_hits": len(classified_hits),
        "processing_time": elapsed,
        "confidence_threshold": confidence_threshold,
        "debug_path": str(debug_output_path) if debug_output_path else None,
        "classifier": drum_classifier.last_classifier_mode,
        "classifier_model_path": drum_classifier.last_classifier_model_path,
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
        default=12.0,
        help="Maximum snap error in milliseconds",
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
        "--force-quantization",
        action="store_true",
        help="Force all events onto the quantized grid even if outside tolerance",
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

    args = parser.parse_args()

    if args.ml and args.no_ml:
        parser.error("Cannot specify both --ml and --no-ml")

    ml_toggle: Optional[bool] = None
    if args.ml:
        ml_toggle = True
    elif args.no_ml:
        ml_toggle = False

    # Validate input
    if not Path(args.input).exists():
        print(f"❌ Error: Input file not found: {args.input}")
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
                print(f"⚠️  Warning: ignoring invalid tempo candidate '{candidate}'")
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
            force_quantization=args.force_quantization,
            tempo_candidates_hint=tempo_candidates_hint,
            use_ml_classifier=ml_toggle,
            ml_model_path=args.ml_model,
            ml_device=args.ml_device,
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
        )
        return 0 if result["success"] else 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
