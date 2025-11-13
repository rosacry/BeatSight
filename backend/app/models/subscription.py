"""Subscription and billing models."""

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


class SubscriptionPlan(str, Enum):  # type: ignore[misc]
    """Subscription tiers."""

    FREE = "free"
    PRO_MONTHLY = "pro_monthly"
    PRO_YEARLY = "pro_yearly"


class SubscriptionStatus(str, Enum):  # type: ignore[misc]
    """Subscription lifecycle state."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class Subscription(Base):
    """Tracks active subscriptions and quotas."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    plan_code: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ai_quota_remaining: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    transactions: Mapped[list["BillingTransaction"]] = relationship(
        "BillingTransaction", back_populates="subscription"
    )


class BillingProvider(str, Enum):  # type: ignore[misc]
    """Payment providers supported."""

    STRIPE = "stripe"


class BillingTransactionType(str, Enum):  # type: ignore[misc]
    """Different transaction categories."""

    SUBSCRIPTION = "subscription"
    BUNDLE_PURCHASE = "bundle_purchase"
    DONATION = "donation"


class BillingTransactionStatus(str, Enum):  # type: ignore[misc]
    """State of the payment."""

    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


class BillingTransaction(Base):
    """Transaction ledger for billing events."""

    __tablename__ = "billing_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[BillingProvider] = mapped_column(Enum(BillingProvider), nullable=False)
    provider_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    tx_type: Mapped[BillingTransactionType] = mapped_column(Enum(BillingTransactionType), nullable=False)
    status: Mapped[BillingTransactionStatus] = mapped_column(Enum(BillingTransactionStatus), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscription: Mapped[Subscription | None] = relationship("Subscription", back_populates="transactions")
