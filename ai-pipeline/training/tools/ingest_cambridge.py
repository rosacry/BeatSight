#!/usr/bin/env python3
"""Ingest Cambridge multitrack stems into BeatSight manifests and provenance logs."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import random
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, TextIO, Tuple

try:  # Optional dependency for precise audio stats
    import soundfile as _sf  # type: ignore[import]
except Exception:  # pragma: no cover - optional helper
    _sf = None

import wave  # Built-in fallback for WAV duration/channel probing

if __package__:
    from . import ingest_utils
else:  # pragma: no cover - fallback for direct execution
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from training.tools import ingest_utils

DEFAULT_ROOT_CANDIDATES: Sequence[str] = (
    "data/raw/cambridge",
    "D:/data/raw/cambridge",
    "/mnt/d/data/raw/cambridge",
)
DEFAULT_SESSIONS_OUTPUT = pathlib.Path("ai-pipeline/training/data/manifests/cambridge_sessions.jsonl")
DEFAULT_EVENTS_OUTPUT = pathlib.Path("ai-pipeline/training/data/manifests/cambridge_events.jsonl")
DEFAULT_PROVENANCE_OUTPUT = pathlib.Path("ai-pipeline/training/data/provenance/cambridge_provenance.jsonl")
DEFAULT_LICENSE_REF = "ai-pipeline/training/data/licenses/cambridge.md"
DEFAULT_SUMMARY_DIR = pathlib.Path("ai-pipeline/training/reports/ingest")
SUPPORTED_EXTS = {".wav", ".flac", ".aif", ".aiff"}
EVENT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://beatsight.ai/datasets/cambridge")
IGNORED_DIRECTORY_NAMES = {"__macosx"}
IGNORED_FILENAME_PREFIXES = ("._",)
NON_DRUM_KEYWORDS = {
    "bass",
    "bassamp",
    "bassampmic",
    "leadvox",
    "leadvocals",
    "leadvoxdt",
    "vox",
    "vocal",
    "vocals",
    "backingvox",
    "bgvox",
    "backingvoxdt",
    "choir",
    "strings",
    "string",
    "violin",
    "viola",
    "cello",
    "horn",
    "horns",
    "brass",
    "woodwind",
    "flute",
    "oboe",
    "clarinet",
    "sax",
    "saxophone",
    "trumpet",
    "trombone",
    "guitar",
    "elecgtr",
    "elecgtrdi",
    "elecgtrdt",
    "acgtr",
    "acousticgtr",
    "gtr",
    "gtrdi",
    "gtrdt",
    "piano",
    "pianos",
    "keys",
    "organ",
    "rhodes",
    "wurlitzer",
    "synth",
    "synths",
    "pad",
    "pads",
    "ambient",
    "ambience",
    "ambi",
    "fx",
    "sfx",
    "loop",
    "loops",
    "drumloop",
    "drumsloop",
    "overheads",
    "overhead",
    "drumsroom",
    "roommic",
    "roommics",
    "room",
    "reference",
    "quartet",
    "acappella",
    "percussion",
    "cymbal",
    "cymbals",
    "hammond",
    "mainpair",
    "chamber",
    "timpani",
    "mandolin",
    "whisper",
    "intro",
    "sample",
    "fill",
    "ukelele",
    "ukulele",
    "banjo",
    "harp",
    "pair",
    "stereo",
    "frontms",
    "clicks",
    "click",
    "dulcimer",
    "mellotron",
    "accordion",
    "fiddle",
    "electrohit",
    "sticks",
    "storm",
    "lightning",
    "speech",
    "heartbeat",
    "heartbeart",
    "vocoder",
    "ela",
    "m60",
    "clavinet",
    "acoustic",
    "bv",
    "clonk",
    "car",
    "climbing",
    "closemic",
    "deck",
    "decks",
    "pizz",
    "arco",
    "theme",
    "vinyl",
    "noise",
    "door",
    "di",
    "breathing",
    "gangs",
    "giggle",
    "giggles",
    "glitch",
    "glup",
    "hiss",
    "ham",
    "helicopter",
    "gtt",
    "gttdt",
    "pansdt",
    "pans1dt",
    "manley",
    "adam",
    "lapsteel",
    "steelgtr",
    "ssle",
    "ssl6000e",
    "ruff",
    "key",
    "leslie",
    "orchestra",
    "orchestrahit",
    "music",
    "moog",
    "narration",
    "hurdy",
    "gurdy",
    "laugh",
    "laughs",
    "llenties",
    "alto",
    "soprano",
    "nord",
    "oh",
    "party",
    "pedalsteel",
    "running",
    "riser",
    "snow",
    "stumbling",
    "tuba",
    "lyrical",
    "adlib",
    "ivo",
    "koto",
    "srtings",
    "shakuhachi",
    "sitar",
    "orch",
    "stabs",
    "piccolo",
    "bone",
    "sobbing",
    "toy",
    "tree",
    "flock",
    "bulldozer",
    "knocking",
    "walla",
    "anvil",
    "tenor",
    "mando",
    "yamaha",
    "mk",
    "gt",
    "ambmono",
    "tape",
    "tapehiss",
    "alarm",
    "harmonica",
    "bazouki",
    "recorder",
    "psaltery",
    "stylophone",
    "telephone",
    "traffic",
    "mc",
    "scream",
    "squash",
    "act",
    "rright",
    "m80",
    "m81",
    "m82",
    "m83",
    "m84",
    "stagelip",
    "shiraki",
    "harmonic",
    "harmonics",
    "timestamped",
    "backingvos",
    "backvos",
    "farfisa",
    "voicemail",
    "breath",
    "chug",
}


@dataclass
class BuildOptions:
    include_events: bool
    include_provenance: bool
    hash_audio: bool
    ingestion_version: str
    license_ref: str


@dataclass
class SessionResult:
    session_id: str
    event_json_lines: List[str]
    provenance_json: Optional[str]
    per_session_events: int
    label_counts: Counter[str]
    unknown_count: int
    unknown_samples: List[str]
    missing_files: int
    hashed_files: int
    non_drum_counts: Counter[str]
    non_drum_samples: List[str]


def discover_dataset_roots(candidates: Sequence[str]) -> List[pathlib.Path]:
    roots: List[pathlib.Path] = []
    for candidate in candidates:
        resolved = ingest_utils.resolve_dataset_roots([candidate])
        roots.extend(resolved)
    unique_roots: List[pathlib.Path] = []
    seen: Set[pathlib.Path] = set()
    for root in roots:
        real = root.resolve(strict=False)
        if real in seen:
            continue
        seen.add(real)
        unique_roots.append(real)
    return unique_roots


def _iter_session_dirs(root: pathlib.Path) -> Iterable[pathlib.Path]:
    if not root.exists():
        return []
    return (
        child
        for child in sorted(root.iterdir())
        if child.is_dir() and child.name.lower() not in IGNORED_DIRECTORY_NAMES
    )


def _gather_audio_files(session_dir: pathlib.Path, dataset_root: pathlib.Path) -> List[str]:
    audio_files: List[str] = []
    for path in sorted(session_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        lower_parts = {part.lower() for part in path.parts}
        if lower_parts & IGNORED_DIRECTORY_NAMES:
            continue
        if any(path.name.startswith(prefix) for prefix in IGNORED_FILENAME_PREFIXES):
            continue
        audio_files.append(path.relative_to(dataset_root).as_posix())
    return audio_files


def discover_sessions(
    roots: Sequence[pathlib.Path],
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    inventory: List[Dict[str, object]] = []
    seen_sessions: Set[Tuple[str, str]] = set()
    stats: List[Dict[str, object]] = []

    primary_candidate = ingest_utils.resolve_repo_path("data/raw/cambridge")
    primary_resolved = primary_candidate.resolve(strict=False)
    primary_exists = primary_resolved.exists()

    for root in roots:
        tier = "primary" if primary_exists and root.resolve(strict=False) == primary_resolved else "external"
        session_dirs = list(_iter_session_dirs(root))
        if not session_dirs:
            stats.append(
                {
                    "root": root.as_posix(),
                    "tier": tier,
                    "session_dirs": 0,
                    "sessions_with_audio": 0,
                    "skipped_empty": 0,
                    "duplicates": 0,
                }
            )
            continue

        description = f"Cambridge ({tier})"
        added = 0
        skipped_empty = 0
        duplicate_count = 0
        for session_dir in ingest_utils.track_progress(session_dirs, description, total=len(session_dirs)):
            audio_files = _gather_audio_files(session_dir, root)
            if not audio_files:
                skipped_empty += 1
                continue

            relative_session = session_dir.relative_to(root).as_posix()
            storage_root = root.as_posix()
            key = (relative_session, storage_root)
            if key in seen_sessions:
                duplicate_count += 1
                continue
            seen_sessions.add(key)
            inventory.append(
                {
                    "session_id": relative_session,
                    "storage_root": storage_root,
                    "storage_tier": tier,
                    "session_path": relative_session,
                    "audio_files": audio_files,
                    "audio_file_count": len(audio_files),
                }
            )
            added += 1

        stats.append(
            {
                "root": root.as_posix(),
                "tier": tier,
                "session_dirs": len(session_dirs),
                "sessions_with_audio": added,
                "skipped_empty": skipped_empty,
                "duplicates": duplicate_count,
            }
        )

    return inventory, stats


def apply_session_limits(
    inventory: Sequence[Dict[str, object]],
    max_sessions: Optional[int],
    max_per_root: Optional[int],
    seed: Optional[int],
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    if (max_sessions is None or max_sessions <= 0) and (max_per_root is None or max_per_root <= 0):
        selected = list(inventory)
        metadata = {
            "limited": False,
            "selected_total": len(selected),
            "available_total": len(inventory),
        }
        return selected, metadata

    groups: Dict[str, Dict[str, object]] = {}
    for entry in inventory:
        root = str(entry.get("storage_root"))
        tier = str(entry.get("storage_tier"))
        group = groups.setdefault(root, {"tier": tier, "items": []})
        group["items"].append(entry)

    rng = random.Random(seed) if seed is not None else None
    selected: List[Dict[str, object]] = []
    per_root_summary: Dict[str, Dict[str, object]] = {}

    for root, data in groups.items():
        items = data["items"]
        available = len(items)
        if rng is not None:
            ordered = items.copy()
            rng.shuffle(ordered)
        else:
            ordered = sorted(items, key=lambda entry: str(entry.get("session_id")))

        limit = max_per_root if (max_per_root is not None and max_per_root > 0) else available
        chosen = ordered[:limit]
        per_root_summary[root] = {
            "tier": data["tier"],
            "available": available,
            "selected": len(chosen),
        }
        selected.extend(chosen)

    if max_sessions is not None and max_sessions > 0 and len(selected) > max_sessions:
        if rng is not None:
            rng.shuffle(selected)
        else:
            selected.sort(key=lambda entry: (str(entry.get("storage_root")), str(entry.get("session_id"))))
        selected = selected[:max_sessions]

        counts: Dict[str, int] = {}
        for entry in selected:
            root = str(entry.get("storage_root"))
            counts[root] = counts.get(root, 0) + 1
        for root, info in per_root_summary.items():
            info["selected"] = counts.get(root, 0)
    else:
        if rng is None:
            selected.sort(key=lambda entry: (str(entry.get("storage_root")), str(entry.get("session_id"))))

    metadata = {
        "limited": True,
        "max_sessions": max_sessions,
        "max_per_root": max_per_root,
        "seed": seed,
        "selected_total": len(selected),
        "available_total": len(inventory),
        "per_root": [
            {
                "storage_root": root,
                "tier": info["tier"],
                "available": info["available"],
                "selected": info["selected"],
            }
            for root, info in sorted(per_root_summary.items())
        ],
    }

    return selected, metadata


def _tokenize(name: str) -> Set[str]:
    tokens: Set[str] = set()
    for part in pathlib.Path(name).parts:
        normalized = (
            part.replace("-", " ")
            .replace("_", " ")
            .replace(".", " ")
        )
        normalized = re.sub(r"(?<=[A-Za-z])(?=[A-Z][a-z])", " ", normalized)
        normalized = normalized.lower()
        for token in normalized.split():
            if token:
                tokens.add(token)
                stripped_digits = token.rstrip("0123456789")
                if stripped_digits and stripped_digits != token:
                    tokens.add(stripped_digits)
                without_digits = re.sub(r"\d+", "", token)
                if without_digits and without_digits != token:
                    tokens.add(without_digits)
                if token.endswith("s") and len(token) > 3:
                    tokens.add(token[:-1])
                if stripped_digits.endswith("s") and len(stripped_digits) > 3:
                    tokens.add(stripped_digits[:-1])
                if without_digits.endswith("s") and len(without_digits) > 3:
                    tokens.add(without_digits[:-1])
                if token.endswith("bells"):
                    tokens.add("bells")
                elif token.endswith("bell"):
                    tokens.add("bell")
                if token.endswith("room") or token.endswith("rooms"):
                    tokens.add("room")
                if token.endswith("sample") or token.endswith("samples"):
                    tokens.add("sample")
                if token.endswith("loop") or token.endswith("loops"):
                    tokens.add("loop")
    return tokens


def _match_non_drum(tokens: Set[str]) -> Optional[str]:
    for token in tokens:
        for keyword in NON_DRUM_KEYWORDS:
            if keyword == "bass" and "drum" in token:
                continue
            if token == keyword or token.startswith(keyword) or keyword in token:
                return keyword
    if {"pedal", "steel"} <= tokens:
        return "pedalsteel"
    if ("backing" in tokens or "back" in tokens) and {"vox", "vos"} & tokens:
        return "backingvos" if "backing" in tokens else "backvos"
    if "amb" in tokens and "mono" in tokens:
        return "ambmono"
    if "amo" in tokens and "mono" in tokens:
        return "ambmono"
    if {"share", "down"} <= tokens:
        return "sharedown"
    if "130624" in tokens and {"1035", "1040"} & tokens:
        return "timestamped"
    if {"main", "xy", "pair"} <= tokens:
        return "mainpair"
    if "clav" in tokens and "clave" not in tokens and "claves" not in tokens:
        return "clavinet"
    if "beep" in tokens:
        return "beep"
    if "footsteps" in tokens or "footstep" in tokens:
        return "footsteps"
    if "rain" in tokens and "stick" not in tokens and "sticks" not in tokens:
        return "rain"
    if ("waves" in tokens) or ("wave" in tokens and all(not item.startswith("waveform") for item in tokens)):
        return "waves"
    if "wind" in tokens and all(not item.startswith("windchim") for item in tokens):
        return "wind"
    if "owl" in tokens:
        return "owl"
    if {"lead", "double"} <= tokens:
        return "leadvox"
    if {"over", "04", "07"} <= tokens:
        return "overheads"
    drum_hints = {"kick", "snare", "tom", "hat", "hihat", "ride", "cymbal", "drum", "drums", "kit", "perc", "percussion"}
    if {"close", "mic", "left"} <= tokens and tokens.isdisjoint(drum_hints):
        return "closemic"
    if {"close", "mic", "right"} <= tokens and tokens.isdisjoint(drum_hints):
        return "closemic"
    if {"close", "mic"} <= tokens and tokens.isdisjoint(drum_hints):
        return "closemic"
    if {"stage", "lip"} <= tokens:
        return "stagelip"
    return None


def _probe_audio_stats(path: pathlib.Path) -> Tuple[Optional[int], Optional[float], Optional[int]]:
    if _sf is not None:
        try:
            info = _sf.info(str(path))
            duration = float(info.frames) / info.samplerate if info.samplerate else None
            return info.samplerate, duration, info.channels
        except Exception:
            pass

    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            samplerate = handle.getframerate()
            channels = handle.getnchannels()
            duration = frames / samplerate if samplerate else None
            return samplerate, duration, channels
    except Exception:
        return None, None, None


def _infer_component(track_path: str) -> Optional[Tuple[str, Dict[str, object], Set[str]]]:
    tokens = _tokenize(track_path)
    lower = track_path.lower()
    name_lower = pathlib.Path(track_path).name.lower()
    stem_lower = pathlib.Path(track_path).stem.lower()
    techniques: Set[str] = set()
    extras: Dict[str, object] = {}

    def has_any(*candidates: str) -> bool:
        for candidate in candidates:
            cand = candidate.lower()
            if cand in tokens:
                return True
            if any(token.startswith(cand) for token in tokens):
                return True
            if cand == "tom":
                # Avoid matching substrings such as "phantom" for tom detection.
                continue
            if cand in lower:
                return True
        return False

    if any(keyword in lower for keyword in ("talkback", "click", "slate", "guide")):
        return None

    if has_any("kick", "bd", "bassdrum", "bass-drum", "kck", "kik"):
        if has_any("sub"):
            extras["instrument_variant"] = "sub"
        if has_any("in", "inside") and not has_any("out"):
            extras["mic_position"] = "inside"
        elif has_any("out", "outside"):
            extras["mic_position"] = "outside"
        return "kick", extras, techniques

    if any(pattern in name_lower for pattern in ("k i", "k_i", "k-i")):
        extras = {"mic_position": "inside"}
        return "kick", extras, techniques

    if any(pattern in name_lower for pattern in ("k o", "k_o", "k-o")):
        extras = {"mic_position": "outside"}
        return "kick", extras, techniques

    if has_any("snare", "sd", "dnare"):
        if has_any("top") and not has_any("bottom"):
            extras["mic_position"] = "top"
        elif has_any("bottom"):
            extras["mic_position"] = "bottom"
        if has_any("rim", "sidestick", "stick"):
            techniques.add("rimshot")
        return "snare", extras, techniques

    if {"share", "down"} <= tokens:
        extras["mic_position"] = "bottom"
        return "snare", extras, techniques

    if has_any("sidestick", "rimshot") and not has_any("snare"):
        return "rimshot", extras, techniques

    if has_any("cross", "stick") and has_any("snare"):
        techniques.add("cross_stick")
        return "snare", extras, techniques

    if "rim" in tokens and not has_any("snare"):
        techniques.add("rimshot")
        return "rimshot", extras, techniques

    if any(pattern in stem_lower for pattern in ("sn t", "sn_t", "sn-t")):
        extras = {"mic_position": "top"}
        return "snare", extras, techniques

    if any(pattern in stem_lower for pattern in ("sn b", "sn_b", "sn-b")):
        extras = {"mic_position": "bottom"}
        return "snare", extras, techniques

    if stem_lower == "sn" or stem_lower.startswith("sn_") or stem_lower.startswith("sn-"):
        return "snare", extras, techniques

    if "sub" in tokens and "hit" in tokens:
        extras["instrument_variant"] = "sub"
        return "aux_percussion", extras, techniques

    if has_any("hihat", "hi-hat", "hh") or "hat" in tokens:
        if has_any("foot", "pedal") and not has_any("open"):
            techniques.add("hihat_foot_chick")
            return "hihat_pedal", extras, techniques
        if has_any("open", "loose") and not has_any("close", "closed"):
            extras["openness"] = 1.0
            techniques.add("hihat_half_open")
            return "hihat_open", extras, techniques
        extras["openness"] = 0.0
        return "hihat_closed", extras, techniques

    if has_any("ride"):
        if has_any("bell"):
            techniques.add("ride_bell_accent")
            extras["strike_position"] = "bell"
        else:
            techniques.add("ride_tip_articulation")
        return "ride_bow", extras, techniques

    if has_any("drum", "drums") and not has_any("loop", "loops", "sfx", "sample"):
        techniques.add("multitrack_context")
        return "drum_mix", extras, techniques

    if "main" in tokens and ("mic" in tokens or "mics" in tokens):
        techniques.add("multitrack_context")
        return "drum_mix", extras, techniques

    if has_any("cowbell"):
        techniques.add("cowbell")
        extras["instrument_variant"] = "cowbell"
        return "aux_percussion", extras, techniques

    if has_any("china"):
        if has_any("high", "bright"):
            extras["instrument_variant"] = "high"
        elif has_any("low", "dark"):
            extras["instrument_variant"] = "low"
        return "china", extras, techniques

    if has_any("splash"):
        return "splash", extras, techniques

    if has_any("crash"):
        if has_any("high", "bright", "small", "left"):
            extras["instrument_variant"] = "high"
        elif has_any("low", "dark", "large", "right"):
            extras["instrument_variant"] = "low"
        elif has_any("mid", "medium"):
            extras["instrument_variant"] = "mid"
        return "crash", extras, techniques

    if has_any("rainstick"):
        extras = {"instrument_variant": "rainstick"}
        return "aux_percussion", extras, techniques

    if has_any("woodblock"):
        extras = {"instrument_variant": "woodblock"}
        return "aux_percussion", extras, techniques

    if has_any("triangle"):
        extras = {"instrument_variant": "triangle"}
        return "aux_percussion", extras, techniques

    if has_any("cajon"):
        extras = {"instrument_variant": "cajon"}
        return "aux_percussion", extras, techniques

    if has_any("brush"):
        techniques.add("brush_sweep")
        extras = {"instrument_variant": "brushes"}
        return "aux_percussion", extras, techniques

    if has_any("djembe"):
        extras = {"instrument_variant": "djembe"}
        return "aux_percussion", extras, techniques

    if has_any("timbale"):
        extras = {"instrument_variant": "timbale"}
        return "aux_percussion", extras, techniques

    if has_any("glock", "glockenspiel"):
        extras = {"instrument_variant": "glockenspiel"}
        return "aux_percussion", extras, techniques

    if has_any("xylophone"):
        extras = {"instrument_variant": "xylophone"}
        return "aux_percussion", extras, techniques

    if has_any("celesta"):
        extras = {"instrument_variant": "celesta"}
        return "aux_percussion", extras, techniques

    if has_any("chime", "chimes") or ("chime" in tokens and "wind" in tokens):
        extras = {"instrument_variant": "chimes"}
        return "aux_percussion", extras, techniques

    if has_any("guiro"):
        extras = {"instrument_variant": "guiro"}
        return "aux_percussion", extras, techniques

    if has_any("kalimba"):
        extras = {"instrument_variant": "kalimba"}
        return "aux_percussion", extras, techniques

    if has_any("whistle"):
        extras = {"instrument_variant": "whistle"}
        return "aux_percussion", extras, techniques

    if ("steel" in tokens and "pan" in tokens) or has_any("steelpan", "steelpans"):
        extras = {"instrument_variant": "steel_pan"}
        return "aux_percussion", extras, techniques

    if has_any("vibes", "vibraphone", "vibrophone"):
        extras = {"instrument_variant": "steel_tongue_drum"}
        return "aux_percussion", extras, techniques

    if has_any("llamador"):
        extras = {"instrument_variant": "llamador"}
        return "aux_percussion", extras, techniques

    if has_any("guaracha"):
        extras = {"instrument_variant": "guaracha_percussion"}
        return "aux_percussion", extras, techniques

    if has_any("guache"):
        extras = {"instrument_variant": "guache"}
        return "aux_percussion", extras, techniques

    if has_any("paliteo"):
        extras = {"instrument_variant": "paliteo"}
        return "aux_percussion", extras, techniques

    if has_any("outrohit"):
        extras = {"instrument_variant": "outro_hit"}
        return "aux_percussion", extras, techniques

    if has_any("bombo"):
        extras = {"instrument_variant": "bombo"}
        return "aux_percussion", extras, techniques

    if has_any("cununo", "cunono"):
        extras = {"instrument_variant": "cununo"}
        return "aux_percussion", extras, techniques

    if has_any("guasa"):
        extras = {"instrument_variant": "guasa"}
        return "aux_percussion", extras, techniques

    if has_any("pandero", "pandeiro"):
        extras = {"instrument_variant": "tambourine"}
        return "aux_percussion", extras, techniques

    if "metalhit" in tokens or (has_any("metal") and has_any("hit")):
        extras = {"instrument_variant": "metal_hit"}
        return "aux_percussion", extras, techniques

    if has_any("anvil"):
        extras = {"instrument_variant": "anvil"}
        return "aux_percussion", extras, techniques

    if has_any("glass"):
        extras = {"instrument_variant": "glass_fx"}
        return "aux_percussion", extras, techniques

    if has_any("break"):
        extras = {"instrument_variant": "break_fx"}
        return "aux_percussion", extras, techniques

    if has_any("drip"):
        extras = {"instrument_variant": "water_drip"}
        return "aux_percussion", extras, techniques

    if has_any("sub"):
        extras = {"instrument_variant": "sub_drop"}
        return "aux_percussion", extras, techniques

    if has_any("marimba"):
        extras = {"instrument_variant": "marimba"}
        return "aux_percussion", extras, techniques

    if has_any("maraca", "maracas"):
        extras = {"instrument_variant": "maracas"}
        return "aux_percussion", extras, techniques

    if has_any("taiko") or "daiko" in tokens:
        extras = {"instrument_variant": "taiko"}
        return "aux_percussion", extras, techniques

    if has_any("cabasa"):
        extras = {"instrument_variant": "cabasa"}
        return "aux_percussion", extras, techniques

    if has_any("vibes", "vibraphone"):
        extras = {"instrument_variant": "vibraphone"}
        return "aux_percussion", extras, techniques

    if has_any("tambo"):
        extras = {"instrument_variant": "tambourine"}
        return "aux_percussion", extras, techniques

    if has_any("timp"):
        extras = {"instrument_variant": "timpani"}
        return "aux_percussion", extras, techniques

    if has_any("clap"):
        extras = {"instrument_variant": "clap"}
        return "aux_percussion", extras, techniques

    if has_any("scratch"):
        extras = {"instrument_variant": "scratch"}
        return "aux_percussion", extras, techniques

    if has_any("clave", "claves"):
        extras = {"instrument_variant": "claves"}
        return "aux_percussion", extras, techniques

    if has_any("impact"):
        extras = {"instrument_variant": "impact_fx"}
        return "aux_percussion", extras, techniques

    if has_any("gunshot"):
        extras = {"instrument_variant": "gunshot"}
        return "aux_percussion", extras, techniques

    if has_any("stomp", "stomps"):
        extras = {"instrument_variant": "stomp"}
        return "aux_percussion", extras, techniques

    if has_any("electrohit"):
        extras = {"instrument_variant": "electro_hit"}
        return "aux_percussion", extras, techniques

    if has_any("cachapas"):
        extras = {"instrument_variant": "cachapas"}
        return "aux_percussion", extras, techniques

    if has_any("beatpunch") or ("beat" in tokens and "punch" in tokens):
        extras = {"instrument_variant": "beat_punch"}
        return "aux_percussion", extras, techniques

    if has_any("vibraslap"):
        extras = {"instrument_variant": "vibraslap"}
        return "aux_percussion", extras, techniques

    if has_any("waterphone"):
        extras = {"instrument_variant": "waterphone"}
        return "aux_percussion", extras, techniques

    if has_any("rototom"):
        extras["instrument_variant"] = "rototom"
        return "tom_high", extras, techniques

    if "ft" in tokens and ("kit" in tokens or "studio" in tokens or "floor" in tokens):
        extras["instrument_variant"] = "low"
        return "tom_low", extras, techniques

    if has_any("tom") or any(token.startswith("tom") for token in tokens):
        if has_any("high", "hi", "rack", "tom1") and not has_any("floor"):
            extras["instrument_variant"] = "high"
            return "tom_high", extras, techniques
        if has_any("mid", "middle", "tom2"):
            extras["instrument_variant"] = "mid"
            return "tom_mid", extras, techniques
        if has_any("floor", "low", "tom3", "ft"):
            extras["instrument_variant"] = "low"
            return "tom_low", extras, techniques
        extras["instrument_variant"] = "mid"
        return "tom_mid", extras, techniques

    if has_any(
        "shaker",
        "tamb",
        "tambourine",
        "snap",
        "conga",
        "congas",
        "bongo",
        "bongos",
        "perc",
        "percussion",
        "timpani",
        "bell",
        "bells",
        "gong",
        "gongs",
    ):
        extras = {"instrument_variant": "aux"}
        return "aux_percussion", extras, techniques

    return None


def _create_event(
    session_id: str,
    audio_rel: str,
    full_path: pathlib.Path,
    inferred: Tuple[str, Dict[str, object], Set[str]],
) -> Dict[str, object]:
    label, extras, techniques = inferred
    samplerate, duration, channels = _probe_audio_stats(full_path)
    file_size = full_path.stat().st_size if full_path.exists() else None

    components: List[Dict[str, object]] = [
        {
            "label": label,
            "source_track": audio_rel,
        }
    ]
    if extras:
        components[0].update(extras)

    event = {
        "event_id": str(uuid.uuid5(EVENT_NAMESPACE, f"{session_id}:{audio_rel}")),
        "session_id": session_id,
        "source_set": "cambridge_multitrack",
        "is_synthetic": False,
        "audio_path": f"cambridge/{audio_rel}",
        "midi_path": None,
        "onset_time": 0.0,
        "offset_time": None,
        "tempo_bpm": None,
        "meter": None,
        "components": components,
        "techniques": sorted(techniques),
        "context_ms": {"pre": 0, "post": 0},
        "metadata_ref": f"provenance:{session_id}",
        "negative_example": False,
    }

    if samplerate:
        event["sample_rate"] = samplerate
    if duration:
        event["duration_seconds"] = round(duration, 6)
    if channels:
        event["channels"] = channels
    if file_size is not None:
        event["file_size_bytes"] = file_size

    return event


def _process_single_session(
    session: Dict[str, object],
    options: BuildOptions,
    now_utc: _dt.datetime,
) -> SessionResult:
    session_id = str(session["session_id"])
    storage_root = ingest_utils.resolve_repo_path(str(session["storage_root"]))
    audio_files = [str(item) for item in session.get("audio_files", [])]

    session_event_counter = 0
    label_counter: Counter[str] = Counter()
    unknown_count = 0
    unknown_samples: List[str] = []
    non_drum_counter: Counter[str] = Counter()
    non_drum_samples: List[str] = []
    hashed_files = 0
    missing_files = 0
    session_techniques: Set[str] = set()
    sample_paths: List[str] = []
    hash_entries: List[Dict[str, str]] = []
    event_lines: List[str] = []

    for audio_rel in audio_files:
        rel_path = pathlib.PurePosixPath(audio_rel).as_posix()
        full_path = storage_root / pathlib.Path(audio_rel)
        if not full_path.exists():
            missing_files += 1
            continue

        sample_paths.append(rel_path)

        if options.hash_audio:
            digest = ingest_utils.sha256_file(full_path)
            hash_entries.append({"path": rel_path, "sha256": digest})
            hashed_files += 1

        if not options.include_events:
            continue

        tokens = _tokenize(rel_path)
        non_drum_hit = _match_non_drum(tokens)
        if non_drum_hit:
            non_drum_counter[non_drum_hit] += 1
            if len(non_drum_samples) < 10:
                non_drum_samples.append(f"{session_id}:{rel_path}")
            continue

        inferred = _infer_component(rel_path)
        if inferred is None:
            unknown_count += 1
            if len(unknown_samples) < 10:
                unknown_samples.append(f"{session_id}:{rel_path}")
            continue

        event = _create_event(session_id, rel_path, full_path, inferred)
        extra_techniques = ingest_utils.apply_taxonomy_inference([event])
        if extra_techniques:
            session_techniques.update(extra_techniques)
            event["techniques"] = sorted(set(event.get("techniques", [])) | extra_techniques)
        label = event["components"][0]["label"]
        label_counter[label] += 1
        session_event_counter += 1
        session_techniques.update(event.get("techniques", []))
        event_lines.append(json.dumps(event, separators=(",", ":")))

    provenance_json: Optional[str] = None
    if options.include_provenance:
        record = ingest_utils.ProvenanceRecord(
            source_set="cambridge_multitrack",
            session_id=session_id,
            sample_paths=sample_paths,
            hashes=hash_entries,
            license_ref=options.license_ref,
            ingestion_script="training/tools/ingest_cambridge.py",
            ingestion_version=options.ingestion_version,
            processing_chain=["raw_multitrack"],
            timestamp_utc=now_utc.isoformat(),
            techniques=sorted(session_techniques),
            notes="Stem-level ingestion; per-hit segmentation pending manual QA.",
        )
        provenance_json = record.to_json()

    return SessionResult(
        session_id=session_id,
        event_json_lines=event_lines,
        provenance_json=provenance_json,
        per_session_events=session_event_counter,
        label_counts=label_counter,
        unknown_count=unknown_count,
        unknown_samples=unknown_samples,
        missing_files=missing_files,
        hashed_files=hashed_files,
        non_drum_counts=non_drum_counter,
        non_drum_samples=non_drum_samples,
    )


def process_sessions(
    inventory: Sequence[Dict[str, object]],
    options: BuildOptions,
    *,
    events_handle: Optional[TextIO] = None,
    provenance_handle: Optional[TextIO] = None,
    workers: int = 1,
) -> Dict[str, object]:
    event_count = 0
    label_counter: Counter[str] = Counter()
    per_session_events: Dict[str, int] = {}
    total_unknown = 0
    unknown_samples: List[str] = []
    missing_file_count = 0
    hashed_files_total = 0
    non_drum_counter: Counter[str] = Counter()
    non_drum_samples: List[str] = []
    provenance_count = 0

    now_utc = _dt.datetime.utcnow().replace(microsecond=0, tzinfo=_dt.timezone.utc)

    def handle_result(result: SessionResult) -> None:
        nonlocal event_count, total_unknown, missing_file_count, hashed_files_total, provenance_count

        event_count += result.per_session_events
        label_counter.update(result.label_counts)
        per_session_events[result.session_id] = result.per_session_events
        total_unknown += result.unknown_count
        missing_file_count += result.missing_files
        hashed_files_total += result.hashed_files
        non_drum_counter.update(result.non_drum_counts)

        if events_handle is not None and result.event_json_lines:
            for line in result.event_json_lines:
                events_handle.write(line + "\n")

        if provenance_handle is not None and result.provenance_json:
            provenance_handle.write(result.provenance_json + "\n")
            provenance_count += 1

        if len(unknown_samples) < 20:
            remaining = 20 - len(unknown_samples)
            unknown_samples.extend(result.unknown_samples[:remaining])

        if len(non_drum_samples) < 50:
            remaining = 50 - len(non_drum_samples)
            non_drum_samples.extend(result.non_drum_samples[:remaining])

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_process_single_session, session, options, now_utc)
                for session in inventory
            ]
            for future in ingest_utils.track_progress(as_completed(futures), "Processing Cambridge sessions", total=len(futures)):
                handle_result(future.result())
    else:
        for session in ingest_utils.track_progress(inventory, "Processing Cambridge sessions", total=len(inventory)):
            result = _process_single_session(session, options, now_utc)
            handle_result(result)

    summary = {
        "sessions": len(inventory),
        "events": event_count,
        "labels": dict(label_counter),
        "per_session_events": per_session_events,
        "unknown_track_count": total_unknown,
        "unknown_tracks_sample": unknown_samples,
        "missing_file_count": missing_file_count,
        "hash_audio": options.hash_audio,
        "hashed_files": hashed_files_total,
        "non_drum_track_count": sum(non_drum_counter.values()),
        "non_drum_keywords": dict(non_drum_counter.most_common(20)),
        "non_drum_tracks_sample": non_drum_samples,
        "provenance_sessions": provenance_count,
    }

    return summary


def write_jsonl(path: pathlib.Path, rows: Iterable[dict]) -> None:
    ingest_utils.write_jsonl(path, rows)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="*",
        help="Override dataset roots. Defaults include repo Cambridge folder and external drive copy.",
    )
    parser.add_argument(
        "--sessions-output",
        type=pathlib.Path,
        default=DEFAULT_SESSIONS_OUTPUT,
        help=f"Inventory JSONL output (default: {DEFAULT_SESSIONS_OUTPUT})",
    )
    parser.add_argument(
        "--events-output",
        type=pathlib.Path,
        help=f"Events JSONL output (default: {DEFAULT_EVENTS_OUTPUT})",
    )
    parser.add_argument(
        "--provenance-output",
        type=pathlib.Path,
        help=f"Provenance JSONL output (default: {DEFAULT_PROVENANCE_OUTPUT})",
    )
    parser.add_argument(
        "--summary-output",
        type=pathlib.Path,
        help="Optional JSON file capturing ingestion summary stats (default: datestamped report under training/reports/ingest).",
    )
    parser.add_argument(
        "--skip-events",
        action="store_true",
        help="Skip event generation (inventory only).",
    )
    parser.add_argument(
        "--skip-provenance",
        action="store_true",
        help="Skip provenance generation (useful for quick inventories).",
    )
    parser.add_argument(
        "--no-hash-audio",
        dest="hash_audio",
        action="store_false",
        help="Skip SHA256 computation for each audio stem (default: compute digests for provenance).",
    )
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="Stop after writing session inventory; skip events and provenance generation.",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        help="Maximum total sessions to process for events/provenance (after inventory).",
    )
    parser.add_argument(
        "--max-per-root",
        type=int,
        help="Maximum sessions per storage root to process for events/provenance.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Random seed used when shuffling before applying session limits (defaults to alphabetical order).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker threads for session processing (default: 1).",
    )
    parser.add_argument(
        "--ingestion-version",
        default="2025-11-08",
        help="Version string recorded in provenance output.",
    )
    parser.add_argument(
        "--license-ref",
        default=DEFAULT_LICENSE_REF,
        help="Relative path to the dataset license summary markdown.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Suppress error when no sessions are discovered.",
    )
    parser.set_defaults(hash_audio=True)
    args = parser.parse_args(argv)

    if args.max_sessions is not None and args.max_sessions < 0:
        parser.error("--max-sessions must be non-negative")
    if args.max_per_root is not None and args.max_per_root < 0:
        parser.error("--max-per-root must be non-negative")
    if args.workers is not None and args.workers <= 0:
        parser.error("--workers must be a positive integer")

    if args.events_output is None and not args.skip_events:
        args.events_output = DEFAULT_EVENTS_OUTPUT
    if args.provenance_output is None and not args.skip_provenance:
        args.provenance_output = DEFAULT_PROVENANCE_OUTPUT
    if args.summary_output is None:
        today = _dt.datetime.utcnow().strftime("%Y%m%d")
        args.summary_output = DEFAULT_SUMMARY_DIR / f"cambridge_summary_{today}.json"

    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)

    candidates = args.roots if args.roots else DEFAULT_ROOT_CANDIDATES
    print("Resolving Cambridge dataset roots...")
    roots = discover_dataset_roots(candidates)
    if not roots:
        raise SystemExit(
            "No Cambridge roots found. Checked: "
            + ", ".join(str(ingest_utils.resolve_repo_path(c)) for c in candidates)
        )
    print(" • Roots: " + ", ".join(str(root) for root in roots))

    print("Building Cambridge session inventory...")
    inventory, root_stats = discover_sessions(roots)
    if not inventory:
        if args.allow_empty:
            print("warning: no Cambridge sessions discovered; inventory not written.")
            return
        raise SystemExit("No audio files discovered under provided Cambridge roots.")

    for stat in root_stats:
        summary_line = (
            f" • Root summary: {stat['root']} [{stat['tier']}] -> "
            f"{stat['sessions_with_audio']} sessions with audio "
            f"({stat['skipped_empty']} empty dirs, {stat['duplicates']} duplicate ids, "
            f"{stat['session_dirs']} total dirs scanned)"
        )
        print(summary_line)

    working_inventory, selection_info = apply_session_limits(
        inventory,
        args.max_sessions,
        args.max_per_root,
        args.random_seed,
    )

    if not working_inventory:
        raise SystemExit("No sessions selected after applying limits; adjust --max-sessions/--max-per-root.")

    if selection_info.get("limited"):
        total_available = selection_info.get("available_total")
        selected_total = selection_info.get("selected_total")
        print(
            "Limiting Cambridge processing to "
            f"{selected_total} sessions (of {total_available})."
        )
        for entry in selection_info.get("per_root", []):
            print(
                "   • {storage_root} [{tier}] -> {selected} selected / {available} available".format(
                    storage_root=entry.get("storage_root"),
                    tier=entry.get("tier"),
                    selected=entry.get("selected"),
                    available=entry.get("available"),
                )
            )

    sessions_output_path = ingest_utils.resolve_repo_path(args.sessions_output)
    print(f"Writing {len(working_inventory)} sessions to {sessions_output_path}...")
    write_jsonl(sessions_output_path, working_inventory)

    options = BuildOptions(
        include_events=not args.skip_events and not args.inventory_only,
        include_provenance=not args.skip_provenance and not args.inventory_only,
        hash_audio=bool(getattr(args, "hash_audio", True)),
        ingestion_version=args.ingestion_version,
        license_ref=args.license_ref,
    )

    summary: Dict[str, object] = {
        "inventory_sessions": len(inventory),
        "sessions": len(working_inventory),
        "events": 0,
        "labels": {},
        "per_session_events": {},
        "unknown_track_count": 0,
        "unknown_tracks_sample": [],
        "missing_file_count": 0,
        "hash_audio": options.hash_audio,
        "hashed_files": 0,
        "roots": root_stats,
        "selection": selection_info,
        "non_drum_track_count": 0,
        "non_drum_keywords": {},
        "non_drum_tracks_sample": [],
        "provenance_sessions": 0,
    }

    events_output_path: Optional[pathlib.Path] = None
    provenance_output_path: Optional[pathlib.Path] = None

    if options.include_events or options.include_provenance:
        print("Generating Cambridge events and provenance payloads...")
        events_handle: Optional[TextIO] = None
        provenance_handle: Optional[TextIO] = None

        try:
            if options.include_events and args.events_output:
                events_output_path = ingest_utils.resolve_repo_path(args.events_output)
                events_output_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"Streaming events to {events_output_path}...")
                events_handle = events_output_path.open("w", encoding="utf-8")
            if options.include_provenance and args.provenance_output:
                provenance_output_path = ingest_utils.resolve_repo_path(args.provenance_output)
                provenance_output_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"Streaming provenance records to {provenance_output_path}...")
                provenance_handle = provenance_output_path.open("w", encoding="utf-8")

            build_summary = process_sessions(
                working_inventory,
                options,
                events_handle=events_handle,
                provenance_handle=provenance_handle,
                workers=args.workers,
            )
        finally:
            if events_handle is not None:
                events_handle.close()
            if provenance_handle is not None:
                provenance_handle.close()

        summary.update(build_summary)
        summary["selection"] = selection_info

        if options.include_events and events_output_path is not None:
            print(f"Wrote {summary['events']} events to {events_output_path}.")
        if options.include_provenance and provenance_output_path is not None:
            print(
                "Wrote provenance records for "
                f"{summary.get('provenance_sessions', 0)} sessions to {provenance_output_path}."
            )
    else:
        if args.inventory_only:
            print("Inventory-only mode requested; skipping events and provenance generation.")

    if args.summary_output:
        summary_path = ingest_utils.resolve_repo_path(str(args.summary_output))
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Writing summary report to {summary_path}...")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    processed_sessions = int(summary.get("sessions", 0))
    total_inventory = int(summary.get("inventory_sessions", processed_sessions))
    if processed_sessions and processed_sessions != total_inventory:
        print(
            "Cambridge processing complete: "
            f"{processed_sessions} sessions processed (subset of {total_inventory})."
        )
    else:
        print(f"Cambridge processing complete: {processed_sessions} sessions processed.")
    if summary.get("events"):
        print(
            "Stem-level events created: "
            f"{summary['events']} (labels: {', '.join(f'{k}:{v}' for k, v in summary['labels'].items())})"
        )
    if summary.get("unknown_track_count"):
        print(
            f"Unclassified stems: {summary['unknown_track_count']} (see summary output for samples)."
        )
    if summary.get("missing_file_count"):
        print(f"Missing files skipped: {summary['missing_file_count']}")
    if options.hash_audio:
        print(f"SHA256 digests computed for {summary['hashed_files']} stems.")
    if options.include_events and summary.get("events", 0) == 0:
        print("note: no stems matched known drum components; event manifest is empty.")

    ingest_utils.print_post_ingest_checklist_hint(
        "ingest_cambridge.py",
        events_path=events_output_path,
        manifest_path=events_output_path,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
