"""
Tests for the AcoustID audio fingerprinting service.

Ticket E1-007: AcoustID Integration
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.acoustid import (
    AcoustIDService,
    AudioFingerprint,
    AcoustIDResult,
    MetadataResult,
    FingerprintError,
    LookupError,
    _RateLimiter,
)


# =============================================================================
# AudioFingerprint Tests
# =============================================================================


class TestAudioFingerprint:
    """Tests for AudioFingerprint dataclass."""
    
    def test_create_fingerprint(self):
        """Create a fingerprint with duration and data."""
        fp = AudioFingerprint(duration=120.5, fingerprint="AQAA1234...")
        
        assert fp.duration == 120.5
        assert fp.fingerprint == "AQAA1234..."
    
    def test_fingerprint_hash(self):
        """Fingerprint hash should be consistent."""
        fp1 = AudioFingerprint(duration=120, fingerprint="AQAA1234")
        fp2 = AudioFingerprint(duration=180, fingerprint="AQAA1234")  # Different duration
        fp3 = AudioFingerprint(duration=120, fingerprint="AQAA5678")  # Different fingerprint
        
        # Same fingerprint data = same hash
        assert fp1.fingerprint_hash() == fp2.fingerprint_hash()
        
        # Different fingerprint = different hash
        assert fp1.fingerprint_hash() != fp3.fingerprint_hash()
    
    def test_fingerprint_hash_length(self):
        """Hash should be a fixed length."""
        fp = AudioFingerprint(duration=120, fingerprint="test")
        
        assert len(fp.fingerprint_hash()) == 32


# =============================================================================
# AcoustIDResult Tests
# =============================================================================


class TestAcoustIDResult:
    """Tests for AcoustIDResult dataclass."""
    
    def test_create_result(self):
        """Create a result with all fields."""
        result = AcoustIDResult(
            id="abc123",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            release_date="2024-01-01",
            score=0.95,
            musicbrainz_id="mb-123",
            duration=180,
        )
        
        assert result.id == "abc123"
        assert result.title == "Test Song"
        assert result.score == 0.95
    
    def test_from_api_response_basic(self):
        """Parse from API response with basic data."""
        api_result = {"id": "acid-123", "score": 0.87}
        recording = {
            "id": "mb-rec-456",
            "title": "Song Title",
            "artists": [{"name": "Artist Name"}],
            "duration": 240,
        }
        
        result = AcoustIDResult.from_api_response(api_result, recording)
        
        assert result.id == "acid-123"
        assert result.title == "Song Title"
        assert result.artist == "Artist Name"
        assert result.score == 0.87
        assert result.musicbrainz_id == "mb-rec-456"
        assert result.duration == 240
    
    def test_from_api_response_multiple_artists(self):
        """Parse response with multiple artists."""
        api_result = {"id": "acid-123", "score": 0.9}
        recording = {
            "id": "mb-rec-456",
            "title": "Collaboration",
            "artists": [
                {"name": "Artist A"},
                {"name": "Artist B"},
                {"name": "Artist C"},
            ],
        }
        
        result = AcoustIDResult.from_api_response(api_result, recording)
        
        assert result.artist == "Artist A, Artist B, Artist C"
    
    def test_from_api_response_with_release(self):
        """Parse response with release group info."""
        api_result = {"id": "acid-123", "score": 0.85}
        recording = {
            "id": "mb-rec-456",
            "title": "Track",
            "artists": [{"name": "Band"}],
            "releasegroups": [
                {
                    "title": "Album Name",
                    "first-release-date": "2020-06-15",
                }
            ],
        }
        
        result = AcoustIDResult.from_api_response(api_result, recording)
        
        assert result.album == "Album Name"
        assert result.release_date == "2020-06-15"
    
    def test_from_api_response_missing_fields(self):
        """Parse response with missing optional fields."""
        api_result = {"id": "acid-123"}
        recording = {"id": "mb-rec-456"}
        
        result = AcoustIDResult.from_api_response(api_result, recording)
        
        assert result.id == "acid-123"
        assert result.title is None
        assert result.artist is None
        assert result.score == 0.0


# =============================================================================
# MetadataResult Tests
# =============================================================================


class TestMetadataResult:
    """Tests for MetadataResult dataclass."""
    
    def test_to_dict_all_fields(self):
        """Convert to dict with all fields."""
        result = MetadataResult(
            title="Song",
            artist="Artist",
            album="Album",
            release_date="2024-01-01",
            confidence=0.95,
            source="acoustid",
            acoustid="acid-123",
            musicbrainz_id="mb-456",
        )
        
        d = result.to_dict()
        
        assert d["title"] == "Song"
        assert d["artist"] == "Artist"
        assert d["confidence"] == 0.95
        assert d["source"] == "acoustid"
    
    def test_to_dict_excludes_none(self):
        """Convert to dict excludes None values."""
        result = MetadataResult(
            title="Song",
            artist=None,
            album=None,
            release_date=None,
            confidence=0.8,
            source="acoustid",
        )
        
        d = result.to_dict()
        
        assert "title" in d
        assert "artist" not in d
        assert "album" not in d
        assert "confidence" in d


# =============================================================================
# RateLimiter Tests
# =============================================================================


class TestRateLimiter:
    """Tests for the rate limiter."""
    
    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self):
        """Requests within limit should not be delayed."""
        limiter = _RateLimiter(max_requests=3, window=1.0)
        
        start = datetime.utcnow()
        
        # Should complete quickly
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        elapsed = (datetime.utcnow() - start).total_seconds()
        assert elapsed < 0.5  # Should be near-instant
    
    @pytest.mark.asyncio
    async def test_delays_when_at_limit(self):
        """Requests exceeding limit should be delayed."""
        limiter = _RateLimiter(max_requests=2, window=0.5)
        
        # Fill the quota
        await limiter.acquire()
        await limiter.acquire()
        
        start = datetime.utcnow()
        
        # This should wait
        await limiter.acquire()
        
        elapsed = (datetime.utcnow() - start).total_seconds()
        # Should have waited approximately 0.5 seconds
        assert elapsed >= 0.4


# =============================================================================
# AcoustIDService Tests
# =============================================================================


class TestAcoustIDService:
    """Tests for the AcoustIDService class."""
    
    def test_init_without_api_key(self):
        """Service initializes without API key."""
        with patch.dict("os.environ", {}, clear=True):
            service = AcoustIDService(api_key=None)
            assert service.api_key is None
    
    def test_init_with_api_key(self):
        """Service initializes with API key."""
        service = AcoustIDService(api_key="test-key")
        assert service.api_key == "test-key"
    
    def test_init_from_env_acoustid_api_key(self):
        """Service reads from ACOUSTID_API_KEY env var."""
        with patch.dict("os.environ", {"ACOUSTID_API_KEY": "env-key"}):
            service = AcoustIDService()
            assert service.api_key == "env-key"
    
    def test_init_from_env_acoustid_key(self):
        """Service reads from ACOUSTID_KEY env var as fallback."""
        with patch.dict("os.environ", {"ACOUSTID_KEY": "fallback-key"}, clear=True):
            service = AcoustIDService()
            assert service.api_key == "fallback-key"
    
    def test_is_available_without_config(self):
        """Service not available without API key or fpcalc."""
        with patch.dict("os.environ", {}, clear=True):
            service = AcoustIDService(api_key=None)
            service._fpcalc_path = None
            assert service.is_available is False
    
    def test_is_available_with_config(self):
        """Service available with API key and fpcalc."""
        service = AcoustIDService(api_key="test-key")
        service._fpcalc_path = "/usr/bin/fpcalc"
        assert service.is_available is True
    
    @pytest.mark.asyncio
    async def test_generate_fingerprint_no_fpcalc(self):
        """Fingerprint generation fails without fpcalc."""
        service = AcoustIDService(api_key="test-key")
        service._fpcalc_path = None
        
        with pytest.raises(FingerprintError, match="fpcalc not available"):
            await service.generate_fingerprint("/path/to/audio.mp3")
    
    @pytest.mark.asyncio
    async def test_generate_fingerprint_file_not_found(self):
        """Fingerprint generation fails for missing file."""
        service = AcoustIDService(api_key="test-key")
        service._fpcalc_path = "/usr/bin/fpcalc"
        
        with pytest.raises(FingerprintError, match="not found"):
            await service.generate_fingerprint("/nonexistent/audio.mp3")
    
    @pytest.mark.asyncio
    async def test_lookup_fingerprint_no_api_key(self):
        """Lookup fails without API key."""
        service = AcoustIDService(api_key=None)
        fp = AudioFingerprint(duration=120, fingerprint="test")
        
        with pytest.raises(LookupError, match="API key not configured"):
            await service.lookup_fingerprint(fp)
    
    @pytest.mark.asyncio
    async def test_lookup_fingerprint_success(self):
        """Successful fingerprint lookup."""
        service = AcoustIDService(api_key="test-key")
        fp = AudioFingerprint(duration=120, fingerprint="AQAA1234")
        
        mock_response = {
            "status": "ok",
            "results": [
                {
                    "id": "acid-123",
                    "score": 0.95,
                    "recordings": [
                        {
                            "id": "mb-456",
                            "title": "Test Song",
                            "artists": [{"name": "Test Artist"}],
                        }
                    ],
                }
            ],
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response_obj
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance
            
            results = await service.lookup_fingerprint(fp)
            
            assert len(results) == 1
            assert results[0].id == "acid-123"
            assert results[0].title == "Test Song"
            assert results[0].score == 0.95
    
    @pytest.mark.asyncio
    async def test_lookup_fingerprint_api_error(self):
        """Handle API error response."""
        service = AcoustIDService(api_key="test-key")
        fp = AudioFingerprint(duration=120, fingerprint="AQAA1234")
        
        mock_response = {
            "status": "error",
            "error": {"message": "Invalid API key"},
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_response_obj = MagicMock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = MagicMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response_obj
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance
            
            with pytest.raises(LookupError, match="Invalid API key"):
                await service.lookup_fingerprint(fp)
    
    @pytest.mark.asyncio
    async def test_lookup_uses_cache(self):
        """Subsequent lookups use cache."""
        service = AcoustIDService(api_key="test-key", cache_ttl=3600)
        fp = AudioFingerprint(duration=120, fingerprint="AQAA1234")
        
        # Pre-populate cache
        cached_result = AcoustIDResult(
            id="cached",
            title="Cached Song",
            artist="Cached Artist",
            album=None,
            release_date=None,
            score=0.99,
            musicbrainz_id=None,
            duration=120,
        )
        cache_key = fp.fingerprint_hash()
        service._cache[cache_key] = (datetime.utcnow(), [cached_result])
        
        # Should return cached result without API call
        with patch("httpx.AsyncClient") as mock_client:
            results = await service.lookup_fingerprint(fp)
            mock_client.assert_not_called()
            
            assert len(results) == 1
            assert results[0].id == "cached"
    
    def test_clear_cache(self):
        """Clear cache returns count and empties cache."""
        service = AcoustIDService(api_key="test-key")
        
        # Add some cache entries
        service._cache["key1"] = (datetime.utcnow(), [])
        service._cache["key2"] = (datetime.utcnow(), [])
        service._cache["key3"] = (datetime.utcnow(), [])
        
        cleared = service.clear_cache()
        
        assert cleared == 3
        assert len(service._cache) == 0
    
    @pytest.mark.asyncio
    async def test_identify_audio_not_available(self):
        """identify_audio returns None when service not available."""
        service = AcoustIDService(api_key=None)
        service._fpcalc_path = None
        
        result = await service.identify_audio("/path/to/audio.mp3")
        
        assert result is None


# =============================================================================
# API Route Tests
# =============================================================================


class TestMetadataRoutes:
    """Tests for metadata API routes."""
    
    def test_status_endpoint(self):
        """Status endpoint returns service info."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.get("/api/metadata/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "has_api_key" in data
        assert "has_chromaprint" in data
        assert "cache_size" in data
