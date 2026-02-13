#!/usr/bin/env python3
"""
Synthesize drum samples from Lakh MIDI events.

This script reads the extracted MIDI drum events and synthesizes audio samples
using either:
1. A SoundFont via FluidSynth (if available)
2. Basic synthetic waveforms (fallback)
3. Recorded drum samples (if provided)

The goal is to generate training data for rare classes (china, splash, cross_stick)
to address class imbalance in the DrumClassifierCNNv5 model.

Usage:
    # Using synthetic drums (no external dependencies)
    python synthesize_lakh_drums.py \
        --events F:/datasets/lakh_midi/drum_events_rare_only.jsonl \
        --output-dir F:/datasets/lakh_synthesized \
        --feature-cache F:/feature_cache \
        --max-samples 50000 \
        --target-class china

    # Using SoundFont
    python synthesize_lakh_drums.py \
        --events F:/datasets/lakh_midi/drum_events_rare_only.jsonl \
        --soundfont F:/datasets/soundfonts/drums.sf2 \
        --output-dir F:/datasets/lakh_synthesized
"""

import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import numpy as np
import torch

try:
    import soundfile as sf
except ImportError:
    sf = None
    logger.error("soundfile not installed. Run: pip install soundfile")
    sys.exit(1)

try:
    import librosa
except ImportError:
    librosa = None
    logger.warning("librosa not installed - will use basic spectrogram")

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# GM MIDI note to class mapping
GM_DRUM_MAP = {
    37: "cross_stick",  # Side stick
    52: "china",        # Chinese cymbal
    55: "splash",       # Splash cymbal
}

# Synthesis parameters for each drum class
# These create distinctive but realistic-sounding synthetic drums
SYNTH_PARAMS = {
    "china": {
        "type": "metallic_noise",
        "attack": 0.001,
        "decay": 1.5,
        "sustain_level": 0.3,
        "release": 0.5,
        "freq_center": 4500,
        "freq_bandwidth": 3000,
        "partials": [1.0, 0.7, 0.5, 0.4, 0.3],  # Harmonic content
        "modulation_freq": 7.5,  # Slight warble
        "noise_level": 0.4,
    },
    "splash": {
        "type": "metallic_noise",
        "attack": 0.001,
        "decay": 0.8,
        "sustain_level": 0.2,
        "release": 0.3,
        "freq_center": 6000,
        "freq_bandwidth": 2500,
        "partials": [1.0, 0.5, 0.3],
        "modulation_freq": 12.0,
        "noise_level": 0.5,
    },
    "cross_stick": {
        "type": "transient_click",
        "attack": 0.0001,
        "decay": 0.15,
        "sustain_level": 0.1,
        "release": 0.1,
        "freq_center": 2500,
        "freq_bandwidth": 1500,
        "partials": [1.0, 0.3],
        "noise_level": 0.2,
    },
}


def synthesize_metallic_noise(
    duration: float,
    sr: int,
    params: dict,
    velocity: int = 100
) -> np.ndarray:
    """
    Synthesize a metallic cymbal sound using filtered noise + sinusoids.
    """
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    
    # Velocity scaling (0-127 -> 0.3-1.0)
    vel_scale = 0.3 + (velocity / 127.0) * 0.7
    
    # Generate filtered noise
    noise = np.random.randn(len(t)).astype(np.float32)
    
    # Bandpass filter the noise
    from scipy.signal import butter, filtfilt
    nyq = sr / 2
    low = max(100, params["freq_center"] - params["freq_bandwidth"]) / nyq
    high = min(nyq - 100, params["freq_center"] + params["freq_bandwidth"]) / nyq
    low = max(0.001, min(0.99, low))
    high = max(low + 0.01, min(0.999, high))
    
    b, a = butter(4, [low, high], btype='band')
    filtered_noise = filtfilt(b, a, noise).astype(np.float32)
    
    # Add harmonic partials
    fundamental = params["freq_center"]
    harmonic_content = np.zeros(len(t), dtype=np.float32)
    for i, amp in enumerate(params["partials"]):
        freq = fundamental * (1 + i * 0.1)  # Slight inharmonicity
        harmonic_content += amp * np.sin(2 * np.pi * freq * t).astype(np.float32)
    
    # Apply modulation (warble effect for cymbals)
    if "modulation_freq" in params:
        mod = 1 + 0.05 * np.sin(2 * np.pi * params["modulation_freq"] * t)
        harmonic_content = harmonic_content * mod.astype(np.float32)
    
    # Mix noise and harmonics
    signal = (params["noise_level"] * filtered_noise + 
              (1 - params["noise_level"]) * harmonic_content / len(params["partials"]))
    
    # Apply ADSR envelope
    env = create_adsr_envelope(t, params)
    signal = signal * env * vel_scale
    
    # Normalize
    max_val = np.abs(signal).max()
    if max_val > 0:
        signal = signal / max_val * 0.9
    
    return signal


