"""Tests for song service operations.

These tests validate CRUD operations and error handling for the song service.
They use an in-memory SQLite database for isolation.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.song import Song, SongStatus
from app.schemas.songs import SongCreate, SongUpdate
from app.services.songs import SongAlreadyExistsError, SongNotFoundError, SongService


class TestSongService:
    """Test cases for SongService."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> SongService:
        """Create a SongService with mocked session."""
        return SongService(mock_session)

    @pytest.mark.asyncio
    async def test_create_song_success(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test successful song creation."""
        payload = SongCreate(
            title="Test Song",
            artist="Test Artist",
            fingerprint_hash="abc123hash",
            bpm=120,
        )

        result = await service.create_song(payload)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_song_duplicate_fingerprint_raises(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test that duplicate fingerprint raises SongAlreadyExistsError."""
        payload = SongCreate(
            title="Duplicate Song",
            artist="Artist",
            fingerprint_hash="duplicate_hash",
        )
        mock_session.commit.side_effect = IntegrityError(
            statement="", params=None, orig=Exception()
        )

        with pytest.raises(SongAlreadyExistsError):
            await service.create_song(payload)

        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_songs_returns_ordered_list(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test listing songs returns properly ordered results."""
        # Create mock songs
        song1 = Song(
            id=uuid.uuid4(),
            title="Song 1",
            artist="Artist",
            fingerprint_hash="hash1",
        )
        song2 = Song(
            id=uuid.uuid4(),
            title="Song 2",
            artist="Artist",
            fingerprint_hash="hash2",
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value = [song2, song1]
        mock_session.execute.return_value = mock_result

        result = await service.list_songs()

        assert len(result) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_song_success(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test successfully retrieving a song by ID."""
        song_id = uuid.uuid4()
        expected_song = Song(
            id=song_id,
            title="Found Song",
            artist="Artist",
            fingerprint_hash="hash123",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected_song
        mock_session.execute.return_value = mock_result

        result = await service.get_song(song_id)

        assert result == expected_song

    @pytest.mark.asyncio
    async def test_get_song_not_found_raises(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test that missing song raises SongNotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(SongNotFoundError):
            await service.get_song(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_song_success(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test successfully updating a song."""
        song_id = uuid.uuid4()
        existing_song = Song(
            id=song_id,
            title="Original Title",
            artist="Original Artist",
            fingerprint_hash="hash123",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_song
        mock_session.execute.return_value = mock_result

        payload = SongUpdate(title="Updated Title", bpm=140)

        result = await service.update_song(song_id, payload)

        assert result.title == "Updated Title"
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_song_not_found_raises(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test that updating non-existent song raises SongNotFoundError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        payload = SongUpdate(title="New Title")

        with pytest.raises(SongNotFoundError):
            await service.update_song(uuid.uuid4(), payload)

    @pytest.mark.asyncio
    async def test_update_song_partial_fields(
        self, service: SongService, mock_session: AsyncMock
    ) -> None:
        """Test that partial updates only modify specified fields."""
        song_id = uuid.uuid4()
        existing_song = Song(
            id=song_id,
            title="Original",
            artist="Original Artist",
            bpm=120,
            fingerprint_hash="hash123",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_song
        mock_session.execute.return_value = mock_result

        # Only update BPM, leave title and artist unchanged
        payload = SongUpdate(bpm=180)

        result = await service.update_song(song_id, payload)

        assert result.title == "Original"  # Unchanged
        assert result.artist == "Original Artist"  # Unchanged
        assert result.bpm == 180  # Updated
