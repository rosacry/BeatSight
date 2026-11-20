"""Experimental 16-class models fine-tuned from ADTOF (BeatSight's own training, 2026-10).

A model directory holds ``best.pt`` (a state dict under "model", Frame_RNN layers with a
16-way output) and ``thresholds.json`` (per-class peak-picking thresholds chosen on
validation data). Off by default: the engine uses it only when a directory is passed.
Weights derive from CC BY-NC-SA 4.0 ADTOF weights: personal/study use, never published.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .decoder import _FPS, pick_peaks
from .model import FrameRnn, sha256

FINE_CLASSES = ("KD", "SD", "SS", "HHC", "HHP", "HHO", "HT", "MT", "LT", "RD", "RB", "CR", "CH", "SP", "CB", "OT")
HIHAT_CLASSES = ("HHC", "HHP", "HHO")
# A hi-hat is one instrument, so one stroke cannot be closed, pedal and open at once. ADTOF's single
# hi-hat output keeps one event per 20 ms; the three hi-hat classes share that rule here. Chosen on
# validation data only (docs/TIERB_DROP_DIAGNOSIS_2026-10-23.md, rule hh_family_combine W20).
HH_COMBINE_SECONDS = 0.02
# Ride, ride bell and crash get the same rule: the model fired a ride with 66% of its crashes where charts
# have two cymbals at once 0.06% of the time. China and splash stay separate (the user hears too few Chinas).
# Rule C20-ridecrash, chosen with the user (docs/CYMBAL_GHOST_RULES_2026-10-24.md).
CYMBAL_COMBINE_CLASSES = ("RD", "RB", "CR")
CYMBAL_COMBINE_SECONDS = 0.02
# Classes the model predicts but charts do not show. "Percussion" (OT) has no lane in rhythm-game charts and
# on recorded songs fires mostly on hi-hats and rides (eval tier B: 2,621 false vs 32 true hits for the
# first 16-class model). User decision 2026-11-06: leave it out of charts; the model keeps the output.
DROPPED_CLASSES = ("OT",)
# BeatSight component IDs (desktop editor vocabulary).
FINE_COMPONENTS = {"KD": "kick", "SD": "snare", "SS": "cross_stick", "HHC": "hihat_closed", "HHP": "hihat_pedal",
                   "HHO": "hihat_open", "HT": "tom_high", "MT": "tom_mid", "LT": "tom_low", "RD": "ride",
                   "RB": "ride_bell", "CR": "crash", "CH": "china", "SP": "splash", "CB": "cowbell", "OT": "percussion"}


class FineFrameRnn(FrameRnn):
    """Frame_RNN with a 16-class output layer (same layer names as the training code)."""

    def __init__(self):
        super().__init__()
        self.output_layer = nn.Linear(120, len(FINE_CLASSES))


def load_fine_model(model_dir):
    """Return (model, thresholds array, info). Raises with a clear message on any mismatch."""
    model_dir = Path(model_dir)
    weights, th_path = model_dir / "best.pt", model_dir / "thresholds.json"
    for p in (weights, th_path):
        if not p.is_file():
            raise FileNotFoundError(f"16-class model file missing: {p}")
    saved = torch.load(weights, map_location="cpu", weights_only=False)
    model = FineFrameRnn()
    model.load_state_dict(saved["model"] if isinstance(saved, dict) and "model" in saved else saved, strict=True)
    model.eval()
    raw = json.loads(th_path.read_text(encoding="utf-8"))
    if set(raw) != set(FINE_CLASSES):
        raise ValueError(f"thresholds.json must list exactly {FINE_CLASSES}")
    thresholds = np.array([float(raw[c]["threshold"] if isinstance(raw[c], dict) else raw[c]) for c in FINE_CLASSES])
    if not np.isfinite(thresholds).all() or (thresholds <= 0).any():
        raise ValueError("thresholds must be finite and positive")
    info = {"model_dir": str(model_dir), "weights_sha256": sha256(weights), "thresholds_sha256": sha256(th_path),
            "thresholds": dict(zip(FINE_CLASSES, map(float, thresholds)))}
    return model, thresholds, info


def combine_hihats(peaks, values, window=HH_COMBINE_SECONDS):
    """Merge hi-hat peaks of any hi-hat class within ``window`` s of the retained left peak."""
    return combine_classes(peaks, values, HIHAT_CLASSES, window)


def combine_cymbals(peaks, values, window=CYMBAL_COMBINE_SECONDS):
    """Merge ride, ride-bell and crash peaks within ``window`` s of the retained left peak."""
    return combine_classes(peaks, values, CYMBAL_COMBINE_CLASSES, window)


def combine_classes(peaks, values, classes, window):
    """Merge peaks of the given classes within ``window`` s of the retained left peak.

    The merged event keeps the left time (the decoder's own left-retention rule) and the class whose
    activation at its own peak frame is highest. Other classes are returned unchanged.
    """
    out = {c: ts for c, ts in peaks.items() if c not in classes}
    out.update({c: [] for c in classes})
    last = len(values) - 1
    pooled = sorted((t, float(values[min(int(round(t * _FPS)), last), FINE_CLASSES.index(c)]), c)
                    for c in classes for t in peaks[c])
    current = None  # [left time, best activation, best class]
    for t, strength, c in pooled:
        if current is not None and t - current[0] <= window + 1e-12:
            if strength > current[1]:
                current[1], current[2] = strength, c
        else:
            if current is not None:
                out[current[2]].append(current[0])
            current = [t, strength, c]
    if current is not None:
        out[current[2]].append(current[0])
    return out


def decode_fine(activations, thresholds, hh_combine_seconds=HH_COMBINE_SECONDS,
                cymbal_combine_seconds=CYMBAL_COMBINE_SECONDS, drop_classes=DROPPED_CLASSES):
    """(frames, 16) activations -> time-sorted [{'time': ms, 'component': BeatSight component}].

    ``hh_combine_seconds=None`` / ``cymbal_combine_seconds=None`` disable the hi-hat / cymbal rule;
    ``drop_classes=()`` keeps every class; all three off is plain per-class peak picking.
    """
    values = np.asarray(activations, dtype=np.float32)
    if values.ndim == 3 and values.shape[0] == 1:
        values = values[0]
    if values.ndim != 2 or values.shape[1] != len(FINE_CLASSES) or not np.isfinite(values).all():
        raise ValueError("Expected finite (frames, 16) activations")
    peaks = {c: pick_peaks(values[:, i], float(thresholds[i])) for i, c in enumerate(FINE_CLASSES)}
    if hh_combine_seconds is not None:
        peaks = combine_hihats(peaks, values, hh_combine_seconds)
    if cymbal_combine_seconds is not None:
        peaks = combine_cymbals(peaks, values, cymbal_combine_seconds)
    events = [{"time": t * 1000, "component": FINE_COMPONENTS[c]} for c in FINE_CLASSES if c not in drop_classes
              for t in peaks[c]]
    return sorted(events, key=lambda e: (e["time"], e["component"]))
