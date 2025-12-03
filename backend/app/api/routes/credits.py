"""Credit API routes for managing user credits and purchases.

Endpoints:
- GET /credits/balance - Get current credit balance
- GET /credits/packs - List available credit packs
- POST /credits/purchase - Create checkout session for credit purchase
- GET /credits/history - Get transaction history
- PUT /credits/auto-topup - Configure auto top-up settings
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.models.credits import CreditPackType
from app.models.user import User
from app.services.credits import (
    CreditService,
    get_all_packs,
    get_pack_config,
)
from app.services.rbac import RequireAdmin
from app.services.stripe_service import get_stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credits", tags=["Credits"])


# =============================================================================
# Schemas
# =============================================================================


class CreditBalanceResponse(BaseModel):
    """Current credit balance."""

    purchased_credits: int = Field(..., description="Purchased credits (never expire)")
    bonus_credits: int = Field(..., description="Bonus/promotional credits")
    total_credits: int = Field(..., description="Total available credits")
    auto_topup_enabled: bool = Field(..., description="Whether auto top-up is enabled")
    auto_topup_pack: str | None = Field(None, description="Pack to buy on auto top-up")


class CreditPackResponse(BaseModel):
    """Credit pack details."""

    id: str = Field(..., description="Pack identifier")
    name: str = Field(..., description="Pack display name")
    description: str = Field(..., description="Pack description")
    credits: int = Field(..., description="Number of credits")
    price_cents: int = Field(..., description="Price in cents")
    price_dollars: float = Field(..., description="Price in dollars")
    per_credit_cents: float = Field(..., description="Cost per credit in cents")
    savings_percent: int = Field(..., description="Savings vs base rate")


class CreditPurchaseRequest(BaseModel):
    """Request to purchase credits."""

    pack_id: str = Field(..., description="Credit pack ID to purchase")
    success_url: str | None = Field(None, description="Custom success redirect URL")
    cancel_url: str | None = Field(None, description="Custom cancel redirect URL")


class CreditPurchaseResponse(BaseModel):
    """Credit purchase checkout response."""

    checkout_url: str = Field(..., description="URL to Stripe checkout")
    session_id: str = Field(..., description="Stripe checkout session ID")


class AutoTopupRequest(BaseModel):
    """Request to configure auto top-up."""

    enabled: bool = Field(..., description="Whether to enable auto top-up")
    pack_id: str | None = Field(None, description="Pack to buy on top-up (default: value)")
    threshold: int = Field(0, ge=0, le=10, description="Trigger when balance <= this")


class CreditTransactionResponse(BaseModel):
    """Credit transaction record."""

    id: str
    transaction_type: str
    amount: int
    balance_after: int
    description: str | None
    created_at: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/packs", response_model=list[CreditPackResponse])
async def list_credit_packs():
    """List available credit packs.

    No authentication required - public endpoint for pricing display.
    """
    return get_all_packs()


@router.get("/balance", response_model=CreditBalanceResponse)
async def get_credit_balance(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get current user's credit balance.

    Returns purchased and bonus credits, plus auto top-up settings.
    """
    service = CreditService(db)
    status = await service.get_status(current_user.id)

    return CreditBalanceResponse(
        purchased_credits=status.purchased_credits,
        bonus_credits=status.bonus_credits,
        total_credits=status.total_credits,
        auto_topup_enabled=status.auto_topup_enabled,
        auto_topup_pack=status.auto_topup_pack.value if status.auto_topup_pack else None,
    )


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_credits(
    request: CreditPurchaseRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a Stripe checkout session for credit purchase.

    Returns a checkout URL to redirect the user to.
    After successful payment, credits are automatically added via webhook.
    """
    # Validate pack ID
    try:
        pack_type = CreditPackType(request.pack_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pack ID: {request.pack_id}. Valid options: {[p.value for p in CreditPackType]}",
        )

    stripe_service = get_stripe_service()
    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment system is not configured",
        )

    pack_config = get_pack_config(pack_type)

    # Create purchase record
    credit_service = CreditService(db)
    purchase = await credit_service.create_purchase(
        user_id=current_user.id,
        pack_type=pack_type,
    )

    try:
        # Create Stripe checkout session for one-time payment
        result = await stripe_service.create_credit_checkout_session(
            db=db,
            user=current_user,
            purchase_id=purchase.id,
            pack_config=pack_config,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )

        # Update purchase with Stripe session ID
        purchase.stripe_checkout_session_id = result["session_id"]
        await db.commit()

        return CreditPurchaseResponse(
            checkout_url=result["checkout_url"],
            session_id=result["session_id"],
        )

    except Exception as e:
        logger.error(f"Failed to create credit checkout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.get("/history", response_model=list[CreditTransactionResponse])
async def get_credit_history(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
):
    """Get credit transaction history.

    Returns recent credit additions and consumptions.
    """
    service = CreditService(db)
    transactions = await service.get_transaction_history(
        user_id=current_user.id,
        limit=min(limit, 100),
        offset=offset,
    )

    return [
        CreditTransactionResponse(
            id=str(tx.id),
            transaction_type=tx.transaction_type.value,
            amount=tx.amount,
            balance_after=tx.balance_after,
            description=tx.description,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]


@router.put("/auto-topup", response_model=CreditBalanceResponse)
async def configure_auto_topup(
    request: AutoTopupRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Configure auto top-up settings.

    When enabled, credits are automatically purchased when balance
    falls to or below the threshold.
    """
    pack_type = None
    if request.enabled and request.pack_id:
        try:
            pack_type = CreditPackType(request.pack_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid pack ID: {request.pack_id}",
            )

    service = CreditService(db)
    balance = await service.configure_auto_topup(
        user_id=current_user.id,
        enabled=request.enabled,
        pack_type=pack_type,
        threshold=request.threshold,
    )
    await db.commit()

    return CreditBalanceResponse(
        purchased_credits=balance.purchased_credits,
        bonus_credits=balance.bonus_credits,
        total_credits=balance.total_credits,
        auto_topup_enabled=balance.auto_topup_enabled,
        auto_topup_pack=balance.auto_topup_pack.value if balance.auto_topup_pack else None,
    )


@router.post("/grant-bonus", include_in_schema=False)
async def grant_bonus_credits(
    user_id: str,
    amount: int,
    description: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    _admin_check: Annotated[None, RequireAdmin],
):
    """Grant bonus credits to a user (admin only).

    This endpoint is for internal/admin use to award promotional credits.
    Requires admin role.
    """
    from uuid import UUID

    service = CreditService(db)
    balance = await service.grant_bonus_credits(
        user_id=UUID(user_id),
        amount=amount,
        description=description,
    )
    await db.commit()

    return {"success": True, "new_balance": balance.total_credits}
