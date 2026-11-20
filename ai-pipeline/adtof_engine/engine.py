"""Audio file -> BeatSight .bsm using stereo Demucs separation and ADTOF Frame_RNN.

Measured configuration (docs/TRANSCRIPTION_ROUTE_2026-10-16.md): stereo input
peak-normalized by its mono downmix, htdemucs_ft drum separation averaged to
mono, madmom-equivalent frontend, ADTOF Frame_RNN, madmom peak picking.
Detected note times are never quantized. A forced tempo/offset from the desktop
only sets grid metadata; it never moves notes.
"""
from __future__ import annotations

import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import FAMILIES
from . import decoder, frontend
from .model import WEIGHTS_FILENAME, WEIGHTS_SHA256, load_model, sha256

# The native schema has detailed components but no broad hi-hat/tom/cymbal IDs.
# These are display proxies for the model's broad families, not articulations.
NATIVE_COMPONENTS = {"kick": "kick", "snare": "snare", "tom": "tom_mid",
                     "hihat": "hihat_closed", "cymbal": "crash"}
SEPARATION_MODEL = "htdemucs_ft"
ENGINE_VERSION = "adtof-frame-rnn-1"
FINE_ENGINE_VERSION = "beatsight-16class-4"  # -2: one hi-hat event per 20 ms; -3: also one ride/bell/crash event; -4: no "percussion" notes
_DEFAULT_VELOCITY = 0.8


def default_weights_path() -> Path:
    return Path(__file__).resolve().parents[1] / "models" / "adtof" / WEIGHTS_FILENAME


def _load_audio(path: Path, start_time: Optional[float], end_time: Optional[float]):
    import librosa

    offset = max(0.0, float(start_time or 0.0))
    duration = None
    if end_time is not None and end_time > 0:
        duration = float(end_time) - offset
        if duration <= 0:
            raise ValueError("--end-time must be after --start-time")
    audio, sr = librosa.load(str(path), sr=frontend.SAMPLE_RATE, mono=False,
                             offset=offset, duration=duration)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    audio = audio[:2].astype(np.float32)
    if audio.shape[1] == 0 or not np.isfinite(audio).all():
        raise ValueError("Audio is empty or contains invalid samples")
    peak = float(np.abs(librosa.to_mono(audio)).max())
    if peak <= 1e-10:
        raise ValueError("Audio is silent; there are no drums to transcribe")
    return audio / peak, sr, offset


def _drum_signal(stereo: np.ndarray, sr: int, separate: bool, log: Callable[[str], None]):
    if not separate:
        return np.mean(stereo, axis=0).astype(np.float32), {"separated": False}
    import random

    import torch
    from separation.demucs_separator import separate_drums

    # Demucs shifts the input by a random offset. Seed it exactly as the audited runs did
    # so the same audio always yields the same chart.
    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    started = time.perf_counter()
    stem, stem_sr = separate_drums((stereo, sr), model_name=SEPARATION_MODEL)
    stem = np.asarray(stem, dtype=np.float32)
    if stem_sr != sr or stem.ndim != 1 or len(stem) != stereo.shape[1] or not np.isfinite(stem).all():
        raise RuntimeError("Drum separation returned an invalid stem")
    seconds = time.perf_counter() - started
    log(f"[adtof] separation {SEPARATION_MODEL} took {seconds:.1f}s")
    return stem, {"separated": True, "model": SEPARATION_MODEL, "seconds": round(seconds, 3)}


def _grid(stem: np.ndarray, sr: int, forced_bpm, forced_offset):
    """Tempo/offset are display grid metadata only."""
    if forced_bpm is not None and math.isfinite(forced_bpm) and forced_bpm > 0:
        bpm, source = float(forced_bpm), "forced"
    else:
        import librosa

        tempo, _ = librosa.beat.beat_track(y=stem, sr=sr)
        bpm = float(np.asarray(tempo).reshape(-1)[0])
        source = "estimated"
        if not 20 <= bpm <= 400:
            bpm, source = 120.0, "default"
    offset_ms = 0
    if forced_offset is not None and math.isfinite(forced_offset):
        offset_ms = int(round(forced_offset * 1000.0))
    return bpm, offset_ms, source


