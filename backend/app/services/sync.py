"""Cloud sync service for user preferences and beatmap library synchronization."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync import (
    ConflictResolution,
    SyncAction,
    SyncClient,
    SyncConflict,
    SyncLog,
    SyncManifestEntry,
    SyncState,
    UserPreferences,
)

logger = logging.getLogger(__name__)


class SyncService:
    """Service for managing cloud synchronization of user data."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize sync service with database session."""
        self.db = db

    # -------------------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------------------

    async def get_user_preferences(self, user_id: uuid.UUID) -> UserPreferences | None:
        """Get user preferences, creating defaults if not exists."""
        result = await self.db.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_default_preferences(self, user_id: uuid.UUID) -> UserPreferences:
        """Create default preferences for a new user."""
        defaults = {
            "scroll_speed": 1.0,
            "note_skin": "default",
            "audio_offset_ms": 0,
            "visual_offset_ms": 0,
            "background_dim": 0.5,
            "master_volume": 1.0,
            "music_volume": 0.8,
            "effects_volume": 0.8,
            "hitsound_volume": 1.0,
            "theme": "dark",
            "language": "en",
            "custom_settings": {},
        }
        checksum = self._compute_checksum(defaults)
        
        prefs = UserPreferences(
            user_id=user_id,
            version=1,  # Explicitly set initial version
            checksum=checksum,
            **defaults,
        )
        self.db.add(prefs)
        await self.db.flush()
        return prefs

    async def update_preferences(
        self,
        user_id: uuid.UUID,
        updates: dict[str, Any],
        expected_version: int | None = None,
    ) -> tuple[UserPreferences, bool]:
        """
        Update user preferences with optional optimistic locking.
        
        Returns (preferences, conflict_occurred).
        """
        prefs = await self.get_user_preferences(user_id)
        if prefs is None:
            prefs = await self.create_default_preferences(user_id)

        # Check for version conflict
        if expected_version is not None and prefs.version != expected_version:
            return prefs, True

        # Apply updates
        allowed_fields = {
            "scroll_speed", "note_skin", "audio_offset_ms", "visual_offset_ms",
            "background_dim", "master_volume", "music_volume", "effects_volume",
            "hitsound_volume", "theme", "language", "custom_settings",
        }
        
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(prefs, key, value)

        # Update version and checksum
        prefs.version += 1
        prefs.checksum = self._compute_preferences_checksum(prefs)
        prefs.last_modified = datetime.now(timezone.utc)

        await self.db.flush()
        return prefs, False

    def _compute_preferences_checksum(self, prefs: UserPreferences) -> str:
        """Compute checksum for preferences object."""
        data = {
            "scroll_speed": prefs.scroll_speed,
            "note_skin": prefs.note_skin,
            "audio_offset_ms": prefs.audio_offset_ms,
            "visual_offset_ms": prefs.visual_offset_ms,
            "background_dim": prefs.background_dim,
            "master_volume": prefs.master_volume,
            "music_volume": prefs.music_volume,
            "effects_volume": prefs.effects_volume,
            "hitsound_volume": prefs.hitsound_volume,
            "theme": prefs.theme,
            "language": prefs.language,
            "custom_settings": prefs.custom_settings or {},
        }
        return self._compute_checksum(data)

    # -------------------------------------------------------------------------
    # Sync Clients (Devices)
    # -------------------------------------------------------------------------

    async def register_client(
        self,
        user_id: uuid.UUID,
        client_name: str,
        client_type: str,
        ip_address: str | None = None,
    ) -> SyncClient:
        """Register a new sync client (device) for a user."""
        client = SyncClient(
            user_id=user_id,
            client_name=client_name,
            client_type=client_type,
            last_ip=ip_address,
        )
        self.db.add(client)
        await self.db.flush()
        
        logger.info(f"Registered sync client {client.id} for user {user_id}")
        return client

    async def get_user_clients(self, user_id: uuid.UUID) -> Sequence[SyncClient]:
        """Get all registered sync clients for a user."""
        result = await self.db.execute(
            select(SyncClient)
            .where(SyncClient.user_id == user_id)
            .order_by(SyncClient.last_sync_at.desc().nullslast())
        )
        return result.scalars().all()

    async def update_client_sync_time(
        self,
        client_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> None:
        """Update last sync time for a client."""
        result = await self.db.execute(
            select(SyncClient).where(SyncClient.id == client_id)
        )
        client = result.scalar_one_or_none()
        if client:
            client.last_sync_at = datetime.now(timezone.utc)
            if ip_address:
                client.last_ip = ip_address
            await self.db.flush()

    async def remove_client(self, client_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Remove a sync client. Returns True if deleted."""
        result = await self.db.execute(
            select(SyncClient).where(
                and_(SyncClient.id == client_id, SyncClient.user_id == user_id)
            )
        )
        client = result.scalar_one_or_none()
        if client:
            await self.db.delete(client)
            await self.db.flush()
            return True
        return False

    # -------------------------------------------------------------------------
    # Sync Manifest
    # -------------------------------------------------------------------------

    async def get_user_manifest(
        self,
        user_id: uuid.UUID,
        since: datetime | None = None,
    ) -> Sequence[SyncManifestEntry]:
        """Get sync manifest entries for a user, optionally filtered by time."""
        query = select(SyncManifestEntry).where(SyncManifestEntry.user_id == user_id)
        
        if since:
            query = query.where(SyncManifestEntry.last_modified > since)
        
        result = await self.db.execute(query.order_by(SyncManifestEntry.last_modified.desc()))
        return result.scalars().all()

    async def get_manifest_entry(
        self,
        user_id: uuid.UUID,
        map_id: uuid.UUID,
    ) -> SyncManifestEntry | None:
        """Get a specific manifest entry."""
        result = await self.db.execute(
            select(SyncManifestEntry).where(
                and_(
                    SyncManifestEntry.user_id == user_id,
                    SyncManifestEntry.map_id == map_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def compare_manifest(
        self,
        user_id: uuid.UUID,
        client_entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Compare client manifest with cloud and determine sync actions.
        
        Returns list of actions: {map_id, action, reason, ...}
        """
        actions = []
        
        # Get cloud manifest
        cloud_entries = await self.get_user_manifest(user_id)
        cloud_by_map = {entry.map_id: entry for entry in cloud_entries}
        
        # Check each client entry
        client_map_ids = set()
        for client_entry in client_entries:
            map_id = uuid.UUID(client_entry["map_id"])
            client_map_ids.add(map_id)
            
            cloud_entry = cloud_by_map.get(map_id)
            
            if cloud_entry is None:
                # New map from client
                actions.append({
                    "map_id": str(map_id),
                    "action": SyncAction.UPLOAD.value,
                    "reason": "local_only",
                })
            elif client_entry.get("checksum") == cloud_entry.checksum:
                # Already in sync
                actions.append({
                    "map_id": str(map_id),
                    "action": SyncAction.NONE.value,
                    "reason": "checksums_match",
                })
            elif client_entry.get("version", 0) > cloud_entry.cloud_version:
                # Client has newer version
                actions.append({
                    "map_id": str(map_id),
                    "action": SyncAction.UPLOAD.value,
                    "reason": "local_newer",
                })
            elif client_entry.get("version", 0) < cloud_entry.cloud_version:
                # Cloud has newer version
                actions.append({
                    "map_id": str(map_id),
                    "action": SyncAction.DOWNLOAD.value,
                    "reason": "cloud_newer",
                    "cloud_version": cloud_entry.cloud_version,
                    "cloud_checksum": cloud_entry.checksum,
                })
            else:
                # Same version but different checksums = conflict
                actions.append({
                    "map_id": str(map_id),
                    "action": SyncAction.CONFLICT.value,
                    "reason": "both_modified",
                    "local_version": client_entry.get("version"),
                    "cloud_version": cloud_entry.cloud_version,
                })
        
        # Check for cloud-only maps
        for map_id, cloud_entry in cloud_by_map.items():
            if map_id not in client_map_ids:
                if cloud_entry.sync_state == SyncState.DELETED:
                    actions.append({
                        "map_id": str(map_id),
                        "action": SyncAction.DELETE.value,
                        "reason": "deleted_in_cloud",
                    })
                else:
                    actions.append({
                        "map_id": str(map_id),
                        "action": SyncAction.DOWNLOAD.value,
                        "reason": "cloud_only",
                        "cloud_version": cloud_entry.cloud_version,
                        "cloud_checksum": cloud_entry.checksum,
                    })
        
        return actions

    async def update_manifest_entry(
        self,
        user_id: uuid.UUID,
        map_id: uuid.UUID,
        version: int,
        checksum: str,
        sync_state: SyncState = SyncState.SYNCED,
    ) -> SyncManifestEntry:
        """Create or update a manifest entry after successful sync."""
        entry = await self.get_manifest_entry(user_id, map_id)
        
        if entry is None:
            entry = SyncManifestEntry(
                user_id=user_id,
                map_id=map_id,
                local_version=version,
                cloud_version=version,
                checksum=checksum,
                sync_state=sync_state,
            )
            self.db.add(entry)
        else:
            entry.cloud_version = version
            entry.local_version = version
            entry.checksum = checksum
            entry.sync_state = sync_state
        
        entry.last_synced_at = datetime.now(timezone.utc)
        entry.last_modified = datetime.now(timezone.utc)
        
        await self.db.flush()
        return entry

    # -------------------------------------------------------------------------
    # Conflict Resolution
    # -------------------------------------------------------------------------

    async def create_conflict(
        self,
        user_id: uuid.UUID,
        map_id: uuid.UUID,
        local_version: int,
        cloud_version: int,
        local_checksum: str,
        cloud_checksum: str,
        differences: dict[str, Any] | None = None,
    ) -> SyncConflict:
        """Record a sync conflict for later resolution."""
        conflict = SyncConflict(
            user_id=user_id,
            map_id=map_id,
            local_version=local_version,
            cloud_version=cloud_version,
            local_checksum=local_checksum,
            cloud_checksum=cloud_checksum,
            differences=differences,
        )
        self.db.add(conflict)
        await self.db.flush()
        
        logger.warning(f"Created sync conflict for map {map_id}, user {user_id}")
        return conflict

    async def get_user_conflicts(
        self,
        user_id: uuid.UUID,
        unresolved_only: bool = True,
    ) -> Sequence[SyncConflict]:
        """Get sync conflicts for a user."""
        query = select(SyncConflict).where(SyncConflict.user_id == user_id)
        
        if unresolved_only:
            query = query.where(SyncConflict.resolved_at.is_(None))
        
        result = await self.db.execute(query.order_by(SyncConflict.created_at.desc()))
        return result.scalars().all()

    async def resolve_conflict(
        self,
        conflict_id: uuid.UUID,
        user_id: uuid.UUID,
        resolution: ConflictResolution,
    ) -> SyncConflict | None:
        """Resolve a sync conflict."""
        result = await self.db.execute(
            select(SyncConflict).where(
                and_(SyncConflict.id == conflict_id, SyncConflict.user_id == user_id)
            )
        )
        conflict = result.scalar_one_or_none()
        
        if conflict:
            conflict.resolution = resolution
            conflict.resolved_at = datetime.now(timezone.utc)
            await self.db.flush()
            
            logger.info(f"Resolved conflict {conflict_id} with {resolution.value}")
        
        return conflict

    # -------------------------------------------------------------------------
    # Sync Logging
    # -------------------------------------------------------------------------

    async def log_sync_operation(
        self,
        user_id: uuid.UUID,
        action: str,
        client_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        maps_synced: int = 0,
        bytes_transferred: int = 0,
    ) -> SyncLog:
        """Log a sync operation for auditing."""
        log_entry = SyncLog(
            user_id=user_id,
            client_id=client_id,
            action=action,
            details=details,
            maps_synced=maps_synced,
            bytes_transferred=bytes_transferred,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def get_sync_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[SyncLog]:
        """Get recent sync history for a user."""
        result = await self.db.execute(
            select(SyncLog)
            .where(SyncLog.user_id == user_id)
            .order_by(SyncLog.timestamp.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _compute_checksum(data: dict[str, Any]) -> str:
        """Compute SHA-256 checksum for data dict."""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    @staticmethod
    def compute_beatmap_checksum(beatmap_data: dict[str, Any]) -> str:
        """Compute checksum for beatmap JSON."""
        # Include only content-relevant fields
        relevant_data = {
            "metadata": beatmap_data.get("metadata", {}),
            "timing": beatmap_data.get("timing", {}),
            "hitObjects": beatmap_data.get("hitObjects", []),
        }
        return SyncService._compute_checksum(relevant_data)
