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
        
    Returns:
        Dictionary with processing results and statistics
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    debug_output_path = Path(debug_output_path) if debug_output_path else None

    print(f"🎵 Processing: {input_path}")
    start_time = time.time()

    # Step 1: Preprocessing
    print("📊 Step 1/5: Preprocessing audio...")
    audio_data, sample_rate = preprocess_audio(str(input_path))

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
        sanitized = [float(value) for value in tempo_candidates_hint if value and value > 0 and math.isfinite(value)]
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
                print("   ⏱️  Using injected tempo candidates " + ", ".join(f"{value:.3f}" for value in hint_values))

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

    print(f"   Classified {len(classified_hits)} hits with confidence >= {confidence_threshold}")
    
    if len(classified_hits) == 0:
        print(f"   ⚠️  WARNING: No hits passed confidence threshold {confidence_threshold}!")
        print(f"   ⚠️  This will trigger fallback pattern generation.")
        if len(refined_onsets) > 0:
            print(f"   ℹ️  Try lowering --confidence threshold (detected {len(refined_onsets)} onsets)")
    else:
        # Show breakdown of classified components
        component_counts = {}
        for hit in classified_hits:
            comp = hit["component"]
            component_counts[comp] = component_counts.get(comp, 0) + 1
        print(f"   Component breakdown: {component_counts}")

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
            description_parts.append(f"Metadata via {provider} (confidence {confidence:.2f})")
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
        print("   📌 Force quantization enabled; all notes will snap to the specified grid")

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
    )

    # Save beatmap
    if output_path.parent:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open('w') as f:
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
        }

        with debug_output_path.open("w") as debug_file:
            json.dump(debug_payload, debug_file, indent=2)

    elapsed = time.time() - start_time

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
    parser = argparse.ArgumentParser(description="BeatSight AI - Audio to Beatmap Processor")
    parser.add_argument("--input", "-i", required=True, help="Input audio file")
    parser.add_argument("--output", "-o", required=True, help="Output .bsm file")
    parser.add_argument("--no-separation", action="store_true", help="Skip drum separation")
    parser.add_argument("--confidence", type=float, default=0.7, help="Confidence threshold (0.0-1.0)")
    parser.add_argument("--sensitivity", type=float, default=60.0, help="Detection sensitivity (0-100)")
    parser.add_argument(
        "--quantization",
        type=str,
        default="sixteenth",
        choices=["quarter", "eighth", "triplet", "sixteenth", "thirtysecond"],
        help="Target quantization grid",
    )
    parser.add_argument("--max-snap-error", type=float, default=12.0, help="Maximum snap error in milliseconds")
    parser.add_argument("--debug", type=str, help="Optional path for detailed debug JSON output")
    parser.add_argument("--force-bpm", type=float, help="Override detected BPM with explicit value")
    parser.add_argument("--force-offset", type=float, help="Override detected beat offset (seconds)")
    parser.add_argument("--force-step", type=float, help="Override quantization step size (seconds)")
    parser.add_argument("--force-quantization", action="store_true", help="Force all events onto the quantized grid even if outside tolerance")
    parser.add_argument("--tempo-candidates", type=str, help="Comma-separated tempo candidates in BPM")
    parser.add_argument("--ml-model", type=str, help="Path to trained drum classifier model (.pth)")
    parser.add_argument("--ml-device", type=str, help="Torch device for ML classifier (e.g. cuda)")
    parser.add_argument("--ml", action="store_true", help="Force ML classifier usage (overrides environment)")
    parser.add_argument("--no-ml", action="store_true", help="Disable ML classifier and use heuristics")
    
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
        raw_candidates = [segment.strip() for segment in args.tempo_candidates.split(",")]
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
        )
        return 0 if result["success"] else 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
