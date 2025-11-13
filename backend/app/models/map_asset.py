"""Auxiliary assets attached to map versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .map_version import MapVersion


class MapAssetType(str, Enum):  # type: ignore[misc]
    """Different types of supplemental assets."""

    WAVEFORM = "waveform"
    PREVIEW_AUDIO = "preview_audio"
    THUMBNAIL = "thumbnail"


class MapAsset(Base):
    """Stores URIs for generated secondary assets."""

    __tablename__ = "map_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_versions.id", ondelete="CASCADE")
    )
    asset_type: Mapped[MapAssetType] = mapped_column(Enum(MapAssetType), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    map_version: Mapped["MapVersion"] = relationship("MapVersion", back_populates="assets")
