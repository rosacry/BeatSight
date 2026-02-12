#!/usr/bin/env python3
"""
Generate cache entries for samples missing from the consolidated cache.

This script finds samples in the labels that don't have cached features,
generates mel spectrograms for them, and appends to the consolidated cache.
"""

import argparse
import json
import numpy as np
import torch
import torchaudio
from pathlib import Path
from tqdm import tqdm
import struct


def load_and_compute_melspec(audio_path: Path, target_sr: int = 22050, n_mels: int = 128, 
                              hop_length: int = 512, n_fft: int = 2048) -> torch.Tensor:
    """Load audio and compute mel spectrogram."""
    # Load audio
    waveform, sr = torchaudio.load(str(audio_path))
    
    # Convert to mono if stereo
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    
    # Resample if needed
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(sr, target_sr)
        waveform = resampler(waveform)
    
    # Compute mel spectrogram
    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=target_sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        power=2.0,
    )
    mel_spec = mel_transform(waveform)
    
    # Convert to log scale
    mel_spec = torch.log(mel_spec + 1e-9)
    
    # Ensure consistent shape (1, n_mels, time_frames)
    # Pad or truncate to fixed length (e.g., 44 frames for ~0.5s at 22050/512)
    target_frames = 44
    if mel_spec.shape[-1] < target_frames:
        pad = target_frames - mel_spec.shape[-1]
        mel_spec = torch.nn.functional.pad(mel_spec, (0, pad))
    elif mel_spec.shape[-1] > target_frames:
        mel_spec = mel_spec[..., :target_frames]
    
    return mel_spec


def append_to_consolidated_cache(cache_dir: Path, new_entries: dict):
    """Append new entries to the consolidated cache."""
    # Load existing index
    index_path = cache_dir / "index.json"
    with open(index_path, 'r') as f:
        cache_index = json.load(f)
    
    # Load manifest to get shard info
    manifest_path = cache_dir / "manifest.json"
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Find the last shard
    num_shards = manifest.get('num_shards', len([f for f in cache_dir.glob('shard_*.bin')]))
    last_shard_idx = num_shards - 1
    last_shard_path = cache_dir / f"shard_{last_shard_idx:04d}.bin"
    
    # Get current shard size
    current_shard_size = last_shard_path.stat().st_size if last_shard_path.exists() else 0
    max_shard_size = 2 * 1024 * 1024 * 1024  # 2GB per shard
    
    # Open shard for appending (or create new one if current is full)
    if current_shard_size >= max_shard_size:
        last_shard_idx += 1
        last_shard_path = cache_dir / f"shard_{last_shard_idx:04d}.bin"
        current_shard_size = 0
        num_shards += 1
    
    added_count = 0
    with open(last_shard_path, 'ab') as shard_file:
        for cache_key, tensor in new_entries.items():
            # Serialize tensor
            tensor_bytes = tensor.numpy().tobytes()
            tensor_size = len(tensor_bytes)
            
            # Check if we need a new shard
            if current_shard_size + tensor_size > max_shard_size:
                shard_file.close()
                last_shard_idx += 1
                last_shard_path = cache_dir / f"shard_{last_shard_idx:04d}.bin"
                shard_file = open(last_shard_path, 'ab')
                current_shard_size = 0
                num_shards += 1
            
            # Write tensor
            offset = current_shard_size
            shard_file.write(tensor_bytes)
            current_shard_size += tensor_size
            
            # Update index
            cache_index[cache_key] = {
                "shard": last_shard_idx,
                "offset": offset,
                "size": tensor_size,
                "shape": list(tensor.shape),
                "dtype": str(tensor.dtype).replace('torch.', '')
            }
            added_count += 1
    
    # Save updated index
    print(f"Saving updated index with {len(cache_index):,} entries...")
    with open(index_path, 'w') as f:
        json.dump(cache_index, f)
    
    # Update manifest
    manifest['num_shards'] = num_shards
    manifest['num_entries'] = len(cache_index)
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    return added_count


