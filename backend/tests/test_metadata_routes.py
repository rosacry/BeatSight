"""Tests for metadata API routes.

These tests validate audio identification and metadata lookup endpoints.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
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


class TestMetadataStatus:
    """Tests for GET /metadata/status endpoint."""

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_get_status_available(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting service status when available."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.api_key = "test-api-key"
        mock_service._fpcalc_path = "/usr/bin/fpcalc"
        mock_service._cache = {"key1": "value1", "key2": "value2"}
        mock_get_service.return_value = mock_service

        response = client_authenticated.get("/api/metadata/status")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is True
        assert data["has_api_key"] is True
        assert data["has_chromaprint"] is True
        assert data["cache_size"] == 2

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_get_status_unavailable(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting service status when not available."""
        mock_service = MagicMock()
        mock_service.is_available = False
        mock_service.api_key = None
        mock_service._fpcalc_path = None
        mock_service._cache = {}
        mock_get_service.return_value = mock_service

        response = client_authenticated.get("/api/metadata/status")

        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert data["has_api_key"] is False
        assert data["has_chromaprint"] is False


class TestIdentifyAudio:
    """Tests for POST /metadata/identify endpoint."""

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_service_unavailable(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification when service is unavailable."""
        mock_service = MagicMock()
        mock_service.is_available = False
        mock_get_service.return_value = mock_service

        # Create a fake audio file
        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 503
        assert "not available" in response.json()["detail"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_invalid_file_type(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification with invalid file type."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_get_service.return_value = mock_service

        # Create a non-audio file
        text_data = b"this is not audio"
        files = {"file": ("test.txt", io.BytesIO(text_data), "text/plain")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 400
        assert "audio file" in response.json()["detail"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_success(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful audio identification."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "release_date": "2024-01-01",
            "confidence": 0.95,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": "mb-123",
        }

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=mock_result)
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["title"] == "Test Song"
        assert data["metadata"]["artist"] == "Test Artist"

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_no_match(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification with no match found."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["metadata"] is None
        assert "No matching" in data["message"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_audio_error(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test identification when AcoustID raises an error."""
        from app.services.acoustid import AcoustIDError

        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(
            side_effect=AcoustIDError("API rate limit exceeded")
        )
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post("/api/metadata/identify", files=files)

        assert response.status_code == 500


class TestIdentifyFingerprint:
    """Tests for POST /metadata/identify-fingerprint endpoint."""

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_no_api_key(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification without API key."""
        mock_service = MagicMock()
        mock_service.api_key = None
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        assert response.status_code == 503
        assert "API key" in response.json()["detail"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_success(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful fingerprint identification."""
        mock_result = MagicMock()
        mock_result.score = 0.9
        mock_result.title = "Test Song"
        mock_result.artist = "Test Artist"
        mock_result.album = "Test Album"
        mock_result.release_date = "2024-01-01"
        mock_result.id = "acoustid-123"
        mock_result.musicbrainz_id = "mb-123"

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(return_value=[mock_result])
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["title"] == "Test Song"

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_no_match(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification with no match."""
        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(return_value=[])
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No matching" in data["message"]

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_below_threshold(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification with results below threshold."""
        mock_result = MagicMock()
        mock_result.score = 0.3  # Below default 0.5 threshold
        mock_result.title = "Test Song"
        mock_result.artist = "Test Artist"

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(return_value=[mock_result])
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0, "min_score": 0.5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_fingerprint_lookup_error(
        self,
        mock_get_service: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test fingerprint identification with lookup error."""
        from app.services.acoustid import LookupError

        mock_service = MagicMock()
        mock_service.api_key = "test-key"
        mock_service.lookup_fingerprint = AsyncMock(
            side_effect=LookupError("Network timeout")
        )
        mock_get_service.return_value = mock_service

        response = client_authenticated.post(
            "/api/metadata/identify-fingerprint",
            params={"fingerprint": "abc123", "duration": 180.0},
        )

        assert response.status_code == 500


class TestManualMetadata:
    """Tests for POST /metadata/manual endpoint."""

    @patch("app.api.routes.metadata.get_intake_analytics")
    def test_submit_manual_metadata_success(
        self,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test successful manual metadata submission."""
        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        response = client_authenticated.post(
            "/api/metadata/manual",
            json={
                "title": "My Song",
                "artist": "My Artist",
                "album": "My Album",
                "release_date": "2024-01-01",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["title"] == "My Song"
        assert data["metadata"]["artist"] == "My Artist"
        assert data["metadata"]["source"] == "manual"
        assert data["metadata"]["confidence"] == 1.0

    @patch("app.api.routes.metadata.get_intake_analytics")
    def test_submit_manual_metadata_minimal(
        self,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test manual metadata with only required fields."""
        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        response = client_authenticated.post(
            "/api/metadata/manual",
            json={
                "title": "Unknown Song",
                "artist": "Unknown Artist",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["album"] is None

    @patch("app.api.routes.metadata.get_intake_analytics")
    def test_submit_manual_metadata_with_session_id(
        self,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test manual metadata with analytics tracking."""
        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        session_id = "test-session-123"
        response = client_authenticated.post(
            f"/api/metadata/manual?session_id={session_id}",
            json={
                "title": "Test Song",
                "artist": "Test Artist",
            },
        )

        assert response.status_code == 200
        mock_analytics.track_metadata_manual.assert_called_once()

    def test_submit_manual_metadata_missing_required(
        self,
        client_authenticated: TestClient,
    ) -> None:
        """Test manual metadata with missing required fields."""
        response = client_authenticated.post(
            "/api/metadata/manual",
            json={
                "title": "Test Song",
                # Missing artist
            },
        )

        assert response.status_code == 422  # Validation error

    @patch("app.api.routes.metadata.get_intake_analytics")
    def test_submit_manual_metadata_anonymous(
        self,
        mock_get_analytics: MagicMock,
        client_anonymous: TestClient,
    ) -> None:
        """Test manual metadata submission without authentication."""
        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        response = client_anonymous.post(
            "/api/metadata/manual",
            json={
                "title": "Test Song",
                "artist": "Test Artist",
            },
        )

        assert response.status_code == 200


class TestIdentifyWithRetry:
    """Tests for POST /metadata/identify-with-retry endpoint."""

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_service_unavailable(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test retry endpoint when service is unavailable."""
        mock_service = MagicMock()
        mock_service.is_available = False
        mock_get_service.return_value = mock_service

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
        )

        assert response.status_code == 503

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_success_first_attempt(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test retry endpoint succeeding on first attempt."""
        mock_result = MagicMock()
        mock_result.to_dict.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "release_date": "2024-01-01",
            "confidence": 0.95,
            "source": "acoustid",
            "acoustid": "abc123",
            "musicbrainz_id": "mb-123",
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

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["attempts"] == 1
        assert data["retry_exhausted"] is False

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_no_match(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test retry endpoint with no match found."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_service.identify_audio_bytes = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service

        mock_analytics = MagicMock()
        mock_get_analytics.return_value = mock_analytics

        audio_data = b"fake audio content"
        files = {"file": ("test.mp3", io.BytesIO(audio_data), "audio/mpeg")}

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["retry_exhausted"] is False

    @patch("app.api.routes.metadata.get_intake_analytics")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_identify_with_retry_invalid_file_type(
        self,
        mock_get_service: MagicMock,
        mock_get_analytics: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test retry endpoint with invalid file type."""
        mock_service = MagicMock()
        mock_service.is_available = True
        mock_get_service.return_value = mock_service

        text_data = b"this is not audio"
        files = {"file": ("test.txt", io.BytesIO(text_data), "text/plain")}

        response = client_authenticated.post(
            "/api/metadata/identify-with-retry",
            files=files,
        )

        assert response.status_code == 400


class TestClearCache:
    """Tests for DELETE /metadata/cache endpoint."""

    @patch("app.services.rbac.RBACService.user_has_any_permission")
    @patch("app.api.routes.metadata.get_acoustid_service")
    def test_clear_cache_unauthorized(
        self,
        mock_get_service: MagicMock,
        mock_has_permission: AsyncMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test cache clearing without admin permissions returns 403."""
        # Mock permission check to return False (no admin permission)
        mock_has_permission.return_value = False
        
        response = client_authenticated.delete("/api/metadata/cache")

        # Without admin permission, should return 403
        assert response.status_code == 403
