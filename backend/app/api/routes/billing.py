"""Stripe payment routes for subscription management.

Endpoints:
- GET /billing/pricing - Get pricing table (public)
- POST /billing/checkout - Create checkout session for subscription upgrade
- POST /billing/portal - Create customer portal session
- POST /billing/webhook - Handle Stripe webhooks
- GET /billing/subscription - Get current subscription status
- GET /billing/config - Get Stripe publishable key (public)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.config import get_settings
from app.core.pricing import get_pricing_table, FREE_TIER
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User
from app.services.stripe_service import get_stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


# -------------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""

    plan: SubscriptionPlan = Field(..., description="Subscription plan to purchase")
    success_url: str | None = Field(None, description="Custom success redirect URL")
    cancel_url: str | None = Field(None, description="Custom cancel redirect URL")


class CheckoutResponse(BaseModel):
    """Checkout session response."""

    session_id: str = Field(..., description="Stripe checkout session ID")
    checkout_url: str = Field(..., description="URL to redirect user to")


class PortalResponse(BaseModel):
    """Customer portal session response."""

    portal_url: str = Field(..., description="URL to Stripe customer portal")


class SubscriptionResponse(BaseModel):
    """Current subscription status."""

    plan: SubscriptionPlan = Field(..., description="Current plan")
    status: SubscriptionStatus = Field(..., description="Subscription status")
    ai_quota_remaining: int = Field(..., description="AI jobs remaining this period")
    current_period_end: str | None = Field(None, description="Period end date (ISO)")
    is_active: bool = Field(..., description="Whether subscription is active")


class StripeConfigResponse(BaseModel):
    """Public Stripe configuration."""

    publishable_key: str | None = Field(None, description="Stripe publishable key")
    is_configured: bool = Field(..., description="Whether Stripe is configured")


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get("/pricing")
async def get_pricing() -> dict[str, Any]:
    """Get pricing table for display.

    Returns all subscription tiers with features and pricing.
    No authentication required - public endpoint for pricing page.
    """
    return get_pricing_table()


@router.get("/config", response_model=StripeConfigResponse)
async def get_stripe_config():
    """Get public Stripe configuration.

    Returns the publishable key for client-side Stripe initialization.
    No authentication required.
    """
    settings = get_settings()
    stripe_service = get_stripe_service()

    return StripeConfigResponse(
        publishable_key=settings.stripe_publishable_key,
        is_configured=stripe_service.is_configured(),
    )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current user's subscription status.

    Returns the active subscription or defaults for free tier.
    """
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.current_period_start.desc())
    )
    subscription = result.scalars().first()

    if subscription:
        return SubscriptionResponse(
            plan=subscription.plan_code,
            status=subscription.status,
            ai_quota_remaining=subscription.ai_quota_remaining,
            current_period_end=subscription.current_period_end.isoformat()
            if subscription.current_period_end
            else None,
            is_active=subscription.status == SubscriptionStatus.ACTIVE,
        )

    # No subscription = free tier
    return SubscriptionResponse(
        plan=SubscriptionPlan.FREE,
        status=SubscriptionStatus.ACTIVE,
        ai_quota_remaining=FREE_TIER.monthly_quota,  # 5 songs/month
        current_period_end=None,
        is_active=True,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    request: CheckoutRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a Stripe checkout session for subscription upgrade.

    Redirects the user to Stripe's hosted checkout page.
    Only pro plans can be purchased (free is default).
    """
    stripe_service = get_stripe_service()

    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment system is not configured",
        )

    if request.plan == SubscriptionPlan.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot purchase free plan. Use portal to cancel subscription.",
        )

    try:
        result = await stripe_service.create_checkout_session(
            db=db,
            user=current_user,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Checkout session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post("/portal", response_model=PortalResponse)
async def create_portal_session(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a Stripe customer portal session.

    Allows users to manage their subscription, update payment method,
    view invoices, and cancel subscription.
    """
    stripe_service = get_stripe_service()

    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment system is not configured",
        )

    try:
        result = await stripe_service.create_portal_session(
            db=db,
            user=current_user,
        )
        return PortalResponse(**result)
    except Exception as e:
        logger.error(f"Portal session creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
):
    """Handle incoming Stripe webhooks.

    Processes events like subscription creation, updates, cancellation,
    and payment success/failure.

    This endpoint should be configured in the Stripe dashboard to receive
    the following events:
    - checkout.session.completed
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    stripe_service = get_stripe_service()

    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook handler is not configured",
        )

    try:
        payload = await request.body()
        result = await stripe_service.handle_webhook(
            db=db,
            payload=payload,
            signature=stripe_signature,
        )
        return {"received": True, **result}
    except ValueError as e:
        logger.warning(f"Webhook validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )
