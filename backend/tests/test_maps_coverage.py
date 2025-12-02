"""
Additional tests for maps routes targeting uncovered code paths.
Focuses on lines 151-170 (verify errors), 198-208 (unverify), 236-246 (archive).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.song import Map, MapState


def create_mock_map(state=MapState.UNVERIFIED, is_canonical=False):
    """Create a mock map object."""
    map_obj = MagicMock(spec=Map)
    map_obj.id = uuid4()
    map_obj.song_id = uuid4()
    map_obj.difficulty_label = "Normal"
    map_obj.state = state
    map_obj.is_canonical = is_canonical
    map_obj.created_at = datetime.now(timezone.utc)
    map_obj.updated_at = datetime.now(timezone.utc)
    return map_obj


def create_mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def create_mock_user():
    """Create a mock user."""
    user = MagicMock()
    user.id = uuid4()
    user.username = "test_verifier"
    return user


class TestVerifyMapRoute:
    """Tests for verify_map endpoint (lines 151-170)."""

    @pytest.mark.asyncio
    async def test_verify_map_success(self):
        """Test successful map verification."""
        from app.api.routes.maps import verify_map, VerifyMapRequest
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()
        mock_map = create_mock_map(state=MapState.VERIFIED, is_canonical=True)
        map_id = mock_map.id

        # Mock the service
        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.verify_map = AsyncMock(return_value=mock_map)
            mock_service_cls.return_value = mock_service

            result = await verify_map(
                map_id=map_id,
                payload=VerifyMapRequest(force=False),
                session=mock_session,
                current_user=mock_user,
            )

            assert result.id == mock_map.id
            assert result.state == "verified"
            assert result.is_canonical is True

    @pytest.mark.asyncio
    async def test_verify_map_not_found(self):
        """Test verify_map raises 404 when map not found."""
        from app.api.routes.maps import verify_map, VerifyMapRequest
        from app.services.maps import MapNotFoundError
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.verify_map = AsyncMock(side_effect=MapNotFoundError("Not found"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await verify_map(
                    map_id=uuid4(),
                    payload=VerifyMapRequest(force=False),
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_verify_map_duplicate_conflict(self):
        """Test verify_map raises 409 when song already has verified map."""
        from app.api.routes.maps import verify_map, VerifyMapRequest
        from app.services.maps import DuplicateVerifiedMapError
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()
        existing_map_id = uuid4()
        song_id = uuid4()

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.verify_map = AsyncMock(
                side_effect=DuplicateVerifiedMapError(song_id, existing_map_id)
            )
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await verify_map(
                    map_id=uuid4(),
                    payload=VerifyMapRequest(force=False),
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 409
            assert "existing_map_id" in str(exc_info.value.detail)


class TestUnverifyMapRoute:
    """Tests for unverify_map endpoint (lines 198-208)."""

    @pytest.mark.asyncio
    async def test_unverify_map_success(self):
        """Test successful map unverification."""
        from app.api.routes.maps import unverify_map
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()
        mock_map = create_mock_map(state=MapState.UNVERIFIED, is_canonical=False)
        map_id = mock_map.id

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.unverify_map = AsyncMock(return_value=mock_map)
            mock_service_cls.return_value = mock_service

            result = await unverify_map(
                map_id=map_id,
                session=mock_session,
                current_user=mock_user,
            )

            assert result.id == mock_map.id
            assert result.state == "unverified"
            mock_service.unverify_map.assert_called_once_with(map_id)

    @pytest.mark.asyncio
    async def test_unverify_map_not_found(self):
        """Test unverify_map raises 404 when map not found."""
        from app.api.routes.maps import unverify_map
        from app.services.maps import MapNotFoundError
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.unverify_map = AsyncMock(side_effect=MapNotFoundError("Not found"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await unverify_map(
                    map_id=uuid4(),
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404


class TestArchiveMapRoute:
    """Tests for archive_map endpoint (lines 236-246)."""

    @pytest.mark.asyncio
    async def test_archive_map_success(self):
        """Test successful map archival."""
        from app.api.routes.maps import archive_map
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()
        mock_map = create_mock_map(state=MapState.ARCHIVED, is_canonical=False)
        map_id = mock_map.id

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.archive_map = AsyncMock(return_value=mock_map)
            mock_service_cls.return_value = mock_service

            result = await archive_map(
                map_id=map_id,
                session=mock_session,
                current_user=mock_user,
            )

            assert result.id == mock_map.id
            assert result.state == "archived"
            mock_service.archive_map.assert_called_once_with(map_id)

    @pytest.mark.asyncio
    async def test_archive_map_not_found(self):
        """Test archive_map raises 404 when map not found."""
        from app.api.routes.maps import archive_map
        from app.services.maps import MapNotFoundError
        
        mock_session = create_mock_session()
        mock_user = create_mock_user()

        from unittest.mock import patch
        with patch("app.api.routes.maps.MapService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.archive_map = AsyncMock(side_effect=MapNotFoundError("Not found"))
            mock_service_cls.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await archive_map(
                    map_id=uuid4(),
                    session=mock_session,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 404
