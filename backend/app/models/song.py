"""Song and map models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .ai_job import AIJob
    from .map_version import MapVersion
    from .map_vote import MapVote
    from .user import User


class SongStatus(str, enum.Enum):
    """Lifecycle status for a song."""

    PENDING = "pending"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    ARCHIVED = "archived"


class MapState(str, enum.Enum):
    """Lifecycle for a map variant."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    ARCHIVED = "archived"


class Song(Base):
    """Canonical song metadata derived from fingerprinting."""

    __tablename__ = "songs"
    __table_args__ = (
        UniqueConstraint("fingerprint_hash", name="uq_song_fingerprint"),
        Index("ix_song_status", "status"),
        # Index for "My Songs" page - finding songs created by a user
        Index("ix_songs_created_by_id", "created_by_id"),
        # Index for sorting by creation date (newest first pagination)
        Index("ix_songs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fingerprint_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artist: Mapped[str] = mapped_column(String(255), nullable=False)
    bpm: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[SongStatus] = mapped_column(
        SAEnum(SongStatus), default=SongStatus.PENDING, nullable=False
    )
    canonical_map_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maps.id")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    maps: Mapped[list["Map"]] = relationship(
        "Map",
        back_populates="song",
        cascade="all, delete-orphan",
        foreign_keys="Map.song_id",
    )
    canonical_map: Mapped["Map | None"] = relationship(
        "Map", foreign_keys=[canonical_map_id], post_update=True
    )
    creator: Mapped["User | None"] = relationship("User", back_populates="songs")
    ai_jobs: Mapped[list["AIJob"]] = relationship("AIJob", back_populates="song")


class Map(Base):
    """Difficulty-specific beatmap for a song."""

    __tablename__ = "maps"
    __table_args__ = (Index("ix_map_state", "state"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("songs.id", ondelete="CASCADE")
    )
    difficulty_label: Mapped[str] = mapped_column(String(64), nullable=False)
    is_canonical: Mapped[bool] = mapped_column(default=False)
    state: Mapped[MapState] = mapped_column(
        SAEnum(MapState), default=MapState.UNVERIFIED, nullable=False
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_versions.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    song: Mapped[Song] = relationship(
        "Song", back_populates="maps", foreign_keys=[song_id]
    )
    versions: Mapped[list["MapVersion"]] = relationship(
        "MapVersion",
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="MapVersion.version_number",
        foreign_keys="MapVersion.map_id",
    )
    current_version: Mapped["MapVersion | None"] = relationship(
        "MapVersion", foreign_keys=[current_version_id], post_update=True
    )
    votes: Mapped[list["MapVote"]] = relationship(
        "MapVote", back_populates="map", cascade="all, delete-orphan"
    )
