"""Service layer for song operations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
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

    async def create_song(self, payload: SongCreate) -> Song:
        song = Song(**payload.model_dump())
        self._session.add(song)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise SongAlreadyExistsError from exc
        await self._session.refresh(song)
        return song

    async def list_songs(self) -> list[Song]:
        result = await self._session.execute(
            select(Song)
            .options(selectinload(Song.maps))
            .order_by(Song.created_at.desc())
        )
        return list(result.scalars().unique())

    async def get_song(self, song_id: uuid.UUID) -> Song:
        result = await self._session.execute(
            select(Song).where(Song.id == song_id).options(selectinload(Song.maps))
        )
        song = result.scalar_one_or_none()
        if not song:
            raise SongNotFoundError
        return song

    async def update_song(
        self, song_id: uuid.UUID, payload: SongUpdate, user_id: uuid.UUID | None = None
    ) -> Song:
        """Update a song. If user_id is provided, verifies ownership."""
        song = await self.get_song(song_id)
        
        # Security: verify ownership if user_id provided
        if user_id is not None and song.created_by_id != user_id:
            raise SongNotFoundError  # Don't reveal the song exists
        
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(song, field, value)
        await self._session.commit()
        await self._session.refresh(song)
        return song
    
    async def delete_song(
        self, song_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        """Delete a song. If user_id is provided, verifies ownership."""
        song = await self.get_song(song_id)
        
        # Security: verify ownership if user_id provided
        if user_id is not None and song.created_by_id != user_id:
            raise SongNotFoundError  # Don't reveal the song exists
        
        await self._session.delete(song)
        await self._session.commit()
