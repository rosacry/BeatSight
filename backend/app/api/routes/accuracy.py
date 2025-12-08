"""Map Accuracy Verification API routes.

This module provides endpoints for the multi-verifier beatmap accuracy system:
- Vote on beatmap accuracy
- View consensus status  
- Get maps needing verification
- View verification statistics

The system requires 3 verifiers to reach consensus, with verified users
(email + phone) receiving a karma bonus to help them participate.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.map_accuracy import (
    AccuracyVoteType,
    MapAccuracyStatus,
    REQUIRED_VERIFIERS_FOR_ACCURACY,
    VERIFIED_USER_KARMA_BONUS,
)
from app.models.user import User
from app.services.map_accuracy import (
    AlreadyVotedError,
    MapAccuracyError,
    MapAccuracyService,
    MapVersionNotFoundError,
    NotEligibleError,
)

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


# =============================================================================
# Schemas
# =============================================================================


class AccuracyVoteRequest(BaseModel):
    """Request to cast an accuracy vote."""

    vote: AccuracyVoteType = Field(..., description="Your accuracy assessment")
    confidence_level: int = Field(
        default=3,
        ge=1,
        le=5,
        description="How confident are you? 1=uncertain, 5=very confident",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional explanation for your vote",
    )
    timestamp_markers: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="JSON array of timestamps where issues were found",
    )


class AccuracyVoteResponse(BaseModel):
    """Response for an accuracy vote."""

    id: uuid.UUID
    map_version_id: uuid.UUID
    verifier_id: uuid.UUID
    vote: AccuracyVoteType
    confidence_level: int
    notes: Optional[str]
    voted_at: datetime

    model_config = {"from_attributes": True}


class ConsensusResponse(BaseModel):
    """Response showing consensus status for a map version."""

    map_version_id: uuid.UUID
    status: MapAccuracyStatus
    total_votes: int
    accurate_votes: int
    inaccurate_votes: int
    needs_work_votes: int
    abstain_votes: int
    average_confidence: Optional[float]
    votes_needed: int  # How many more votes needed for consensus
    consensus_reached_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EligibilityResponse(BaseModel):
    """Response indicating if user can vote on accuracy."""

    eligible: bool
    reason: str
    email_verified: bool
    phone_verified: bool
    karma_score: int
    min_karma_required: int


class VerificationBonusResponse(BaseModel):
    """Response for verification bonus status."""

    eligible: bool
    awarded: bool
    bonus_amount: int
    email_verified: bool
    phone_verified: bool
    awarded_at: Optional[datetime]


class MapNeedingVerificationResponse(BaseModel):
    """Map version that needs more verification votes."""

    map_version_id: uuid.UUID
    current_votes: int
    votes_needed: int


class MapsNeedingVerificationResponse(BaseModel):
    """List of maps needing verification."""

    items: list[MapNeedingVerificationResponse]
    total_pending: int


class VerificationStatsResponse(BaseModel):
    """User's verification statistics."""

    total_votes: int
    consensus_matches: int
    accuracy_rate: float  # Percentage of votes matching consensus
    by_vote_type: dict[str, int]


class SystemStatsResponse(BaseModel):
    """System-wide verification statistics."""

    verified_maps_count: int
    required_verifiers: int
    karma_bonus_amount: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/eligibility", response_model=EligibilityResponse)
