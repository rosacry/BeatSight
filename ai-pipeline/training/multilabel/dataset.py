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


# =============================================================================
# 12-Class Drum Component Mapping (Final Production Structure)
# =============================================================================
# This matches components.json in prod_v5_final dataset
# Rimshot merged into snare, toms unified, hi-hat variants consolidated

DEFAULT_DRUM_COMPONENTS = [
    "china",         # 0
    "crash",         # 1
    "cross_stick",   # 2
    "hihat_closed",  # 3
    "hihat_open",    # 4
    "hihat_pedal",   # 5
    "kick",          # 6
    "ride_bell",     # 7
    "ride_bow",      # 8
    "snare",         # 9 (includes rimshot, snare_center, snare_rimshot)
    "splash",        # 10
    "tom",           # 11 (includes tom_high, tom_mid, tom_low)
]

# Legacy class mapping for backwards compatibility (21-class → 12-class)
LEGACY_CLASS_MAPPING = {
    "aux_percussion": None,  # Dropped
    "china": 0,
    "crash": 1,
    "cross_stick": 2,
    "hihat_closed": 3,
    "hihat_foot_splash": 5,  # Maps to hihat_pedal
    "hihat_open": 4,
    "hihat_pedal": 5,
    "hihat_splash": 4,  # Maps to hihat_open
    "kick": 6,
    "ride_bell": 7,
    "ride_bow": 8,
    "rimshot": 9,  # Maps to snare
    "snare": 9,
    "snare_center": 9,  # Maps to snare
    "snare_cross_stick": 2,  # Maps to cross_stick
    "snare_rimshot": 9,  # Maps to snare
    "splash": 10,
    "tom_high": 11,  # Maps to tom
    "tom_mid": 11,   # Maps to tom
    "tom_low": 11,   # Maps to tom
    "tom": 11,
}


