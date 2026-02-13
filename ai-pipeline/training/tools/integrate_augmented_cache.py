#!/usr/bin/env python3
"""
Integrate Augmented Samples into Feature Cache

This script takes augmented audio samples and adds them to the consolidated
feature cache. It computes mel spectrograms for the augmented samples and
appends them to new shards in the cache.

Usage:
    python integrate_augmented_cache.py \
        --augmented-dir C:/temp_dataset/augmented_rare_classes \
        --cache-dir C:/temp_dataset/feature_cache_v5 \
        --output-dir C:/temp_dataset/feature_cache_v5_augmented
"""

from __future__ import annotations

import argparse
import json
import logging
import mmap
import os
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torchaudio
from tqdm import tqdm

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MelSpectrogramTransform:
    """Compute mel spectrogram matching the training pipeline."""
    
    def __init__(
        self,
        sample_rate: int = 44100,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
        target_frames: int = 128
    ):
        self.sample_rate = sample_rate
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.target_frames = target_frames
        
        self.mel_transform = torchaudio.transforms.MelSpectrogram(
            sample_rate=sample_rate,
            n_fft=n_fft,
            hop_length=hop_length,
            n_mels=n_mels,
            power=2.0
        )
    
    def __call__(self, waveform: torch.Tensor) -> torch.Tensor:
        """
        Compute mel spectrogram from waveform.
        
        Args:
            waveform: (channels, samples) tensor
            
        Returns:
            (1, n_mels, target_frames) tensor in float16
        """
        # Convert to mono if stereo
        if waveform.dim() == 2 and waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        elif waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        
        # Compute mel spectrogram
        mel = self.mel_transform(waveform)
        
        # Convert to log scale (add small epsilon to avoid log(0))
        mel = torch.log(mel + 1e-9)
        
        # Normalize to [-1, 1] range (approximate)
        mel = (mel + 10) / 10  # Rough normalization
        mel = mel.clamp(-1, 1)
        
        # Ensure we have exactly target_frames
        if mel.shape[-1] < self.target_frames:
            # Pad with zeros
            padding = self.target_frames - mel.shape[-1]
            mel = torch.nn.functional.pad(mel, (0, padding), value=-1)
        elif mel.shape[-1] > self.target_frames:
            # Truncate
            mel = mel[..., :self.target_frames]
        
        # Ensure shape is (1, n_mels, target_frames)
        if mel.dim() == 3:
            mel = mel.squeeze(0)  # Remove batch dim if present
        mel = mel.unsqueeze(0)  # Add channel dim
        
        # Convert to float16
        return mel.half()


def load_cache_manifest(cache_dir: Path, split: str = 'train') -> dict:
    """Load the cache manifest."""
    manifest_path = cache_dir / split / 'manifest.json'
    with open(manifest_path, 'r') as f:
        return json.load(f)


def load_cache_index(cache_dir: Path, split: str = 'train') -> dict:
    """Load the cache index."""
    index_path = cache_dir / split / 'index.json'
    with open(index_path, 'r') as f:
        return json.load(f)


def create_augmented_shards(
    augmented_dir: Path,
    output_dir: Path,
    existing_manifest: dict,
    existing_index: dict,
    sample_rate: int = 44100,
    samples_per_shard: int = 65536
) -> Tuple[List[dict], dict]:
    """
    Create new shards containing augmented samples.
    
    Returns:
        Tuple of (new_shards_info, new_index_entries)
    """
    transform = MelSpectrogramTransform(sample_rate=sample_rate)
    
    # Find all augmented audio files
    audio_files = []
    for class_dir in augmented_dir.iterdir():
        if class_dir.is_dir():
            for audio_file in class_dir.glob('*.wav'):
                class_name = class_dir.name
                audio_files.append((audio_file, class_name))
    
    if not audio_files:
        logger.warning("No augmented audio files found!")
        return [], {}
    
    logger.info(f"Found {len(audio_files)} augmented audio files")
    
    # Determine starting shard ID
    start_shard_id = existing_manifest['num_shards']
    
    # Process files and create shards
    new_shards = []
    new_index = {}
    
    # Buffer for current shard
    shard_buffer = []
    current_shard_id = start_shard_id
    
    bytes_per_sample = existing_manifest['bytes_per_sample']
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for audio_path, class_name in tqdm(audio_files, desc="Processing augmented samples"):
        try:
            # Load and transform
            waveform, sr = torchaudio.load(audio_path)
            if sr != sample_rate:
                resampler = torchaudio.transforms.Resample(sr, sample_rate)
                waveform = resampler(waveform)
            
            mel = transform(waveform)
            
            # Create unique key
            key = f"augmented/{class_name}/{audio_path.stem}__{class_name}.pt"
            
            # Add to buffer
            shard_buffer.append((key, mel))
            
            # Check if shard is full
            if len(shard_buffer) >= samples_per_shard:
                # Write shard
                shard_path = output_dir / f"shard_{current_shard_id:04d}.bin"
                write_shard(shard_path, [m for _, m in shard_buffer], bytes_per_sample)
                
                # Update index
                for idx, (k, _) in enumerate(shard_buffer):
                    new_index[k] = [current_shard_id, idx]
                
                # Record shard info
                new_shards.append({
                    'shard_id': current_shard_id,
                    'filename': f"shard_{current_shard_id:04d}.bin",
                    'num_samples': len(shard_buffer)
                })
                
                logger.info(f"Wrote shard {current_shard_id} with {len(shard_buffer)} samples")
                
                # Reset buffer and increment shard ID
                shard_buffer = []
                current_shard_id += 1
                
        except Exception as e:
            logger.warning(f"Failed to process {audio_path}: {e}")
            continue
    
    # Write final partial shard if needed
    if shard_buffer:
        shard_path = output_dir / f"shard_{current_shard_id:04d}.bin"
        write_shard(shard_path, [m for _, m in shard_buffer], bytes_per_sample)
        
        for idx, (k, _) in enumerate(shard_buffer):
            new_index[k] = [current_shard_id, idx]
        
        new_shards.append({
            'shard_id': current_shard_id,
            'filename': f"shard_{current_shard_id:04d}.bin",
            'num_samples': len(shard_buffer)
        })
        
        logger.info(f"Wrote final shard {current_shard_id} with {len(shard_buffer)} samples")
    
    return new_shards, new_index


