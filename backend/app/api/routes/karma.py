"""Karma API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.user import User
from app.services.karma import (
    KarmaError,
    KarmaService,
    RoleCode,
    ROLE_KARMA_THRESHOLDS,
)

router = APIRouter(prefix="/karma", tags=["karma"])


# =============================================================================
# Response Models
# =============================================================================


class KarmaResponse(BaseModel):
    """User's current karma summary."""

    user_id: uuid.UUID
    karma_score: int
    rank: int
    daily_ai_quota: int
    eligible_roles: list[str]
    current_roles: list[str]


class KarmaHistoryItem(BaseModel):
    """Single karma ledger entry."""

    id: uuid.UUID
    delta: int
    reason: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[uuid.UUID]
    recorded_at: datetime


class KarmaHistoryResponse(BaseModel):
    """Paginated karma history."""

    items: list[KarmaHistoryItem]
    total_count: int
    limit: int
    offset: int


class KarmaBreakdownItem(BaseModel):
    """Karma totals for a specific reason."""

    reason: str
    total: int
    count: int


class KarmaStatsResponse(BaseModel):
    """Detailed karma statistics."""

    current_score: int
    rank: int
    breakdown: list[KarmaBreakdownItem]
    eligible_roles: list[str]
    current_roles: list[str]
    daily_ai_quota: int


class LeaderboardEntry(BaseModel):
    """Single leaderboard entry."""

    rank: int
    user_id: uuid.UUID
    display_name: str
    karma_score: int


class LeaderboardResponse(BaseModel):
    """Karma leaderboard."""

    entries: list[LeaderboardEntry]
    limit: int
    offset: int


class RoleThreshold(BaseModel):
    """Role and its karma threshold."""

    role: str
    min_karma: int
    requires_phone: bool = False


class RolesInfoResponse(BaseModel):
    """Information about available roles."""

    roles: list[RoleThreshold]


class QuotaResponse(BaseModel):
    """AI generation quota information."""

    daily_quota: int
    karma_score: int
    next_tier_karma: Optional[int]
    next_tier_quota: Optional[int]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/me", response_model=KarmaResponse)
