"""Quick diagnostic: check raw probabilities on test song."""
import torch
import numpy as np
import librosa
import sys

print("Loading model...", flush=True)
from transcription.multilabel_inference import load_model_checkpoint, DEFAULT_DRUM_COMPONENTS
model = load_model_checkpoint('runs/v5_multilabel_final_v3/best_multilabel_model_ema.pt', device='cuda')
model.eval()

print("Loading audio...", flush=True)
from pipeline.preprocessing import preprocess_audio
from separation.demucs_separator import separate_drums
audio_data, sr = preprocess_audio('../test_songs/0101 - Heir of Grief.flac')
drum_result = separate_drums((audio_data, sr), return_timing=True)
if isinstance(drum_result, tuple) and len(drum_result) == 2:
    drum_audio_tuple, _ = drum_result
    if isinstance(drum_audio_tuple, tuple):
        drum_audio, drum_sr = drum_audio_tuple
    else:
        drum_audio = drum_audio_tuple
        drum_sr = sr
else:
    drum_audio = drum_result
    drum_sr = sr
print(f"Audio: {len(drum_audio)/drum_sr:.1f}s @ {drum_sr}Hz", flush=True)

# Simple onset detection to get some onset times
from transcription.onset_detector import detect_onsets, refine_onsets
det = detect_onsets((drum_audio, drum_sr), sensitivity=60.0, use_adaptive=False)
raw_onsets = refine_onsets((drum_audio, sr), det.onsets)
onset_times = [o.time for o in raw_onsets]
print(f"Onsets: {len(onset_times)}", flush=True)

# Extract spectrograms using the same code as classify_batch
mel_fb = librosa.filters.mel(sr=sr, n_fft=2048, n_mels=128, fmax=8000)
window_ms = 100.0
window_samples = int(window_ms * sr / 1000)

spectrograms = []
for t in onset_times:
    center = int(t * sr)
    start = max(0, center - window_samples // 2)
    end = start + window_samples
    if end > len(drum_audio):
        end = len(drum_audio)
        start = max(0, end - window_samples)
    segment = drum_audio[start:end]
    if len(segment) < window_samples:
        segment = np.pad(segment, (0, window_samples - len(segment)))
    
    hop_length = max(1, len(segment) // 128)
    stft = np.abs(librosa.stft(segment.astype(np.float32), n_fft=2048, hop_length=hop_length))
    mel_spec = np.dot(mel_fb, stft)
    mel_db = librosa.amplitude_to_db(mel_spec, ref=np.max)
    
    if mel_db.shape[1] < 128:
        mel_db = np.pad(mel_db, ((0, 0), (0, 128 - mel_db.shape[1])), mode='constant')
    elif mel_db.shape[1] > 128:
        mel_db = mel_db[:, :128]
    
    mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
    spectrograms.append(mel_db.astype(np.float32))

print(f"Extracted {len(spectrograms)} spectrograms", flush=True)

# Run model
all_probs = []
for i in range(0, len(spectrograms), 256):
    batch = np.stack(spectrograms[i:i+256])
    x = torch.from_numpy(batch).float().unsqueeze(1).cuda()
    with torch.inference_mode():
        probs = torch.sigmoid(model(x)).cpu().numpy()
    all_probs.append(probs)
all_probs = np.concatenate(all_probs)

print(f"\n=== Raw probability stats (correct [0,1] normalization) ===", flush=True)
for i, name in enumerate(DEFAULT_DRUM_COMPONENTS):
    p = all_probs[:, i]
    above_03 = (p >= 0.3).sum()
    above_05 = (p >= 0.5).sum()
    above_07 = (p >= 0.7).sum()
    print(f"  {name:15s}: min={p.min():.3f} max={p.max():.3f} mean={p.mean():.3f} | "
          f">0.3:{above_03:4d} >0.5:{above_05:4d} >0.7:{above_07:4d}", flush=True)

# Show thresholds from file
import json
with open('runs/v5_multilabel_final_v3/thresholds.json') as f:
    th = json.load(f)['per_class_thresholds']
print(f"\n=== File thresholds vs max probability ===", flush=True)
for i, name in enumerate(DEFAULT_DRUM_COMPONENTS):
    t = th.get(name, 0.5)
    mx = all_probs[:, i].max()
    status = "PASS" if mx >= t else "BLOCKED"
    print(f"  {name:15s}: threshold={t:.2f}, max_prob={mx:.3f} -> {status}", flush=True)

print("\nDONE", flush=True)
