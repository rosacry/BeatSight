"""Training contribution API routes for collaborative beatmap refinement.

This module provides endpoints for submitting, reviewing, and managing
user corrections to AI-generated beatmaps that can be used to improve
the model over time.

Endpoints:
- POST /contributions/submit - Submit a correction for training
- GET /contributions/pending - Get pending contributions for review (verifiers)
- POST /contributions/{id}/approve - Approve a contribution (verifiers)
- POST /contributions/{id}/reject - Reject a contribution (verifiers)
- GET /contributions/my - Get current user's contributions
- GET /contributions/stats - Get contribution statistics
- POST /contributions/consent - Update contribution consent settings
- GET /contributions/consent - Get current consent settings
- GET /contributions/export - Export approved contributions for training (admin)
- GET /contributions/manifest - Generate training manifest JSON (admin)
- GET /contributions/export-stats - Get export statistics (admin)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, get_db_session
from app.models.karma import KarmaReason
from app.models.training_contribution import (
    ContributionBatchImpact,
    ContributionConsent,
    ContributionStatus,
    CorrectionType,
    TrainingContribution,
)
from app.models.map_version import MapVersion
from app.models.user import User
from app.services.karma import KarmaService
from app.services.rbac import RequireAdmin, RequireVerifier
from app.services.training_export import TrainingExportService

router = APIRouter(prefix="/contributions", tags=["contributions"])

# =============================================================================
# Configuration
# =============================================================================

# Minimum karma required to submit contributions
MIN_KARMA_FOR_CONTRIBUTIONS = 100

# Maximum contributions per user per day
MAX_DAILY_CONTRIBUTIONS = 50

# Component changes require verifier approval
HIGH_IMPACT_CORRECTION_TYPES = {
    CorrectionType.COMPONENT_CHANGE,
    CorrectionType.NOTE_ADDITION,
}

# Statistical validation thresholds
MAX_TIMING_ADJUSTMENT_MS = 500  # Reject timing corrections > 500ms
MAX_CONFLICTING_CORRECTIONS = 3  # Flag onsets with too many conflicting corrections

# Valid drum components for validation
VALID_DRUM_COMPONENTS = {
    "kick",
    "snare",
    "hi-hat",
    "closed-hat",
    "open-hat",
    "crash",
    "ride",
    "tom",
    "high-tom",
    "mid-tom",
    "low-tom",
    "floor-tom",
    "china",
    "splash",
    "bell",
    "rim",
    "ghost",
    "flam",
}


# =============================================================================
# Schemas
# =============================================================================


class ContributionSubmitRequest(BaseModel):
    """Request to submit a training contribution."""

    map_version_id: uuid.UUID = Field(..., description="ID of the beatmap version")
    onset_time_ms: int = Field(..., ge=0, description="Onset time in milliseconds")
    correction_type: CorrectionType = Field(..., description="Type of correction")
    original_component: str = Field(
        ..., max_length=50, description="Original AI prediction"
    )
    corrected_component: str = Field(..., max_length=50, description="Your correction")
    original_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Original confidence score (0-1)"
    )
    corrected_time_ms: Optional[int] = Field(
        None, ge=0, description="Adjusted onset time (for timing corrections)"
    )
    corrected_velocity: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Adjusted velocity (0-1)"
    )
    correction_reason: Optional[str] = Field(
        None, max_length=500, description="Explanation for the correction"
    )

    @field_validator("correction_type")
    @classmethod
    def validate_correction_fields(cls, v: CorrectionType) -> CorrectionType:
        return v


class ContributionResponse(BaseModel):
    """Response for a single contribution."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: Optional[str] = None
    map_version_id: uuid.UUID
    onset_time_ms: int
    correction_type: CorrectionType
    original_component: str
    corrected_component: str
    original_confidence: Optional[float]
    correction_reason: Optional[str]
    status: ContributionStatus
    created_at: datetime
    reviewed_at: Optional[datetime]
    verifier_notes: Optional[str]


class ContributionListResponse(BaseModel):
    """Response for a list of contributions."""

    items: list[ContributionResponse]
    total: int
    page: int
    page_size: int


class ReviewRequest(BaseModel):
    """Request to approve or reject a contribution."""

    notes: Optional[str] = Field(None, max_length=512, description="Review notes")


