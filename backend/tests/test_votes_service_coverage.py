"""Additional tests for votes service to improve coverage.

Covers missing lines: 120-162, 178-202, 208-216
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.map_vote import VoteType
from app.models.karma import KarmaReason
from app.services.votes import (
    VoteService,
    SelfVoteError,
)


class TestVoteChangingBehavior:
    """Tests for vote changing behavior (lines 120-162)."""

    @pytest.mark.asyncio
    async def test_change_vote_from_upvote_to_downvote(self):
        """Test changing from upvote to downvote reverses karma correctly."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        # Mock map and song
        mock_map = MagicMock()
        mock_map.song_id = uuid.uuid4()
        mock_song = MagicMock()
        mock_song.created_by_id = creator_id

        # Mock existing upvote
        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 0, "downvotes": 1}
            ),
            patch.object(
                service._karma_service, "award_karma", new_callable=AsyncMock
            ) as mock_award,
        ):
            _result = await service.cast_vote(user_id, map_id, VoteType.DOWNVOTE)

        # Should have reversed upvote karma (-5) and applied downvote karma
        assert mock_award.call_count == 2

        # First call should reverse upvote
        first_call = mock_award.call_args_list[0]
        assert first_call[1]["delta"] == -5  # Reverse upvote
        assert first_call[1]["reason"] == KarmaReason.MAP_UPVOTED

    @pytest.mark.asyncio
    async def test_change_vote_from_downvote_to_upvote(self):
        """Test changing from downvote to upvote reverses karma correctly."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.song_id = uuid.uuid4()
        mock_song = MagicMock()
        mock_song.created_by_id = creator_id

        # Mock existing downvote
        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.DOWNVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 1, "downvotes": 0}
            ),
            patch.object(
                service._karma_service, "award_karma", new_callable=AsyncMock
            ) as mock_award,
        ):
            _result = await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

        # First call should reverse downvote (+3 to undo -3)
        first_call = mock_award.call_args_list[0]
        assert first_call[1]["delta"] == 3  # Reverse downvote
        assert first_call[1]["reason"] == KarmaReason.MAP_DOWNVOTED

    @pytest.mark.asyncio
    async def test_same_vote_type_no_change(self):
        """Test that voting with same type returns early."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.song_id = uuid.uuid4()
        mock_song = MagicMock()
        mock_song.created_by_id = uuid.uuid4()

        # Existing upvote
        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 1, "downvotes": 0}
            ) as mock_counts,
        ):
            # Vote same type again
            _result = await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

        # Should just return current counts without karma changes
        mock_counts.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_vote_awards_karma(self):
        """Test that new vote awards karma to creator."""
        mock_session = AsyncMock()
        # Synchronous methods should use MagicMock, not AsyncMock
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_map.song_id = uuid.uuid4()
        mock_song = MagicMock()
        mock_song.created_by_id = creator_id

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=None),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 1, "downvotes": 0}
            ),
            patch.object(
                service, "_award_karma_for_vote", new_callable=AsyncMock
            ) as mock_award,
        ):
            await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

        mock_award.assert_called_once_with(creator_id, map_id, VoteType.UPVOTE)

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
            with pytest.raises(SelfVoteError, match="Cannot vote on your own maps"):
                await service.cast_vote(user_id, map_id, VoteType.UPVOTE)


