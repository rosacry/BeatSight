"""Fixed ADTOF frontend for already-decoded mono float32 PCM at 44.1 kHz.

Matches the reviewed madmom v0.16.1 float-input path used by ADTOF Frame_RNN:
440 Hz anchored logarithmic filters, centered 2048-sample Hann windows, 100 fps,
normal end handling, no Nyquist bin, log10(1 + normalized filtered magnitude).
File decoding, integer PCM scaling, resampling and model conversion are outside
this adapter's contract. It does not change the pinned port or application.
"""
from functools import lru_cache

import numpy as np
from scipy import fftpack


@lru_cache(maxsize=1)
def filterbank():
    fft_hz = np.fft.fftfreq(2048, 1 / 44100)[:1024]
    semitones = np.arange(np.floor(np.log2(20 / 440) * 12),
                          np.ceil(np.log2(20000 / 440) * 12))
    hz = 440 * 2 ** (semitones / 12)
    hz = hz[(hz >= 20) & (hz <= 20000)]
    bins = np.clip(np.searchsorted(fft_hz, hz), 1, len(fft_hz) - 1)
    bins -= hz - fft_hz[bins - 1] < fft_hz[bins] - hz
    bins = np.unique(bins)
    bank = np.zeros((1024, len(bins) - 2), dtype=np.float32)
    for i, (left, center, right) in enumerate(zip(bins, bins[1:], bins[2:])):
        # Construct and normalize each compact filter before inserting it.
        values = np.concatenate((np.linspace(0, 1, center-left, endpoint=False),
                                 np.linspace(1, 0, right-center, endpoint=False))).astype(np.float32)
        values /= np.sum(values)
        bank[left:right, i] = values
    bank.flags.writeable = False
    return bank


def frame_audio(audio):
    audio = np.asarray(audio)
    if audio.dtype != np.float32 or audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
        raise ValueError('Expected nonempty finite mono float32 PCM at 44100 Hz')
    padded = np.pad(audio, (1024, 1024))
    frames = np.lib.stride_tricks.sliding_window_view(padded, 2048)[::441]
    # madmom normal end handling: no frame centered at exactly len(audio).
    return frames[:(len(audio) + 440) // 441]


def magnitude(audio):
    frames = frame_audio(audio)
    spectrum = fftpack.fft(frames * np.hanning(2048), axis=1)[:, :1024]
    return np.abs(spectrum.astype(np.complex64))


def features(audio):
    filtered = np.dot(magnitude(audio), filterbank())
    filtered += 1
    np.log10(filtered, out=filtered)
    return filtered[:, :, None]
