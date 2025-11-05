"""Utilities for extracting metadata for a song via tag parsing and acoustic fingerprinting."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import mutagen
except ImportError:  # pragma: no cover - dependency is guaranteed in runtime env
    mutagen = None  # type: ignore

try:
    import acoustid  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    acoustid = None  # type: ignore

@dataclass
class DetectedMetadata:
    """Holds metadata fields discovered for an audio file."""

    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    release_date: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    confidence: Optional[float] = None
    provider: Optional[str] = None

    def merge_into(self, target: Dict[str, object]) -> Dict[str, object]:
        if self.title:
            target.setdefault("title", self.title)
        if self.artist:
            target.setdefault("artist", self.artist)
        if self.album:
            target.setdefault("album", self.album)
        if self.source:
            target.setdefault("source", self.source)
        if self.release_date:
            target.setdefault("release_date", self.release_date)
        if self.tags:
            existing = list(target.get("tags", []))
            for tag in self.tags:
                if tag not in existing:
                    existing.append(tag)
            target["tags"] = existing
        if self.confidence is not None:
            target.setdefault("confidence", self.confidence)
        if self.provider:
            target.setdefault("provider", self.provider)
        return target


def detect_song_metadata(audio_path: str) -> Dict[str, object]:
    """Attempt to discover metadata for ``audio_path``.

    The detection pipeline follows three tiers:
    1. Embedded tags via :mod:`mutagen`.
    2. Acoustic fingerprint lookup via :mod:`pyacoustid` + AcoustID if
       ``ACOUSTID_API_KEY`` (or ``ACOUSTID_KEY``) is present and Chromaprint
       tooling is available.

    Returns a metadata dictionary that may be partially populated. Missing
    values are simply omitted so callers can decide on fallback behaviour.
    """

    metadata: Dict[str, object] = {}

    # --- Tier 1: ID3/Vorbis/etc. tags -------------------------------------------------
    if mutagen is not None:
        try:
            audio = mutagen.File(audio_path, easy=True)
        except Exception as exc:  # pragma: no cover - mutagen quirks
            logging.debug("mutagen failed to read tags for %s: %s", audio_path, exc)
        else:
            if audio is not None:
                title = _first_or_none(audio.get("title"))
                artist = _first_or_none(audio.get("artist"))
                album = _first_or_none(audio.get("album"))
                date = _first_or_none(audio.get("date")) or _first_or_none(audio.get("originaldate"))
                genre = _first_or_none(audio.get("genre"))

                if title:
                    metadata["title"] = title
                if artist:
                    metadata["artist"] = artist
                if album:
                    metadata["album"] = album
                if date:
                    metadata["release_date"] = date
                if genre:
                    metadata.setdefault("tags", []).append(genre)

    # --- Tier 2: AcoustID lookup -------------------------------------------------------
    title_missing = not metadata.get("title")
    artist_missing = not metadata.get("artist")

    api_key = os.getenv("ACOUSTID_API_KEY") or os.getenv("ACOUSTID_KEY")
    if (title_missing or artist_missing) and api_key and acoustid is not None:
        try:
            matches = list(acoustid.match(api_key, audio_path, meta="recordings"))
        except acoustid.NoBackendError:  # type: ignore[attr-defined]
            logging.debug("Chromaprint backend unavailable; skipping acoustic lookup")
        except acoustid.AcoustidError as exc:  # type: ignore[attr-defined]
            logging.debug("AcoustID lookup failed: %s", exc)
        except Exception as exc:  # pragma: no cover - network/decoding issues
            logging.debug("Unexpected AcoustID failure: %s", exc)
        else:
            resolved = _select_best_match(matches, title_missing, artist_missing)
            if resolved is not None:
                resolved.merge_into(metadata)

    metadata.setdefault("provider", metadata.get("provider", "embedded" if metadata else None))
    return metadata


def _select_best_match(matches, want_title: bool, want_artist: bool) -> Optional[DetectedMetadata]:
    if not matches:
        return None

    best: Optional[DetectedMetadata] = None
    best_score = 0.0

    for match in matches:
        # ``match`` is typically (score, recording_id, title, artist) but extra
        # fields may appear depending on the ``meta`` parameter.
        if not match:
            continue

        try:
            score = float(match[0])
        except (ValueError, TypeError):
            score = 0.0

        if score <= best_score:
            continue

        title = None
        artist = None
        if len(match) >= 3:
            title = match[2] or None
        if len(match) >= 4:
            artist = match[3] or None

        if not want_title and not want_artist:
            # We already have both title and artist from tags; prefer not to
            # override unless the acoustic match is exceptionally confident.
            if score < 0.8:
                continue

        best = DetectedMetadata(title=title, artist=artist, confidence=score, provider="acoustid")
        best_score = score

    return best


def _first_or_none(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            if item:
                return str(item)
        return None
    return str(value) if value else None