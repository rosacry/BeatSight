#!/usr/bin/env python3
"""
Offline Augmentation Script for Rare Drum Classes

This script generates augmented versions of rare class samples (china, splash, rimshot)
to help balance the training dataset. It performs audio-domain augmentation on the
source audio files and saves new clips with modified spectrograms.

Augmentation techniques:
- Pitch shifting (±2 semitones)
- Time stretching (0.9x - 1.1x)
- Gain variation (±3dB)
- Noise injection (SNR 20-40dB)
- EQ variation (random shelf filters)

Target: Bring each rare class to at least 50K samples for effective training.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import signal
import sys
import threading
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import hashlib
import uuid

import numpy as np
import torch
import torchaudio
from tqdm import tqdm

# Global flag for graceful interruption
_interrupt_requested = False
_pause_lock = threading.Lock()
_paused = False


def signal_handler(signum, frame):
    """Handle Ctrl+C for graceful interruption."""
    global _interrupt_requested
    if _interrupt_requested:
        print("\n\nForce quit requested. Exiting immediately...")
        sys.exit(1)
    _interrupt_requested = True
    print("\n\n" + "="*60)
    print("INTERRUPT RECEIVED - Will stop after current file")
    print("Press Ctrl+C again to force quit")
    print("Progress will be saved for resume")
    print("="*60 + "\n")


def check_pause():
    """Check if pause was requested and wait if so."""
    global _paused
    while _paused:
        pass  # Busy wait (simple approach)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Target counts for rare classes (based on prod_v5_fixed_20251212 dataset)
# Note: rimshot was merged into snare class (detected via post-processing now)
TARGET_COUNTS = {
    'china': 50000,      # From 2,081 → 50K (24x augmentation)
    'splash': 50000,     # From 6,550 → 50K (8x augmentation)
}

# Classes to augment (12-class model - rimshot merged into snare)
RARE_CLASSES = ['china', 'splash']


class AudioAugmenter:
    """Audio augmentation pipeline for drum samples - optimized for speed."""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        # Pre-create resamplers for common pitch shifts (much faster than sox)
        self._resamplers = {}
        
    def _get_resampler(self, factor: float) -> torchaudio.transforms.Resample:
        """Get cached resampler for speed."""
        key = round(factor, 3)
        if key not in self._resamplers:
            self._resamplers[key] = torchaudio.transforms.Resample(
                orig_freq=int(self.sample_rate * factor),
                new_freq=self.sample_rate
            )
        return self._resamplers[key]
        
    def pitch_shift(self, waveform: torch.Tensor, semitones: float) -> torch.Tensor:
        """Shift pitch by semitones - fast resampling method."""
        if abs(semitones) < 0.1:
            return waveform
        # Fast pitch shift via resampling (changes duration slightly, acceptable for drums)
        factor = 2 ** (semitones / 12)
        resampler = self._get_resampler(factor)
        return resampler(waveform)
    
    def time_stretch(self, waveform: torch.Tensor, rate: float) -> torch.Tensor:
        """Stretch time by rate factor - fast interpolation method."""
        if abs(rate - 1.0) < 0.01:
            return waveform
        # Fast time stretch via interpolation
        target_len = int(waveform.shape[-1] / rate)
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        stretched = torch.nn.functional.interpolate(
            waveform.unsqueeze(0), size=target_len, mode='linear', align_corners=False
        ).squeeze(0)
        if stretched.dim() > 1 and stretched.shape[0] == 1:
            pass  # Keep channel dim
        return stretched
    
    def add_gain(self, waveform: torch.Tensor, gain_db: float) -> torch.Tensor:
        """Apply gain in dB."""
        gain_linear = 10 ** (gain_db / 20)
        return waveform * gain_linear
    
    def add_noise(self, waveform: torch.Tensor, snr_db: float) -> torch.Tensor:
        """Add Gaussian noise at specified SNR."""
        signal_power = waveform.pow(2).mean()
        noise_power = signal_power / (10 ** (snr_db / 10))
        noise = torch.randn_like(waveform) * torch.sqrt(noise_power)
        return waveform + noise
    
    def apply_eq(self, waveform: torch.Tensor, low_gain_db: float, high_gain_db: float) -> torch.Tensor:
        """Apply simple high/low shelf EQ using fast biquad filters."""
        if abs(low_gain_db) < 0.5 and abs(high_gain_db) < 0.5:
            return waveform
        
        result = waveform
        
        # Simple approximation using lowpass/highpass combination
        # For drums, a rough EQ is sufficient for augmentation
        try:
            if abs(low_gain_db) > 0.5:
                # Boost/cut bass by mixing with lowpassed version
                lowpass = torchaudio.functional.lowpass_biquad(waveform, self.sample_rate, 200)
                gain = 10 ** (low_gain_db / 20)
                result = result + lowpass * (gain - 1)
            
            if abs(high_gain_db) > 0.5:
                # Boost/cut treble by mixing with highpassed version  
                highpass = torchaudio.functional.highpass_biquad(result, self.sample_rate, 4000)
                gain = 10 ** (high_gain_db / 20)
                result = result + highpass * (gain - 1)
        except Exception:
            pass  # Skip EQ if it fails
            
        return result
    
    def augment(self, waveform: torch.Tensor, aug_type: str) -> Tuple[torch.Tensor, str]:
        """
        Apply a specific augmentation type.
        
        Returns:
            Tuple of (augmented_waveform, augmentation_description)
        """
        if aug_type == 'pitch_up':
            semitones = random.uniform(0.5, 2.0)
            return self.pitch_shift(waveform, semitones), f"pitch+{semitones:.1f}"
        
        elif aug_type == 'pitch_down':
            semitones = random.uniform(-2.0, -0.5)
            return self.pitch_shift(waveform, semitones), f"pitch{semitones:.1f}"
        
        elif aug_type == 'time_fast':
            rate = random.uniform(1.05, 1.15)
            return self.time_stretch(waveform, rate), f"tempo{rate:.2f}"
        
        elif aug_type == 'time_slow':
            rate = random.uniform(0.85, 0.95)
            return self.time_stretch(waveform, rate), f"tempo{rate:.2f}"
        
        elif aug_type == 'gain_up':
            gain = random.uniform(1.0, 3.0)
            return self.add_gain(waveform, gain), f"gain+{gain:.1f}dB"
        
        elif aug_type == 'gain_down':
            gain = random.uniform(-3.0, -1.0)
            return self.add_gain(waveform, gain), f"gain{gain:.1f}dB"
        
        elif aug_type == 'noise':
            snr = random.uniform(20, 40)
            return self.add_noise(waveform, snr), f"noise_snr{snr:.0f}"
        
        elif aug_type == 'eq_bright':
            return self.apply_eq(waveform, -2, 3), "eq_bright"
        
        elif aug_type == 'eq_dark':
            return self.apply_eq(waveform, 2, -3), "eq_dark"
        
        elif aug_type == 'combined':
            # Combine multiple light augmentations
            w = waveform
            desc_parts = []
            
            # Small pitch shift
            if random.random() > 0.5:
                semi = random.uniform(-1, 1)
                w = self.pitch_shift(w, semi)
                desc_parts.append(f"p{semi:.1f}")
            
            # Small gain
            gain = random.uniform(-2, 2)
            w = self.add_gain(w, gain)
            desc_parts.append(f"g{gain:.1f}")
            
            # Light noise
            if random.random() > 0.5:
                w = self.add_noise(w, random.uniform(30, 40))
                desc_parts.append("n")
            
            return w, "comb_" + "_".join(desc_parts)
        
        else:
            return waveform, "none"


# Augmentation types for workers
AUG_TYPES = [
    'pitch_up', 'pitch_down',
    'time_fast', 'time_slow', 
    'gain_up', 'gain_down',
    'noise',
    'eq_bright', 'eq_dark',
    'combined', 'combined', 'combined'
]


def process_single_clip(args: Tuple) -> List[dict]:
    """
    Worker function to process a single audio clip with multiple augmentations.
    
    This runs in a separate process for parallelization.
    """
    event_id, audio_path, class_name, augs_per_clip, output_dir, sample_rate = args
    
    augmenter = AudioAugmenter(sample_rate)
    results = []
    
    try:
        # Load audio
        waveform, sr = torchaudio.load(audio_path)
        if sr != sample_rate:
            resampler = torchaudio.transforms.Resample(sr, sample_rate)
            waveform = resampler(waveform)
    except Exception as e:
        return []  # Skip failed loads
    
    for aug_idx in range(augs_per_clip):
        aug_type = AUG_TYPES[aug_idx % len(AUG_TYPES)]
        
        try:
            aug_waveform, aug_desc = augmenter.augment(waveform, aug_type)
            
            # Normalize
            max_val = aug_waveform.abs().max()
            if max_val > 0:
                aug_waveform = aug_waveform / max_val * 0.95
            
            # Generate unique ID
            aug_id = f"{event_id}_aug{aug_idx}_{aug_desc}"
            aug_hash = hashlib.md5(aug_id.encode()).hexdigest()[:8]
            output_filename = f"{aug_hash}__{class_name}.wav"
            output_path = Path(output_dir) / output_filename
            
            # Save augmented audio
            torchaudio.save(str(output_path), aug_waveform, sample_rate)
            
            results.append({
                'original_id': event_id,
                'augmented_id': aug_id,
                'filename': output_filename,
                'augmentation': aug_desc,
                'class': class_name
            })
            
        except Exception:
            continue
    
    return results


def load_dataset_clips(
    dataset_dir: Path,
    class_name: str,
    split: str = 'train'
) -> List[Tuple[str, Path]]:
    """
    Load clip paths for a specific class from the dataset.
    
    Returns:
        List of (event_id, audio_path) tuples
    """
    labels_file = dataset_dir / split / f'{split}_labels.json'
    audio_dir = dataset_dir / split / 'audio'
    
    if not labels_file.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_file}")
    
    logger.info(f"Loading labels from {labels_file}...")
    with open(labels_file, 'r') as f:
        labels_data = json.load(f)
    
    clips = []
    
    # Handle both formats: list of dicts or dict of {filename: label}
    if isinstance(labels_data, list):
        # Format: [{'file': 'audio/xxx.wav', 'label': 'snare', 'event_id': '...'}, ...]
        for item in tqdm(labels_data, desc=f"Finding {class_name} clips"):
            if item.get('label') == class_name:
                file_path = item.get('file', '')
                # file_path is like 'audio/xxx__label.wav', extract just the filename
                clip_name = Path(file_path).name
                audio_path = audio_dir / clip_name
                if audio_path.exists():
                    event_id = item.get('event_id', clip_name.replace('.wav', '').replace('.pt', ''))
                    clips.append((event_id, audio_path))
    else:
        # Format: {'filename.wav': 'label', ...}
        for clip_name, label in tqdm(labels_data.items(), desc=f"Finding {class_name} clips"):
            if label == class_name:
                audio_path = audio_dir / clip_name
                if audio_path.exists():
                    event_id = clip_name.replace('.pt', '').replace('.wav', '')
                    clips.append((event_id, audio_path))
    
    logger.info(f"Found {len(clips)} {class_name} clips in {split}")
    return clips


def load_from_feature_cache(
    cache_dir: Path,
    class_name: str,
    split: str = 'train'
) -> List[Tuple[str, int, int]]:
    """
    Load sample locations for a specific class from the consolidated feature cache.
    
    Returns:
        List of (key, shard_id, sample_offset) tuples
    """
    index_file = cache_dir / split / 'index.json'
    
    if not index_file.exists():
        raise FileNotFoundError(f"Index file not found: {index_file}")
    
    logger.info(f"Loading index from {index_file}...")
    with open(index_file, 'r') as f:
        index = json.load(f)
    
    samples = []
    for key, (shard_id, offset) in tqdm(index.items(), desc=f"Finding {class_name} samples"):
        # Key format: 'audio\\xxx__CLASS.pt'
        key_class = key.rsplit('__', 1)[-1].replace('.pt', '')
        if key_class == class_name:
            samples.append((key, shard_id, offset))
    
    logger.info(f"Found {len(samples)} {class_name} samples in {split} cache")
    return samples


def load_progress(output_dir: Path) -> Dict[str, int]:
    """Load progress from previous run."""
    progress_file = output_dir / 'augmentation_progress.json'
    if progress_file.exists():
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {}


def save_progress(output_dir: Path, progress: Dict[str, int]):
    """Save progress for resume."""
    progress_file = output_dir / 'augmentation_progress.json'
    with open(progress_file, 'w') as f:
        json.dump(progress, f, indent=2)


def augment_rare_classes(
    dataset_dir: Path,
    output_dir: Path,
    target_counts: Dict[str, int],
    sample_rate: int = 44100,
    dry_run: bool = False,
    resume: bool = True,
    num_workers: int = 6
):
    """
    Main augmentation pipeline for rare classes.
    
    Supports graceful interruption (Ctrl+C), resume from progress, and multiprocessing.
    """
    global _interrupt_requested
    
    # Register signal handler for graceful interruption
    signal.signal(signal.SIGINT, signal_handler)
    
    # Load progress if resuming
    progress = load_progress(output_dir) if resume else {}
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for class_name in RARE_CLASSES:
        if class_name not in target_counts:
            continue
            
        target = target_counts.get(class_name, 50000)
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {class_name} (target: {target:,})")
        logger.info(f"{'='*60}")
        
        # Load existing clips
        try:
            clips = load_dataset_clips(dataset_dir, class_name, 'train')
        except FileNotFoundError as e:
            logger.warning(f"Could not load clips: {e}")
            continue
        
        current_count = len(clips)
        if current_count >= target:
            logger.info(f"{class_name} already has {current_count:,} >= {target:,}, skipping")
            continue
        
        augmentations_needed = target - current_count
        augs_per_clip = (augmentations_needed // current_count) + 1
        
        logger.info(f"Need {augmentations_needed:,} augmentations ({augs_per_clip} per clip)")
        
        if dry_run:
            logger.info(f"[DRY RUN] Would generate {augmentations_needed:,} augmented samples")
            continue
        
        # Create output directory for this class
        class_output_dir = output_dir / class_name
        class_output_dir.mkdir(exist_ok=True)
        
        # Check for existing progress (resume support)
        existing_count = progress.get(class_name, 0)
        if existing_count > 0:
            # Count actual files to verify
            actual_files = len(list(class_output_dir.glob(f'*__{class_name}.wav')))
            existing_count = min(existing_count, actual_files)
            logger.info(f"Resuming from {existing_count:,} existing augmented samples")
            augmentations_needed -= existing_count
            if augmentations_needed <= 0:
                logger.info(f"{class_name} already complete, skipping")
                continue
        
        augmented_count = existing_count
        augmented_manifest = []
        
        # Load existing manifest if present
        manifest_path = class_output_dir / 'augmentation_manifest.json'
        if manifest_path.exists() and resume:
            try:
                with open(manifest_path, 'r') as f:
                    augmented_manifest = json.load(f)
            except Exception:
                augmented_manifest = []
        
        # Calculate how many clips to process (skip already processed)
        processed_ids = {m['original_id'] for m in augmented_manifest}
        clips_to_process = [(eid, path) for eid, path in clips if eid not in processed_ids]
        
        # Limit clips to process based on remaining need
        clips_needed = (augmentations_needed // augs_per_clip) + 1
        clips_to_process = clips_to_process[:clips_needed]
        
        logger.info(f"Processing {len(clips_to_process)} clips with {num_workers} workers...")
        
        # Prepare arguments for parallel processing
        worker_args = [
            (event_id, str(audio_path), class_name, augs_per_clip, str(class_output_dir), sample_rate)
            for event_id, audio_path in clips_to_process
        ]
        
        total_target = augmentations_needed + existing_count
        
        # Process in parallel with progress bar
        with tqdm(total=total_target, initial=existing_count, desc=f"Augmenting {class_name}") as pbar:
            # Use ProcessPoolExecutor for true parallelism
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(process_single_clip, args): args[0] for args in worker_args}
                
                for future in as_completed(futures):
                    if _interrupt_requested:
                        logger.info(f"\nInterrupt requested. Cancelling remaining tasks...")
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    try:
                        results = future.result(timeout=60)  # 60s timeout per clip
                        for result in results:
                            if augmented_count >= total_target:
                                break
                            augmented_manifest.append(result)
                            augmented_count += 1
                            pbar.update(1)
                    except Exception as e:
                        logger.warning(f"Worker failed: {e}")
                        continue
                    
                    if augmented_count >= total_target:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
        
        # Save manifest and progress
        with open(manifest_path, 'w') as f:
            json.dump(augmented_manifest, f, indent=2)
        progress[class_name] = augmented_count
        save_progress(output_dir, progress)
        
        logger.info(f"Generated {augmented_count:,} augmented {class_name} samples")
        logger.info(f"Manifest saved to {manifest_path}")
        
        if _interrupt_requested:
            logger.info("Stopping due to interrupt request")
            return
            return


def main():
    parser = argparse.ArgumentParser(
        description="Generate augmented samples for rare drum classes"
    )
    parser.add_argument(
        '--dataset-dir',
        type=Path,
        default=Path('C:/temp_dataset/prod_v5_fixed_20251212'),
        help='Path to the built dataset directory'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('C:/temp_dataset/augmented_rare_classes'),
        help='Output directory for augmented samples'
    )
    parser.add_argument(
        '--target',
        type=int,
        default=50000,
        help='Target count for each rare class (default: 50000)'
    )
    parser.add_argument(
        '--sample-rate',
        type=int,
        default=44100,
        help='Sample rate for audio (default: 44100)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be done without actually doing it'
    )
    parser.add_argument(
        '--classes',
        nargs='+',
        default=RARE_CLASSES,
        choices=RARE_CLASSES,
        help='Classes to augment (default: all rare classes)'
    )
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start fresh, ignoring any previous progress'
    )
    parser.add_argument(
        '--split',
        type=str,
        default='train',
        help='Dataset split to augment (default: train)'
    )
    parser.add_argument(
        '--num-workers',
        type=int,
        default=6,
        help='Number of parallel workers (default: 6, recommended: CPU cores - 2)'
    )
    
    args = parser.parse_args()
    
    # Update target counts
    target_counts = {cls: args.target for cls in args.classes}
    
    logger.info("="*60)
    logger.info("Rare Class Augmentation Pipeline (PARALLEL)")
    logger.info("="*60)
    logger.info(f"Dataset: {args.dataset_dir}")
    logger.info(f"Output: {args.output_dir}")
    logger.info(f"Target counts: {target_counts}")
    logger.info(f"Workers: {args.num_workers}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Resume: {not args.no_resume}")
    logger.info("="*60)
    logger.info("Press Ctrl+C to pause and save progress")
    logger.info("="*60)
    
    augment_rare_classes(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        target_counts=target_counts,
        sample_rate=args.sample_rate,
        dry_run=args.dry_run,
        resume=not args.no_resume,
        num_workers=args.num_workers
    )
    
    logger.info("\nAugmentation complete!")


if __name__ == '__main__':
    mp.freeze_support()  # Required for Windows multiprocessing
    main()
