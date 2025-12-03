"""Credit system models for pay-per-use billing.

This module provides:
- CreditBalance: Tracks user's available credits
- CreditPurchase: Records credit pack purchases
- CreditTransaction: Ledger of credit usage/additions

Credits are the universal fallback for users who:
1. Don't want a subscription (casual users)
2. Exceed their Pro tier quota (power users)
3. Want to try before committing to Pro
"""

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
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .user import User


class CreditTransactionType(str, enum.Enum):
    """Types of credit transactions."""

    PURCHASE = "purchase"  # User bought credits
    CONSUMPTION = "consumption"  # Credit used for AI job
    REFUND = "refund"  # Credit refunded (rare, admin only)
    BONUS = "bonus"  # Promotional credits awarded
    SUBSCRIPTION_GRANT = "subscription_grant"  # Monthly credits from subscription
    EXPIRY = "expiry"  # Bonus credits expired (purchased never expire)


class CreditPackType(str, enum.Enum):
    """Available credit pack sizes."""

    STARTER = "starter"  # 5 credits - $1.75
    VALUE = "value"  # 15 credits - $4.50
    POWER = "power"  # 40 credits - $10.00


class CreditBalance(Base):
    """Tracks a user's current credit balance.

    Design decisions:
    - Purchased credits never expire (builds trust)
    - Bonus credits may have expiry (promotional)
    - Subscription quota consumed before credits
    - Balance is denormalized for fast reads (transactions are source of truth)
    """

    __tablename__ = "credit_balances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Current balance (denormalized from transactions)
    purchased_credits: Mapped[int] = mapped_column(Integer, default=0)
    bonus_credits: Mapped[int] = mapped_column(Integer, default=0)

    # Auto top-up settings
    auto_topup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_topup_pack: Mapped[CreditPackType | None] = mapped_column(
        SAEnum(CreditPackType), nullable=True
    )
    auto_topup_threshold: Mapped[int] = mapped_column(
        Integer, default=0
    )  # Trigger when balance <= this

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="credit_balance")
    transactions: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction", back_populates="balance", order_by="CreditTransaction.created_at.desc()"
    )

    @property
    def total_credits(self) -> int:
        """Total available credits (purchased + bonus)."""
        return self.purchased_credits + self.bonus_credits

    @property
    def has_credits(self) -> bool:
        """Check if user has any credits available."""
        return self.total_credits > 0

    def can_afford(self, amount: int = 1) -> bool:
        """Check if user can afford a certain number of credits."""
        return self.total_credits >= amount


class CreditPurchase(Base):
    """Records a credit pack purchase.

    Tracks Stripe payment and fulfillment status.
    """

    __tablename__ = "credit_purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Purchase details
    pack_type: Mapped[CreditPackType] = mapped_column(
        SAEnum(CreditPackType), nullable=False
    )
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    # Stripe references
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    # Status
    is_fulfilled: Mapped[bool] = mapped_column(Boolean, default=False)
    fulfilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Auto top-up flag
    is_auto_topup: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User")


class CreditTransaction(Base):
    """Ledger of all credit movements.

    This is the source of truth for credit balance.
    CreditBalance is denormalized for performance.
    """

    __tablename__ = "credit_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    balance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("credit_balances.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Transaction details
    transaction_type: Mapped[CreditTransactionType] = mapped_column(
        SAEnum(CreditTransactionType), nullable=False
    )
    amount: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Positive for additions, negative for consumption
    is_purchased: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # False for bonus credits

    # Balance snapshot (for audit trail)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference to related entities
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("credit_purchases.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Description for display
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    balance: Mapped["CreditBalance"] = relationship(
        "CreditBalance", back_populates="transactions"
    )
    user: Mapped["User"] = relationship("User")
    purchase: Mapped["CreditPurchase | None"] = relationship("CreditPurchase")
