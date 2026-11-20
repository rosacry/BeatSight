"""Recovery-only decoder matching the reviewed madmom v0.16.1 configuration.

Primary algorithm: CPJKU/madmom v0.16.1 features/onsets.py peak_picking and
utils/__init__.py combine_events(..., 'left'); ADTOF model/peakPicking.py parameters.
No smoothing; 100 fps; 100/10 ms average, 20/10 ms maximum, 20 ms combine.
This does not modify the pinned PyTorch checkout, historical exports or app defaults.
"""
import numpy as np
from scipy.ndimage import maximum_filter, uniform_filter

from evaluate_adtof import FAMILY_COMPONENTS

LABELS = [35, 38, 47, 42, 49]
THRESHOLDS = [.22, .24, .32, .22, .30]


def pick_reference(values, threshold):
    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError('Expected finite one-dimensional activations')
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError('Expected a finite positive threshold')
    if len(values) == 0:
        return []
    # Use zero padding and masked raw activation strengths, not contrast maxima.
    average = uniform_filter(values, size=12, mode='constant', origin=4)
    detections = values * (values >= average + threshold)
    local_max = maximum_filter(detections, size=4, mode='constant', origin=0)
    frames = np.flatnonzero(detections * (detections == local_max))
    times = frames.astype(float) / 100
    kept = []
    for t in times:
        # Compare to the retained left event, not the previous member of a chain.
        if not kept or t-kept[-1] > .02+1e-12:
            kept.append(float(t))
    return kept


def decode_activations(activations):
    values = np.asarray(activations, dtype=np.float32)
    if values.ndim == 3 and values.shape[0] == 1:
        values = values[0]
    if values.ndim != 2 or values.shape[1] != 5 or not np.isfinite(values).all():
        raise ValueError('Expected finite (frames, 5) or (1, frames, 5) activations')
    return {'hitObjects': sorted([
        {'time': t*1000, 'component': FAMILY_COMPONENTS[label]}
        for i,label in enumerate(LABELS)
        for t in pick_reference(values[:,i], THRESHOLDS[i])], key=lambda e:e['time'])}
