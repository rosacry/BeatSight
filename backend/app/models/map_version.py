"""Map version model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .ai_job import AIJob
    from .map_asset import MapAsset
    from .map_edit import MapEditProposal
    from .song import Map


class MapSource(str, Enum):  # type: ignore[misc]
    """Enumerates how a map version was generated."""

    AI = "ai"
    MANUAL = "manual"
    EDIT = "edit"


class MapVersion(Base):
    """Concrete version of a map, referencing stored artifacts."""

    __tablename__ = "map_versions"
    __table_args__ = (UniqueConstraint("map_id", "version_number", name="uq_map_version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("maps.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[MapSource] = mapped_column(Enum(MapSource), default=MapSource.AI, nullable=False)
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_jobs.id", ondelete="SET NULL")
    )
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    stem_uri: Mapped[str | None] = mapped_column(String(512))
    diff_summary: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    map: Mapped["Map"] = relationship("Map", back_populates="versions")
    generation_job: Mapped["AIJob" | None] = relationship("AIJob", back_populates="output_versions")
    assets: Mapped[list["MapAsset"]] = relationship("MapAsset", back_populates="map_version", cascade="all, delete-orphan")
    edit_proposals: Mapped[list["MapEditProposal"]] = relationship(
        "MapEditProposal", back_populates="map_version", cascade="all, delete-orphan"
    )
