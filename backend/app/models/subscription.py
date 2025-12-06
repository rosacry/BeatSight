"""Subscription and billing models."""

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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class SubscriptionPlan(str, enum.Enum):
    """Subscription tiers.

    Pricing Strategy (December 2025):
    - FREE: 5 songs/month - Get users hooked
    - BASIC: $8/mo, 30 songs/month - Casual drummers
    - PRO: $15/mo, unlimited - Serious musicians
    """

    FREE = "free"
    BASIC_MONTHLY = "basic_monthly"
    BASIC_YEARLY = "basic_yearly"
    PRO_MONTHLY = "pro_monthly"
    PRO_YEARLY = "pro_yearly"


class SubscriptionStatus(str, enum.Enum):
    """Subscription lifecycle state."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class Subscription(Base):
    """Tracks active subscriptions and quotas."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        # Index for looking up a user's subscription (common query)
        Index("ix_subscriptions_user_id", "user_id"),
        # Index for filtering by status (active subscriptions, batch updates)
        Index("ix_subscriptions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    plan_code: Mapped[SubscriptionPlan] = mapped_column(
        SAEnum(SubscriptionPlan), default=SubscriptionPlan.FREE
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ai_quota_remaining: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    transactions: Mapped[list["BillingTransaction"]] = relationship(
        "BillingTransaction", back_populates="subscription"
    )


class BillingProvider(str, enum.Enum):
    """Payment providers supported."""

    STRIPE = "stripe"


class BillingTransactionType(str, enum.Enum):
    """Different transaction categories."""

    SUBSCRIPTION = "subscription"
    BUNDLE_PURCHASE = "bundle_purchase"
    DONATION = "donation"


class BillingTransactionStatus(str, enum.Enum):
    """State of the payment."""

    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


class BillingTransaction(Base):
    """Transaction ledger for billing events."""

    __tablename__ = "billing_transactions"
    __table_args__ = (
        # Index for billing history queries per user
        Index("ix_billing_transactions_user_id", "user_id"),
        # Index for looking up transactions by payment provider reference
        Index("ix_billing_transactions_provider_ref", "provider_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    provider: Mapped[BillingProvider] = mapped_column(
        SAEnum(BillingProvider), nullable=False
    )
    provider_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    tx_type: Mapped[BillingTransactionType] = mapped_column(
        SAEnum(BillingTransactionType), nullable=False
    )
    status: Mapped[BillingTransactionStatus] = mapped_column(
        SAEnum(BillingTransactionStatus), nullable=False
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="transactions"
    )