class ConsentRequest(BaseModel):
    """Request to update consent settings."""

    consent_given: bool = Field(..., description="Whether user consents to contribute")
    allow_anonymous_export: bool = Field(
        True, description="Allow contributions to be exported without attribution"
    )
    allow_public_credit: bool = Field(
        False, description="Allow public credit in release notes"
    )


class ConsentResponse(BaseModel):
    """Response for consent settings."""

    model_config = {"from_attributes": True}

    consent_given: bool
    allow_anonymous_export: bool
    allow_public_credit: bool
    consented_at: Optional[datetime]
    updated_at: datetime


class ContributionStatsResponse(BaseModel):
    """Statistics about a user's contributions."""

    total_submitted: int
    pending: int
    approved: int
    rejected: int
    exported: int
    approval_rate: float
    karma_earned: int


class ExportResponse(BaseModel):
    """Response for contribution export."""

    batch_id: str
    count: int
    contributions: list[dict]


class ExportStatisticsResponse(BaseModel):
    """Response for export statistics."""

    total_contributions: int
    pending_review: int
    approved: int
    rejected: int
    exported: int
    pending_export: int
    correction_types_approved: dict[str, int]


class ManifestResponse(BaseModel):
    """Response for training manifest generation."""

    version: str
    batch_id: str
    generated_at: str
    sample_count: int
    source: str
    statistics: dict[str, Any]
    samples: list[dict[str, Any]]
    metadata: Optional[dict[str, Any]] = None


class ImpactCreateRequest(BaseModel):
    """Request to record contribution batch impact after training."""

    batch_id: str = Field(..., description="Training batch ID from manifest")
    model_checkpoint: str = Field(..., description="Model checkpoint path/identifier")
    baseline_accuracy: float = Field(
        ..., ge=0, le=1, description="Accuracy before training"
    )
    post_training_accuracy: float = Field(
        ..., ge=0, le=1, description="Accuracy after training"
    )
    baseline_f1_macro: Optional[float] = Field(None, ge=0, le=1)
    post_training_f1_macro: Optional[float] = Field(None, ge=0, le=1)
    baseline_f1_per_class: Optional[dict[str, float]] = Field(default=None)
    post_training_f1_per_class: Optional[dict[str, float]] = Field(default=None)
    per_class_improvement: Optional[dict[str, float]] = Field(default=None)
    contribution_count: int = Field(..., ge=0)
    top_contributors: Optional[list[dict[str, Any]]] = Field(default=None)


class ImpactResponse(BaseModel):
    """Response for a single batch impact record."""

    id: int
    batch_id: str
    model_checkpoint: str
    baseline_accuracy: float
    post_training_accuracy: float
    accuracy_improvement: float
    baseline_f1_macro: Optional[float]
    post_training_f1_macro: Optional[float]
    f1_improvement: Optional[float]
    per_class_improvement: Optional[dict[str, float]]
    contribution_count: int
    top_contributors: Optional[list[dict[str, Any]]]
    evaluated_at: datetime


class ImpactSummaryResponse(BaseModel):
    """Summary of all contribution impacts on model accuracy."""

    total_batches: int
    total_contributions_trained: int
    total_accuracy_improvement: float
    average_accuracy_improvement: float
    best_batch: Optional[dict[str, Any]]
    class_improvements: dict[str, float]
    recent_impacts: list[dict[str, Any]]


# =============================================================================
# Consent Endpoints
# =============================================================================


@router.get("/consent", response_model=ConsentResponse)
async def get_consent_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConsentResponse:
    """Get current user's contribution consent settings."""
    result = await db.execute(
        select(ContributionConsent).where(
            ContributionConsent.user_id == current_user.id
        )
    )
    consent = result.scalar_one_or_none()

    if not consent:
        # Return default (no consent)
        return ConsentResponse(
            consent_given=False,
            allow_anonymous_export=True,
            allow_public_credit=False,
            consented_at=None,
            updated_at=datetime.utcnow(),
        )

    return ConsentResponse.model_validate(consent)


