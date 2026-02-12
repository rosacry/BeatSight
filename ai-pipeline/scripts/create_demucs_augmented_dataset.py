#!/usr/bin/env python3
"""
Create Demucs-Augmented Training Data for Domain Gap Elimination

This script processes raw audio through Demucs source separation to create
training data that matches the spectral characteristics seen at inference time.

The core problem: The model was trained on clean drum audio (electronic kit recordings,
MIDI-synthesized, dry acoustic mixes). At inference, audio passes through Demucs
separation first, which introduces spectral artifacts (high-freq attenuation,
temporal smoothing, cross-bleed). The model never saw these artifacts during training.

Solution: Process training audio through Demucs → extract spectrograms → fine-tune.

Four augmentation modes:

1. ENST wet_mix → Demucs (--source enst)
   - ENST has pre-mixed `wet_mix` recordings (drums + accompaniment)
   - Run Demucs on wet_mix → get estimated drums stem
   - Extract spectrograms using ground-truth labels from JSONL events
   - ~319 recordings, ~45K onset events
   - THIS IS THE GOLD STANDARD: real acoustic drums in real mixes
   - Processing time: ~15 minutes on GPU

2. Slakh2100 mix.flac → Demucs (--source slakh)
   - Slakh has full multi-instrument mixes (mix.flac) with MIDI-derived labels
   - Run Demucs on mix.flac → get estimated drums stem
   - CRITICAL: Only dataset with china (2K) and splash (6.5K) events
   - ~1708 tracks, ~262K onset events
   - Processing time: ~2-4 hours on GPU

3. EGMD + musdb18 mixing → Demucs (--source egmd)
   - Mix EGMD electronic drum stems with random musdb18 non-drum stems
   - Run Demucs on the mixture → get estimated drums
   - Use existing MIDI-derived labels from JSONL events
   - Subsample configurable number of recordings (default 5000)
   - Processing time: ~2-8 hours on GPU

4. Groove MIDI + musdb18 mixing → Demucs (--source groove)
   - Same approach as EGMD but for Groove MIDI dataset
   - All ~1090 recordings
   - Processing time: ~30 minutes on GPU

All four phases are recommended. ENST provides the highest-quality signal (real
acoustic drums in real mixes), Slakh2100 provides critical china/splash coverage,
while EGMD provides volume and rare-class coverage for robust domain adaptation.

Output: batched .npy files + manifest.json in F:/datasets/multilabel_real_v3/
The training script auto-discovers these via *_manifest.json glob patterns.

Optimizations (adopted from extract_multilabel_from_midi.py):
  - Checkpoint/resume: crash recovery via JSON checkpoint per phase
  - Incremental disk flushing: every 2000 samples, prevents OOM on large datasets
  - In-memory Demucs: EGMD/Groove pass tensors directly, skip temp file I/O
  - Audio prefetch: overlaps D: HDD reads with GPU Demucs processing
  - Skip-if-completed: checks manifest existence before reprocessing
  - Graceful Ctrl-C: saves checkpoint on interruption

Usage:
    # Analyze what's available
    python scripts/create_demucs_augmented_dataset.py --analyze

    # Process ENST through Demucs (highest impact, do first)
    python scripts/create_demucs_augmented_dataset.py --source enst

    # Process Slakh2100 (critical for china/splash coverage)
    python scripts/create_demucs_augmented_dataset.py --source slakh

    # Process Groove MIDI
    python scripts/create_demucs_augmented_dataset.py --source groove

    # Process EGMD (subsample 5000 files for rare-class coverage)
    python scripts/create_demucs_augmented_dataset.py --source egmd --max-files 5000

    # Or process all sources in sequence
    python scripts/create_demucs_augmented_dataset.py --source all

    # Force reprocessing (ignores existing manifests and checkpoints)
    python scripts/create_demucs_augmented_dataset.py --source enst --force
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import shutil
import signal
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import librosa
except ImportError:
    print("ERROR: librosa required. pip install librosa")
    sys.exit(1)

try:
    import torch
    import torchaudio
except ImportError:
    print("ERROR: torch + torchaudio required")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    sf = None  # Only needed for ENST (file-based Demucs)

from tqdm import tqdm


# ============================================================================
# Graceful Shutdown
# ============================================================================

_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle Ctrl-C: set flag so current file finishes, then checkpoint saves."""
    global _shutdown_requested
    if _shutdown_requested:
        print("\n\n   Force quit!")
        sys.exit(1)
    _shutdown_requested = True
    print("\n\n   ⚠️ Ctrl-C detected. Finishing current file and saving checkpoint...")


# ============================================================================
# Configuration
# ============================================================================

# Output directory (same root as existing training data)
OUTPUT_BASE = Path("F:/datasets/multilabel_real_v3")

# Raw audio roots
# Prefer F: NVMe (7250 MB/s) over D: USB HDD (120 MB/s) where data exists
# musdb18_hq: robocopy D:\data\raw\musdb18_hq F:\data\raw\musdb18_hq /E /MT:4
AUDIO_ROOTS = {
    "enst_drums": Path("D:/data/raw/ENST-Drums"),       # Only on D:
    "egmd": Path("F:/data/raw/egmd"),                    # F: NVMe — 60x faster
    "groove_midi": Path("F:/data/raw/groove_midi"),      # F: NVMe — 60x faster
    "slakh2100": Path("D:/data/raw/slakh2100"),          # Only on D: (HDD — GPU is bottleneck)
    "musdb18_hq": Path("F:/data/raw/musdb18_hq") if Path("F:/data/raw/musdb18_hq").exists()
                  else Path("D:/data/raw/musdb18_hq"),   # F: NVMe if copied, else D:
}

# JSONL event manifest directory
MANIFESTS_DIR = Path("training/data/manifests")

# Feature extraction parameters (MUST match training pipeline exactly!)
SAMPLE_RATE = 22050
N_MELS = 128
N_FFT = 2048
FMAX = 8000
TARGET_FRAMES = 128

# Batch parameters
BATCH_SIZE = 2000  # Samples per batch file (matches existing ~1900-2500)
TRAIN_RATIO = 0.8

# Incremental flush threshold (from extract_multilabel_from_midi.py)
# Flush to disk every N samples to prevent OOM on large datasets
FLUSH_THRESHOLD = 2000

# 12-class drum component mapping (MUST match training)
CLASS_NAMES = [
    'china', 'crash', 'cross_stick', 'hihat_closed', 'hihat_open',
    'hihat_pedal', 'kick', 'ride_bell', 'ride_bow', 'snare', 'splash', 'tom'
]
CLASS_TO_IDX = {name: idx for idx, name in enumerate(CLASS_NAMES)}

# Label normalization (same as create_full_acoustic_dataset.py)
LABEL_MAP = {
    'tom_high': 'tom', 'tom_mid': 'tom', 'tom_low': 'tom',
    'tom_floor': 'tom', 'tom1': 'tom', 'tom2': 'tom', 'tom3': 'tom',
    'snare_center': 'snare', 'snare_edge': 'snare', 'snare_rimshot': 'snare',
    'snare_cross_stick': 'cross_stick', 'rimshot': 'snare',
    'hihat_foot_splash': 'hihat_pedal', 'hihat_splash': 'hihat_open',
    'hihat_foot': 'hihat_pedal', 'hihat_half_open': 'hihat_open',
    'ride': 'ride_bow', 'ride_edge': 'ride_bow', 'ride_crash': 'crash',
    'crash1': 'crash', 'crash2': 'crash',
}

# Demucs separation model
DEMUCS_MODEL = "htdemucs_ft"


# ============================================================================
# Feature Extraction (matches training pipeline EXACTLY)
# ============================================================================

