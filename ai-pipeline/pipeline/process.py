"""
BeatSight AI Pipeline - Main Processing Module

Orchestrates the entire audio-to-beatmap pipeline.
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any
import time

from .preprocessing import preprocess_audio
from .separation.demucs_separator import separate_drums
from .transcription.onset_detector import detect_onsets
from .transcription.drum_classifier import classify_drums
from .beatmap_generator import generate_beatmap


def process_audio_file(
    input_path: str,
    output_path: str,
    isolate_drums: bool = True,
    confidence_threshold: float = 0.7,
) -> Dict[str, Any]:
    """
    Process an audio file and generate a beatmap.
    
    Args:
        input_path: Path to input audio file
        output_path: Path for output .bsm file
        isolate_drums: Whether to perform source separation
        confidence_threshold: Minimum confidence for including hits
        
    Returns:
        Dictionary with processing results and statistics
    """
    print(f"🎵 Processing: {input_path}")
    start_time = time.time()
    
    # Step 1: Preprocessing
    print("📊 Step 1/5: Preprocessing audio...")
    preprocessed_audio = preprocess_audio(input_path)
    
    # Step 2: Source Separation (if requested)
    drum_audio = preprocessed_audio
    if isolate_drums:
        print("🎛️  Step 2/5: Separating drum track (this may take a minute)...")
        drum_audio = separate_drums(preprocessed_audio)
    else:
        print("⏭️  Step 2/5: Skipping source separation")
    
    # Step 3: Onset Detection
    print("🔍 Step 3/5: Detecting drum hits...")
    onsets = detect_onsets(drum_audio)
    print(f"   Found {len(onsets)} potential hits")
    
    # Step 4: Drum Classification
    print("🥁 Step 4/5: Classifying drum components...")
    classified_hits = classify_drums(drum_audio, onsets, confidence_threshold)
    print(f"   Classified {len(classified_hits)} hits with confidence >= {confidence_threshold}")
    
    # Step 5: Beatmap Generation
    print("📝 Step 5/5: Generating beatmap...")
    beatmap = generate_beatmap(
        classified_hits,
        audio_path=input_path,
        drum_stem_path=drum_audio if isolate_drums else None,
        metadata={
            "creator": "BeatSight AI",
            "ai_version": "1.0.0",
        }
    )
    
    # Save beatmap
    with open(output_path, 'w') as f:
        json.dump(beatmap, f, indent=2)
    
    elapsed = time.time() - start_time
    
    print(f"✅ Complete! Saved to: {output_path}")
    print(f"⏱️  Processing time: {elapsed:.2f}s")
    
    return {
        "success": True,
        "output_path": output_path,
        "total_hits": len(classified_hits),
        "processing_time": elapsed,
        "confidence_threshold": confidence_threshold,
    }


def main():
    parser = argparse.ArgumentParser(description="BeatSight AI - Audio to Beatmap Processor")
    parser.add_argument("--input", "-i", required=True, help="Input audio file")
    parser.add_argument("--output", "-o", required=True, help="Output .bsm file")
    parser.add_argument("--no-separation", action="store_true", help="Skip drum separation")
    parser.add_argument("--confidence", type=float, default=0.7, help="Confidence threshold (0.0-1.0)")
    
    args = parser.parse_args()
    
    # Validate input
    if not Path(args.input).exists():
        print(f"❌ Error: Input file not found: {args.input}")
        return 1
    
    # Process
    try:
        result = process_audio_file(
            args.input,
            args.output,
            isolate_drums=not args.no_separation,
            confidence_threshold=args.confidence,
        )
        return 0 if result["success"] else 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
