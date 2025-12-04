"""Karma ledger model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class KarmaReason(str, enum.Enum):
    """Reasons for karma adjustments."""

    FIX_ACCEPTED = "fix_accepted"
    FIX_REJECTED = "fix_rejected"
    VERIFICATION_COMPLETE = "verification_complete"
    VERIFICATION_REJECTED = "verification_rejected"
    SUBSCRIPTION_BONUS = "subscription_bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"
    MAP_UPVOTED = "map_upvoted"  # Map creator receives upvote
    MAP_DOWNVOTED = "map_downvoted"  # Map creator receives downvote
    CONTRIBUTION_APPROVED = "contribution_approved"  # Training contribution approved
    CONTRIBUTION_REJECTED = "contribution_rejected"  # Training contribution rejected


class KarmaLedger(Base):
    """Stores immutable karma events for auditing."""

    __tablename__ = "karma_ledger"
    
    # Indexes for common query patterns:
    # - user_id: get_karma_history, get_karma_stats breakdown query
    # - user_id + recorded_at: get_karma_history with ORDER BY recorded_at DESC
    # - user_id + reason_code: get_karma_stats GROUP BY reason_code
    __table_args__ = (
        Index("ix_karma_ledger_user_id", "user_id"),
        Index("ix_karma_ledger_user_recorded", "user_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[KarmaReason] = mapped_column(
        SAEnum(KarmaReason), nullable=False
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(64))
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="karma_events")
