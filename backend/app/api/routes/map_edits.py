"""Map edit proposal API routes for submitting beatmap corrections."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, get_db_session, get_rbac_service
from app.models.map_edit import EditStatus, MapEditProposal
from app.models.map_version import MapVersion
from app.models.user import User
from app.services.rbac import RBACService

router = APIRouter(prefix="/map-edit-proposals", tags=["map-edits"])


# =============================================================================
# Schemas
# =============================================================================


class ProposedChanges(BaseModel):
    """Changes being proposed to a beatmap."""

    edits: list[dict] = Field(
        ..., description="List of note edits (add, remove, modify operations)"
    )
    bsm_content: dict = Field(..., description="Full updated beatmap content")


class ProposalCreateRequest(BaseModel):
    """Request to create a new map edit proposal."""

    map_id: uuid.UUID = Field(..., description="ID of the map being edited")
    proposed_changes: ProposedChanges
    comment: str = Field(
        default="Submitted via Timeline Editor",
        max_length=500,
        description="Description of the changes",
    )
    edit_type: str = Field(
        default="general",
        description="Type of edit: timing_fix, note_correction, lane_adjustment, general",
    )


class ProposalResponse(BaseModel):
    """Response after creating a proposal."""

    id: uuid.UUID
    map_version_id: uuid.UUID
    proposer_id: uuid.UUID
    summary: str
    status: EditStatus
    submitted_at: datetime

    model_config = {"from_attributes": True}


class ProposalListItem(BaseModel):
    """Summary of a proposal for list views."""

    id: uuid.UUID
    map_version_id: uuid.UUID
    summary: str
    status: EditStatus
    submitted_at: datetime
    song_title: Optional[str] = None
    artist: Optional[str] = None

    model_config = {"from_attributes": True}


class MyProposalsResponse(BaseModel):
    """Paginated list of user's own proposals."""

    items: list[ProposalListItem]
    total: int
    page: int
    page_size: int


# =============================================================================
# Routes
# =============================================================================


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    request: ProposalCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProposalResponse:
    """Submit a new map edit proposal.

    Creates a proposal for changes to a beatmap that will be reviewed
    by verifiers before being applied.
    """
    # Find the latest version of the map
    query = (
        select(MapVersion)
        .where(MapVersion.map_id == request.map_id)
        .order_by(MapVersion.version_number.desc())
        .limit(1)
    )
    result = await db.execute(query)
    map_version = result.scalar_one_or_none()

    if not map_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Map {request.map_id} not found",
        )

    # Count number of edits for the summary
    edit_count = len(request.proposed_changes.edits)
    summary = f"{request.edit_type.replace('_', ' ').title()}: {request.comment[:100]}"
    if len(request.comment) > 100:
        summary = summary[:97] + "..."

    # Create the proposal
    proposal = MapEditProposal(
        map_version_id=map_version.id,
        proposer_id=current_user.id,
        summary=summary,
        diff_payload={
            "edit_type": request.edit_type,
            "edit_count": edit_count,
            "edits": request.proposed_changes.edits,
            "bsm_content": request.proposed_changes.bsm_content,
            "comment": request.comment,
        },
        status=EditStatus.PENDING,
    )

    db.add(proposal)
    await db.commit()
    await db.refresh(proposal)

    # Check and award edit achievements (best effort)
    try:
        from app.services.achievements import check_edit_achievements

        awarded = await check_edit_achievements(
            db, current_user.id, edit_approved=False
        )
        if awarded:
            await db.commit()
    except Exception:
        pass  # Silent failure for achievements

    return ProposalResponse(
        id=proposal.id,
        map_version_id=proposal.map_version_id,
        proposer_id=proposal.proposer_id,
        summary=proposal.summary,
        status=proposal.status,
        submitted_at=proposal.submitted_at,
    )


@router.get("/mine", response_model=MyProposalsResponse)
async def list_my_proposals(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[EditStatus] = Query(None, alias="status"),
) -> MyProposalsResponse:
    """List the current user's map edit proposals.

    Returns a paginated list of proposals submitted by the current user.
    """
    offset = (page - 1) * page_size

    # Build query
    query = (
        select(MapEditProposal)
        .options(joinedload(MapEditProposal.map_version))
        .where(MapEditProposal.proposer_id == current_user.id)
    )

    if status_filter:
        query = query.where(MapEditProposal.status == status_filter)

    # Get total count
    from sqlalchemy import func

    count_query = (
        select(func.count())
        .select_from(MapEditProposal)
        .where(MapEditProposal.proposer_id == current_user.id)
    )
    if status_filter:
        count_query = count_query.where(MapEditProposal.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get proposals
    query = (
        query.order_by(MapEditProposal.submitted_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    proposals = result.scalars().all()

    items = []
    for p in proposals:
        items.append(
            ProposalListItem(
                id=p.id,
                map_version_id=p.map_version_id,
                summary=p.summary,
                status=p.status,
                submitted_at=p.submitted_at,
                # Could join through to song for title/artist
            )
        )

    return MyProposalsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    rbac: Annotated[RBACService, Depends(get_rbac_service)],
) -> ProposalResponse:
    """Get a specific proposal by ID.

    Users can view their own proposals. Verifiers can view any proposal.
    """
    query = select(MapEditProposal).where(MapEditProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )

    # Check access - must be proposer or verifier
    if proposal.proposer_id != current_user.id:
        # Check if user has verifier role
        is_verifier = await rbac.user_is_verifier(current_user.id)
        if not is_verifier:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own proposals",
            )

    return ProposalResponse(
        id=proposal.id,
        map_version_id=proposal.map_version_id,
        proposer_id=proposal.proposer_id,
        summary=proposal.summary,
        status=proposal.status,
        submitted_at=proposal.submitted_at,
    )


@router.delete(
    "/{proposal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def withdraw_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Withdraw a pending proposal.

    Only the proposer can withdraw their own pending proposals.
    """
    query = select(MapEditProposal).where(MapEditProposal.id == proposal_id)
    result = await db.execute(query)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )

    if proposal.proposer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only withdraw your own proposals",
        )

    if proposal.status != EditStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot withdraw proposal with status: {proposal.status.value}",
        )

    proposal.status = EditStatus.WITHDRAWN
    await db.commit()
