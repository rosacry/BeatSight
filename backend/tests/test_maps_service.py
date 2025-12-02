"""Tests for maps service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.song import MapState, SongStatus
from app.services.maps import (
    MapService,
    MapError,
    MapNotFoundError,
    SongNotFoundError,
    VerificationError,
    DuplicateVerifiedMapError,
)


class TestMapExceptions:
    """Tests for map exception classes."""

    def test_map_error_is_exception(self):
        """Test that MapError is an Exception."""
        error = MapError("test")
        assert isinstance(error, Exception)

    def test_map_not_found_inherits(self):
        """Test that MapNotFoundError inherits from MapError."""
        error = MapNotFoundError("test")
        assert isinstance(error, MapError)

    def test_song_not_found_inherits(self):
        """Test that SongNotFoundError inherits from MapError."""
        error = SongNotFoundError("test")
        assert isinstance(error, MapError)

    def test_verification_error_inherits(self):
        """Test that VerificationError inherits from MapError."""
        error = VerificationError("test")
        assert isinstance(error, MapError)

    def test_duplicate_verified_map_error(self):
        """Test DuplicateVerifiedMapError stores IDs."""
        song_id = uuid.uuid4()
        map_id = uuid.uuid4()

        error = DuplicateVerifiedMapError(song_id, map_id)

        assert error.song_id == song_id
        assert error.existing_map_id == map_id
        assert str(song_id) in str(error)
        assert str(map_id) in str(error)

    def test_duplicate_verified_inherits_verification_error(self):
        """Test DuplicateVerifiedMapError inherits from VerificationError."""
        error = DuplicateVerifiedMapError(uuid.uuid4(), uuid.uuid4())
        assert isinstance(error, VerificationError)


class TestMapServiceInit:
    """Tests for MapService initialization."""

    def test_init_stores_session(self):
        """Test that service stores the session."""
        mock_session = MagicMock()
        service = MapService(mock_session)
        assert service._session is mock_session


class TestGetMap:
    """Tests for get_map method."""

    @pytest.mark.asyncio
    async def test_map_found(self):
        """Test returning a found map."""
        mock_session = AsyncMock()
        mock_map = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_map
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_map(uuid.uuid4())

        assert result is mock_map

    @pytest.mark.asyncio
    async def test_map_not_found(self):
        """Test MapNotFoundError when map doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)
        map_id = uuid.uuid4()

        with pytest.raises(MapNotFoundError) as exc_info:
            await service.get_map(map_id)

        assert str(map_id) in str(exc_info.value)


