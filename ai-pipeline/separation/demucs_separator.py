"""
Drum source separation using Demucs
"""

import torch
import numpy as np
from demucs.pretrained import get_model
from demucs.apply import apply_model
from typing import Tuple


class DrumSeparator:
    """Wrapper for Demucs drum separation"""
    
    def __init__(self, model_name: str = "htdemucs"):
        """
        Initialize Demucs model.
        
        Args:
            model_name: Demucs model to use (htdemucs, htdemucs_ft, etc.)
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"   Loading Demucs model '{model_name}' on {self.device}...")
        self.model = get_model(model_name)
        self.model.to(self.device)
        self.model.eval()
        
    def separate(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Separate drums from audio.
        
        Args:
            audio: Audio data (mono or stereo)
            sr: Sample rate
            
        Returns:
            Isolated drum track (mono)
        """
        # Ensure stereo for Demucs (it expects stereo input)
        if audio.ndim == 1:
            audio = np.stack([audio, audio])  # Convert mono to stereo
        elif audio.ndim == 2 and audio.shape[0] > 2:
            audio = audio[:2]  # Take first 2 channels if more
            
        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio).float().unsqueeze(0).to(self.device)
        
        # Apply model
        with torch.no_grad():
            sources = apply_model(self.model, audio_tensor, device=self.device)
        
        # Extract drums (index depends on model, typically index 0)
        # HTDemucs order: drums, bass, other, vocals
        drums = sources[0, 0].cpu().numpy()  # First source is drums
        
        # Convert stereo to mono
        if drums.ndim == 2:
            drums = np.mean(drums, axis=0)
            
        return drums


# Global instance (lazy loaded)
_separator = None


def separate_drums(audio: Tuple[np.ndarray, int]) -> Tuple[np.ndarray, int]:
    """
    Separate drums from audio using Demucs.
    
    Args:
        audio: Tuple of (audio data, sample rate)
        
    Returns:
        Tuple of (isolated drums, sample rate)
    """
    global _separator
    
    audio_data, sr = audio
    
    if _separator is None:
        _separator = DrumSeparator()
    
    drums = _separator.separate(audio_data, sr)
    
    return drums, sr
