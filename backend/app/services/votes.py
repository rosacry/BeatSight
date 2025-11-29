"""Service layer for map voting operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.karma import KarmaReason
from app.models.map_vote import MapVote, VoteType
from app.models.song import Map, Song
from app.services.karma import KarmaService


class VoteError(Exception):
    """Base exception for voting operations."""

    pass


class MapNotFoundError(VoteError):
    """Raised when a map cannot be found."""

    pass


class SelfVoteError(VoteError):
    """Raised when a user tries to vote on their own map."""

    pass


class VoteService:
    """Encapsulates map voting operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._karma_service = KarmaService(session)

    async def get_map_with_song(self, map_id: uuid.UUID) -> tuple[Map, Song]:
        """Fetch a map and its parent song."""
        result = await self._session.execute(
            select(Map).where(Map.id == map_id)
        )
        map_obj = result.scalar_one_or_none()
        if map_obj is None:
            raise MapNotFoundError(f"Map {map_id} not found")

        result = await self._session.execute(
            select(Song).where(Song.id == map_obj.song_id)
        )
        song = result.scalar_one()
        return map_obj, song

    async def get_vote(
        self, user_id: uuid.UUID, map_id: uuid.UUID
    ) -> Optional[MapVote]:
        """Get a user's current vote on a map, if any."""
        result = await self._session.execute(
            select(MapVote).where(
                and_(MapVote.user_id == user_id, MapVote.map_id == map_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_vote_counts(self, map_id: uuid.UUID) -> dict:
        """Get vote tallies for a map."""
        result = await self._session.execute(
            select(
                func.count(MapVote.id).filter(MapVote.vote_type == VoteType.UPVOTE).label("upvotes"),
                func.count(MapVote.id).filter(MapVote.vote_type == VoteType.DOWNVOTE).label("downvotes"),
            ).where(MapVote.map_id == map_id)
        )
        row = result.one()
        upvotes = row.upvotes or 0
        downvotes = row.downvotes or 0
        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "score": upvotes - downvotes,
        }

    async def cast_vote(
        self,
        user_id: uuid.UUID,
        map_id: uuid.UUID,
        vote_type: VoteType,
    ) -> dict:
        """
        Cast or change a vote on a map.

        Args:
            user_id: The voter's user ID.
            map_id: The map being voted on.
            vote_type: UPVOTE (+1) or DOWNVOTE (-1).

        Returns:
            Updated vote counts for the map.

        Raises:
            MapNotFoundError: If the map doesn't exist.
            SelfVoteError: If user tries to vote on their own map.
        """
        map_obj, song = await self.get_map_with_song(map_id)

        # Prevent self-voting (if map creator is tracked via song creator)
        if song.created_by_id and song.created_by_id == user_id:
            raise SelfVoteError("Cannot vote on your own maps")

        existing_vote = await self.get_vote(user_id, map_id)

        if existing_vote is not None:
            # User is changing their vote
            if existing_vote.vote_type == vote_type:
                # Same vote - no change needed
                return await self.get_vote_counts(map_id)

            old_vote_type = existing_vote.vote_type
            existing_vote.vote_type = vote_type
            await self._session.flush()

            # Adjust karma for the map creator (undo old vote, apply new)
            if song.created_by_id:
                # Undo old vote
                if old_vote_type == VoteType.UPVOTE:
                    await self._karma_service.award_karma(
                        user_id=song.created_by_id,
                        reason=KarmaReason.MAP_UPVOTED,
                        delta=-5,  # Reverse the upvote reward
                        related_entity_type="map",
                        related_entity_id=map_id,
                    )
                else:
                    await self._karma_service.award_karma(
                        user_id=song.created_by_id,
                        reason=KarmaReason.MAP_DOWNVOTED,
                        delta=3,  # Reverse the downvote penalty
                        related_entity_type="map",
                        related_entity_id=map_id,
                    )

                # Apply new vote
                await self._award_karma_for_vote(song.created_by_id, map_id, vote_type)

        else:
            # New vote
            new_vote = MapVote(
                user_id=user_id,
                map_id=map_id,
                vote_type=vote_type,
            )
            self._session.add(new_vote)
            await self._session.flush()

            # Award karma to map creator
            if song.created_by_id:
                await self._award_karma_for_vote(song.created_by_id, map_id, vote_type)

        await self._session.commit()
        return await self.get_vote_counts(map_id)

    async def remove_vote(self, user_id: uuid.UUID, map_id: uuid.UUID) -> dict:
        """
        Remove a user's vote from a map.

        Returns:
            Updated vote counts for the map.
        """
        map_obj, song = await self.get_map_with_song(map_id)

        existing_vote = await self.get_vote(user_id, map_id)
        if existing_vote is None:
            # No vote to remove
            return await self.get_vote_counts(map_id)

        old_vote_type = existing_vote.vote_type
        await self._session.delete(existing_vote)
        await self._session.flush()

        # Reverse karma for map creator
        if song.created_by_id:
            if old_vote_type == VoteType.UPVOTE:
                await self._karma_service.award_karma(
                    user_id=song.created_by_id,
                    reason=KarmaReason.MAP_UPVOTED,
                    delta=-5,  # Reverse the upvote
                    related_entity_type="map",
                    related_entity_id=map_id,
                )
            else:
                await self._karma_service.award_karma(
                    user_id=song.created_by_id,
                    reason=KarmaReason.MAP_DOWNVOTED,
                    delta=3,  # Reverse the downvote
                    related_entity_type="map",
                    related_entity_id=map_id,
                )

        await self._session.commit()
        return await self.get_vote_counts(map_id)

    async def _award_karma_for_vote(
        self, creator_id: uuid.UUID, map_id: uuid.UUID, vote_type: VoteType
    ) -> None:
        """Helper to award karma based on vote type."""
        if vote_type == VoteType.UPVOTE:
            await self._karma_service.award_karma(
                user_id=creator_id,
                reason=KarmaReason.MAP_UPVOTED,
                related_entity_type="map",
                related_entity_id=map_id,
            )
        else:
            await self._karma_service.award_karma(
                user_id=creator_id,
                reason=KarmaReason.MAP_DOWNVOTED,
                related_entity_type="map",
                related_entity_id=map_id,
            )

    async def get_user_votes(
        self, user_id: uuid.UUID, map_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, VoteType]:
        """
        Get a user's votes for multiple maps.

        Args:
            user_id: The user whose votes to fetch.
            map_ids: List of map IDs to check.

        Returns:
            Dict mapping map_id -> VoteType for maps the user has voted on.
        """
        if not map_ids:
            return {}

        result = await self._session.execute(
            select(MapVote).where(
                and_(MapVote.user_id == user_id, MapVote.map_id.in_(map_ids))
            )
        )
        votes = result.scalars().all()
        return {vote.map_id: vote.vote_type for vote in votes}