class TestGetSong:
    """Tests for get_song method."""

    @pytest.mark.asyncio
    async def test_song_found(self):
        """Test returning a found song."""
        mock_session = AsyncMock()
        mock_song = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_song
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_song(uuid.uuid4())

        assert result is mock_song

    @pytest.mark.asyncio
    async def test_song_not_found(self):
        """Test SongNotFoundError when song doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)
        song_id = uuid.uuid4()

        with pytest.raises(SongNotFoundError) as exc_info:
            await service.get_song(song_id)

        assert str(song_id) in str(exc_info.value)


class TestGetVerifiedMapForSong:
    """Tests for get_verified_map_for_song method."""

    @pytest.mark.asyncio
    async def test_no_verified_map(self):
        """Test returning None when no verified map exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_verified_map_for_song(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_verified_map_found(self):
        """Test returning verified map when it exists."""
        mock_session = AsyncMock()
        mock_map = MagicMock()
        mock_map.state = MapState.VERIFIED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_map
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_verified_map_for_song(uuid.uuid4())

        assert result is mock_map


class TestVerifyMap:
    """Tests for verify_map method."""

    @pytest.mark.asyncio
    async def test_verify_map_no_existing(self):
        """Test verifying a map when no other verified map exists."""
        mock_session = AsyncMock()

        map_id = uuid.uuid4()
        song_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.id = map_id
        mock_map.song_id = song_id
        mock_map.state = MapState.UNVERIFIED

        mock_song = MagicMock()
        mock_song.id = song_id

        service = MapService(mock_session)

        with patch.object(service, "get_map", return_value=mock_map):
            with patch.object(service, "get_song", return_value=mock_song):
                with patch.object(
                    service, "get_verified_map_for_song", return_value=None
                ):
                    _result = await service.verify_map(map_id)

        assert mock_map.state == MapState.VERIFIED
        assert mock_map.is_canonical is True
        assert mock_song.canonical_map_id == map_id
        assert mock_song.status == SongStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_verify_map_duplicate_without_force(self):
        """Test that verifying fails when another verified map exists."""
        mock_session = AsyncMock()

        map_id = uuid.uuid4()
        existing_map_id = uuid.uuid4()
        song_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.id = map_id
        mock_map.song_id = song_id

        mock_song = MagicMock()
        mock_song.id = song_id

        mock_existing = MagicMock()
        mock_existing.id = existing_map_id

        service = MapService(mock_session)

        with patch.object(service, "get_map", return_value=mock_map):
            with patch.object(service, "get_song", return_value=mock_song):
                with patch.object(
                    service, "get_verified_map_for_song", return_value=mock_existing
                ):
                    with pytest.raises(DuplicateVerifiedMapError) as exc_info:
                        await service.verify_map(map_id, force=False)

        assert exc_info.value.song_id == song_id
        assert exc_info.value.existing_map_id == existing_map_id

    @pytest.mark.asyncio
    async def test_verify_map_force_archives_existing(self):
        """Test that force=True archives existing verified map."""
        mock_session = AsyncMock()

        map_id = uuid.uuid4()
        existing_map_id = uuid.uuid4()
        song_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.id = map_id
        mock_map.song_id = song_id

        mock_song = MagicMock()
        mock_song.id = song_id

        mock_existing = MagicMock()
        mock_existing.id = existing_map_id
        mock_existing.state = MapState.VERIFIED

        service = MapService(mock_session)

        with patch.object(service, "get_map", return_value=mock_map):
            with patch.object(service, "get_song", return_value=mock_song):
                with patch.object(
                    service, "get_verified_map_for_song", return_value=mock_existing
                ):
                    _result = await service.verify_map(map_id, force=True)

        # Existing map should be archived
        assert mock_existing.state == MapState.ARCHIVED
        assert mock_existing.is_canonical is False

        # New map should be verified
        assert mock_map.state == MapState.VERIFIED
        assert mock_map.is_canonical is True


class TestUnverifyMap:
    """Tests for unverify_map method."""

    @pytest.mark.asyncio
    async def test_unverify_map(self):
        """Test unverifying a map."""
        mock_session = AsyncMock()

        map_id = uuid.uuid4()
        song_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.id = map_id
        mock_map.song_id = song_id
        mock_map.state = MapState.VERIFIED
        mock_map.is_canonical = True

        mock_song = MagicMock()
        mock_song.id = song_id
        mock_song.canonical_map_id = map_id

        service = MapService(mock_session)

        with patch.object(service, "get_map", return_value=mock_map):
            with patch.object(service, "get_song", return_value=mock_song):
                _result = await service.unverify_map(map_id)

        assert mock_map.state == MapState.UNVERIFIED
        assert mock_map.is_canonical is False
        assert mock_song.canonical_map_id is None
        assert mock_song.status == SongStatus.UNVERIFIED


class TestArchiveMap:
    """Tests for archive_map method."""

    @pytest.mark.asyncio
    async def test_archive_canonical_map(self):
        """Test archiving a canonical map clears song reference."""
        mock_session = AsyncMock()

        map_id = uuid.uuid4()
        song_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.id = map_id
        mock_map.song_id = song_id
        mock_map.is_canonical = True

        mock_song = MagicMock()
        mock_song.id = song_id
        mock_song.canonical_map_id = map_id

        # No other verified maps
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        with patch.object(service, "get_map", return_value=mock_map):
            with patch.object(service, "get_song", return_value=mock_song):
                _result = await service.archive_map(map_id)

        assert mock_map.state == MapState.ARCHIVED
        assert mock_map.is_canonical is False
        assert mock_song.canonical_map_id is None


class TestGetSongMaps:
    """Tests for get_song_maps method."""

    @pytest.mark.asyncio
    async def test_returns_map_list(self):
        """Test that maps are returned as a list."""
        mock_session = AsyncMock()

        mock_map1 = MagicMock()
        mock_map2 = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_map1, mock_map2]
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_song_maps(uuid.uuid4())

        assert len(result) == 2
        assert mock_map1 in result
        assert mock_map2 in result

    @pytest.mark.asyncio
    async def test_empty_list_for_no_maps(self):
        """Test that empty list is returned when no maps exist."""
        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        service = MapService(mock_session)

        result = await service.get_song_maps(uuid.uuid4())

        assert result == []
