"""
Onset detection for drum hits
"""

import librosa
import numpy as np
from typing import List, Tuple


def detect_onsets(
    audio: Tuple[np.ndarray, int],
    hop_length: int = 512,
    threshold: float = 0.5,
) -> List[Tuple[float, float]]:
    """
    Detect onset times in audio.
    
    Args:
        audio: Tuple of (audio data, sample rate)
        hop_length: Hop length for analysis
        threshold: Onset detection threshold (0.0-1.0)
        
    Returns:
        List of (time in seconds, confidence) tuples
    """
    audio_data, sr = audio
    
    # Compute onset strength envelope
    onset_env = librosa.onset.onset_strength(
        y=audio_data,
        sr=sr,
        hop_length=hop_length,
        aggregate=np.median,
    )
    
    # Detect peaks in onset strength
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop_length,
        backtrack=True,
        threshold=threshold,
    )
    
    # Convert frames to times and add confidence
    onsets = []
    for frame in onset_frames:
        time = librosa.frames_to_time(frame, sr=sr, hop_length=hop_length)
        # Confidence is the onset strength at that frame
        confidence = float(onset_env[frame]) if frame < len(onset_env) else 0.0
        onsets.append((time, confidence))
    
    return onsets


def refine_onsets(
    audio: Tuple[np.ndarray, int],
    onsets: List[Tuple[float, float]],
    window_ms: float = 50.0,
) -> List[Tuple[float, float]]:
    """
    Refine onset times using local maxima in audio energy.
    
    Args:
        audio: Tuple of (audio data, sample rate)
        onsets: Initial onset detections
        window_ms: Window size for refinement in milliseconds
        
    Returns:
        Refined onset list
    """
    audio_data, sr = audio
    window_samples = int(window_ms * sr / 1000)
    
    refined = []
    for time, confidence in onsets:
        # Get window around onset
        center = int(time * sr)
        start = max(0, center - window_samples // 2)
        end = min(len(audio_data), center + window_samples // 2)
        
        window = audio_data[start:end]
        
        # Find local maximum in absolute amplitude
        local_max_idx = np.argmax(np.abs(window))
        refined_time = (start + local_max_idx) / sr
        
        refined.append((refined_time, confidence))
    
    return refined
