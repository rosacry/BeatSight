"""Comprehensive tests for maps API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.maps import (
    DuplicateVerifiedMapError,
    MapNotFoundError,
    MapService,
    SongNotFoundError,
)
from app.services.rbac import RBACService


# =============================================================================
# Test Fixtures
# =============================================================================

def create_mock_user(user_id: uuid.UUID | None = None) -> MagicMock:
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = user_id or uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    return user


def create_mock_map(
    map_id: uuid.UUID | None = None,
    song_id: uuid.UUID | None = None,
    difficulty_label: str = "Expert",
    state: str = "VERIFIED",
    is_canonical: bool = True,
) -> MagicMock:
    """Create a mock map object."""
    mock_map = MagicMock()
    mock_map.id = map_id or uuid.uuid4()
    mock_map.song_id = song_id or uuid.uuid4()
    mock_map.difficulty_label = difficulty_label
    mock_map.state = MagicMock()
    mock_map.state.value = state
    mock_map.is_canonical = is_canonical
    mock_map.created_at = datetime.utcnow()
    mock_map.updated_at = datetime.utcnow()
    return mock_map


def create_mock_song(
    song_id: uuid.UUID | None = None,
    canonical_map_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a mock song object."""
    mock_song = MagicMock()
    mock_song.id = song_id or uuid.uuid4()
    mock_song.canonical_map_id = canonical_map_id
    return mock_song


def create_mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# =============================================================================
# Test Get Map
# =============================================================================

