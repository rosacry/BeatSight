#!/usr/bin/env python3
"""Debug benchmark predictions to understand why model outputs are so low."""

import numpy as np
import torch
import librosa
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.multilabel.dataset import DEFAULT_DRUM_COMPONENTS

CLASS_NAMES = DEFAULT_DRUM_COMPONENTS[:12]


def load_model(model_path: str, device: str = "cuda"):
    """Load model."""
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    model = cnn_v5_large(num_classes=12)
    
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'ema_state_dict' in checkpoint:
        ema = checkpoint['ema_state_dict']
        state_dict = ema.get('ema_model', ema)
    else:
        state_dict = checkpoint
    
    cleaned = {k.replace('backbone.', ''): v for k, v in state_dict.items()}
    model.load_state_dict(cleaned, strict=False)
    model.to(device)
    model.eval()
    return model


def extract_spec_eval_style(audio: np.ndarray, sr: int) -> np.ndarray:
    """Extract spectrogram the CORRECT way (matching production pipeline)."""
    n_mels = 128
    target_frames = 128
    fmax = 8000
    
    # Ensure minimum audio length
    min_samples = 1024
    if len(audio) < min_samples:
        audio = np.pad(audio, (0, min_samples - len(audio)))
    
    # CRITICAL: Dynamic hop_length to get exactly ~128 frames
    hop_length = len(audio) // target_frames + 1
    
    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_mels=n_mels, fmax=fmax, hop_length=hop_length
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    
    # Normalize to [0, 1]
    mel_min, mel_max = mel_db.min(), mel_db.max()
    if mel_max - mel_min > 1e-8:
        mel_db = (mel_db - mel_min) / (mel_max - mel_min)
    else:
        mel_db = np.zeros_like(mel_db)
    
    # Resize to exactly 128x128
    if mel_db.shape[1] != target_frames:
        mel_db = np.resize(mel_db, (n_mels, target_frames))
    
    return mel_db.astype(np.float32)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Load model
    model_path = "models/drum_classifier_production/best_multilabel_model_ema.pt"
    model = load_model(model_path, device)
    print(f"Model loaded: {model_path}")
    
    # Find an ENST sample
    enst_dir = Path("D:/data/raw/ENST-Drums")
    audio_dir = enst_dir / "drummer_1" / "audio" / "dry_mix"
    anno_dir = enst_dir / "drummer_1" / "annotation"
    
    # Use the snare sample
    audio_path = audio_dir / "001_hits_snare-drum_sticks_x6.wav"
    anno_path = anno_dir / "001_hits_snare-drum_sticks_x6.txt"
    
    print(f"\nAudio file: {audio_path}")
    print(f"Exists: {audio_path.exists()}")
    
    if not audio_path.exists():
        print("ERROR: File not found")
        return
    
    # Load audio at 22050 Hz
    sr = 22050
    audio, loaded_sr = librosa.load(str(audio_path), sr=sr, mono=True)
    print(f"\nAudio loaded: {len(audio)} samples, {len(audio)/sr:.2f} seconds")
    print(f"Audio stats: min={audio.min():.4f}, max={audio.max():.4f}, std={audio.std():.4f}")
    
    # Read annotation
    with open(anno_path) as f:
        annotations = [line.strip().split() for line in f if line.strip()]
    print(f"\nAnnotations ({len(annotations)} events):")
    for onset_time, label in annotations[:5]:
        print(f"  {onset_time}s: {label}")
    
    # Extract spectrogram at first onset (matching ml_drum_classifier.py window)
    first_onset = float(annotations[0][0])
    first_label = annotations[0][1]
    
    window_ms = 100.0
    window_samples = int(window_ms * sr / 1000)
    
    # Asymmetric window: 1/4 before, 3/4 after (matches ml_drum_classifier.py)
    center = int(first_onset * sr)
    start = max(0, center - window_samples // 4)
    end = min(len(audio), center + window_samples)
    segment = audio[start:end]
    
    print(f"\n--- SEGMENT AT {first_onset}s (label={first_label}) ---")
    print(f"Segment: {len(segment)} samples")
    print(f"Segment stats: min={segment.min():.4f}, max={segment.max():.4f}, std={segment.std():.4f}")
    
    # My spectrogram extraction
    spec = extract_spec_eval_style(segment, sr)
    print(f"\nSpectrogram (eval style): shape={spec.shape}")
    print(f"  min={spec.min():.4f}, max={spec.max():.4f}, mean={spec.mean():.4f}")
    print(f"  Non-zero ratio: {(spec > 0).sum() / spec.size:.2%}")
    
    # Run inference
    x = torch.from_numpy(spec).unsqueeze(0).unsqueeze(0).to(device)
    print(f"\nInput tensor: shape={x.shape}")
    
    with torch.no_grad():
        logits = model(x)
        probs = torch.sigmoid(logits).cpu().numpy()[0]
    
    print(f"\n--- RAW MODEL OUTPUTS ---")
    print(f"Logits: min={logits.min().item():.4f}, max={logits.max().item():.4f}")
    print(f"\nSigmoid probabilities:")
    for i, cls in enumerate(CLASS_NAMES):
        marker = "<<<" if cls == "snare" else ""
        print(f"  {cls:15s}: {probs[i]:.6f} {marker}")
    
    print(f"\nMax prob: {probs.max():.4f} at {CLASS_NAMES[probs.argmax()]}")
    
    # Now compare with a TRAINING sample to see the difference
    print("\n" + "="*60)
    print("COMPARING WITH TRAINING DATA SAMPLE")
    print("="*60)
    
    # Load a training sample
    training_manifest = Path("F:/manifests/multilabel_real_v3/egmd_manifest.json")
    if training_manifest.exists():
        import json
        with open(training_manifest) as f:
            manifest = json.load(f)
        
        # Find a snare sample
        snare_samples = [s for s in manifest['samples'][:1000] if 'snare' in s.get('labels', [])]
        if snare_samples:
            sample = snare_samples[0]
            print(f"\nTraining sample: {sample['id']}")
            print(f"Labels: {sample.get('labels', [])}")
            
            # Load the spectrogram
            spec_path = Path("F:/datasets/multilabel_real_v3") / sample['path']
            if spec_path.exists():
                train_spec = np.load(spec_path)
                print(f"Training spec: shape={train_spec.shape}")
                print(f"  min={train_spec.min():.4f}, max={train_spec.max():.4f}, mean={train_spec.mean():.4f}")
                print(f"  Non-zero ratio: {(train_spec > 0).sum() / train_spec.size:.2%}")
                
                # Run inference on training sample
                x_train = torch.from_numpy(train_spec.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    logits_train = model(x_train)
                    probs_train = torch.sigmoid(logits_train).cpu().numpy()[0]
                
                print(f"\nTraining sample predictions:")
                for i, cls in enumerate(CLASS_NAMES):
                    if probs_train[i] > 0.1:
                        print(f"  {cls:15s}: {probs_train[i]:.4f}")
    else:
        print("Training manifest not found, skipping comparison")


if __name__ == "__main__":
    main()
