"""ADTOF Frame_RNN input features for mono float32 PCM at 44.1 kHz.

Matches the madmom v0.16.1 float-input path used by ADTOF: 440 Hz anchored
logarithmic filters (12 bands per octave, 20 Hz-20 kHz), centered 2048-sample
Hann windows, 100 fps, normal end handling, no Nyquist bin, and
log10(1 + filtered magnitude). Verified against the primary functions in
docs/ADTOF_FRONTEND_CONFORMANCE_2026-10-15.md.
"""
from functools import lru_cache

import numpy as np
from scipy import fftpack

SAMPLE_RATE = 44100
FPS = 100
_FRAME_SIZE = 2048
_HOP = SAMPLE_RATE // FPS


@lru_cache(maxsize=1)
def filterbank():
    fft_hz = np.fft.fftfreq(_FRAME_SIZE, 1 / SAMPLE_RATE)[:_FRAME_SIZE // 2]
    semitones = np.arange(np.floor(np.log2(20 / 440) * 12),
                          np.ceil(np.log2(20000 / 440) * 12))
    hz = 440 * 2 ** (semitones / 12)
    hz = hz[(hz >= 20) & (hz <= 20000)]
    bins = np.clip(np.searchsorted(fft_hz, hz), 1, len(fft_hz) - 1)
    bins -= hz - fft_hz[bins - 1] < fft_hz[bins] - hz
    bins = np.unique(bins)
    bank = np.zeros((len(fft_hz), len(bins) - 2), dtype=np.float32)
    for i, (left, center, right) in enumerate(zip(bins, bins[1:], bins[2:])):
        # Build and normalize each triangular filter before inserting it.
        values = np.concatenate((np.linspace(0, 1, center - left, endpoint=False),
                                 np.linspace(1, 0, right - center, endpoint=False))).astype(np.float32)
        values /= np.sum(values)
        bank[left:right, i] = values
    bank.flags.writeable = False
    return bank


def _frames(audio):
    padded = np.pad(audio, (_FRAME_SIZE // 2, _FRAME_SIZE // 2))
    frames = np.lib.stride_tricks.sliding_window_view(padded, _FRAME_SIZE)[::_HOP]
    # madmom normal end handling: no frame centered at exactly len(audio).
    return frames[:(len(audio) + _HOP - 1) // _HOP]


def features(audio):
    """Return (frames, 84, 1) float32 features for mono float32 PCM at 44.1 kHz."""
    audio = np.asarray(audio)
    if audio.dtype != np.float32 or audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Expected nonempty finite mono float32 PCM at 44100 Hz")
    spectrum = fftpack.fft(_frames(audio) * np.hanning(_FRAME_SIZE), axis=1)[:, :_FRAME_SIZE // 2]
    filtered = np.dot(np.abs(spectrum.astype(np.complex64)), filterbank())
    filtered += 1
    np.log10(filtered, out=filtered)
    return filtered[:, :, None]