def synthesize_transient_click(
    duration: float,
    sr: int,
    params: dict,
    velocity: int = 100
) -> np.ndarray:
    """
    Synthesize a short transient click (for cross-stick).
    """
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    
    # Velocity scaling
    vel_scale = 0.3 + (velocity / 127.0) * 0.7
    
    # Create a short burst of filtered noise
    noise = np.random.randn(len(t)).astype(np.float32)
    
    # Highpass to get click character
    from scipy.signal import butter, filtfilt
    nyq = sr / 2
    cutoff = params["freq_center"] / nyq
    cutoff = max(0.01, min(0.99, cutoff))
    b, a = butter(2, cutoff, btype='high')
    signal = filtfilt(b, a, noise).astype(np.float32)
    
    # Very fast envelope for transient
    attack_samples = int(sr * params["attack"])
    decay_samples = int(sr * params["decay"])
    
    env = np.zeros(len(t), dtype=np.float32)
    env[:attack_samples] = np.linspace(0, 1, attack_samples)
    env[attack_samples:attack_samples + decay_samples] = np.exp(
        -np.linspace(0, 5, decay_samples)
    )
    
    signal = signal * env * vel_scale
    
    # Normalize
    max_val = np.abs(signal).max()
    if max_val > 0:
        signal = signal / max_val * 0.9
    
    return signal


def create_adsr_envelope(t: np.ndarray, params: dict) -> np.ndarray:
    """Create an ADSR envelope."""
    sr = len(t) / t[-1] if t[-1] > 0 else 44100
    
    attack_samples = int(params["attack"] * sr)
    decay_samples = int(params["decay"] * sr)
    release_samples = int(params["release"] * sr)
    sustain_samples = max(0, len(t) - attack_samples - decay_samples - release_samples)
    
    # Attack
    attack = np.linspace(0, 1, attack_samples, dtype=np.float32) if attack_samples > 0 else np.array([], dtype=np.float32)
    
    # Decay
    decay = np.exp(-np.linspace(0, 3, decay_samples)).astype(np.float32) if decay_samples > 0 else np.array([], dtype=np.float32)
    decay = 1 - (1 - params["sustain_level"]) * (1 - decay)
    
    # Sustain
    sustain = np.full(sustain_samples, params["sustain_level"], dtype=np.float32)
    
    # Release
    release = params["sustain_level"] * np.exp(-np.linspace(0, 3, release_samples)).astype(np.float32) if release_samples > 0 else np.array([], dtype=np.float32)
    
    envelope = np.concatenate([attack, decay, sustain, release])
    
    # Ensure same length as input
    if len(envelope) < len(t):
        envelope = np.pad(envelope, (0, len(t) - len(envelope)), mode='constant')
    elif len(envelope) > len(t):
        envelope = envelope[:len(t)]
    
    return envelope


def synthesize_drum(
    drum_class: str,
    velocity: int = 100,
    sr: int = 22050,
    duration: float = 2.0
) -> np.ndarray:
    """
    Synthesize a drum sound for the given class.
    """
    if drum_class not in SYNTH_PARAMS:
        logger.warning(f"Unknown class {drum_class}, using china params")
        params = SYNTH_PARAMS["china"]
    else:
        params = SYNTH_PARAMS[drum_class]
    
    if params["type"] == "metallic_noise":
        return synthesize_metallic_noise(duration, sr, params, velocity)
    elif params["type"] == "transient_click":
        return synthesize_transient_click(duration, sr, params, velocity)
    else:
        raise ValueError(f"Unknown synthesis type: {params['type']}")


def compute_mel_spectrogram(
    audio: np.ndarray,
    sr: int = 22050,
    n_mels: int = 128,
    hop_length: int = 512,
    n_fft: int = 2048,
    target_frames: int = 128
) -> np.ndarray:
    """Compute mel spectrogram for audio."""
    if librosa is not None:
        mel = librosa.feature.melspectrogram(
            y=audio,
            sr=sr,
            n_mels=n_mels,
            hop_length=hop_length,
            n_fft=n_fft,
            fmin=20,
            fmax=8000
        )
        mel_db = librosa.power_to_db(mel, ref=np.max)
    else:
        # Basic fallback without librosa
        from scipy.signal import stft
        _, _, Zxx = stft(audio, sr, nperseg=n_fft, noverlap=n_fft-hop_length)
        mel = np.abs(Zxx) ** 2
        mel_db = 10 * np.log10(mel + 1e-10)
    
    # Normalize to 0-1
    mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
    
    # Pad or truncate
    if mel_db.shape[1] < target_frames:
        mel_db = np.pad(mel_db, ((0, 0), (0, target_frames - mel_db.shape[1])), mode='constant')
    else:
        mel_db = mel_db[:, :target_frames]
    
    return mel_db.astype(np.float32)


