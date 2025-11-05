"""High-resolution drum onset detection with adaptive thresholding."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import librosa
from scipy import ndimage


@dataclass
class DetectedOnset:
    """Container describing a detected onset."""

    time: float
    confidence: float
    envelope_value: float
    threshold_value: float
    frame_index: int
    band_energies: np.ndarray

    def as_legacy_tuple(self) -> Tuple[float, float]:
        return float(self.time), float(self.confidence)

    def to_debug_dict(self) -> Dict[str, object]:
        return {
            "time": float(self.time),
            "confidence": float(self.confidence),
            "envelope": float(self.envelope_value),
            "threshold": float(self.threshold_value),
            "frame": int(self.frame_index),
            "band_energy": self.band_energies.astype(float).tolist(),
        }


@dataclass
class OnsetDetectionResult:
    """Full detection result including debug artefacts."""

    onsets: List[DetectedOnset]
    envelope: np.ndarray
    adaptive_threshold: np.ndarray
    sample_rate: int
    hop_length: int
    estimated_tempo: float
    tempo_candidates: Sequence[float]

    def legacy_tuples(self) -> List[Tuple[float, float]]:
        return [onset.as_legacy_tuple() for onset in self.onsets]

    def to_debug_payload(self) -> Dict[str, object]:
        return {
            "sample_rate": int(self.sample_rate),
            "hop_length": int(self.hop_length),
            "tempo": float(self.estimated_tempo),
            "tempo_candidates": [float(t) for t in self.tempo_candidates],
            "envelope": self.envelope.astype(float).tolist(),
            "adaptive_threshold": self.adaptive_threshold.astype(float).tolist(),
            "peaks": [onset.to_debug_dict() for onset in self.onsets],
        }


def _compute_percussive_stem(audio: np.ndarray) -> np.ndarray:
    """Extract the percussive component using HPSS."""

    harmonic, percussive = librosa.effects.hpss(audio, margin=(1.2, 2.5), power=2.0)
    # Keep only the percussive layer; ensure contiguous copy to avoid view surprises.
    return np.array(percussive, dtype=np.float32, copy=True)


def _mel_spectral_flux(
    audio: np.ndarray,
    sr: int,
    hop_length: int,
    n_fft: int,
    n_mels: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return percussive mel spectrogram and spectral flux onset envelope."""

    pre_emphasised = librosa.effects.preemphasis(audio, coef=0.97)
    mel = librosa.feature.melspectrogram(
        y=pre_emphasised,
        sr=sr,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=n_mels,
        fmin=30.0,
        fmax=min(sr / 2 - 100, 14000.0),
        power=2.0,
        htk=True,
    )

    log_mel = librosa.power_to_db(mel, ref=np.max)
    diff = np.diff(log_mel, axis=1)
    flux = np.maximum(diff, 0.0)
    envelope = np.sum(flux, axis=0)
    # Pad so the envelope length matches the frame count of mel spectrogram.
    envelope = np.concatenate([[0.0], envelope])

    if envelope.size > 0 and np.max(envelope) > 0:
        envelope /= np.max(envelope)

    return mel, envelope


def _adaptive_threshold(
    envelope: np.ndarray,
    window: int,
    k: float,
) -> np.ndarray:
    """Compute moving adaptive threshold using median + k*MAD."""

    if window % 2 == 0:
        window += 1

    median_env = ndimage.median_filter(envelope, size=window, mode="nearest")
    abs_diff = np.abs(envelope - median_env)
    median_abs_dev = ndimage.median_filter(abs_diff, size=window, mode="nearest")
    # Consistent with standard MAD scaling factor for normal distribution
    mad_scaled = median_abs_dev * 1.4826 + 1e-6
    threshold = median_env + k * mad_scaled
    return threshold


def _tempo_candidates(
    envelope: np.ndarray,
    sr: int,
    hop_length: int,
) -> List[float]:
    """Return tempo candidates including double/half time hypotheses."""

    raw = librosa.beat.tempo(
        onset_envelope=envelope,
        sr=sr,
        hop_length=hop_length,
        aggregate=None,
        max_tempo=240,
    )

    candidates: List[float] = []
    if raw is None or len(raw) == 0:
        candidates = [120.0]
    else:
        # librosa returns an ndarray; take unique rounded tempos to avoid duplicates.
        rounded = sorted(
            {
                float(t)
                for t in raw
                if np.isfinite(t) and t > 0 and t >= 60.0
            }
        )
        if not rounded:
            rounded = [120.0]
        candidates.extend(rounded[:4])

    final_candidates: List[float] = []
    for tempo in candidates:
        for factor in (0.5, 1.0, 2.0):
            candidate = tempo * factor
            if 50 <= candidate <= 260:
                final_candidates.append(candidate)

    if not final_candidates:
        final_candidates = [120.0]

    # Remove near-duplicates while preserving order
    deduped: List[float] = []
    for tempo in final_candidates:
        if all(abs(existing - tempo) > 0.5 for existing in deduped):
            deduped.append(tempo)

    return deduped


