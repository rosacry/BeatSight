"""Peak picking matching madmom v0.16.1 as configured by ADTOF.

madmom features/onsets.py peak_picking and utils combine_events(..., 'left') with
ADTOF model/peakPicking.py parameters: no smoothing, 100 fps, 100/10 ms moving
average, 20/10 ms local maximum, 20 ms combine. Verified on 1,000 synthetic cases
and seven saved charts (docs/MDB_RESIDUAL_INPUT_AND_DECODER_AUDIT_2026-10-15.md).
"""
import numpy as np
from scipy.ndimage import maximum_filter, uniform_filter

from . import FAMILIES

# Frame_RNN output order and per-class thresholds (kick, snare, tom, hi-hat, cymbal).
THRESHOLDS = (0.22, 0.24, 0.32, 0.22, 0.30)
_FPS = 100
_COMBINE_SECONDS = 0.02


def pick_peaks(values, threshold):
    """Return onset times in seconds for one class activation curve."""
    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("Expected finite one-dimensional activations")
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("Expected a finite positive threshold")
    if len(values) == 0:
        return []
    # Zero padding; keep raw activation strengths of frames above the moving average.
    average = uniform_filter(values, size=12, mode="constant", origin=4)
    detections = values * (values >= average + threshold)
    local_max = maximum_filter(detections, size=4, mode="constant", origin=0)
    frames = np.flatnonzero(detections * (detections == local_max))
    kept = []
    for t in frames.astype(float) / _FPS:
        # Compare with the retained left event, not the previous member of a chain.
        if not kept or t - kept[-1] > _COMBINE_SECONDS + 1e-12:
            kept.append(float(t))
    return kept


def decode(activations):
    """Decode (frames, 5) activations to time-sorted [{'time': ms, 'component': family}]."""
    values = np.asarray(activations, dtype=np.float32)
    if values.ndim == 3 and values.shape[0] == 1:
        values = values[0]
    if values.ndim != 2 or values.shape[1] != len(FAMILIES) or not np.isfinite(values).all():
        raise ValueError("Expected finite (frames, 5) activations")
    events = [{"time": t * 1000, "component": family}
              for i, family in enumerate(FAMILIES)
              for t in pick_peaks(values[:, i], THRESHOLDS[i])]
    return sorted(events, key=lambda e: e["time"])
