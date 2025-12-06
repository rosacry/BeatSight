"""Webhook event tracking model for idempotency."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedWebhookEvent(Base):
    """Tracks processed webhook events to ensure idempotency.

    Stripe may send the same webhook event multiple times due to retries.
    This table records processed events to prevent duplicate processing.
    """

    __tablename__ = "processed_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The provider's event ID (e.g., Stripe's evt_xxx)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    # Event type (e.g., checkout.session.completed)
    event_type: Mapped[str] = mapped_column(String(128))
    # Provider name (stripe, modal, etc.)
    provider: Mapped[str] = mapped_column(String(32))
    # When the event was processed
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Optional extra data about the processing (renamed from 'metadata' which is reserved)
    event_metadata: Mapped[str | None] = mapped_column(String(512))