def detect_onsets(
    audio: Tuple[np.ndarray, int],
    *,
    hop_length: int = 256,
    n_fft: int = 2048,
    n_mels: int = 80,
    sensitivity: float = 60.0,
    tempo_hint: Optional[float] = None,
    threshold_window_seconds: float = 0.35,
) -> OnsetDetectionResult:
    """Detect onsets from audio with adaptive thresholding.

    Args:
        audio: Tuple containing (audio_data, sample_rate)
        hop_length: STFT hop length in samples
        n_fft: STFT window size
        n_mels: Number of Mel filter bands
        sensitivity: User-provided sensitivity [0, 100]
        tempo_hint: Optional BPM hint to guide the minimum IOI calculation
        threshold_window_seconds: Window for adaptive threshold (in seconds)

    Returns:
        OnsetDetectionResult describing detected onsets and debug artefacts.
    """

    audio_data, sr = audio
    percussive = _compute_percussive_stem(audio_data)
    mel, envelope = _mel_spectral_flux(percussive, sr, hop_length, n_fft, n_mels)

    candidates = _tempo_candidates(envelope, sr, hop_length)
    estimated_tempo = tempo_hint if tempo_hint is not None else candidates[0]

    sens_clamped = float(np.clip(sensitivity, 0.0, 100.0)) / 100.0
    threshold_k = float(np.interp(sens_clamped, [0.0, 1.0], [2.4, 0.6]))

    window_frames = max(7, int(round(threshold_window_seconds * sr / hop_length)))
    adaptive_threshold = _adaptive_threshold(envelope, window_frames, threshold_k)

    base_sixteenth = 60.0 / max(estimated_tempo, 1e-3) / 4.0
    base_sixteenth = max(0.02, min(base_sixteenth, 0.12))
    min_ioi = base_sixteenth * (1.0 + (1.0 - sens_clamped) * 0.6)
    min_ioi = min(min_ioi, max(0.084, base_sixteenth))
    min_separation_frames = max(1, int(np.floor(min_ioi * sr / hop_length)))

    peak_window = 2  # frames on either side to check for local maxima

    onsets: List[DetectedOnset] = []
    last_onset_time = -np.inf
    last_onset_frame = -10_000

    for frame_index, (env_val, thr_val) in enumerate(zip(envelope, adaptive_threshold)):
        if env_val <= thr_val:
            continue

        local_start = max(0, frame_index - peak_window)
        local_end = min(len(envelope), frame_index + peak_window + 1)
        local_max = np.max(envelope[local_start:local_end])
        if env_val < local_max - 1e-6:
            continue

        time_seconds = librosa.frames_to_time(frame_index, sr=sr, hop_length=hop_length)
        if frame_index - last_onset_frame < min_separation_frames:
            continue

        band_energy = mel[:, frame_index] if frame_index < mel.shape[1] else np.zeros(mel.shape[0])
        confidence = float(np.clip((env_val - thr_val) / (1.0 - thr_val + 1e-6), 0.0, 1.0))
        onsets.append(
            DetectedOnset(
                time=float(time_seconds),
                confidence=confidence,
                envelope_value=float(env_val),
                threshold_value=float(thr_val),
                frame_index=frame_index,
                band_energies=np.asarray(band_energy, dtype=np.float32),
            )
        )
        last_onset_time = time_seconds
        last_onset_frame = frame_index

    return OnsetDetectionResult(
        onsets=onsets,
        envelope=envelope,
        adaptive_threshold=adaptive_threshold,
        sample_rate=sr,
        hop_length=hop_length,
        estimated_tempo=float(estimated_tempo),
        tempo_candidates=candidates,
    )


def refine_onsets(
    audio: Tuple[np.ndarray, int],
    onsets: Iterable[DetectedOnset],
    window_ms: float = 28.0,
) -> List[DetectedOnset]:
    """Snap onsets to the nearest energy peak inside a small window."""

    audio_data, sr = audio
    window_samples = max(1, int(window_ms * sr / 1000.0))

    onset_list = list(onsets)
    raw_times = np.array([onset.time for onset in onset_list], dtype=float)
    min_spacing = 0.0
    if raw_times.size > 1:
        min_spacing = 0.95 * float(np.min(np.diff(raw_times)))

    refined: List[DetectedOnset] = []
    last_time = -np.inf
    for onset in onsets:
        centre = int(onset.time * sr)
        start = max(0, centre - window_samples // 2)
        end = min(len(audio_data), centre + window_samples // 2)

        window = audio_data[start:end]
        if len(window) == 0:
            refined.append(onset)
            continue

        local_max_idx = int(np.argmax(np.abs(window)))
        refined_time = (start + local_max_idx) / sr
        if min_spacing > 0.0 and last_time > -np.inf:
            min_allowed = last_time + min_spacing
            window_end_time = (end - 1) / sr if end > 0 else 0.0
            refined_time = max(refined_time, min_allowed)
            refined_time = min(refined_time, window_end_time)
        refined.append(dataclasses.replace(onset, time=float(refined_time)))
        last_time = refined_time

    return refined
