"""AI job tracking model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .map_version import MapVersion
    from .song import Song
    from .user import User


class AIJobState(str, enum.Enum):
    """Workflow states for AI generation tasks."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJobPriority(str, enum.Enum):
    """Priority tiers for AI jobs."""

    STANDARD = "standard"
    PRIORITY = "priority"


class AIJob(Base):
    """Represents a queued or completed AI mapping job."""

    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    song_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("songs.id", ondelete="CASCADE")
    )
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    state: Mapped[AIJobState] = mapped_column(
        SAEnum(AIJobState), default=AIJobState.QUEUED, nullable=False
    )
    priority: Mapped[AIJobPriority] = mapped_column(
        SAEnum(AIJobPriority), default=AIJobPriority.STANDARD, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(512))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Worker heartbeat fields for job monitoring (E2-001)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Retry tracking fields (E2-005)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    song: Mapped["Song"] = relationship("Song", back_populates="ai_jobs")
    requester: Mapped["User | None"] = relationship("User", back_populates="ai_jobs")
    output_versions: Mapped[list["MapVersion"]] = relationship(
        "MapVersion", back_populates="generation_job"
    )
