"""Map management API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.maps import (
    DuplicateVerifiedMapError,
    MapNotFoundError,
    MapService,
    SongNotFoundError,
)
from app.services.rbac import Permission, require_any_permission

router = APIRouter(prefix="/maps", tags=["maps"])

# RBAC dependencies
RequireVerifier = require_any_permission(Permission.MAP_VERIFY)
RequireMapApprove = require_any_permission(Permission.MAP_APPROVE)


# =============================================================================
# Response Models
# =============================================================================


class MapStateResponse(BaseModel):
    """Map state information."""

    id: uuid.UUID
    song_id: uuid.UUID
    difficulty_label: str
    state: str
    is_canonical: bool
    created_at: datetime
    updated_at: datetime


class MapListResponse(BaseModel):
    """List of maps for a song."""

    song_id: uuid.UUID
    maps: list[MapStateResponse]
    canonical_map_id: Optional[uuid.UUID]


class VerifyMapRequest(BaseModel):
    """Request to verify a map."""

    force: bool = False  # If True, archive existing verified map


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{map_id}", response_model=MapStateResponse)
async def get_map(
    map_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MapStateResponse:
    """Get map details."""
    service = MapService(session)

    try:
        map_obj = await service.get_map(map_id)
    except MapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map not found",
        )

    return MapStateResponse(
        id=map_obj.id,
        song_id=map_obj.song_id,
        difficulty_label=map_obj.difficulty_label,
        state=map_obj.state.value,
        is_canonical=map_obj.is_canonical,
        created_at=map_obj.created_at,
        updated_at=map_obj.updated_at,
    )


@router.get("/song/{song_id}", response_model=MapListResponse)
async def get_song_maps(
    song_id: uuid.UUID,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> MapListResponse:
    """Get all maps for a song."""
    service = MapService(session)

    try:
        song = await service.get_song(song_id)
        maps = await service.get_song_maps(song_id, include_archived=include_archived)
    except SongNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found",
        )

    return MapListResponse(
        song_id=song_id,
        maps=[
            MapStateResponse(
                id=m.id,
                song_id=m.song_id,
                difficulty_label=m.difficulty_label,
                state=m.state.value,
                is_canonical=m.is_canonical,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in maps
        ],
        canonical_map_id=song.canonical_map_id,
    )


@router.post(
    "/{map_id}/verify",
    response_model=MapStateResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def verify_map(
    map_id: uuid.UUID,
    payload: VerifyMapRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MapStateResponse:
    """
    Verify a map and set it as canonical for its song.

    Requires MAP_VERIFY permission.

    Only one map per song can be verified at a time:
    - If the song already has a verified map, returns 409 Conflict
    - Unless force=True, which archives the existing verified map

    This ensures users see only the best quality map for each song.
    """
    service = MapService(session)

    try:
        map_obj = await service.verify_map(map_id, force=payload.force)
    except MapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map not found",
        )
    except DuplicateVerifiedMapError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Song already has a verified map",
                "existing_map_id": str(e.existing_map_id),
                "hint": "Set force=true to archive the existing map and verify this one",
            },
        )

    return MapStateResponse(
        id=map_obj.id,
        song_id=map_obj.song_id,
        difficulty_label=map_obj.difficulty_label,
        state=map_obj.state.value,
        is_canonical=map_obj.is_canonical,
        created_at=map_obj.created_at,
        updated_at=map_obj.updated_at,
    )


@router.post(
    "/{map_id}/unverify",
    response_model=MapStateResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def unverify_map(
    map_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MapStateResponse:
    """
    Remove verification from a map.

    Requires MAP_VERIFY permission.

    The map will be set back to UNVERIFIED state.
    """
    service = MapService(session)

    try:
        map_obj = await service.unverify_map(map_id)
    except MapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map not found",
        )

    return MapStateResponse(
        id=map_obj.id,
        song_id=map_obj.song_id,
        difficulty_label=map_obj.difficulty_label,
        state=map_obj.state.value,
        is_canonical=map_obj.is_canonical,
        created_at=map_obj.created_at,
        updated_at=map_obj.updated_at,
    )


@router.post(
    "/{map_id}/archive",
    response_model=MapStateResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def archive_map(
    map_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MapStateResponse:
    """
    Archive a map.

    Requires MAP_VERIFY permission.

    Archived maps are hidden from normal listings but retained for history.
    """
    service = MapService(session)

    try:
        map_obj = await service.archive_map(map_id)
    except MapNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map not found",
        )

    return MapStateResponse(
        id=map_obj.id,
        song_id=map_obj.song_id,
        difficulty_label=map_obj.difficulty_label,
        state=map_obj.state.value,
        is_canonical=map_obj.is_canonical,
        created_at=map_obj.created_at,
        updated_at=map_obj.updated_at,
    )
