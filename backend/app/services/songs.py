"""Service layer for song operations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.song import Song
from app.schemas.songs import SongCreate, SongUpdate


class SongAlreadyExistsError(Exception):
    """Raised when a song with the same fingerprint already exists."""


class SongNotFoundError(Exception):
    """Raised when a song cannot be located."""


class SongService:
    """Encapsulates song-related database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_song(self, payload: SongCreate, user_id: uuid.UUID) -> Song:
        """Create a new song.

        Args:
            payload: Song data
            user_id: The creating user's ID (will be set as owner)
        """
        song = Song(**payload.model_dump(), created_by_id=user_id)
        self._session.add(song)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise SongAlreadyExistsError from exc
        await self._session.refresh(song)
        return song

    async def list_songs(
        self,
        user_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Song]:
        """List songs with pagination.

        Args:
            user_id: If provided, filter to user's songs. If None, return public songs.
            limit: Maximum number of songs to return.
            offset: Number of songs to skip.
        """
        query = (
            select(Song)
            .options(selectinload(Song.maps))
            .order_by(Song.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        # Filter by user if specified
        if user_id is not None:
            query = query.where(Song.created_by_id == user_id)

        result = await self._session.execute(query)
        return list(result.scalars().unique())

    async def count_songs(self, user_id: uuid.UUID | None = None) -> int:
        """Count total songs for pagination metadata.

        Args:
            user_id: If provided, count user's songs. If None, count public songs.
        """
        query = select(func.count()).select_from(Song)

        if user_id is not None:
            query = query.where(Song.created_by_id == user_id)

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_song(self, song_id: uuid.UUID) -> Song:
        result = await self._session.execute(
            select(Song).where(Song.id == song_id).options(selectinload(Song.maps))
        )
        song = result.scalar_one_or_none()
        if not song:
            raise SongNotFoundError
        return song

    async def update_song(
        self, song_id: uuid.UUID, payload: SongUpdate, user_id: uuid.UUID
    ) -> Song:
        """Update a song. Verifies ownership before allowing modification.

        Args:
            song_id: The song to update
            payload: Fields to update
            user_id: The requesting user's ID (required for authorization)

        Raises:
            SongNotFoundError: If song doesn't exist or user doesn't own it
        """
        song = await self.get_song(song_id)

        # Security: ALWAYS verify ownership - no bypass allowed
        if song.created_by_id != user_id:
            raise SongNotFoundError  # Don't reveal the song exists

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(song, field, value)
        await self._session.commit()
        await self._session.refresh(song)
        return song

    async def delete_song(
        self, song_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a song. Verifies ownership before allowing deletion.

        Args:
            song_id: The song to delete
            user_id: The requesting user's ID (required for authorization)

        Raises:
            SongNotFoundError: If song doesn't exist or user doesn't own it
        """
        song = await self.get_song(song_id)

        # Security: ALWAYS verify ownership - no bypass allowed
        if song.created_by_id != user_id:
            raise SongNotFoundError  # Don't reveal the song exists

        await self._session.delete(song)
        await self._session.commit()