def load_midi_events(events_path: Path, target_class: Optional[str] = None) -> List[dict]:
    """Load MIDI events from JSONL file."""
    events = []
    with open(events_path, 'r') as f:
        for line in f:
            event = json.loads(line)
            if target_class is None or event["class"] == target_class:
                events.append(event)
    return events


def main():
    parser = argparse.ArgumentParser(description="Synthesize drums from Lakh MIDI events")
    parser.add_argument("--events", type=str, required=True,
                        help="Path to drum_events.jsonl file")
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Directory to save synthesized audio")
    parser.add_argument("--feature-cache", type=str, required=True,
                        help="Directory to save computed features")
    parser.add_argument("--target-class", type=str, default=None,
                        help="Only synthesize this class (china, splash, cross_stick)")
    parser.add_argument("--max-samples", type=int, default=50000,
                        help="Maximum number of samples per class")
    parser.add_argument("--sr", type=int, default=22050,
                        help="Sample rate for synthesis")
    parser.add_argument("--duration", type=float, default=1.5,
                        help="Duration of each synthesized sample in seconds")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without synthesizing")
    parser.add_argument("--save-audio", action="store_true",
                        help="Also save synthesized audio WAV files")
    
    args = parser.parse_args()
    
    events_path = Path(args.events)
    output_dir = Path(args.output_dir)
    feature_cache = Path(args.feature_cache)
    
    if not events_path.exists():
        logger.error(f"Events file not found: {events_path}")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_cache.mkdir(parents=True, exist_ok=True)
    
    # Load class mapping (12 classes, rimshot merged into snare)
    class_to_idx = {
        "china": 0, "crash": 1, "cross_stick": 2, "hihat_closed": 3,
        "hihat_open": 4, "hihat_pedal": 5, "kick": 6, "ride_bell": 7,
        "ride_bow": 8, "snare": 9, "splash": 10, "tom": 11
    }
    
    # Load events
    logger.info(f"Loading events from {events_path}")
    events = load_midi_events(events_path, args.target_class)
    
    # Count by class
    class_counts = Counter(e["class"] for e in events)
    logger.info(f"Found {len(events):,} events:")
    for cls, count in sorted(class_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {cls}: {count:,}")
    
    if args.dry_run:
        logger.info("[DRY RUN] Would synthesize samples for each class")
        return
    
    # Synthesize samples for each class
    new_file_ids = []
    new_labels = []
    
    for drum_class in class_counts.keys():
        if args.target_class and drum_class != args.target_class:
            continue
        
        class_events = [e for e in events if e["class"] == drum_class]
        
        # Limit samples
        if len(class_events) > args.max_samples:
            random.shuffle(class_events)
            class_events = class_events[:args.max_samples]
        
        logger.info(f"\nSynthesizing {len(class_events):,} samples for {drum_class}")
        
        for i, event in enumerate(class_events):
            if (i + 1) % 1000 == 0:
                logger.info(f"  Progress: {i+1}/{len(class_events)}")
            
            # Create unique ID
            event_hash = hashlib.md5(
                f"{event['midi_file']}:{event['time']}:{event['note']}".encode()
            ).hexdigest()[:12]
            feature_id = f"lakh_{drum_class}_{event_hash}"
            
            # Synthesize audio
            audio = synthesize_drum(
                drum_class,
                velocity=event.get("velocity", 100),
                sr=args.sr,
                duration=args.duration
            )
            
            # Optionally save audio
            if args.save_audio:
                audio_path = output_dir / drum_class / f"{feature_id}.wav"
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(audio_path, audio, args.sr)
            
            # Compute mel spectrogram
            mel = compute_mel_spectrogram(audio, sr=args.sr)
            
            # Save feature
            feature_path = feature_cache / f"{feature_id}.pt"
            torch.save(torch.from_numpy(mel), feature_path)
            
            new_file_ids.append(feature_id)
            new_labels.append(class_to_idx[drum_class])
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Synthesis complete!")
    logger.info(f"Generated {len(new_file_ids):,} features")
    
    # Save manifest for appending to dataset later
    manifest_path = output_dir / "synthesis_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump({
            "file_ids": new_file_ids,
            "labels": new_labels,
            "class_counts": dict(Counter(new_labels)),
            "source": "lakh_midi_synthesis"
        }, f, indent=2)
    
    logger.info(f"Manifest saved to {manifest_path}")
    logger.info(f"\nTo append to dataset, run:")
    logger.info(f"  python append_manifest.py --manifest {manifest_path} --dataset-dir <path>")


if __name__ == "__main__":
    main()
