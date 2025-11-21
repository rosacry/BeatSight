"""
Beatmap generation from classified drum hits
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Sequence, Tuple
from datetime import datetime
import hashlib
import math

import librosa
import numpy as np


LANE_DEFAULT = 4

COMPONENT_ALIASES: Dict[str, str] = {
    "hi-hat": "hihat_closed",
    "hi_hat": "hihat_closed",
    "closed_hat": "hihat_closed",
    "open_hat": "hihat_open",
    "ride_cymbal": "ride",
    "ridecymbal": "ride",
    "bass_drum": "kick",
    "bass": "kick",
    "floor_tom": "tom_low",
    "rack_tom": "tom_high",
}

COMPONENT_LANE_MAP: Dict[str, int] = {
    "kick": 3,
    "snare": 1,
    "snare_center": 1,
    "snare_rimshot": 1,
    "snare_cross_stick": 1,
    "snare_off": 1,
    "rim": 1,
    "rimshot": 1,
    "sidestick": 1,
    "clap": 1,
    "ghost": 1,
    "hihat": 5,
    "hihat_closed": 5,
    "hihat_open": 5,
    "hihat_half": 5,
    "hihat_choke": 5,
    "hihat_splash": 5,
    "hihat_pedal": 0,
    "hihat_foot": 0,
    "tom": 4,
    "tom_high": 2,
    "tom_mid": 4,
    "tom_low": 4,
    "tom_floor": 4,
    "floor_tom": 4,
    "ride": 6,
    "ride_bow": 6,
    "ride_bell": 6,
    "ride_edge": 6,
    "crash": 6,
    "crash1": 6,
    "crash_1": 6,
    "crash2": 0,
    "crash_2": 0,
    "china": 6,
    "splash": 6,
    "stack": 6,
    "cowbell": 0,
    "tambourine": 0,
    "shaker": 0,
    "percussion": 0,
    "perc": 0,
}


def _is_cymbal_component(component: str) -> bool:
    comp = (component or "").lower()
    return any(token in comp for token in ("crash", "ride", "china", "splash", "stack", "cym"))


def _is_tom_component(component: str) -> bool:
    comp = (component or "").lower()
    return "tom" in comp or any(token in comp for token in ("rack", "floor"))


def _resolve_lane(component: str) -> int:
    comp = (component or "").strip().lower()
    if not comp:
        return LANE_DEFAULT

    comp = COMPONENT_ALIASES.get(comp, comp)

    if comp in COMPONENT_LANE_MAP:
        return COMPONENT_LANE_MAP[comp]

    if "kick" in comp or "bass" in comp:
        return COMPONENT_LANE_MAP.get("kick", 3)

    if any(token in comp for token in ("snare", "rim", "clap", "ghost", "sidestick")):
        return COMPONENT_LANE_MAP.get("snare", 1)

    if "pedal" in comp and "hat" in comp:
        return COMPONENT_LANE_MAP.get("hihat_pedal", 0)

    if "hat" in comp or comp.startswith("hh"):
        return COMPONENT_LANE_MAP.get("hihat_closed", 5)

    if "tom" in comp or "rack" in comp or "floor" in comp:
        if any(token in comp for token in ("high", "upper", "rack", "small")):
            return COMPONENT_LANE_MAP.get("tom_high", 2)
        if any(token in comp for token in ("mid", "middle")):
            return COMPONENT_LANE_MAP.get("tom_mid", 4)
        if any(token in comp for token in ("low", "floor", "floor_tom", "ft")):
            return COMPONENT_LANE_MAP.get("tom_low", 4)
        return COMPONENT_LANE_MAP.get("tom", COMPONENT_LANE_MAP.get("tom_mid", LANE_DEFAULT))

    if any(token in comp for token in ("ride", "crash", "china", "splash", "cym", "bell", "stack")):
        if "crash2" in comp or "left" in comp:
            return COMPONENT_LANE_MAP.get("crash2", 0)
        return COMPONENT_LANE_MAP.get("crash", 6)

    if any(token in comp for token in ("cowbell", "clave", "block", "tamb", "shaker", "perc", "agogo", "wood", "fx")):
        return COMPONENT_LANE_MAP.get("cowbell", 0)

    return LANE_DEFAULT


def calculate_difficulty(hits: List[Dict]) -> float:
    """
    Calculate difficulty rating based on hit patterns.
    
    Factors considered:
    - Density (hits per second)
    - Complexity (variety of drum components)
    - Speed (timing between consecutive hits)
    - Patterns (rolls, polyrhythms)
    
    Returns:
        Difficulty rating (0.0 - 10.0)
    """
    if not hits:
        return 0.0
    
    # Density
    duration = hits[-1]["time"] - hits[0]["time"]
    if duration == 0:
        density = 0
    else:
        density = len(hits) / duration  # hits per second
    
    # Complexity (unique components)
    unique_components = len(set(hit["component"] for hit in hits))
    
    # Speed (average time between hits)
    if len(hits) > 1:
        time_diffs = [hits[i+1]["time"] - hits[i]["time"] for i in range(len(hits)-1)]
        avg_time_diff = sum(time_diffs) / len(time_diffs)
        speed_factor = max(0, 1.0 - avg_time_diff)  # Faster = higher difficulty
    else:
        speed_factor = 0
    
    # Combine factors
    difficulty = (
        min(density * 2.0, 4.0) +  # Density contribution (max 4.0)
        min(unique_components * 0.5, 3.0) +  # Complexity (max 3.0)
        min(speed_factor * 5.0, 3.0)  # Speed (max 3.0)
    )
    
    return min(difficulty, 10.0)


def assign_lanes(hits: List[Dict]) -> List[Dict]:
    """
    Assign visual lanes using the same layout as the LiveInput HUD.

    Heuristics emphasise the centre kick lane and mirrored cymbal/tom placement:
    - Kick drums anchor lane 3 (Space)
    - Snare, rimshot and clap-style hits lean to lane 1 (D)
    - Stick hi-hat strikes sit on lane 5 (K) while pedal splashes use lane 0 (S)
    - High toms prefer lane 2, mid/low toms favour lane 4
    - Cymbals (crash/ride/china) default to lane 6 with alternates fanning to lane 0
    Unknown parts fall back to lane 4 to stay in view without colliding with the kick lane.
    """

    cymbal_last_time = None
    cymbal_last_lane = None
    cymbal_window = 0.45  # seconds window to alternate clustered cymbal hits
    tom_last_time = None
    tom_last_lane = None
    tom_window = 0.35
    cymbal_switches = 0
    tom_switches = 0

    for hit in hits:
        component = hit.get("component", "")
        lane = _resolve_lane(component)

        if _is_cymbal_component(component):
            time = float(hit.get("time", 0) or 0.0)
            if cymbal_last_time is not None and abs(time - cymbal_last_time) <= cymbal_window:
                lane = 0 if cymbal_last_lane == 6 else 6
            else:
                if lane not in (0, 6):
                    lane = 6

            if cymbal_last_lane is not None and lane != cymbal_last_lane:
                cymbal_switches += 1

            cymbal_last_time = time
            cymbal_last_lane = lane
        elif _is_tom_component(component):
            time = float(hit.get("time", 0) or 0.0)
            if tom_last_time is not None and abs(time - tom_last_time) <= tom_window:
                lane = 2 if tom_last_lane == 4 else 4
            else:
                if lane not in (2, 4):
                    lane = 4

            if tom_last_lane is not None and lane != tom_last_lane:
                tom_switches += 1

            tom_last_time = time
            tom_last_lane = lane

        hit["lane"] = lane

    assign_lanes._lane_stats = {  # type: ignore[attr-defined]
        "cymbal_switches": cymbal_switches,
        "tom_switches": tom_switches,
    }

    return hits


def detect_bpm(audio: np.ndarray, sr: int) -> float:
    """Detect BPM of audio using librosa as a coarse estimate."""

    tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)

    if isinstance(tempo, np.ndarray):
        tempo = float(tempo[0]) if len(tempo) > 0 else 120.0

    if not tempo or not math.isfinite(tempo):
        return 120.0

    return float(tempo)


QUANTIZATION_DIVISORS = {
    "quarter": 1,
    "eighth": 2,
    "triplet": 3,
    "sixteenth": 4,
    "thirtysecond": 8,
}


def _resolve_grid(grid: str) -> str:
    key = (grid or "").lower()
    if key in QUANTIZATION_DIVISORS:
        return key
    return "sixteenth"


def _quantization_step(bpm: float, grid: str) -> float:
    divisor = QUANTIZATION_DIVISORS[_resolve_grid(grid)]
    beat_duration = 60.0 / max(bpm, 1e-6)
    return beat_duration / divisor


def _measure_error(times: np.ndarray, snapped: np.ndarray, tolerance: float) -> Tuple[float, float, float]:
    errors = snapped - times
    abs_errors = np.abs(errors)
    within = abs_errors <= tolerance

    coverage = float(np.count_nonzero(within)) / max(len(times), 1)
    mean_error = float(np.mean(abs_errors)) if len(abs_errors) else 0.0
    median_error = float(np.median(abs_errors)) if len(abs_errors) else 0.0
    return coverage, mean_error, median_error


def _optimal_offset(times: np.ndarray, step: float) -> float:
    if len(times) == 0:
        return 0.0

    remainders = np.mod(times, step)
    # Use circular mean with wrap-around to keep offset inside [0, step).
    # If spread is large, fall back to median.
    variance = np.var(remainders)
    if variance < (step * 0.45) ** 2:
        return float(np.median(remainders))

    bins = np.linspace(0, step, num=32, endpoint=False)
    hist, edges = np.histogram(remainders, bins=bins)
    best_bin = int(np.argmax(hist))
    return float(edges[best_bin])


def _quantize_times(times: np.ndarray, bpm: float, grid: str, tolerance: float) -> Dict[str, Any]:
    step = _quantization_step(bpm, grid)
    if step <= 0:
        return {
            "bpm": bpm,
            "grid": grid,
            "quantized": times.copy(),
            "errors": np.zeros_like(times),
            "coverage": 0.0,
            "mean_error": 0.0,
            "median_error": 0.0,
            "offset": 0.0,
        }

    offset = _optimal_offset(times, step)
    snapped = offset + np.round((times - offset) / step) * step
    coverage, mean_error, median_error = _measure_error(times, snapped, tolerance)

    return {
        "bpm": bpm,
        "grid": grid,
        "quantized": snapped,
        "errors": snapped - times,
        "coverage": coverage,
        "mean_error": mean_error,
        "median_error": median_error,
        "offset": offset,
        "step": step,
    }


def _select_best_quantization(
    times: np.ndarray,
    tempo_candidates: Sequence[float],
    grid: str,
    tolerance: float,
    hint_count: int = 0,
) -> Dict[str, Any]:
    evaluated: List[Dict[str, Any]] = []
    for index, tempo in enumerate(tempo_candidates):
        if tempo <= 0 or not math.isfinite(tempo):
            continue
        candidate = _quantize_times(times, tempo, grid, tolerance)
        candidate["_source_index"] = index
        candidate["_is_hint"] = index < hint_count
        bonus = 0.02 if candidate["_is_hint"] else 0.0
        candidate["_score"] = candidate["coverage"] + bonus
        evaluated.append(candidate)

    if not evaluated:
        fallback = _quantize_times(times, 120.0, grid, tolerance)
        fallback["_source_index"] = 0
        fallback["_is_hint"] = False
        fallback["_score"] = fallback["coverage"]
        evaluated.append(fallback)

    evaluated.sort(key=lambda d: (-d["_score"], d["mean_error"], d["_source_index"]))

    best = evaluated[0]
    detection_best = None
    for candidate in evaluated:
        if candidate.get("_is_hint"):
            continue

        if detection_best is None:
            detection_best = candidate
            continue

        current_key = (
            candidate["coverage"],
            -candidate["mean_error"],
            -candidate["_source_index"],
        )
        best_key = (
            detection_best["coverage"],
            -detection_best["mean_error"],
            -detection_best["_source_index"],
        )

        if current_key > best_key:
            detection_best = candidate

    if best.get("_is_hint") and detection_best is not None:
        coverage_gap = detection_best["coverage"] - best["coverage"]
        mean_gap = best["mean_error"] - detection_best["mean_error"]

        fallback_needed = coverage_gap > 0.06 or (best["coverage"] < 0.45 and coverage_gap > 0)
        if not fallback_needed and coverage_gap > 0.03 and mean_gap > 0:
            fallback_needed = True

        if fallback_needed:
            best = detection_best

    candidate_summaries: List[Dict[str, Any]] = []
    for item in evaluated:
        candidate_summaries.append(
            {
                "bpm": round(item["bpm"], 4),
                "coverage": round(item["coverage"], 4),
                "mean_error": round(item["mean_error"], 4),
                "hint": bool(item.get("_is_hint", False)),
                "source_index": int(item.get("_source_index", 0)),
            }
        )
        item.pop("_score", None)
        item.pop("_source_index", None)
        item.pop("_is_hint", None)

    best["candidates"] = candidate_summaries

    return best


def _section_counts(times: Sequence[float], bpm: float, beats_per_section: int = 16) -> List[Dict[str, Any]]:
    if not times:
        return []

    beat_duration = 60.0 / max(bpm, 1e-6)
    section_length = beat_duration * beats_per_section
    sections: Dict[int, List[float]] = {}

    for time in times:
        index = int(time // section_length)
        sections.setdefault(index, []).append(time)

    results: List[Dict[str, Any]] = []
    for index in sorted(sections.keys()):
        start = index * section_length
        end = start + section_length
        segment_times = sections[index]
        density = len(segment_times) / section_length
        results.append(
            {
                "section": index,
                "start": start,
                "end": end,
                "count": len(segment_times),
                "density": density,
            }
        )

    return results


def compute_audio_hash(file_path: str) -> str:
    """
    Compute SHA-256 hash of audio file.
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def _generate_fallback_hits(duration_seconds: float, bpm: float, start_time: float = 0.0) -> List[Dict[str, Any]]:
    """Create a simple metronomic groove when no classified hits are available.
    
    Args:
        duration_seconds: Total duration of audio
        bpm: Tempo in beats per minute
        start_time: When to start generating hits (useful for songs with intros)
    """

    if bpm <= 0:
        bpm = 120.0

    steps_per_beat = 2  # eighth notes by default
    interval = max(60.0 / (bpm * steps_per_beat), 0.12)
    
    # Calculate how many steps to generate from start_time to end
    remaining_duration = duration_seconds - start_time
    total_steps = int(remaining_duration / interval) + 2
    max_hits = max(1, min(total_steps, 2000))

    hits: List[Dict[str, Any]] = []

    # Add an opening crash to mark where drums start (not necessarily at 0)
    if start_time < duration_seconds:
        hits.append({
            "time": start_time,
            "component": "crash",
            "confidence": 0.3,
            "onset_confidence": 0.3,
            "class_confidence": 0.3,
            "fallback": True,
        })

    for step in range(max_hits):
        time = start_time + (step * interval)
        if time >= duration_seconds:
            break

        measure_steps = steps_per_beat * 4
        position_in_measure = step % measure_steps

        if position_in_measure == 0:
            component = "kick"
        elif position_in_measure == steps_per_beat * 2:
            component = "snare"
        elif position_in_measure == steps_per_beat:
            component = "kick"
        else:
            component = "hihat_closed"

        hits.append({
            "time": time,
            "component": component,
            "confidence": 0.4 if component != "hihat_closed" else 0.3,
            "onset_confidence": 0.35,
            "class_confidence": 0.35,
            "fallback": True,
        })

    return hits


