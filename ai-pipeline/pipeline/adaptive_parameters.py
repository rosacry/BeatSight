"""
Adaptive Parameters for BeatSight AI Pipeline

This module provides DYNAMIC, LEARNED, and ADAPTIVE versions of what were
previously hardcoded constants. This is key to achieving revolutionary
accuracy - parameters that adapt to the music being processed.

Key innovations:
1. Learned Transition Matrices - train from labeled data per genre
2. Adaptive IOI Limits - tempo and style-dependent constraints
3. Signal-Adaptive Preprocessing - HPSS, onset detection tuning
4. Self-Calibrating Thresholds - confidence calibration
5. Dynamic Architecture Selection - route to best model per audio

The philosophy: NOTHING should be hardcoded that can be learned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence, Any, Callable
from pathlib import Path
from enum import Enum, auto
import numpy as np
import json
import warnings

try:
    import pickle
except ImportError:
    pickle = None


# =============================================================================
# GENRE/STYLE DETECTION
# =============================================================================

class MusicStyle(Enum):
    """Detected music style for parameter adaptation."""
    ROCK = auto()
    METAL = auto()
    JAZZ = auto()
    POP = auto()
    FUNK = auto()
    LATIN = auto()
    ELECTRONIC = auto()
    HIP_HOP = auto()
    COUNTRY = auto()
    BLUES = auto()
    CLASSICAL = auto()
    WORLD = auto()
    UNKNOWN = auto()


@dataclass
class AudioCharacteristics:
    """
    Analyzed characteristics of an audio signal.
    Used to adapt all downstream parameters.
    """
    # Tempo characteristics
    estimated_bpm: float = 120.0
    bpm_confidence: float = 0.5
    tempo_stability: float = 1.0  # 1.0 = very stable, 0.0 = highly variable
    
    # Spectral characteristics
    spectral_centroid_mean: float = 2000.0
    spectral_brightness: float = 0.5  # 0-1, 1 = very bright
    spectral_flatness: float = 0.5    # 0-1, 1 = noisy
    
    # Dynamic characteristics
    dynamic_range_db: float = 20.0
    crest_factor: float = 10.0  # Peak to RMS ratio
    
    # Rhythmic characteristics  
    pulse_clarity: float = 0.5   # How clear is the beat
    syncopation_level: float = 0.3  # Amount of off-beat emphasis
    
    # Complexity
    polyphony_estimate: float = 1.0  # How many simultaneous sounds
    rhythmic_complexity: float = 0.5
    
    # Style inference
    inferred_style: MusicStyle = MusicStyle.UNKNOWN
    style_confidence: float = 0.0
    
    @classmethod
    def from_audio(
        cls,
        audio: np.ndarray,
        sr: int,
        bpm: Optional[float] = None,
    ) -> 'AudioCharacteristics':
        """
        Analyze audio to extract characteristics.
        
        Args:
            audio: Audio signal
            sr: Sample rate
            bpm: Pre-detected BPM (optional)
            
        Returns:
            AudioCharacteristics instance
        """
        try:
            import librosa
        except ImportError:
            warnings.warn("librosa not available, using default characteristics")
            return cls()
        
        # Ensure mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=0)
        
        # Basic spectral analysis
        spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
        spectral_centroid_mean = float(np.mean(spectral_centroids))
        
        # Brightness (ratio of high to low frequency energy)
        spec = np.abs(librosa.stft(audio))
        freq_bins = librosa.fft_frequencies(sr=sr)
        mid_freq_idx = np.searchsorted(freq_bins, 2000)
        low_energy = np.mean(spec[:mid_freq_idx])
        high_energy = np.mean(spec[mid_freq_idx:])
        brightness = high_energy / (low_energy + high_energy + 1e-10)
        
        # Flatness
        flatness = librosa.feature.spectral_flatness(y=audio)[0]
        mean_flatness = float(np.mean(flatness))
        
        # Dynamics
        rms = librosa.feature.rms(y=audio)[0]
        peak = np.max(np.abs(audio))
        rms_mean = np.mean(rms)
        dynamic_range = 20 * np.log10(np.max(rms) / (np.min(rms) + 1e-10) + 1e-10)
        crest_factor = peak / (rms_mean + 1e-10)
        
        # Tempo
        if bpm is None:
            tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
            bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])
        
        # Tempo stability (variance of inter-beat intervals)
        _, beat_frames = librosa.beat.beat_track(y=audio, sr=sr)
        if len(beat_frames) > 2:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            ibis = np.diff(beat_times)
            tempo_stability = 1.0 - min(1.0, np.std(ibis) / (np.mean(ibis) + 1e-10))
        else:
            tempo_stability = 0.5
        
        # Onset analysis for rhythmic complexity
        onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
        pulse_clarity = float(np.max(pulse)) if len(pulse) > 0 else 0.5
        
        # Infer style from characteristics
        style, style_conf = cls._infer_style(
            bpm, spectral_centroid_mean, brightness, 
            mean_flatness, dynamic_range, pulse_clarity
        )
        
        return cls(
            estimated_bpm=bpm,
            bpm_confidence=pulse_clarity,
            tempo_stability=tempo_stability,
            spectral_centroid_mean=spectral_centroid_mean,
            spectral_brightness=brightness,
            spectral_flatness=mean_flatness,
            dynamic_range_db=dynamic_range,
            crest_factor=crest_factor,
            pulse_clarity=pulse_clarity,
            rhythmic_complexity=1.0 - tempo_stability,
            inferred_style=style,
            style_confidence=style_conf,
        )
    
    @staticmethod
    def _infer_style(
        bpm: float,
        centroid: float,
        brightness: float,
        flatness: float,
        dynamics: float,
        pulse_clarity: float,
    ) -> Tuple[MusicStyle, float]:
        """Infer music style from audio characteristics."""
        scores: Dict[MusicStyle, float] = {}
        
        # Metal: fast, bright, high dynamics
        metal_score = 0.0
        if bpm > 140:
            metal_score += 0.3
        if brightness > 0.6:
            metal_score += 0.3
        if dynamics > 30:
            metal_score += 0.2
        if centroid > 3000:
            metal_score += 0.2
        scores[MusicStyle.METAL] = metal_score
        
        # Jazz: moderate tempo, high dynamics, complex rhythms
        jazz_score = 0.0
        if 80 < bpm < 180:
            jazz_score += 0.2
        if dynamics > 25:
            jazz_score += 0.3
        if pulse_clarity < 0.6:  # More rhythmic freedom
            jazz_score += 0.3
        if 1500 < centroid < 4000:
            jazz_score += 0.2
        scores[MusicStyle.JAZZ] = jazz_score
        
        # Electronic: steady tempo, flat spectrum, clear pulse
        electronic_score = 0.0
        if pulse_clarity > 0.7:
            electronic_score += 0.3
        if flatness > 0.4:
            electronic_score += 0.3
        if 100 < bpm < 150:
            electronic_score += 0.2
        scores[MusicStyle.ELECTRONIC] = electronic_score
        
        # Hip-hop: slower tempo, bass-heavy
        hiphop_score = 0.0
        if 70 < bpm < 110:
            hiphop_score += 0.4
        if brightness < 0.4:
            hiphop_score += 0.3
        if pulse_clarity > 0.6:
            hiphop_score += 0.2
        scores[MusicStyle.HIP_HOP] = hiphop_score
        
        # Rock: moderate tempo, balanced spectrum
        rock_score = 0.0
        if 90 < bpm < 160:
            rock_score += 0.3
        if 0.4 < brightness < 0.6:
            rock_score += 0.3
        if pulse_clarity > 0.5:
            rock_score += 0.2
        scores[MusicStyle.ROCK] = rock_score
        
        # Funk: moderate tempo, syncopated
        funk_score = 0.0
        if 90 < bpm < 130:
            funk_score += 0.3
        if pulse_clarity < 0.6:
            funk_score += 0.3  # More off-beat emphasis
        scores[MusicStyle.FUNK] = funk_score
        
        # Pop: clear beat, moderate everything
        pop_score = 0.0
        if 100 < bpm < 140:
            pop_score += 0.3
        if pulse_clarity > 0.6:
            pop_score += 0.3
        if 0.3 < brightness < 0.6:
            pop_score += 0.2
        scores[MusicStyle.POP] = pop_score
        
        # Find best match
        best_style = max(scores, key=scores.get)
        best_score = scores[best_style]
        
        if best_score < 0.4:
            return MusicStyle.UNKNOWN, best_score
        
        return best_style, best_score


# =============================================================================
# ADAPTIVE TRANSITION MATRICES
# =============================================================================

@dataclass
class LearnedTransitionMatrix:
    """
    Transition matrix that can be learned from labeled data.
    
    Instead of hardcoded probabilities, these are computed from
    actual drum transcriptions per genre/style.
    """
    
    num_states: int = 7
    matrix: np.ndarray = field(default_factory=lambda: np.ones((7, 7)) / 7)
    
    # Genre-specific matrices
    genre_matrices: Dict[MusicStyle, np.ndarray] = field(default_factory=dict)
    
    # Observation counts for online learning
    transition_counts: np.ndarray = field(default_factory=lambda: np.zeros((7, 7)))
    
    # Prior strength (how much to trust the prior vs observed data)
    prior_strength: float = 10.0
    
    def __post_init__(self):
        """Initialize with reasonable default priors."""
        # Default prior (uniform-ish with some musical knowledge)
        self.matrix = np.array([
            # To:   SIL   KICK  SNARE HIHAT TOM   CYM   GHOST
            [0.90, 0.02, 0.02, 0.03, 0.01, 0.01, 0.01],  # From SILENCE
            [0.15, 0.05, 0.25, 0.35, 0.08, 0.10, 0.02],  # From KICK
            [0.20, 0.15, 0.05, 0.40, 0.08, 0.10, 0.02],  # From SNARE
            [0.10, 0.20, 0.20, 0.30, 0.08, 0.07, 0.05],  # From HIHAT
            [0.15, 0.15, 0.20, 0.25, 0.15, 0.08, 0.02],  # From TOM
            [0.25, 0.20, 0.15, 0.25, 0.05, 0.05, 0.05],  # From CYMBAL
            [0.05, 0.10, 0.60, 0.15, 0.03, 0.02, 0.05],  # From GHOST
        ], dtype=np.float64)
        
        self.transition_counts = self.matrix * self.prior_strength
    
    def observe_transition(self, from_state: int, to_state: int, count: float = 1.0) -> None:
        """
        Observe a transition and update counts (online learning).
        
        Args:
            from_state: Previous state index
            to_state: Current state index
            count: Weight of observation (default 1.0)
        """
        self.transition_counts[from_state, to_state] += count
        
        # Update matrix from counts
        row_sums = self.transition_counts.sum(axis=1, keepdims=True)
        self.matrix = self.transition_counts / (row_sums + 1e-10)
    
    def learn_from_sequence(
        self,
        state_sequence: Sequence[int],
        style: Optional[MusicStyle] = None,
    ) -> None:
        """
        Learn transition probabilities from a labeled sequence.
        
        Args:
            state_sequence: Sequence of state indices
            style: Optional music style for style-specific learning
        """
        if len(state_sequence) < 2:
            return
        
        for i in range(len(state_sequence) - 1):
            from_state = state_sequence[i]
            to_state = state_sequence[i + 1]
            self.observe_transition(from_state, to_state)
        
        # Also update genre-specific matrix
        if style is not None and style != MusicStyle.UNKNOWN:
            if style not in self.genre_matrices:
                self.genre_matrices[style] = np.zeros((self.num_states, self.num_states))
            
            for i in range(len(state_sequence) - 1):
                self.genre_matrices[style][state_sequence[i], state_sequence[i + 1]] += 1
    
    def get_matrix(self, style: Optional[MusicStyle] = None) -> np.ndarray:
        """
        Get transition matrix, optionally style-specific.
        
        Args:
            style: Music style to get specialized matrix for
            
        Returns:
            Transition probability matrix
        """
        if style is not None and style in self.genre_matrices:
            genre_counts = self.genre_matrices[style]
            if genre_counts.sum() > 50:  # Enough observations
                row_sums = genre_counts.sum(axis=1, keepdims=True)
                genre_matrix = genre_counts / (row_sums + 1e-10)
                # Blend with general matrix
                blend_factor = min(1.0, genre_counts.sum() / 500)
                return blend_factor * genre_matrix + (1 - blend_factor) * self.matrix
        
        return self.matrix
    
    def save(self, path: Path) -> None:
        """Save learned matrices to disk."""
        data = {
            'matrix': self.matrix.tolist(),
            'transition_counts': self.transition_counts.tolist(),
            'genre_matrices': {
                style.name: mat.tolist() 
                for style, mat in self.genre_matrices.items()
            },
            'prior_strength': self.prior_strength,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> 'LearnedTransitionMatrix':
        """Load learned matrices from disk."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        instance = cls()
        instance.matrix = np.array(data['matrix'])
        instance.transition_counts = np.array(data['transition_counts'])
        instance.prior_strength = data.get('prior_strength', 10.0)
        instance.genre_matrices = {
            MusicStyle[name]: np.array(mat)
            for name, mat in data.get('genre_matrices', {}).items()
        }
        
        return instance


