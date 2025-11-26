"""Stripe payment service for subscription management.

Handles:
- Creating checkout sessions for subscription upgrades
- Managing customer portal sessions
- Processing Stripe webhooks
- Syncing subscription status from Stripe
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.subscription import (
    BillingProvider,
    BillingTransaction,
    BillingTransactionStatus,
    BillingTransactionType,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment operations."""

    def __init__(self):
        settings = get_settings()
        self.secret_key = settings.stripe_secret_key
        self.webhook_secret = settings.stripe_webhook_secret
        self.pro_monthly_price_id = settings.stripe_pro_monthly_price_id
        self.pro_yearly_price_id = settings.stripe_pro_yearly_price_id
        self.frontend_url = settings.frontend_url or "http://localhost:5173"

        if self.secret_key:
            stripe.api_key = self.secret_key

    def is_configured(self) -> bool:
        """Check if Stripe is properly configured."""
        return bool(self.secret_key and self.webhook_secret)

    async def get_or_create_customer(
        self,
        db: AsyncSession,
        user: User,
    ) -> str:
        """Get existing Stripe customer ID or create a new one.

        Stores the customer ID in the user's subscription record.
        """
        # Check if user already has a Stripe customer ID
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.current_period_start.desc())
        )
        existing_sub = result.scalars().first()

        # Look for existing customer ID in transactions
        if existing_sub:
            tx_result = await db.execute(
                select(BillingTransaction)
                .where(
                    BillingTransaction.user_id == user.id,
                    BillingTransaction.provider == BillingProvider.STRIPE,
                )
                .limit(1)
            )
            existing_tx = tx_result.scalars().first()
            if existing_tx and existing_tx.provider_ref.startswith("cus_"):
                return existing_tx.provider_ref.split(":")[0]

        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name,
            metadata={
                "user_id": str(user.id),
                "display_name": user.display_name,
            },
        )

        logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
        return customer.id

    async def create_checkout_session(
        self,
        db: AsyncSession,
        user: User,
        plan: SubscriptionPlan,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe checkout session for subscription.

        Returns:
            Dict with session_id and checkout_url
        """
        if not self.is_configured():
            raise ValueError("Stripe is not configured")

        # Map plan to price ID
        price_id = self._get_price_id(plan)
        if not price_id:
            raise ValueError(f"No Stripe price configured for plan: {plan}")

        customer_id = await self.get_or_create_customer(db, user)

        # Default URLs
        success_url = (
            success_url or f"{self.frontend_url}/settings/subscription?success=true"
        )
        cancel_url = cancel_url or f"{self.frontend_url}/pricing?cancelled=true"

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": str(user.id),
                "plan": plan.value,
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "plan": plan.value,
                },
            },
            allow_promotion_codes=True,
        )

        logger.info(
            f"Created checkout session {session.id} for user {user.id}, plan {plan}"
        )

        return {
            "session_id": session.id,
            "checkout_url": session.url,
        }

    async def create_portal_session(
        self,
        db: AsyncSession,
        user: User,
        return_url: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe customer portal session for managing subscription.

        Returns:
            Dict with portal_url
        """
        if not self.is_configured():
            raise ValueError("Stripe is not configured")

        customer_id = await self.get_or_create_customer(db, user)
        return_url = return_url or f"{self.frontend_url}/settings/subscription"

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return {"portal_url": session.url}

    async def handle_webhook(
        self,
        db: AsyncSession,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any]:
        """Process incoming Stripe webhook.

        Returns:
            Dict with event_type and any relevant data
        """
        if not self.webhook_secret:
            raise ValueError("Stripe webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Invalid Stripe webhook signature: {e}")
            raise ValueError("Invalid signature")

        event_type = event["type"]
        data = event["data"]["object"]

        logger.info(f"Processing Stripe webhook: {event_type}")

        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            result = await handler(db, data)
            return {"event_type": event_type, "processed": True, **result}

        return {"event_type": event_type, "processed": False}

    async def _handle_checkout_completed(
        self,
        db: AsyncSession,
        session: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle successful checkout session completion."""
        user_id = session.get("metadata", {}).get("user_id")
        if not user_id:
            logger.warning("Checkout session missing user_id metadata")
            return {"error": "missing_user_id"}

        subscription_id = session.get("subscription")
        customer_id = session.get("customer")
        plan = session.get("metadata", {}).get("plan", "pro_monthly")

        logger.info(
            f"Checkout completed for user {user_id}, subscription {subscription_id}"
        )

        return {
            "user_id": user_id,
            "subscription_id": subscription_id,
            "customer_id": customer_id,
            "plan": plan,
        }

    async def _handle_subscription_created(
        self,
        db: AsyncSession,
        subscription_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle new subscription creation."""
        return await self._sync_subscription(db, subscription_data)

    async def _handle_subscription_updated(
        self,
        db: AsyncSession,
        subscription_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle subscription update (plan change, renewal, etc.)."""
        return await self._sync_subscription(db, subscription_data)

    async def _handle_subscription_deleted(
        self,
        db: AsyncSession,
        subscription_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle subscription cancellation."""
        user_id = subscription_data.get("metadata", {}).get("user_id")
        if not user_id:
            return {"error": "missing_user_id"}

        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == UUID(user_id))
            .order_by(Subscription.current_period_start.desc())
        )
        subscription = result.scalars().first()

        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.plan_code = SubscriptionPlan.FREE
            subscription.ai_quota_remaining = 0
            subscription.last_synced_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info(f"Cancelled subscription for user {user_id}")

        return {"user_id": user_id, "status": "cancelled"}

    async def _handle_invoice_paid(
        self,
        db: AsyncSession,
        invoice: dict[str, Any],
    ) -> dict[str, Any]:
        """Record successful payment."""
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        amount_paid = invoice.get("amount_paid", 0)
        currency = invoice.get("currency", "usd").upper()

        # Get user from subscription metadata
        if subscription_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                user_id = stripe_sub.metadata.get("user_id")

                if user_id:
                    # Record transaction
                    transaction = BillingTransaction(
                        user_id=UUID(user_id),
                        provider=BillingProvider.STRIPE,
                        provider_ref=f"{customer_id}:{invoice.get('id')}",
                        amount_cents=amount_paid,
                        currency=currency,
                        tx_type=BillingTransactionType.SUBSCRIPTION,
                        status=BillingTransactionStatus.SUCCEEDED,
                    )
                    db.add(transaction)
                    await db.commit()

                    logger.info(
                        f"Recorded payment of {amount_paid} {currency} for user {user_id}"
                    )
                    return {
                        "user_id": user_id,
                        "amount": amount_paid,
                        "currency": currency,
                    }
            except Exception as e:
                logger.error(f"Failed to record payment: {e}")

        return {"subscription_id": subscription_id}

    async def _handle_invoice_failed(
        self,
        db: AsyncSession,
        invoice: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle failed payment - mark subscription as past due."""
        subscription_id = invoice.get("subscription")

        if subscription_id:
            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                user_id = stripe_sub.metadata.get("user_id")

                if user_id:
                    result = await db.execute(
                        select(Subscription)
                        .where(Subscription.user_id == UUID(user_id))
                        .order_by(Subscription.current_period_start.desc())
                    )
                    subscription = result.scalars().first()

                    if subscription:
                        subscription.status = SubscriptionStatus.PAST_DUE
                        subscription.last_synced_at = datetime.now(timezone.utc)
                        await db.commit()

                        logger.warning(f"Payment failed for user {user_id}")
                        return {"user_id": user_id, "status": "past_due"}
            except Exception as e:
                logger.error(f"Failed to update subscription status: {e}")

        return {"subscription_id": subscription_id}

    async def _sync_subscription(
        self,
        db: AsyncSession,
        subscription_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Sync subscription data from Stripe to database."""
        user_id = subscription_data.get("metadata", {}).get("user_id")
        if not user_id:
            return {"error": "missing_user_id"}

        # Map Stripe status to our status
        stripe_status = subscription_data.get("status")
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELLED,
            "unpaid": SubscriptionStatus.PAST_DUE,
        }
        status = status_map.get(stripe_status, SubscriptionStatus.ACTIVE)

        # Get plan from price
        items = subscription_data.get("items", {}).get("data", [])
        price_id = items[0].get("price", {}).get("id") if items else None
        plan = self._get_plan_from_price(price_id)

        # Period dates
        period_start = datetime.fromtimestamp(
            subscription_data.get("current_period_start", 0),
            tz=timezone.utc,
        )
        period_end = datetime.fromtimestamp(
            subscription_data.get("current_period_end", 0),
            tz=timezone.utc,
        )

        # Find or create subscription
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == UUID(user_id))
            .order_by(Subscription.current_period_start.desc())
        )
        subscription = result.scalars().first()

        # Quota based on plan
        quota_map = {
            SubscriptionPlan.FREE: 3,
            SubscriptionPlan.PRO_MONTHLY: 100,
            SubscriptionPlan.PRO_YEARLY: 100,
        }

        if subscription:
            subscription.plan_code = plan
            subscription.status = status
            subscription.current_period_start = period_start
            subscription.current_period_end = period_end
            subscription.ai_quota_remaining = quota_map.get(plan, 3)
            subscription.last_synced_at = datetime.now(timezone.utc)
        else:
            subscription = Subscription(
                user_id=UUID(user_id),
                plan_code=plan,
                status=status,
                current_period_start=period_start,
                current_period_end=period_end,
                ai_quota_remaining=quota_map.get(plan, 3),
                last_synced_at=datetime.now(timezone.utc),
            )
            db.add(subscription)

        await db.commit()

        logger.info(
            f"Synced subscription for user {user_id}: plan={plan}, status={status}"
        )
        return {"user_id": user_id, "plan": plan.value, "status": status.value}

    def _get_price_id(self, plan: SubscriptionPlan) -> str | None:
        """Get Stripe price ID for a plan."""
        return {
            SubscriptionPlan.PRO_MONTHLY: self.pro_monthly_price_id,
            SubscriptionPlan.PRO_YEARLY: self.pro_yearly_price_id,
        }.get(plan)

    def _get_plan_from_price(self, price_id: str | None) -> SubscriptionPlan:
        """Get plan from Stripe price ID."""
        if price_id == self.pro_monthly_price_id:
            return SubscriptionPlan.PRO_MONTHLY
        elif price_id == self.pro_yearly_price_id:
            return SubscriptionPlan.PRO_YEARLY
        return SubscriptionPlan.FREE


# Singleton instance
_stripe_service: StripeService | None = None


def get_stripe_service() -> StripeService:
    """Get or create StripeService singleton."""
    global _stripe_service
    if _stripe_service is None:
        _stripe_service = StripeService()
    return _stripe_service
