"""Song API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.models.user import User
from app.schemas.songs import SongCreate, SongRead, SongUpdate
from app.services.songs import SongAlreadyExistsError, SongNotFoundError, SongService

router = APIRouter(prefix="/songs", tags=["songs"])


@router.post("", response_model=SongRead, status_code=status.HTTP_201_CREATED)
async def create_song(
    payload: SongCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SongRead:
    """Create a new song record. Requires authentication."""

    service = SongService(session)
    try:
        song = await service.create_song(payload, user_id=current_user.id)
    except SongAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Song already exists"
        )
    return SongRead.model_validate(song)


@router.get("", response_model=list[SongRead])
async def list_songs(
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> list[SongRead]:
    """List songs. Authenticated users see their own songs, anonymous users see public songs."""

    service = SongService(session)
    user_id = current_user.id if current_user else None
    songs = await service.list_songs(user_id=user_id)
    return [SongRead.model_validate(song) for song in songs]


@router.get("/{song_id}", response_model=SongRead)
async def get_song(
    song_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> SongRead:
    """Retrieve a song by ID."""

    service = SongService(session)
    try:
        song = await service.get_song(song_id)
    except SongNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Song not found"
        )
    return SongRead.model_validate(song)


@router.patch("/{song_id}", response_model=SongRead)
async def update_song(
    song_id: uuid.UUID,
    payload: SongUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SongRead:
    """Update song metadata. Requires authentication and ownership."""

    service = SongService(session)
    try:
        song = await service.update_song(song_id, payload, user_id=current_user.id)
    except SongNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Song not found"
        )
    return SongRead.model_validate(song)


@router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_song(
    song_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a song. Requires authentication and ownership."""

    service = SongService(session)
    try:
        await service.delete_song(song_id, user_id=current_user.id)
    except SongNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Song not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
