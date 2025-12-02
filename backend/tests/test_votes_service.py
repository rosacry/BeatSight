"""Tests for vote service."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.map_vote import VoteType
from app.services.votes import (
    VoteService,
    VoteError,
    MapNotFoundError,
    SelfVoteError,
)


class TestVoteServiceInit:
    """Tests for VoteService initialization."""

    def test_init_creates_karma_service(self):
        """Test that VoteService creates a KarmaService."""
        mock_session = MagicMock()
        service = VoteService(mock_session)
        assert service._session is mock_session
        assert service._karma_service is not None


class TestGetMapWithSong:
    """Tests for get_map_with_song method."""

    @pytest.mark.asyncio
    async def test_map_not_found(self):
        """Test that MapNotFoundError is raised when map doesn't exist."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)
        map_id = uuid.uuid4()

        with pytest.raises(MapNotFoundError) as exc_info:
            await service.get_map_with_song(map_id)

        assert str(map_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_map_found_returns_tuple(self):
        """Test that found map returns (map, song) tuple."""
        mock_session = AsyncMock()

        mock_map = MagicMock()
        mock_map.song_id = uuid.uuid4()

        mock_song = MagicMock()

        # First call returns map, second returns song
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = mock_map

        mock_result2 = MagicMock()
        mock_result2.scalar_one.return_value = mock_song

        mock_session.execute.side_effect = [mock_result1, mock_result2]

        service = VoteService(mock_session)
        map_id = uuid.uuid4()

        result = await service.get_map_with_song(map_id)

        assert result == (mock_map, mock_song)


class TestGetVote:
    """Tests for get_vote method."""

    @pytest.mark.asyncio
    async def test_no_existing_vote(self):
        """Test returning None when no vote exists."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)

        result = await service.get_vote(uuid.uuid4(), uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_existing_vote_returned(self):
        """Test returning existing vote."""
        mock_session = AsyncMock()
        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_vote
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)

        result = await service.get_vote(uuid.uuid4(), uuid.uuid4())

        assert result is mock_vote


class TestGetVoteCounts:
    """Tests for get_vote_counts method."""

    @pytest.mark.asyncio
    async def test_returns_vote_counts(self):
        """Test that vote counts are properly calculated."""
        mock_session = AsyncMock()

        mock_row = MagicMock()
        mock_row.upvotes = 10
        mock_row.downvotes = 3

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)
        map_id = uuid.uuid4()

        result = await service.get_vote_counts(map_id)

        assert result["upvotes"] == 10
        assert result["downvotes"] == 3
        assert result["score"] == 7

    @pytest.mark.asyncio
    async def test_handles_none_counts(self):
        """Test that None counts are treated as zero."""
        mock_session = AsyncMock()

        mock_row = MagicMock()
        mock_row.upvotes = None
        mock_row.downvotes = None

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)

        result = await service.get_vote_counts(uuid.uuid4())

        assert result["upvotes"] == 0
        assert result["downvotes"] == 0
        assert result["score"] == 0


class TestCastVote:
    """Tests for cast_vote method."""

    @pytest.mark.asyncio
    async def test_self_vote_raises_error(self):
        """Test that voting on own map raises SelfVoteError."""
        mock_session = AsyncMock()

        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = user_id  # Same as voter

        service = VoteService(mock_session)

        with patch.object(
            service, "get_map_with_song", return_value=(mock_map, mock_song)
        ):
            with pytest.raises(SelfVoteError) as exc_info:
                await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

            assert "own maps" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_same_vote_no_change(self):
        """Test that casting same vote type returns counts unchanged."""
        mock_session = AsyncMock()

        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = uuid.uuid4()  # Different user

        mock_existing_vote = MagicMock()
        mock_existing_vote.vote_type = VoteType.UPVOTE

        expected_counts = {"upvotes": 5, "downvotes": 2, "score": 3}

        service = VoteService(mock_session)

        with patch.object(
            service, "get_map_with_song", return_value=(mock_map, mock_song)
        ):
            with patch.object(service, "get_vote", return_value=mock_existing_vote):
                with patch.object(
                    service, "get_vote_counts", return_value=expected_counts
                ):
                    result = await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

        assert result == expected_counts


class TestRemoveVote:
    """Tests for remove_vote method."""

    @pytest.mark.asyncio
    async def test_no_vote_to_remove(self):
        """Test removing non-existent vote returns current counts."""
        mock_session = AsyncMock()

        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = uuid.uuid4()

        expected_counts = {"upvotes": 5, "downvotes": 2, "score": 3}

        service = VoteService(mock_session)

        with patch.object(
            service, "get_map_with_song", return_value=(mock_map, mock_song)
        ):
            with patch.object(service, "get_vote", return_value=None):
                with patch.object(
                    service, "get_vote_counts", return_value=expected_counts
                ):
                    result = await service.remove_vote(user_id, map_id)

        assert result == expected_counts


class TestGetUserVotes:
    """Tests for get_user_votes method."""

    @pytest.mark.asyncio
    async def test_empty_map_ids(self):
        """Test that empty map_ids returns empty dict."""
        mock_session = AsyncMock()
        service = VoteService(mock_session)

        result = await service.get_user_votes(uuid.uuid4(), [])

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_vote_dict(self):
        """Test that votes are returned as map_id -> VoteType dict."""
        mock_session = AsyncMock()

        map_id_1 = uuid.uuid4()
        map_id_2 = uuid.uuid4()

        mock_vote_1 = MagicMock()
        mock_vote_1.map_id = map_id_1
        mock_vote_1.vote_type = VoteType.UPVOTE

        mock_vote_2 = MagicMock()
        mock_vote_2.map_id = map_id_2
        mock_vote_2.vote_type = VoteType.DOWNVOTE

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_vote_1, mock_vote_2]
        mock_session.execute.return_value = mock_result

        service = VoteService(mock_session)
        user_id = uuid.uuid4()

        result = await service.get_user_votes(user_id, [map_id_1, map_id_2])

        assert result[map_id_1] == VoteType.UPVOTE
        assert result[map_id_2] == VoteType.DOWNVOTE


class TestVoteExceptions:
    """Tests for vote exception classes."""

    def test_vote_error_is_exception(self):
        """Test that VoteError is an Exception."""
        error = VoteError("test")
        assert isinstance(error, Exception)

    def test_map_not_found_inherits_vote_error(self):
        """Test that MapNotFoundError inherits from VoteError."""
        error = MapNotFoundError("test")
        assert isinstance(error, VoteError)

    def test_self_vote_error_inherits_vote_error(self):
        """Test that SelfVoteError inherits from VoteError."""
        error = SelfVoteError("test")
        assert isinstance(error, VoteError)