class MultiLabelDrumDataset(Dataset):
    """
    PyTorch dataset for multi-label drum classification.
    
    Each sample can have multiple active drum classes (simultaneous hits).
    Labels are returned as multi-hot encoded tensors.
    
    Args:
        data_dir: Root directory containing audio files
        labels_file: Path to labels.json or events.jsonl
        sr: Sample rate (default: 44100)
        num_classes: Number of drum classes (default: 12 for production)
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
        num_classes: int = 12,  # Updated to 12-class production structure
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
            # Fallback to librosa - match training pipeline:
            # STFT -> mel filterbank -> amplitude_to_db
            if librosa is None:
                raise ImportError("Either torchaudio or librosa is required")
            y = waveform.squeeze().numpy()
            mel_fb = librosa.filters.mel(sr=self.sr, n_fft=self.n_fft, n_mels=self.n_mels, fmax=self.fmax)
            stft = np.abs(librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length))
            mel = np.dot(mel_fb, stft)
            mel_db = librosa.amplitude_to_db(mel, ref=np.max)
            mel_db = torch.from_numpy(mel_db).unsqueeze(0)
        
        # Normalize to [0, 1] range to match preextracted training data
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
        print("Multi-Label Dataset Statistics")
        print(f"{'='*60}")
        print(f"Total samples: {total:,}")
        print("\nPer-class counts:")
        print(f"{'Class':<25} {'Count':>8} {'%':>8}")
        print(f"{'-'*45}")
        
        for idx, name in enumerate(self.class_names[:self.num_classes]):
            count = counts[idx]
            pct = 100 * count / total
            print(f"{name:<25} {count:>8,} {pct:>7.1f}%")
        
        # Label distribution
        label_counts = [s['label_count'] for s in self.samples]
        print("\nLabels per sample distribution:")
        for n in range(1, max(label_counts) + 1):
            count = sum(1 for lc in label_counts if lc == n)
            if count > 0:
                print(f"  {n} label(s): {count:,} ({100*count/total:.1f}%)")
        
        # Top co-occurrences
        cooccur = self.get_cooccurrence_matrix()
        np.fill_diagonal(cooccur, 0)  # Remove self-co-occurrence
        
        print("\nTop 10 co-occurring pairs:")
        flat_idx = np.argsort(cooccur.flatten())[::-1][:10]
        for flat in flat_idx:
            i, j = flat // self.num_classes, flat % self.num_classes
            if i < j and cooccur[i, j] > 0:
                print(f"  {self.class_names[i]} + {self.class_names[j]}: {cooccur[i, j]:,}")
        
        print(f"{'='*60}\n")


# =============================================================================
# High-Performance Cached Multi-Label Dataset
# =============================================================================

class CachedMultiLabelDataset(Dataset):
    """
    High-performance multi-label dataset using consolidated cache and numpy labels.
    
    This class mirrors the single-label DrumSampleDataset from train_classifier.py
    but returns multi-hot encoded labels instead of single class indices.
    
    For multi-label data, the labels are stored as:
    - train_labels_labels.npy: Shape (N, num_classes) with multi-hot encoding
    - OR: train_labels_labels.npy: Shape (N,) with single labels (converted on-the-fly)
    
    Args:
        data_dir: Root directory containing the split (train/val)
        num_classes: Number of drum classes (default: 12)
        class_names: List of class names in order
        feature_cache_dir: Directory containing consolidated feature cache
        cache_mapping_path: Path to cache_mapping.npz for O(1) lookups
        specaugment: Optional SpecAugment transform for training
        is_multilabel: If True, expects multi-hot labels; if False, converts single-label
    """
    
    def __init__(
        self,
        data_dir: Union[str, Path],
        num_classes: int = 12,
        class_names: Optional[List[str]] = None,
        feature_cache_dir: Optional[Union[str, Path]] = None,
        cache_mapping_path: Optional[Union[str, Path]] = None,
        specaugment: Optional[Any] = None,
        is_multilabel: bool = True,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.num_classes = num_classes
        self.specaugment = specaugment
        self.is_multilabel = is_multilabel
        
        # Load class names from components.json or use defaults
        if class_names is not None:
            self.class_names = class_names
        else:
            components_path = self.data_dir.parent / "components.json"
            if components_path.exists():
                with open(components_path, 'r') as f:
                    comp_data = json.load(f)
                    if isinstance(comp_data, dict) and 'components' in comp_data:
                        self.class_names = comp_data['components']
                    elif isinstance(comp_data, list):
                        self.class_names = comp_data
                    else:
                        self.class_names = DEFAULT_DRUM_COMPONENTS[:num_classes]
            else:
                self.class_names = DEFAULT_DRUM_COMPONENTS[:num_classes]
        
        # Create class name to index mapping
        self.class_to_idx = {name: idx for idx, name in enumerate(self.class_names)}
        
        # Determine split name (train/val) for proper file naming
        split_name = self.data_dir.name  # 'train' or 'val'
        
        # Load numpy labels - support multiple naming conventions:
        # 1. features.npy + labels.npy (simple_extract.py output)
        # 2. {split}_labels_labels.npy (split-specific naming)
        # 3. train_labels_labels.npy (fallback)
        simple_features_npy = self.data_dir / "features.npy"
        simple_labels_npy = self.data_dir / "labels.npy"
        
        if simple_features_npy.exists() and simple_labels_npy.exists():
            # Simple format from simple_extract.py
            labels_npy = simple_labels_npy
            files_npy = None  # No files list in simple format
            self._simple_features_path = simple_features_npy
        else:
            # Legacy format with train_labels_*.npy naming
            labels_npy = self.data_dir / f"{split_name}_labels_labels.npy"
            files_npy = self.data_dir / f"{split_name}_labels_files.npy"
            self._simple_features_path = None
            
            # Fallback to train_labels_*.npy if split-specific files don't exist
            if not labels_npy.exists():
                labels_npy = self.data_dir / "train_labels_labels.npy"
                files_npy = self.data_dir / "train_labels_files.npy"
        
        if not labels_npy.exists():
            raise FileNotFoundError(f"Labels file not found in {self.data_dir}. "
                                   f"Expected labels.npy, {split_name}_labels_labels.npy, or train_labels_labels.npy")
        
        # Load labels with mmap for memory efficiency
        self._labels = np.load(labels_npy, mmap_mode='r')
        print(f"[MultiLabel] Loaded {len(self._labels):,} labels from {labels_npy.name}")
        
        # Check if labels are already multi-hot or single-label
        if self._labels.ndim == 2 and self._labels.shape[1] == num_classes:
            self._is_multihot = True
            print(f"[MultiLabel] Labels are multi-hot encoded ({self._labels.shape})")
        else:
            self._is_multihot = False
            if is_multilabel and self._labels.ndim == 1:
                print(f"[MultiLabel] Labels are single-index, will convert to multi-hot on-the-fly")
        
        # Load simple format features if available (from simple_extract.py)
        self._simple_features = None
        if hasattr(self, '_simple_features_path') and self._simple_features_path is not None:
            self._simple_features = np.load(self._simple_features_path, mmap_mode='r')
            print(f"[MultiLabel] Loaded {len(self._simple_features):,} pre-extracted features from features.npy")
        
        # Load source indices for synthetic multi-label samples (spectrogram blending)
        self._source_indices = None
        source_indices_npy = self.data_dir / "source_indices.npy"
        if source_indices_npy.exists():
            self._source_indices = np.load(source_indices_npy, allow_pickle=True)
            print(f"[MultiLabel] Loaded source indices for spectrogram blending ({len(self._source_indices):,} samples)")
        
        # Load pre-extracted features from real multi-label datasets (egmd, groove, etc.)
        self._real_features = None
        self._real_labels = None
        self._real_feature_files = []  # List of (features_array, labels_array) tuples
        
        # Only look for *_features.npy if not using simple format (avoid matching features.npy)
        if self._simple_features is None:
            for features_file in self.data_dir.glob('*_features.npy'):
                source_name = features_file.stem.replace('_features', '')
                labels_file = self.data_dir / f"{source_name}_labels.npy"
                if labels_file.exists():
                    feat = np.load(features_file, mmap_mode='r')
                    lab = np.load(labels_file, mmap_mode='r')
                    self._real_feature_files.append((source_name, feat, lab))
                print(f"[MultiLabel] Loaded {len(feat):,} real features from {source_name}")
        
        # If we have real features, combine them with synthetic indices
        if self._real_feature_files:
            total_real = sum(len(f[1]) for f in self._real_feature_files)
            print(f"[MultiLabel] Total real multi-label samples: {total_real:,}")
        
        # Load files (optional, only needed for audio fallback)
        self._files = None
        if files_npy.exists():
            try:
                self._files = np.load(files_npy, mmap_mode='r')
            except ValueError:
                self._files = np.load(files_npy, allow_pickle=True)
        
        # Setup consolidated cache
        self._consolidated_reader = None
        self._cache_mapping_shards = None
        self._cache_mapping_offsets = None
        self._cache_mapping_valid = None
        
        if feature_cache_dir is not None:
            feature_cache_dir = Path(feature_cache_dir)
            # Try to find consolidated cache
            # Look for split-specific cache first (e.g., feature_cache/train)
            split_name = self.data_dir.name  # 'train' or 'val'
            consolidated_dir = feature_cache_dir / split_name
            if not (consolidated_dir / "manifest.json").exists():
                consolidated_dir = feature_cache_dir  # Try root
            
            if (consolidated_dir / "manifest.json").exists():
                try:
                    # Import here to avoid circular imports
                    from training.utils.consolidated_cache import ConsolidatedCacheReader
                    self._consolidated_reader = ConsolidatedCacheReader(consolidated_dir)
                    print(f"[MultiLabel] Using consolidated cache: {len(self._consolidated_reader):,} samples")
                except ImportError:
                    print("[MultiLabel] Warning: ConsolidatedCacheReader not available")
                except Exception as e:
                    print(f"[MultiLabel] Failed to load consolidated cache: {e}")
        
        # Load cache mapping for O(1) lookups
        if cache_mapping_path is not None:
            cache_mapping_path = Path(cache_mapping_path)
            if cache_mapping_path.exists():
                try:
                    mapping_data = np.load(cache_mapping_path, allow_pickle=True, mmap_mode='r')
                    self._cache_mapping_shards = mapping_data['shard_ids']
                    self._cache_mapping_offsets = mapping_data['offsets']
                    self._cache_mapping_valid = mapping_data['valid']
                    valid_count = np.sum(self._cache_mapping_valid)
                    print(f"[MultiLabel] Using cache mapping: {valid_count:,}/{len(self._cache_mapping_valid):,} valid")
                except Exception as e:
                    print(f"[MultiLabel] Failed to load cache mapping: {e}")
            elif (self.data_dir / "cache_mapping.npz").exists():
                # Try default location
                try:
                    mapping_data = np.load(self.data_dir / "cache_mapping.npz", allow_pickle=True, mmap_mode='r')
                    self._cache_mapping_shards = mapping_data['shard_ids']
                    self._cache_mapping_offsets = mapping_data['offsets']
                    self._cache_mapping_valid = mapping_data['valid']
                    valid_count = np.sum(self._cache_mapping_valid)
                    print(f"[MultiLabel] Using cache mapping: {valid_count:,}/{len(self._cache_mapping_valid):,} valid")
                except Exception as e:
                    print(f"[MultiLabel] Failed to load cache mapping: {e}")
        
        # Compute class statistics
        self._class_counts = None
        self._pos_weights = None
        
        # Compute combined dataset size (synthetic + real)
        self._synthetic_size = len(self._labels) if self._source_indices is not None else 0
        self._real_sizes = [(name, len(feat)) for name, feat, lab in self._real_feature_files]
        self._total_real = sum(size for _, size in self._real_sizes)
        
        # Build index mapping for real features
        self._real_index_offsets = []
        offset = self._synthetic_size
        for name, feat, lab in self._real_feature_files:
            self._real_index_offsets.append((offset, offset + len(feat), feat, lab))
            offset += len(feat)
        
        if self._real_feature_files:
            print(f"[MultiLabel] Combined dataset: {self._synthetic_size:,} synthetic + {self._total_real:,} real = {self._synthetic_size + self._total_real:,} total")
    
    def __len__(self) -> int:
        # Return combined size of synthetic + real samples
        if self._source_indices is not None and self._real_feature_files:
            return len(self._source_indices) + self._total_real
        elif self._real_feature_files:
            return self._total_real
        return len(self._labels)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        # Check if this is a real sample (idx >= synthetic size)
        if self._real_index_offsets and idx >= self._synthetic_size:
            # Find which real dataset this belongs to
            for start_offset, end_offset, feat_array, lab_array in self._real_index_offsets:
                if start_offset <= idx < end_offset:
                    real_idx = idx - start_offset
                    features = torch.from_numpy(feat_array[real_idx].copy())
                    if features.ndim == 2:
                        features = features.unsqueeze(0)  # Add channel dim
                    labels = torch.from_numpy(lab_array[real_idx].copy()).float()
                    
                    # Apply specaugment if provided
                    if self.specaugment is not None:
                        features = self.specaugment(features)
                    
                    return features.float().contiguous(), labels
        
        # Simple format: load from pre-extracted features.npy
        if self._simple_features is not None:
            features = torch.from_numpy(self._simple_features[idx].copy())
            if features.ndim == 2:
                features = features.unsqueeze(0)  # Add channel dim (1, H, W)
            
            # Apply specaugment if provided
            if self.specaugment is not None:
                features = self.specaugment(features)
            
            # Get labels
            labels = torch.from_numpy(self._labels[idx].copy()).float()
            
            return features.float().contiguous(), labels
        
        # Synthetic sample: get features from cache (with blending)
        if self._source_indices is not None:
            # Synthetic multi-label: blend spectrograms from source samples
            features = self._load_blended_features(idx)
        else:
            # Regular: load single sample features
            features = self._load_features(idx)
        
        # Apply specaugment if provided (training only)
        if self.specaugment is not None:
            features = self.specaugment(features)
        
        # Get multi-hot labels
        if self._is_multihot:
            labels = torch.from_numpy(self._labels[idx].copy()).float()
        else:
            # Convert single-label to multi-hot
            label_idx = int(self._labels[idx])
            labels = torch.zeros(self.num_classes, dtype=torch.float32)
            if 0 <= label_idx < self.num_classes:
                labels[label_idx] = 1.0
        
        return features.float().contiguous(), labels
    
    def _load_blended_features(self, idx: int) -> torch.Tensor:
        """Load and blend spectrograms from multiple source samples.
        
        Blending strategies:
        - max: Takes maximum value at each point (preserves peaks, fast)
        - mean: Averages values (more realistic acoustic mixing)
        - weighted: Uses class-specific weights to prevent masking of quiet instruments
        - softmax: Soft-max pooling (smooth approximation of max)
        """
        source_indices = self._source_indices[idx]
        
        if not hasattr(source_indices, '__len__') or len(source_indices) == 0:
            # Fallback: single sample
            return self._load_features(int(source_indices) if not hasattr(source_indices, '__len__') else source_indices[0])
        
        # Load all source spectrograms
        spectrograms = []
        labels = self._labels[idx] if hasattr(self, '_labels') else None
        
        for src_idx in source_indices:
            try:
                spec = self._load_features(int(src_idx))
                spectrograms.append(spec)
            except Exception as e:
                # Skip failed samples
                continue
        
        if len(spectrograms) == 0:
            raise RuntimeError(f"Failed to load any source samples for index {idx}")
        
        if len(spectrograms) == 1:
            return spectrograms[0]
        
        # Get blending strategy from instance variable
        blending_strategy = getattr(self, 'blending_strategy', 'max')
        
        stacked = torch.stack(spectrograms, dim=0)  # (N, C, H, W)
        
        if blending_strategy == 'max':
            # Max pooling: preserves strongest signal at each point
            blended = stacked.max(dim=0)[0]
            
        elif blending_strategy == 'mean':
            # Mean: more realistic acoustic mixing
            blended = stacked.mean(dim=0)
            
        elif blending_strategy == 'softmax':
            # Soft-max pooling with temperature
            # Higher temp = more like mean, lower temp = more like max
            temperature = getattr(self, 'blending_temperature', 2.0)
            weights = torch.softmax(stacked / temperature, dim=0)
            blended = (weights * stacked).sum(dim=0)
            
        elif blending_strategy == 'weighted_sum':
            # Weighted sum with class-specific boosts for quiet instruments
            # This helps hihat_pedal, cross_stick etc. not get masked
            weights = torch.ones(len(spectrograms), dtype=torch.float32)
            if labels is not None:
                class_boost = getattr(self, 'class_boost_weights', None)
                if class_boost is not None:
                    # Boost weights for samples containing boosted classes
                    for i, src_idx in enumerate(source_indices):
                        src_label = self._get_source_label(int(src_idx))
                        if src_label is not None:
                            for cls_idx, boost in class_boost.items():
                                if src_label == cls_idx:
                                    weights[i] *= boost
            
            weights = weights / weights.sum()  # Normalize
            weights = weights.view(-1, 1, 1, 1)
            blended = (weights * stacked).sum(dim=0)
            
        else:
            # Default to max
            blended = stacked.max(dim=0)[0]
        
        return blended
    
    def _get_source_label(self, src_idx: int) -> Optional[int]:
        """Get the single-label class for a source sample (for weighted blending)."""
        # This would need access to the source dataset's labels
        # For now, return None (not implemented)
        return None
    
    def _load_features(self, idx: int) -> torch.Tensor:
        """Load pre-computed mel spectrogram features from cache."""
        # Try direct cache mapping first (O(1) lookup)
        if (self._cache_mapping_valid is not None and 
            self._consolidated_reader is not None and
            idx < len(self._cache_mapping_valid) and
            self._cache_mapping_valid[idx]):
            
            shard_id = int(self._cache_mapping_shards[idx])
            offset = int(self._cache_mapping_offsets[idx])
            # Use _read_sample for direct shard/offset access
            return self._consolidated_reader._read_sample(shard_id, offset)
        
        # Fallback: Try to load from consolidated reader using file path
        if self._consolidated_reader is not None and self._files is not None:
            file_bytes = self._files[idx]
            if isinstance(file_bytes, bytes):
                file_path = file_bytes.decode('utf-8')
            else:
                file_path = str(file_bytes)
            
            # Try to find in cache by file path
            try:
                sample = self._consolidated_reader.get_by_path(file_path)
                if sample is not None:
                    return sample
            except (KeyError, AttributeError):
                pass
        
        raise RuntimeError(f"Cannot load features for sample {idx}: no valid cache mapping or reader")
    
    def get_class_counts(self) -> np.ndarray:
        """Get count of positive samples for each class."""
        if self._class_counts is None:
            if self._is_multihot:
                # Sum columns for multi-hot labels
                self._class_counts = np.sum(self._labels, axis=0).astype(np.int64)
            else:
                # Count occurrences for single-label
                counts = np.zeros(self.num_classes, dtype=np.int64)
                unique, unique_counts = np.unique(self._labels, return_counts=True)
                for idx, count in zip(unique, unique_counts):
                    if 0 <= idx < self.num_classes:
                        counts[int(idx)] = count
                self._class_counts = counts
        return self._class_counts
    
    def get_pos_weights(self, method: str = "sqrt_inverse") -> torch.Tensor:
        """
        Compute positive class weights for BCEWithLogitsLoss.
        
        Args:
            method: Weighting method
                - "inverse": weight = num_neg / num_pos
                - "sqrt_inverse": weight = sqrt(num_neg / num_pos)
                - "effective": Uses effective number of samples (CVPR 2019)
        
        Returns:
            Tensor of shape (num_classes,) with positive weights
        """
        if self._pos_weights is None:
            counts = self.get_class_counts()
            total = len(self._labels)
            neg_counts = total - counts
            
            if method == "inverse":
                weights = neg_counts / (counts + 1)
            elif method == "sqrt_inverse":
                weights = np.sqrt(neg_counts / (counts + 1))
            elif method == "effective":
                beta = 0.9999
                effective_num = 1.0 - np.power(beta, counts)
                weights = (1.0 - beta) / (effective_num + 1e-8)
            else:
                weights = np.ones(self.num_classes)
            
            weights = np.clip(weights, 0.1, 100.0)
            self._pos_weights = torch.from_numpy(weights.astype(np.float32))
        
        return self._pos_weights
    
    def get_sample_weights(self, method: str = "rare_class") -> np.ndarray:
        """
        Compute per-sample weights for balanced sampling.
        
        This is crucial for class-balanced training - samples containing
        rare classes (hihat_pedal, cross_stick, ride_bow) get higher weights
        so they are sampled more frequently during training.
        
        Args:
            method: Weighting method
                - "rare_class": Weight by inverse frequency of rarest class in sample
                - "mean_class": Weight by mean inverse frequency of all classes in sample
                - "max_class": Weight by inverse frequency of most common class (less aggressive)
        
        Returns:
            Array of shape (num_samples,) with sampling weights
        """
        counts = self.get_class_counts().astype(np.float64)
        total = len(self._labels)
        
        # Compute class frequencies and inverse weights
        class_freq = counts / total
        class_weights = 1.0 / (class_freq + 1e-8)  # Inverse frequency
        class_weights = class_weights / class_weights.sum() * self.num_classes  # Normalize
        
        # Compute per-sample weight
        sample_weights = np.zeros(len(self._labels), dtype=np.float64)
        
        if self._is_multihot:
            for i in range(len(self._labels)):
                active = np.where(self._labels[i] > 0)[0]
                if len(active) == 0:
                    sample_weights[i] = 1.0
                else:
                    weights_for_active = class_weights[active]
                    if method == "rare_class":
                        # Use weight of rarest class (highest weight)
                        sample_weights[i] = np.max(weights_for_active)
                    elif method == "mean_class":
                        # Average weight of all active classes
                        sample_weights[i] = np.mean(weights_for_active)
                    elif method == "max_class":
                        # Use weight of most common class (lowest weight, less aggressive)
                        sample_weights[i] = np.min(weights_for_active)
                    else:
                        sample_weights[i] = np.max(weights_for_active)
        else:
            # Single-label: direct class weight lookup
            for i in range(len(self._labels)):
                label_idx = int(self._labels[i])
                if 0 <= label_idx < self.num_classes:
                    sample_weights[i] = class_weights[label_idx]
                else:
                    sample_weights[i] = 1.0
        
        # Add real samples' weights if present
        if hasattr(self, '_real_index_offsets') and self._real_index_offsets:
            real_weights = []
            for start_offset, end_offset, feat_array, lab_array in self._real_index_offsets:
                for j in range(len(lab_array)):
                    active = np.where(lab_array[j] > 0)[0]
                    if len(active) == 0:
                        real_weights.append(1.0)
                    else:
                        weights_for_active = class_weights[active]
                        if method == "rare_class":
                            real_weights.append(np.max(weights_for_active))
                        elif method == "mean_class":
                            real_weights.append(np.mean(weights_for_active))
                        else:
                            real_weights.append(np.min(weights_for_active))
            sample_weights = np.concatenate([sample_weights, np.array(real_weights)])
        
        return sample_weights
    
    def get_multilabel_statistics(self) -> Dict[str, Any]:
        """Compute and return multi-label dataset statistics."""
        if self._is_multihot:
            # Count labels per sample
            labels_per_sample = np.sum(self._labels > 0, axis=1)
        else:
            labels_per_sample = np.ones(len(self._labels), dtype=np.int64)
        
        multi_count = np.sum(labels_per_sample > 1)
        avg_labels = np.mean(labels_per_sample)
        
        # Class counts
        counts = self.get_class_counts()
        
        stats = {
            "total_samples": len(self._labels),
            "samples_with_multilabel": int(multi_count),
            "avg_labels_per_sample": float(avg_labels),
            "class_counts": {self.class_names[i]: int(counts[i]) for i in range(self.num_classes)},
        }
        
        return stats
    
    def print_statistics(self) -> None:
        """Print dataset statistics."""
        stats = self.get_multilabel_statistics()
        counts = self.get_class_counts()
        total = len(self._labels)
        
        print(f"\n{'='*60}")
        print("Multi-Label Dataset Statistics")
        print(f"{'='*60}")
        print(f"Total samples: {total:,}")
        print(f"Samples with multiple labels: {stats['samples_with_multilabel']:,} ({100*stats['samples_with_multilabel']/total:.1f}%)")
        print(f"Average labels per sample: {stats['avg_labels_per_sample']:.2f}")
        
        print("\nPer-class counts:")
        print(f"{'Class':<20} {'Count':>10} {'%':>8}")
        print(f"{'-'*40}")
        
        for idx, name in enumerate(self.class_names[:self.num_classes]):
            count = counts[idx]
            pct = 100 * count / total
            print(f"{name:<20} {count:>10,} {pct:>7.1f}%")
        
        print(f"{'='*60}\n")


class BatchedMultiLabelDataset(Dataset):
    """
    High-performance multi-label dataset that loads from batched .npy files via manifest.
    
    This is designed for large datasets (e.g., EGMD with 4.6M samples) where consolidating
    all data into single files would require 300+ GB. Instead, this loads from many small
    batch files (~3200 samples each) with manifest-based indexing.
    
    Manifest format (JSON):
    {
        "dataset": "egmd",
        "total_samples": 4635498,
        "batch_count": 1444,
        "batches": [
            {"features": "features_batch_0.npy", "labels": "labels_batch_0.npy", "samples": 3214},
            ...
        ]
    }
    
    Args:
        manifest_path: Path to the manifest JSON file
        batch_dir: Directory containing batch files (default: same as manifest)
        specaugment: Optional SpecAugment transform for training
        num_classes: Number of drum classes (default: 12)
        shuffle_batches: Whether to shuffle batch order (for training)
        preload_batches: Number of batches to preload (0 = load on demand)
    """
    
    def __init__(
        self,
        manifest_path: Union[str, Path],
        batch_dir: Optional[Union[str, Path]] = None,
        specaugment: Optional[Any] = None,
        num_classes: int = 12,
        shuffle_batches: bool = False,
        preload_batches: int = 0,
        is_train: bool = True,
        train_ratio: float = 0.9,
        max_cache_batches: int = 100,  # Maximum batches to keep in memory (for balanced sampling)
        shuffle_before_split: bool = True,  # Shuffle batches BEFORE train/val split for stratification
        split_seed: int = 42,  # Seed for reproducible train/val split
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self._max_cache_batches = max_cache_batches
        self.batch_dir = Path(batch_dir) if batch_dir else self.manifest_path.parent
        self.specaugment = specaugment
        self.num_classes = num_classes
        self.is_train = is_train
        self.train_ratio = train_ratio
        
        # Handle nested batch directory (egmd/egmd_batches pattern)
        if not any(self.batch_dir.glob('features_batch_*.npy')):
            # Look for subdirectory matching dataset name
            for subdir in self.batch_dir.iterdir():
                if subdir.is_dir() and any(subdir.glob('features_batch_*.npy')):
                    self.batch_dir = subdir
                    break
        
        # Load manifest
        with open(self.manifest_path, 'r') as f:
            self.manifest = json.load(f)
        self.dataset_name = self.manifest.get('dataset', self.manifest_path.parent.name)
        
        self.total_samples = self.manifest['total_samples']
        self.batch_count = self.manifest['batch_count']
        raw_batches = self.manifest['batches']
        
        # Normalize batch format: handle both list and dict formats
        if isinstance(raw_batches, dict):
            # Dict format (e.g., Slakh): {"0": {...}, "1": {...}, ...}
            # Convert to sorted list by numeric key
            self.batches = [raw_batches[str(i)] for i in range(len(raw_batches))]
        else:
            # List format (e.g., EGMD, Groove): [{...}, {...}, ...]
            self.batches = raw_batches
        
        # Normalize key names: features_file -> features, labels_file -> labels
        for batch in self.batches:
            if 'features_file' in batch and 'features' not in batch:
                batch['features'] = batch['features_file']
            if 'labels_file' in batch and 'labels' not in batch:
                batch['labels'] = batch['labels_file']
        
        # Create batch indices and optionally shuffle BEFORE splitting
        # This ensures train and val have similar class distributions
        all_batch_indices = list(range(self.batch_count))
        if shuffle_before_split:
            rng = np.random.RandomState(split_seed)  # Reproducible shuffle
            rng.shuffle(all_batch_indices)
        
        # Build index mapping: global_idx -> (batch_idx, local_idx)
        # Also compute cumulative samples for O(1) batch lookup
        # NOTE: cumsum uses original batch order, active_batches maps to shuffled order
        self._batch_cumsum = np.zeros(self.batch_count + 1, dtype=np.int64)
        for i, batch in enumerate(self.batches):
            self._batch_cumsum[i + 1] = self._batch_cumsum[i] + batch['samples']
        
        # Verify total
        actual_total = self._batch_cumsum[-1]
        if actual_total != self.total_samples:
            print(f"[BatchedDataset] Warning: manifest claims {self.total_samples:,} but batches sum to {actual_total:,}")
            self.total_samples = actual_total
        
        # Train/val split based on shuffled batch indices (not samples)
        n_train_batches = int(self.batch_count * train_ratio)
        if is_train:
            self._active_batches = all_batch_indices[:n_train_batches]
            self._num_samples = sum(self.batches[b]['samples'] for b in self._active_batches)
        else:
            self._active_batches = all_batch_indices[n_train_batches:]
            self._num_samples = sum(self.batches[b]['samples'] for b in self._active_batches)
        
        # Build cumsum for active batches (in active batch order)
        self._active_cumsum = np.zeros(len(self._active_batches) + 1, dtype=np.int64)
        for i, batch_idx in enumerate(self._active_batches):
            self._active_cumsum[i + 1] = self._active_cumsum[i] + self.batches[batch_idx]['samples']
        
        # Optional batch shuffling (for training) - shuffle the order of active batches
        if shuffle_batches and is_train:
            # Note: this shuffles for epoch-level randomness, different from split shuffling
            np.random.shuffle(self._active_batches)
            # Rebuild cumsum after shuffling
            self._active_cumsum = np.zeros(len(self._active_batches) + 1, dtype=np.int64)
            for i, batch_idx in enumerate(self._active_batches):
                self._active_cumsum[i + 1] = self._active_cumsum[i] + self.batches[batch_idx]['samples']
        
        # Cache for loaded batches (LRU-style)
        self._batch_cache: Dict[int, Tuple[np.ndarray, np.ndarray]] = {}
        self._cache_order: List[int] = []
        self._max_cache_size = max(self._max_cache_batches, preload_batches)  # Use configured max cache
        
        # Preload some batches for faster first epoch
        if preload_batches > 0:
            print(f"[BatchedDataset] Preloading {preload_batches} batches...")
            for i in range(min(preload_batches, len(self._active_batches))):
                batch_idx = self._active_batches[i]
                self._load_batch(batch_idx)
        
        split_name = "train" if is_train else "val"
        print(f"[BatchedDataset] {split_name}: {self._num_samples:,} samples across {len(self._active_batches)} batches"
              f" (shuffle_before_split={shuffle_before_split})")
        print(f"[BatchedDataset] Batch directory: {self.batch_dir}")
    
    def _load_batch(self, batch_idx: int) -> Tuple[np.ndarray, np.ndarray]:
        """Load a batch from disk or cache."""
        if batch_idx in self._batch_cache:
            return self._batch_cache[batch_idx]
        
        batch_info = self.batches[batch_idx]
        feat_rel = batch_info['features']
        label_rel = batch_info['labels']
        
        # If path contains directory component (e.g., "slakh_batches/features_batch_0.npy"),
        # use manifest parent as base. Otherwise use batch_dir.
        if '/' in feat_rel or '\\' in feat_rel:
            feat_path = self.manifest_path.parent / feat_rel
            label_path = self.manifest_path.parent / label_rel
        else:
            feat_path = self.batch_dir / feat_rel
            label_path = self.batch_dir / label_rel
        
        # Use memory-mapped loading to avoid OOM with multiple workers
        # mmap_mode='r' means read-only, data is loaded on-demand from disk
        features = np.load(feat_path, mmap_mode='r')
        labels = np.load(label_path, mmap_mode='r')
        
        # Don't cache mmap arrays (they're already efficient)
        # Just return directly - each access reads from disk but with OS-level caching
        return features, labels
    
    def _global_to_batch_local(self, global_idx: int) -> Tuple[int, int]:
        """Convert global sample index to (actual_batch_idx, local_idx) for train or val split."""
        # Binary search in active cumsum to find which active batch
        active_batch_pos = np.searchsorted(self._active_cumsum[1:], global_idx + 1, side='left')
        local_idx = global_idx - int(self._active_cumsum[active_batch_pos])
        
        # Map to actual batch index
        actual_batch_idx = self._active_batches[active_batch_pos]
        
        return int(actual_batch_idx), int(local_idx)
    
    def __len__(self) -> int:
        return self._num_samples
    
    def __getstate__(self):
        """Exclude cache from pickling for Windows multiprocessing."""
        state = self.__dict__.copy()
        # Remove unpicklable/large cached data
        state['_batch_cache'] = {}
        state['_cache_order'] = []
        return state
    
    def __setstate__(self, state):
        """Restore state after unpickling."""
        self.__dict__.update(state)
        # Reinitialize cache
        if '_batch_cache' not in self.__dict__:
            self._batch_cache = {}
        if '_cache_order' not in self.__dict__:
            self._cache_order = []
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        batch_idx, local_idx = self._global_to_batch_local(idx)
        
        features, labels = self._load_batch(batch_idx)
        
        # Get sample
        feat = torch.from_numpy(features[local_idx].copy())
        label = torch.from_numpy(labels[local_idx].copy())
        
        # Ensure correct shape: (C, H, W)
        if feat.ndim == 2:
            feat = feat.unsqueeze(0)  # Add channel dim
        
        # Apply specaugment if provided
        if self.specaugment is not None:
            feat = self.specaugment(feat)
        
        return feat.float().contiguous(), label.float()
    
    def get_class_counts(self) -> np.ndarray:
        """Compute class counts for class-balanced loss (scans all labels once)."""
        if hasattr(self, '_class_counts_cache') and self._class_counts_cache is not None:
            return self._class_counts_cache
            
        counts = np.zeros(self.num_classes, dtype=np.int64)
        
        # Only count active batches (train or val)
        for batch_idx in self._active_batches:
            _, labels = self._load_batch(batch_idx)
            counts += labels.sum(axis=0).astype(np.int64)
        
        self._class_counts_cache = counts
        return counts
    
    def get_sample_weights(self, method: str = "rare_class") -> np.ndarray:
        """
        Compute per-sample weights for balanced sampling.
        
        For multi-label, weights samples by the rarest class they contain,
        so rare classes (hihat_pedal, cross_stick, ride_bow) get sampled more.
        
        Args:
            method: Weighting method
                - "rare_class": Weight by inverse frequency of rarest class in sample
                - "mean_class": Weight by mean inverse frequency of all classes in sample
        
        Returns:
            Array of shape (num_samples,) with sampling weights
        """
        # First compute total samples in active batches
        total_samples = sum(self.batches[i]['samples'] for i in self._active_batches)
        
        # Handle empty datasets (e.g., MedleyDB with 0 train samples)
        if total_samples == 0:
            print(f"[BatchedDataset] Skipping empty dataset (0 samples)")
            return np.array([], dtype=np.float64)
        
        # Compute class counts fresh (don't use cached which might be from different batch set)
        counts = np.zeros(self.num_classes, dtype=np.int64)
        for batch_idx in self._active_batches:
            _, labels = self._load_batch(batch_idx)
            counts += labels.sum(axis=0).astype(np.int64)
        
        # Compute class inverse frequency weights
        # Handle zero counts by setting them to min non-zero count
        nonzero_counts = counts[counts > 0]
        min_count = nonzero_counts.min() if len(nonzero_counts) > 0 else 1
        safe_counts = np.maximum(counts, min_count)
        
        class_weights = total_samples / safe_counts.astype(np.float64)
        # Normalize so mean weight = 1 (handle case where all counts are 0)
        mean_weight = class_weights.mean()
        if mean_weight > 0 and not np.isnan(mean_weight):
            class_weights = class_weights / mean_weight
        else:
            class_weights = np.ones(self.num_classes, dtype=np.float64)
        
        print(f"[BatchedDataset] Computing sample weights for {total_samples:,} samples...")
        print(f"[BatchedDataset] Class counts: {counts}")
        print(f"[BatchedDataset] Class weight range: [{class_weights.min():.2f}, {class_weights.max():.2f}]")
        
        # Compute per-sample weight
        sample_weights = []
        
        for batch_idx in self._active_batches:
            _, labels = self._load_batch(batch_idx)
            
            for local_idx in range(len(labels)):
                active = np.where(labels[local_idx] > 0)[0]
                if len(active) == 0:
                    sample_weights.append(1.0)
                else:
                    weights_for_active = class_weights[active]
                    if method == "rare_class":
                        sample_weights.append(float(np.max(weights_for_active)))
                    elif method == "mean_class":
                        sample_weights.append(float(np.mean(weights_for_active)))
                    else:
                        sample_weights.append(float(np.max(weights_for_active)))
        
        sample_weights = np.array(sample_weights, dtype=np.float64)
        print(f"[BatchedDataset] Sample weights: min={sample_weights.min():.2f}, max={sample_weights.max():.2f}, mean={sample_weights.mean():.2f}")
        return sample_weights
    
    def print_statistics(self) -> None:
        """Print dataset statistics."""
        split_name = "Train" if self.is_train else "Val"
        print(f"\n{'='*60}")
        print(f"{split_name} Dataset Statistics (BatchedMultiLabelDataset)")
        print(f"{'='*60}")
        print(f"Total samples: {self._num_samples:,}")
        print(f"Active batches: {len(self._active_batches)}")
        print(f"Batch directory: {self.batch_dir}")
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
