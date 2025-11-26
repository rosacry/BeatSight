"""Push subscription model for WebPush notifications."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class PushSubscription(Base):
    """Web Push subscription for a user.

    Stores the push subscription endpoint and keys needed to send
    push notifications to a user's browser.
    """

    __tablename__ = "push_subscriptions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Subscription endpoint (unique per browser/device)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Push keys from browser
    p256dh_key: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # User association
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional device/browser identifier for user to manage subscriptions
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="push_subscriptions")

    __table_args__ = (
        # Ensure unique endpoint per user (in case of endpoint reuse)
        UniqueConstraint(
            "user_id", "endpoint", name="uq_push_subscription_user_endpoint"
        ),
        Index("ix_push_subscription_user_id", "user_id"),
    )

    def to_subscription_info(self) -> dict:
        """Convert to format expected by pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key,
            },
        }
