"""
Multi-Label MIDI Dataset

Dataset for training with real multi-label drum data from MIDI datasets.
Uses pre-extracted labels and audio paths, extracts spectrograms on-the-fly.

Sources:
- Groove MIDI Dataset: Professional drummer recordings
- E-GMD (Expanded Groove MIDI Dataset): Extended recordings

Usage:
    from training.multilabel.midi_multilabel_dataset import MIDIMultiLabelDataset
    
    dataset = MIDIMultiLabelDataset(
        metadata_dir='F:/datasets/multilabel_real',
        sources=['groove_midi', 'egmd'],
        split='train'
    )
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch.utils.data import Dataset

try:
    import librosa
except ImportError:
    librosa = None


class MIDIMultiLabelDataset(Dataset):
    """
    Dataset for multi-label drum classification using real MIDI annotations.
    
    Loads pre-computed labels and audio paths from metadata files,
    extracts mel-spectrograms on-the-fly from audio files.
    
    Args:
        metadata_dir: Root directory containing source subdirectories
        sources: List of sources to include ('groove_midi', 'egmd')
        split: 'train' or 'val'
        drive_remap: Dict to remap drive letters (e.g., {'D:': 'F:'})
        sr: Sample rate (default: 44100)
        n_mels: Number of mel bands (default: 128)
        target_width: Target spectrogram width (default: 128)
        window_ms: Window duration in milliseconds (default: 100)
        cache_audio: If True, cache loaded audio in memory (uses more RAM)
        transform: Optional transform for spectrograms
    """
    
    def __init__(
        self,
        metadata_dir: Union[str, Path],
        sources: List[str] = ['groove_midi', 'egmd'],
        split: str = 'train',
        drive_remap: Optional[Dict[str, str]] = None,
        sr: int = 44100,
        n_mels: int = 128,
        target_width: int = 128,
        window_ms: float = 100.0,
        cache_audio: bool = False,
        transform: Optional[Any] = None,
    ) -> None:
        if librosa is None:
            raise ImportError("librosa is required for MIDIMultiLabelDataset")
        
        self.metadata_dir = Path(metadata_dir)
        self.sources = sources
        self.split = split
        self.drive_remap = drive_remap or {'D:': 'F:'}
        self.sr = sr
        self.n_mels = n_mels
        self.target_width = target_width
        self.window_ms = window_ms
        self.cache_audio = cache_audio
        self.transform = transform
        
        # 12-class drum components
        self.class_names = [
            "china", "crash", "cross_stick", "hihat_closed", "hihat_open",
            "hihat_pedal", "kick", "ride_bell", "ride_bow", "snare",
            "splash", "tom"
        ]
        self.num_classes = len(self.class_names)
        
        # Load data from all sources
        self.samples: List[Dict[str, Any]] = []
        self._load_all_sources()
        
        # Audio cache
        self._audio_cache: Dict[str, np.ndarray] = {}
        
        # Compute mel filterbank once
        self._mel_fb = librosa.filters.mel(
            sr=sr, n_fft=2048, n_mels=n_mels, fmax=8000
        )
        
        print(f"[MIDIMultiLabel] Loaded {len(self.samples):,} {split} samples")
        multilabel = sum(1 for s in self.samples if s['label'].sum() > 1)
        print(f"[MIDIMultiLabel] {multilabel:,} ({100*multilabel/len(self.samples):.1f}%) multi-label")
    
    def _load_all_sources(self) -> None:
        """Load samples from all specified sources."""
        for source in self.sources:
            source_dir = self.metadata_dir / source / self.split
            if not source_dir.exists():
                print(f"[MIDIMultiLabel] Source not found: {source_dir}")
                continue
            
            # Find labels and metadata files
            label_files = list(source_dir.glob('*labels*.npy'))
            meta_files = list(source_dir.glob('*.json'))
            
            if not label_files or not meta_files:
                print(f"[MIDIMultiLabel] Incomplete data in {source_dir}")
                continue
            
            labels = np.load(label_files[0])
            with open(meta_files[0]) as f:
                metadata = json.load(f)
            
            audio_paths = metadata.get('audio_paths', [])
            times = metadata.get('times', [])
            
            if len(labels) != len(audio_paths) or len(labels) != len(times):
                print(f"[MIDIMultiLabel] Size mismatch in {source}: "
                      f"labels={len(labels)}, paths={len(audio_paths)}, times={len(times)}")
                continue
            
            # Remap drive letters
            for i in range(len(audio_paths)):
                path = audio_paths[i]
                for old, new in self.drive_remap.items():
                    path = path.replace(old, new)
                audio_paths[i] = path
            
            # Add samples
            for i in range(len(labels)):
                self.samples.append({
                    'audio_path': audio_paths[i],
                    'time': times[i],
                    'label': labels[i],
                    'source': source,
                })
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]
        audio_path = sample['audio_path']
        onset_time = sample['time']
        label = sample['label']
        
        # Load audio (with caching if enabled)
        audio = self._load_audio(audio_path)
        
        # Extract spectrogram around onset time
        spec = self._extract_spectrogram(audio, onset_time)
        
        # Apply transform if provided
        if self.transform is not None:
            spec = self.transform(spec)
        
        # Convert to tensors
        spec_tensor = torch.from_numpy(spec).float().unsqueeze(0)  # Add channel dim
        label_tensor = torch.from_numpy(label).float()
        
        return spec_tensor, label_tensor
    
    def _load_audio(self, path: str) -> np.ndarray:
        """Load audio file, with optional caching."""
        if self.cache_audio and path in self._audio_cache:
            return self._audio_cache[path]
        
        audio, _ = librosa.load(path, sr=self.sr, mono=True)
        
        if self.cache_audio:
            self._audio_cache[path] = audio
        
        return audio
    
    def _extract_spectrogram(
        self, audio: np.ndarray, onset_time: float
    ) -> np.ndarray:
        """Extract mel spectrogram centered on onset time."""
        window_samples = int(self.sr * self.window_ms / 1000.0)
        center_sample = int(onset_time * self.sr)
        
        # Extract window centered on onset
        half_window = window_samples // 2
        start = max(0, center_sample - half_window)
        end = min(len(audio), center_sample + half_window)
        
        segment = audio[start:end]
        
        # Pad if necessary
        if len(segment) < window_samples:
            pad_left = (window_samples - len(segment)) // 2
            pad_right = window_samples - len(segment) - pad_left
            segment = np.pad(segment, (pad_left, pad_right), mode='constant')
        
        # Compute mel spectrogram
        hop_length = max(1, len(segment) // self.target_width)
        
        stft = np.abs(librosa.stft(segment, n_fft=2048, hop_length=hop_length))
        mel_spec = np.dot(self._mel_fb, stft)
        mel_db = librosa.amplitude_to_db(mel_spec, ref=np.max)
        
        # Resize to target width
        if mel_db.shape[1] < self.target_width:
            # Pad
            pad_width = self.target_width - mel_db.shape[1]
            mel_db = np.pad(mel_db, ((0, 0), (0, pad_width)), mode='constant')
        elif mel_db.shape[1] > self.target_width:
            # Truncate
            mel_db = mel_db[:, :self.target_width]
        
        # Normalize to [-1, 1]
        mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
        mel_db = mel_db * 2 - 1
        
        return mel_db.astype(np.float32)
    
    def get_class_weights(self) -> torch.Tensor:
        """
        Compute positive class weights for BCE loss.
        
        Returns weights that balance positive/negative samples per class.
        """
        labels = np.array([s['label'] for s in self.samples])
        pos_counts = labels.sum(axis=0)
        neg_counts = len(labels) - pos_counts
        
        # pos_weight = neg_count / pos_count (for BCEWithLogitsLoss)
        pos_weights = neg_counts / (pos_counts + 1e-8)
        
        # Clip extreme weights
        pos_weights = np.clip(pos_weights, 0.5, 10.0)
        
        return torch.from_numpy(pos_weights).float()
    
    def get_sample_weights(self) -> np.ndarray:
        """
        Compute per-sample weights for weighted sampling.
        
        Upweights multi-label samples and rare classes.
        """
        labels = np.array([s['label'] for s in self.samples])
        
        # Base weight: upweight multi-label samples
        label_counts = labels.sum(axis=1)
        weights = np.where(label_counts > 1, 2.0, 1.0)
        
        # Also upweight rare classes
        class_freqs = labels.sum(axis=0) / len(labels)
        for i in range(len(labels)):
            active_classes = np.where(labels[i] > 0)[0]
            if len(active_classes) > 0:
                # Boost by inverse frequency of rarest active class
                min_freq = class_freqs[active_classes].min()
                weights[i] *= (1.0 / (min_freq + 0.1))
        
        # Normalize
        weights = weights / weights.sum() * len(weights)
        
        return weights


class CachedMIDIMultiLabelDataset(Dataset):
    """
    Pre-cached version of MIDIMultiLabelDataset for faster training.
    
    Expects pre-extracted spectrograms stored as:
    - features.npy: (N, 128, 128) spectrograms
    - labels.npy: (N, 12) multi-hot labels
    
    Args:
        features_path: Path to features.npy
        labels_path: Path to labels.npy
        transform: Optional transform for spectrograms
    """
    
    def __init__(
        self,
        features_path: Union[str, Path],
        labels_path: Union[str, Path],
        transform: Optional[Any] = None,
    ) -> None:
        self.features = np.load(features_path)
        self.labels = np.load(labels_path)
        self.transform = transform
        
        assert len(self.features) == len(self.labels), \
            f"Size mismatch: features={len(self.features)}, labels={len(self.labels)}"
        
        print(f"[CachedMultiLabel] Loaded {len(self.features):,} samples")
        multilabel = (self.labels.sum(axis=1) > 1).sum()
        print(f"[CachedMultiLabel] {multilabel:,} ({100*multilabel/len(self.labels):.1f}%) multi-label")
    
    def __len__(self) -> int:
        return len(self.features)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        feat = self.features[idx]
        label = self.labels[idx]
        
        if self.transform is not None:
            feat = self.transform(feat)
        
        feat_tensor = torch.from_numpy(feat).float().unsqueeze(0)
        label_tensor = torch.from_numpy(label).float()
        
        return feat_tensor, label_tensor
    
    def get_class_weights(self) -> torch.Tensor:
        """Compute positive class weights for BCE loss."""
        pos_counts = self.labels.sum(axis=0)
        neg_counts = len(self.labels) - pos_counts
        pos_weights = neg_counts / (pos_counts + 1e-8)
        pos_weights = np.clip(pos_weights, 0.5, 10.0)
        return torch.from_numpy(pos_weights).float()


if __name__ == '__main__':
    # Test the dataset
    print("Testing MIDIMultiLabelDataset...")
    
    dataset = MIDIMultiLabelDataset(
        metadata_dir='F:/datasets/multilabel_real',
        sources=['groove_midi', 'egmd'],
        split='train',
        drive_remap={'D:': 'F:'},
    )
    
    # Load a sample
    spec, label = dataset[0]
    print(f"Spectrogram shape: {spec.shape}")
    print(f"Label shape: {label.shape}")
    print(f"Active classes: {label.nonzero().squeeze().tolist()}")
    
    # Get weights
    class_weights = dataset.get_class_weights()
    print(f"Class weights: {class_weights}")
