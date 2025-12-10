"""User settings model for privacy and preferences."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from .user import User


class UploadVisibility(str, enum.Enum):
    """Visibility options for user uploads."""

    PUBLIC = "public"  # Visible to everyone, linked to profile
    ANONYMOUS = "anonymous"  # Visible to everyone, not linked to profile
    PRIVATE = "private"  # Only visible to uploader


class ReEvaluationPolicy(str, enum.Enum):
    """User preference for AI re-evaluation of their maps."""

    AUTO_FREE = "auto_free"  # Auto-improve unverified maps when model updates (free)
    OPT_IN = "opt_in"  # Only re-evaluate when user requests
    OPT_OUT = "opt_out"  # Never re-evaluate, keep original


class UserSettings(Base):
    """User-configurable settings for privacy and preferences.

    This model stores user preferences that affect how their content
    is displayed and how the AI system handles their uploads.

    Key settings:
    - Upload visibility: Control whether uploads are public, anonymous, or private
    - Re-evaluation policy: Control automatic AI improvement of unverified maps
    - Notification preferences: Control what notifications to receive
    """

    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # -------------------------------------------------------------------------
    # Privacy Settings
    # -------------------------------------------------------------------------

    # Default visibility for new uploads
    default_upload_visibility: Mapped[UploadVisibility] = mapped_column(
        SAEnum(UploadVisibility, values_callable=lambda x: [e.value for e in x]),
        default=UploadVisibility.PUBLIC,
        nullable=False,
        comment="Default visibility for new song uploads",
    )

    # Profile visibility settings
    show_activity_on_profile: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Show recent activity (uploads, edits) on public profile",
    )
    show_statistics_on_profile: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Show statistics (total maps, accuracy score) on public profile",
    )

    # Anonymous mode settings
    hide_from_leaderboards: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="Hide user from public leaderboards (karma, verifiers, contributors)",
    )
    hide_from_public_queues: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="Hide user's jobs from public queue view",
    )

    # -------------------------------------------------------------------------
    # AI Re-evaluation Settings
    # -------------------------------------------------------------------------

    # How to handle AI model improvements for user's unverified maps
    re_evaluation_policy: Mapped[ReEvaluationPolicy] = mapped_column(
        SAEnum(ReEvaluationPolicy, values_callable=lambda x: [e.value for e in x]),
        default=ReEvaluationPolicy.AUTO_FREE,
        nullable=False,
        comment="User preference for AI re-evaluation of unverified maps",
    )

    # Track last acknowledged model version (to avoid repeated re-evaluation prompts)
    last_acknowledged_model_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
        comment="Last AI model version the user acknowledged/dismissed",
    )

    # -------------------------------------------------------------------------
    # Notification Settings
    # -------------------------------------------------------------------------

    notify_job_complete: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Notify when AI job completes",
    )
    notify_map_verified: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Notify when user's map is verified by community",
    )
    notify_re_evaluation_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Notify when AI model improves and re-evaluation is available",
    )
    notify_weekly_summary: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="Send weekly summary of activity and new features",
    )

    # -------------------------------------------------------------------------
    # Timestamps
    # -------------------------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # -------------------------------------------------------------------------
    # Relationships
    # -------------------------------------------------------------------------

    user: Mapped["User"] = relationship("User", back_populates="settings")
