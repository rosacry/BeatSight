"""Song API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.schemas.songs import SongCreate, SongRead, SongUpdate
from app.services.songs import SongAlreadyExistsError, SongNotFoundError, SongService

router = APIRouter(prefix="/songs", tags=["songs"])


@router.post("", response_model=SongRead, status_code=status.HTTP_201_CREATED)
async def create_song(
    payload: SongCreate,
    session: AsyncSession = Depends(get_db_session),
) -> SongRead:
    """Create a new song record."""

    service = SongService(session)
    try:
        song = await service.create_song(payload)
    except SongAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Song already exists")
    return SongRead.model_validate(song)


@router.get("", response_model=list[SongRead])
async def list_songs(session: AsyncSession = Depends(get_db_session)) -> list[SongRead]:
    """List songs ordered by creation time."""

    service = SongService(session)
    songs = await service.list_songs()
    return [SongRead.model_validate(song) for song in songs]


@router.get("/{song_id}", response_model=SongRead)
async def get_song(song_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> SongRead:
    """Retrieve a song by ID."""

    service = SongService(session)
    try:
        song = await service.get_song(song_id)
    except SongNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    return SongRead.model_validate(song)


@router.patch("/{song_id}", response_model=SongRead)
async def update_song(
    song_id: uuid.UUID,
    payload: SongUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> SongRead:
    """Update song metadata."""

    service = SongService(session)
    try:
        song = await service.update_song(song_id, payload)
    except SongNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Song not found")
    return SongRead.model_validate(song)