def extract_mel_spectrogram(
    audio: np.ndarray,
    sr: int,
    onset_time: float,
    window_ms: float = 100.0,
    n_mels: int = N_MELS,
    target_width: int = TARGET_FRAMES,
) -> Optional[np.ndarray]:
    """
    Extract a mel-spectrogram centered on an onset time.

    This MUST produce identical spectrograms to the training extraction pipeline.
    Uses: power mel spectrogram, power_to_db, normalize [0,1], asymmetric window.
    """
    window_samples = int(sr * window_ms / 1000.0)
    center = int(onset_time * sr)

    # Asymmetric window: more audio after the onset (matches training)
    start = max(0, center - window_samples // 4)
    end = min(len(audio), center + window_samples)

    if end - start < window_samples // 4:
        return None

    window = audio[start:end]

    # Pad if necessary
    if len(window) < window_samples:
        window = np.pad(window, (0, window_samples - len(window)), mode='constant')

    # Compute mel-spectrogram (power, not amplitude)
    hop_length = max(1, len(window) // target_width)
    mel_spec = librosa.feature.melspectrogram(
        y=window, sr=sr, n_mels=n_mels, fmax=FMAX, hop_length=hop_length
    )

    # Convert to dB scale
    mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)

    # Normalize to [0, 1]
    mel_min, mel_max = mel_spec_db.min(), mel_spec_db.max()
    if mel_max - mel_min > 1e-8:
        mel_spec_norm = (mel_spec_db - mel_min) / (mel_max - mel_min)
    else:
        mel_spec_norm = np.zeros_like(mel_spec_db)

    # Resize to target width if needed
    if mel_spec_norm.shape[1] != target_width:
        from scipy.ndimage import zoom
        zoom_factor = target_width / mel_spec_norm.shape[1]
        mel_spec_norm = zoom(mel_spec_norm, (1, zoom_factor), order=1)
        mel_spec_norm = mel_spec_norm[:, :target_width]
        if mel_spec_norm.shape[1] < target_width:
            mel_spec_norm = np.pad(
                mel_spec_norm,
                ((0, 0), (0, target_width - mel_spec_norm.shape[1])),
                mode='constant'
            )

    return mel_spec_norm.astype(np.float32)


def normalize_label(label: str) -> Optional[str]:
    """Normalize a label string to standard 12-class vocabulary."""
    label = label.lower().strip()
    if label in CLASS_NAMES:
        return label
    if label in LABEL_MAP:
        return LABEL_MAP[label]
    return None


# ============================================================================
# Incremental Batch Writer (adopted from extract_multilabel_from_midi.py)
# ============================================================================

class IncrementalBatchWriter:
    """
    Handles incremental flushing of features/labels to disk with checkpoint/resume.

    Key patterns from extract_multilabel_from_midi.py:
    - Flushes every FLUSH_THRESHOLD samples to prevent OOM
    - Saves checkpoint JSON after each flush for crash recovery
    - Creates final manifest compatible with BatchedMultiLabelDataset
    - Supports resume: skips already-processed files on restart
    """

    def __init__(
        self,
        output_dir: Path,
        dataset_name: str,
        flush_threshold: int = FLUSH_THRESHOLD,
    ):
        self.output_dir = output_dir
        self.dataset_name = dataset_name
        self.batch_dir = output_dir / f"{dataset_name}_batches"
        self.checkpoint_dir = output_dir / f".{dataset_name}_checkpoint"
        self.checkpoint_file = self.checkpoint_dir / "checkpoint.json"
        self.flush_threshold = flush_threshold

        self.batch_features: List[np.ndarray] = []
        self.batch_labels: List[np.ndarray] = []
        self.batch_num: int = 0
        self.total_samples: int = 0
        self.processed_files: set = set()
        self._newly_processed: List[str] = []

        self.batch_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def load_checkpoint(self) -> bool:
        """Load checkpoint if it exists. Returns True if resumed."""
        if not self.checkpoint_file.exists():
            return False
        try:
            with open(self.checkpoint_file) as f:
                cp = json.load(f)
            self.processed_files = set(cp.get('processed_files', []))
            self.batch_num = cp.get('batch_num', 0)
            self.total_samples = cp.get('total_samples', 0)
            print(f"   Resuming from checkpoint: {len(self.processed_files)} files, "
                  f"{self.total_samples:,} samples, {self.batch_num} batches on disk")
            return True
        except (json.JSONDecodeError, KeyError) as e:
            print(f"   WARNING: Corrupt checkpoint, starting fresh: {e}")
            return False

    def clear_checkpoint(self):
        """Remove checkpoint and existing batches (for --force mode)."""
        if self.checkpoint_dir.exists():
            shutil.rmtree(self.checkpoint_dir, ignore_errors=True)
        if self.batch_dir.exists():
            shutil.rmtree(self.batch_dir, ignore_errors=True)
        self.batch_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.batch_num = 0
        self.total_samples = 0
        self.processed_files.clear()
        self._newly_processed.clear()

    def is_processed(self, file_key: str) -> bool:
        """Check if a file was already processed in a previous run."""
        return file_key in self.processed_files

    def add_sample(self, feature: np.ndarray, label: np.ndarray):
        """Add a single (feature, label) sample. Auto-flushes at threshold."""
        self.batch_features.append(feature)
        self.batch_labels.append(label)

        if len(self.batch_features) >= self.flush_threshold:
            self._flush()

    def mark_processed(self, file_key: str):
        """Mark a file as processed (will be saved in next checkpoint)."""
        self._newly_processed.append(file_key)

    def _flush(self):
        """Flush accumulated samples to disk and save checkpoint."""
        if not self.batch_features:
            return

        feat_arr = np.array(self.batch_features, dtype=np.float32)
        label_arr = np.array(self.batch_labels, dtype=np.float32)

        np.save(self.batch_dir / f'features_batch_{self.batch_num}.npy', feat_arr)
        np.save(self.batch_dir / f'labels_batch_{self.batch_num}.npy', label_arr)

        self.total_samples += len(self.batch_features)
        self.batch_num += 1

        # Update processed set and save checkpoint
        self.processed_files.update(self._newly_processed)
        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'processed_files': list(self.processed_files),
                'batch_num': self.batch_num,
                'total_samples': self.total_samples,
            }, f)

        self.batch_features.clear()
        self.batch_labels.clear()
        self._newly_processed.clear()
        del feat_arr, label_arr
        gc.collect()

    def flush_remaining(self):
        """Flush any remaining samples (call before finalize)."""
        self._flush()

    def finalize(self) -> Optional[dict]:
        """
        Flush remaining samples, create manifest, print stats, clean up checkpoint.

        Returns the manifest dict, or None if no samples.
        """
        self.flush_remaining()

        if self.total_samples == 0:
            print("   WARNING: No samples to finalize!")
            return None

        print(f"   Creating manifest for {self.batch_num} batches "
              f"({self.total_samples:,} samples)...")

        manifest = {
            'dataset': self.dataset_name,
            'total_samples': self.total_samples,
            'batch_count': self.batch_num,
            'sample_rate': SAMPLE_RATE,
            'feature_shape': [N_MELS, TARGET_FRAMES],
            'num_classes': len(CLASS_NAMES),
            'class_names': CLASS_NAMES,
            'demucs_model': DEMUCS_MODEL,
            'augmentation_type': 'demucs_separation',
            'batches': [],
        }

        # Scan batches for metadata + train/val split
        np.random.seed(42)
        total_label_counts = np.zeros(len(CLASS_NAMES))

        for i in range(self.batch_num):
            labels = np.load(self.batch_dir / f'labels_batch_{i}.npy')
            total_label_counts += labels.sum(axis=0)
            multi_count = int((labels.sum(axis=1) > 1).sum())

            manifest['batches'].append({
                'features': f'features_batch_{i}.npy',
                'labels': f'labels_batch_{i}.npy',
                'samples': len(labels),
                'multi_label_ratio': float(multi_count / len(labels)) if len(labels) > 0 else 0,
            })
            del labels

        # Random train/val split at batch level (90/10)
        batch_indices = np.random.permutation(self.batch_num)
        n_val = max(1, self.batch_num // 10)
        val_set = set(batch_indices[:n_val].tolist())

        for i, batch_info in enumerate(manifest['batches']):
            batch_info['split'] = 'val' if i in val_set else 'train'

        # Print label distribution
        print("\n   Label distribution:")
        for idx, name in enumerate(CLASS_NAMES):
            count = int(total_label_counts[idx])
            pct = 100 * count / self.total_samples if self.total_samples > 0 else 0
            print(f"     {name:<15}: {count:>6} ({pct:>5.1f}%)")

        # Save manifest
        manifest_path = self.output_dir / f"{self.dataset_name}_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Clean up checkpoint directory
        shutil.rmtree(self.checkpoint_dir, ignore_errors=True)

        train_samples = sum(
            b['samples'] for i, b in enumerate(manifest['batches']) if i not in val_set
        )
        val_samples = sum(
            b['samples'] for i, b in enumerate(manifest['batches']) if i in val_set
        )

        print(f"\n   Saved {self.total_samples:,} samples across {self.batch_num} batches")
        print(f"      Train: {train_samples:,}, Val: {val_samples:,}")
        print(f"      Manifest: {manifest_path}")

        return manifest


# ============================================================================
# Demucs Separation
# ============================================================================

class DemucsProcessor:
    """Manages Demucs model loading and audio separation."""

    def __init__(self, model_name: str = DEMUCS_MODEL, device: str = "auto"):
        self.model_name = model_name
        self.model = None
        self._device = device

    @property
    def device(self):
        if self._device == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(self._device)

    def load_model(self):
        """Load Demucs model (lazy, only when first needed)."""
        if self.model is not None:
            return

        print(f"Loading Demucs model: {self.model_name}")
        print(f"Device: {self.device}")

        try:
            from demucs.pretrained import get_model
            from demucs.apply import apply_model
            self._apply_model = apply_model
        except ImportError:
            print("ERROR: demucs not installed. pip install demucs")
            sys.exit(1)

        self.model = get_model(self.model_name)
        self.model.to(self.device)
        self.model.eval()
        print(f"Demucs model loaded: {self.model_name}")

    def separate_drums(self, audio_path: Path) -> Optional[np.ndarray]:
        """
        Run Demucs separation on an audio file and return the drums stem.

        Args:
            audio_path: Path to audio file (WAV, FLAC, MP3)

        Returns:
            Drums stem as numpy array (mono, sr=SAMPLE_RATE) or None
        """
        self.load_model()

        try:
            # Load at model's native sample rate (44100 for htdemucs_ft)
            model_sr = self.model.samplerate
            wav, sr = torchaudio.load(str(audio_path))

            # Resample if needed
            if sr != model_sr:
                wav = torchaudio.functional.resample(wav, sr, model_sr)

            # Ensure stereo (Demucs expects stereo)
            if wav.shape[0] == 1:
                wav = wav.repeat(2, 1)
            elif wav.shape[0] > 2:
                wav = wav[:2]

            # Add batch dimension and move to device
            wav = wav.unsqueeze(0).to(self.device)

            # Run separation
            with torch.no_grad():
                sources = self._apply_model(
                    self.model, wav, device=self.device,
                    split=True, overlap=0.25
                )

            # Extract drums stem (index depends on model)
            # htdemucs_ft sources: drums, bass, other, vocals
            source_names = self.model.sources
            drums_idx = source_names.index('drums')
            drums_wav = sources[0, drums_idx]  # (channels, samples)

            # Convert to mono
            drums_mono = drums_wav.mean(dim=0).cpu().numpy()

            # FREE GPU tensors immediately
            del wav, sources, drums_wav
            torch.cuda.empty_cache()

            # Resample to training sample rate if needed
            if model_sr != SAMPLE_RATE:
                drums_mono = librosa.resample(
                    drums_mono, orig_sr=model_sr, target_sr=SAMPLE_RATE
                )

            return drums_mono

        except Exception as e:
            print(f"  ERROR separating {audio_path}: {e}")
            torch.cuda.empty_cache()
            return None

    def separate_drums_from_array(
        self, audio: np.ndarray, sr: int
    ) -> Optional[np.ndarray]:
        """
        Run Demucs on an in-memory audio array. Avoids writing/reading temp files.

        This eliminates the temp WAV file round-trip for EGMD/Groove processing,
        saving ~5-30 MB of disk I/O per file × 5000+ files.

        Args:
            audio: Mono audio as numpy float32 array
            sr: Sample rate of the input audio

        Returns:
            Drums stem as numpy array (mono, sr=SAMPLE_RATE) or None
        """
        self.load_model()

        try:
            model_sr = self.model.samplerate

            # Convert numpy → torch tensor
            wav = torch.from_numpy(audio).float().unsqueeze(0)  # (1, samples)

            # Resample to model's native rate if needed
            if sr != model_sr:
                wav = torchaudio.functional.resample(wav, sr, model_sr)

            # Make stereo (Demucs expects stereo input)
            wav = wav.repeat(2, 1)  # (2, samples)

            # Add batch dimension and move to device
            wav = wav.unsqueeze(0).to(self.device)  # (1, 2, samples)

            # Run separation
            with torch.no_grad():
                sources = self._apply_model(
                    self.model, wav, device=self.device,
                    split=True, overlap=0.25
                )

            # Extract drums stem
            source_names = self.model.sources
            drums_idx = source_names.index('drums')
            drums_wav = sources[0, drums_idx]  # (channels, samples)

            # Convert to mono
            drums_mono = drums_wav.mean(dim=0).cpu().numpy()

            # FREE GPU tensors immediately to prevent VRAM fragmentation.
            # With only 12GB VRAM, Demucs intermediates can push into shared
            # GPU memory (over PCIe) which is ~30x slower.
            del wav, sources, drums_wav
            torch.cuda.empty_cache()

            # Resample to training sample rate
            if model_sr != SAMPLE_RATE:
                drums_mono = librosa.resample(
                    drums_mono, orig_sr=model_sr, target_sr=SAMPLE_RATE
                )

            return drums_mono

        except Exception as e:
            print(f"  ERROR separating audio array: {e}")
            # Clean up GPU even on error
            torch.cuda.empty_cache()
            return None


# ============================================================================
# Mixing Utilities (for EGMD/Groove + musdb18)
# ============================================================================

class MusicMixer:
    """Provides random music backing tracks for mixing with drum stems."""

    def __init__(self, musdb_root: Path, sr: int = SAMPLE_RATE):
        self.musdb_root = musdb_root
        self.sr = sr
        self._backing_tracks: List[Path] = []
        self._loaded_backings: Dict[str, np.ndarray] = {}

    def discover_tracks(self):
        """Find all musdb18 songs with non-drum stems."""
        for split in ['train', 'test']:
            split_dir = self.musdb_root / split
            if not split_dir.exists():
                continue
            for song_dir in sorted(split_dir.iterdir()):
                if song_dir.is_dir():
                    # Check for non-drum stems
                    bass = song_dir / "bass.wav"
                    other = song_dir / "other.wav"
                    vocals = song_dir / "vocals.wav"
                    if bass.exists() and other.exists() and vocals.exists():
                        self._backing_tracks.append(song_dir)

        print(f"Found {len(self._backing_tracks)} musdb18 songs for backing tracks")

    def get_random_backing(self, duration_samples: int) -> np.ndarray:
        """
        Get a random non-drum backing track mixed together.

        Returns mono audio of the specified length.
        """
        if not self._backing_tracks:
            # Fallback: return silence (still runs Demucs on drum-only audio)
            return np.zeros(duration_samples, dtype=np.float32)

        song_dir = random.choice(self._backing_tracks)
        song_key = str(song_dir)

        # Try to use cached version
        if song_key in self._loaded_backings:
            backing = self._loaded_backings[song_key]
        else:
            try:
                # Load and sum non-drum stems
                bass, _ = librosa.load(song_dir / "bass.wav", sr=self.sr, mono=True)
                other, _ = librosa.load(song_dir / "other.wav", sr=self.sr, mono=True)
                vocals, _ = librosa.load(song_dir / "vocals.wav", sr=self.sr, mono=True)

                # Align lengths
                min_len = min(len(bass), len(other), len(vocals))
                backing = bass[:min_len] + other[:min_len] + vocals[:min_len]

                # Cache (limit cache size)
                if len(self._loaded_backings) < 20:
                    self._loaded_backings[song_key] = backing
            except Exception as e:
                print(f"  WARNING: Failed loading backing from {song_dir}: {e}")
                return np.zeros(duration_samples, dtype=np.float32)

        # Random offset into the backing track
        if len(backing) > duration_samples:
            max_start = len(backing) - duration_samples
            start = random.randint(0, max_start)
            segment = backing[start:start + duration_samples]
        else:
            # Pad if backing is shorter
            segment = np.pad(backing, (0, max(0, duration_samples - len(backing))))
            segment = segment[:duration_samples]

        return segment.astype(np.float32)

    def mix_drums_with_backing(
        self, drums: np.ndarray, snr_db: float = 0.0
    ) -> np.ndarray:
        """
        Mix drums with a random backing track at specified SNR.

        Args:
            drums: Drum audio (mono)
            snr_db: Signal-to-noise ratio in dB (drums relative to backing)
                    0 dB = equal, +6 dB = drums 2x louder, -6 dB = backing 2x louder

        Returns:
            Mixed audio
        """
        backing = self.get_random_backing(len(drums))

        # Calculate mixing levels from SNR
        drums_rms = np.sqrt(np.mean(drums ** 2)) + 1e-8
        backing_rms = np.sqrt(np.mean(backing ** 2)) + 1e-8

        # Target: 20*log10(drums_rms / (backing_rms * gain)) = snr_db
        target_ratio = 10 ** (snr_db / 20.0)
        backing_gain = drums_rms / (backing_rms * target_ratio)

        mixture = drums + backing * backing_gain

        # Normalize to prevent clipping
        peak = np.abs(mixture).max()
        if peak > 0.95:
            mixture = mixture * (0.95 / peak)

        return mixture


# ============================================================================
# Audio Prefetch Helper (for D: HDD bottleneck)
# ============================================================================

def _load_audio_worker(args: tuple) -> Tuple[str, Optional[np.ndarray]]:
    """
    Worker function for audio prefetch thread.

    Loads and resamples audio from HDD. Runs in a background thread so
    the next file's I/O overlaps with the current file's GPU processing.

    The D: drive is a 120 MB/s USB HDD — by prefetching the next file
    while the GPU runs Demucs on the current file (~1-3 sec), we hide
    most of the HDD read latency.
    """
    file_path, audio_root, sr = args
    full_path = audio_root / file_path.replace('\\', '/')
    if not full_path.exists():
        return file_path, None
    try:
        audio, _ = librosa.load(str(full_path), sr=sr, mono=True)
        if len(audio) < sr // 2:  # Skip very short files (<0.5s)
            return file_path, None
        return file_path, audio
    except Exception:
        return file_path, None


def _extract_events_to_samples(
    drums_audio: np.ndarray,
    events: List[dict],
) -> Tuple[List[np.ndarray], List[np.ndarray], int]:
    """
    Extract mel spectrograms + labels for all onset events from a drums audio.

    Returns (features_list, labels_list, skipped_count).
    """
    features = []
    labels = []
    skipped = 0

    for event in events:
        onset_time = event['onset_time']

        mel = extract_mel_spectrogram(drums_audio, SAMPLE_RATE, onset_time)
        if mel is None:
            skipped += 1
            continue

        label_vec = np.zeros(len(CLASS_NAMES), dtype=np.float32)
        for comp in event.get('components', []):
            raw_label = comp.get('label', '')
            normalized = normalize_label(raw_label)
            if normalized and normalized in CLASS_TO_IDX:
                label_vec[CLASS_TO_IDX[normalized]] = 1.0

        if label_vec.sum() == 0:
            skipped += 1
            continue

        features.append(mel)
        labels.append(label_vec)

    return features, labels, skipped


# ============================================================================
# Phase 1: ENST wet_mix → Demucs
# ============================================================================

def process_enst_demucs(
    demucs: DemucsProcessor,
    output_dir: Optional[Path] = None,
    max_recordings: Optional[int] = None,
    force: bool = False,
):
    """
    Process ENST wet_mix recordings through Demucs.

    ENST has wet_mix = drums + accompaniment already mixed together.
    This is the closest analog to real music → Demucs at inference time.
    Ground-truth labels come from JSONL event manifests.
    """
    print("\n" + "=" * 70)
    print("PHASE 1: ENST wet_mix → Demucs Augmentation")
    print("=" * 70)

    dataset_name = "enst_drums_demucs"
    if output_dir is None:
        output_dir = OUTPUT_BASE / dataset_name

    # Check if already completed
    manifest_path = output_dir / f"{dataset_name}_manifest.json"
    if manifest_path.exists() and not force:
        with open(manifest_path) as f:
            m = json.load(f)
        print(f"   Already completed: {m['total_samples']:,} samples")
        print(f"   Use --force to reprocess")
        return m

    audio_root = AUDIO_ROOTS["enst_drums"]
    events_manifest = MANIFESTS_DIR / "enst_drums_events.jsonl"

    # Verify paths
    if not audio_root.exists():
        print(f"ERROR: ENST audio not found at {audio_root}")
        return None
    if not events_manifest.exists():
        print(f"ERROR: ENST manifest not found at {events_manifest}")
        return None

    # Load events and group by recording (audio_path)
    print("Loading ENST event manifest...")
    events_by_recording: Dict[str, List[dict]] = defaultdict(list)
    total_events = 0

    with open(events_manifest) as f:
        for line in f:
            try:
                event = json.loads(line)
                audio_path = event.get('audio_path', '')
                if audio_path and event.get('onset_time') is not None:
                    events_by_recording[audio_path].append(event)
                    total_events += 1
            except json.JSONDecodeError:
                pass

    print(f"Loaded {total_events:,} events across {len(events_by_recording)} recordings")

    # Optionally limit recordings
    recording_paths = list(events_by_recording.keys())
    if max_recordings and len(recording_paths) > max_recordings:
        random.seed(42)
        recording_paths = random.sample(recording_paths, max_recordings)
        print(f"Limited to {max_recordings} recordings")

    # Initialize incremental writer with checkpoint/resume
    writer = IncrementalBatchWriter(output_dir, dataset_name)
    if force:
        writer.clear_checkpoint()
    else:
        writer.load_checkpoint()

    # Filter out already-processed recordings
    remaining = [r for r in recording_paths if not writer.is_processed(r)]
    skipped_from_checkpoint = len(recording_paths) - len(remaining)
    if skipped_from_checkpoint > 0:
        print(f"   Skipping {skipped_from_checkpoint} already-processed recordings")

    # Process each recording
    processed_count = 0
    skipped_events = 0

    for rec_path in tqdm(remaining, desc="Processing recordings"):
        if _shutdown_requested:
            break

        events = events_by_recording[rec_path]

        # Original path uses dry_mix, we need wet_mix
        wet_path_rel = rec_path.replace('dry_mix', 'wet_mix').replace('\\', '/')
        wet_path = audio_root / wet_path_rel

        if not wet_path.exists():
            dry_path = audio_root / rec_path.replace('\\', '/')
            if dry_path.exists():
                wet_path = dry_path
            else:
                skipped_events += len(events)
                writer.mark_processed(rec_path)
                continue

        # Run Demucs on the wet mix
        drums_audio = demucs.separate_drums(wet_path)
        if drums_audio is None:
            skipped_events += len(events)
            writer.mark_processed(rec_path)
            continue

        # Extract spectrograms for each onset event
        features, labels, n_skipped = _extract_events_to_samples(drums_audio, events)
        skipped_events += n_skipped

        for feat, lab in zip(features, labels):
            writer.add_sample(feat, lab)

        writer.mark_processed(rec_path)
        processed_count += 1

        del drums_audio

    # Handle interruption
    if _shutdown_requested:
        writer.flush_remaining()
        print(f"   Checkpoint saved: {len(writer.processed_files)} recordings, "
              f"{writer.total_samples:,} samples")
        print(f"   Run again to resume.")
        return None

    print(f"\nProcessed: {processed_count + skipped_from_checkpoint} recordings")
    print(f"Skipped events: {skipped_events:,}")

    return writer.finalize()


# ============================================================================
# Phase 2: Slakh2100 mix.flac → Demucs
# ============================================================================

def process_slakh_demucs(
    demucs: DemucsProcessor,
    output_dir: Optional[Path] = None,
    max_tracks: Optional[int] = None,
    force: bool = False,
):
    """
    Process Slakh2100 mix.flac recordings through Demucs.

    Slakh2100 is a multi-instrument MIDI-synthesized dataset with full mixes.
    Each track has a mix.flac (all instruments mixed) and per-stem FLAC files.
    This is Mode A (like ENST): run Demucs on the full mix to get estimated drums.

    CRITICAL: Slakh has 2,045 china + 6,557 splash events — the ONLY dataset
    with significant china/splash coverage for Demucs domain gap training.

    Ground-truth labels come from slakh2100_events.jsonl manifest.
    Audio paths in manifest point to stems (S01.flac etc.), but we load mix.flac
    from the parent track directory instead.

    ~1,708 tracks (1,557 train + 151 test), ~262K events total.
    Processing time: ~2-4 hours on GPU (HDD-bound reads, GPU separation).
    """
    print("\n" + "=" * 70)
    print("PHASE 2: Slakh2100 mix.flac → Demucs Augmentation")
    print("=" * 70)

    dataset_name = "slakh2100_demucs"
    if output_dir is None:
        output_dir = OUTPUT_BASE / dataset_name

    # Check if already completed
    manifest_path = output_dir / f"{dataset_name}_manifest.json"
    if manifest_path.exists() and not force:
        with open(manifest_path) as f:
            m = json.load(f)
        print(f"   Already completed: {m['total_samples']:,} samples")
        print(f"   Use --force to reprocess")
        return m

    audio_root = AUDIO_ROOTS["slakh2100"]
    events_manifest = MANIFESTS_DIR / "slakh2100_events.jsonl"

    # Verify paths
    if not audio_root.exists():
        print(f"ERROR: Slakh2100 audio not found at {audio_root}")
        return None
    if not events_manifest.exists():
        print(f"ERROR: Slakh2100 manifest not found at {events_manifest}")
        return None

    # Load events and group by TRACK (not by stem file)
    # Manifest audio_path is like "train\Track00001\stems\S01.flac"
    # We group by "train/Track00001" and load mix.flac from that directory
    print("Loading Slakh2100 event manifest...")
    events_by_track: Dict[str, List[dict]] = defaultdict(list)
    total_events = 0

    with open(events_manifest) as f:
        for line in f:
            try:
                event = json.loads(line)
                audio_path = event.get('audio_path', '')
                if audio_path and event.get('onset_time') is not None:
                    # Extract track key: "train/Track00001" from "train\Track00001\stems\S01.flac"
                    parts = audio_path.replace('\\', '/').split('/')
                    if len(parts) >= 2:
                        track_key = f"{parts[0]}/{parts[1]}"
                        events_by_track[track_key].append(event)
                        total_events += 1
            except json.JSONDecodeError:
                pass

    print(f"Loaded {total_events:,} events across {len(events_by_track)} tracks")

    # Count china/splash for user visibility
    class_counts = Counter()
    for events in events_by_track.values():
        for event in events:
            for comp in event.get('components', []):
                label = normalize_label(comp.get('label', ''))
                if label:
                    class_counts[label] += 1
    print(f"  china: {class_counts.get('china', 0):,}, "
          f"splash: {class_counts.get('splash', 0):,}, "
          f"crash: {class_counts.get('crash', 0):,}")

    # Optionally limit tracks
    track_keys = sorted(events_by_track.keys())
    if max_tracks and len(track_keys) > max_tracks:
        random.seed(42)
        track_keys = random.sample(track_keys, max_tracks)
        track_keys.sort()
        print(f"Limited to {max_tracks} tracks")

    # Initialize incremental writer with checkpoint/resume
    writer = IncrementalBatchWriter(output_dir, dataset_name)
    if force:
        writer.clear_checkpoint()
    else:
        writer.load_checkpoint()

    # Filter out already-processed tracks
    remaining = [t for t in track_keys if not writer.is_processed(t)]
    skipped_from_checkpoint = len(track_keys) - len(remaining)
    if skipped_from_checkpoint > 0:
        print(f"   Skipping {skipped_from_checkpoint} already-processed tracks (checkpoint)")

    # Process each track
    processed_count = 0
    skipped_events = 0
    missing_mix = 0

    # Pipeline: overlap CPU feature extraction with GPU Demucs processing.
    # While the GPU runs Demucs on track N+1, the CPU extracts mel spectrograms
    # for track N's ~1,489 events. librosa releases the GIL so this truly
    # parallelizes with CUDA operations.
    pending_future = None
    pending_track_key = None

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='feat_extract') as executor:
        for track_key in tqdm(remaining, desc="Processing tracks"):
            if _shutdown_requested:
                break

            # Collect results from previous track's feature extraction
            if pending_future is not None:
                features, labels, n_skipped = pending_future.result()
                skipped_events += n_skipped
                for feat, lab in zip(features, labels):
                    writer.add_sample(feat, lab)
                writer.mark_processed(pending_track_key)
                processed_count += 1
                pending_future = None
                pending_track_key = None

            events = events_by_track[track_key]

            # Build path to mix.flac: audio_root / "train/Track00001/mix.flac"
            mix_path = audio_root / track_key / "mix.flac"

            if not mix_path.exists():
                # Try .wav as fallback
                mix_path_wav = audio_root / track_key / "mix.wav"
                if mix_path_wav.exists():
                    mix_path = mix_path_wav
                else:
                    missing_mix += 1
                    skipped_events += len(events)
                    writer.mark_processed(track_key)
                    continue

            # Load audio and trim BEFORE Demucs to avoid processing
            # minutes of silence/non-drum audio on the GPU.
            # Slakh songs can be 5+ min but events may span only 2-3 min.
            # Load at native SR (typically 44100) to preserve quality for Demucs.
            try:
                raw_audio, native_sr = librosa.load(str(mix_path), sr=None, mono=True)
            except Exception as e:
                print(f"  ERROR loading {mix_path}: {e}")
                skipped_events += len(events)
                writer.mark_processed(track_key)
                continue

            if len(raw_audio) < native_sr // 2:
                skipped_events += len(events)
                writer.mark_processed(track_key)
                continue

            # Trim audio to [first_onset - 2s, last_onset + 2s]
            # Keeps Demucs context around events while cutting silence/outros.
            min_onset = min(e['onset_time'] for e in events)
            max_onset = max(e['onset_time'] for e in events)
            trim_start_s = max(0.0, min_onset - 2.0)
            trim_end_s = max_onset + 2.0
            trim_start = int(trim_start_s * native_sr)
            trim_end = min(len(raw_audio), int(trim_end_s * native_sr))
            if trim_end > trim_start:
                trimmed = raw_audio[trim_start:trim_end]
            else:
                trimmed = raw_audio
            # Adjust onset times relative to the trimmed audio
            onset_offset = trim_start_s
            trimmed_events = []
            for e in events:
                e_copy = dict(e)
                e_copy['onset_time'] = e['onset_time'] - onset_offset
                trimmed_events.append(e_copy)

            del raw_audio

            # Run Demucs on trimmed audio (in-memory, no temp file)
            drums_audio = demucs.separate_drums_from_array(trimmed, native_sr)
            del trimmed

            if drums_audio is None:
                skipped_events += len(events)
                writer.mark_processed(track_key)
                continue

            # Submit CPU-bound feature extraction to background thread.
            # The next iteration's Demucs GPU call runs in parallel with this.
            pending_future = executor.submit(
                _extract_events_to_samples, drums_audio, trimmed_events
            )
            pending_track_key = track_key

        # Collect final pending result
        if pending_future is not None:
            features, labels, n_skipped = pending_future.result()
            skipped_events += n_skipped
            for feat, lab in zip(features, labels):
                writer.add_sample(feat, lab)
            writer.mark_processed(pending_track_key)
            processed_count += 1

    # Handle interruption
    if _shutdown_requested:
        writer.flush_remaining()
        print(f"   Checkpoint saved: {len(writer.processed_files)} tracks, "
              f"{writer.total_samples:,} samples")
        print(f"   Run again to resume.")
        return None

    print(f"\nProcessed: {processed_count + skipped_from_checkpoint} tracks")
    if missing_mix > 0:
        print(f"Missing mix.flac: {missing_mix} tracks")
    print(f"Skipped events: {skipped_events:,}")

    return writer.finalize()


