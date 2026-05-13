#!/usr/bin/env python3
"""Diagnostic: dump raw probabilities from the model on Demucs-separated audio."""
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.preprocessing import preprocess_audio
from pipeline.separation.demucs_separator import separate_drums
from pipeline.transcription.onset_detector import detect_onsets
from transcription.multilabel_inference import MultiLabelDrumClassifier
from training.multilabel.dataset import DEFAULT_DRUM_COMPONENTS

CLASSES = DEFAULT_DRUM_COMPONENTS
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--model", default="runs/v5_multilabel_final_v3_continued/best_multilabel_model_ema.pt")
parser.add_argument("--audio", default="../test_songs/0101 - Heir of Grief.flac")
_args = parser.parse_args()
model_path = _args.model
audio_path = _args.audio

# Load model  
clf = MultiLabelDrumClassifier(model_path=model_path)

# Process audio through Demucs (same as pipeline)
audio_data, sr = preprocess_audio(audio_path)
drum_audio_data, drum_sr = separate_drums((audio_data, sr))
print("Demucs separation done")

# Detect onsets
detection_result = detect_onsets((drum_audio_data, drum_sr), sensitivity=80)
onset_times = [o.time for o in detection_result.onsets]
print(f"Found {len(onset_times)} onsets")

# Get raw probabilities using the classifier's internal method
probs = clf._get_raw_probabilities_batch(
    drum_audio_data, drum_sr, onset_times, show_progress=True
)
print(f"Got probabilities for {probs.shape[0]} onsets (shape: {probs.shape})")

# Show per-class statistics
header = "{:<16} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
    "Class", "Mean", "Max", "p>0.3", "p>0.5", "p>0.7"
)
print("\n" + header)
print("-" * 64)
for i, cls in enumerate(CLASSES):
    col = probs[:, i]
    line = "{:<16} {:8.3f} {:8.3f} {:8d} {:8d} {:8d}".format(
        cls, col.mean(), col.max(),
        int((col > 0.3).sum()), int((col > 0.5).sum()), int((col > 0.7).sum())
    )
    print(line)

# For onsets classified as hihat, show crash/china probs
hh_closed_idx = CLASSES.index("hihat_closed")
crash_idx = CLASSES.index("crash")
china_idx = CLASSES.index("china")
hh_open_idx = CLASSES.index("hihat_open")

top_class = probs.argmax(axis=1)
hh_mask = (top_class == hh_closed_idx) | (top_class == hh_open_idx)

print(f"\n--- Onsets where top class is hihat (N={int(hh_mask.sum())}) ---")
crash_of_hh = probs[hh_mask, crash_idx]
china_of_hh = probs[hh_mask, china_idx]
print(f"  Their crash probs:  mean={crash_of_hh.mean():.3f}, max={crash_of_hh.max():.3f}, >0.3: {int((crash_of_hh>0.3).sum())}, >0.5: {int((crash_of_hh>0.5).sum())}")
print(f"  Their china probs:  mean={china_of_hh.mean():.3f}, max={china_of_hh.max():.3f}, >0.3: {int((china_of_hh>0.3).sum())}, >0.5: {int((china_of_hh>0.5).sum())}")

# Onsets where crash prob > 0.2 but got classified as something else
crash_potential = probs[:, crash_idx] > 0.2
print(f"\n--- Onsets with crash prob > 0.2 (N={int(crash_potential.sum())}) ---")
print("  Classified as (top class):")
for i, cls in enumerate(CLASSES):
    count = int((top_class[crash_potential] == i).sum())
    if count > 0:
        print(f"    {cls}: {count}")

china_potential = probs[:, china_idx] > 0.1
print(f"\n--- Onsets with china prob > 0.1 (N={int(china_potential.sum())}) ---")
print("  Classified as (top class):")
for i, cls in enumerate(CLASSES):
    count = int((top_class[china_potential] == i).sum())
    if count > 0:
        print(f"    {cls}: {count}")

# Distribution of max probability per onset (confidence)
max_probs = probs.max(axis=1)
print("\n--- Overall confidence distribution ---")
print(f"  Max prob mean: {max_probs.mean():.3f}")
print(f"  Max prob median: {np.median(max_probs):.3f}")
for t in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    print(f"  max_prob > {t}: {int((max_probs > t).sum())}")

# Show the crash probability histogram
print("\n--- Crash probability histogram (all onsets) ---")
bins = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
        (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
for lo, hi in bins:
    count = int(((probs[:, crash_idx] >= lo) & (probs[:, crash_idx] < hi)).sum())
    bar = "#" * (count // 10)
    print(f"  [{lo:.1f}-{hi:.1f}): {count:5d}  {bar}")

print("\n--- China probability histogram (all onsets) ---")
for lo, hi in bins:
    count = int(((probs[:, china_idx] >= lo) & (probs[:, china_idx] < hi)).sum())
    bar = "#" * (count // 10)
    print(f"  [{lo:.1f}-{hi:.1f}): {count:5d}  {bar}")

# CRITICAL: Show what crash hits look like — the highest-crash-prob onsets
print("\n--- Top 30 onsets by crash probability ---")
crash_ranking = np.argsort(probs[:, crash_idx])[::-1][:30]
print("{:<8} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
    "Onset#", "Crash", "China", "HH_C", "HH_O", "Kick", "TopClass"))
for idx in crash_ranking:
    tc = CLASSES[top_class[idx]]
    print("{:<8d} {:8.3f} {:8.3f} {:8.3f} {:8.3f} {:8.3f} {:>8}".format(
        idx, probs[idx, crash_idx], probs[idx, china_idx],
        probs[idx, hh_closed_idx], probs[idx, hh_open_idx],
        probs[idx, CLASSES.index("kick")], tc))

print("\n--- Top 30 onsets by china probability ---")
china_ranking = np.argsort(probs[:, china_idx])[::-1][:30]
print("{:<8} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
    "Onset#", "China", "Crash", "HH_C", "HH_O", "Kick", "TopClass"))
for idx in china_ranking:
    tc = CLASSES[top_class[idx]]
    print("{:<8d} {:8.3f} {:8.3f} {:8.3f} {:8.3f} {:8.3f} {:>8}".format(
        idx, probs[idx, china_idx], probs[idx, crash_idx],
        probs[idx, hh_closed_idx], probs[idx, hh_open_idx],
        probs[idx, CLASSES.index("kick")], tc))