class TestRemoveVote:
    """Tests for remove_vote method (lines 178-202)."""

    @pytest.mark.asyncio
    async def test_remove_upvote_reverses_karma(self):
        """Test removing upvote reverses karma award."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = creator_id

        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 0, "downvotes": 0}
            ),
            patch.object(
                service._karma_service, "award_karma", new_callable=AsyncMock
            ) as mock_award,
        ):
            await service.remove_vote(user_id, map_id)

        mock_session.delete.assert_called_once_with(mock_vote)
        mock_award.assert_called_once()
        call_kwargs = mock_award.call_args[1]
        assert call_kwargs["delta"] == -5  # Reverse upvote
        assert call_kwargs["reason"] == KarmaReason.MAP_UPVOTED

    @pytest.mark.asyncio
    async def test_remove_downvote_reverses_penalty(self):
        """Test removing downvote reverses karma penalty."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = creator_id

        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.DOWNVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 0, "downvotes": 0}
            ),
            patch.object(
                service._karma_service, "award_karma", new_callable=AsyncMock
            ) as mock_award,
        ):
            await service.remove_vote(user_id, map_id)

        call_kwargs = mock_award.call_args[1]
        assert call_kwargs["delta"] == 3  # Reverse downvote
        assert call_kwargs["reason"] == KarmaReason.MAP_DOWNVOTED

    @pytest.mark.asyncio
    async def test_remove_nonexistent_vote_returns_counts(self):
        """Test removing non-existent vote just returns current counts."""
        mock_session = AsyncMock()
        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = uuid.uuid4()

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=None),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 5, "downvotes": 2}
            ),
        ):
            result = await service.remove_vote(user_id, map_id)

        assert result == {"upvotes": 5, "downvotes": 2}
        mock_session.delete.assert_not_called()


class TestAwardKarmaForVote:
    """Tests for _award_karma_for_vote helper (lines 208-216)."""

    @pytest.mark.asyncio
    async def test_upvote_awards_positive_karma(self):
        """Test upvote awards positive karma via MAP_UPVOTED reason."""
        mock_session = AsyncMock()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        service = VoteService(mock_session)

        with patch.object(
            service._karma_service, "award_karma", new_callable=AsyncMock
        ) as mock_award:
            await service._award_karma_for_vote(creator_id, map_id, VoteType.UPVOTE)

        mock_award.assert_called_once_with(
            user_id=creator_id,
            reason=KarmaReason.MAP_UPVOTED,
            related_entity_type="map",
            related_entity_id=map_id,
        )

    @pytest.mark.asyncio
    async def test_downvote_awards_negative_karma(self):
        """Test downvote awards negative karma via MAP_DOWNVOTED reason."""
        mock_session = AsyncMock()
        creator_id = uuid.uuid4()
        map_id = uuid.uuid4()

        service = VoteService(mock_session)

        with patch.object(
            service._karma_service, "award_karma", new_callable=AsyncMock
        ) as mock_award:
            await service._award_karma_for_vote(creator_id, map_id, VoteType.DOWNVOTE)

        mock_award.assert_called_once_with(
            user_id=creator_id,
            reason=KarmaReason.MAP_DOWNVOTED,
            related_entity_type="map",
            related_entity_id=map_id,
        )


class TestVoteWithNoCreator:
    """Tests for voting when map has no creator."""

    @pytest.mark.asyncio
    async def test_vote_no_creator_skips_karma(self):
        """Test that voting on map without creator skips karma award."""
        mock_session = AsyncMock()
        # Synchronous methods should use MagicMock
        mock_session.add = MagicMock()
        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = None  # No creator

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=None),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 1, "downvotes": 0}
            ),
            patch.object(
                service, "_award_karma_for_vote", new_callable=AsyncMock
            ) as mock_award,
        ):
            await service.cast_vote(user_id, map_id, VoteType.UPVOTE)

        # Karma should not be awarded when no creator
        mock_award.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_vote_no_creator_skips_karma_reversal(self):
        """Test removing vote on creatorless map skips karma reversal."""
        mock_session = AsyncMock()
        # session.delete() is async in SQLAlchemy async session
        mock_session.delete = AsyncMock()
        user_id = uuid.uuid4()
        map_id = uuid.uuid4()

        mock_map = MagicMock()
        mock_song = MagicMock()
        mock_song.created_by_id = None  # No creator

        mock_vote = MagicMock()
        mock_vote.vote_type = VoteType.UPVOTE

        service = VoteService(mock_session)

        with (
            patch.object(
                service, "get_map_with_song", return_value=(mock_map, mock_song)
            ),
            patch.object(service, "get_vote", return_value=mock_vote),
            patch.object(
                service, "get_vote_counts", return_value={"upvotes": 0, "downvotes": 0}
            ),
            patch.object(
                service._karma_service, "award_karma", new_callable=AsyncMock
            ) as mock_award,
        ):
            await service.remove_vote(user_id, map_id)

        # Vote should be deleted, but karma not reversed
        mock_session.delete.assert_called_once()
        mock_award.assert_not_called()