# ============================================================================
# Phase 3: EGMD + musdb18 → mix → Demucs
# ============================================================================

def process_egmd_demucs(
    demucs: DemucsProcessor,
    mixer: MusicMixer,
    output_dir: Optional[Path] = None,
    max_files: int = 5000,
    snr_range: Tuple[float, float] = (-3.0, 6.0),
    force: bool = False,
):
    """
    Process EGMD drum recordings mixed with musdb18 backing tracks through Demucs.

    Optimizations vs original:
    - In-memory Demucs: passes tensor directly, no temp WAV file I/O
    - Audio prefetch: reads next file from D: HDD while GPU processes current
    - Checkpoint/resume: crash at file 4999 → resume from 4999, not restart
    - Incremental flush: never accumulates >2000 samples in RAM
    """
    print("\n" + "=" * 70)
    print("PHASE 3: EGMD + musdb18 mixing → Demucs Augmentation")
    print("=" * 70)

    dataset_name = "egmd_demucs"
    if output_dir is None:
        output_dir = OUTPUT_BASE / dataset_name

    # Check if already completed
    manifest_path = output_dir / f"{dataset_name}_manifest.json"
    if manifest_path.exists() and not force:
        with open(manifest_path) as f:
            m = json.load(f)
        print(f"   Already completed: {m['total_samples']:,} samples")
        print(f"   Use --force to reprocess")
        return m

    audio_root = AUDIO_ROOTS["egmd"]
    events_manifest = MANIFESTS_DIR / "egmd_events.jsonl"

    if not audio_root.exists():
        print(f"ERROR: EGMD audio not found at {audio_root}")
        return None
    if not events_manifest.exists():
        print(f"ERROR: EGMD manifest not found at {events_manifest}")
        return None

    # Load events — memory-efficient two-pass for large manifests with subsampling
    manifest_size = events_manifest.stat().st_size
    print(f"Loading EGMD event manifest ({manifest_size / 1e9:.1f} GB)...")

    if max_files and manifest_size > 500_000_000:
        # Two-pass approach: avoids loading all events into memory
        # Pass 1 (binary, no JSON parsing): discover unique audio file paths
        print(f"  Pass 1/2: Scanning for unique audio files...")
        unique_files = set()
        lines_scanned = 0
        with open(events_manifest, 'rb') as f:
            for raw_line in f:
                idx = raw_line.find(b'"audio_path"')
                if idx >= 0:
                    # Extract value: find opening quote after colon, then closing quote
                    q1 = raw_line.find(b'"', idx + 12 + 1)  # skip past "audio_path"
                    if q1 >= 0:
                        q2 = raw_line.find(b'"', q1 + 1)
                        if q2 > q1:
                            # Use json.loads on the quoted bytes to properly
                            # unescape JSON strings (e.g. \\\\ → \\, \\/ → /)
                            try:
                                unique_files.add(json.loads(raw_line[q1:q2 + 1]))
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass
                lines_scanned += 1
                if lines_scanned % 5_000_000 == 0:
                    print(f"    ...{lines_scanned:,} lines scanned, {len(unique_files):,} unique files")

        print(f"  Found {len(unique_files):,} unique audio files across {lines_scanned:,} events")

        # Subsample (deterministic)
        all_files_sorted = sorted(unique_files)
        del unique_files
        random.seed(42)
        selected_files = random.sample(all_files_sorted, min(max_files, len(all_files_sorted)))
        selected_set = frozenset(selected_files)
        del all_files_sorted
        print(f"  Subsampled to {len(selected_files):,} files")

        # Pass 2 (text mode, JSON parsing): load events only for selected files
        print(f"  Pass 2/2: Loading events for selected files...")
        events_by_file: Dict[str, List[dict]] = defaultdict(list)
        total_events = 0
        lines_read = 0
        with open(events_manifest) as f:
            for line in f:
                lines_read += 1
                try:
                    event = json.loads(line)
                    ap = event.get('audio_path', '')
                    if ap in selected_set and event.get('onset_time') is not None:
                        events_by_file[ap].append(event)
                        total_events += 1
                except json.JSONDecodeError:
                    pass
                if lines_read % 5_000_000 == 0:
                    print(f"    ...{lines_read:,} lines, {total_events:,} events loaded")

        del selected_set
        print(f"  Loaded {total_events:,} events across {len(events_by_file):,} audio files")
    else:
        # Small manifests or no subsampling: load everything
        events_by_file: Dict[str, List[dict]] = defaultdict(list)
        total_events = 0
        with open(events_manifest) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    audio_path = event.get('audio_path', '')
                    if audio_path and event.get('onset_time') is not None:
                        events_by_file[audio_path].append(event)
                        total_events += 1
                except json.JSONDecodeError:
                    pass
        print(f"Loaded {total_events:,} events across {len(events_by_file):,} audio files")

        # Subsample audio files (deterministic)
        all_files = list(events_by_file.keys())
        if max_files and len(all_files) > max_files:
            random.seed(42)
            selected_files = random.sample(all_files, max_files)
            print(f"Subsampled to {max_files} files")
        else:
            selected_files = all_files

    # Ensure mixer has backing tracks
    if not mixer._backing_tracks:
        mixer.discover_tracks()

    # Initialize incremental writer with checkpoint/resume
    writer = IncrementalBatchWriter(output_dir, dataset_name)
    if force:
        writer.clear_checkpoint()
    else:
        writer.load_checkpoint()

    # Filter out already-processed files
    remaining_files = [f for f in selected_files if not writer.is_processed(f)]
    skipped_from_checkpoint = len(selected_files) - len(remaining_files)
    if skipped_from_checkpoint > 0:
        print(f"   Skipping {skipped_from_checkpoint} already-processed files")
    print(f"   Files to process: {len(remaining_files)}")

    if not remaining_files:
        print("   All files already processed. Finalizing...")
        return writer.finalize()

    # Process with audio prefetch from D: HDD
    processed_count = 0
    skipped_events = 0
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='hdd_prefetch') as prefetcher:
        # Submit first file for loading
        future = prefetcher.submit(
            _load_audio_worker, (remaining_files[0], audio_root, SAMPLE_RATE)
        )

        for i in tqdm(range(len(remaining_files)), desc="Processing EGMD files"):
            if _shutdown_requested:
                break

            # Get current file's audio (already loaded by prefetch thread)
            fp, drums = future.result()

            # Submit NEXT file for prefetch (overlaps HDD I/O with GPU processing)
            if i + 1 < len(remaining_files):
                future = prefetcher.submit(
                    _load_audio_worker,
                    (remaining_files[i + 1], audio_root, SAMPLE_RATE)
                )

            events = events_by_file[fp]

            if drums is None:
                skipped_events += len(events)
                writer.mark_processed(fp)
                continue

            # Trim audio to last onset + 1 sec — avoids processing 10-min
            # files through Demucs when events only span the first 45 sec.
            # A 10-min file at 44.1kHz is 10x more GPU work than 1 min.
            max_onset = max(e['onset_time'] for e in events)
            trim_samples = int((max_onset + 1.0) * SAMPLE_RATE)
            if trim_samples < len(drums):
                drums = drums[:trim_samples]

            # Mix with random backing at random SNR
            snr_db = random.uniform(snr_range[0], snr_range[1])
            mixture = mixer.mix_drums_with_backing(drums, snr_db=snr_db)

            # Run Demucs directly from array (no temp file!)
            demucs_drums = demucs.separate_drums_from_array(mixture, SAMPLE_RATE)

            if demucs_drums is None:
                skipped_events += len(events)
                writer.mark_processed(fp)
                del drums, mixture
                continue

            # Extract spectrograms for each onset
            features, labels, n_skipped = _extract_events_to_samples(
                demucs_drums, events
            )
            skipped_events += n_skipped

            for feat, lab in zip(features, labels):
                writer.add_sample(feat, lab)

            writer.mark_processed(fp)
            processed_count += 1

            # Memory management
            del drums, mixture, demucs_drums

            # Periodic CUDA cache clear — 12GB VRAM is tight with Demucs
            if processed_count % 10 == 0:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Progress report with ETA
            if processed_count % 250 == 0:
                elapsed = time.time() - t_start
                rate = processed_count / elapsed if elapsed > 0 else 0
                remaining_n = len(remaining_files) - (i + 1)
                eta_sec = remaining_n / rate if rate > 0 else 0
                eta_min = eta_sec / 60
                print(f"\n  [{processed_count}/{len(remaining_files)}] "
                      f"{writer.total_samples:,} samples | "
                      f"{rate:.1f} files/sec | ETA: {eta_min:.0f} min")

    # Handle interruption
    if _shutdown_requested:
        writer.flush_remaining()
        print(f"   Checkpoint saved: {len(writer.processed_files)} files, "
              f"{writer.total_samples:,} samples")
        print(f"   Run again to resume.")
        return None

    elapsed = time.time() - t_start
    print(f"\nProcessed: {processed_count + skipped_from_checkpoint} files "
          f"in {elapsed / 60:.1f} min")
    print(f"Skipped events: {skipped_events:,}")

    return writer.finalize()


