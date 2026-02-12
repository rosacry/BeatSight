#!/usr/bin/env python3
"""
Diagnostic: Capture raw model probabilities on actual Demucs-separated audio.

This bypasses the full pipeline and directly checks what probabilities
the model outputs for each class at every onset in the test song.
"""
import sys
import json
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch

CLASS_NAMES = [
    "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
    "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare", "splash", "tom",
]

def main():
    import librosa
    from transcription.multilabel_inference import MultiLabelDrumClassifier, load_model_checkpoint

    # Load both models on CPU
    models = {}
    for name, path in [
        ("old", "runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt"),
        ("new", "runs/v5_finetune_demucs/best_multilabel_model_ema.pt"),
    ]:
        print(f"Loading {name} model...")
        model = load_model_checkpoint(path, device="cpu", num_classes=12)
        model.eval()
        models[name] = model

    # Load the test song and separate with Demucs
    test_song = "../test_songs/0101 - Heir of Grief.flac"
    print(f"\nLoading test song: {test_song}")

    from pipeline.preprocessing import preprocess_audio
    audio_data, sample_rate = preprocess_audio(test_song, offset=60, duration=60)

    print(f"Audio: {len(audio_data)} samples, {sample_rate} Hz, {len(audio_data)/sample_rate:.1f}s")

    # Run Demucs separation
    print("Running Demucs separation...")
    from pipeline.separation.demucs_separator import separate_drums
    drum_audio, drum_sr = separate_drums((audio_data, sample_rate))
    print(f"Drum stem: {len(drum_audio)} samples, {drum_sr} Hz")

    # Detect onsets
    print("Detecting onsets...")
    from transcription.onset_detector import detect_onsets, refine_onsets
    detection_result = detect_onsets((drum_audio, drum_sr))
    refined_onsets = refine_onsets((drum_audio, drum_sr), detection_result.onsets)
    onset_times = [o.time if hasattr(o, 'time') else o[0] for o in refined_onsets]
    print(f"Found {len(onset_times)} onsets")

    # Resample to 22050 for spectrogram extraction (matching training)
    if drum_sr != 22050:
        drum_audio_22k = librosa.resample(drum_audio, orig_sr=drum_sr, target_sr=22050)
        sr = 22050
    else:
        drum_audio_22k = drum_audio
        sr = drum_sr

    # Extract spectrograms at each onset
    print("Extracting spectrograms...")
    spectrograms = []
    valid_onset_times = []

    for onset_time in onset_times:
        window_ms = 100.0
        window_samples = int(window_ms * sr / 1000)
        center = int(onset_time * sr)
        start = max(0, center - window_samples // 4)
        end = min(len(drum_audio_22k), center + window_samples)

        if end - start < 10:
            continue

        segment = drum_audio_22k[start:end]
        if len(segment) < window_samples:
            segment = np.pad(segment, (0, window_samples - len(segment)), mode='constant')

        hop_length = max(1, len(segment) // 128)
        mel_spec = librosa.feature.melspectrogram(
            y=segment.astype(np.float32), sr=sr, n_mels=128,
            fmax=8000, hop_length=hop_length,
        )
        mel_db = librosa.power_to_db(mel_spec, ref=np.max)

        if mel_db.shape[1] != 128:
            if mel_db.shape[1] < 128:
                mel_db = np.pad(mel_db, ((0, 0), (0, 128 - mel_db.shape[1])), mode='constant')
            else:
                mel_db = mel_db[:, :128]

        mel_min, mel_max = mel_db.min(), mel_db.max()
        if mel_max - mel_min > 1e-8:
            mel_db = (mel_db - mel_min) / (mel_max - mel_min)
        else:
            mel_db = np.zeros_like(mel_db)

        spectrograms.append(mel_db.astype(np.float32))
        valid_onset_times.append(onset_time)

    print(f"Extracted {len(spectrograms)} spectrograms")

    # Run both models and compare
    batch = np.stack(spectrograms)
    x = torch.from_numpy(batch).float().unsqueeze(1)  # (B, 1, 128, 128)

    for model_name, model in models.items():
        print(f"\n{'='*80}")
        print(f"  {model_name.upper()} MODEL - Raw probabilities on real Demucs audio")
        print(f"{'='*80}")

        with torch.inference_mode():
            logits = model(x)
            probs = torch.sigmoid(logits).numpy()

        # Per-class statistics
        print(f"\n  Per-class probability statistics (all {len(probs)} onsets):")
        print(f"  {'Class':<15} {'Mean':>8} {'Median':>8} {'Max':>8} {'Min':>8} {'StdDev':>8} {'> 0.3':>6} {'> 0.5':>6} {'> 0.7':>6}")
        print(f"  {'-'*85}")
        for idx, name in enumerate(CLASS_NAMES):
            p = probs[:, idx]
            above03 = (p > 0.3).sum()
            above05 = (p > 0.5).sum()
            above07 = (p > 0.7).sum()
            print(f"  {name:<15} {p.mean():>8.4f} {np.median(p):>8.4f} {p.max():>8.4f} {p.min():>8.4f} {p.std():>8.4f} {above03:>6} {above05:>6} {above07:>6}")

        # Show top detections for rare classes
        for rare_class, idx in [("china", 0), ("splash", 10), ("crash", 1)]:
            top5_indices = np.argsort(probs[:, idx])[-5:][::-1]
            print(f"\n  Top 5 {rare_class} probabilities:")
            for i in top5_indices:
                all_probs_str = ", ".join(f"{CLASS_NAMES[j]}={probs[i,j]:.3f}" for j in np.argsort(probs[i])[-4:][::-1])
                print(f"    t={valid_onset_times[i]:.3f}s: {rare_class}={probs[i,idx]:.4f} | top4: [{all_probs_str}]")


if __name__ == "__main__":
    main()