def main():
    parser = argparse.ArgumentParser(description="Generate missing cache entries")
    parser.add_argument("--labels-dir", required=True, help="Directory with train_labels_*.npy files")
    parser.add_argument("--cache-dir", required=True, help="Directory with consolidated cache")
    parser.add_argument("--audio-dirs", nargs='+', required=True, help="Directories to search for audio files")
    parser.add_argument("--batch-size", type=int, default=1000, help="Save every N entries")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just show stats")
    args = parser.parse_args()

    labels_dir = Path(args.labels_dir)
    cache_dir = Path(args.cache_dir)
    audio_dirs = [Path(d) for d in args.audio_dirs]

    # Load cache index
    index_path = cache_dir / "index.json"
    print(f"Loading cache index from {index_path}...")
    with open(index_path, 'r') as f:
        cache_index = json.load(f)
    cache_keys = set(cache_index.keys())
    print(f"  Cache contains {len(cache_keys):,} entries")

    # Load labels
    prefix = labels_dir.name
    files_path = labels_dir / f"{prefix}_labels_files.npy"
    print(f"Loading labels from {files_path}...")
    files = np.load(files_path, allow_pickle=True)
    print(f"  Labels contain {len(files):,} entries")

    # Find missing samples
    print("Finding missing samples...")
    missing = []
    for i, file_bytes in enumerate(files):
        if isinstance(file_bytes, bytes):
            file_path = file_bytes.decode('utf-8')
        else:
            file_path = str(file_bytes)
        
        cache_key = file_path.replace('/', '\\').replace('.wav', '.pt')
        if cache_key not in cache_keys:
            missing.append((i, file_path, cache_key))
    
    print(f"  Missing: {len(missing):,} samples")
    
    if not missing:
        print("No missing samples!")
        return
    
    # Show sample missing entries
    print("\nSample missing entries:")
    for idx, file_path, cache_key in missing[:5]:
        print(f"  [{idx}] {file_path} -> {cache_key}")

    if args.dry_run:
        print("\n[DRY RUN] Searching for audio files...")
        found = 0
        not_found = []
        for idx, file_path, cache_key in missing[:100]:  # Check first 100
            audio_found = False
            for audio_dir in audio_dirs:
                # Try various path patterns
                candidates = [
                    audio_dir / file_path,
                    audio_dir / Path(file_path).name,
                    audio_dir / file_path.replace('audio/', ''),
                ]
                for candidate in candidates:
                    if candidate.exists():
                        audio_found = True
                        found += 1
                        break
                if audio_found:
                    break
            if not audio_found:
                not_found.append(file_path)
        
        print(f"  Found: {found}/100 checked")
        if not_found:
            print(f"  Not found examples:")
            for nf in not_found[:5]:
                print(f"    {nf}")
        return

    # Generate features for missing samples
    print(f"\nGenerating features for {len(missing):,} missing samples...")
    new_entries = {}
    not_found_count = 0
    
    for idx, file_path, cache_key in tqdm(missing, desc="Processing"):
        # Find audio file
        audio_path = None
        for audio_dir in audio_dirs:
            candidates = [
                audio_dir / file_path,
                audio_dir / Path(file_path).name,
                audio_dir / file_path.replace('audio/', ''),
            ]
            for candidate in candidates:
                if candidate.exists():
                    audio_path = candidate
                    break
            if audio_path:
                break
        
        if not audio_path:
            not_found_count += 1
            continue
        
        try:
            mel_spec = load_and_compute_melspec(audio_path)
            new_entries[cache_key] = mel_spec
        except Exception as e:
            print(f"  Error processing {audio_path}: {e}")
            continue
        
        # Batch save
        if len(new_entries) >= args.batch_size:
            added = append_to_consolidated_cache(cache_dir, new_entries)
            print(f"  Added {added:,} entries to cache")
            new_entries = {}
    
    # Save remaining
    if new_entries:
        added = append_to_consolidated_cache(cache_dir, new_entries)
        print(f"  Added {added:,} entries to cache")
    
    print(f"\nDone! Audio not found for {not_found_count:,} samples")


if __name__ == "__main__":
    main()