def _chart(events, *, input_path: Path, duration_ms: int, sr: int, bpm: float, offset_ms: int, metadata,
           fine: Optional[dict] = None):
    """``events`` carry ADTOF family names, or final component IDs when ``fine`` is given."""
    now = datetime.now(timezone.utc).isoformat()
    if fine:
        from .fine import FINE_COMPONENTS
        names = {c: c for c in FINE_COMPONENTS.values()}
        creator, tags, version = "BeatSight AI (16-class, experimental)", ["ai-generated", "beatsight-16class", "experimental"], FINE_ENGINE_VERSION
        description = ("Automatic transcription by an experimental BeatSight 16-class model fine-tuned from ADTOF "
                       "(cymbal, hi-hat articulation and tom detail); at most one hi-hat event and one "
                       "ride/ride-bell/crash event per 20 ms; no 'percussion' notes (no chart lane). "
                       "Velocity is a display default. BPM/offset are "
                       "grid metadata; notes keep detected times. Derived from ADTOF Frame_RNN weights "
                       "(Zehren et al.), CC BY-NC-SA 4.0; personal use only.")
    else:
        names = NATIVE_COMPONENTS
        creator, tags, version = "BeatSight AI (ADTOF)", ["ai-generated", "adtof", "broad-families"], ENGINE_VERSION
        description = ("Automatic ADTOF transcription. Broad drum families only: hihat_closed, "
                       "tom_mid and crash stand for any hi-hat, tom and cymbal. Velocity is a "
                       "display default. BPM/offset are grid metadata; notes keep detected times. "
                       "Model: ADTOF Frame_RNN (Zehren et al.), CC BY-NC-SA 4.0.")
    components = list(dict.fromkeys(names[e["component"]] for e in events)) if fine else list(dict.fromkeys(names.values()))
    return {
        "version": "1.1.0",
        "metadata": {
            "title": str(metadata.get("title") or input_path.stem),
            "artist": str(metadata.get("artist") or "Unknown Artist"),
            "creator": creator,
            "difficulty": 0,
            "beatmapId": str(uuid.uuid4()),
            "createdAt": now,
            "modifiedAt": now,
            "tags": tags,
            "description": description,
        },
        "audio": {"filename": input_path.name, "hash": "sha256:" + sha256(input_path),
                  "duration": duration_ms, "sampleRate": sr},
        "timing": {"bpm": bpm, "offset": offset_ms, "timeSignature": "4/4",
                   "timingPoints": [{"time": offset_ms, "bpm": bpm, "timeSignature": "4/4"}]},
        "drumKit": {"components": components, "layout": "custom"},
        "hitObjects": [{"time": int(round(e["time"])), "component": names[e["component"]],
                        "velocity": _DEFAULT_VELOCITY} for e in events],
        "editor": {"aiGenerationMetadata": {"modelVersion": version,
                                            "processedAt": now, "manualEdits": False}},
    }


def transcribe(input_path, output_path, *, debug_path=None, separate=True, start_time=None,
               end_time=None, forced_bpm=None, forced_offset=None, weights_path=None,
               fine_model_dir=None, log: Callable[[str], None] = print) -> dict:
    """Write a .bsm for ``input_path``; return a summary. Raises on any failure.

    ``fine_model_dir`` selects an experimental 16-class model (adtof_engine.fine) instead of ADTOF.
    """
    import torch

    input_path, output_path = Path(input_path), Path(output_path)
    weights_path = Path(weights_path) if weights_path else default_weights_path()
    started = time.perf_counter()

    log("Step 1/4: Loading audio...")
    fine_info = None
    if fine_model_dir:
        from .fine import load_fine_model
        model, fine_thresholds, fine_info = load_fine_model(fine_model_dir)
    else:
        model = load_model(weights_path)
    stereo, sr, offset_s = _load_audio(input_path, start_time, end_time)
    duration_ms = int(round(stereo.shape[1] / sr * 1000))

    log("Step 2/4: Separating drums..." if separate else "Step 2/4: Using full mix (separation off)...")
    stem, separation = _drum_signal(stereo, sr, separate, log)

    log("Step 3/4: Transcribing drums (BeatSight 16-class, experimental)..." if fine_info else "Step 3/4: Transcribing drums (ADTOF)...")
    with torch.no_grad():
        activations = model(torch.from_numpy(frontend.features(stem))[None])[0].numpy()
    if fine_info:
        from .fine import decode_fine
        events = decode_fine(activations, fine_thresholds)
    else:
        events = decoder.decode(activations)
    if offset_s:
        for e in events:
            e["time"] += offset_s * 1000.0
    if not events:
        raise RuntimeError("No drum hits were detected in this audio.")

    log("Step 4/4: Writing beatmap...")
    bpm, offset_ms, grid_source = _grid(stem, sr, forced_bpm, forced_offset)
    try:
        from pipeline.metadata_detection import detect_song_metadata
        metadata = detect_song_metadata(str(input_path)) or {}
    except Exception:  # metadata is optional; the desktop enriches it afterwards
        metadata = {}
    chart = _chart(events, input_path=input_path, duration_ms=duration_ms + int(round(offset_s * 1000)),
                   sr=sr, bpm=bpm, offset_ms=offset_ms, metadata=metadata, fine=fine_info)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(chart, indent=2, allow_nan=False), encoding="utf-8")

    if fine_info:
        counts = {c: sum(e["component"] == c for e in events) for c in dict.fromkeys(e["component"] for e in events)}
        from .fine import CYMBAL_COMBINE_CLASSES, CYMBAL_COMBINE_SECONDS, DROPPED_CLASSES, HH_COMBINE_SECONDS
        identity = {"engine": "beatsight-16class", "engine_version": FINE_ENGINE_VERSION, "model": fine_info,
                    "weights_sha256": fine_info["weights_sha256"], "thresholds": fine_info["thresholds"],
                    "hh_combine_seconds": HH_COMBINE_SECONDS, "cymbal_combine_seconds": CYMBAL_COMBINE_SECONDS,
                    "cymbal_combine_classes": list(CYMBAL_COMBINE_CLASSES), "dropped_classes": list(DROPPED_CLASSES)}
    else:
        counts = {family: sum(e["component"] == family for e in events) for family in FAMILIES}
        identity = {"engine": "adtof", "engine_version": ENGINE_VERSION, "weights_sha256": WEIGHTS_SHA256,
                    "thresholds": list(decoder.THRESHOLDS)}
    summary = {
        **identity,
        "separation": separation, "frames": int(activations.shape[0]), "fps": frontend.FPS,
        "family_counts": counts, "notes": len(events),
        "grid": {"bpm": bpm, "offset_ms": offset_ms, "source": grid_source, "quantized": False},
        "window_seconds": {"start": offset_s, "duration": stereo.shape[1] / sr},
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    if debug_path:
        Path(debug_path).write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    log(f"[{identity['engine']}] notes={len(events)} " + " ".join(f"{k}={v}" for k, v in counts.items()))
    log(f"Complete: wrote {output_path.name}")
    return summary