class TestGetMap:
    """Tests for GET /maps/{map_id} endpoint."""

    def test_get_map_success(self):
        """Test successfully getting a map."""
        map_id = uuid.uuid4()
        song_id = uuid.uuid4()
        mock_map = create_mock_map(map_id=map_id, song_id=song_id)
        
        with patch.object(MapService, "get_map", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_map
            
            client = TestClient(app)
            response = client.get(f"/api/maps/{map_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(map_id)
            assert data["song_id"] == str(song_id)
            assert data["difficulty_label"] == "Expert"
            assert data["state"] == "VERIFIED"
            assert data["is_canonical"] == True

    def test_get_map_not_found(self):
        """Test getting a non-existent map."""
        map_id = uuid.uuid4()
        
        with patch.object(MapService, "get_map", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = MapNotFoundError(f"Map {map_id} not found")
            
            client = TestClient(app)
            response = client.get(f"/api/maps/{map_id}")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_map_invalid_uuid(self):
        """Test getting a map with invalid UUID."""
        client = TestClient(app)
        response = client.get("/api/maps/not-a-uuid")
        
        assert response.status_code == 422

    def test_get_map_various_states(self):
        """Test getting maps in various states."""
        states = ["UNVERIFIED", "VERIFIED", "ARCHIVED", "PENDING"]
        
        for state in states:
            map_id = uuid.uuid4()
            mock_map = create_mock_map(map_id=map_id, state=state)
            
            with patch.object(MapService, "get_map", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_map
                
                client = TestClient(app)
                response = client.get(f"/api/maps/{map_id}")
                
                assert response.status_code == 200
                assert response.json()["state"] == state


# =============================================================================
# Test Get Song Maps
# =============================================================================

class TestGetSongMaps:
    """Tests for GET /maps/song/{song_id} endpoint."""

    def test_get_song_maps_success(self):
        """Test successfully getting all maps for a song."""
        song_id = uuid.uuid4()
        canonical_map_id = uuid.uuid4()
        mock_song = create_mock_song(song_id=song_id, canonical_map_id=canonical_map_id)
        
        maps = [
            create_mock_map(map_id=canonical_map_id, song_id=song_id, difficulty_label="Expert"),
            create_mock_map(song_id=song_id, difficulty_label="Hard", is_canonical=False),
        ]
        
        with patch.object(MapService, "get_song", new_callable=AsyncMock) as mock_get_song, \
             patch.object(MapService, "get_song_maps", new_callable=AsyncMock) as mock_get_maps:
            mock_get_song.return_value = mock_song
            mock_get_maps.return_value = maps
            
            client = TestClient(app)
            response = client.get(f"/api/maps/song/{song_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["song_id"] == str(song_id)
            assert data["canonical_map_id"] == str(canonical_map_id)
            assert len(data["maps"]) == 2

    def test_get_song_maps_not_found(self):
        """Test getting maps for a non-existent song."""
        song_id = uuid.uuid4()
        
        with patch.object(MapService, "get_song", new_callable=AsyncMock) as mock_get_song:
            mock_get_song.side_effect = SongNotFoundError(f"Song {song_id} not found")
            
            client = TestClient(app)
            response = client.get(f"/api/maps/song/{song_id}")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_song_maps_empty(self):
        """Test getting maps for a song with no maps."""
        song_id = uuid.uuid4()
        mock_song = create_mock_song(song_id=song_id, canonical_map_id=None)
        
        with patch.object(MapService, "get_song", new_callable=AsyncMock) as mock_get_song, \
             patch.object(MapService, "get_song_maps", new_callable=AsyncMock) as mock_get_maps:
            mock_get_song.return_value = mock_song
            mock_get_maps.return_value = []
            
            client = TestClient(app)
            response = client.get(f"/api/maps/song/{song_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["maps"]) == 0
            assert data["canonical_map_id"] is None

    def test_get_song_maps_include_archived(self):
        """Test getting maps including archived ones."""
        song_id = uuid.uuid4()
        mock_song = create_mock_song(song_id=song_id)
        
        maps = [
            create_mock_map(song_id=song_id, state="VERIFIED"),
            create_mock_map(song_id=song_id, state="ARCHIVED"),
        ]
        
        with patch.object(MapService, "get_song", new_callable=AsyncMock) as mock_get_song, \
             patch.object(MapService, "get_song_maps", new_callable=AsyncMock) as mock_get_maps:
            mock_get_song.return_value = mock_song
            mock_get_maps.return_value = maps
            
            client = TestClient(app)
            response = client.get(f"/api/maps/song/{song_id}?include_archived=true")
            
            assert response.status_code == 200
            mock_get_maps.assert_called_once()
            call_kwargs = mock_get_maps.call_args
            # Verify include_archived was passed
            assert call_kwargs[1]["include_archived"] == True

    def test_get_song_maps_invalid_uuid(self):
        """Test getting maps for song with invalid UUID."""
        client = TestClient(app)
        response = client.get("/api/maps/song/not-a-uuid")
        
        assert response.status_code == 422


# =============================================================================
# Test Verify Map - Authentication/Authorization
# =============================================================================

class TestVerifyMap:
    """Tests for POST /maps/{map_id}/verify endpoint."""

    def test_verify_map_requires_auth(self):
        """Test verify map requires authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        map_id = uuid.uuid4()
        response = client.post(
            f"/api/maps/{map_id}/verify",
            json={"force": False}
        )
        
        # Should require authentication/permission
        assert response.status_code in [401, 403]

    def test_verify_map_endpoint_exists(self):
        """Test that verify map endpoint exists and accepts requests."""
        # This test verifies the endpoint routing without full auth
        map_id = uuid.uuid4()
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        response = client.post(
            f"/api/maps/{map_id}/verify",
            json={"force": False}
        )
        
        # Not a 404 (endpoint exists), but auth required
        assert response.status_code != 404

    def test_verify_map_invalid_uuid(self):
        """Test verify map with invalid UUID."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/maps/invalid-uuid/verify",
            json={"force": False}
        )
        
        # Should be 422 (validation error) or auth error
        assert response.status_code in [422, 401, 403]

    def test_verify_map_invalid_body(self):
        """Test verify map with invalid request body."""
        map_id = uuid.uuid4()
        client = TestClient(app, raise_server_exceptions=False)
        
        response = client.post(
            f"/api/maps/{map_id}/verify",
            json={"force": "not-a-boolean"}
        )
        
        # Should be 422 (validation) or auth error
        assert response.status_code in [422, 401, 403]


# =============================================================================
# Test Unverify Map - Authentication/Authorization
# =============================================================================

class TestUnverifyMap:
    """Tests for POST /maps/{map_id}/unverify endpoint."""

    def test_unverify_map_requires_auth(self):
        """Test unverify map requires authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        map_id = uuid.uuid4()
        response = client.post(f"/api/maps/{map_id}/unverify")
        
        assert response.status_code in [401, 403]

    def test_unverify_map_endpoint_exists(self):
        """Test that unverify map endpoint exists."""
        map_id = uuid.uuid4()
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        response = client.post(f"/api/maps/{map_id}/unverify")
        
        # Not a 404 (endpoint exists)
        assert response.status_code != 404

    def test_unverify_map_invalid_uuid(self):
        """Test unverify map with invalid UUID."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/maps/invalid-uuid/unverify")
        
        # Should be 422 (validation error) or auth error
        assert response.status_code in [422, 401, 403]


# =============================================================================
# Test Archive Map - Authentication/Authorization
# =============================================================================

class TestArchiveMap:
    """Tests for POST /maps/{map_id}/archive endpoint."""

    def test_archive_map_requires_auth(self):
        """Test archive map requires authentication."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        map_id = uuid.uuid4()
        response = client.post(f"/api/maps/{map_id}/archive")
        
        assert response.status_code in [401, 403]

    def test_archive_map_endpoint_exists(self):
        """Test that archive map endpoint exists."""
        map_id = uuid.uuid4()
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        
        response = client.post(f"/api/maps/{map_id}/archive")
        
        # Not a 404 (endpoint exists)
        assert response.status_code != 404

    def test_archive_map_invalid_uuid(self):
        """Test archive map with invalid UUID."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/maps/invalid-uuid/archive")
        
        # Should be 422 (validation error) or auth error
        assert response.status_code in [422, 401, 403]


# =============================================================================
# Test Validation Errors
# =============================================================================

class TestMapsValidation:
    """Validation tests for maps routes."""

    def test_invalid_map_id_format(self):
        """Test various invalid map ID formats."""
        invalid_ids = ["abc", "123", "not-a-uuid"]
        
        client = TestClient(app)
        for invalid_id in invalid_ids:
            response = client.get(f"/api/maps/{invalid_id}")
            assert response.status_code == 422

    def test_invalid_song_id_format(self):
        """Test various invalid song ID formats."""
        invalid_ids = ["abc", "123", "not-a-uuid"]
        
        client = TestClient(app)
        for invalid_id in invalid_ids:
            response = client.get(f"/api/maps/song/{invalid_id}")
            assert response.status_code == 422


# =============================================================================
# Test Map Response Format
# =============================================================================

class TestMapResponseFormat:
    """Tests for map response format and structure."""

    def test_map_response_has_all_fields(self):
        """Test that map response includes all required fields."""
        map_id = uuid.uuid4()
        song_id = uuid.uuid4()
        now = datetime.utcnow()
        
        mock_map = create_mock_map(
            map_id=map_id,
            song_id=song_id,
            difficulty_label="Expert Plus",
            state="VERIFIED",
            is_canonical=True,
        )
        mock_map.created_at = now
        mock_map.updated_at = now
        
        with patch.object(MapService, "get_map", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_map
            
            client = TestClient(app)
            response = client.get(f"/api/maps/{map_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check all fields are present
            required_fields = [
                "id", "song_id", "difficulty_label", 
                "state", "is_canonical", "created_at", "updated_at"
            ]
            for field in required_fields:
                assert field in data, f"Missing field: {field}"

    def test_map_list_response_format(self):
        """Test that map list response has correct format."""
        song_id = uuid.uuid4()
        canonical_id = uuid.uuid4()
        
        mock_song = create_mock_song(song_id=song_id, canonical_map_id=canonical_id)
        maps = [
            create_mock_map(map_id=canonical_id, song_id=song_id),
            create_mock_map(song_id=song_id),
        ]
        
        with patch.object(MapService, "get_song", new_callable=AsyncMock) as mock_get_song, \
             patch.object(MapService, "get_song_maps", new_callable=AsyncMock) as mock_get_maps:
            mock_get_song.return_value = mock_song
            mock_get_maps.return_value = maps
            
            client = TestClient(app)
            response = client.get(f"/api/maps/song/{song_id}")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check list response fields
            assert "song_id" in data
            assert "maps" in data
            assert "canonical_map_id" in data
            assert isinstance(data["maps"], list)