def write_shard(path: Path, tensors: List[torch.Tensor], bytes_per_sample: int):
    """Write a list of tensors to a binary shard file."""
    with open(path, 'wb') as f:
        for tensor in tensors:
            data = tensor.numpy().tobytes()
            if len(data) != bytes_per_sample:
                # Pad or truncate if necessary
                if len(data) < bytes_per_sample:
                    data = data + b'\x00' * (bytes_per_sample - len(data))
                else:
                    data = data[:bytes_per_sample]
            f.write(data)


def integrate_augmented_samples(
    augmented_dir: Path,
    cache_dir: Path,
    output_dir: Path,
    split: str = 'train',
    sample_rate: int = 44100
):
    """
    Main integration pipeline.
    """
    # Load existing cache info
    logger.info(f"Loading existing cache from {cache_dir}/{split}")
    manifest = load_cache_manifest(cache_dir, split)
    index = load_cache_index(cache_dir, split)
    
    logger.info(f"Existing cache: {manifest['total_samples']:,} samples in {manifest['num_shards']} shards")
    
    # Create augmented shards
    split_output = output_dir / split
    new_shards, new_index = create_augmented_shards(
        augmented_dir=augmented_dir,
        output_dir=split_output,
        existing_manifest=manifest,
        existing_index=index,
        sample_rate=sample_rate
    )
    
    if not new_shards:
        logger.warning("No new shards created!")
        return
    
    # Copy existing shards
    logger.info("Copying existing shards...")
    existing_split = cache_dir / split
    for shard_info in tqdm(manifest['shards'], desc="Copying shards"):
        src = existing_split / shard_info['filename']
        dst = split_output / shard_info['filename']
        if src.exists() and not dst.exists():
            import shutil
            shutil.copy2(src, dst)
    
    # Update manifest
    new_total_samples = manifest['total_samples'] + sum(s['num_samples'] for s in new_shards)
    new_num_shards = manifest['num_shards'] + len(new_shards)
    
    updated_manifest = {
        'version': manifest['version'],
        'total_samples': new_total_samples,
        'tensor_shape': manifest['tensor_shape'],
        'dtype': manifest['dtype'],
        'samples_per_shard': manifest['samples_per_shard'],
        'bytes_per_sample': manifest['bytes_per_sample'],
        'num_shards': new_num_shards,
        'shards': manifest['shards'] + new_shards
    }
    
    manifest_path = split_output / 'manifest.json'
    with open(manifest_path, 'w') as f:
        json.dump(updated_manifest, f, indent=2)
    
    # Update index
    updated_index = {**index, **new_index}
    index_path = split_output / 'index.json'
    with open(index_path, 'w') as f:
        json.dump(updated_index, f)
    
    logger.info(f"\nIntegration complete!")
    logger.info(f"Original: {manifest['total_samples']:,} samples")
    logger.info(f"Added: {sum(s['num_samples'] for s in new_shards):,} samples")
    logger.info(f"Total: {new_total_samples:,} samples")
    logger.info(f"Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Integrate augmented samples into feature cache"
    )
    parser.add_argument(
        '--augmented-dir',
        type=Path,
        default=Path('C:/temp_dataset/augmented_rare_classes'),
        help='Directory containing augmented samples'
    )
    parser.add_argument(
        '--cache-dir',
        type=Path,
        default=Path('C:/temp_dataset/feature_cache_v5'),
        help='Existing feature cache directory'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('C:/temp_dataset/feature_cache_v5_augmented'),
        help='Output directory for combined cache'
    )
    parser.add_argument(
        '--split',
        choices=['train', 'val'],
        default='train',
        help='Split to augment (default: train)'
    )
    parser.add_argument(
        '--sample-rate',
        type=int,
        default=44100,
        help='Sample rate (default: 44100)'
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("Feature Cache Integration")
    logger.info("="*60)
    logger.info(f"Augmented dir: {args.augmented_dir}")
    logger.info(f"Cache dir: {args.cache_dir}")
    logger.info(f"Output dir: {args.output_dir}")
    logger.info("="*60)
    
    integrate_augmented_samples(
        augmented_dir=args.augmented_dir,
        cache_dir=args.cache_dir,
        output_dir=args.output_dir,
        split=args.split,
        sample_rate=args.sample_rate
    )


if __name__ == '__main__':
    main()