# ============================================================================
# Phase 2: Groove MIDI + musdb18 → mix → Demucs
# ============================================================================

def process_groove_demucs(
    demucs: DemucsProcessor,
    mixer: MusicMixer,
    output_dir: Optional[Path] = None,
    max_files: Optional[int] = None,
    snr_range: Tuple[float, float] = (-3.0, 6.0),
    force: bool = False,
):
    """
    Process Groove MIDI recordings mixed with musdb18 backing tracks through Demucs.
    Same approach as EGMD but smaller dataset (~1090 files).
    """
    print("\n" + "=" * 70)
    print("PHASE 2: Groove MIDI + musdb18 mixing → Demucs Augmentation")
    print("=" * 70)

    dataset_name = "groove_midi_demucs"
    if output_dir is None:
        output_dir = OUTPUT_BASE / dataset_name

    # Check if already completed
    manifest_path = output_dir / f"{dataset_name}_manifest.json"
    if manifest_path.exists() and not force:
        with open(manifest_path) as f:
            m = json.load(f)
        print(f"   Already completed: {m['total_samples']:,} samples")
        print(f"   Use --force to reprocess")
        return m

    audio_root = AUDIO_ROOTS["groove_midi"]
    events_manifest = MANIFESTS_DIR / "groove_events.jsonl"

    # Try alternative manifest name
    if not events_manifest.exists():
        events_manifest = MANIFESTS_DIR / "groove_mididataset_events.jsonl"

    if not audio_root.exists():
        print(f"ERROR: Groove MIDI audio not found at {audio_root}")
        return None
    if not events_manifest.exists():
        print(f"ERROR: Groove manifest not found")
        return None

    # Load events grouped by audio file
    print("Loading Groove MIDI event manifest...")
    events_by_file: Dict[str, List[dict]] = defaultdict(list)
    total_events = 0

    with open(events_manifest) as f:
        for line in f:
            try:
                event = json.loads(line)
                audio_path = event.get('audio_path', '')
                if audio_path and event.get('onset_time') is not None:
                    events_by_file[audio_path].append(event)
                    total_events += 1
            except json.JSONDecodeError:
                pass

    print(f"Loaded {total_events:,} events across {len(events_by_file):,} audio files")

    all_files = list(events_by_file.keys())
    if max_files and len(all_files) > max_files:
        random.seed(42)
        all_files = random.sample(all_files, max_files)

    if not mixer._backing_tracks:
        mixer.discover_tracks()

    # Initialize incremental writer with checkpoint/resume
    writer = IncrementalBatchWriter(output_dir, dataset_name)
    if force:
        writer.clear_checkpoint()
    else:
        writer.load_checkpoint()

    # Filter out already-processed files
    remaining_files = [f for f in all_files if not writer.is_processed(f)]
    skipped_from_checkpoint = len(all_files) - len(remaining_files)
    if skipped_from_checkpoint > 0:
        print(f"   Skipping {skipped_from_checkpoint} already-processed files")
    print(f"   Files to process: {len(remaining_files)}")

    if not remaining_files:
        print("   All files already processed. Finalizing...")
        return writer.finalize()

    # Process with audio prefetch
    processed_count = 0
    skipped_events = 0
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='hdd_prefetch') as prefetcher:
        future = prefetcher.submit(
            _load_audio_worker, (remaining_files[0], audio_root, SAMPLE_RATE)
        )

        for i in tqdm(range(len(remaining_files)), desc="Processing Groove files"):
            if _shutdown_requested:
                break

            fp, drums = future.result()

            # Prefetch next
            if i + 1 < len(remaining_files):
                future = prefetcher.submit(
                    _load_audio_worker,
                    (remaining_files[i + 1], audio_root, SAMPLE_RATE)
                )

            events = events_by_file[fp]

            if drums is None:
                skipped_events += len(events)
                writer.mark_processed(fp)
                continue

            # Trim audio to last onset + 1 sec — avoids processing 10-min
            # files through Demucs when events only span the first 45 sec.
            max_onset = max(e['onset_time'] for e in events)
            trim_samples = int((max_onset + 1.0) * SAMPLE_RATE)
            if trim_samples < len(drums):
                drums = drums[:trim_samples]

            # Mix with backing
            snr_db = random.uniform(snr_range[0], snr_range[1])
            mixture = mixer.mix_drums_with_backing(drums, snr_db=snr_db)

            # In-memory Demucs (no temp file)
            demucs_drums = demucs.separate_drums_from_array(mixture, SAMPLE_RATE)

            if demucs_drums is None:
                skipped_events += len(events)
                writer.mark_processed(fp)
                del drums, mixture
                continue

            features, labels, n_skipped = _extract_events_to_samples(
                demucs_drums, events
            )
            skipped_events += n_skipped

            for feat, lab in zip(features, labels):
                writer.add_sample(feat, lab)

            writer.mark_processed(fp)
            processed_count += 1

            del drums, mixture, demucs_drums
            if processed_count % 10 == 0:
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    # Handle interruption
    if _shutdown_requested:
        writer.flush_remaining()
        print(f"   Checkpoint saved: {len(writer.processed_files)} files, "
              f"{writer.total_samples:,} samples")
        print(f"   Run again to resume.")
        return None

    elapsed = time.time() - t_start
    print(f"\nProcessed: {processed_count + skipped_from_checkpoint} files "
          f"in {elapsed / 60:.1f} min")
    print(f"Skipped events: {skipped_events:,}")

    return writer.finalize()


