"""Cloud sync API routes for preferences and library synchronization."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session, require_cloud_sync
from app.models.sync import ConflictResolution, SyncAction, SyncState
from app.models.user import User
from app.services.sync import SyncService

# All sync routes require cloud_sync feature to be enabled
router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    dependencies=[Depends(require_cloud_sync)],
)


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------


class PreferencesResponse(BaseModel):
    """User preferences response."""

    version: int
    checksum: str
    scroll_speed: float
    note_skin: str
    audio_offset_ms: int
    visual_offset_ms: int
    background_dim: float
    master_volume: float
    music_volume: float
    effects_volume: float
    hitsound_volume: float
    theme: str
    language: str
    custom_settings: dict[str, Any]
    last_modified: datetime

    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    """Update user preferences."""

    scroll_speed: float | None = None
    note_skin: str | None = None
    audio_offset_ms: int | None = None
    visual_offset_ms: int | None = None
    background_dim: float | None = None
    master_volume: float | None = None
    music_volume: float | None = None
    effects_volume: float | None = None
    hitsound_volume: float | None = None
    theme: str | None = None
    language: str | None = None
    custom_settings: dict[str, Any] | None = None
    expected_version: int | None = Field(None, description="For optimistic locking")


class SyncClientResponse(BaseModel):
    """Sync client (device) response."""

    id: uuid.UUID
    client_name: str
    client_type: str
    last_sync_at: datetime | None
    last_ip: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterClientRequest(BaseModel):
    """Register a new sync client."""

    client_name: str = Field(..., min_length=1, max_length=255)
    client_type: str = Field(..., pattern="^(desktop|web|mobile)$")


class ManifestEntry(BaseModel):
    """Client-side manifest entry for comparison."""

    map_id: str
    version: int
    checksum: str
    sync_state: str = "synced"


class SyncManifestRequest(BaseModel):
    """Request to compare manifests."""

    client_id: str | None = None
    last_sync_timestamp: datetime | None = None
    beatmaps: list[ManifestEntry] = Field(default_factory=list)


class SyncActionResponse(BaseModel):
    """Sync action determined by manifest comparison."""

    map_id: str
    action: str
    reason: str
    cloud_version: int | None = None
    cloud_checksum: str | None = None
    local_version: int | None = None


class ManifestCompareResponse(BaseModel):
    """Response from manifest comparison."""

    server_timestamp: datetime
    actions: list[SyncActionResponse]


class ConflictResponse(BaseModel):
    """Sync conflict response."""

    id: uuid.UUID
    map_id: uuid.UUID
    local_version: int
    cloud_version: int
    local_checksum: str
    cloud_checksum: str
    differences: dict[str, Any] | None
    resolution: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveConflictRequest(BaseModel):
    """Request to resolve a sync conflict."""

    resolution: ConflictResolution


class SyncLogResponse(BaseModel):
    """Sync log entry response."""

    id: uuid.UUID
    action: str
    details: dict[str, Any] | None
    maps_synced: int
    bytes_transferred: int
    timestamp: datetime

    model_config = {"from_attributes": True}


class SyncStatusResponse(BaseModel):
    """Overall sync status."""

    preferences_version: int
    preferences_checksum: str
    total_maps: int
    synced_maps: int
    pending_uploads: int
    pending_downloads: int
    conflicts: int
    last_sync: datetime | None
    clients: int


# -------------------------------------------------------------------------
# Preferences Routes
# -------------------------------------------------------------------------


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PreferencesResponse:
    """Get current user preferences."""
    service = SyncService(db)
    prefs = await service.get_user_preferences(current_user.id)

    if prefs is None:
        prefs = await service.create_default_preferences(current_user.id)
        await db.commit()

    return PreferencesResponse.model_validate(prefs)


@router.put("/preferences", response_model=PreferencesResponse)
async def update_preferences(
    request: PreferencesUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PreferencesResponse:
    """Update user preferences with optional optimistic locking."""
    service = SyncService(db)

    updates = request.model_dump(exclude={"expected_version"}, exclude_none=True)
    prefs, conflict = await service.update_preferences(
        current_user.id,
        updates,
        expected_version=request.expected_version,
    )

    if conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "version_conflict",
                "message": f"Expected version {request.expected_version}, but current is {prefs.version}",
                "current_version": prefs.version,
            },
        )

    await db.commit()
    return PreferencesResponse.model_validate(prefs)


# -------------------------------------------------------------------------
# Client (Device) Routes
# -------------------------------------------------------------------------


@router.get("/clients", response_model=list[SyncClientResponse])
async def list_clients(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SyncClientResponse]:
    """List all registered sync clients for the current user."""
    service = SyncService(db)
    clients = await service.get_user_clients(current_user.id)
    return [SyncClientResponse.model_validate(c) for c in clients]


@router.post(
    "/clients", response_model=SyncClientResponse, status_code=status.HTTP_201_CREATED
)
async def register_client(
    request: RegisterClientRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SyncClientResponse:
    """Register a new sync client (device)."""
    service = SyncService(db)

    ip_address = http_request.client.host if http_request.client else None

    client = await service.register_client(
        user_id=current_user.id,
        client_name=request.client_name,
        client_type=request.client_type,
        ip_address=ip_address,
    )

    await db.commit()
    return SyncClientResponse.model_validate(client)


@router.delete(
    "/clients/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_client(
    client_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Remove a sync client."""
    service = SyncService(db)

    deleted = await service.remove_client(client_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------------
# Manifest Routes
# -------------------------------------------------------------------------


@router.post("/manifest", response_model=ManifestCompareResponse)
async def compare_manifest(
    request: SyncManifestRequest,
    http_request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ManifestCompareResponse:
    """
    Compare client manifest with cloud to determine sync actions.

    This is Phase 1 of the sync protocol - discovery phase.
    """
    service = SyncService(db)

    # Convert entries to dicts for comparison
    client_entries = [entry.model_dump() for entry in request.beatmaps]

    actions = await service.compare_manifest(current_user.id, client_entries)

    # Update client sync time if client_id provided
    if request.client_id:
        try:
            client_uuid = uuid.UUID(request.client_id)
            ip_address = http_request.client.host if http_request.client else None
            await service.update_client_sync_time(client_uuid, ip_address)
        except (ValueError, TypeError):
            pass  # Invalid client ID, ignore

    # Log the manifest comparison
    await service.log_sync_operation(
        user_id=current_user.id,
        action="manifest",
        client_id=uuid.UUID(request.client_id) if request.client_id else None,
        details={"entries_compared": len(client_entries)},
        maps_synced=len([a for a in actions if a["action"] == SyncAction.NONE.value]),
    )

    await db.commit()

    return ManifestCompareResponse(
        server_timestamp=datetime.utcnow(),
        actions=[SyncActionResponse(**a) for a in actions],
    )


@router.post("/manifest/{map_id}", status_code=status.HTTP_200_OK)
async def update_manifest_entry(
    map_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    version: int = Query(..., ge=1),
    checksum: str = Query(..., min_length=1),
) -> dict[str, Any]:
    """Update manifest entry after successful upload/download."""
    service = SyncService(db)

    entry = await service.update_manifest_entry(
        user_id=current_user.id,
        map_id=map_id,
        version=version,
        checksum=checksum,
    )

    await db.commit()

    return {
        "map_id": str(map_id),
        "version": entry.cloud_version,
        "checksum": entry.checksum,
        "sync_state": entry.sync_state.value,
    }


# -------------------------------------------------------------------------
# Conflict Routes
# -------------------------------------------------------------------------


@router.get("/conflicts", response_model=list[ConflictResponse])
async def list_conflicts(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_resolved: bool = Query(False),
) -> list[ConflictResponse]:
    """List sync conflicts for the current user."""
    service = SyncService(db)
    conflicts = await service.get_user_conflicts(
        current_user.id,
        unresolved_only=not include_resolved,
    )
    return [ConflictResponse.model_validate(c) for c in conflicts]


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    request: ResolveConflictRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConflictResponse:
    """Resolve a sync conflict."""
    service = SyncService(db)

    conflict = await service.resolve_conflict(
        conflict_id=conflict_id,
        user_id=current_user.id,
        resolution=request.resolution,
    )

    if conflict is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conflict not found",
        )

    # Log conflict resolution
    await service.log_sync_operation(
        user_id=current_user.id,
        action="conflict_resolved",
        details={
            "conflict_id": str(conflict_id),
            "resolution": request.resolution.value,
        },
    )

    await db.commit()
    return ConflictResponse.model_validate(conflict)


# -------------------------------------------------------------------------
# History & Status Routes
# -------------------------------------------------------------------------


@router.get("/history", response_model=list[SyncLogResponse])
async def get_sync_history(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=200),
) -> list[SyncLogResponse]:
    """Get recent sync history."""
    service = SyncService(db)
    logs = await service.get_sync_history(current_user.id, limit=limit)
    return [SyncLogResponse.model_validate(log) for log in logs]


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SyncStatusResponse:
    """Get overall sync status for the current user."""
    service = SyncService(db)

    # Get preferences
    prefs = await service.get_user_preferences(current_user.id)
    if prefs is None:
        prefs = await service.create_default_preferences(current_user.id)
        await db.commit()

    # Get manifest stats
    manifest = await service.get_user_manifest(current_user.id)
    total_maps = len(manifest)
    synced_maps = sum(1 for e in manifest if e.sync_state == SyncState.SYNCED)
    pending_uploads = sum(1 for e in manifest if e.sync_state == SyncState.MODIFIED)
    pending_downloads = sum(1 for e in manifest if e.sync_state == SyncState.CLOUD_ONLY)

    # Get conflicts
    conflicts = await service.get_user_conflicts(current_user.id, unresolved_only=True)

    # Get clients
    clients = await service.get_user_clients(current_user.id)

    # Get last sync time
    history = await service.get_sync_history(current_user.id, limit=1)
    last_sync = history[0].timestamp if history else None

    return SyncStatusResponse(
        preferences_version=prefs.version,
        preferences_checksum=prefs.checksum,
        total_maps=total_maps,
        synced_maps=synced_maps,
        pending_uploads=pending_uploads,
        pending_downloads=pending_downloads,
        conflicts=len(conflicts),
        last_sync=last_sync,
        clients=len(clients),
    )
