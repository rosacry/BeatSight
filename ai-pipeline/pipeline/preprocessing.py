"""
Audio preprocessing utilities
"""

import soundfile as sf
import librosa
import numpy as np
from pathlib import Path
from typing import Tuple


def preprocess_audio(input_path: str, target_sr: int = 44100) -> Tuple[np.ndarray, int]:
    """
    Preprocess audio file to standard format.
    
    Args:
        input_path: Path to input audio file
        target_sr: Target sample rate (default 44100 Hz)
        
    Returns:
        Tuple of (audio data as numpy array, sample rate)
    """
    # Load audio with librosa (handles most formats via soundfile/audioread)
    audio, sr = librosa.load(input_path, sr=target_sr, mono=False)
    
    # Convert stereo to mono if needed (mix down)
    if audio.ndim == 2:
        audio = librosa.to_mono(audio)
    
    # Normalize audio to [-1, 1] range
    audio = librosa.util.normalize(audio)
    
    return audio, sr


def compute_audio_hash(audio: np.ndarray) -> str:
    """
    Compute SHA-256 hash of audio data for integrity checking.
    """
    import hashlib
    return "sha256:" + hashlib.sha256(audio.tobytes()).hexdigest()


def get_audio_duration(audio: np.ndarray, sr: int) -> float:
    """
    Get audio duration in seconds.
    """
    return len(audio) / sr