@router.post("/consent", response_model=ConsentResponse)
async def update_consent_settings(
    request: ConsentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConsentResponse:
    """Update contribution consent settings."""
    result = await db.execute(
        select(ContributionConsent).where(
            ContributionConsent.user_id == current_user.id
        )
    )
    consent = result.scalar_one_or_none()

    now = datetime.utcnow()

    if not consent:
        consent = ContributionConsent(
            user_id=current_user.id,
            consent_given=request.consent_given,
            allow_anonymous_export=request.allow_anonymous_export,
            allow_public_credit=request.allow_public_credit,
            consented_at=now if request.consent_given else None,
        )
        db.add(consent)
    else:
        consent.consent_given = request.consent_given
        consent.allow_anonymous_export = request.allow_anonymous_export
        consent.allow_public_credit = request.allow_public_credit

        if request.consent_given and not consent.consented_at:
            consent.consented_at = now
        elif not request.consent_given:
            consent.revoked_at = now

    await db.commit()
    await db.refresh(consent)

    return ConsentResponse.model_validate(consent)


# =============================================================================
# Submission Endpoints
# =============================================================================


@router.post(
    "/submit", response_model=ContributionResponse, status_code=status.HTTP_201_CREATED
)
async def submit_contribution(
    request: ContributionSubmitRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributionResponse:
    """Submit a correction as a training contribution.

    Requirements:
    - User must have given consent to contribute
    - User must meet minimum karma threshold
    - User must not exceed daily contribution limit
    - No duplicate contribution for same onset from same user
    """
    # Check consent
    consent_result = await db.execute(
        select(ContributionConsent).where(
            ContributionConsent.user_id == current_user.id
        )
    )
    consent = consent_result.scalar_one_or_none()

    if not consent or not consent.consent_given:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must enable contribution consent in settings before submitting",
        )

    # Check karma threshold
    if current_user.karma_score < MIN_KARMA_FOR_CONTRIBUTIONS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Minimum karma of {MIN_KARMA_FOR_CONTRIBUTIONS} required to contribute. "
            f"Your current karma: {current_user.karma_score}",
        )

    # Check daily rate limit
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_count_result = await db.execute(
        select(func.count()).where(
            and_(
                TrainingContribution.user_id == current_user.id,
                TrainingContribution.created_at >= today_start,
            )
        )
    )
    daily_count = daily_count_result.scalar() or 0

    if daily_count >= MAX_DAILY_CONTRIBUTIONS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily contribution limit reached ({MAX_DAILY_CONTRIBUTIONS}). "
            "Try again tomorrow.",
        )

    # Verify map version exists
    version_result = await db.execute(
        select(MapVersion).where(MapVersion.id == request.map_version_id)
    )
    version = version_result.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Map version not found",
        )

    # Statistical validation
    # 1. Validate component names
    if request.corrected_component.lower() not in VALID_DRUM_COMPONENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid drum component: {request.corrected_component}. "
            f"Valid components: {', '.join(sorted(VALID_DRUM_COMPONENTS))}",
        )

    # 2. Validate timing adjustment magnitude
    if request.correction_type == CorrectionType.TIMING_ADJUSTMENT:
        if request.corrected_time_ms is not None:
            time_delta = abs(request.corrected_time_ms - request.onset_time_ms)
            if time_delta > MAX_TIMING_ADJUSTMENT_MS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Timing adjustment too large ({time_delta}ms). "
                    f"Maximum allowed: {MAX_TIMING_ADJUSTMENT_MS}ms. "
                    "For larger changes, consider adding a new note instead.",
                )

    # 3. Check for conflicting corrections from other users
    conflict_result = await db.execute(
        select(func.count()).where(
            and_(
                TrainingContribution.map_version_id == request.map_version_id,
                TrainingContribution.onset_time_ms == request.onset_time_ms,
                TrainingContribution.user_id != current_user.id,
                TrainingContribution.status.in_(
                    [
                        ContributionStatus.PENDING,
                        ContributionStatus.APPROVED,
                    ]
                ),
            )
        )
    )
    conflict_count = conflict_result.scalar() or 0

    # Check for duplicate
    existing_result = await db.execute(
        select(TrainingContribution).where(
            and_(
                TrainingContribution.map_version_id == request.map_version_id,
                TrainingContribution.onset_time_ms == request.onset_time_ms,
                TrainingContribution.user_id == current_user.id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a correction for this onset",
        )

    # Determine initial status
    # High-impact corrections or conflicting corrections require verifier review
    requires_review = (
        request.correction_type in HIGH_IMPACT_CORRECTION_TYPES
        or conflict_count >= MAX_CONFLICTING_CORRECTIONS
    )

    if requires_review:
        initial_status = ContributionStatus.PENDING
    else:
        # Low-impact corrections (timing, velocity) auto-approve
        initial_status = ContributionStatus.APPROVED

    contribution = TrainingContribution(
        user_id=current_user.id,
        map_version_id=request.map_version_id,
        onset_time_ms=request.onset_time_ms,
        correction_type=request.correction_type,
        original_component=request.original_component,
        corrected_component=request.corrected_component,
        original_confidence=request.original_confidence,
        corrected_time_ms=request.corrected_time_ms,
        corrected_velocity=request.corrected_velocity,
        correction_reason=request.correction_reason,
        status=initial_status,
    )

    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)

    return ContributionResponse(
        id=contribution.id,
        user_id=contribution.user_id,
        user_display_name=current_user.display_name,
        map_version_id=contribution.map_version_id,
        onset_time_ms=contribution.onset_time_ms,
        correction_type=contribution.correction_type,
        original_component=contribution.original_component,
        corrected_component=contribution.corrected_component,
        original_confidence=contribution.original_confidence,
        correction_reason=contribution.correction_reason,
        status=contribution.status,
        created_at=contribution.created_at,
        reviewed_at=contribution.reviewed_at,
        verifier_notes=contribution.verifier_notes,
    )


@router.get("/my", response_model=ContributionListResponse)
async def get_my_contributions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Optional[ContributionStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContributionListResponse:
    """Get current user's contributions."""
    query = select(TrainingContribution).where(
        TrainingContribution.user_id == current_user.id
    )

    if status_filter:
        query = query.where(TrainingContribution.status == status_filter)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page
    query = query.order_by(TrainingContribution.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    contributions = result.scalars().all()

    return ContributionListResponse(
        items=[
            ContributionResponse(
                id=c.id,
                user_id=c.user_id,
                user_display_name=current_user.display_name,
                map_version_id=c.map_version_id,
                onset_time_ms=c.onset_time_ms,
                correction_type=c.correction_type,
                original_component=c.original_component,
                corrected_component=c.corrected_component,
                original_confidence=c.original_confidence,
                correction_reason=c.correction_reason,
                status=c.status,
                created_at=c.created_at,
                reviewed_at=c.reviewed_at,
                verifier_notes=c.verifier_notes,
            )
            for c in contributions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=ContributionStatsResponse)
async def get_contribution_stats(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributionStatsResponse:
    """Get contribution statistics for current user."""
    # Count by status
    status_counts = {}
    for s in ContributionStatus:
        count_result = await db.execute(
            select(func.count()).where(
                and_(
                    TrainingContribution.user_id == current_user.id,
                    TrainingContribution.status == s,
                )
            )
        )
        status_counts[s] = count_result.scalar() or 0

    total = sum(status_counts.values())
    approved = status_counts.get(ContributionStatus.APPROVED, 0)
    exported = status_counts.get(ContributionStatus.EXPORTED, 0)

    # Calculate approval rate (approved + exported vs reviewed)
    reviewed = approved + exported + status_counts.get(ContributionStatus.REJECTED, 0)
    approval_rate = (approved + exported) / reviewed if reviewed > 0 else 0.0

    # Karma earned from contributions (10 per approved contribution)
    karma_earned = (approved + exported) * 10

    return ContributionStatsResponse(
        total_submitted=total,
        pending=status_counts.get(ContributionStatus.PENDING, 0),
        approved=approved,
        rejected=status_counts.get(ContributionStatus.REJECTED, 0),
        exported=exported,
        approval_rate=approval_rate,
        karma_earned=karma_earned,
    )


# =============================================================================
# Verifier Endpoints
# =============================================================================


@router.get("/pending", response_model=ContributionListResponse)
async def get_pending_contributions(
    current_user: Annotated[User, Depends(get_current_user)],
    _verifier: Annotated[None, RequireVerifier],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ContributionListResponse:
    """Get pending contributions for verifier review.

    Requires verifier role.
    """
    query = (
        select(TrainingContribution)
        .where(TrainingContribution.status == ContributionStatus.PENDING)
        .options(joinedload(TrainingContribution.user))
    )

    # Count total
    count_query = select(func.count()).where(
        TrainingContribution.status == ContributionStatus.PENDING
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page (oldest first for fair review)
    query = query.order_by(TrainingContribution.created_at.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    contributions = result.unique().scalars().all()

    return ContributionListResponse(
        items=[
            ContributionResponse(
                id=c.id,
                user_id=c.user_id,
                user_display_name=c.user.display_name if c.user else None,
                map_version_id=c.map_version_id,
                onset_time_ms=c.onset_time_ms,
                correction_type=c.correction_type,
                original_component=c.original_component,
                corrected_component=c.corrected_component,
                original_confidence=c.original_confidence,
                correction_reason=c.correction_reason,
                status=c.status,
                created_at=c.created_at,
                reviewed_at=c.reviewed_at,
                verifier_notes=c.verifier_notes,
            )
            for c in contributions
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{contribution_id}/approve", response_model=ContributionResponse)
async def approve_contribution(
    contribution_id: uuid.UUID,
    request: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _verifier: Annotated[None, RequireVerifier],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributionResponse:
    """Approve a pending contribution.

    Requires verifier role. Awards karma to the contributor.
    """
    result = await db.execute(
        select(TrainingContribution)
        .where(TrainingContribution.id == contribution_id)
        .options(joinedload(TrainingContribution.user))
    )
    contribution = result.unique().scalar_one_or_none()

    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found",
        )

    if contribution.status != ContributionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution is not pending (status: {contribution.status.value})",
        )

    contribution.status = ContributionStatus.APPROVED
    contribution.verifier_id = current_user.id
    contribution.verifier_notes = request.notes
    contribution.reviewed_at = datetime.utcnow()

    # Award karma to the contributor
    karma_service = KarmaService(db)
    await karma_service.award_karma(
        user_id=contribution.user_id,
        reason=KarmaReason.CONTRIBUTION_APPROVED,
        related_entity_type="training_contribution",
        related_entity_id=contribution.id,
    )

    await db.commit()
    await db.refresh(contribution)

    return ContributionResponse(
        id=contribution.id,
        user_id=contribution.user_id,
        user_display_name=contribution.user.display_name if contribution.user else None,
        map_version_id=contribution.map_version_id,
        onset_time_ms=contribution.onset_time_ms,
        correction_type=contribution.correction_type,
        original_component=contribution.original_component,
        corrected_component=contribution.corrected_component,
        original_confidence=contribution.original_confidence,
        correction_reason=contribution.correction_reason,
        status=contribution.status,
        created_at=contribution.created_at,
        reviewed_at=contribution.reviewed_at,
        verifier_notes=contribution.verifier_notes,
    )


@router.post("/{contribution_id}/reject", response_model=ContributionResponse)
async def reject_contribution(
    contribution_id: uuid.UUID,
    request: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _verifier: Annotated[None, RequireVerifier],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContributionResponse:
    """Reject a pending contribution.

    Requires verifier role. Notes are required to explain rejection.
    Applies karma penalty to the contributor.
    """
    if not request.notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notes are required when rejecting a contribution",
        )

    result = await db.execute(
        select(TrainingContribution)
        .where(TrainingContribution.id == contribution_id)
        .options(joinedload(TrainingContribution.user))
    )
    contribution = result.unique().scalar_one_or_none()

    if not contribution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contribution not found",
        )

    if contribution.status != ContributionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contribution is not pending (status: {contribution.status.value})",
        )

    contribution.status = ContributionStatus.REJECTED
    contribution.verifier_id = current_user.id
    contribution.verifier_notes = request.notes
    contribution.reviewed_at = datetime.utcnow()

    # Apply karma penalty to the contributor
    karma_service = KarmaService(db)
    await karma_service.award_karma(
        user_id=contribution.user_id,
        reason=KarmaReason.CONTRIBUTION_REJECTED,
        related_entity_type="training_contribution",
        related_entity_id=contribution.id,
    )

    await db.commit()
    await db.refresh(contribution)

    return ContributionResponse(
        id=contribution.id,
        user_id=contribution.user_id,
        user_display_name=contribution.user.display_name if contribution.user else None,
        map_version_id=contribution.map_version_id,
        onset_time_ms=contribution.onset_time_ms,
        correction_type=contribution.correction_type,
        original_component=contribution.original_component,
        corrected_component=contribution.corrected_component,
        original_confidence=contribution.original_confidence,
        correction_reason=contribution.correction_reason,
        status=contribution.status,
        created_at=contribution.created_at,
        reviewed_at=contribution.reviewed_at,
        verifier_notes=contribution.verifier_notes,
    )


# =============================================================================
# Admin Export Endpoint
# =============================================================================


@router.get("/export", response_model=ExportResponse)
async def export_contributions(
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(1000, ge=1, le=10000),
) -> ExportResponse:
    """Export approved contributions for model training.

    Requires admin role. Marks exported contributions to prevent re-export.
    """
    # Get approved but not yet exported contributions
    result = await db.execute(
        select(TrainingContribution)
        .where(
            and_(
                TrainingContribution.status == ContributionStatus.APPROVED,
                TrainingContribution.exported_to_training.is_(False),
            )
        )
        .limit(limit)
    )
    contributions = result.scalars().all()

    if not contributions:
        return ExportResponse(
            batch_id="",
            count=0,
            contributions=[],
        )

    # Generate batch ID
    batch_id = f"export-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    now = datetime.utcnow()

    # Mark as exported and build export data
    export_data = []
    for c in contributions:
        c.exported_to_training = True
        c.exported_at = now
        c.export_batch_id = batch_id
        c.status = ContributionStatus.EXPORTED

        export_data.append(
            {
                "id": str(c.id),
                "map_version_id": str(c.map_version_id),
                "onset_time_ms": c.onset_time_ms,
                "correction_type": c.correction_type.value,
                "original_component": c.original_component,
                "corrected_component": c.corrected_component,
                "original_confidence": c.original_confidence,
                "corrected_time_ms": c.corrected_time_ms,
                "corrected_velocity": c.corrected_velocity,
            }
        )

    await db.commit()

    return ExportResponse(
        batch_id=batch_id,
        count=len(export_data),
        contributions=export_data,
    )


@router.get("/manifest", response_model=ManifestResponse)
async def generate_training_manifest(
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(10000, ge=1, le=50000),
    include_metadata: bool = Query(True),
    weighted: bool = Query(True, description="Include karma-based weights"),
) -> ManifestResponse:
    """Generate a training manifest from approved contributions.

    This endpoint generates a comprehensive training manifest in a format
    compatible with the AI pipeline. Unlike /export, this does NOT mark
    contributions as exported - it's a preview/dry-run.

    Use /export to actually mark contributions as exported after successfully
    integrating them into training.

    Requires admin role.
    """
    service = TrainingExportService(db)
    manifest = await service.generate_manifest(
        limit=limit,
        include_metadata=include_metadata,
        weighted_by_karma=weighted,
    )
    return ManifestResponse(**manifest)


@router.get("/export-stats", response_model=ExportStatisticsResponse)
async def get_export_statistics(
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ExportStatisticsResponse:
    """Get statistics about export-ready contributions.

    Provides an overview of contribution status and what's ready for export.

    Requires admin role.
    """
    service = TrainingExportService(db)
    stats = await service.get_export_statistics()
    return ExportStatisticsResponse(**stats)


# =============================================================================
# Impact Tracking Endpoints
# =============================================================================


@router.post(
    "/impact", response_model=ImpactResponse, status_code=status.HTTP_201_CREATED
)
async def record_batch_impact(
    request: ImpactCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImpactResponse:
    """Record model accuracy impact after training on a contribution batch.

    This endpoint stores the results of evaluating model performance before
    and after training on user-contributed corrections. Call this from the
    AI pipeline after completing a training run.

    Requires admin role.
    """
    # Check if batch already has impact recorded
    existing = await db.execute(
        select(ContributionBatchImpact).where(
            ContributionBatchImpact.batch_id == request.batch_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Impact already recorded for batch {request.batch_id}",
        )

    impact = ContributionBatchImpact(
        batch_id=request.batch_id,
        model_checkpoint=request.model_checkpoint,
        baseline_accuracy=request.baseline_accuracy,
        post_training_accuracy=request.post_training_accuracy,
        baseline_f1_macro=request.baseline_f1_macro,
        post_training_f1_macro=request.post_training_f1_macro,
        baseline_f1_per_class=request.baseline_f1_per_class,
        post_training_f1_per_class=request.post_training_f1_per_class,
        per_class_improvement=request.per_class_improvement,
        contribution_count=request.contribution_count,
        top_contributors=request.top_contributors,
    )
    db.add(impact)
    await db.commit()
    await db.refresh(impact)

    return ImpactResponse(
        id=impact.id,
        batch_id=impact.batch_id,
        model_checkpoint=impact.model_checkpoint,
        baseline_accuracy=impact.baseline_accuracy,
        post_training_accuracy=impact.post_training_accuracy,
        accuracy_improvement=impact.post_training_accuracy - impact.baseline_accuracy,
        baseline_f1_macro=impact.baseline_f1_macro,
        post_training_f1_macro=impact.post_training_f1_macro,
        f1_improvement=(
            impact.post_training_f1_macro - impact.baseline_f1_macro
            if impact.post_training_f1_macro and impact.baseline_f1_macro
            else None
        ),
        per_class_improvement=impact.per_class_improvement,
        contribution_count=impact.contribution_count,
        top_contributors=impact.top_contributors,
        evaluated_at=impact.evaluated_at,
    )


@router.get("/impact/{batch_id}", response_model=ImpactResponse)
async def get_batch_impact(
    batch_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImpactResponse:
    """Get impact metrics for a specific training batch.

    Requires admin role.
    """
    result = await db.execute(
        select(ContributionBatchImpact).where(
            ContributionBatchImpact.batch_id == batch_id
        )
    )
    impact = result.scalar_one_or_none()

    if not impact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No impact record found for batch {batch_id}",
        )

    return ImpactResponse(
        id=impact.id,
        batch_id=impact.batch_id,
        model_checkpoint=impact.model_checkpoint,
        baseline_accuracy=impact.baseline_accuracy,
        post_training_accuracy=impact.post_training_accuracy,
        accuracy_improvement=impact.post_training_accuracy - impact.baseline_accuracy,
        baseline_f1_macro=impact.baseline_f1_macro,
        post_training_f1_macro=impact.post_training_f1_macro,
        f1_improvement=(
            impact.post_training_f1_macro - impact.baseline_f1_macro
            if impact.post_training_f1_macro and impact.baseline_f1_macro
            else None
        ),
        per_class_improvement=impact.per_class_improvement,
        contribution_count=impact.contribution_count,
        top_contributors=impact.top_contributors,
        evaluated_at=impact.evaluated_at,
    )


@router.get("/impact/summary", response_model=ImpactSummaryResponse)
async def get_impact_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    _admin: Annotated[None, RequireAdmin],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImpactSummaryResponse:
    """Get overall summary of contribution impact on model accuracy.

    This provides aggregate statistics across all training batches to
    show the cumulative effect of user contributions on model quality.

    Requires admin role.
    """
    # Get all impact records
    result = await db.execute(
        select(ContributionBatchImpact).order_by(
            ContributionBatchImpact.evaluated_at.desc()
        )
    )
    impacts = result.scalars().all()

    if not impacts:
        return ImpactSummaryResponse(
            total_batches=0,
            total_contributions_trained=0,
            total_accuracy_improvement=0.0,
            average_accuracy_improvement=0.0,
            best_batch=None,
            class_improvements={},
            recent_impacts=[],
        )

    # Calculate aggregates
    total_contributions = sum(i.contribution_count for i in impacts)
    improvements = [i.post_training_accuracy - i.baseline_accuracy for i in impacts]
    total_improvement = sum(improvements)
    avg_improvement = total_improvement / len(impacts)

    # Find best batch
    best_idx = improvements.index(max(improvements))
    best = impacts[best_idx]
    best_batch = {
        "batch_id": best.batch_id,
        "accuracy_improvement": improvements[best_idx],
        "contribution_count": best.contribution_count,
        "evaluated_at": best.evaluated_at.isoformat(),
    }

    # Aggregate class improvements
    class_improvements: dict[str, list[float]] = {}
    for impact in impacts:
        if impact.per_class_improvement:
            for cls, improvement in impact.per_class_improvement.items():
                if cls not in class_improvements:
                    class_improvements[cls] = []
                class_improvements[cls].append(improvement)

    avg_class_improvements = {
        cls: sum(vals) / len(vals) for cls, vals in class_improvements.items()
    }

    # Recent impacts
    recent = [
        {
            "batch_id": i.batch_id,
            "accuracy_improvement": i.post_training_accuracy - i.baseline_accuracy,
            "contribution_count": i.contribution_count,
            "evaluated_at": i.evaluated_at.isoformat(),
        }
        for i in impacts[:10]
    ]

    return ImpactSummaryResponse(
        total_batches=len(impacts),
        total_contributions_trained=total_contributions,
        total_accuracy_improvement=total_improvement,
        average_accuracy_improvement=avg_improvement,
        best_batch=best_batch,
        class_improvements=avg_class_improvements,
        recent_impacts=recent,
    )
