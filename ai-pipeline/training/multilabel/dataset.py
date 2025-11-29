"""
Multi-Label Drum Sample Dataset

This dataset returns multi-hot encoded labels for samples that may contain
multiple simultaneous drum hits (e.g., kick + hi-hat, snare + crash).

The key difference from single-label DrumSampleDataset:
- Single-label: Returns int label (component_idx)
- Multi-label: Returns tensor of shape (num_classes,) with 1s for active drums

Example label formats supported:
1. New events.jsonl format with components array:
   {"components": [{"label": "kick"}, {"label": "hihat_closed"}]}
   
2. Legacy labels.json with component_idx (falls back to single-label):
   {"file": "audio/s1.wav", "component_idx": 9}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

try:
    import torchaudio
    from torchaudio import functional as ta_F
    from torchaudio import transforms as ta_T
except ImportError:
    torchaudio = None
    ta_F = None
    ta_T = None

try:
    import librosa
except ImportError:
    librosa = None


# Default drum component list (should match components.json)
DEFAULT_DRUM_COMPONENTS = [
    "aux_percussion",
    "china",
    "crash",
    "cross_stick",
    "hihat_closed",
    "hihat_foot_splash",
    "hihat_open",
    "hihat_pedal",
    "hihat_splash",
    "kick",
    "ride_bell",
    "ride_bow",
    "rimshot",
    "snare",
    "snare_center",
    "snare_cross_stick",
    "snare_rimshot",
    "splash",
    "tom_high",
    "tom_low",
    "tom_mid",
]


class MultiLabelDrumDataset(Dataset):
    """
    PyTorch dataset for multi-label drum classification.
    
    Each sample can have multiple active drum classes (simultaneous hits).
    Labels are returned as multi-hot encoded tensors.
    
    Args:
        data_dir: Root directory containing audio files
        labels_file: Path to labels.json or events.jsonl
        sr: Sample rate (default: 44100)
        num_classes: Number of drum classes (default: 21)
        class_names: List of class names in order, or None to load from components.json
        cache_dir: Optional directory for feature caching
        prefer_torchaudio: Use torchaudio for loading (faster)
        n_fft: FFT size for mel spectrogram
        hop_length: Hop length for mel spectrogram
        n_mels: Number of mel bins
        fmax: Maximum frequency for mel bins
        target_frames: Target number of frames (pads/truncates)
        threshold_velocity: Minimum velocity to consider a hit active (default: 0.1)
        return_velocities: If True, return velocity values instead of binary labels
    """
    
    def __init__(
        self,
        data_dir: Union[str, Path],
        labels_file: Union[str, Path],
        sr: int = 44100,
        num_classes: int = 21,
        class_names: Optional[List[str]] = None,
        *,
        cache_dir: Optional[Path] = None,
        prefer_torchaudio: bool = True,
        n_fft: int = 2048,
        hop_length: int = 512,
        n_mels: int = 128,
        fmax: Optional[int] = 8000,
        target_frames: int = 128,
        threshold_velocity: float = 0.1,
        return_velocities: bool = False,
        waveform_transform: Optional[Any] = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.labels_path = Path(labels_file)
        self.sr = sr
        self.num_classes = num_classes
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.n_mels = n_mels
        self.fmax = fmax
        self.target_frames = target_frames
        self.threshold_velocity = threshold_velocity
        self.return_velocities = return_velocities
        self.waveform_transform = waveform_transform
        
        self._torchaudio_enabled = bool(
            prefer_torchaudio and torchaudio is not None and ta_T is not None
        )
        
        # Load or set class names
        if class_names is not None:
            self.class_names = class_names
        else:
            components_path = self.data_dir / "components.json"
            if components_path.exists():
                with open(components_path, 'r') as f:
                    self.class_names = json.load(f)
            else:
                self.class_names = DEFAULT_DRUM_COMPONENTS[:num_classes]
        
        # Create class name to index mapping
        self.class_to_idx = {name: idx for idx, name in enumerate(self.class_names)}
        
        # Initialize mel spectrogram transform
        if self._torchaudio_enabled:
            self._mel_transform = ta_T.MelSpectrogram(
                sample_rate=self.sr,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                n_mels=self.n_mels,
                f_max=self.fmax,
                pad_mode="reflect",
                power=2.0,
            )
            self._amplitude_to_db = ta_T.AmplitudeToDB(stype="power")
        else:
            self._mel_transform = None
            self._amplitude_to_db = None
        
        # Load labels
        self.samples = self._load_labels()
        
        # Compute class statistics for weighted loss
        self._class_counts: Optional[np.ndarray] = None
        self._pos_weights: Optional[torch.Tensor] = None
    
    def _load_labels(self) -> List[Dict[str, Any]]:
        """Load labels from JSON or JSONL file."""
        samples = []
        
        if self.labels_path.suffix == '.jsonl':
            # JSONL format (events.jsonl) - one JSON object per line
            with open(self.labels_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if HAS_ORJSON and orjson is not None:
                        item = orjson.loads(line)
                    else:
                        item = json.loads(line)
                    samples.append(self._parse_event(item))
        else:
            # JSON format (labels.json) - list of objects
            if HAS_ORJSON and orjson is not None:
                with open(self.labels_path, 'rb') as f:
                    data = orjson.loads(f.read())
            else:
                with open(self.labels_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            for item in data:
                samples.append(self._parse_event(item))
        
        print(f"[MultiLabel] Loaded {len(samples):,} samples from {self.labels_path.name}")
        
        # Count multi-label samples
        multi_count = sum(1 for s in samples if s['label_count'] > 1)
        print(f"[MultiLabel] {multi_count:,} samples ({100*multi_count/len(samples):.1f}%) have multiple labels")
        
        return samples
    
    def _parse_event(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single event into standardized format."""
        # Get audio path
        if 'audio_path' in item:
            audio_path = item['audio_path']
        elif 'file' in item:
            audio_path = item['file']
        else:
            raise ValueError(f"No audio path found in item: {item}")
        
        # Get labels (multi-hot encoding)
        labels = np.zeros(self.num_classes, dtype=np.float32)
        velocities = np.zeros(self.num_classes, dtype=np.float32)
        label_count = 0
        
        if 'components' in item and isinstance(item['components'], list):
            # New format with components array
            for comp in item['components']:
                label_name = comp.get('label', '')
                if label_name in self.class_to_idx:
                    idx = self.class_to_idx[label_name]
                    velocity = comp.get('velocity', 1.0)
                    if velocity >= self.threshold_velocity:
                        labels[idx] = 1.0
                        velocities[idx] = velocity
                        label_count += 1
        elif 'component_idx' in item:
            # Legacy format with single component index
            idx = int(item['component_idx'])
            if 0 <= idx < self.num_classes:
                labels[idx] = 1.0
                velocities[idx] = item.get('velocity', 1.0)
                label_count = 1
        elif 'component' in item:
            # Legacy format with component name
            label_name = item['component']
            if label_name in self.class_to_idx:
                idx = self.class_to_idx[label_name]
                labels[idx] = 1.0
                velocities[idx] = item.get('velocity', 1.0)
                label_count = 1
        
        return {
            'audio_path': audio_path,
            'labels': labels,
            'velocities': velocities,
            'label_count': label_count,
        }
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]
        audio_path = self.data_dir / sample['audio_path']
        
        # Load and process audio
        waveform = self._load_audio(audio_path)
        
        if self.waveform_transform is not None:
            waveform = self.waveform_transform(waveform, self.sr)
        
        features = self._extract_features(waveform)
        
        # Get labels
        if self.return_velocities:
            labels = torch.from_numpy(sample['velocities'])
        else:
            labels = torch.from_numpy(sample['labels'])
        
        return features.float().contiguous(), labels
    
    def _load_audio(self, audio_path: Path) -> torch.Tensor:
        """Load audio file and return as mono waveform tensor."""
        if self._torchaudio_enabled and torchaudio is not None:
            waveform, sample_rate = torchaudio.load(str(audio_path))
            if waveform.size(0) > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            if sample_rate != self.sr:
                waveform = ta_F.resample(waveform, sample_rate, self.sr)
            return waveform.squeeze(0)
        else:
            # Fallback to librosa
            if librosa is None:
                raise ImportError("Either torchaudio or librosa is required")
            y, _ = librosa.load(str(audio_path), sr=self.sr, mono=True)
            return torch.from_numpy(y)
    
    def _extract_features(self, waveform: torch.Tensor) -> torch.Tensor:
        """Extract mel spectrogram features from waveform."""
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        
        if self._torchaudio_enabled and self._mel_transform is not None:
            mel = self._mel_transform(waveform)
            mel_db = self._amplitude_to_db(mel)
        else:
            # Fallback to librosa
            if librosa is None:
                raise ImportError("Either torchaudio or librosa is required")
            y = waveform.squeeze().numpy()
            mel = librosa.feature.melspectrogram(
                y=y, sr=self.sr, n_fft=self.n_fft,
                hop_length=self.hop_length, n_mels=self.n_mels,
                fmax=self.fmax
            )
            mel_db = librosa.power_to_db(mel, ref=np.max)
            mel_db = torch.from_numpy(mel_db).unsqueeze(0)
        
        # Normalize to [0, 1] range
        mel_db = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-8)
        
        # Pad or truncate to target frames
        if mel_db.size(-1) < self.target_frames:
            padding = self.target_frames - mel_db.size(-1)
            mel_db = F.pad(mel_db, (0, padding))
        elif mel_db.size(-1) > self.target_frames:
            mel_db = mel_db[..., :self.target_frames]
        
        return mel_db
    
    def get_class_counts(self) -> np.ndarray:
        """Get count of positive samples for each class."""
        if self._class_counts is None:
            counts = np.zeros(self.num_classes, dtype=np.int64)
            for sample in self.samples:
                counts += (sample['labels'] > 0).astype(np.int64)
            self._class_counts = counts
        return self._class_counts
    
    def get_pos_weights(self, method: str = "inverse") -> torch.Tensor:
        """
        Compute positive class weights for BCEWithLogitsLoss.
        
        Args:
            method: Weighting method
                - "inverse": weight = num_neg / num_pos
                - "sqrt_inverse": weight = sqrt(num_neg / num_pos)
                - "effective": Uses effective number of samples
        
        Returns:
            Tensor of shape (num_classes,) with positive weights
        """
        if self._pos_weights is None:
            counts = self.get_class_counts()
            total = len(self.samples)
            neg_counts = total - counts
            
            if method == "inverse":
                weights = neg_counts / (counts + 1)
            elif method == "sqrt_inverse":
                weights = np.sqrt(neg_counts / (counts + 1))
            elif method == "effective":
                # Effective number of samples (Cui et al., 2019)
                beta = 0.9999
                effective_num = 1.0 - np.power(beta, counts)
                weights = (1.0 - beta) / (effective_num + 1e-8)
            else:
                weights = np.ones(self.num_classes)
            
            # Clip extreme weights
            weights = np.clip(weights, 0.1, 100.0)
            self._pos_weights = torch.from_numpy(weights.astype(np.float32))
        
        return self._pos_weights
    
    def get_cooccurrence_matrix(self) -> np.ndarray:
        """
        Compute co-occurrence matrix showing which classes appear together.
        
        Returns:
            Matrix of shape (num_classes, num_classes) where entry (i,j) is
            the count of samples where both class i and class j are active.
        """
        cooccurrence = np.zeros((self.num_classes, self.num_classes), dtype=np.int64)
        
        for sample in self.samples:
            active = np.where(sample['labels'] > 0)[0]
            for i in active:
                for j in active:
                    cooccurrence[i, j] += 1
        
        return cooccurrence
    
    def print_statistics(self) -> None:
        """Print dataset statistics."""
        counts = self.get_class_counts()
        total = len(self.samples)
        
        print(f"\n{'='*60}")
        print(f"Multi-Label Dataset Statistics")
        print(f"{'='*60}")
        print(f"Total samples: {total:,}")
        print(f"\nPer-class counts:")
        print(f"{'Class':<25} {'Count':>8} {'%':>8}")
        print(f"{'-'*45}")
        
        for idx, name in enumerate(self.class_names[:self.num_classes]):
            count = counts[idx]
            pct = 100 * count / total
            print(f"{name:<25} {count:>8,} {pct:>7.1f}%")
        
        # Label distribution
        label_counts = [s['label_count'] for s in self.samples]
        print(f"\nLabels per sample distribution:")
        for n in range(1, max(label_counts) + 1):
            count = sum(1 for lc in label_counts if lc == n)
            if count > 0:
                print(f"  {n} label(s): {count:,} ({100*count/total:.1f}%)")
        
        # Top co-occurrences
        cooccur = self.get_cooccurrence_matrix()
        np.fill_diagonal(cooccur, 0)  # Remove self-co-occurrence
        
        print(f"\nTop 10 co-occurring pairs:")
        flat_idx = np.argsort(cooccur.flatten())[::-1][:10]
        for flat in flat_idx:
            i, j = flat // self.num_classes, flat % self.num_classes
            if i < j and cooccur[i, j] > 0:
                print(f"  {self.class_names[i]} + {self.class_names[j]}: {cooccur[i, j]:,}")
        
        print(f"{'='*60}\n")


def convert_singlelabel_to_multilabel(
    input_path: Path,
    output_path: Path,
    class_names: List[str]
) -> None:
    """
    Convert single-label labels.json to multi-label format.
    
    Single-label format:
        [{"file": "audio.wav", "component_idx": 9}, ...]
    
    Multi-label format:
        [{"file": "audio.wav", "components": [{"label": "kick", "velocity": 1.0}]}, ...]
    """
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    converted = []
    for item in data:
        idx = item.get('component_idx', 0)
        label = class_names[idx] if idx < len(class_names) else f"class_{idx}"
        
        new_item = {
            'file': item['file'],
            'components': [{
                'label': label,
                'velocity': item.get('velocity', 1.0)
            }]
        }
        
        # Preserve other metadata
        for key in ['onset_time', 'session_id', 'source_set']:
            if key in item:
                new_item[key] = item[key]
        
        converted.append(new_item)
    
    with open(output_path, 'w') as f:
        json.dump(converted, f, indent=2)
    
    print(f"Converted {len(converted)} samples to multi-label format")
    print(f"Output: {output_path}")