# =============================================================================
# ADAPTIVE IOI LIMITS
# =============================================================================

@dataclass
class AdaptiveIOILimits:
    """
    Tempo and style-dependent inter-onset interval limits.
    
    Instead of fixed minimums, these adapt based on:
    - Current tempo (faster tempo = stricter limits)
    - Music style (metal allows faster double bass)
    - Audio characteristics (transient clarity)
    """
    
    # Base limits in ms (at 120 BPM)
    base_limits: Dict[int, float] = field(default_factory=lambda: {
        0: 0,      # SILENCE
        1: 50,     # KICK
        2: 40,     # SNARE
        3: 30,     # HIHAT
        4: 60,     # TOM
        5: 80,     # CYMBAL
        6: 35,     # GHOST
    })
    
    # Style multipliers
    style_multipliers: Dict[MusicStyle, Dict[int, float]] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize style-specific multipliers."""
        # Metal: faster double bass, blast beats
        self.style_multipliers[MusicStyle.METAL] = {
            1: 0.6,   # Kick can be very fast (double bass)
            2: 0.7,   # Blast beat snares
            3: 0.8,
            4: 0.9,
            5: 1.0,
            6: 0.8,
        }
        
        # Jazz: allows brush rolls, ghost note clusters
        self.style_multipliers[MusicStyle.JAZZ] = {
            1: 0.9,
            2: 0.7,  # Brush rolls
            3: 0.8,
            4: 0.8,
            5: 0.9,
            6: 0.6,  # Ghost note clusters
        }
        
        # Electronic: very precise, can be fast
        self.style_multipliers[MusicStyle.ELECTRONIC] = {
            1: 0.7,
            2: 0.8,
            3: 0.7,  # Fast hi-hat patterns
            4: 0.9,
            5: 0.9,
            6: 0.8,
        }
        
        # Funk: ghost notes are key
        self.style_multipliers[MusicStyle.FUNK] = {
            1: 0.9,
            2: 0.8,
            3: 0.9,
            4: 0.9,
            5: 1.0,
            6: 0.5,  # Very fast ghost notes
        }
    
    def get_limit(
        self,
        state: int,
        bpm: float,
        style: MusicStyle = MusicStyle.UNKNOWN,
        characteristics: Optional[AudioCharacteristics] = None,
    ) -> float:
        """
        Get adaptive IOI limit for a given state and context.
        
        Args:
            state: Drum state index
            bpm: Current tempo
            style: Music style
            characteristics: Audio characteristics for fine-tuning
            
        Returns:
            Minimum IOI in milliseconds
        """
        base = self.base_limits.get(state, 50)
        
        # Tempo scaling: faster tempos need proportionally faster limits
        # But not linear - there's a floor
        tempo_factor = max(0.5, min(1.5, 120.0 / bpm))
        
        # Style multiplier
        style_mults = self.style_multipliers.get(style, {})
        style_factor = style_mults.get(state, 1.0)
        
        # Characteristics-based adjustment
        char_factor = 1.0
        if characteristics is not None:
            # High pulse clarity = can be stricter
            if characteristics.pulse_clarity > 0.7:
                char_factor *= 0.9
            # High dynamic range = cleaner transients
            if characteristics.dynamic_range_db > 25:
                char_factor *= 0.95
        
        return base * tempo_factor * style_factor * char_factor


# =============================================================================
# ADAPTIVE PREPROCESSING PARAMETERS
# =============================================================================

@dataclass
class AdaptivePreprocessingParams:
    """
    Signal-adaptive preprocessing parameters.
    
    Instead of fixed HPSS margins, onset thresholds, etc.,
    these adapt based on audio characteristics.
    """
    
    # HPSS (Harmonic-Percussive Separation)
    hpss_harmonic_margin: float = 1.2
    hpss_percussive_margin: float = 2.5
    
    # Pre-emphasis
    preemphasis_coef: float = 0.97
    
    # Mel spectrogram
    fmin: float = 30.0
    fmax: float = 14000.0
    n_mels: int = 80
    
    # Onset detection
    onset_threshold_k: float = 1.5
    onset_wait_frames: int = 2
    onset_pre_avg: int = 3
    onset_post_avg: int = 3
    
    @classmethod
    def from_characteristics(
        cls,
        characteristics: AudioCharacteristics,
        sr: int = 44100,
    ) -> 'AdaptivePreprocessingParams':
        """
        Create adaptive parameters based on audio characteristics.
        
        Args:
            characteristics: Analyzed audio characteristics
            sr: Sample rate
            
        Returns:
            Adapted preprocessing parameters
        """
        params = cls()
        
        # HPSS margins: brighter audio needs different separation
        if characteristics.spectral_brightness > 0.6:
            # Bright audio: more percussive content, less harmonic masking
            params.hpss_harmonic_margin = 1.0
            params.hpss_percussive_margin = 3.0
        elif characteristics.spectral_brightness < 0.3:
            # Dark audio: more harmonic bleed into percussive
            params.hpss_harmonic_margin = 1.5
            params.hpss_percussive_margin = 2.0
        
        # Pre-emphasis: less for already bright audio
        if characteristics.spectral_brightness > 0.5:
            params.preemphasis_coef = 0.95
        else:
            params.preemphasis_coef = 0.98
        
        # Mel frequency range: adapt to actual content
        params.fmax = min(sr / 2 - 100, 14000.0)
        if characteristics.spectral_brightness < 0.3:
            params.fmax = min(params.fmax, 10000.0)  # Less high freq content
        
        # Onset detection: adapt to rhythmic clarity
        if characteristics.pulse_clarity > 0.7:
            # Clear transients: can use stricter threshold
            params.onset_threshold_k = 1.8
            params.onset_wait_frames = 2
        elif characteristics.pulse_clarity < 0.4:
            # Muddy transients: more lenient
            params.onset_threshold_k = 1.2
            params.onset_wait_frames = 3
            params.onset_pre_avg = 5
            params.onset_post_avg = 5
        
        # Tempo-based adjustments
        if characteristics.estimated_bpm > 160:
            # Fast tempo: smaller windows
            params.onset_wait_frames = 1
        elif characteristics.estimated_bpm < 80:
            # Slow tempo: can afford larger windows
            params.onset_wait_frames = 3
        
        return params


# =============================================================================
# SELF-CALIBRATING CONFIDENCE THRESHOLDS
# =============================================================================

@dataclass
class AdaptiveConfidenceThresholds:
    """
    Self-calibrating confidence thresholds.
    
    Instead of fixed thresholds like 0.95 for self-training,
    these adapt based on:
    - Per-class difficulty
    - Model calibration
    - Dataset characteristics
    """
    
    # Base thresholds per class
    class_thresholds: Dict[int, float] = field(default_factory=dict)
    
    # Global threshold
    global_threshold: float = 0.9
    
    # Calibration data
    confidence_bins: np.ndarray = field(
        default_factory=lambda: np.linspace(0, 1, 11)
    )
    accuracy_in_bins: np.ndarray = field(
        default_factory=lambda: np.linspace(0, 1, 10)
    )
    
    # Track reliability
    true_positive_rates: Dict[int, float] = field(default_factory=dict)
    false_positive_rates: Dict[int, float] = field(default_factory=dict)
    
    def calibrate(
        self,
        predictions: np.ndarray,
        confidences: np.ndarray,
        ground_truth: np.ndarray,
    ) -> None:
        """
        Calibrate thresholds based on validation predictions.
        
        Args:
            predictions: Predicted class indices
            confidences: Confidence scores
            ground_truth: True class indices
        """
        num_classes = int(np.max(predictions)) + 1
        
        # Per-class calibration
        for cls in range(num_classes):
            mask = predictions == cls
            if mask.sum() < 10:
                continue
            
            cls_conf = confidences[mask]
            cls_correct = (predictions[mask] == ground_truth[mask])
            
            # Find threshold where precision >= 0.95
            for thresh in np.linspace(0.5, 0.99, 50):
                high_conf_mask = cls_conf >= thresh
                if high_conf_mask.sum() < 5:
                    continue
                precision = cls_correct[high_conf_mask].mean()
                if precision >= 0.95:
                    self.class_thresholds[cls] = thresh
                    break
            else:
                self.class_thresholds[cls] = 0.99
            
            # Track TPR and FPR
            self.true_positive_rates[cls] = cls_correct.mean()
        
        # Reliability diagram data
        for i in range(len(self.confidence_bins) - 1):
            low, high = self.confidence_bins[i], self.confidence_bins[i + 1]
            mask = (confidences >= low) & (confidences < high)
            if mask.sum() > 0:
                self.accuracy_in_bins[i] = (predictions[mask] == ground_truth[mask]).mean()
    
    def get_threshold(
        self,
        class_idx: Optional[int] = None,
        use_class_specific: bool = True,
    ) -> float:
        """
        Get calibrated threshold.
        
        Args:
            class_idx: Class index (optional)
            use_class_specific: Whether to use per-class thresholds
            
        Returns:
            Calibrated confidence threshold
        """
        if use_class_specific and class_idx is not None:
            return self.class_thresholds.get(class_idx, self.global_threshold)
        return self.global_threshold
    
    def is_reliable(self, confidence: float, class_idx: int) -> bool:
        """Check if a prediction is reliable enough."""
        thresh = self.get_threshold(class_idx)
        return confidence >= thresh


# =============================================================================
# DYNAMIC FOCAL LOSS PARAMETERS
# =============================================================================

@dataclass
class AdaptiveFocalLossParams:
    """
    Per-class and training-progress-adaptive focal loss parameters.
    
    Instead of fixed gamma=2.0, adapt based on:
    - Class difficulty (harder classes need higher gamma)
    - Training progress (start low, increase)
    - Class frequency (rare classes need different treatment)
    """
    
    # Per-class gamma values
    class_gamma: Dict[int, float] = field(default_factory=dict)
    
    # Base gamma
    base_gamma: float = 2.0
    
    # Training progress
    current_epoch: int = 0
    total_epochs: int = 100
    
    # Gamma scheduling
    gamma_start: float = 1.0
    gamma_end: float = 3.0
    gamma_warmup_epochs: int = 10
    
    def update_epoch(self, epoch: int) -> None:
        """Update current epoch for scheduling."""
        self.current_epoch = epoch
    
    def get_gamma(self, class_idx: Optional[int] = None) -> float:
        """
        Get current gamma value.
        
        Args:
            class_idx: Optional class index for per-class gamma
            
        Returns:
            Gamma value for focal loss
        """
        # Epoch-based scheduling
        if self.current_epoch < self.gamma_warmup_epochs:
            progress = self.current_epoch / self.gamma_warmup_epochs
            scheduled_gamma = self.gamma_start + progress * (self.base_gamma - self.gamma_start)
        else:
            progress = (self.current_epoch - self.gamma_warmup_epochs) / max(
                1, self.total_epochs - self.gamma_warmup_epochs
            )
            scheduled_gamma = self.base_gamma + progress * (self.gamma_end - self.base_gamma)
        
        # Per-class adjustment
        if class_idx is not None and class_idx in self.class_gamma:
            class_factor = self.class_gamma[class_idx] / self.base_gamma
            return scheduled_gamma * class_factor
        
        return scheduled_gamma
    
    def calibrate_from_accuracy(
        self,
        class_accuracies: Dict[int, float],
    ) -> None:
        """
        Set per-class gamma based on class difficulties.
        
        Harder classes (lower accuracy) get higher gamma.
        
        Args:
            class_accuracies: Dict mapping class index to accuracy
        """
        if not class_accuracies:
            return
        
        mean_acc = np.mean(list(class_accuracies.values()))
        
        for cls, acc in class_accuracies.items():
            # Lower accuracy = higher gamma (more focus on hard examples)
            difficulty = 1.0 - acc
            relative_difficulty = difficulty / (1.0 - mean_acc + 1e-10)
            
            # Scale gamma: 1.0-4.0 based on difficulty
            self.class_gamma[cls] = self.base_gamma * max(0.5, min(2.0, relative_difficulty))


# =============================================================================
# DYNAMIC AUGMENTATION PARAMETERS
# =============================================================================

@dataclass
class AdaptiveAugmentationParams:
    """
    Training-progress and dataset-adaptive augmentation parameters.
    
    Instead of fixed augmentation strengths, adapt based on:
    - Training progress (curriculum)
    - Dataset size (smaller datasets need more augmentation)
    - Class imbalance (oversample rare classes with more augmentation)
    """
    
    # Current settings
    mixup_alpha: float = 0.2
    cutmix_alpha: float = 1.0
    spec_augment_freq_masks: int = 2
    spec_augment_time_masks: int = 2
    spec_augment_freq_width: int = 15
    spec_augment_time_width: int = 35
    
    # Training progress
    current_epoch: int = 0
    total_epochs: int = 100
    
    # Schedules
    mixup_start: float = 0.1
    mixup_end: float = 0.4
    cutmix_start: float = 0.3
    cutmix_end: float = 1.0
    
    # Dataset characteristics
    dataset_size: int = 10000
    class_counts: Dict[int, int] = field(default_factory=dict)
    
    def update_epoch(self, epoch: int) -> None:
        """Update augmentation parameters for current epoch."""
        self.current_epoch = epoch
        progress = epoch / max(1, self.total_epochs)
        
        # Curriculum: increase augmentation over time
        self.mixup_alpha = self.mixup_start + progress * (self.mixup_end - self.mixup_start)
        
        # CutMix: starts later, increases more aggressively
        cutmix_progress = max(0, (progress - 0.2) / 0.8)
        self.cutmix_alpha = self.cutmix_start + cutmix_progress * (
            self.cutmix_end - self.cutmix_start
        )
        
        # SpecAugment: also increases
        time_mask_progress = 25 + progress * 20  # 25 -> 45
        self.spec_augment_time_width = int(time_mask_progress)
    
    def get_augmentation_strength(self, class_idx: int) -> float:
        """
        Get augmentation strength multiplier for a class.
        
        Rare classes get stronger augmentation.
        
        Args:
            class_idx: Class index
            
        Returns:
            Multiplier for augmentation strength (1.0 = normal)
        """
        if not self.class_counts:
            return 1.0
        
        class_count = self.class_counts.get(class_idx, 1)
        max_count = max(self.class_counts.values())
        
        # Inverse frequency weighting
        rarity = max_count / (class_count + 1)
        
        # Cap at 2x
        return min(2.0, 1.0 + 0.5 * np.log(rarity))


# =============================================================================
# MASTER ADAPTIVE CONFIG
# =============================================================================

@dataclass
class AdaptiveConfig:
    """
    Master configuration that adapts all parameters.
    
    This is the single entry point for getting adapted parameters
    based on audio characteristics and training state.
    """
    
    # Audio characteristics (set during processing)
    characteristics: Optional[AudioCharacteristics] = None
    
    # Components
    transition_matrix: LearnedTransitionMatrix = field(
        default_factory=LearnedTransitionMatrix
    )
    ioi_limits: AdaptiveIOILimits = field(
        default_factory=AdaptiveIOILimits
    )
    preprocessing: AdaptivePreprocessingParams = field(
        default_factory=AdaptivePreprocessingParams
    )
    confidence: AdaptiveConfidenceThresholds = field(
        default_factory=AdaptiveConfidenceThresholds
    )
    focal_loss: AdaptiveFocalLossParams = field(
        default_factory=AdaptiveFocalLossParams
    )
    augmentation: AdaptiveAugmentationParams = field(
        default_factory=AdaptiveAugmentationParams
    )
    
    def adapt_to_audio(
        self,
        audio: np.ndarray,
        sr: int,
        bpm: Optional[float] = None,
    ) -> None:
        """
        Adapt all parameters based on audio analysis.
        
        Args:
            audio: Audio signal
            sr: Sample rate
            bpm: Pre-detected BPM (optional)
        """
        self.characteristics = AudioCharacteristics.from_audio(audio, sr, bpm)
        self.preprocessing = AdaptivePreprocessingParams.from_characteristics(
            self.characteristics, sr
        )
    
    def get_preprocessing_params(self) -> AdaptivePreprocessingParams:
        """Get current preprocessing parameters."""
        if self.characteristics is not None:
            return AdaptivePreprocessingParams.from_characteristics(
                self.characteristics
            )
        return self.preprocessing
    
    def get_ioi_limit(self, state: int, bpm: float) -> float:
        """Get adaptive IOI limit."""
        style = MusicStyle.UNKNOWN
        if self.characteristics is not None:
            style = self.characteristics.inferred_style
        return self.ioi_limits.get_limit(state, bpm, style, self.characteristics)
    
    def get_transition_matrix(self) -> np.ndarray:
        """Get transition matrix adapted to current style."""
        style = None
        if self.characteristics is not None:
            style = self.characteristics.inferred_style
        return self.transition_matrix.get_matrix(style)
    
    def save(self, path: Path) -> None:
        """Save all learned parameters."""
        path.mkdir(parents=True, exist_ok=True)
        self.transition_matrix.save(path / "transition_matrix.json")
        
        # Save other calibrated parameters
        config_data = {
            'global_confidence_threshold': self.confidence.global_threshold,
            'class_thresholds': self.confidence.class_thresholds,
            'focal_loss_class_gamma': self.focal_loss.class_gamma,
        }
        with open(path / "adaptive_config.json", 'w') as f:
            json.dump(config_data, f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> 'AdaptiveConfig':
        """Load learned parameters from disk."""
        config = cls()
        
        tm_path = path / "transition_matrix.json"
        if tm_path.exists():
            config.transition_matrix = LearnedTransitionMatrix.load(tm_path)
        
        cfg_path = path / "adaptive_config.json"
        if cfg_path.exists():
            with open(cfg_path, 'r') as f:
                data = json.load(f)
            config.confidence.global_threshold = data.get(
                'global_confidence_threshold', 0.9
            )
            config.confidence.class_thresholds = {
                int(k): v for k, v in data.get('class_thresholds', {}).items()
            }
            config.focal_loss.class_gamma = {
                int(k): v for k, v in data.get('focal_loss_class_gamma', {}).items()
            }
        
        return config


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global adaptive config instance
_GLOBAL_CONFIG: Optional[AdaptiveConfig] = None


def get_adaptive_config() -> AdaptiveConfig:
    """Get the global adaptive configuration."""
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = AdaptiveConfig()
    return _GLOBAL_CONFIG


def set_adaptive_config(config: AdaptiveConfig) -> None:
    """Set the global adaptive configuration."""
    global _GLOBAL_CONFIG
    _GLOBAL_CONFIG = config


def adapt_to_audio(audio: np.ndarray, sr: int, bpm: Optional[float] = None) -> AdaptiveConfig:
    """
    Convenience function to adapt global config to audio.
    
    Args:
        audio: Audio signal
        sr: Sample rate  
        bpm: Pre-detected BPM
        
    Returns:
        Adapted configuration
    """
    config = get_adaptive_config()
    config.adapt_to_audio(audio, sr, bpm)
    return config
