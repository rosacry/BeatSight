"""
Diagnose ensemble classification by dumping raw probabilities.

This script runs the dual-model ensemble but outputs raw probabilities
BEFORE thresholding, so we can see what the models actually predict
on real-world audio. This answers: are hihat_open/ride_bell truly
absent, or just below threshold?

Usage:
  cd /c/github/BeatSight/ai-pipeline && PYTHONPATH=. python scripts/diagnose_ensemble_probs.py \
    --input "../test_songs/0101 - Heir of Grief.flac" \
    --clean-model runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt \
    --clean-thresholds runs/v5_multilabel_final_v3_continued/thresholds.json \
    --demucs-model runs/v5_demucs_only_finetune_lr2e5/best_multilabel_model_ema.pt \
    --demucs-thresholds runs/v5_demucs_only_finetune_lr2e5/thresholds_demucs_only.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transcription.multilabel_inference import MultiLabelDrumClassifier, DEFAULT_DRUM_COMPONENTS


def load_audio(path: str):
    """Load audio file."""
    import soundfile as sf
    audio, sr = sf.read(path, dtype='float32')
    if audio.ndim == 2:
        audio = audio.mean(axis=1)  # stereo to mono
    return audio, sr


def main():
    parser = argparse.ArgumentParser(description="Diagnose ensemble probabilities")
    parser.add_argument("--input", required=True, help="Audio file")
    parser.add_argument("--clean-model", required=True, help="Clean model path")
    parser.add_argument("--clean-thresholds", required=True, help="Clean thresholds JSON")
    parser.add_argument("--demucs-model", required=True, help="Demucs model path")
    parser.add_argument("--demucs-thresholds", required=True, help="Demucs thresholds JSON")
    parser.add_argument("--max-onsets", type=int, default=200, help="Max onsets to analyze")
    parser.add_argument("--device", default=None, help="Device: cuda, cpu, or auto (default: auto)")
    parser.add_argument("--demucs-audio", default=None, help="Pre-separated drums audio (skip Demucs)")
    args = parser.parse_args()

    if args.device:
        device = args.device
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load audio
    print(f"Loading audio: {args.input}")
    audio, sr = load_audio(args.input)
    duration = len(audio) / sr
    print(f"  Duration: {duration:.1f}s, SR: {sr}")

    # Separate with Demucs (or load pre-separated)
    if args.demucs_audio:
        print(f"Loading pre-separated drums: {args.demucs_audio}")
        demucs_audio, demucs_sr = load_audio(args.demucs_audio)
        if demucs_sr != sr:
            import librosa
            demucs_audio = librosa.resample(demucs_audio, orig_sr=demucs_sr, target_sr=sr)
        print(f"  Loaded, shape: {demucs_audio.shape}")
    else:
        print("Separating with Demucs (this takes ~30-60s on GPU, longer on CPU)...")
        from separation.demucs_separator import DrumSeparator
        separator = DrumSeparator(device=device)
        demucs_audio = separator.separate(audio, sr)
        print(f"  Separation complete, shape: {demucs_audio.shape}")
        # Free Demucs to reclaim GPU memory before loading classifiers
        del separator
        torch.cuda.empty_cache() if device == "cuda" else None
        print("  Freed Demucs model from GPU")

    # Detect onsets
    print("Detecting onsets...")
    from transcription.onset_detector import detect_onsets
    result = detect_onsets((demucs_audio, sr))
    onset_times = [o.time for o in result.onsets]
    n_onsets = len(onset_times)
    print(f"  Found {n_onsets} onsets")

    if args.max_onsets and n_onsets > args.max_onsets:
        print(f"  Analyzing first {args.max_onsets} onsets")
        onset_times = onset_times[:args.max_onsets]
        n_onsets = len(onset_times)

    # Load classifiers (Demucs model freed, so memory should be available)
    print("Loading clean model...")
    clean_cls = MultiLabelDrumClassifier(
        model_path=args.clean_model,
        threshold=0.5,
        thresholds_file=args.clean_thresholds,
        device=device,
    )

    print("Loading Demucs classifier model...")
    demucs_cls = MultiLabelDrumClassifier(
        model_path=args.demucs_model,
        threshold=0.5,
        thresholds_file=args.demucs_thresholds,
        device=device,
    )

    # Extract spectrograms and run inference for both models
    print(f"\nExtracting spectrograms and running inference on {n_onsets} onsets...")

    # Clean model on full-mix audio
    hybrid_specs, hybrid_valid, _ = clean_cls._extract_spectrograms_batch(
        audio, sr, onset_times, 100.0,
        silence_gate=False, label="hybrid",
    )
    hybrid_probs = clean_cls._run_batch_inference(hybrid_specs) if hybrid_specs else None

    # Demucs model on separated audio
    demucs_specs, demucs_valid, demucs_skipped = demucs_cls._extract_spectrograms_batch(
        demucs_audio, sr, onset_times, 100.0,
        silence_gate=True, label="demucs",
    )
    demucs_probs_arr = demucs_cls._run_batch_inference(demucs_specs) if demucs_specs else None

    # Build prob maps
    hybrid_prob_map = {}
    if hybrid_probs is not None:
        for i, idx in enumerate(hybrid_valid):
            hybrid_prob_map[idx] = hybrid_probs[i]

    demucs_prob_map = {}
    if demucs_probs_arr is not None:
        for i, idx in enumerate(demucs_valid):
            demucs_prob_map[idx] = demucs_probs_arr[i]

    # Analyze raw probabilities
    class_names = DEFAULT_DRUM_COMPONENTS
    hybrid_classes = {'kick', 'snare', 'hihat_closed', 'hihat_open', 'hihat_pedal',
                      'tom', 'cross_stick', 'ride_bow', 'ride_bell'}
    demucs_classes = {'crash', 'china', 'splash'}

    # Collect all probabilities per class
    hybrid_all_probs = defaultdict(list)
    demucs_all_probs = defaultdict(list)

    for onset_idx in range(n_onsets):
        if onset_idx in hybrid_prob_map:
            probs = hybrid_prob_map[onset_idx]
            for cls_idx, prob in enumerate(probs):
                name = class_names[cls_idx]
                if name in hybrid_classes:
                    hybrid_all_probs[name].append(float(prob))

        if onset_idx in demucs_prob_map:
            probs = demucs_prob_map[onset_idx]
            for cls_idx, prob in enumerate(probs):
                name = class_names[cls_idx]
                if name in demucs_classes:
                    demucs_all_probs[name].append(float(prob))

    # Print analysis
    print("\n" + "=" * 80)
    print("RAW PROBABILITY ANALYSIS (before thresholding)")
    print("=" * 80)

    print(f"\n{'='*80}")
    print("BODY DRUMS — Clean model on full-mix audio")
    print(f"{'='*80}")
    print(f"{'Class':<15} {'Thresh':>7} {'Mean':>7} {'Max':>7} {'P95':>7} {'P75':>7} {'P50':>7} {'P25':>7} {'>Thresh':>8} {'Total':>7}")
    print("-" * 90)
    
    for name in ['kick', 'snare', 'hihat_closed', 'hihat_open', 'hihat_pedal',
                  'tom', 'cross_stick', 'ride_bow', 'ride_bell']:
        probs = hybrid_all_probs.get(name, [])
        if not probs:
            print(f"{name:<15} {'N/A':>7}")
            continue
        arr = np.array(probs)
        thresh = clean_cls.per_class_thresholds.get(name, 0.5)
        above = np.sum(arr >= thresh)
        print(f"{name:<15} {thresh:>7.3f} {arr.mean():>7.3f} {arr.max():>7.3f} "
              f"{np.percentile(arr, 95):>7.3f} {np.percentile(arr, 75):>7.3f} "
              f"{np.percentile(arr, 50):>7.3f} {np.percentile(arr, 25):>7.3f} "
              f"{above:>8d} {len(arr):>7d}")

    print(f"\n{'='*80}")
    print("CYMBALS — Demucs model on separated audio")
    print(f"{'='*80}")
    print(f"{'Class':<15} {'Thresh':>7} {'Mean':>7} {'Max':>7} {'P95':>7} {'P75':>7} {'P50':>7} {'P25':>7} {'>Thresh':>8} {'Total':>7}")
    print("-" * 90)

    for name in ['crash', 'china', 'splash']:
        probs = demucs_all_probs.get(name, [])
        if not probs:
            print(f"{name:<15} {'N/A':>7}")
            continue
        arr = np.array(probs)
        thresh = demucs_cls.per_class_thresholds.get(name, 0.5)
        above = np.sum(arr >= thresh)
        print(f"{name:<15} {thresh:>7.3f} {arr.mean():>7.3f} {arr.max():>7.3f} "
              f"{np.percentile(arr, 95):>7.3f} {np.percentile(arr, 75):>7.3f} "
              f"{np.percentile(arr, 50):>7.3f} {np.percentile(arr, 25):>7.3f} "
              f"{above:>8d} {len(arr):>7d}")

    # Show distribution of probabilities for problem classes
    print(f"\n{'='*80}")
    print("PROBABILITY DISTRIBUTION for weak classes (hihat_open, ride_bell, china)")
    print(f"{'='*80}")
    
    for name in ['hihat_open', 'ride_bell', 'china']:
        source = hybrid_all_probs if name in hybrid_classes else demucs_all_probs
        probs = source.get(name, [])
        if not probs:
            print(f"\n{name}: No predictions available")
            continue
        
        arr = np.array(probs)
        thresh = (clean_cls if name in hybrid_classes else demucs_cls).per_class_thresholds.get(name, 0.5)
        
        print(f"\n{name} (threshold={thresh:.3f}):")
        # Histogram buckets
        buckets = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
                   (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
        for lo, hi in buckets:
            count = np.sum((arr >= lo) & (arr < hi))
            bar = "█" * min(count, 80)
            marker = " ← threshold" if lo <= thresh < hi else ""
            print(f"  [{lo:.1f}-{hi:.1f}): {count:>5d} {bar}{marker}")

    # Show top-confidence detections for each class
    print(f"\n{'='*80}")
    print("TOP 5 HIGHEST-CONFIDENCE DETECTIONS per class")
    print(f"{'='*80}")
    
    for name in class_names:
        source = hybrid_all_probs if name in hybrid_classes else demucs_all_probs
        probs = source.get(name, [])
        if not probs:
            continue
        
        # Find onset indices with highest probs
        all_onset_probs = []
        prob_source = hybrid_prob_map if name in hybrid_classes else demucs_prob_map
        cls_idx = class_names.index(name)
        for onset_idx, prob_arr in prob_source.items():
            if onset_idx < n_onsets:
                all_onset_probs.append((float(prob_arr[cls_idx]), onset_times[onset_idx]))
        
        all_onset_probs.sort(reverse=True)
        top5 = all_onset_probs[:5]
        
        thresh = (clean_cls if name in hybrid_classes else demucs_cls).per_class_thresholds.get(name, 0.5)
        above = sum(1 for p, _ in all_onset_probs if p >= thresh)
        print(f"\n{name} (thresh={thresh:.3f}, {above} above threshold):")
        for prob, time in top5:
            marker = "✓" if prob >= thresh else "✗"
            mins = int(time // 60)
            secs = time % 60
            print(f"  {marker} prob={prob:.4f} at {mins}:{secs:05.2f}")


if __name__ == "__main__":
    main()
