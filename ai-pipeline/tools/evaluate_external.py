#!/usr/bin/env python3
"""
External Benchmark Evaluation for Multi-Label Drum Classifier

This script evaluates the trained model on external datasets that were NOT
used during training to validate "best in class" claims.

Supported External Datasets:
- ENST-Drums: Real recordings with annotations
- IDMT-SMT-Drums: Synthesized drums with annotations

Usage:
    # Evaluate on ENST-Drums
    python tools/evaluate_external.py \
        --model runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt \
        --thresholds runs/v5_multilabel_final_v2/thresholds.json \
        --dataset enst \
        --data-dir data/raw/ENST-Drums

    # Evaluate on IDMT-SMT-Drums
    python tools/evaluate_external.py \
        --model runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt \
        --dataset idmt \
        --data-dir data/raw/idmt_smt_drums_v2

Note: External datasets must be downloaded separately. See docs for instructions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import torch
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.models.cnn_v5 import cnn_v5_large
from training.multilabel.dataset import DEFAULT_DRUM_COMPONENTS

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

CLASS_NAMES = DEFAULT_DRUM_COMPONENTS[:12]


def load_model(model_path: str, device: str = "cuda") -> torch.nn.Module:
    """Load the trained model."""
    print(f"Loading model: {model_path}")
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    
    model = cnn_v5_large(num_classes=12)
    
    # Get state dict
    if 'model_state_dict' in checkpoint:
        state_dict = checkpoint['model_state_dict']
    elif 'ema_state_dict' in checkpoint:
        ema = checkpoint['ema_state_dict']
        state_dict = ema.get('ema_model', ema)
    else:
        state_dict = checkpoint
    
    # Remove backbone prefix
    cleaned = {k.replace('backbone.', ''): v for k, v in state_dict.items()}
    model.load_state_dict(cleaned, strict=False)
    
    model.to(device)
    model.eval()
    return model


def load_thresholds(thresholds_path: str) -> Dict[str, float]:
    """Load per-class thresholds."""
    if not os.path.exists(thresholds_path):
        return {cls: 0.5 for cls in CLASS_NAMES}
    
    with open(thresholds_path) as f:
        data = json.load(f)
    return data.get("per_class_thresholds", {cls: 0.5 for cls in CLASS_NAMES})


def extract_spectrogram(audio: np.ndarray, sr: int) -> np.ndarray:
    """Extract mel spectrogram for a short audio segment.
    
    CRITICAL: Must match production pipeline (ml_drum_classifier.py) exactly!
    - Sample rate: 22050 Hz
    - n_mels: 128
    - fmax: 8000 Hz
    - DYNAMIC hop_length to always get ~128 frames
    - Normalization: Min-Max to [0, 1]
    - Resize to exactly 128x128
    """
    n_mels = 128
    target_frames = 128
    fmax = 8000
    
    # Ensure minimum audio length
    min_samples = 1024
    if len(audio) < min_samples:
        audio = np.pad(audio, (0, min_samples - len(audio)))
    
    # CRITICAL: Dynamic hop_length to get exactly ~128 frames
    # This matches ml_drum_classifier.py: hop_length = len(window) // 128 + 1
    hop_length = len(audio) // target_frames + 1
    
    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_mels=n_mels, fmax=fmax, hop_length=hop_length
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    
    # Normalize to [0, 1] - MUST MATCH TRAINING!
    mel_min, mel_max = mel_db.min(), mel_db.max()
    if mel_max - mel_min > 1e-8:
        mel_db = (mel_db - mel_min) / (mel_max - mel_min)
    else:
        mel_db = np.zeros_like(mel_db)
    
    # Resize to exactly 128x128 (matches ml_drum_classifier.py)
    if mel_db.shape[1] != target_frames:
        mel_db = np.resize(mel_db, (n_mels, target_frames))
    
    return mel_db.astype(np.float32)


# ============================================================================
# ENST-Drums Dataset Handler
# ============================================================================

def load_enst_drums(data_dir: str) -> List[Dict[str, Any]]:
    """
    Load ENST-Drums dataset.
    
    Expected structure:
    ENST-Drums/
        drummer_1/
            audio/
                dry_mix/
                    *.wav
            annotation/
                *.txt
        drummer_2/
        ...
    
    Annotation format:
    onset_time    drum_label
    0.123         sd
    0.456         bd
    ...
    """
    data_dir = Path(data_dir)
    
    if not data_dir.exists():
        print(f"ERROR: Dataset directory not found: {data_dir}")
        print("Please download ENST-Drums and extract to this location.")
        return []
    
    samples = []
    
    # Look for drummer subdirectories
    for drummer_dir in data_dir.iterdir():
        if not drummer_dir.is_dir() or not drummer_dir.name.startswith('drummer'):
            continue
        
        # Use dry_mix audio (isolated drums without room ambience)
        audio_dir = drummer_dir / "audio" / "dry_mix"
        annotation_dir = drummer_dir / "annotation"
        
        if not audio_dir.exists():
            # Try alternative paths
            audio_dir = drummer_dir / "audio"
        
        if not audio_dir.exists() or not annotation_dir.exists():
            print(f"Skipping {drummer_dir.name}: missing audio or annotation folder")
            continue
        
        for annotation_file in annotation_dir.glob("*.txt"):
            # Find matching audio file
            audio_file = audio_dir / annotation_file.with_suffix('.wav').name
            
            if audio_file.exists():
                samples.append({
                    "audio_path": str(audio_file),
                    "annotation_path": str(annotation_file),
                    "drummer": drummer_dir.name,
                })
    
    print(f"Found {len(samples)} ENST-Drums samples")
    return samples


def parse_enst_annotation(annotation_path: str) -> List[Tuple[float, str]]:
    """Parse ENST-Drums annotation file."""
    events = []
    
    # Map ENST labels to our 12-class labels
    # ENST uses short codes: bd, sd, chh, ohh, etc.
    # Also has numbered variants: rc2, rc3, rc4, c1, c4, cr1, cr2, etc.
    label_map = {
        # Kick drum
        "bd": "kick",
        # Snare drum variants
        "sd": "snare",
        "sd-": "snare",  # Snare without snare wires
        "rs": "cross_stick",  # Rim shot / cross stick
        # Hi-hat variants
        "hh": "hihat_closed",
        "chh": "hihat_closed",
        "ohh": "hihat_open",
        "phh": "hihat_pedal",
        # Ride cymbal variants (ENST uses rc, rc2, rc3, rc4)
        "rc": "ride_bow",
        "rc1": "ride_bow",
        "rc2": "ride_bow",
        "rc3": "ride_bow",
        "rc4": "ride_bow",
        "rb": "ride_bell",
        # Crash cymbal variants (ENST uses c1, cs, c4, cr1, cr2, cr5)
        "cc": "crash",
        "c1": "crash",
        "c2": "crash",
        "c3": "crash",
        "c4": "crash",
        "cs": "crash",  # Crash splash?
        "cr1": "crash",
        "cr2": "crash",
        "cr3": "crash",
        "cr4": "crash",
        "cr5": "crash",
        # Other cymbals
        "ch": "china",
        "sp": "splash",
        "cb": "ride_bell",  # Cowbell → closest is ride_bell
        # Tom variants (ENST uses ht, mt, lt, ft, lmt, lft)
        "ht": "tom",
        "mt": "tom",
        "lt": "tom",
        "ft": "tom",
        "tt": "tom",
        "lmt": "tom",  # Low-mid tom
        "lft": "tom",  # Low-floor tom
        # Also handle longer names from filename parsing
        "snare": "snare",
        "bass": "kick",
        "kick": "kick",
        "tom": "tom",
        "ride": "ride_bow",
        "crash": "crash",
        "hi-hat": "hihat_closed",
        "hihat": "hihat_closed",
    }
    
    with open(annotation_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                try:
                    onset_time = float(parts[0])
                    raw_label = parts[1].lower()
                    label = label_map.get(raw_label, None)
                    if label:
                        events.append((onset_time, label))
                except ValueError:
                    continue
    
    return events


# ============================================================================
# IDMT-SMT-Drums Dataset Handler
# ============================================================================

def load_idmt_drums(data_dir: str) -> List[Dict[str, Any]]:
    """
    Load IDMT-SMT-Drums dataset.
    
    Expected structure:
    idmt_smt_drums_v2/
        audio/
            *.wav
        annotations/
            *.xml or *.txt
    """
    data_dir = Path(data_dir)
    
    if not data_dir.exists():
        print(f"ERROR: Dataset directory not found: {data_dir}")
        print("Please download IDMT-SMT-Drums and extract to this location.")
        return []
    
    samples = []
    
    audio_dir = data_dir / "audio"
    if audio_dir.exists():
        for audio_file in audio_dir.glob("*.wav"):
            samples.append({
                "audio_path": str(audio_file),
                "label_from_filename": True,  # IDMT uses filename conventions
            })
    
    # Also check for direct wav files
    for audio_file in data_dir.glob("*.wav"):
        samples.append({
            "audio_path": str(audio_file),
            "label_from_filename": True,
        })
    
    print(f"Found {len(samples)} IDMT samples")
    return samples


def parse_idmt_label(filename: str) -> str:
    """Parse drum label from IDMT filename."""
    # IDMT filenames often contain drum type like "kick_001.wav", "snare_drum_002.wav"
    name = filename.lower()
    
    if "kick" in name or "bd" in name:
        return "kick"
    elif "snare" in name or "sd" in name:
        return "snare"
    elif "hihat" in name or "hh" in name:
        return "hihat_closed"
    elif "tom" in name:
        return "tom"
    elif "crash" in name:
        return "crash"
    elif "ride" in name:
        return "ride_bow"
    
    return None


# ============================================================================
# Evaluation Functions
# ============================================================================

def evaluate_on_dataset(
    model: torch.nn.Module,
    samples: List[Dict[str, Any]],
    thresholds: Dict[str, float],
    device: str = "cuda",
    window_ms: float = 100.0,
) -> Dict[str, Any]:
    """
    Evaluate model on a dataset.
    
    For each annotated onset, extract a spectrogram and run inference.
    Compare predictions to ground truth.
    
    CRITICAL: Window extraction matches ml_drum_classifier.py exactly!
    - window_ms: 100ms (same as production default)
    - Asymmetric window: 1/4 before onset, 3/4 after onset
    - sr=22050 to match training
    """
    all_predictions = []
    all_labels = []
    
    # MUST match training sample rate!
    sr = 22050
    window_samples = int(window_ms * sr / 1000)
    
    for sample in tqdm(samples, desc="Evaluating"):
        audio_path = sample["audio_path"]
        
        if not os.path.exists(audio_path):
            continue
        
        # Load audio
        audio, sr = librosa.load(audio_path, sr=sr, mono=True)
        
        if "annotation_path" in sample:
            # Parse annotations
            events = parse_enst_annotation(sample["annotation_path"])
            
            for onset_time, true_label in events:
                # CRITICAL: Match ml_drum_classifier.py window extraction exactly!
                # start = center - window_samples // 4 (asymmetric: 1/4 before, 3/4 after)
                center = int(onset_time * sr)
                start = max(0, center - window_samples // 4)
                end = min(len(audio), center + window_samples)
                
                if end - start < 10:
                    continue
                
                segment = audio[start:end]
                spec = extract_spectrogram(segment, sr)
                
                # Run inference
                with torch.no_grad():
                    x = torch.from_numpy(spec).unsqueeze(0).unsqueeze(0).to(device)
                    logits = model(x)
                    probs = torch.sigmoid(logits).cpu().numpy()[0]
                
                # Apply thresholds
                pred_labels = set()
                for i, cls in enumerate(CLASS_NAMES):
                    if probs[i] >= thresholds.get(cls, 0.5):
                        pred_labels.add(cls)
                
                all_predictions.append(pred_labels)
                all_labels.append({true_label})
        
        elif sample.get("label_from_filename"):
            # Use filename as label (single-label samples)
            true_label = parse_idmt_label(os.path.basename(audio_path))
            
            if true_label is None:
                continue
            
            # Extract from beginning of file
            segment = audio[:window_samples] if len(audio) >= window_samples else audio
            if len(segment) < window_samples:
                segment = np.pad(segment, (0, window_samples - len(segment)))
            
            spec = extract_spectrogram(segment, sr)
            
            with torch.no_grad():
                x = torch.from_numpy(spec).unsqueeze(0).unsqueeze(0).to(device)
                logits = model(x)
                probs = torch.sigmoid(logits).cpu().numpy()[0]
            
            pred_labels = set()
            for i, cls in enumerate(CLASS_NAMES):
                if probs[i] >= thresholds.get(cls, 0.5):
                    pred_labels.add(cls)
            
            all_predictions.append(pred_labels)
            all_labels.append({true_label})
    
    # Compute metrics
    return compute_multilabel_metrics(all_predictions, all_labels)


def compute_multilabel_metrics(
    predictions: List[set],
    labels: List[set],
) -> Dict[str, Any]:
    """Compute multi-label classification metrics."""
    epsilon = 1e-8
    
    # Per-sample exact match
    exact_matches = sum(1 for p, l in zip(predictions, labels) if p == l)
    exact_accuracy = exact_matches / max(len(predictions), 1)
    
    # Micro metrics
    tp = 0
    fp = 0
    fn = 0
    
    for pred_set, label_set in zip(predictions, labels):
        tp += len(pred_set & label_set)
        fp += len(pred_set - label_set)
        fn += len(label_set - pred_set)
    
    micro_precision = tp / (tp + fp + epsilon)
    micro_recall = tp / (tp + fn + epsilon)
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall + epsilon)
    
    # Per-class metrics
    class_metrics = {}
    for cls in CLASS_NAMES:
        cls_tp = sum(1 for p, l in zip(predictions, labels) if cls in p and cls in l)
        cls_fp = sum(1 for p, l in zip(predictions, labels) if cls in p and cls not in l)
        cls_fn = sum(1 for p, l in zip(predictions, labels) if cls not in p and cls in l)
        
        cls_prec = cls_tp / (cls_tp + cls_fp + epsilon)
        cls_rec = cls_tp / (cls_tp + cls_fn + epsilon)
        cls_f1 = 2 * cls_prec * cls_rec / (cls_prec + cls_rec + epsilon)
        
        class_metrics[cls] = {
            "precision": round(cls_prec, 4),
            "recall": round(cls_rec, 4),
            "f1": round(cls_f1, 4),
            "support": cls_tp + cls_fn,
        }
    
    macro_f1 = np.mean([m["f1"] for m in class_metrics.values()])
    
    return {
        "num_samples": len(predictions),
        "exact_accuracy": round(exact_accuracy, 4),
        "micro_precision": round(micro_precision, 4),
        "micro_recall": round(micro_recall, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4),
        "per_class": class_metrics,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate multi-label drum classifier on external datasets"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="runs/v5_multilabel_final_v2/best_multilabel_model_ema.pt",
        help="Path to trained model checkpoint",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default="runs/v5_multilabel_final_v2/thresholds.json",
        help="Path to per-class thresholds JSON",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["enst", "idmt", "medleydb"],
        required=True,
        help="External dataset to evaluate on",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to dataset directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path for results JSON",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    
    args = parser.parse_args()
    
    if not HAS_LIBROSA:
        print("ERROR: librosa is required for external evaluation")
        sys.exit(1)
    
    # Validate paths
    if not os.path.exists(args.model):
        print(f"ERROR: Model not found: {args.model}")
        sys.exit(1)
    
    if not os.path.exists(args.data_dir):
        print(f"ERROR: Dataset directory not found: {args.data_dir}")
        print(f"Please download the {args.dataset.upper()} dataset and extract it.")
        sys.exit(1)
    
    print("="*60)
    print(f"EXTERNAL BENCHMARK: {args.dataset.upper()}")
    print("="*60)
    
    # Load model and thresholds
    model = load_model(args.model, args.device)
    thresholds = load_thresholds(args.thresholds)
    
    # Load dataset
    if args.dataset == "enst":
        samples = load_enst_drums(args.data_dir)
    elif args.dataset == "idmt":
        samples = load_idmt_drums(args.data_dir)
    else:
        print(f"Dataset {args.dataset} not yet supported")
        sys.exit(1)
    
    if not samples:
        print("No samples found in dataset")
        sys.exit(1)
    
    # Evaluate
    results = evaluate_on_dataset(model, samples, thresholds, args.device)
    
    # Print results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"Samples evaluated: {results['num_samples']}")
    print(f"Exact match accuracy: {results['exact_accuracy']:.2%}")
    print(f"Micro-F1: {results['micro_f1']:.4f}")
    print(f"Macro-F1: {results['macro_f1']:.4f}")
    print(f"Micro-Precision: {results['micro_precision']:.4f}")
    print(f"Micro-Recall: {results['micro_recall']:.4f}")
    
    print("\nPer-class F1:")
    for cls in CLASS_NAMES:
        m = results['per_class'].get(cls, {})
        if m.get('support', 0) > 0:
            print(f"  {cls}: {m['f1']:.4f} (support={m['support']})")
    
    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
