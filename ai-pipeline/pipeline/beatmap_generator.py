"""
Beatmap generation from classified drum hits
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import librosa
import numpy as np


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
    Assign visual lanes to hits based on drum component.
    
    Standard 7-lane layout:
    0: Kick
    1: Hi-hat (foot)
    2: Snare
    3: Hi-hat (hand)
    4: Toms (high)
    5: Toms (mid/low)
    6: Cymbals (crash/ride/china)
    """
    lane_map = {
        "kick": 0,
        "hihat_pedal": 1,
        "snare": 2,
        "hihat_closed": 3,
        "hihat_open": 3,
        "tom_high": 4,
        "tom_mid": 5,
        "tom_low": 5,
        "crash": 6,
        "crash2": 6,
        "ride": 6,
        "ride_bell": 6,
        "china": 6,
        "splash": 6,
    }
    
    for hit in hits:
        hit["lane"] = lane_map.get(hit["component"], 6)  # Default to lane 6
    
    return hits


def detect_bpm(audio: np.ndarray, sr: int) -> float:
    """
    Detect BPM of audio using librosa.
    """
    tempo, _ = librosa.beat.beat_track(y=audio, sr=sr)
    
    # beat_track returns numpy array in newer versions
    if isinstance(tempo, np.ndarray):
        tempo = float(tempo[0]) if len(tempo) > 0 else 120.0
    
    return float(tempo)


def compute_audio_hash(file_path: str) -> str:
    """
    Compute SHA-256 hash of audio file.
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def generate_beatmap(
    classified_hits: List[Dict],
    audio_path: str,
    drum_stem_path: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate complete .bsm beatmap file.
    
    Args:
        classified_hits: List of classified drum hits
        audio_path: Path to original audio file
        drum_stem_path: Path to isolated drum stem (optional)
        metadata: Additional metadata (creator, title, etc.)
        
    Returns:
        Complete beatmap dictionary
    """
    metadata = metadata or {}
    
    # Load audio for analysis
    audio, sr = librosa.load(audio_path, sr=44100, mono=True)
    duration_ms = int(len(audio) / sr * 1000)
    
    # Detect BPM
    bpm = detect_bpm(audio, sr)
    
    # Assign lanes
    hits_with_lanes = assign_lanes(classified_hits)
    
    # Convert to hitObjects format
    hit_objects = []
    for hit in hits_with_lanes:
        hit_objects.append({
            "time": int(hit["time"] * 1000),  # Convert to milliseconds
            "component": hit["component"],
            "velocity": 0.8,  # Default velocity
            "lane": hit["lane"],
        })
    
    # Sort by time
    hit_objects.sort(key=lambda x: x["time"])
    
    # Calculate difficulty
    difficulty = calculate_difficulty(classified_hits)
    
    # Get unique drum components
    drum_components = sorted(set(hit["component"] for hit in classified_hits))
    
    # Build beatmap structure
    beatmap = {
        "version": "1.0.0",
        "metadata": {
            "title": metadata.get("title", Path(audio_path).stem),
            "artist": metadata.get("artist", "Unknown Artist"),
            "creator": metadata.get("creator", "BeatSight AI"),
            "tags": metadata.get("tags", ["ai-generated"]),
            "difficulty": round(difficulty, 2),
            "previewTime": 10000,  # 10 seconds in
            "beatmapId": metadata.get("beatmap_id", str(hash(audio_path))),
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "modifiedAt": datetime.utcnow().isoformat() + "Z",
        },
        "audio": {
            "filename": Path(audio_path).name,
            "hash": compute_audio_hash(audio_path),
            "duration": duration_ms,
            "sampleRate": sr,
        },
        "timing": {
            "bpm": round(bpm, 2),
            "offset": 0,
            "timeSignature": "4/4",
        },
        "drumKit": {
            "components": drum_components,
            "layout": "standard_5piece",
        },
        "hitObjects": hit_objects,
        "editor": {
            "snapDivisor": 4,
            "visualLanes": 7,
            "aiGenerationMetadata": {
                "modelVersion": metadata.get("ai_version", "1.0.0"),
                "confidence": round(
                    sum(h["confidence"] for h in classified_hits) / len(classified_hits),
                    3
                ) if classified_hits else 0.0,
                "processedAt": datetime.utcnow().isoformat() + "Z",
            }
        }
    }
    
    # Add drum stem info if available
    if drum_stem_path:
        beatmap["audio"]["drumStem"] = Path(drum_stem_path).name
        beatmap["audio"]["drumStemHash"] = compute_audio_hash(drum_stem_path)
    
    return beatmap
