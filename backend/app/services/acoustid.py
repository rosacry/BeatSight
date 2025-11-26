"""
AcoustID audio fingerprinting service.

Ticket E1-007: AcoustID Integration
- Audio fingerprint generation and lookup
- MusicBrainz metadata retrieval
- Caching layer for API responses
- Rate limiting compliance
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)

# AcoustID API configuration
ACOUSTID_API_URL = "https://api.acoustid.org/v2/lookup"
ACOUSTID_FINGERPRINT_URL = "https://api.acoustid.org/v2/submit"

# Rate limiting: AcoustID allows 3 requests per second
RATE_LIMIT_REQUESTS = 3
RATE_LIMIT_WINDOW = 1.0  # seconds


@dataclass
class AudioFingerprint:
    """Audio fingerprint data from Chromaprint."""
    
    duration: float  # seconds
    fingerprint: str  # Base64-encoded Chromaprint fingerprint
    
    def fingerprint_hash(self) -> str:
        """Generate a hash of the fingerprint for caching."""
        return hashlib.sha256(self.fingerprint.encode()).hexdigest()[:32]


@dataclass
class AcoustIDResult:
    """Result from AcoustID lookup."""
    
    id: str  # AcoustID recording ID
    title: str | None
    artist: str | None
    album: str | None
    release_date: str | None
    score: float  # Confidence score 0-1
    musicbrainz_id: str | None  # MusicBrainz recording ID
    duration: int | None  # Track duration in seconds
    
    @classmethod
    def from_api_response(cls, result: dict, recording: dict) -> "AcoustIDResult":
        """Create from AcoustID API response data."""
        # Extract artists
        artists = recording.get("artists", [])
        artist_names = [a.get("name") for a in artists if a.get("name")]
        artist = ", ".join(artist_names) if artist_names else None
        
        # Extract release info
        releases = recording.get("releasegroups", [])
        album = None
        release_date = None
        if releases:
            first_release = releases[0]
            album = first_release.get("title")
            # Get earliest release date
            secondarytypes = first_release.get("secondarytypes", [])
            if not secondarytypes or "Compilation" not in secondarytypes:
                release_date = first_release.get("first-release-date")
        
        return cls(
            id=result.get("id", ""),
            title=recording.get("title"),
            artist=artist,
            album=album,
            release_date=release_date,
            score=result.get("score", 0.0),
            musicbrainz_id=recording.get("id"),
            duration=recording.get("duration"),
        )


@dataclass
class MetadataResult:
    """Combined metadata result."""
    
    title: str | None
    artist: str | None
    album: str | None
    release_date: str | None
    confidence: float
    source: str
    acoustid: str | None = None
    musicbrainz_id: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class AcoustIDError(Exception):
    """Base exception for AcoustID operations."""
    pass


class FingerprintError(AcoustIDError):
    """Error generating audio fingerprint."""
    pass


class LookupError(AcoustIDError):
    """Error looking up fingerprint."""
    pass


class AcoustIDService:
    """
    Service for audio fingerprinting and metadata lookup via AcoustID.
    
    Uses Chromaprint for fingerprint generation and the AcoustID API
    for metadata lookup against the MusicBrainz database.
    """
    
    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl: int = 86400,  # 24 hours
    ):
        """
        Initialize the AcoustID service.
        
        Args:
            api_key: AcoustID API key. Falls back to ACOUSTID_API_KEY env var.
            cache_ttl: Cache TTL in seconds for lookup results.
        """
        settings = get_settings()
        self.api_key = api_key or os.getenv("ACOUSTID_API_KEY") or os.getenv("ACOUSTID_KEY")
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[datetime, list[AcoustIDResult]]] = {}
        self._rate_limiter = _RateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW)
        
        # Check for fpcalc binary (Chromaprint)
        self._fpcalc_path = self._find_fpcalc()
    
    def _find_fpcalc(self) -> str | None:
        """Find the fpcalc binary for fingerprint generation."""
        # Check common locations
        paths_to_check = [
            "fpcalc",  # In PATH
            "/usr/bin/fpcalc",
            "/usr/local/bin/fpcalc",
            "C:\\Program Files\\Chromaprint\\fpcalc.exe",
            "C:\\Program Files (x86)\\Chromaprint\\fpcalc.exe",
        ]
        
        for path in paths_to_check:
            try:
                result = subprocess.run(
                    [path, "-version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    logger.debug("Found fpcalc at: %s", path)
                    return path
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                continue
        
        logger.warning("fpcalc not found - fingerprinting will be unavailable")
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self.api_key and self._fpcalc_path)
    
    async def generate_fingerprint(
        self,
        audio_path: str,
        duration: int = 120,  # Analyze first 2 minutes
    ) -> AudioFingerprint:
        """
        Generate an audio fingerprint using Chromaprint.
        
        Args:
            audio_path: Path to the audio file.
            duration: Maximum duration to analyze (seconds).
            
        Returns:
            AudioFingerprint with duration and fingerprint data.
            
        Raises:
            FingerprintError: If fingerprint generation fails.
        """
        if not self._fpcalc_path:
            raise FingerprintError("fpcalc not available - install Chromaprint")
        
        if not os.path.exists(audio_path):
            raise FingerprintError(f"Audio file not found: {audio_path}")
        
        try:
            # Run fpcalc in a thread to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [self._fpcalc_path, "-json", "-length", str(duration), audio_path],
                    capture_output=True,
                    timeout=60,
                ),
            )
            
            if result.returncode != 0:
                error = result.stderr.decode() if result.stderr else "Unknown error"
                raise FingerprintError(f"fpcalc failed: {error}")
            
            output = json.loads(result.stdout.decode())
            
            return AudioFingerprint(
                duration=output.get("duration", 0),
                fingerprint=output.get("fingerprint", ""),
            )
            
        except json.JSONDecodeError as e:
            raise FingerprintError(f"Invalid fpcalc output: {e}")
        except subprocess.TimeoutExpired:
            raise FingerprintError("Fingerprint generation timed out")
        except Exception as e:
            raise FingerprintError(f"Fingerprint generation failed: {e}")
    
    async def lookup_fingerprint(
        self,
        fingerprint: AudioFingerprint,
        include_metadata: bool = True,
    ) -> list[AcoustIDResult]:
        """
        Look up an audio fingerprint in the AcoustID database.
        
        Args:
            fingerprint: The audio fingerprint to look up.
            include_metadata: Whether to include MusicBrainz metadata.
            
        Returns:
            List of matching recordings, sorted by confidence.
            
        Raises:
            LookupError: If the API request fails.
        """
        if not self.api_key:
            raise LookupError("AcoustID API key not configured")
        
        # Check cache
        cache_key = fingerprint.fingerprint_hash()
        if cache_key in self._cache:
            cached_time, cached_results = self._cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl):
                logger.debug("Cache hit for fingerprint: %s", cache_key[:8])
                return cached_results
        
        # Rate limiting
        await self._rate_limiter.acquire()
        
        # Build request
        params = {
            "client": self.api_key,
            "duration": int(fingerprint.duration),
            "fingerprint": fingerprint.fingerprint,
            "format": "json",
        }
        
        if include_metadata:
            # Request recording metadata from MusicBrainz
            params["meta"] = "recordings releasegroups"
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(ACOUSTID_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            if data.get("status") != "ok":
                error = data.get("error", {}).get("message", "Unknown error")
                raise LookupError(f"AcoustID API error: {error}")
            
            # Parse results
            results: list[AcoustIDResult] = []
            for result in data.get("results", []):
                recordings = result.get("recordings", [])
                if recordings:
                    # Use the first recording (usually best match)
                    for recording in recordings[:3]:  # Top 3 recordings per result
                        parsed = AcoustIDResult.from_api_response(result, recording)
                        results.append(parsed)
            
            # Sort by score descending
            results.sort(key=lambda r: r.score, reverse=True)
            
            # Cache results
            self._cache[cache_key] = (datetime.utcnow(), results)
            
            logger.info(
                "AcoustID lookup complete",
                fingerprint=cache_key[:8],
                results=len(results),
                top_score=results[0].score if results else 0,
            )
            
            return results
            
        except httpx.HTTPStatusError as e:
            raise LookupError(f"AcoustID API HTTP error: {e}")
        except httpx.RequestError as e:
            raise LookupError(f"AcoustID API request failed: {e}")
        except Exception as e:
            raise LookupError(f"AcoustID lookup failed: {e}")
    
    async def identify_audio(
        self,
        audio_path: str,
        min_score: float = 0.5,
    ) -> MetadataResult | None:
        """
        Identify audio and return metadata.
        
        This is the main entry point for audio identification.
        
        Args:
            audio_path: Path to the audio file.
            min_score: Minimum confidence score to accept (0-1).
            
        Returns:
            MetadataResult if a confident match is found, None otherwise.
        """
        if not self.is_available:
            logger.warning("AcoustID service not available")
            return None
        
        try:
            # Generate fingerprint
            fingerprint = await self.generate_fingerprint(audio_path)
            
            # Look up in database
            results = await self.lookup_fingerprint(fingerprint)
            
            if not results:
                logger.debug("No AcoustID matches found for: %s", audio_path)
                return None
            
            # Find best result above threshold
            for result in results:
                if result.score >= min_score and (result.title or result.artist):
                    return MetadataResult(
                        title=result.title,
                        artist=result.artist,
                        album=result.album,
                        release_date=result.release_date,
                        confidence=result.score,
                        source="acoustid",
                        acoustid=result.id,
                        musicbrainz_id=result.musicbrainz_id,
                    )
            
            logger.debug(
                "No AcoustID matches above threshold",
                path=audio_path,
                min_score=min_score,
                top_score=results[0].score if results else 0,
            )
            return None
            
        except AcoustIDError as e:
            logger.error("AcoustID identification failed", error=str(e), path=audio_path)
            return None
    
    async def identify_audio_bytes(
        self,
        audio_data: bytes,
        filename: str = "audio.mp3",
        min_score: float = 0.5,
    ) -> MetadataResult | None:
        """
        Identify audio from bytes.
        
        Writes to a temporary file for processing.
        
        Args:
            audio_data: Raw audio file bytes.
            filename: Original filename (for extension).
            min_score: Minimum confidence score.
            
        Returns:
            MetadataResult if found, None otherwise.
        """
        ext = Path(filename).suffix or ".mp3"
        
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            return await self.identify_audio(temp_path, min_score)
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    
    def clear_cache(self) -> int:
        """Clear the lookup cache. Returns number of entries cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count


class _RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, max_requests: int, window: float):
        self.max_requests = max_requests
        self.window = window
        self._requests: list[datetime] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire a request slot, waiting if necessary."""
        async with self._lock:
            now = datetime.utcnow()
            
            # Remove old requests outside the window
            cutoff = now - timedelta(seconds=self.window)
            self._requests = [t for t in self._requests if t > cutoff]
            
            # Wait if at limit
            if len(self._requests) >= self.max_requests:
                oldest = self._requests[0]
                wait_time = (oldest + timedelta(seconds=self.window) - now).total_seconds()
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self._requests.append(datetime.utcnow())


# Singleton instance
_service: AcoustIDService | None = None


def get_acoustid_service() -> AcoustIDService:
    """Get the shared AcoustID service instance."""
    global _service
    if _service is None:
        _service = AcoustIDService()
    return _service
