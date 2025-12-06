"""Credit service for managing user credits and purchases.

This service handles:
- Credit balance management
- Credit consumption (for AI jobs)
- Credit pack purchases
- Auto top-up logic
- Transaction history
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credits import (
    CreditBalance,
    CreditPackType,
    CreditPurchase,
    CreditTransaction,
    CreditTransactionType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CREDIT PACK CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class CreditPackConfig:
    """Configuration for a credit pack."""

    pack_type: CreditPackType
    credits: int
    price_cents: int
    name: str
    description: str

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100

    @property
    def per_credit_cents(self) -> float:
        return self.price_cents / self.credits

    @property
    def savings_percent(self) -> int:
        """Savings compared to starter pack."""
        base_rate = 35  # Starter pack is $0.35/credit
        return int((1 - self.per_credit_cents / base_rate) * 100)


# Define available credit packs
CREDIT_PACKS: dict[CreditPackType, CreditPackConfig] = {
    CreditPackType.STARTER: CreditPackConfig(
        pack_type=CreditPackType.STARTER,
        credits=15,
        price_cents=500,  # $5.00
        name="Starter Pack",
        description="15 credits - great for getting started",
    ),
    CreditPackType.VALUE: CreditPackConfig(
        pack_type=CreditPackType.VALUE,
        credits=30,
        price_cents=1000,  # $10.00 ($0.33/credit)
        name="Value Pack",
        description="30 credits - Save 5%",
    ),
    CreditPackType.POWER: CreditPackConfig(
        pack_type=CreditPackType.POWER,
        credits=75,
        price_cents=2500,  # $25.00 ($0.33/credit)
        name="Power Pack",
        description="75 credits - Best value",
    ),
}


def get_pack_config(pack_type: CreditPackType) -> CreditPackConfig:
    """Get configuration for a credit pack."""
    return CREDIT_PACKS[pack_type]


def get_all_packs() -> list[dict[str, Any]]:
    """Get all credit packs for API response."""
    return [
        {
            "id": pack.pack_type.value,
            "name": pack.name,
            "description": pack.description,
            "credits": pack.credits,
            "price_cents": pack.price_cents,
            "price_dollars": pack.price_dollars,
            "per_credit_cents": round(pack.per_credit_cents, 1),
            "savings_percent": pack.savings_percent,
        }
        for pack in CREDIT_PACKS.values()
    ]


# =============================================================================
# CREDIT SERVICE
# =============================================================================


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient credits: need {required}, have {available}")


@dataclass
class CreditStatus:
    """Current credit status for a user."""

    purchased_credits: int
    bonus_credits: int
    total_credits: int
    auto_topup_enabled: bool
    auto_topup_pack: CreditPackType | None

    @property
    def has_credits(self) -> bool:
        return self.total_credits > 0


class CreditService:
    """Service for managing user credits."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_or_create_balance(
        self, user_id: uuid.UUID, for_update: bool = False
    ) -> CreditBalance:
        """Get or create a credit balance for a user.

        Args:
            user_id: The user's ID
            for_update: If True, acquire a row-level lock (FOR UPDATE) to prevent
                       concurrent modifications. Use this when you intend to modify
                       the balance to prevent race conditions.
        """
        query = select(CreditBalance).where(CreditBalance.user_id == user_id)

        if for_update:
            # Acquire row-level lock to prevent concurrent modifications
            # This ensures only one transaction can modify this balance at a time
            query = query.with_for_update()

        result = await self._session.execute(query)
        balance = result.scalar_one_or_none()

        if not balance:
            # Create new balance - use INSERT with ON CONFLICT to handle race
            # condition where two requests try to create balance simultaneously
            balance = CreditBalance(user_id=user_id)
            self._session.add(balance)
            try:
                await self._session.flush()
                logger.info(f"Created credit balance for user {user_id}")
            except Exception:
                # Another transaction created it first, rollback and re-query
                await self._session.rollback()
                result = await self._session.execute(
                    select(CreditBalance)
                    .where(CreditBalance.user_id == user_id)
                    .with_for_update()
                    if for_update
                    else select(CreditBalance).where(CreditBalance.user_id == user_id)
                )
                balance = result.scalar_one()

        return balance

    async def get_status(self, user_id: uuid.UUID) -> CreditStatus:
        """Get current credit status for a user."""
        balance = await self.get_or_create_balance(user_id)
        return CreditStatus(
            purchased_credits=balance.purchased_credits,
            bonus_credits=balance.bonus_credits,
            total_credits=balance.total_credits,
            auto_topup_enabled=balance.auto_topup_enabled,
            auto_topup_pack=balance.auto_topup_pack,
        )

    async def add_credits(
        self,
        user_id: uuid.UUID,
        amount: int,
        transaction_type: CreditTransactionType,
        is_purchased: bool = True,
        purchase_id: uuid.UUID | None = None,
        description: str | None = None,
    ) -> CreditBalance:
        """Add credits to a user's balance.

        Args:
            user_id: User to add credits to
            amount: Number of credits to add (positive)
            transaction_type: Type of transaction
            is_purchased: True for purchased credits (never expire)
            purchase_id: Related purchase record if applicable
            description: Human-readable description

        Uses row-level locking to ensure atomic balance updates.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Use FOR UPDATE to prevent race conditions when adding credits
        balance = await self.get_or_create_balance(user_id, for_update=True)

        # Update balance
        if is_purchased:
            balance.purchased_credits += amount
        else:
            balance.bonus_credits += amount

        # Create transaction record
        transaction = CreditTransaction(
            balance_id=balance.id,
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            is_purchased=is_purchased,
            balance_after=balance.total_credits,
            purchase_id=purchase_id,
            description=description or f"Added {amount} credits",
        )
        self._session.add(transaction)

        await self._session.flush()
        logger.info(
            f"Added {amount} credits to user {user_id} ({transaction_type.value})"
        )

        return balance

    async def consume_credit(
        self,
        user_id: uuid.UUID,
        ai_job_id: uuid.UUID | None = None,
        description: str | None = None,
    ) -> CreditBalance:
        """Consume one credit for an AI job.

        Consumes bonus credits first, then purchased credits.
        Raises InsufficientCreditsError if no credits available.

        Uses row-level locking (FOR UPDATE) to prevent race conditions
        where concurrent requests could overdraw the balance.
        """
        # Use FOR UPDATE to prevent concurrent modifications
        # This ensures atomicity of the check-then-modify operation
        balance = await self.get_or_create_balance(user_id, for_update=True)

        if not balance.has_credits:
            raise InsufficientCreditsError(required=1, available=0)

        # Consume bonus credits first (they might expire)
        is_purchased = True
        if balance.bonus_credits > 0:
            balance.bonus_credits -= 1
            is_purchased = False
        else:
            balance.purchased_credits -= 1

        # Create transaction record
        transaction = CreditTransaction(
            balance_id=balance.id,
            user_id=user_id,
            transaction_type=CreditTransactionType.CONSUMPTION,
            amount=-1,
            is_purchased=is_purchased,
            balance_after=balance.total_credits,
            ai_job_id=ai_job_id,
            description=description or "AI beatmap generation",
        )
        self._session.add(transaction)

        await self._session.flush()
        logger.info(
            f"Consumed 1 credit from user {user_id}, remaining: {balance.total_credits}"
        )

        return balance

    async def create_purchase(
        self,
        user_id: uuid.UUID,
        pack_type: CreditPackType,
        stripe_payment_intent_id: str | None = None,
        stripe_checkout_session_id: str | None = None,
        is_auto_topup: bool = False,
    ) -> CreditPurchase:
        """Create a credit purchase record (before payment).

        The purchase will be fulfilled after payment confirmation.
        """
        pack = get_pack_config(pack_type)

        purchase = CreditPurchase(
            user_id=user_id,
            pack_type=pack_type,
            credits_amount=pack.credits,
            price_cents=pack.price_cents,
            stripe_payment_intent_id=stripe_payment_intent_id,
            stripe_checkout_session_id=stripe_checkout_session_id,
            is_auto_topup=is_auto_topup,
        )
        self._session.add(purchase)
        await self._session.flush()

        logger.info(
            f"Created credit purchase {purchase.id} for user {user_id}: "
            f"{pack.credits} credits for ${pack.price_dollars}"
        )

        return purchase

    async def fulfill_purchase(self, purchase_id: uuid.UUID) -> CreditBalance:
        """Fulfill a credit purchase after payment confirmation.

        Called by Stripe webhook handler.
        Uses row-level locking to prevent double-fulfillment from concurrent webhooks.
        """
        # Lock the purchase row to prevent double-fulfillment from concurrent webhooks
        result = await self._session.execute(
            select(CreditPurchase)
            .where(CreditPurchase.id == purchase_id)
            .with_for_update()
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            raise ValueError(f"Purchase not found: {purchase_id}")

        if purchase.is_fulfilled:
            logger.warning(f"Purchase {purchase_id} already fulfilled")
            balance = await self.get_or_create_balance(purchase.user_id)
            return balance

        # Mark as fulfilled
        purchase.is_fulfilled = True
        purchase.fulfilled_at = datetime.now(timezone.utc)

        # Add credits to balance
        balance = await self.add_credits(
            user_id=purchase.user_id,
            amount=purchase.credits_amount,
            transaction_type=CreditTransactionType.PURCHASE,
            is_purchased=True,
            purchase_id=purchase.id,
            description=f"Purchased {purchase.credits_amount} credits ({purchase.pack_type.value} pack)",
        )

        logger.info(
            f"Fulfilled purchase {purchase_id}: {purchase.credits_amount} credits"
        )

        return balance

    async def fulfill_purchase_by_payment_intent(
        self, payment_intent_id: str
    ) -> CreditBalance | None:
        """Fulfill a purchase by Stripe payment intent ID.

        Called by webhook handler.
        """
        result = await self._session.execute(
            select(CreditPurchase).where(
                CreditPurchase.stripe_payment_intent_id == payment_intent_id
            )
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            logger.warning(f"No purchase found for payment intent: {payment_intent_id}")
            return None

        return await self.fulfill_purchase(purchase.id)

    async def get_transaction_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CreditTransaction]:
        """Get credit transaction history for a user."""
        balance = await self.get_or_create_balance(user_id)

        result = await self._session.execute(
            select(CreditTransaction)
            .where(CreditTransaction.balance_id == balance.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        return list(result.scalars().all())

    async def get_purchase_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CreditPurchase]:
        """Get credit purchase history for a user."""
        result = await self._session.execute(
            select(CreditPurchase)
            .where(CreditPurchase.user_id == user_id)
            .order_by(CreditPurchase.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        return list(result.scalars().all())

    async def configure_auto_topup(
        self,
        user_id: uuid.UUID,
        enabled: bool,
        pack_type: CreditPackType | None = None,
        threshold: int = 0,
    ) -> CreditBalance:
        """Configure auto top-up settings.

        Args:
            user_id: User to configure
            enabled: Whether auto top-up is enabled
            pack_type: Which pack to buy when triggered
            threshold: Trigger when balance <= this (default 0)
        """
        balance = await self.get_or_create_balance(user_id)

        balance.auto_topup_enabled = enabled
        if enabled:
            balance.auto_topup_pack = pack_type or CreditPackType.VALUE
            balance.auto_topup_threshold = threshold
        else:
            balance.auto_topup_pack = None
            balance.auto_topup_threshold = 0

        await self._session.flush()

        logger.info(
            f"Configured auto top-up for user {user_id}: "
            f"enabled={enabled}, pack={balance.auto_topup_pack}, threshold={threshold}"
        )

        return balance

    async def check_auto_topup_needed(
        self, user_id: uuid.UUID
    ) -> CreditPackType | None:
        """Check if auto top-up should be triggered.

        Returns the pack type to purchase if auto top-up is needed, None otherwise.
        """
        balance = await self.get_or_create_balance(user_id)

        if not balance.auto_topup_enabled:
            return None

        if balance.total_credits <= balance.auto_topup_threshold:
            return balance.auto_topup_pack

        return None

    async def grant_bonus_credits(
        self,
        user_id: uuid.UUID,
        amount: int,
        description: str,
    ) -> CreditBalance:
        """Grant bonus credits to a user (promotional).

        Bonus credits are consumed before purchased credits
        but may have expiry (handled separately).
        """
        return await self.add_credits(
            user_id=user_id,
            amount=amount,
            transaction_type=CreditTransactionType.BONUS,
            is_purchased=False,
            description=description,
        )
