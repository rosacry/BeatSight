#!/usr/bin/env python3
"""
Integration Test for the Full Drum Transcription Pipeline

Tests the pipeline end-to-end with either:
1. A synthetic drum test audio (if no test file provided)
2. A real audio file (if --audio is specified)

Usage:
    python tools/test_pipeline.py
    python tools/test_pipeline.py --audio path/to/drums.wav
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_synthetic_drum_audio(sr: int = 44100, duration: float = 5.0) -> np.ndarray:
    """
    Generate a simple synthetic drum pattern for testing.
    
    This creates a short test audio with recognizable drum-like transients:
    - Bass frequencies at 0.0, 1.0, 2.0, 3.0, 4.0s (kick)
    - Mid frequencies at 0.5, 1.5, 2.5, 3.5s (snare)
    - High frequencies at 0.25, 0.75, 1.25... (hihat)
    
    This is NOT for accuracy testing, just for pipeline validation.
    """
    n_samples = int(sr * duration)
    audio = np.zeros(n_samples)
    
    def add_transient(audio, time, freq_low, freq_high, decay, amp=0.5):
        """Add a synthetic drum transient."""
        start = int(time * sr)
        length = int(0.1 * sr)  # 100ms transient
        if start + length > len(audio):
            length = len(audio) - start
        if length <= 0:
            return
        
        t = np.linspace(0, 0.1, length)
        envelope = np.exp(-decay * t)
        
        # Mix of frequencies
        wave = 0.6 * np.sin(2 * np.pi * freq_low * t)
        wave += 0.4 * np.sin(2 * np.pi * freq_high * t)
        if freq_high > 5000:  # Add noise for hi-hats
            wave += 0.3 * np.random.randn(length)
        
        audio[start:start+length] += amp * envelope * wave
    
    # Kick pattern (low freq ~80-100Hz)
    for t in [0.0, 1.0, 2.0, 3.0, 4.0]:
        add_transient(audio, t, 60, 100, 20, 0.8)
    
    # Snare pattern (mid freq ~200-500Hz + noise)
    for t in [0.5, 1.5, 2.5, 3.5]:
        add_transient(audio, t, 200, 300, 15, 0.6)
        # Add noise burst
        start = int(t * sr)
        length = int(0.05 * sr)
        if start + length < len(audio):
            audio[start:start+length] += 0.3 * np.random.randn(length) * np.exp(-30 * np.linspace(0, 0.05, length))
    
    # Hi-hat pattern (high freq ~8000-10000Hz)
    for i in range(20):
        t = i * 0.25  # Every 250ms
        if t < duration:
            add_transient(audio, t, 8000, 10000, 40, 0.3)
    
    # Normalize
    audio = audio / (np.abs(audio).max() + 1e-8) * 0.9
    
    return audio


def test_model_loading():
    """Test that the model loads correctly."""
    print("\n" + "="*60)
    print("TEST 1: Model Loading")
    print("="*60)
    
    model_path = "runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt"
    
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return False
    
    try:
        from transcription.multilabel_inference import MultiLabelDrumClassifier
        
        classifier = MultiLabelDrumClassifier(
            model_path=model_path,
            threshold=0.5,
            device="cuda" if __import__('torch').cuda.is_available() else "cpu"
        )
        
        print(f"[OK] Loaded model from {model_path}")
        print(f"  Device: {classifier.device}")
        print(f"  Classes: {len(classifier.components)}")
        
        # Quick inference test
        dummy_spec = np.random.randn(128, 128).astype(np.float32)
        result = classifier.classify_spectrogram(dummy_spec)
        print(f"  Test inference: {len(result)} classes detected")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thresholds_loading():
    """Test that thresholds file loads correctly."""
    print("\n" + "="*60)
    print("TEST 2: Thresholds Loading")
    print("="*60)
    
    thresholds_path = "runs/v5_multilabel_final_v2/thresholds.json"
    
    if not os.path.exists(thresholds_path):
        print(f"ERROR: Thresholds not found at {thresholds_path}")
        return False
    
    try:
        with open(thresholds_path) as f:
            data = json.load(f)
        
        per_class = data.get("per_class_thresholds", {})
        print(f"[OK] Loaded {len(per_class)} per-class thresholds")
        for cls, t in per_class.items():
            print(f"  {cls}: {t}")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to load thresholds: {e}")
        return False


def test_full_pipeline(audio_path: str = None):
    """Test the full transcription pipeline."""
    print("\n" + "="*60)
    print("TEST 3: Full Pipeline")
    print("="*60)
    
    model_path = "runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt"
    thresholds_path = "runs/v5_multilabel_final_v2/thresholds.json"
    
    try:
        from transcription.full_pipeline import DrumTranscriptionPipeline, PipelineConfig
        
        # Load thresholds
        per_class_thresholds = {}
        if os.path.exists(thresholds_path):
            with open(thresholds_path) as f:
                data = json.load(f)
            per_class_thresholds = data.get("per_class_thresholds", {})
        
        config = PipelineConfig(
            per_class_thresholds=per_class_thresholds,
            enable_count_estimation=True,
            enable_pitch_ranking=True,
        )
        
        print("Initializing pipeline...")
        pipeline = DrumTranscriptionPipeline(
            multilabel_model_path=model_path,
            thresholds_path=thresholds_path,
            config=config,
        )
        print("[OK] Pipeline initialized")
        
        # Get or generate audio
        if audio_path and os.path.exists(audio_path):
            print(f"\nLoading test audio: {audio_path}")
            audio, sr = librosa.load(audio_path, sr=None, mono=True)
        else:
            print("\nGenerating synthetic test audio...")
            sr = 44100
            audio = generate_synthetic_drum_audio(sr=sr, duration=5.0)
        
        print(f"  Audio duration: {len(audio)/sr:.2f}s")
        print(f"  Sample rate: {sr}")
        
        # Run transcription
        print("\nRunning transcription...")
        result = pipeline.transcribe_audio(audio, sr)
        
        print(f"\n[OK] Transcription complete!")
        print(f"  Duration: {result.audio_duration:.2f}s")
        print(f"  Onsets detected: {result.num_onsets}")
        print(f"  Events: {result.num_events}")
        print(f"  Processing time: {result.processing_time:.2f}s")
        
        # Print events
        print("\nFirst 20 events:")
        for event in result.events[:20]:
            print(f"  {event.time:.3f}s: {event.label} ({event.confidence:.2f})")
        
        # Print class counts
        print("\nClass counts:")
        for cls, count in sorted(result.class_counts.items()):
            print(f"  {cls}: {count}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inference_on_spectrograms():
    """Test batch inference on real spectrograms from the dataset."""
    print("\n" + "="*60)
    print("TEST 4: Batch Spectrogram Inference")
    print("="*60)
    
    model_path = "runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt"
    thresholds_path = "runs/v5_multilabel_final_v2/thresholds.json"
    batch_path = "F:/datasets/multilabel_real_v3/egmd/egmd_batches/features_batch_0.npy"
    labels_path = "F:/datasets/multilabel_real_v3/egmd/egmd_batches/labels_batch_0.npy"
    
    if not os.path.exists(batch_path):
        print(f"  Skip: Batch file not found at {batch_path}")
        return True
    
    try:
        from transcription.multilabel_inference import MultiLabelDrumClassifier
        
        # Load thresholds
        per_class_thresholds = {}
        if os.path.exists(thresholds_path):
            with open(thresholds_path) as f:
                data = json.load(f)
            per_class_thresholds = data.get("per_class_thresholds", {})
        
        classifier = MultiLabelDrumClassifier(
            model_path=model_path,
            threshold=0.5,
            per_class_thresholds=per_class_thresholds,
        )
        
        # Load batch
        specs = np.load(batch_path)
        labels = np.load(labels_path)
        print(f"  Loaded batch: {specs.shape} specs, {labels.shape} labels")
        
        # Test on first 100 samples
        n_test = min(100, len(specs))
        correct = 0
        total_labels = 0
        
        for i in range(n_test):
            spec = specs[i]
            # Specs are 2D (128, 128), classifier expects (128, 128) not (1, 128, 128)
            if spec.ndim == 3 and spec.shape[0] == 1:
                spec = spec[0]  # Remove channel dim if present
            
            detections = classifier.classify_spectrogram(spec)
            true_labels = set(np.where(labels[i] == 1)[0])
            pred_labels = set([classifier.components.index(k) for k in detections.keys()])
            
            # Count hits
            for idx in true_labels:
                total_labels += 1
                if idx in pred_labels:
                    correct += 1
        
        recall = correct / max(total_labels, 1)
        print(f"  [OK] Tested {n_test} samples")
        print(f"    Label recall: {recall:.2%} ({correct}/{total_labels})")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Batch inference failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=str, default=None, help="Test audio file")
    args = parser.parse_args()
    
    print("="*60)
    print("DRUM TRANSCRIPTION PIPELINE INTEGRATION TEST")
    print("="*60)
    
    results = {}
    
    results["model_loading"] = test_model_loading()
    results["thresholds_loading"] = test_thresholds_loading()
    results["full_pipeline"] = test_full_pipeline(args.audio)
    results["batch_inference"] = test_inference_on_spectrograms()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