def generate_beatmap(
    classified_hits: List[Dict],
    audio_path: str,
    drum_stem_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    analysis_audio: Optional[np.ndarray] = None,
    analysis_sr: Optional[int] = None,
    tempo_candidates: Optional[Sequence[float]] = None,
    tempo_hint_count: int = 0,
    quantization_grid: str = "sixteenth",
    max_snap_error_ms: float = 12.0,
    detection_debug: Optional[Dict[str, Any]] = None,
    forced_bpm: Optional[float] = None,
    forced_offset: Optional[float] = None,
    forced_step: Optional[float] = None,
    force_quantization: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Generate complete .bsm beatmap file.
    
    Args:
        classified_hits: List of classified drum hits
        audio_path: Path to original audio file
        drum_stem_path: Path to isolated drum stem (optional)
    metadata: Additional metadata (creator, title, etc.)
    tempo_hint_count: Number of leading tempo candidates originating from host hints
        
    Returns:
        Tuple containing the beatmap dictionary and auxiliary debug data
    """
    metadata = metadata or {}
    
    # Load audio for analysis
    if analysis_audio is None or analysis_sr is None:
        analysis_audio, analysis_sr = librosa.load(audio_path, sr=44100, mono=True)
    else:
        # Ensure mono and numpy array for downstream calculations
        analysis_audio = np.asarray(analysis_audio)
        if analysis_audio.ndim > 1:
            analysis_audio = librosa.to_mono(analysis_audio)

    if analysis_audio.size == 0:
        raise ValueError("Analysis audio is empty; cannot generate beatmap")

    duration_seconds = len(analysis_audio) / analysis_sr
    duration_ms = int(duration_seconds * 1000)

    # Detect BPM
    bpm_estimate = detect_bpm(analysis_audio, analysis_sr)

    used_fallback = False

    if not classified_hits:
        print("⚠️  WARNING: No confident drum hits detected; generating fallback pattern.")
        print("   This means the AI couldn't detect actual drums in the audio.")
        print("   The beatmap will contain a generic metronomic pattern.")
        print("   Try: 1) Lowering confidence threshold, 2) Checking if audio has drums")
        
        # Try to detect when drums might start by looking for energy increase
        # Calculate RMS energy over time
        frame_length = 2048
        hop_length = 512
        rms = librosa.feature.rms(y=analysis_audio, frame_length=frame_length, hop_length=hop_length)[0]

        # Find first significant energy increase (drums starting)
        rms_threshold = np.percentile(rms, 25)  # 25th percentile of energy
        drum_start = 0.0
        for i, energy in enumerate(rms):
            if energy > rms_threshold * 2:  # Energy doubles from baseline
                drum_start = librosa.frames_to_time(i, sr=analysis_sr, hop_length=hop_length)
                print(f"   Detected potential drum start at {drum_start:.1f}s")
                break

        classified_hits = _generate_fallback_hits(duration_seconds, bpm_estimate, start_time=drum_start)
        used_fallback = True

    # Assign lanes
    hits_with_lanes = assign_lanes(classified_hits)
    lane_stats = getattr(assign_lanes, "_lane_stats", {"cymbal_switches": 0, "tom_switches": 0})

    times_seconds = np.array([hit["time"] for hit in hits_with_lanes], dtype=float)
    tolerance = max_snap_error_ms / 1000.0
    tempo_candidates = tempo_candidates or [bpm_estimate, bpm_estimate * 2, bpm_estimate / 2]
    hint_count = max(0, min(tempo_hint_count, len(tempo_candidates)))
    quantization_result = _select_best_quantization(times_seconds, tempo_candidates, quantization_grid, tolerance, hint_count)

    applied_bpm = quantization_result["bpm"]
    applied_step = quantization_result.get("step") or _quantization_step(applied_bpm, quantization_grid)
    applied_offset = quantization_result.get("offset", 0.0)

    overrides_applied = False

    if forced_bpm is not None and forced_bpm > 0:
        applied_bpm = float(forced_bpm)
        applied_step = _quantization_step(applied_bpm, quantization_grid)
        applied_offset = _optimal_offset(times_seconds, applied_step)
        overrides_applied = True

    if forced_step is not None and forced_step > 0:
        applied_step = float(forced_step)
        overrides_applied = True
        if forced_offset is None or not math.isfinite(forced_offset):
            applied_offset = _optimal_offset(times_seconds, applied_step)

    if forced_offset is not None and math.isfinite(forced_offset):
        applied_offset = float(forced_offset)
        overrides_applied = True

    if applied_step <= 0:
        applied_step = max(60.0 / max(applied_bpm, 1e-6) / QUANTIZATION_DIVISORS[_resolve_grid(quantization_grid)], 1e-3)

    if force_quantization:
        overrides_applied = True

    if overrides_applied:
        snapped_times = applied_offset + np.round((times_seconds - applied_offset) / applied_step) * applied_step
        errors = snapped_times - times_seconds
        coverage, mean_error, median_error = _measure_error(times_seconds, snapped_times, tolerance)

        quantization_result.update(
            {
                "bpm": applied_bpm,
                "offset": applied_offset,
                "step": applied_step,
                "quantized": snapped_times,
                "errors": errors,
                "coverage": coverage,
                "mean_error": mean_error,
                "median_error": median_error,
                "forced": True,
            }
        )
    else:
        snapped_times = quantization_result["quantized"]
        errors = quantization_result["errors"]

    within = np.abs(errors) <= tolerance

    for hit, snapped, err, is_within in zip(hits_with_lanes, snapped_times, errors, within):
        if is_within:
            hit["time"] = float(snapped)
        hit["quantization_error"] = float(err)
    
    # Convert to hitObjects format
    hit_objects = []
    for hit in hits_with_lanes:
        hit_objects.append({
            "time": int(round(hit["time"] * 1000)),
            "component": hit["component"],
            "velocity": 0.8,
            "lane": hit["lane"],
        })
    
    # Sort by time
    hit_objects.sort(key=lambda x: x["time"])

    print(f"Beatmap generation produced {len(hit_objects)} hit objects (fallback={used_fallback}).")
    
    # Calculate difficulty
    difficulty = calculate_difficulty(classified_hits)
    
    # Get unique drum components
    drum_components = sorted(set(hit["component"] for hit in classified_hits))
    
    # Build beatmap structure
    tags = metadata.get("tags") if metadata else None
    if not tags:
        tags = ["ai-generated"]

    description = metadata.get("description") if metadata else None

    snap_divisor = {
        "quarter": 1,
        "eighth": 2,
        "triplet": 3,
        "sixteenth": 4,
        "thirtysecond": 8,
    }[_resolve_grid(quantization_grid)]

    beatmap = {
        "version": "1.0.0",
        "metadata": {
            "title": metadata.get("title", Path(audio_path).stem),
            "artist": metadata.get("artist", "Unknown Artist"),
            "creator": metadata.get("creator", "BeatSight AI"),
            "tags": tags,
            "difficulty": round(difficulty, 2),
            "previewTime": 10000,  # 10 seconds in
            "beatmapId": metadata.get("beatmap_id", str(hash(audio_path))),
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "modifiedAt": datetime.utcnow().isoformat() + "Z",
            "source": metadata.get("source"),
            "description": description,
        },
        "audio": {
            "filename": Path(audio_path).name,
            "hash": compute_audio_hash(audio_path),
            "duration": duration_ms,
            "sampleRate": analysis_sr,
        },
        "timing": {
            "bpm": round(quantization_result["bpm"], 2),
            "offset": int(round(quantization_result.get("offset", 0.0) * 1000.0)),
            "timeSignature": "4/4",
        },
        "drumKit": {
            "components": drum_components,
            "layout": "standard_5piece",
        },
        "hitObjects": hit_objects,
        "editor": {
            "snapDivisor": snap_divisor,
            "visualLanes": 7,
            "aiGenerationMetadata": {
                "modelVersion": metadata.get("ai_version", "1.0.0"),
                "confidence": round(
                    sum(h["confidence"] for h in classified_hits) / len(classified_hits),
                    3
                ) if classified_hits else 0.0,
                "processedAt": datetime.utcnow().isoformat() + "Z",
                "metadataProvider": metadata.get("metadata_provider"),
                "metadataConfidence": metadata.get("metadata_confidence"),
            }
        }
    }
    
    # Add drum stem info if available
    if drum_stem_path:
        beatmap["audio"]["drumStem"] = Path(drum_stem_path).name
        beatmap["audio"]["drumStemHash"] = compute_audio_hash(drum_stem_path)

    debug_info = {
        "used_fallback": used_fallback,
        "quantization": {
            "grid": _resolve_grid(quantization_grid),
            "max_error_ms": max_snap_error_ms,
            "coverage": quantization_result["coverage"],
            "mean_error_ms": quantization_result["mean_error"] * 1000.0,
            "median_error_ms": quantization_result["median_error"] * 1000.0,
            "offset": quantization_result.get("offset", 0.0),
            "step": quantization_result.get("step", 0.0),
            "candidates": quantization_result.get("candidates", []),
            "forced": quantization_result.get("forced", False),
            "forced_bpm": forced_bpm,
            "forced_offset": forced_offset,
            "forced_step": forced_step,
            "force_quantization": force_quantization,
    },
    "lane_stats": lane_stats,
        "sections": _section_counts(snapped_times.tolist(), quantization_result["bpm"]),
    }

    if detection_debug:
        debug_info["detection"] = detection_debug

    return beatmap, debug_info
