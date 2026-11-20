"""Score exported events with one-to-one family and timing diagnostics.

Assignment first maximizes match count within tolerance, then minimizes absolute
timing error. It does not shift, quantize, or otherwise adjust predictions.
"""
from collections import defaultdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from evaluate_mdb import drum_family, scores


def match_timing(reference, predicted, tolerance=0.05):
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Tolerance must be finite and nonnegative')
    ref = np.sort(np.asarray(reference, dtype=float))
    pred = np.sort(np.asarray(predicted, dtype=float))
    if not np.isfinite(ref).all() or not np.isfinite(pred).all():
        raise ValueError('Nonfinite event time')
    errors = []
    if len(ref) and len(pred):
        delta = pred[None, :] - ref[:, None]
        valid = np.abs(delta) <= tolerance + 1e-9
        # Each row can choose a private unmatched slot. The unmatched penalty
        # exceeds the entire possible timing cost, ensuring maximum cardinality.
        penalty = (len(ref) + 1) * (tolerance + 1)
        costs = np.full((len(ref), len(pred) + len(ref)), penalty)
        costs[:, :len(pred)] = np.where(valid, np.abs(delta), 2 * penalty)
        row, col = linear_sum_assignment(costs)
        errors = [float(delta[r, c]) for r, c in zip(row, col)
                  if c < len(pred) and valid[r, c]]
    return {**scores(len(errors), len(pred) - len(errors), len(ref) - len(errors)),
            'signed_errors_seconds': errors}


def timing_summary(errors):
    values = np.asarray(errors, dtype=float) * 1000
    if not len(values):
        return {'matched_events': 0, 'median_absolute_ms': None,
                'p90_absolute_ms': None, 'median_signed_ms': None}
    return {'matched_events': len(values),
            'median_absolute_ms': float(np.median(np.abs(values))),
            'p90_absolute_ms': float(np.percentile(np.abs(values), 90)),
            'median_signed_ms': float(np.median(values))}


def evaluate_timing(chart, reference, tolerance=0.05):
    predictions = defaultdict(list)
    for event in chart['hitObjects']:
        predictions[drum_family(event['component'])].append(event['time'] / 1000)
    by_family = {label: match_timing(reference.get(label, []), predictions[label], tolerance)
                 for label in sorted(reference.keys() | predictions.keys())}
    errors = [value for row in by_family.values() for value in row['signed_errors_seconds']]
    totals = {key: sum(row[key] for row in by_family.values()) for key in ('tp', 'fp', 'fn')}
    return {'tolerance_seconds': tolerance, 'micro': scores(**totals),
            'timing': timing_summary(errors), 'by_family': by_family}
