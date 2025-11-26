"""Cloud sync models for user preferences and library synchronization."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class SyncState(str, enum.Enum):
    """Sync state for beatmaps and settings."""

    LOCAL = "local"  # Created locally, never synced
    SYNCED = "synced"  # In sync with cloud
    MODIFIED = "modified"  # Local changes pending upload
    CONFLICT = "conflict"  # Both local and cloud modified
    CLOUD_ONLY = "cloud_only"  # Exists in cloud, not downloaded
    DELETED = "deleted"  # Marked for deletion on next sync


class SyncAction(str, enum.Enum):
    """Actions returned by sync manifest comparison."""

    NONE = "none"  # Already in sync
    UPLOAD = "upload"  # Local → Cloud
    DOWNLOAD = "download"  # Cloud → Local
    CONFLICT = "conflict"  # Manual resolution needed
    DELETE = "delete"  # Remove from both


class ConflictResolution(str, enum.Enum):
    """How to resolve sync conflicts."""

    LAST_WRITE_WINS = "last_write_wins"
    KEEP_LOCAL = "keep_local"
    KEEP_CLOUD = "keep_cloud"
    MERGE = "merge"


class UserPreferences(Base):
    """User preferences that sync across devices."""

    __tablename__ = "user_preferences"
    __table_args__ = (Index("ix_user_preferences_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)

    # Gameplay preferences
    scroll_speed: Mapped[float | None] = mapped_column(default=1.0)
    note_skin: Mapped[str | None] = mapped_column(String(64), default="default")
    audio_offset_ms: Mapped[int | None] = mapped_column(Integer, default=0)
    visual_offset_ms: Mapped[int | None] = mapped_column(Integer, default=0)
    background_dim: Mapped[float | None] = mapped_column(default=0.5)

    # Audio preferences
    master_volume: Mapped[float | None] = mapped_column(default=1.0)
    music_volume: Mapped[float | None] = mapped_column(default=0.8)
    effects_volume: Mapped[float | None] = mapped_column(default=0.8)
    hitsound_volume: Mapped[float | None] = mapped_column(default=1.0)

    # UI preferences
    theme: Mapped[str | None] = mapped_column(String(32), default="dark")
    language: Mapped[str | None] = mapped_column(String(8), default="en")

    # Additional custom settings as JSON
    custom_settings: Mapped[dict | None] = mapped_column(JSON, default=dict)

    last_modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", backref="preferences")


class SyncClient(Base):
    """Registered sync clients (devices) for a user."""

    __tablename__ = "sync_clients"
    __table_args__ = (Index("ix_sync_clients_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_type: Mapped[str] = mapped_column(String(64), nullable=False)  # desktop, web, mobile
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", backref="sync_clients")


class SyncManifestEntry(Base):
    """Tracks sync state for each beatmap per user."""

    __tablename__ = "sync_manifest_entries"
    __table_args__ = (
        Index("ix_sync_manifest_user_map", "user_id", "map_id"),
        Index("ix_sync_manifest_user_state", "user_id", "sync_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maps.id", ondelete="CASCADE")
    )
    local_version: Mapped[int] = mapped_column(Integer, default=0)
    cloud_version: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    sync_state: Mapped[SyncState] = mapped_column(
        SAEnum(SyncState), default=SyncState.SYNCED, nullable=False
    )
    last_modified: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", backref="sync_manifest")


class SyncConflict(Base):
    """Records sync conflicts for manual resolution."""

    __tablename__ = "sync_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maps.id", ondelete="CASCADE")
    )
    local_version: Mapped[int] = mapped_column(Integer, nullable=False)
    cloud_version: Mapped[int] = mapped_column(Integer, nullable=False)
    local_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    cloud_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    differences: Mapped[dict | None] = mapped_column(JSON)  # Detailed diff info
    resolution: Mapped[ConflictResolution | None] = mapped_column(SAEnum(ConflictResolution))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", backref="sync_conflicts")


class SyncLog(Base):
    """Audit log for sync operations."""

    __tablename__ = "sync_logs"
    __table_args__ = (Index("ix_sync_logs_user_id_timestamp", "user_id", "timestamp"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_clients.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # manifest, upload, download, conflict_resolved
    details: Mapped[dict | None] = mapped_column(JSON)
    maps_synced: Mapped[int] = mapped_column(Integer, default=0)
    bytes_transferred: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", backref="sync_logs")