# ============================================================================
# Analysis
# ============================================================================

def analyze_available_data():
    """Analyze what raw data is available for Demucs augmentation."""
    print("=" * 70)
    print("DEMUCS AUGMENTATION — DATA AVAILABILITY ANALYSIS")
    print("=" * 70)
    print()

    # Check ENST
    enst_root = AUDIO_ROOTS["enst_drums"]
    print("1. ENST Drums (wet_mix → Demucs)")
    if enst_root.exists():
        wet_mix_count = 0
        for drummer_dir in sorted(enst_root.iterdir()):
            if drummer_dir.is_dir() and 'drummer' in drummer_dir.name:
                wet_dir = drummer_dir / "audio" / "wet_mix"
                if wet_dir.exists():
                    n = len(list(wet_dir.glob("*.wav")))
                    wet_mix_count += n
                    print(f"   {drummer_dir.name}: {n} wet_mix recordings")
        print(f"   Total wet_mix recordings: {wet_mix_count}")

        # Count events
        manifest = MANIFESTS_DIR / "enst_drums_events.jsonl"
        if manifest.exists():
            with open(manifest) as f:
                event_count = sum(1 for _ in f)
            print(f"   JSONL events: {event_count:,}")
        print(f"   Status: READY")
    else:
        print(f"   Status: MISSING (need {enst_root})")

    print()

    # Check Slakh2100
    slakh_root = AUDIO_ROOTS["slakh2100"]
    print("2. Slakh2100 (mix.flac → Demucs) — CHINA/SPLASH SOURCE")
    if slakh_root.exists():
        mix_count = 0
        for split in ['train', 'test']:
            split_dir = slakh_root / split
            if split_dir.exists():
                tracks = [d for d in split_dir.iterdir() if d.is_dir() and (d / "mix.flac").exists()]
                mix_count += len(tracks)
                print(f"   {split}: {len(tracks)} tracks with mix.flac")
        print(f"   Total tracks: {mix_count}")

        manifest = MANIFESTS_DIR / "slakh2100_events.jsonl"
        if manifest.exists():
            event_count = 0
            china_count = 0
            splash_count = 0
            with open(manifest) as f:
                for line_str in f:
                    try:
                        evt = json.loads(line_str)
                        event_count += 1
                        for comp in evt.get('components', []):
                            lbl = comp.get('label', '').lower()
                            if lbl == 'china':
                                china_count += 1
                            elif lbl == 'splash':
                                splash_count += 1
                    except json.JSONDecodeError:
                        pass
            print(f"   JSONL events: {event_count:,}")
            print(f"   china: {china_count:,}, splash: {splash_count:,}")
        print(f"   Status: READY")
    else:
        print(f"   Status: MISSING (need {slakh_root})")

    print()

    # Check EGMD
    egmd_root = AUDIO_ROOTS["egmd"]
    print("3. EGMD (mix with musdb18 → Demucs)")
    if egmd_root.exists():
        wav_count = 0
        for drummer_dir in sorted(egmd_root.iterdir()):
            if drummer_dir.is_dir() and 'drummer' in drummer_dir.name:
                for session_dir in drummer_dir.iterdir():
                    if session_dir.is_dir():
                        wav_count += len(list(session_dir.glob("*.wav")))
        print(f"   Total WAV files: {wav_count:,}")

        manifest = MANIFESTS_DIR / "egmd_events.jsonl"
        if manifest.exists():
            with open(manifest) as f:
                event_count = sum(1 for _ in f)
            print(f"   JSONL events: {event_count:,}")
        print(f"   Status: READY")
    else:
        print(f"   Status: MISSING (need {egmd_root})")

    print()

    # Check Groove
    groove_root = AUDIO_ROOTS["groove_midi"]
    print("4. Groove MIDI (mix with musdb18 → Demucs)")
    if groove_root.exists():
        wav_count = 0
        for drummer_dir in sorted(groove_root.iterdir()):
            if drummer_dir.is_dir() and 'drummer' in drummer_dir.name:
                for session_dir in drummer_dir.iterdir():
                    if session_dir.is_dir():
                        wav_count += len(list(session_dir.glob("*.wav")))
        print(f"   Total WAV files: {wav_count:,}")

        for name in ["groove_events.jsonl", "groove_mididataset_events.jsonl"]:
            manifest = MANIFESTS_DIR / name
            if manifest.exists():
                with open(manifest) as f:
                    event_count = sum(1 for _ in f)
                print(f"   JSONL events ({name}): {event_count:,}")
        print(f"   Status: READY")
    else:
        print(f"   Status: MISSING (need {groove_root})")

    print()

    # Check musdb18 (needed for mixing)
    musdb_root = AUDIO_ROOTS["musdb18_hq"]
    print("5. musdb18-HQ (backing tracks for mixing)")
    if musdb_root.exists():
        for split in ['train', 'test']:
            split_dir = musdb_root / split
            if split_dir.exists():
                songs = [d for d in split_dir.iterdir() if d.is_dir()]
                print(f"   {split}: {len(songs)} songs")
        print(f"   Status: READY")
    else:
        print(f"   Status: MISSING (need {musdb_root})")

    print()

    # Check existing Demucs-augmented data
    print("=" * 70)
    print("EXISTING DEMUCS-AUGMENTED DATASETS")
    print("=" * 70)
    for name in ["enst_drums_demucs", "slakh2100_demucs", "egmd_demucs", "groove_midi_demucs"]:
        ds_dir = OUTPUT_BASE / name
        manifest = ds_dir / f"{name}_manifest.json"
        checkpoint_dir = ds_dir / f".{name}_checkpoint"
        if manifest.exists():
            with open(manifest) as f:
                m = json.load(f)
            print(f"  {name}: {m['total_samples']:,} samples, "
                  f"{m['batch_count']} batches  [COMPLETE]")
        elif checkpoint_dir.exists():
            cp_file = checkpoint_dir / "checkpoint.json"
            if cp_file.exists():
                with open(cp_file) as f:
                    cp = json.load(f)
                print(f"  {name}: {cp['total_samples']:,} samples so far  "
                      f"[IN PROGRESS — run again to resume]")
            else:
                print(f"  {name}: NOT YET CREATED")
        else:
            print(f"  {name}: NOT YET CREATED")

    print()
    print("=" * 70)
    print("RECOMMENDED PROCESSING ORDER:")
    print("=" * 70)
    print("1. ENST wet_mix → Demucs   (~15 min GPU, ~45K samples, HIGHEST impact)")
    print("2. Slakh2100 mix → Demucs  (~2-4 hrs GPU, ~262K samples, CHINA/SPLASH)")
    print("3. Groove + musdb18 → mix → Demucs  (~30 min GPU, ~20K samples)")
    print("4. EGMD + musdb18 → mix → Demucs  (~2-8 hrs GPU, ~100-500K samples)")
    print()
    print("Commands:")
    print("  python scripts/create_demucs_augmented_dataset.py --source enst")
    print("  python scripts/create_demucs_augmented_dataset.py --source slakh")
    print("  python scripts/create_demucs_augmented_dataset.py --source groove")
    print("  python scripts/create_demucs_augmented_dataset.py --source egmd --max-files 5000")
    print()
    print("All phases support checkpoint/resume — safe to Ctrl-C and restart.")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Create Demucs-augmented training data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze what's available
  python scripts/create_demucs_augmented_dataset.py --analyze

  # Process ENST (fastest, highest impact)
  python scripts/create_demucs_augmented_dataset.py --source enst

  # Process Slakh2100 (china/splash coverage)
  python scripts/create_demucs_augmented_dataset.py --source slakh

  # Process EGMD with 5000 file subsample
  python scripts/create_demucs_augmented_dataset.py --source egmd --max-files 5000

  # Process all sources
  python scripts/create_demucs_augmented_dataset.py --source all

  # Force reprocessing (ignores existing manifest + checkpoint)
  python scripts/create_demucs_augmented_dataset.py --source enst --force
        """,
    )
    parser.add_argument('--analyze', action='store_true',
                        help='Analyze available data without processing')
    parser.add_argument('--source', type=str, choices=['enst', 'slakh', 'egmd', 'groove', 'all'],
                        help='Which source to process')
    parser.add_argument('--max-files', type=int, default=5000,
                        help='Max files to process for EGMD/Groove (default: 5000)')
    parser.add_argument('--max-recordings', type=int, default=None,
                        help='Max recordings for ENST (default: all)')
    parser.add_argument('--max-tracks', type=int, default=None,
                        help='Max tracks for Slakh2100 (default: all ~1708)')
    parser.add_argument('--snr-min', type=float, default=-3.0,
                        help='Minimum SNR for drum/backing mix in dB (default: -3)')
    parser.add_argument('--snr-max', type=float, default=6.0,
                        help='Maximum SNR for drum/backing mix in dB (default: 6)')
    parser.add_argument('--device', type=str, default='auto',
                        help='Device for Demucs (auto/cuda/cpu)')
    parser.add_argument('--output', type=str, default=None,
                        help='Override output base directory')
    parser.add_argument('--force', action='store_true',
                        help='Force reprocessing (ignores existing manifests and checkpoints)')

    args = parser.parse_args()

    if args.analyze:
        analyze_available_data()
        return

    if not args.source:
        parser.print_help()
        return

    # Install signal handler for graceful Ctrl-C
    signal.signal(signal.SIGINT, _signal_handler)

    # Override output if specified
    global OUTPUT_BASE
    if args.output:
        OUTPUT_BASE = Path(args.output)

    # Initialize Demucs processor
    demucs = DemucsProcessor(device=args.device)

    # Initialize music mixer (for EGMD/Groove phases)
    mixer = MusicMixer(AUDIO_ROOTS["musdb18_hq"], sr=SAMPLE_RATE)

    snr_range = (args.snr_min, args.snr_max)

    sources = ['enst', 'slakh', 'egmd', 'groove'] if args.source == 'all' else [args.source]

    results = {}

    for source in sources:
        if _shutdown_requested:
            print("\n   Stopping — Ctrl-C was pressed.")
            break

        if source == 'enst':
            result = process_enst_demucs(
                demucs,
                max_recordings=args.max_recordings,
                force=args.force,
            )
            results['enst'] = result

        elif source == 'slakh':
            result = process_slakh_demucs(
                demucs,
                max_tracks=args.max_tracks,
                force=args.force,
            )
            results['slakh'] = result

        elif source == 'egmd':
            result = process_egmd_demucs(
                demucs, mixer,
                max_files=args.max_files,
                snr_range=snr_range,
                force=args.force,
            )
            results['egmd'] = result

        elif source == 'groove':
            result = process_groove_demucs(
                demucs, mixer,
                max_files=args.max_files,
                snr_range=snr_range,
                force=args.force,
            )
            results['groove'] = result

    # Summary
    print("\n" + "=" * 70)
    print("DEMUCS AUGMENTATION SUMMARY")
    print("=" * 70)
    for source, result in results.items():
        if result:
            print(f"  {source}: {result['total_samples']:,} samples, "
                  f"{result['batch_count']} batches")
        else:
            print(f"  {source}: INCOMPLETE (run again to resume)")

    if not _shutdown_requested:
        print("\nThe training script will automatically discover these datasets.")
        print("To fine-tune, run training with the existing dataset path:")
        print(f"  --dataset {OUTPUT_BASE}")


if __name__ == "__main__":
    main()
