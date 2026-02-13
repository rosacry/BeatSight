#!/usr/bin/env python3
"""
Quick verification script to test the drum classifier on unseen audio files.

This script processes audio files through the full pipeline and outputs
the classified drum hits for manual verification.

Usage:
    cd /c/github/BeatSight/ai-pipeline
    PYTHONPATH=. python training/tools/verify_on_unseen.py --audio /path/to/song.mp3

    # Or with multiple files
    PYTHONPATH=. python training/tools/verify_on_unseen.py \
        --audio song1.mp3 song2.mp3 song3.mp3 \
        --output verification_results.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter

import numpy as np
import torch
import librosa

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom"
]


def load_model(checkpoint_path: str, v5_size: str = "large", device: str = "cuda"):
    """Load the trained v5 model."""
    from training.models.cnn_v5 import DrumClassifierCNNv5
    
    model = DrumClassifierCNNv5(num_classes=12, size=v5_size)
    
    checkpoint = torch.load(checkpoint_path, map_location=device)
    
    # Handle different checkpoint formats
    if "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
    elif "ema_state_dict" in checkpoint:
        state_dict = checkpoint["ema_state_dict"]
    else:
        state_dict = checkpoint
    
    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()
    
    return model


def extract_mel_spectrogram(audio: np.ndarray, sr: int, onset_time: float, 
                            window_ms: float = 100.0) -> torch.Tensor:
    """Extract 128x128 mel spectrogram around an onset."""
    window_samples = int(window_ms * sr / 1000)
    center = int(onset_time * sr)
    
    # Window: 25% before onset, 75% after (capture attack and sustain)
    start = max(0, center - window_samples // 4)
    end = min(len(audio), center + 3 * window_samples // 4)
    
    if end - start < 100:
        return None
    
    window = audio[start:end]
    
    # Compute mel spectrogram
    mel_spec = librosa.feature.melspectrogram(
        y=window, sr=sr, n_mels=128, fmax=8000,
        hop_length=max(1, len(window) // 128)
    )
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
    
    # Normalize
    mel_min, mel_max = mel_spec_db.min(), mel_spec_db.max()
    mel_spec_norm = (mel_spec_db - mel_min) / (mel_max - mel_min + 1e-8)
    
    # Resize to 128x128
    if mel_spec_norm.shape[1] != 128:
        from scipy.ndimage import zoom
        zoom_factors = (1.0, 128 / mel_spec_norm.shape[1])
        mel_spec_norm = zoom(mel_spec_norm, zoom_factors, order=1)
    
    # Ensure exact shape
    mel_spec_norm = mel_spec_norm[:128, :128]
    if mel_spec_norm.shape != (128, 128):
        padded = np.zeros((128, 128))
        h, w = mel_spec_norm.shape
        padded[:h, :w] = mel_spec_norm
        mel_spec_norm = padded
    
    return torch.from_numpy(mel_spec_norm).float().unsqueeze(0).unsqueeze(0)


def detect_onsets_simple(audio: np.ndarray, sr: int) -> List[float]:
    """Simple onset detection using librosa."""
    onset_frames = librosa.onset.onset_detect(
        y=audio, sr=sr, hop_length=512, backtrack=True,
        pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.07, wait=5
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=512)
    return onset_times.tolist()


def classify_audio(audio_path: str, model, device: str = "cuda",
                   max_onsets: int = 500) -> Dict:
    """Classify drum hits in an audio file."""
    print(f"\n{'='*60}")
    print(f"Processing: {audio_path}")
    print(f"{'='*60}")
    
    # Load audio
    audio, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = len(audio) / sr
    print(f"Duration: {duration:.1f}s, Sample rate: {sr}")
    
    # Detect onsets
    print("Detecting onsets...")
    onsets = detect_onsets_simple(audio, sr)
    print(f"Found {len(onsets)} onsets")
    
    if len(onsets) > max_onsets:
        print(f"Limiting to first {max_onsets} onsets")
        onsets = onsets[:max_onsets]
    
    # Classify each onset
    print("Classifying...")
    results = []
    class_counts = Counter()
    
    with torch.no_grad():
        for i, onset_time in enumerate(onsets):
            mel = extract_mel_spectrogram(audio, sr, onset_time)
            if mel is None:
                continue
            
            mel = mel.to(device)
            logits = model(mel)
            probs = torch.softmax(logits, dim=1)
            
            pred_class = probs.argmax(dim=1).item()
            confidence = probs[0, pred_class].item()
            
            class_name = CLASS_NAMES[pred_class]
            class_counts[class_name] += 1
            
            results.append({
                "time": round(onset_time, 3),
                "class": class_name,
                "confidence": round(confidence, 3),
                "top3": [
                    (CLASS_NAMES[idx], round(probs[0, idx].item(), 3))
                    for idx in probs[0].argsort(descending=True)[:3].tolist()
                ]
            })
    
    # Summary
    print(f"\nClassification Summary ({len(results)} hits):")
    print("-" * 40)
    for class_name in CLASS_NAMES:
        count = class_counts[class_name]
        pct = 100 * count / len(results) if results else 0
        bar = "█" * int(pct / 5)
        print(f"  {class_name:15} {count:4d} ({pct:5.1f}%) {bar}")
    
    # Show first 20 hits for manual verification
    print(f"\nFirst 20 hits (for manual verification):")
    print("-" * 60)
    for hit in results[:20]:
        top3_str = ", ".join([f"{c}:{p:.2f}" for c, p in hit["top3"]])
        print(f"  {hit['time']:6.2f}s  {hit['class']:15}  conf={hit['confidence']:.2f}  [{top3_str}]")
    
    return {
        "file": str(audio_path),
        "duration": round(duration, 2),
        "num_onsets": len(onsets),
        "num_classified": len(results),
        "class_distribution": dict(class_counts),
        "hits": results
    }


def main():
    parser = argparse.ArgumentParser(description="Verify drum classifier on unseen audio")
    parser.add_argument("--audio", nargs="+", required=True, help="Audio file(s) to process")
    parser.add_argument("--checkpoint", default="runs/v5_phase2/checkpoints/best_checkpoint.pth",
                        help="Path to model checkpoint")
    parser.add_argument("--v5-size", default="large", choices=["small", "medium", "large"])
    parser.add_argument("--device", default="cuda", help="Torch device")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--max-onsets", type=int, default=500, help="Max onsets per file")
    
    args = parser.parse_args()
    
    # Check checkpoint exists
    if not Path(args.checkpoint).exists():
        print(f"ERROR: Checkpoint not found: {args.checkpoint}")
        sys.exit(1)
    
    # Load model
    print(f"Loading model from {args.checkpoint}...")
    device = args.device if torch.cuda.is_available() else "cpu"
    model = load_model(args.checkpoint, args.v5_size, device)
    print(f"Model loaded on {device}")
    
    # Process each audio file
    all_results = []
    for audio_path in args.audio:
        if not Path(audio_path).exists():
            print(f"WARNING: File not found: {audio_path}")
            continue
        
        try:
            result = classify_audio(audio_path, model, device, args.max_onsets)
            all_results.append(result)
        except Exception as e:
            print(f"ERROR processing {audio_path}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save results if requested
    if args.output and all_results:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    # Final summary
    print(f"\n{'='*60}")
    print("VERIFICATION COMPLETE")
    print(f"{'='*60}")
    print(f"Processed {len(all_results)} files")
    print("\nNext steps:")
    print("1. Listen to the audio files")
    print("2. Check if the classifications match what you hear")
    print("3. Pay attention to:")
    print("   - Are kicks detected as kicks?")
    print("   - Are hi-hats detected as hi-hats?")
    print("   - Are cymbals (crash/china/splash) distinguishable?")
    print("   - Do rare classes (china, splash) appear when expected?")


if __name__ == "__main__":
    main()
