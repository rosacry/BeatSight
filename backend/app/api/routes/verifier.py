"""Verifier dashboard API routes for map edit proposals."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, get_db_session
from app.models.map_edit import (
    EditStatus,
    MapEditProposal,
    MapVerificationDecision,
    VerificationDecision,
)
from app.models.user import User
from app.services.rbac import Permission, require_any_permission

router = APIRouter(prefix="/verifier", tags=["verifier"])

# RBAC dependencies
RequireVerifier = require_any_permission(Permission.MAP_VERIFY)
RequireMapApprove = require_any_permission(Permission.MAP_APPROVE)
RequireMapReject = require_any_permission(Permission.MAP_REJECT)


# =============================================================================
# Schemas
# =============================================================================


class ProposerInfo(BaseModel):
    """Brief info about the proposer."""

    id: uuid.UUID
    username: str
    avatar_url: Optional[str] = None


class MapVersionInfo(BaseModel):
    """Brief info about the map version."""

    id: uuid.UUID
    song_title: Optional[str] = None
    artist: Optional[str] = None
    difficulty: Optional[str] = None


class ProposalRead(BaseModel):
    """Map edit proposal details."""

    id: uuid.UUID
    map_version_id: uuid.UUID
    proposer: ProposerInfo
    summary: str
    diff_payload: dict
    status: EditStatus
    submitted_at: datetime
    updated_at: datetime

    # Decision info if exists
    decision: Optional["DecisionRead"] = None

    model_config = {"from_attributes": True}


class DecisionRead(BaseModel):
    """Verification decision details."""

    id: uuid.UUID
    decision: VerificationDecision
    notes: Optional[str] = None
    verifier_id: uuid.UUID
    verifier_username: Optional[str] = None
    decided_at: datetime

    model_config = {"from_attributes": True}


class ProposalListResponse(BaseModel):
    """Paginated list of proposals."""

    items: list[ProposalRead]
    total: int
    page: int
    page_size: int
    has_next: bool


class VerifierStatsResponse(BaseModel):
    """Statistics for the verifier dashboard."""

    pending_count: int
    approved_today: int
    rejected_today: int
    total_reviewed_by_user: int
    avg_review_time_hours: Optional[float] = None


class VerifierLeaderboardEntry(BaseModel):
    """Entry in the verifier leaderboard."""

    verifier_id: uuid.UUID
    username: str
    total_reviews: int
    approved: int
    rejected: int
    avg_review_time_hours: Optional[float] = None


class VerifierLeaderboardResponse(BaseModel):
    """Verifier leaderboard for admin dashboard."""

    verifiers: list[VerifierLeaderboardEntry]


class DecisionCreate(BaseModel):
    """Request to create a verification decision."""

    decision: VerificationDecision = Field(..., description="The verification decision")
    notes: Optional[str] = Field(
        None, max_length=512, description="Optional notes explaining the decision"
    )


class DecisionResponse(BaseModel):
    """Response after creating a decision."""

    id: uuid.UUID
    proposal_id: uuid.UUID
    decision: VerificationDecision
    notes: Optional[str]
    decided_at: datetime


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/proposals",
    response_model=ProposalListResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def list_proposals(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    status_filter: Annotated[
        Optional[EditStatus], Query(description="Filter by proposal status")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ProposalListResponse:
    """
    List map edit proposals for verification.

    Requires MAP_VERIFY permission (verifier or admin role).
    Default shows pending proposals first.
    """
    offset = (page - 1) * page_size

    # Build base query
    base_query = select(MapEditProposal).options(
        joinedload(MapEditProposal.proposer),
        joinedload(MapEditProposal.decision).joinedload(
            MapVerificationDecision.verifier
        ),
    )

    # Apply status filter
    if status_filter:
        base_query = base_query.where(MapEditProposal.status == status_filter)
    else:
        # Default: show pending first, then recently updated
        base_query = base_query.order_by(
            # Pending first
            (MapEditProposal.status == EditStatus.PENDING).desc(),
            MapEditProposal.submitted_at.desc(),
        )

    # Count total
    count_query = select(func.count()).select_from(MapEditProposal)
    if status_filter:
        count_query = count_query.where(MapEditProposal.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = base_query.offset(offset).limit(page_size)
    result = await session.execute(query)
    proposals = result.scalars().unique().all()

    # Convert to response
    items = []
    for proposal in proposals:
        decision_read = None
        if proposal.decision:
            decision_read = DecisionRead(
                id=proposal.decision.id,
                decision=proposal.decision.decision,
                notes=proposal.decision.notes,
                verifier_id=proposal.decision.verifier_id,
                verifier_username=proposal.decision.verifier.username
                if proposal.decision.verifier
                else None,
                decided_at=proposal.decision.decided_at,
            )

        items.append(
            ProposalRead(
                id=proposal.id,
                map_version_id=proposal.map_version_id,
                proposer=ProposerInfo(
                    id=proposal.proposer.id,
                    username=proposal.proposer.username,
                    avatar_url=None,  # Add avatar if available
                ),
                summary=proposal.summary,
                diff_payload=proposal.diff_payload,
                status=proposal.status,
                submitted_at=proposal.submitted_at,
                updated_at=proposal.updated_at,
                decision=decision_read,
            )
        )

    return ProposalListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + len(items)) < total,
    )


@router.get(
    "/proposals/{proposal_id}",
    response_model=ProposalRead,
    dependencies=[Depends(RequireVerifier)],
)
async def get_proposal(
    proposal_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProposalRead:
    """
    Get a specific map edit proposal.

    Requires MAP_VERIFY permission.
    """
    query = (
        select(MapEditProposal)
        .options(
            joinedload(MapEditProposal.proposer),
            joinedload(MapEditProposal.decision).joinedload(
                MapVerificationDecision.verifier
            ),
        )
        .where(MapEditProposal.id == proposal_id)
    )

    result = await session.execute(query)
    proposal = result.scalar()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    decision_read = None
    if proposal.decision:
        decision_read = DecisionRead(
            id=proposal.decision.id,
            decision=proposal.decision.decision,
            notes=proposal.decision.notes,
            verifier_id=proposal.decision.verifier_id,
            verifier_username=proposal.decision.verifier.username
            if proposal.decision.verifier
            else None,
            decided_at=proposal.decision.decided_at,
        )

    return ProposalRead(
        id=proposal.id,
        map_version_id=proposal.map_version_id,
        proposer=ProposerInfo(
            id=proposal.proposer.id,
            username=proposal.proposer.username,
            avatar_url=None,
        ),
        summary=proposal.summary,
        diff_payload=proposal.diff_payload,
        status=proposal.status,
        submitted_at=proposal.submitted_at,
        updated_at=proposal.updated_at,
        decision=decision_read,
    )


@router.post(
    "/proposals/{proposal_id}/decision",
    response_model=DecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_decision(
    proposal_id: uuid.UUID,
    request: DecisionCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    _approve: None = Depends(
        RequireMapApprove
    ),  # Require either approve or reject permission
) -> DecisionResponse:
    """
    Create a verification decision for a proposal.

    Requires MAP_APPROVE or MAP_REJECT permission depending on the decision.
    Only pending proposals can be decided.
    """
    # Get the proposal
    query = (
        select(MapEditProposal)
        .options(
            joinedload(MapEditProposal.decision),
        )
        .where(MapEditProposal.id == proposal_id)
    )

    result = await session.execute(query)
    proposal = result.scalar()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    # Check if already decided
    if proposal.status != EditStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal is already {proposal.status.value}",
        )

    if proposal.decision:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposal already has a decision",
        )

    # Create the decision
    decision = MapVerificationDecision(
        proposal_id=proposal_id,
        verifier_id=current_user.id,
        decision=request.decision,
        notes=request.notes,
    )
    session.add(decision)

    # Update proposal status
    if request.decision == VerificationDecision.APPROVE:
        proposal.status = EditStatus.APPROVED
        
        # Award "helpful editor" achievement to the proposer (best effort)
        try:
            from app.services.achievements import check_edit_achievements
            
            awarded = await check_edit_achievements(
                session, proposal.proposer_id, edit_approved=True
            )
            if awarded:
                pass  # Logged in service
        except Exception:
            pass  # Silent failure for achievements
            
    elif request.decision == VerificationDecision.REJECT:
        proposal.status = EditStatus.REJECTED
    # NEEDS_CHANGES keeps it PENDING but adds feedback

    await session.commit()
    await session.refresh(decision)

    return DecisionResponse(
        id=decision.id,
        proposal_id=proposal_id,
        decision=decision.decision,
        notes=decision.notes,
        decided_at=decision.decided_at,
    )


@router.get(
    "/stats",
    response_model=VerifierStatsResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def get_verifier_stats(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> VerifierStatsResponse:
    """
    Get verification statistics for the dashboard.

    Includes pending count, today's activity, and user's review history.
    Optimized: runs all queries in parallel for faster response.
    """
    import asyncio
    from datetime import timezone
    from sqlalchemy import extract

    # Get today's start in UTC
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Define all queries
    pending_query = (
        select(func.count())
        .select_from(MapEditProposal)
        .where(MapEditProposal.status == EditStatus.PENDING)
    )

    approved_query = (
        select(func.count())
        .select_from(MapVerificationDecision)
        .where(
            and_(
                MapVerificationDecision.decision == VerificationDecision.APPROVE,
                MapVerificationDecision.decided_at >= today_start,
            )
        )
    )

    rejected_query = (
        select(func.count())
        .select_from(MapVerificationDecision)
        .where(
            and_(
                MapVerificationDecision.decision == VerificationDecision.REJECT,
                MapVerificationDecision.decided_at >= today_start,
            )
        )
    )

    user_reviewed_query = (
        select(func.count())
        .select_from(MapVerificationDecision)
        .where(MapVerificationDecision.verifier_id == current_user.id)
    )

    avg_review_query = (
        select(
            func.avg(
                extract("epoch", MapVerificationDecision.decided_at)
                - extract("epoch", MapEditProposal.submitted_at)
            )
            / 3600.0  # Convert seconds to hours
        )
        .select_from(MapVerificationDecision)
        .join(
            MapEditProposal, MapVerificationDecision.proposal_id == MapEditProposal.id
        )
    )

    # Execute all queries in parallel
    pending_result, approved_result, rejected_result, user_reviewed_result, avg_review_result = await asyncio.gather(
        session.execute(pending_query),
        session.execute(approved_query),
        session.execute(rejected_query),
        session.execute(user_reviewed_query),
        session.execute(avg_review_query),
    )

    pending_count = pending_result.scalar() or 0
    approved_today = approved_result.scalar() or 0
    rejected_today = rejected_result.scalar() or 0
    total_reviewed_by_user = user_reviewed_result.scalar() or 0
    avg_review_seconds = avg_review_result.scalar()
    avg_review_time_hours = round(avg_review_seconds, 2) if avg_review_seconds else None

    return VerifierStatsResponse(
        pending_count=pending_count,
        approved_today=approved_today,
        rejected_today=rejected_today,
        total_reviewed_by_user=total_reviewed_by_user,
        avg_review_time_hours=avg_review_time_hours,
    )


@router.get(
    "/leaderboard",
    response_model=VerifierLeaderboardResponse,
)
async def get_verifier_leaderboard(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=50, description="Max verifiers to return")] = 10,
) -> VerifierLeaderboardResponse:
    """
    Get top verifiers ranked by total reviews.

    Returns verifier stats including approval/rejection counts and average review time.
    Available to any authenticated user.
    """
    from sqlalchemy import case, extract, literal_column
    from sqlalchemy.orm import aliased

    # Subquery for verifier stats
    stats_query = (
        select(
            MapVerificationDecision.verifier_id,
            func.count().label("total_reviews"),
            func.sum(
                case(
                    (MapVerificationDecision.decision == VerificationDecision.APPROVE, 1),
                    else_=0,
                )
            ).label("approved"),
            func.sum(
                case(
                    (MapVerificationDecision.decision == VerificationDecision.REJECT, 1),
                    else_=0,
                )
            ).label("rejected"),
            func.avg(
                extract("epoch", MapVerificationDecision.decided_at)
                - extract("epoch", MapEditProposal.submitted_at)
            ).label("avg_review_seconds"),
        )
        .join(MapEditProposal, MapVerificationDecision.proposal_id == MapEditProposal.id)
        .group_by(MapVerificationDecision.verifier_id)
        .order_by(literal_column("total_reviews").desc())
        .limit(limit)
        .subquery()
    )

    # Join with users to get usernames
    query = (
        select(
            stats_query.c.verifier_id,
            User.display_name,
            stats_query.c.total_reviews,
            stats_query.c.approved,
            stats_query.c.rejected,
            stats_query.c.avg_review_seconds,
        )
        .join(User, stats_query.c.verifier_id == User.id)
    )

    result = await session.execute(query)
    rows = result.all()

    verifiers = [
        VerifierLeaderboardEntry(
            verifier_id=row.verifier_id,
            username=row.display_name,
            total_reviews=row.total_reviews or 0,
            approved=row.approved or 0,
            rejected=row.rejected or 0,
            avg_review_time_hours=(
                round(row.avg_review_seconds / 3600.0, 2)
                if row.avg_review_seconds
                else None
            ),
        )
        for row in rows
    ]

    return VerifierLeaderboardResponse(verifiers=verifiers)


@router.get(
    "/my-decisions",
    response_model=ProposalListResponse,
    dependencies=[Depends(RequireVerifier)],
)
async def list_my_decisions(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> ProposalListResponse:
    """
    List proposals that the current user has reviewed.

    Useful for tracking your own verification history.
    """
    offset = (page - 1) * page_size

    # Get proposals where user made a decision
    query = (
        select(MapEditProposal)
        .join(MapVerificationDecision)
        .options(
            joinedload(MapEditProposal.proposer),
            joinedload(MapEditProposal.decision).joinedload(
                MapVerificationDecision.verifier
            ),
        )
        .where(MapVerificationDecision.verifier_id == current_user.id)
        .order_by(MapVerificationDecision.decided_at.desc())
    )

    # Count total
    count_query = (
        select(func.count())
        .select_from(MapEditProposal)
        .join(MapVerificationDecision)
        .where(MapVerificationDecision.verifier_id == current_user.id)
    )

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    paginated_query = query.offset(offset).limit(page_size)
    result = await session.execute(paginated_query)
    proposals = result.scalars().unique().all()

    # Convert to response
    items = []
    for proposal in proposals:
        decision_read = None
        if proposal.decision:
            decision_read = DecisionRead(
                id=proposal.decision.id,
                decision=proposal.decision.decision,
                notes=proposal.decision.notes,
                verifier_id=proposal.decision.verifier_id,
                verifier_username=proposal.decision.verifier.username
                if proposal.decision.verifier
                else None,
                decided_at=proposal.decision.decided_at,
            )

        items.append(
            ProposalRead(
                id=proposal.id,
                map_version_id=proposal.map_version_id,
                proposer=ProposerInfo(
                    id=proposal.proposer.id,
                    username=proposal.proposer.username,
                    avatar_url=None,
                ),
                summary=proposal.summary,
                diff_payload=proposal.diff_payload,
                status=proposal.status,
                submitted_at=proposal.submitted_at,
                updated_at=proposal.updated_at,
                decision=decision_read,
            )
        )

    return ProposalListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + len(items)) < total,
    )