async def get_my_karma(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> KarmaResponse:
    """Get the current user's karma summary."""
    service = KarmaService(session)
    stats = await service.get_karma_stats(current_user.id)

    return KarmaResponse(
        user_id=current_user.id,
        karma_score=stats["current_score"],
        rank=stats["rank"],
        daily_ai_quota=stats["daily_ai_quota"],
        eligible_roles=stats["eligible_roles"],
        current_roles=stats["current_roles"],
    )


@router.get("/me/stats", response_model=KarmaStatsResponse)
async def get_my_karma_stats(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> KarmaStatsResponse:
    """Get detailed karma statistics for the current user."""
    service = KarmaService(session)
    stats = await service.get_karma_stats(current_user.id)

    breakdown = [
        KarmaBreakdownItem(reason=reason, total=data["total"], count=data["count"])
        for reason, data in stats["breakdown"].items()
    ]

    return KarmaStatsResponse(
        current_score=stats["current_score"],
        rank=stats["rank"],
        breakdown=breakdown,
        eligible_roles=stats["eligible_roles"],
        current_roles=stats["current_roles"],
        daily_ai_quota=stats["daily_ai_quota"],
    )


@router.get("/me/history", response_model=KarmaHistoryResponse)
async def get_my_karma_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> KarmaHistoryResponse:
    """Get the current user's karma history."""
    service = KarmaService(session)
    entries = await service.get_karma_history(current_user.id, limit=limit, offset=offset)
    total_count = await service.get_karma_history_count(current_user.id)

    items = [
        KarmaHistoryItem(
            id=entry.id,
            delta=entry.delta,
            reason=entry.reason_code.value,
            related_entity_type=entry.related_entity_type,
            related_entity_id=entry.related_entity_id,
            recorded_at=entry.recorded_at,
        )
        for entry in entries
    ]

    return KarmaHistoryResponse(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


@router.get("/me/quota", response_model=QuotaResponse)
async def get_my_quota(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotaResponse:
    """Get the current user's AI generation quota."""
    service = KarmaService(session)
    karma = await service.get_user_karma(current_user.id)
    quota = await service.get_daily_ai_quota(current_user.id)

    # Find next tier
    from app.services.karma import AI_GENERATION_QUOTAS

    next_tier_karma = None
    next_tier_quota = None

    for threshold, allowed in sorted(AI_GENERATION_QUOTAS.items()):
        if threshold > karma:
            next_tier_karma = threshold
            next_tier_quota = allowed
            break

    return QuotaResponse(
        daily_quota=quota,
        karma_score=karma,
        next_tier_karma=next_tier_karma,
        next_tier_quota=next_tier_quota,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> LeaderboardResponse:
    """
    Get the karma leaderboard.

    This endpoint does not require authentication.
    """
    service = KarmaService(session)
    entries = await service.get_karma_leaderboard(limit=limit, offset=offset)

    leaderboard = [
        LeaderboardEntry(
            rank=offset + i + 1,
            user_id=user_id,
            display_name=display_name,
            karma_score=karma_score,
        )
        for i, (user_id, display_name, karma_score) in enumerate(entries)
    ]

    return LeaderboardResponse(
        entries=leaderboard,
        limit=limit,
        offset=offset,
    )


@router.get("/roles", response_model=RolesInfoResponse)
async def get_roles_info() -> RolesInfoResponse:
    """
    Get information about available roles and their karma requirements.

    This endpoint does not require authentication.
    """
    roles = [
        RoleThreshold(role=RoleCode.FIXER.value, min_karma=ROLE_KARMA_THRESHOLDS[RoleCode.FIXER]),
        RoleThreshold(role=RoleCode.VERIFIER.value, min_karma=ROLE_KARMA_THRESHOLDS[RoleCode.VERIFIER], requires_phone=True),
        RoleThreshold(role=RoleCode.CURATOR.value, min_karma=ROLE_KARMA_THRESHOLDS[RoleCode.CURATOR], requires_phone=True),
        RoleThreshold(role=RoleCode.ADMIN.value, min_karma=ROLE_KARMA_THRESHOLDS[RoleCode.ADMIN], requires_phone=True),
    ]

    return RolesInfoResponse(roles=roles)


@router.post("/me/roles/{role_code}", status_code=status.HTTP_201_CREATED)
async def claim_role(
    role_code: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Claim an eligible role.

    User must meet the karma threshold and any verification requirements.
    """
    service = KarmaService(session)

    # Validate role code
    try:
        RoleCode(role_code)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role code: {role_code}",
        )

    # Attempt to assign
    success = await service.assign_role(current_user.id, role_code)

    if not success:
        # Determine why
        eligible = await service.get_eligible_roles(current_user.id)
        current = await service.get_user_roles(current_user.id)

        if role_code in current:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have this role",
            )

        if role_code not in eligible:
            karma = await service.get_user_karma(current_user.id)
            required = ROLE_KARMA_THRESHOLDS.get(RoleCode(role_code), 0)

            if karma < required:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient karma: requires {required}, you have {karma}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Phone verification required for this role",
                )

    return {"message": f"Role '{role_code}' assigned successfully"}


@router.get("/users/{user_id}", response_model=KarmaResponse)
async def get_user_karma(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> KarmaResponse:
    """
    Get karma summary for a specific user (public profile).

    This endpoint does not require authentication.
    """
    service = KarmaService(session)

    try:
        # Check if user exists by attempting to get karma
        await service.get_user_karma(user_id)
    except KarmaError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    stats = await service.get_karma_stats(user_id)

    return KarmaResponse(
        user_id=user_id,
        karma_score=stats["current_score"],
        rank=stats["rank"],
        daily_ai_quota=stats["daily_ai_quota"],
        eligible_roles=stats["eligible_roles"],
        current_roles=stats["current_roles"],
    )
