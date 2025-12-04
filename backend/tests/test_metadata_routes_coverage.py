"""Extended tests for metadata API routes - Coverage expansion.

These tests add coverage for edge cases and less-tested code paths.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.main import app
from app.models.user import User


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def client_authenticated(mock_user: User, mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_anonymous(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client without authentication."""
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestIdentifyAudioEdgeCases:
    """Edge case tests for POST /metadata/identify endpoint."""

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_with_valid_extension_no_content_type(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification when file has valid extension but no content type."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": None,
            "release_date": None,
            "confidence": 0.8,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": None,
        }

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        # File with .mp3 extension but application/octet-stream content type
        audio_data = b"fake audio content"
        files = {
            "file": ("test.mp3", io.BytesIO(audio_data), "application/octet-stream")
        }

        response = client_authenticated.post("/api/metadata/identify", files=files)

        # Should accept file based on extension
        assert response.status_code == 200

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_file_size_limit(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification rejects files over 100MB."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_get_service.return_value = mock_service

        # Create file just over 100MB (100MB + 1 byte)
        large_data = b"x" * (100 * 1024 * 1024 + 1)
        files = {"file": ("test.mp3", io.BytesIO(large_data), "audio/mpeg")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 413
        assert "100MB" in response.json()["detail"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_with_min_score_parameter(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification with custom min_score parameter."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": None,
            "release_date": None,
            "confidence": 0.7,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": None,
        }

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post(
            "/api/metadata/identify",
            files=files,
            params={"min_score": 0.6},
        )

        assert response.status_code == 200
        # Verify min_score was passed to service
        mock_service.identify_audio_bytes.assert_called_once()
        call_kwargs = mock_service.identify_audio_bytes.call_args.kwargs
        assert call_kwargs["min_score"] == 0.6

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_anonymous_user(
        self,
        mock_get_service: MagicMock,
        client_anonymous: TestClient,
    ) -> None:
        """Test identification without authentication (allowed)."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": None,
            "release_date": None,
            "confidence": 0.9,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": None,
        }

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_anonymous.post("/api/metadata/identify", files=files)

        assert response.status_code == 200


class TestIdentifyFingerprintEdgeCases:
    """Edge case tests for fingerprint identification."""

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_result_without_title(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification when result has no title."""
        mock_result = MagicMock()
        mock_result.score = 0.9
        mock_result.title = None  # No title
        mock_result.artist = None  # No artist
        mock_result.album = None
        mock_result.release_date = None
        mock_result.id = "acoustid-123"
        mock_result.musicbrainz_id = None

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(return_value=[mock_result])
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        # Should return no match since title and artist are both None
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_with_only_artist(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification when result has only artist."""
        mock_result = MagicMock()
        mock_result.score = 0.9
        mock_result.title = None
        mock_result.artist = "Test Artist"  # Only artist
        mock_result.album = None
        mock_result.release_date = None
        mock_result.id = "acoustid-123"
        mock_result.musicbrainz_id = None

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(return_value=[mock_result])
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        # Should return success since artist is present
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["artist"] == "Test Artist"

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_multiple_results_picks_best(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint picks first result above threshold."""
        # First result below threshold
        mock_result1 = MagicMock()
        mock_result1.score = 0.3
        mock_result1.title = "Low Score Song"
        mock_result1.artist = "Artist 1"

        # Second result above threshold
        mock_result2 = MagicMock()
        mock_result2.score = 0.8
        mock_result2.title = "High Score Song"
        mock_result2.artist = "Artist 2"
        mock_result2.album = None
        mock_result2.release_date = None
        mock_result2.id = "acoustid-456"
        mock_result2.musicbrainz_id = None

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(
            return_value=[mock_result1, mock_result2]
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0, "min_score": 0.5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should pick second result (first above threshold)
        assert data["metadata"]["title"] == "High Score Song"


class TestIdentifyWithRetryEdgeCases:
    """Edge case tests for retry identification."""

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_tracks_analytics_on_success(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test analytics tracking when identification succeeds."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": None,
            "release_date": None,
            "confidence": 0.95,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": None,
        }
        mock_result.source = "acoustid"
        mock_result.confidence = 0.95

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        session_id = "test-session-456"
        response = client_authenticated.post(
            f"/api/metadata/identify-with-retry?session_id={session_id}",
            files=files,
        )

        assert response.status_code == 200
        # Verify analytics was called
        mock_analytics.track.assert_called()
        mock_analytics.track_metadata_found.assert_called_once()

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_tracks_analytics_on_no_match(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test analytics tracking when no match found."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service

        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        session_id = "test-session-789"
        response = client_authenticated.post(
            f"/api/metadata/identify-with-retry?session_id={session_id}",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        mock_analytics.track_metadata_not_found.assert_called_once()

    @patch("app.api.routes.metadata.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_retries_on_fingerprint_error(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        mock_sleep: AsyncMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test retry behavior on FingerprintError."""
        from app.services.acoustid import FingerprintError

        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": None,
            "release_date": None,
            "confidence": 0.9,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": None,
        }
        mock_result.source = "acoustid"
        mock_result.confidence = 0.9

        mock_service = MagicMock()
        mock_service.is_available = True
        # Fail first time, succeed second time
        mock_service.identify_audio_bytes = AsyncMock(
            side_effect=[FingerprintError("Transient error"), mock_result]
        )
        mock_get_service.return_value = mock_service

        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
            params={"max_retries": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["attempts"] == 2  # Failed once, succeeded on retry

    @patch("app.api.routes.metadata.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_exhausts_retries(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        mock_sleep: AsyncMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test behavior when all retries are exhausted."""
        from app.services.acoustid import LookupError

        mock_service = MagicMock()
        mock_service.is_available = True
        # Fail all attempts
        mock_service.identify_audio_bytes = AsyncMock(
            side_effect=LookupError("Persistent error")
        )
        mock_get_service.return_value = mock_service

        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
            params={"max_retries": 2},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["retry_exhausted"] is True
        assert data["attempts"] == 2


class TestClearCacheEdgeCases:
    """Edge case tests for cache clearing."""

    @patch("app.services.rbac.RBACService.user_has_any_permission")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_clear_cache_success(
        self,
        mock_get_service: MagicMock,
        mock_has_permission: AsyncMock,
        mock_user: User,
        mock_db_session: AsyncMock,
    ) -> None:
        """Test successful cache clearing with admin permission."""
        mock_has_permission.return_value = True

        mock_service = MagicMock()
        mock_service.clear_cache.return_value = 5
        mock_get_service.return_value = mock_service

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.delete("/api/metadata/cache")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cleared_entries"] == 5