async def check_eligibility(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EligibilityResponse:
    """
    Check if the current user is eligible to vote on beatmap accuracy.
    
    Requirements to vote:
    - Verified email address
    - Verified phone number
    - At least 100 karma (fixer threshold)
    
    Users with both email and phone verified receive a 200 karma bonus
    to help them reach the 100 karma threshold.
    """
    service = MapAccuracyService(session)
    eligible, reason = await service.is_eligible_to_vote(current_user.id)
    
    return EligibilityResponse(
        eligible=eligible,
        reason=reason if not eligible else "You are eligible to vote",
        email_verified=current_user.email_verified,
        phone_verified=current_user.phone_verified,
        karma_score=current_user.karma_score,
        min_karma_required=100,
    )


@router.post("/bonus/claim", response_model=VerificationBonusResponse)
async def claim_verification_bonus(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VerificationBonusResponse:
    """
    Claim the one-time karma bonus for verified users.
    
    Users with BOTH verified email AND verified phone receive a 200 karma
    bonus. This helps them reach the 100 karma threshold needed to
    participate in beatmap accuracy verification.
    
    This bonus can only be claimed once per account.
    """
    service = MapAccuracyService(session)
    
    # Check current status
    from app.models.map_accuracy import UserVerificationBonus
    from sqlalchemy import select
    
    result = await session.execute(
        select(UserVerificationBonus).where(
            UserVerificationBonus.user_id == current_user.id
        )
    )
    existing = result.scalar_one_or_none()
    
    eligible = current_user.email_verified and current_user.phone_verified
    already_awarded = existing.bonus_awarded if existing else False
    
    if not eligible:
        return VerificationBonusResponse(
            eligible=False,
            awarded=False,
            bonus_amount=VERIFIED_USER_KARMA_BONUS,
            email_verified=current_user.email_verified,
            phone_verified=current_user.phone_verified,
            awarded_at=None,
        )
    
    if already_awarded:
        return VerificationBonusResponse(
            eligible=True,
            awarded=True,
            bonus_amount=VERIFIED_USER_KARMA_BONUS,
            email_verified=current_user.email_verified,
            phone_verified=current_user.phone_verified,
            awarded_at=existing.awarded_at if existing else None,
        )
    
    # Award the bonus
    awarded = await service.check_and_award_verification_bonus(current_user.id)
    
    # Re-fetch to get updated info
    result = await session.execute(
        select(UserVerificationBonus).where(
            UserVerificationBonus.user_id == current_user.id
        )
    )
    bonus_record = result.scalar_one_or_none()
    
    return VerificationBonusResponse(
        eligible=True,
        awarded=awarded or (bonus_record.bonus_awarded if bonus_record else False),
        bonus_amount=VERIFIED_USER_KARMA_BONUS,
        email_verified=current_user.email_verified,
        phone_verified=current_user.phone_verified,
        awarded_at=bonus_record.awarded_at if bonus_record else None,
    )


@router.post(
    "/maps/{map_version_id}/vote",
    response_model=AccuracyVoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cast_accuracy_vote(
    map_version_id: uuid.UUID,
    request: AccuracyVoteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AccuracyVoteResponse:
    """
    Cast your vote on a beatmap's accuracy.
    
    You can vote:
    - **accurate**: The beatmap accurately represents the song
    - **inaccurate**: The beatmap has significant errors
    - **needs_work**: Close but needs improvements
    - **abstain**: Cannot make determination
    
    A beatmap needs 3 verifiers to reach consensus. Your vote earns 5 karma,
    and if your vote matches the final consensus, you earn an additional 10 karma.
    
    Requirements:
    - Verified email and phone
    - At least 100 karma
    """
    service = MapAccuracyService(session)
    
    try:
        vote = await service.cast_accuracy_vote(
            map_version_id=map_version_id,
            verifier_id=current_user.id,
            vote=request.vote,
            confidence_level=request.confidence_level,
            notes=request.notes,
            timestamp_markers=request.timestamp_markers,
        )
    except NotEligibleError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except AlreadyVotedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except MapVersionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    
    return AccuracyVoteResponse(
        id=vote.id,
        map_version_id=vote.map_version_id,
        verifier_id=vote.verifier_id,
        vote=vote.vote,
        confidence_level=vote.confidence_level,
        notes=vote.notes,
        voted_at=vote.voted_at,
    )


@router.put(
    "/maps/{map_version_id}/vote",
    response_model=AccuracyVoteResponse,
)
async def update_accuracy_vote(
    map_version_id: uuid.UUID,
    request: AccuracyVoteRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AccuracyVoteResponse:
    """
    Update your existing vote on a beatmap.
    
    You can change your vote until consensus is reached.
    Once consensus is reached, votes are locked.
    """
    service = MapAccuracyService(session)
    
    try:
        vote = await service.update_accuracy_vote(
            map_version_id=map_version_id,
            verifier_id=current_user.id,
            vote=request.vote,
            confidence_level=request.confidence_level,
            notes=request.notes,
            timestamp_markers=request.timestamp_markers,
        )
    except NotEligibleError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except MapVersionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except MapAccuracyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return AccuracyVoteResponse(
        id=vote.id,
        map_version_id=vote.map_version_id,
        verifier_id=vote.verifier_id,
        vote=vote.vote,
        confidence_level=vote.confidence_level,
        notes=vote.notes,
        voted_at=vote.voted_at,
    )


@router.get(
    "/maps/{map_version_id}/vote",
    response_model=Optional[AccuracyVoteResponse],
)
async def get_my_vote(
    map_version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Optional[AccuracyVoteResponse]:
    """Get your vote on a specific map version, if you've voted."""
    service = MapAccuracyService(session)
    vote = await service.get_user_vote(map_version_id, current_user.id)
    
    if vote is None:
        return None
    
    return AccuracyVoteResponse(
        id=vote.id,
        map_version_id=vote.map_version_id,
        verifier_id=vote.verifier_id,
        vote=vote.vote,
        confidence_level=vote.confidence_level,
        notes=vote.notes,
        voted_at=vote.voted_at,
    )


@router.get(
    "/maps/{map_version_id}/consensus",
    response_model=ConsensusResponse,
)
async def get_consensus(
    map_version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ConsensusResponse:
    """
    Get the consensus status for a map version.
    
    Shows:
    - Current status (pending, verified, disputed, rejected, needs_revision)
    - Vote breakdown
    - How many more votes are needed
    
    This endpoint is public to encourage transparency.
    """
    service = MapAccuracyService(session)
    consensus = await service.get_consensus(map_version_id)
    
    if consensus is None:
        # Create a pending consensus response
        return ConsensusResponse(
            map_version_id=map_version_id,
            status=MapAccuracyStatus.PENDING,
            total_votes=0,
            accurate_votes=0,
            inaccurate_votes=0,
            needs_work_votes=0,
            abstain_votes=0,
            average_confidence=None,
            votes_needed=REQUIRED_VERIFIERS_FOR_ACCURACY,
            consensus_reached_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    
    # Calculate votes needed
    non_abstain = (
        consensus.accurate_votes
        + consensus.inaccurate_votes
        + consensus.needs_work_votes
    )
    votes_needed = max(0, REQUIRED_VERIFIERS_FOR_ACCURACY - non_abstain)
    
    return ConsensusResponse(
        map_version_id=consensus.map_version_id,
        status=consensus.status,
        total_votes=consensus.total_votes,
        accurate_votes=consensus.accurate_votes,
        inaccurate_votes=consensus.inaccurate_votes,
        needs_work_votes=consensus.needs_work_votes,
        abstain_votes=consensus.abstain_votes,
        average_confidence=consensus.average_confidence,
        votes_needed=votes_needed,
        consensus_reached_at=consensus.consensus_reached_at,
        created_at=consensus.created_at,
        updated_at=consensus.updated_at,
    )


@router.get(
    "/maps/{map_version_id}/votes",
    response_model=list[AccuracyVoteResponse],
)
async def get_all_votes(
    map_version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[AccuracyVoteResponse]:
    """
    Get all votes for a map version.
    
    Returns the list of all accuracy votes cast by verifiers.
    This is public to encourage transparency in the verification process.
    """
    service = MapAccuracyService(session)
    votes = await service.get_map_version_votes(map_version_id)
    
    return [
        AccuracyVoteResponse(
            id=v.id,
            map_version_id=v.map_version_id,
            verifier_id=v.verifier_id,
            vote=v.vote,
            confidence_level=v.confidence_level,
            notes=v.notes,
            voted_at=v.voted_at,
        )
        for v in votes
    ]


@router.get(
    "/pending",
    response_model=MapsNeedingVerificationResponse,
)
async def get_maps_needing_verification(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> MapsNeedingVerificationResponse:
    """
    Get maps that need more verification votes.
    
    Returns maps in order of oldest first (to prioritize maps
    that have been waiting longest for verification).
    """
    service = MapAccuracyService(session)
    
    maps = await service.get_maps_needing_verification(limit=limit, offset=offset)
    
    items = [
        MapNeedingVerificationResponse(
            map_version_id=map_version_id,
            current_votes=current_votes,
            votes_needed=max(0, REQUIRED_VERIFIERS_FOR_ACCURACY - current_votes),
        )
        for map_version_id, current_votes in maps
    ]
    
    # Count total pending
    from app.models.map_accuracy import MapAccuracyConsensus
    from sqlalchemy import select, func
    
    count_result = await session.execute(
        select(func.count()).where(
            MapAccuracyConsensus.status == MapAccuracyStatus.PENDING
        )
    )
    total_pending = count_result.scalar() or 0
    
    return MapsNeedingVerificationResponse(
        items=items,
        total_pending=total_pending,
    )


@router.get(
    "/my-stats",
    response_model=VerificationStatsResponse,
)
async def get_my_verification_stats(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VerificationStatsResponse:
    """
    Get your verification statistics.
    
    Shows:
    - Total votes cast
    - How many of your votes matched the final consensus
    - Your accuracy rate (% of votes matching consensus)
    - Breakdown by vote type
    """
    service = MapAccuracyService(session)
    stats = await service.get_user_verification_stats(current_user.id)
    
    accuracy_rate = 0.0
    if stats["total_votes"] > 0:
        accuracy_rate = (stats["consensus_matches"] / stats["total_votes"]) * 100
    
    return VerificationStatsResponse(
        total_votes=stats["total_votes"],
        consensus_matches=stats["consensus_matches"],
        accuracy_rate=round(accuracy_rate, 1),
        by_vote_type=stats["by_vote_type"],
    )


@router.get(
    "/system-stats",
    response_model=SystemStatsResponse,
)
async def get_system_stats(
    session: AsyncSession = Depends(get_db_session),
) -> SystemStatsResponse:
    """
    Get system-wide verification statistics.
    
    Public endpoint showing:
    - Total verified maps count
    - Required number of verifiers for consensus
    - Karma bonus amount for verified users
    """
    service = MapAccuracyService(session)
    verified_count = await service.get_verified_maps_count()
    
    return SystemStatsResponse(
        verified_maps_count=verified_count,
        required_verifiers=REQUIRED_VERIFIERS_FOR_ACCURACY,
        karma_bonus_amount=VERIFIED_USER_KARMA_BONUS,
    )
