"""Tests for songs API routes.

These tests validate the CRUD endpoints for songs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.main import app
from app.models.song import Song, SongStatus
from app.models.user import User
from app.services.songs import SongAlreadyExistsError, SongNotFoundError


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
def mock_song() -> Song:
    """Create a mock song object with proper field values."""
    song = MagicMock(spec=Song)
    song.id = uuid.uuid4()
    song.title = "Test Song"
    song.artist = "Test Artist"
    song.album = "Test Album"
    song.bpm = 120
    song.duration_seconds = 180.5
    song.fingerprint_hash = "abc123hash"
    song.audio_url = "https://storage.example.com/audio.mp3"
    song.created_at = datetime.now(timezone.utc)
    song.updated_at = datetime.now(timezone.utc)
    song.user_id = uuid.uuid4()
    # These fields are required for SongRead validation
    song.status = SongStatus.PENDING
    song.canonical_map_id = None
    song.maps = []
    return song


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


class TestCreateSong:
    """Tests for POST /songs endpoint."""

    def test_create_song_success(
        self, client_authenticated: TestClient, mock_song: Song
    ) -> None:
        """Test successful song creation."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.create_song.return_value = mock_song
            MockService.return_value = mock_service

            response = client_authenticated.post(
                "/api/songs",
                json={
                    "title": "Test Song",
                    "artist": "Test Artist",
                    "fingerprint_hash": "abc123hash",
                    "bpm": 120,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"

    def test_create_song_duplicate(self, client_authenticated: TestClient) -> None:
        """Test song creation with duplicate fingerprint."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.create_song.side_effect = SongAlreadyExistsError()
            MockService.return_value = mock_service

            response = client_authenticated.post(
                "/api/songs",
                json={
                    "title": "Duplicate Song",
                    "artist": "Artist",
                    "fingerprint_hash": "duplicate_hash",
                },
            )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_song_unauthenticated(self) -> None:
        """Test song creation without authentication."""
        # Clear any dependency overrides
        app.dependency_overrides.clear()
        client = TestClient(app)

        response = client.post(
            "/api/songs",
            json={
                "title": "Test Song",
                "artist": "Test Artist",
                "fingerprint_hash": "hash123",
            },
        )

        # Should be 401 or 403 depending on auth implementation
        assert response.status_code in (401, 403)


class TestListSongs:
    """Tests for GET /songs endpoint."""

    def test_list_songs_authenticated(
        self, client_authenticated: TestClient, mock_song: Song
    ) -> None:
        """Test listing songs as authenticated user."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_songs.return_value = [mock_song]
            MockService.return_value = mock_service

            response = client_authenticated.get("/api/songs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Song"

    def test_list_songs_anonymous(
        self, client_anonymous: TestClient, mock_song: Song
    ) -> None:
        """Test listing songs as anonymous user."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_songs.return_value = [mock_song]
            MockService.return_value = mock_service

            response = client_anonymous.get("/api/songs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_list_songs_empty(self, client_anonymous: TestClient) -> None:
        """Test listing songs when none exist."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_songs.return_value = []
            MockService.return_value = mock_service

            response = client_anonymous.get("/api/songs")

        assert response.status_code == 200
        assert response.json() == []


class TestGetSong:
    """Tests for GET /songs/{song_id} endpoint."""

    def test_get_song_success(
        self, client_anonymous: TestClient, mock_song: Song
    ) -> None:
        """Test retrieving a song by ID."""
        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_song.return_value = mock_song
            MockService.return_value = mock_service

            response = client_anonymous.get(f"/api/songs/{mock_song.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"

    def test_get_song_not_found(self, client_anonymous: TestClient) -> None:
        """Test retrieving a non-existent song."""
        song_id = uuid.uuid4()

        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_song.side_effect = SongNotFoundError()
            MockService.return_value = mock_service

            response = client_anonymous.get(f"/api/songs/{song_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_song_invalid_uuid(self, client_anonymous: TestClient) -> None:
        """Test retrieving a song with invalid UUID."""
        response = client_anonymous.get("/api/songs/not-a-uuid")

        assert response.status_code == 422


class TestUpdateSong:
    """Tests for PATCH /songs/{song_id} endpoint."""

    def test_update_song_success(
        self, client_authenticated: TestClient, mock_song: Song
    ) -> None:
        """Test successful song update."""
        mock_song.title = "Updated Title"

        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.update_song.return_value = mock_song
            MockService.return_value = mock_service

            response = client_authenticated.patch(
                f"/api/songs/{mock_song.id}",
                json={"title": "Updated Title"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    def test_update_song_not_found(self, client_authenticated: TestClient) -> None:
        """Test updating a non-existent song."""
        song_id = uuid.uuid4()

        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.update_song.side_effect = SongNotFoundError()
            MockService.return_value = mock_service

            response = client_authenticated.patch(
                f"/api/songs/{song_id}",
                json={"title": "New Title"},
            )

        assert response.status_code == 404

    def test_update_song_unauthenticated(self) -> None:
        """Test updating song without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app)
        song_id = uuid.uuid4()

        response = client.patch(
            f"/api/songs/{song_id}",
            json={"title": "New Title"},
        )

        assert response.status_code in (401, 403)


class TestDeleteSong:
    """Tests for DELETE /songs/{song_id} endpoint."""

    def test_delete_song_success(self, client_authenticated: TestClient) -> None:
        """Test successful song deletion."""
        song_id = uuid.uuid4()

        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.delete_song.return_value = None
            MockService.return_value = mock_service

            response = client_authenticated.delete(f"/api/songs/{song_id}")

        assert response.status_code == 204

    def test_delete_song_not_found(self, client_authenticated: TestClient) -> None:
        """Test deleting a non-existent song."""
        song_id = uuid.uuid4()

        with patch("app.api.routes.songs.SongService") as MockService:
            mock_service = AsyncMock()
            mock_service.delete_song.side_effect = SongNotFoundError()
            MockService.return_value = mock_service

            response = client_authenticated.delete(f"/api/songs/{song_id}")

        assert response.status_code == 404

    def test_delete_song_unauthenticated(self) -> None:
        """Test deleting song without authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app)
        song_id = uuid.uuid4()

        response = client.delete(f"/api/songs/{song_id}")

        assert response.status_code in (401, 403)
