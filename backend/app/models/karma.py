"""Karma ledger model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class KarmaReason(str, Enum):  # type: ignore[misc]
    """Reasons for karma adjustments."""

    FIX_ACCEPTED = "fix_accepted"
    FIX_REJECTED = "fix_rejected"
    VERIFICATION_COMPLETE = "verification_complete"
    VERIFICATION_REJECTED = "verification_rejected"
    SUBSCRIPTION_BONUS = "subscription_bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"


class KarmaLedger(Base):
    """Stores immutable karma events for auditing."""

    __tablename__ = "karma_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_code: Mapped[KarmaReason] = mapped_column(Enum(KarmaReason), nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(64))
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="karma_events")
