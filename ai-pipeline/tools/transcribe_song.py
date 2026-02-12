#!/usr/bin/env python3
"""
End-to-End Drum Transcription Test

This script runs the full drum transcription pipeline on a real song:
1. Source separation (Demucs) to isolate drums
2. Onset detection 
3. Multi-label drum classification
4. Count estimation for simultaneous hits
5. Pitch ranking for cymbals/toms

Usage:
    python tools/transcribe_song.py --audio path/to/song.flac
    python tools/transcribe_song.py --audio path/to/song.flac --skip-separation  # if already isolated drums
    python tools/transcribe_song.py --audio path/to/song.flac --output results.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Full drum transcription pipeline")
    parser.add_argument(
        "--audio",
        type=str,
        required=True,
        help="Path to audio file (song or isolated drums)",
    )
    parser.add_argument(
        "--skip-separation",
        action="store_true",
        help="Skip drum separation (use if audio is already isolated drums)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Path to model checkpoint (default: production model)",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Path to thresholds JSON (default: production thresholds)",
    )
    parser.add_argument(
        "--save-drums",
        type=str,
        default=None,
        help="Save separated drums to this path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output",
    )
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.audio):
        print(f"ERROR: Audio file not found: {args.audio}")
        sys.exit(1)
    
    # Find production model
    script_dir = Path(__file__).parent
    ai_pipeline_dir = script_dir.parent
    production_dir = ai_pipeline_dir / "models" / "drum_classifier_production"
    
    model_path = args.model or str(production_dir / "best_multilabel_model_ema.pt")
    thresholds_path = args.thresholds or str(production_dir / "thresholds.json")
    
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found: {model_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("BEATSIGHT DRUM TRANSCRIPTION")
    print("=" * 60)
    print(f"Input: {args.audio}")
    print(f"Model: {model_path}")
    print(f"Thresholds: {thresholds_path}")
    print()
    
    total_start = time.time()
    
    # Import dependencies
    import librosa
    import torch
    
    # Step 1: Load audio
    print("[1/5] Loading audio...")
    audio, sr = librosa.load(args.audio, sr=44100, mono=False)
    
    # Handle mono/stereo
    if audio.ndim == 1:
        audio_mono = audio
        audio_stereo = np.stack([audio, audio])
    else:
        audio_mono = audio.mean(axis=0)
        audio_stereo = audio
    
    duration = len(audio_mono) / sr
    print(f"      Duration: {duration:.1f}s ({duration/60:.1f} min)")
    print(f"      Sample rate: {sr} Hz")
    print(f"      Channels: {'stereo' if audio.ndim > 1 else 'mono'}")
    
    # Step 2: Drum separation
    drums_audio = audio_mono  # Default to full audio
    
    if not args.skip_separation:
        print("\n[2/5] Separating drums (Demucs)...")
        sep_start = time.time()
        
        try:
            from separation.demucs_separator import DrumSeparator
            
            separator = DrumSeparator(
                model_name="htdemucs_ft",  # Fast model
                verbose=True,
            )
            
            drums_audio, timing = separator.separate(
                audio_stereo, 
                sr,
                return_timing=True,
            )
            
            sep_time = time.time() - sep_start
            print(f"      Separation complete: {sep_time:.1f}s")
            print(f"      Model: htdemucs_ft (2.5x faster)")
            
            # Save separated drums if requested
            if args.save_drums:
                import soundfile as sf
                sf.write(args.save_drums, drums_audio, sr)
                print(f"      Saved drums to: {args.save_drums}")
                
        except Exception as e:
            print(f"      WARNING: Separation failed: {e}")
            print(f"      Falling back to full mix (results may be less accurate)")
            drums_audio = audio_mono
    else:
        print("\n[2/5] Skipping separation (using input as drums)")
    
    # Step 3: Run transcription pipeline
    print("\n[3/5] Running transcription pipeline...")
    trans_start = time.time()
    
    from transcription.full_pipeline import DrumTranscriptionPipeline, PipelineConfig
    
    config = PipelineConfig(
        enable_count_estimation=True,
        enable_pitch_ranking=True,
        batch_size=64,
    )
    
    pipeline = DrumTranscriptionPipeline(
        multilabel_model_path=model_path,
        thresholds_path=thresholds_path,
        config=config,
    )
    
    result = pipeline.transcribe_audio(drums_audio.astype(np.float32), sr)
    trans_time = time.time() - trans_start
    
    print(f"      Transcription complete: {trans_time:.1f}s")
    print(f"      Onsets detected: {result.num_onsets}")
    print(f"      Events transcribed: {result.num_events}")
    
    # Step 4: Print results summary
    print("\n[4/5] Results Summary")
    print("-" * 40)
    
    total_time = time.time() - total_start
    print(f"Total processing time: {total_time:.1f}s")
    print(f"Real-time factor: {duration/total_time:.1f}x")
    print()
    
    print("Class distribution:")
    for label, count in sorted(result.class_counts.items(), key=lambda x: -x[1]):
        pct = count / result.num_events * 100 if result.num_events > 0 else 0
        bar = "=" * int(pct / 2)
        print(f"  {label:20s}: {count:5d} ({pct:5.1f}%) {bar}")
    
    # Step 5: Show sample events
    print("\n[5/5] Sample Events (first 30)")
    print("-" * 40)
    
    for i, event in enumerate(result.events[:30]):
        print(f"  {event.time:7.3f}s | {event.label:20s} | conf={event.confidence:.2f}")
    
    if len(result.events) > 30:
        print(f"  ... and {len(result.events) - 30} more events")
    
    # Save output
    if args.output:
        output_data = {
            "metadata": {
                "source_file": args.audio,
                "duration_seconds": duration,
                "sample_rate": sr,
                "num_onsets": result.num_onsets,
                "num_events": result.num_events,
                "processing_time_seconds": total_time,
                "model": model_path,
                "drum_separation": not args.skip_separation,
            },
            "class_counts": result.class_counts,
            "events": [
                {
                    "time": e.time,
                    "label": e.label,
                    "confidence": e.confidence,
                    "base_label": e.base_label,
                }
                for e in result.events
            ],
        }
        
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    print("\n" + "=" * 60)
    print("TRANSCRIPTION COMPLETE!")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    main()
