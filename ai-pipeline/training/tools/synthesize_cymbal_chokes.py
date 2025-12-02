#!/usr/bin/env python3
"""
Synthesize cymbal choke samples from existing crash/china samples.

Cymbal chokes have a distinctive acoustic signature:
1. Normal attack transient
2. Abrupt amplitude cutoff (hand grabbing cymbal)
3. Very short sustain compared to normal cymbals

This script takes existing cymbal samples and applies DSP transforms to
simulate the choking effect, generating training data for the cymbal_choke class.

Usage:
    python synthesize_cymbal_chokes.py \
        --input-dir E:/data/raw/cymbal_samples \
        --output-dir E:/data/synthetic/cymbal_chokes \
        --num-variations 5

Author: BeatSight AI Pipeline
Date: November 2025
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

try:
    import librosa
    import soundfile as sf
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False
    print("Warning: librosa/soundfile not available")


# Cymbal classes that can be choked
CHOKEABLE_CLASSES = {
    "crash", "china", "splash", "ride_bow", "ride_bell",
    "hihat_open", "hihat_splash"
}


def apply_choke_envelope(
    audio: np.ndarray,
    sr: int,
    choke_time_ms: float = 100.0,
    fade_time_ms: float = 20.0,
    attack_preserve_ms: float = 50.0,
) -> np.ndarray:
    """
    Apply a choke envelope to cymbal audio.
    
    Args:
        audio: Input audio signal
        sr: Sample rate
        choke_time_ms: Time at which choke occurs (from start)
        fade_time_ms: Duration of the choke fadeout
        attack_preserve_ms: How much of the attack to preserve
        
    Returns:
        Choked audio signal
    """
    choke_sample = int(choke_time_ms * sr / 1000)
    fade_samples = int(fade_time_ms * sr / 1000)
    preserve_samples = int(attack_preserve_ms * sr / 1000)
    
    # Ensure we don't choke before the attack
    choke_sample = max(choke_sample, preserve_samples)
    
    # Ensure we don't exceed audio length
    choke_sample = min(choke_sample, len(audio) - fade_samples - 1)
    
    if choke_sample <= 0:
        return audio
    
    # Create output
    output = audio.copy()
    
    # Create fadeout envelope
    fade_envelope = np.linspace(1.0, 0.0, fade_samples)
    
    # Apply fade starting at choke point
    fade_start = choke_sample
    fade_end = min(choke_sample + fade_samples, len(output))
    actual_fade_len = fade_end - fade_start
    
    output[fade_start:fade_end] *= fade_envelope[:actual_fade_len]
    
    # Zero out everything after fade
    output[fade_end:] = 0.0
    
    return output


def apply_damping_resonance(
    audio: np.ndarray,
    sr: int,
    damping_freq: float = 2000.0,
    resonance: float = 0.3,
) -> np.ndarray:
    """
    Apply damping that simulates hand touching cymbal.
    
    The hand dampens high frequencies first, creating a
    characteristic "thud" quality.
    """
    from scipy import signal
    
    # Low-pass filter to simulate damping
    nyquist = sr / 2
    cutoff = damping_freq / nyquist
    cutoff = min(0.99, max(0.01, cutoff))  # Clamp to valid range
    
    b, a = signal.butter(2, cutoff, btype='low')
    
    # Apply filter
    filtered = signal.filtfilt(b, a, audio)
    
    # Mix with original based on resonance
    output = audio * resonance + filtered * (1 - resonance)
    
    return output


def add_muting_noise(
    audio: np.ndarray,
    sr: int,
    noise_level: float = 0.02,
    noise_duration_ms: float = 30.0,
    noise_start_ms: float = 100.0,
) -> np.ndarray:
    """
    Add subtle noise to simulate hand contact.
    """
    noise_start = int(noise_start_ms * sr / 1000)
    noise_samples = int(noise_duration_ms * sr / 1000)
    
    if noise_start + noise_samples > len(audio):
        return audio
    
    output = audio.copy()
    
    # Create short noise burst
    noise = np.random.randn(noise_samples) * noise_level
    
    # Apply quick envelope
    envelope = np.hanning(noise_samples)
    noise *= envelope
    
    # Add to audio
    output[noise_start:noise_start + noise_samples] += noise
    
    return output


def synthesize_choke(
    audio: np.ndarray,
    sr: int,
    variation_seed: Optional[int] = None,
) -> Tuple[np.ndarray, dict]:
    """
    Apply full choke synthesis with random variations.
    
    Returns:
        Tuple of (choked_audio, parameters_used)
    """
    if variation_seed is not None:
        random.seed(variation_seed)
        np.random.seed(variation_seed)
    
    # Randomize parameters for variety
    params = {
        "choke_time_ms": random.uniform(80, 200),
        "fade_time_ms": random.uniform(15, 40),
        "attack_preserve_ms": random.uniform(30, 70),
        "damping_freq": random.uniform(1500, 3000),
        "resonance": random.uniform(0.2, 0.5),
        "noise_level": random.uniform(0.01, 0.03),
    }
    
    # Apply choke envelope
    output = apply_choke_envelope(
        audio, sr,
        choke_time_ms=params["choke_time_ms"],
        fade_time_ms=params["fade_time_ms"],
        attack_preserve_ms=params["attack_preserve_ms"],
    )
    
    # Apply damping resonance
    try:
        output = apply_damping_resonance(
            output, sr,
            damping_freq=params["damping_freq"],
            resonance=params["resonance"],
        )
    except ImportError:
        pass  # scipy not available
    
    # Optionally add muting noise
    if random.random() < 0.5:
        output = add_muting_noise(
            output, sr,
            noise_level=params["noise_level"],
            noise_duration_ms=30.0,
            noise_start_ms=params["choke_time_ms"] - 10,
        )
        params["has_muting_noise"] = True
    else:
        params["has_muting_noise"] = False
    
    # Normalize
    max_val = np.abs(output).max()
    if max_val > 0:
        output = output / max_val * 0.9
    
    return output, params


def find_cymbal_samples(input_dir: Path) -> List[Tuple[Path, str]]:
    """Find cymbal audio files that can be used for choke synthesis."""
    samples = []
    
    for ext in ["*.wav", "*.flac", "*.mp3", "*.ogg"]:
        for audio_file in input_dir.rglob(ext):
            # Try to determine class from filename or path
            name_lower = audio_file.stem.lower()
            parent_lower = audio_file.parent.name.lower()
            
            detected_class = None
            for cymbal_class in CHOKEABLE_CLASSES:
                if cymbal_class.replace("_", "") in name_lower or \
                   cymbal_class.replace("_", "") in parent_lower or \
                   cymbal_class in name_lower or \
                   cymbal_class in parent_lower:
                    detected_class = cymbal_class
                    break
            
            if detected_class:
                samples.append((audio_file, detected_class))
    
    return samples


def main():
    parser = argparse.ArgumentParser(
        description="Synthesize cymbal choke samples from existing cymbal audio"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        required=True,
        help="Directory containing cymbal audio samples",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Directory to write synthesized choke samples",
    )
    parser.add_argument(
        "--num-variations",
        type=int,
        default=3,
        help="Number of choke variations per input sample",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Output sample rate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list files, don't process",
    )
    
    args = parser.parse_args()
    
    if not HAS_AUDIO:
        print("Error: librosa and soundfile are required")
        print("Install with: pip install librosa soundfile")
        return
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists():
        print(f"Error: Input directory not found: {input_dir}")
        return
    
    # Find cymbal samples
    print(f"Searching for cymbal samples in: {input_dir}")
    samples = find_cymbal_samples(input_dir)
    
    if not samples:
        print("No cymbal samples found!")
        print(f"Looking for classes: {CHOKEABLE_CLASSES}")
        return
    
    print(f"Found {len(samples)} cymbal samples")
    
    # Group by class
    by_class = {}
    for path, cls in samples:
        if cls not in by_class:
            by_class[cls] = []
        by_class[cls].append(path)
    
    print("\nSamples by class:")
    for cls, paths in sorted(by_class.items()):
        print(f"  {cls}: {len(paths)}")
    
    if args.dry_run:
        print("\nDry run - not processing")
        return
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process samples
    total_generated = 0
    sample_idx = 0
    
    for sample_path, original_class in samples:
        try:
            # Load audio
            audio, sr = librosa.load(sample_path, sr=args.sample_rate, mono=True)
            
            if len(audio) < sr * 0.1:  # Skip very short samples
                continue
            
            # Generate variations
            for var_idx in range(args.num_variations):
                choked_audio, params = synthesize_choke(
                    audio, sr,
                    variation_seed=hash(f"{sample_path}_{var_idx}") % (2**31)
                )
                
                # Create output filename with unique index to avoid overwrites
                # Include sample_idx to differentiate same-named files from different paths
                output_name = f"choke_{original_class}_{sample_idx:04d}_{sample_path.stem}_v{var_idx}.wav"
                output_path = output_dir / output_name
                
                # Save
                sf.write(output_path, choked_audio, sr)
                total_generated += 1
                
            sample_idx += 1
                
            if total_generated % 100 == 0:
                print(f"  Generated {total_generated} samples...")
                
        except Exception as e:
            print(f"Error processing {sample_path}: {e}")
            continue
    
    print(f"\nGenerated {total_generated} cymbal choke samples")
    print(f"Output directory: {output_dir}")
    
    # Create labels file
    labels_path = output_dir / "labels.json"
    labels = {
        "class": "cymbal_choke",
        "class_index": 21,  # Index for cymbal_choke in 22-class model
        "num_samples": total_generated,
        "source": "synthetic",
        "source_classes": list(by_class.keys()),
    }
    
    import json
    with open(labels_path, 'w') as f:
        json.dump(labels, f, indent=2)
    
    print(f"Labels saved to: {labels_path}")


if __name__ == "__main__":
    main()
