"""
Admin API routes for internal tooling and support.

Ticket E2-007: Admin Dashboard for AI Job Inspection
- Admin route: /admin/ai-jobs
- List view with filters: status, user, date range
- Detail view showing job parameters, progress history, error logs
- Retry button
- Requires admin role
- Audit log for admin actions

Updated with E4-001: RBAC System
- All admin endpoints now require ADMIN_DASHBOARD permission
- Job management requires JOB_ADMIN permission
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.ai_job import AIJob, AIJobState, AIJobPriority
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.role import Role, UserRole
from app.logging import get_logger
from app.services.rbac import Permission, require_permission, RequireAdminDashboard

router = APIRouter(prefix="/admin", tags=["admin"])
logger = get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class AdminJobSummary(BaseModel):
    """Summary of an AI job for admin list view."""

    id: uuid.UUID
    song_id: uuid.UUID
    state: AIJobState
    priority: AIJobPriority
    requested_by_id: uuid.UUID | None
    requested_by_email: str | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    retry_count: int
    max_retries: int
    worker_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class AdminJobDetail(AdminJobSummary):
    """Detailed AI job info for admin view."""

    progress_percent: int | None
    progress_message: str | None
    last_heartbeat: datetime | None
    next_retry_at: datetime | None
    last_error: str | None
    duration_seconds: float | None = None


class AdminJobListResponse(BaseModel):
    """Response for admin job list endpoint."""

    jobs: list[AdminJobSummary]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class QueueStats(BaseModel):
    """Statistics about the job queue."""

    total_jobs: int
    queued: int
    processing: int
    complete: int
    failed: int
    cancelled: int
    avg_processing_time_seconds: float | None
    jobs_today: int
    jobs_this_hour: int


class AdminAction(BaseModel):
    """Record of an admin action."""

    action: str
    job_id: uuid.UUID
    admin_id: uuid.UUID | None
    timestamp: datetime
    details: dict[str, Any] | None = None


class AdminActionResponse(BaseModel):
    """Response for admin action."""

    success: bool
    message: str
    job: AdminJobSummary | None = None


# =============================================================================
# Helper Functions
# =============================================================================


async def log_admin_action(
    action: str,
    job_id: uuid.UUID,
    admin_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an admin action for audit trail."""
    logger.info(
        "admin_action",
        action=action,
        job_id=str(job_id),
        admin_id=str(admin_id) if admin_id else None,
        details=details,
    )


def job_to_summary(job: AIJob, email: str | None = None) -> AdminJobSummary:
    """Convert AIJob model to AdminJobSummary."""
    return AdminJobSummary(
        id=job.id,
        song_id=job.song_id,
        state=job.state,
        priority=job.priority,
        requested_by_id=job.requested_by_id,
        requested_by_email=email,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        worker_id=job.worker_id,
    )


def job_to_detail(job: AIJob, email: str | None = None) -> AdminJobDetail:
    """Convert AIJob model to AdminJobDetail."""
    duration = None
    if job.started_at and job.finished_at:
        duration = (job.finished_at - job.started_at).total_seconds()

    return AdminJobDetail(
        id=job.id,
        song_id=job.song_id,
        state=job.state,
        priority=job.priority,
        requested_by_id=job.requested_by_id,
        requested_by_email=email,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        worker_id=job.worker_id,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        last_heartbeat=job.last_heartbeat,
        next_retry_at=job.next_retry_at,
        last_error=job.last_error,
        duration_seconds=duration,
    )


# =============================================================================
# Admin Endpoints
# =============================================================================


@router.get(
    "/ai-jobs",
    response_model=AdminJobListResponse,
    summary="List AI jobs with filters",
    description="Admin endpoint to list and filter AI jobs.",
)
async def list_ai_jobs(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
    state: Annotated[
        AIJobState | None, Query(description="Filter by job state")
    ] = None,
    user_id: Annotated[
        uuid.UUID | None, Query(description="Filter by requesting user")
    ] = None,
    priority: Annotated[
        AIJobPriority | None, Query(description="Filter by priority")
    ] = None,
    date_from: Annotated[
        datetime | None, Query(description="Filter jobs created after this date")
    ] = None,
    date_to: Annotated[
        datetime | None, Query(description="Filter jobs created before this date")
    ] = None,
    has_error: Annotated[
        bool | None, Query(description="Filter jobs with/without errors")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> AdminJobListResponse:
    """
    List AI jobs with optional filters.

    Supports filtering by:
    - state: queued, processing, complete, failed, cancelled
    - user_id: UUID of requesting user
    - priority: standard, priority
    - date_from/date_to: created_at range
    - has_error: whether job has an error message
    """
    # Build query with filters
    conditions = []

    if state is not None:
        conditions.append(AIJob.state == state)
    if user_id is not None:
        conditions.append(AIJob.requested_by_id == user_id)
    if priority is not None:
        conditions.append(AIJob.priority == priority)
    if date_from is not None:
        conditions.append(AIJob.created_at >= date_from)
    if date_to is not None:
        conditions.append(AIJob.created_at <= date_to)
    if has_error is True:
        conditions.append(AIJob.error_message.isnot(None))
    elif has_error is False:
        conditions.append(AIJob.error_message.is_(None))

    # Count total
    count_query = select(func.count(AIJob.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch jobs with pagination
    offset = (page - 1) * page_size
    query = (
        select(AIJob).order_by(AIJob.created_at.desc()).offset(offset).limit(page_size)
    )
    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    jobs = result.scalars().all()

    # Convert to response models
    job_summaries = [job_to_summary(job) for job in jobs]

    return AdminJobListResponse(
        jobs=job_summaries,
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + len(jobs) < total,
        has_prev=page > 1,
    )


@router.get(
    "/ai-jobs/stats",
    response_model=QueueStats,
    summary="Get queue statistics",
    description="Get statistics about the AI job queue.",
)
async def get_queue_stats(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> QueueStats:
    """
    Get statistics about the AI job queue.

    Returns counts by state, average processing time, and recent activity.
    Optimized: single query for state counts + parallel execution.
    """
    import asyncio
    from datetime import timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_ago = now - timedelta(hours=1)

    # Single query for all state counts (much faster than 5 separate queries)
    state_count_query = select(AIJob.state, func.count(AIJob.id)).group_by(AIJob.state)

    # Average processing time for completed jobs
    avg_query = select(
        func.avg(
            func.extract("epoch", AIJob.finished_at)
            - func.extract("epoch", AIJob.started_at)
        )
    ).where(
        and_(
            AIJob.state == AIJobState.COMPLETE,
            AIJob.started_at.isnot(None),
            AIJob.finished_at.isnot(None),
        )
    )

    # Jobs today
    today_query = select(func.count(AIJob.id)).where(AIJob.created_at >= today_start)

    # Jobs this hour
    hour_query = select(func.count(AIJob.id)).where(AIJob.created_at >= hour_ago)

    # Execute queries sequentially (async SQLAlchemy doesn't support concurrent operations on same session)
    state_result = await db.execute(state_count_query)
    avg_result = await db.execute(avg_query)
    today_result = await db.execute(today_query)
    hour_result = await db.execute(hour_query)

    # Process state counts
    state_counts = {state.value: 0 for state in AIJobState}
    for state, count in state_result.all():
        state_counts[state.value] = count

    total = sum(state_counts.values())

    return QueueStats(
        total_jobs=total,
        queued=state_counts.get("queued", 0),
        processing=state_counts.get("processing", 0),
        complete=state_counts.get("complete", 0),
        failed=state_counts.get("failed", 0),
        cancelled=state_counts.get("cancelled", 0),
        avg_processing_time_seconds=avg_result.scalar(),
        jobs_today=today_result.scalar() or 0,
        jobs_this_hour=hour_result.scalar() or 0,
    )


@router.get(
    "/ai-jobs/{job_id}",
    response_model=AdminJobDetail,
    summary="Get AI job details",
    description="Get detailed information about a specific AI job.",
)
async def get_ai_job_detail(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> AdminJobDetail:
    """
    Get detailed information about a specific AI job.

    Includes all job fields, progress information, and calculated duration.
    """
    query = select(AIJob).where(AIJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Get requester email if available
    email = None
    if job.requested_by_id:
        user_query = select(User.email).where(User.id == job.requested_by_id)
        email = (await db.execute(user_query)).scalar()

    return job_to_detail(job, email)


@router.post(
    "/ai-jobs/{job_id}/retry",
    response_model=AdminActionResponse,
    summary="Retry a failed job",
    description="Reset a failed or cancelled job to queued state.",
)
async def admin_retry_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.JOB_ADMIN))],
) -> AdminActionResponse:
    """
    Retry a failed or cancelled job.

    Resets the job to queued state and clears error information.
    Increments retry count and logs the admin action.
    """
    query = select(AIJob).where(AIJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.state not in (AIJobState.FAILED, AIJobState.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job in state {job.state}",
        )

    # Reset job state
    job.state = AIJobState.QUEUED
    job.error_message = None
    job.started_at = None
    job.finished_at = None
    job.worker_id = None
    job.last_heartbeat = None
    job.progress_percent = None
    job.progress_message = None
    job.retry_count += 1

    await db.commit()
    await db.refresh(job)

    # Log admin action
    await log_admin_action(
        "retry_job", job_id, admin_id=admin.id, details={"new_state": "queued"}
    )

    return AdminActionResponse(
        success=True,
        message=f"Job {job_id} has been requeued (retry #{job.retry_count})",
        job=job_to_summary(job),
    )


@router.post(
    "/ai-jobs/{job_id}/cancel",
    response_model=AdminActionResponse,
    summary="Cancel a job",
    description="Cancel a queued or processing job.",
)
async def admin_cancel_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.JOB_ADMIN))],
) -> AdminActionResponse:
    """
    Cancel a queued or processing job.

    Sets the job state to cancelled and logs the admin action.
    """
    query = select(AIJob).where(AIJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.state not in (AIJobState.QUEUED, AIJobState.PROCESSING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in state {job.state}",
        )

    old_state = job.state
    job.state = AIJobState.CANCELLED
    job.finished_at = datetime.utcnow()

    await db.commit()
    await db.refresh(job)

    # Log admin action
    await log_admin_action(
        "cancel_job",
        job_id,
        admin_id=admin.id,
        details={"old_state": old_state.value, "new_state": "cancelled"},
    )

    return AdminActionResponse(
        success=True,
        message=f"Job {job_id} has been cancelled",
        job=job_to_summary(job),
    )


@router.post(
    "/ai-jobs/{job_id}/set-priority",
    response_model=AdminActionResponse,
    summary="Change job priority",
    description="Change the priority of a queued job.",
)
async def admin_set_priority(
    job_id: uuid.UUID,
    priority: AIJobPriority,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.JOB_ADMIN))],
) -> AdminActionResponse:
    """
    Change the priority of a job.

    Can only change priority of queued jobs.
    """
    query = select(AIJob).where(AIJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.state != AIJobState.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change priority of job in state {job.state}",
        )

    old_priority = job.priority
    job.priority = priority

    await db.commit()
    await db.refresh(job)

    # Log admin action
    await log_admin_action(
        "set_priority",
        job_id,
        admin_id=admin.id,
        details={"old_priority": old_priority.value, "new_priority": priority.value},
    )

    return AdminActionResponse(
        success=True,
        message=f"Job {job_id} priority changed to {priority.value}",
        job=job_to_summary(job),
    )


@router.get(
    "/ai-jobs/{job_id}/logs",
    summary="Get job logs",
    description="Get recent log entries for a specific job.",
)
async def get_job_logs(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> dict[str, Any]:
    """
    Get log/progress history for a job.

    Returns available log information from the job record.
    Full log retrieval would require integration with a logging system.
    """
    query = select(AIJob).where(AIJob.id == job_id)
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Return available job history from the record
    # In production, this would query a logging service
    return {
        "job_id": str(job.id),
        "current_state": job.state.value,
        "error_message": job.error_message,
        "last_error": job.last_error,
        "progress_percent": job.progress_percent,
        "progress_message": job.progress_message,
        "retry_count": job.retry_count,
        "timeline": {
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "last_heartbeat": job.last_heartbeat.isoformat()
            if job.last_heartbeat
            else None,
            "next_retry_at": job.next_retry_at.isoformat()
            if job.next_retry_at
            else None,
        },
    }


# =============================================================================
# User Management Models
# =============================================================================


class AdminUserSummary(BaseModel):
    """User summary for admin list view."""

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    email_verified: bool
    phone_verified: bool = False
    karma_score: int
    created_at: datetime
    subscription_plan: str | None = None
    subscription_status: str | None = None
    job_count: int = 0
    last_active: datetime | None = None
    # Moderation fields
    restriction_level: str = "none"
    is_restricted: bool = False
    is_banned: bool = False
    user_warnings: int = 0

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    """Response for admin user list endpoint."""

    users: list[AdminUserSummary]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


class UserStats(BaseModel):
    """User statistics."""

    total_users: int
    verified_users: int
    pro_users: int
    users_today: int
    users_this_week: int
    users_this_month: int


class SystemOverview(BaseModel):
    """System overview statistics."""

    # Users
    total_users: int
    active_users_24h: int
    pro_subscribers: int

    # Jobs
    total_jobs: int
    jobs_today: int
    processing_jobs: int
    failed_jobs_24h: int

    # Revenue (if applicable)
    monthly_recurring_revenue: float | None = None

    # System health
    api_requests_today: int | None = None
    avg_response_time_ms: float | None = None


class UpdateUserRoleRequest(BaseModel):
    """Request to update user role."""

    role: str


class AdminUserActionResponse(BaseModel):
    """Response for user management actions."""

    success: bool
    message: str


# =============================================================================
# User Management Endpoints
# =============================================================================


async def get_user_role_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Get role codes for a user."""
    query = (
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    result = await db.execute(query)
    return [r for r in result.scalars().all()]


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List users with filters",
    description="Admin endpoint to list and filter users.",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
    search: Annotated[
        str | None, Query(description="Search by email or display name")
    ] = None,
    role: Annotated[str | None, Query(description="Filter by role code")] = None,
    subscription: Annotated[
        str | None, Query(description="Filter by subscription plan")
    ] = None,
    verified: Annotated[
        bool | None, Query(description="Filter by email verification")
    ] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> AdminUserListResponse:
    """List users with optional filters."""

    conditions = []

    if search:
        search_term = f"%{search}%"
        conditions.append(
            or_(
                User.email.ilike(search_term),
                User.display_name.ilike(search_term),
            )
        )

    if role:
        # Filter users by role code
        role_subquery = (
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.code == role)
        )
        conditions.append(User.id.in_(role_subquery))

    if verified is not None:
        conditions.append(User.email_verified == verified)

    # Base query
    base_query = select(User)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    # Count total
    count_query = select(func.count(User.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar() or 0

    # Get users with pagination
    query = (
        base_query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    users = result.scalars().all()

    # Get subscription info and job counts for users
    user_summaries = []
    for user in users:
        # Get subscription
        sub_query = (
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        sub_result = await db.execute(sub_query)
        user_subscription = sub_result.scalar_one_or_none()

        # Skip if subscription filter doesn't match
        if subscription:
            plan = user_subscription.plan_code.value if user_subscription else "free"
            if subscription == "pro" and plan not in ("pro_monthly", "pro_yearly"):
                continue
            if subscription == "free" and plan in ("pro_monthly", "pro_yearly"):
                continue

        # Get job count
        job_count_query = select(func.count(AIJob.id)).where(
            AIJob.requested_by_id == user.id
        )
        job_count = (await db.execute(job_count_query)).scalar() or 0

        # Get last job as proxy for activity
        last_job_query = (
            select(AIJob.created_at)
            .where(AIJob.requested_by_id == user.id)
            .order_by(AIJob.created_at.desc())
            .limit(1)
        )
        last_job = (await db.execute(last_job_query)).scalar()

        # Get user roles
        role_codes = await get_user_role_codes(db, user.id)
        primary_role = role_codes[0] if role_codes else "user"

        user_summaries.append(
            AdminUserSummary(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=primary_role,
                email_verified=user.email_verified,
                phone_verified=user.phone_verified,
                karma_score=user.karma_score,
                created_at=user.created_at,
                subscription_plan=user_subscription.plan_code.value
                if user_subscription
                else "free",
                subscription_status=user_subscription.status.value
                if user_subscription
                else None,
                job_count=job_count,
                last_active=last_job,
                restriction_level=user.restriction_level,
                is_restricted=user.is_restricted,
                is_banned=user.is_banned,
                user_warnings=user.user_warnings,
            )
        )

    return AdminUserListResponse(
        users=user_summaries,
        total=total,
        page=page,
        page_size=page_size,
        has_next=page * page_size < total,
        has_prev=page > 1,
    )


@router.get(
    "/users/stats",
    response_model=UserStats,
    summary="Get user statistics",
    description="Get aggregate statistics about users.",
)
async def get_user_stats(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> UserStats:
    """Get aggregate user statistics. Optimized with parallel query execution."""
    import asyncio
    from datetime import timedelta

    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # Define all queries
    total_query = select(func.count(User.id))
    verified_query = select(func.count(User.id)).where(User.email_verified.is_(True))
    pro_query = select(func.count(func.distinct(Subscription.user_id))).where(
        and_(
            or_(
                Subscription.plan_code == SubscriptionPlan.PRO_MONTHLY,
                Subscription.plan_code == SubscriptionPlan.PRO_YEARLY,
            ),
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    today_query = select(func.count(User.id)).where(User.created_at >= today)
    week_query = select(func.count(User.id)).where(User.created_at >= week_ago)
    month_query = select(func.count(User.id)).where(User.created_at >= month_ago)

    # Execute queries sequentially (async SQLAlchemy doesn't support concurrent operations on same session)
    total_r = await db.execute(total_query)
    verified_r = await db.execute(verified_query)
    pro_r = await db.execute(pro_query)
    today_r = await db.execute(today_query)
    week_r = await db.execute(week_query)
    month_r = await db.execute(month_query)

    return UserStats(
        total_users=total_r.scalar() or 0,
        verified_users=verified_r.scalar() or 0,
        pro_users=pro_r.scalar() or 0,
        users_today=today_r.scalar() or 0,
        users_this_week=week_r.scalar() or 0,
        users_this_month=month_r.scalar() or 0,
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserSummary,
    summary="Get user details",
    description="Get detailed information about a specific user.",
)
async def get_user_detail(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> AdminUserSummary:
    """Get detailed user information."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Get subscription
    sub_query = (
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub_result = await db.execute(sub_query)
    subscription = sub_result.scalar_one_or_none()

    # Get job count
    job_count = (
        await db.execute(
            select(func.count(AIJob.id)).where(AIJob.requested_by_id == user.id)
        )
    ).scalar() or 0

    # Get user roles
    role_codes = await get_user_role_codes(db, user.id)
    primary_role = role_codes[0] if role_codes else "user"

    return AdminUserSummary(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=primary_role,
        email_verified=user.email_verified,
        phone_verified=user.phone_verified,
        karma_score=user.karma_score,
        created_at=user.created_at,
        subscription_plan=subscription.plan_code.value if subscription else "free",
        subscription_status=subscription.status.value if subscription else None,
        job_count=job_count,
        restriction_level=user.restriction_level,
        is_restricted=user.is_restricted,
        is_banned=user.is_banned,
        user_warnings=user.user_warnings,
    )


@router.post(
    "/users/{user_id}/role",
    response_model=AdminUserActionResponse,
    summary="Update user role",
    description="Add or remove a role from a user.",
)
async def update_user_role(
    user_id: uuid.UUID,
    request: UpdateUserRoleRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.ROLE_ASSIGN))],
) -> AdminUserActionResponse:
    """Update user role. Requires USER_ADMIN permission."""
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Prevent demoting yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # Find the role by code
    role_query = select(Role).where(Role.code == request.role)
    role_result = await db.execute(role_query)
    role = role_result.scalar_one_or_none()

    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {request.role}",
        )

    # Get current roles
    old_roles = await get_user_role_codes(db, user.id)

    # Check if user already has this role
    existing_query = select(UserRole).where(
        and_(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    existing = (await db.execute(existing_query)).scalar_one_or_none()

    if existing:
        return AdminUserActionResponse(
            success=True,
            message=f"User already has role {request.role}",
        )

    # Add the role
    new_user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(new_user_role)
    await db.commit()

    logger.info(
        "admin_action",
        action="add_role",
        user_id=str(user_id),
        admin_id=str(admin.id),
        details={"old_roles": old_roles, "added_role": request.role},
    )

    return AdminUserActionResponse(
        success=True,
        message=f"Role {request.role} added to user",
    )


@router.get(
    "/overview",
    response_model=SystemOverview,
    summary="Get system overview",
    description="Get high-level system statistics and health metrics.",
)
async def get_system_overview(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> SystemOverview:
    """Get system overview with key metrics."""
    from datetime import timedelta

    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_ago = now - timedelta(hours=24)

    # User metrics
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    # Active users in last 24h (users who created jobs)
    active_users_query = select(func.count(func.distinct(AIJob.requested_by_id))).where(
        AIJob.created_at >= day_ago
    )
    active_users = (await db.execute(active_users_query)).scalar() or 0

    # Pro subscribers
    pro_query = select(func.count(func.distinct(Subscription.user_id))).where(
        and_(
            or_(
                Subscription.plan_code == SubscriptionPlan.PRO_MONTHLY,
                Subscription.plan_code == SubscriptionPlan.PRO_YEARLY,
            ),
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
    )
    pro_subs = (await db.execute(pro_query)).scalar() or 0

    # Job metrics
    total_jobs = (await db.execute(select(func.count(AIJob.id)))).scalar() or 0

    jobs_today = (
        await db.execute(select(func.count(AIJob.id)).where(AIJob.created_at >= today))
    ).scalar() or 0

    processing = (
        await db.execute(
            select(func.count(AIJob.id)).where(AIJob.state == AIJobState.PROCESSING)
        )
    ).scalar() or 0

    failed_24h = (
        await db.execute(
            select(func.count(AIJob.id)).where(
                and_(
                    AIJob.state == AIJobState.FAILED,
                    AIJob.finished_at >= day_ago,
                )
            )
        )
    ).scalar() or 0

    return SystemOverview(
        total_users=total_users,
        active_users_24h=active_users,
        pro_subscribers=pro_subs,
        total_jobs=total_jobs,
        jobs_today=jobs_today,
        processing_jobs=processing,
        failed_jobs_24h=failed_24h,
    )


# =============================================================================
# Account Security Management
# =============================================================================


class AccountLockoutStatus(BaseModel):
    """Account lockout status response."""

    email: str
    is_locked: bool
    lockout_until: datetime | None
    failed_attempts: int
    remaining_attempts: int


class UnlockAccountRequest(BaseModel):
    """Request to unlock an account."""

    email: str


class UnlockAccountResponse(BaseModel):
    """Response for account unlock action."""

    success: bool
    message: str


@router.get(
    "/security/lockout-status",
    response_model=AccountLockoutStatus,
    summary="Check account lockout status",
)
async def get_lockout_status(
    email: str = Query(..., description="Email address to check"),
    _admin_check: Annotated[None, RequireAdminDashboard] = None,
) -> AccountLockoutStatus:
    """
    Check the lockout status of an account.

    Requires ADMIN_DASHBOARD permission.
    """
    from app.services.account_security import get_account_security_service

    security_service = get_account_security_service()
    status = await security_service.get_attempt_status(email)

    return AccountLockoutStatus(
        email=email,
        is_locked=status["is_locked"],
        lockout_until=status["lockout_until"],
        failed_attempts=status["attempts"],
        remaining_attempts=status["remaining_attempts"],
    )


@router.post(
    "/security/unlock-account",
    response_model=UnlockAccountResponse,
    summary="Manually unlock a locked account",
)
async def unlock_account(
    request: UnlockAccountRequest,
    _admin_check: Annotated[None, RequireAdminDashboard] = None,
) -> UnlockAccountResponse:
    """
    Manually unlock a user account that was locked due to failed login attempts.

    Requires ADMIN_DASHBOARD permission.
    """
    from app.services.account_security import get_account_security_service

    security_service = get_account_security_service()
    was_locked = await security_service.manually_unlock_account(request.email)

    if was_locked:
        logger.info(
            "admin_unlocked_account", extra={"email": request.email[:3] + "***"}
        )
        return UnlockAccountResponse(
            success=True,
            message=f"Account {request.email} has been unlocked.",
        )

    return UnlockAccountResponse(
        success=True,
        message=f"Account {request.email} was not locked.",
    )


# =============================================================================
# User Moderation Models
# =============================================================================


class UserModerationStatus(BaseModel):
    """Current moderation status of a user."""

    user_id: uuid.UUID
    display_name: str
    email: str
    restriction_level: str
    restriction_reason: str | None
    restriction_expires_at: datetime | None
    restricted_at: datetime | None
    restricted_by: str | None = None
    user_warnings: int
    is_restricted: bool
    is_banned: bool
    is_silenced: bool


class ModerationHistoryItem(BaseModel):
    """Single entry in moderation history."""

    id: uuid.UUID
    action: str
    duration_hours: int | None
    reason: str | None
    admin_notes: str | None
    created_at: datetime
    actor_name: str | None = None


class UserModerationDetail(BaseModel):
    """Detailed moderation info for a user."""

    status: UserModerationStatus
    history: list[ModerationHistoryItem]


class SilenceUserRequest(BaseModel):
    """Request to silence a user."""

    duration_hours: int
    reason: str
    admin_notes: str | None = None


class RestrictUserRequest(BaseModel):
    """Request to restrict a user."""

    duration_hours: int | None = None  # None = permanent
    reason: str
    admin_notes: str | None = None


class BanUserRequest(BaseModel):
    """Request to ban a user."""

    permanent: bool = False
    duration_hours: int | None = None  # Required if not permanent
    reason: str
    admin_notes: str | None = None


class AddNoteRequest(BaseModel):
    """Request to add a note to user's account."""

    note: str
    admin_notes: str | None = None


class ModerationActionResponse(BaseModel):
    """Response for moderation actions."""

    success: bool
    message: str
    action: str | None = None


# =============================================================================
# User Moderation Endpoints
# =============================================================================


@router.get(
    "/users/{user_id}/moderation",
    response_model=UserModerationDetail,
    summary="Get user moderation status and history",
)
async def get_user_moderation(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> UserModerationDetail:
    """Get the moderation status and history for a user."""
    from app.models.moderation import UserAccountHistory
    
    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Get the admin who restricted (if any)
    restricted_by_name = None
    if user.restricted_by_id:
        admin_query = select(User.display_name).where(User.id == user.restricted_by_id)
        admin_result = await db.execute(admin_query)
        restricted_by_name = admin_result.scalar()

    # Build status
    mod_status = UserModerationStatus(
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        restriction_level=user.restriction_level,
        restriction_reason=user.restriction_reason,
        restriction_expires_at=user.restriction_expires_at,
        restricted_at=user.restricted_at,
        restricted_by=restricted_by_name,
        user_warnings=user.user_warnings,
        is_restricted=user.is_restricted,
        is_banned=user.is_banned,
        is_silenced=user.is_silenced,
    )

    # Get moderation history
    history_query = (
        select(UserAccountHistory)
        .where(UserAccountHistory.user_id == user_id)
        .order_by(UserAccountHistory.created_at.desc())
        .limit(50)
    )
    history_result = await db.execute(history_query)
    history_records = history_result.scalars().all()

    # Build history items with actor names
    history_items = []
    for record in history_records:
        actor_name = None
        if record.actor_id:
            actor_query = select(User.display_name).where(User.id == record.actor_id)
            actor_result = await db.execute(actor_query)
            actor_name = actor_result.scalar()

        history_items.append(
            ModerationHistoryItem(
                id=record.id,
                action=record.action.value,
                duration_hours=record.duration_hours,
                reason=record.reason,
                admin_notes=record.admin_notes,
                created_at=record.created_at,
                actor_name=actor_name,
            )
        )

    return UserModerationDetail(
        status=mod_status,
        history=history_items,
    )


@router.post(
    "/users/{user_id}/silence",
    response_model=ModerationActionResponse,
    summary="Silence a user (prevent posting)",
)
async def silence_user(
    user_id: uuid.UUID,
    request: SilenceUserRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.ROLE_ASSIGN))],
) -> ModerationActionResponse:
    """Silence a user, preventing them from posting or commenting."""
    from datetime import timedelta, timezone
    from app.models.moderation import UserAccountHistory, ModerationAction
    from app.models.user import RestrictionLevel

    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Prevent silencing yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot silence yourself",
        )

    # Check if already banned (more severe)
    if user.restriction_level == RestrictionLevel.BANNED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already banned (more severe than silence)",
        )

    # Apply silence
    now = datetime.now(timezone.utc)
    user.restriction_level = RestrictionLevel.SILENCED.value
    user.restriction_reason = request.reason
    user.restriction_expires_at = now + timedelta(hours=request.duration_hours)
    user.restricted_by_id = admin.id
    user.restricted_at = now
    user.user_warnings += 1

    # Create history record
    history = UserAccountHistory.add_silence(
        user_id=user.id,
        actor_id=admin.id,
        duration_hours=request.duration_hours,
        reason=request.reason,
        admin_notes=request.admin_notes,
    )
    db.add(history)

    await db.commit()

    logger.info(
        "user_silenced",
        user_id=str(user_id),
        admin_id=str(admin.id),
        duration_hours=request.duration_hours,
        reason=request.reason,
    )

    return ModerationActionResponse(
        success=True,
        message=f"User silenced for {request.duration_hours} hours",
        action="silence",
    )


@router.post(
    "/users/{user_id}/restrict",
    response_model=ModerationActionResponse,
    summary="Restrict a user (limited visibility)",
)
async def restrict_user(
    user_id: uuid.UUID,
    request: RestrictUserRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.ROLE_ASSIGN))],
) -> ModerationActionResponse:
    """Restrict a user, hiding them from leaderboards and limiting interactions."""
    from datetime import timedelta, timezone
    from app.models.moderation import UserAccountHistory, ModerationAction
    from app.models.user import RestrictionLevel

    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Prevent restricting yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot restrict yourself",
        )

    # Check if already banned
    if user.restriction_level == RestrictionLevel.BANNED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already banned (more severe than restriction)",
        )

    # Apply restriction
    now = datetime.now(timezone.utc)
    user.restriction_level = RestrictionLevel.RESTRICTED.value
    user.restriction_reason = request.reason
    user.restriction_expires_at = (
        now + timedelta(hours=request.duration_hours)
        if request.duration_hours
        else None
    )
    user.restricted_by_id = admin.id
    user.restricted_at = now
    user.user_warnings += 1

    # Create history record
    history = UserAccountHistory.add_restriction(
        user_id=user.id,
        actor_id=admin.id,
        duration_hours=request.duration_hours,
        reason=request.reason,
        admin_notes=request.admin_notes,
    )
    db.add(history)

    await db.commit()

    duration_msg = f" for {request.duration_hours} hours" if request.duration_hours else " permanently"
    logger.info(
        "user_restricted",
        user_id=str(user_id),
        admin_id=str(admin.id),
        duration_hours=request.duration_hours,
        reason=request.reason,
    )

    return ModerationActionResponse(
        success=True,
        message=f"User restricted{duration_msg}",
        action="restriction",
    )


@router.post(
    "/users/{user_id}/ban",
    response_model=ModerationActionResponse,
    summary="Ban a user (full account ban)",
)
async def ban_user(
    user_id: uuid.UUID,
    request: BanUserRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.ROLE_ASSIGN))],
) -> ModerationActionResponse:
    """Ban a user, completely disabling their account."""
    from datetime import timedelta, timezone
    from app.models.moderation import UserAccountHistory, ModerationAction
    from app.models.user import RestrictionLevel

    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Prevent banning yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban yourself",
        )

    # Validate duration for non-permanent bans
    if not request.permanent and not request.duration_hours:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify duration_hours for non-permanent ban",
        )

    # Apply ban
    now = datetime.now(timezone.utc)
    user.restriction_level = RestrictionLevel.BANNED.value
    user.restriction_reason = request.reason
    user.restriction_expires_at = (
        None if request.permanent else now + timedelta(hours=request.duration_hours)
    )
    user.restricted_by_id = admin.id
    user.restricted_at = now
    user.user_warnings += 1

    # Create history record
    history = UserAccountHistory.add_ban(
        user_id=user.id,
        actor_id=admin.id,
        reason=request.reason,
        permanent=request.permanent,
        duration_hours=request.duration_hours,
        admin_notes=request.admin_notes,
    )
    db.add(history)

    await db.commit()

    duration_msg = "permanently" if request.permanent else f"for {request.duration_hours} hours"
    logger.info(
        "user_banned",
        user_id=str(user_id),
        admin_id=str(admin.id),
        permanent=request.permanent,
        duration_hours=request.duration_hours,
        reason=request.reason,
    )

    return ModerationActionResponse(
        success=True,
        message=f"User banned {duration_msg}",
        action="ban",
    )


@router.post(
    "/users/{user_id}/remove-restriction",
    response_model=ModerationActionResponse,
    summary="Remove all restrictions from a user",
)
async def remove_restriction(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(require_permission(Permission.ROLE_ASSIGN))],
) -> ModerationActionResponse:
    """Remove all restrictions from a user."""
    from datetime import timezone
    from app.models.moderation import UserAccountHistory, ModerationAction
    from app.models.user import RestrictionLevel

    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    if user.restriction_level == RestrictionLevel.NONE.value:
        return ModerationActionResponse(
            success=True,
            message="User has no active restrictions",
            action=None,
        )

    # Determine what action to log
    action_map = {
        RestrictionLevel.SILENCED.value: ModerationAction.UNSILENCE,
        RestrictionLevel.RESTRICTED.value: ModerationAction.UNRESTRICT,
        RestrictionLevel.BANNED.value: ModerationAction.UNBAN,
    }
    log_action = action_map.get(user.restriction_level, ModerationAction.UNRESTRICT)
    old_level = user.restriction_level

    # Remove restrictions
    user.restriction_level = RestrictionLevel.NONE.value
    user.restriction_reason = None
    user.restriction_expires_at = None
    user.restricted_by_id = None
    user.restricted_at = None

    # Create history record
    history = UserAccountHistory(
        user_id=user.id,
        actor_id=admin.id,
        action=log_action,
        reason=f"Restriction removed by admin (was: {old_level})",
    )
    db.add(history)

    await db.commit()

    logger.info(
        "user_restriction_removed",
        user_id=str(user_id),
        admin_id=str(admin.id),
        old_restriction=old_level,
    )

    return ModerationActionResponse(
        success=True,
        message=f"Removed {old_level} from user",
        action=log_action.value,
    )


@router.post(
    "/users/{user_id}/add-note",
    response_model=ModerationActionResponse,
    summary="Add a note to user's account history",
)
async def add_user_note(
    user_id: uuid.UUID,
    request: AddNoteRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> ModerationActionResponse:
    """Add an administrative note to a user's account without any punishment."""
    from app.models.moderation import UserAccountHistory

    # Get the user
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Create history record
    history = UserAccountHistory.add_note(
        user_id=user.id,
        actor_id=admin.id,
        reason=request.note,
        admin_notes=request.admin_notes,
    )
    db.add(history)

    await db.commit()

    logger.info(
        "user_note_added",
        user_id=str(user_id),
        admin_id=str(admin.id),
    )

    return ModerationActionResponse(
        success=True,
        message="Note added to user's account",
        action="note",
    )


# =============================================================================
# AI Training & Re-evaluation Admin Endpoints
# =============================================================================


class TrainingPipelineStatusResponse(BaseModel):
    """Status of the autonomous training pipeline."""

    state: str
    is_enabled: bool
    contributions_since_last_train: int
    min_contributions_threshold: int
    current_model_version: str
    staged_model_version: str | None
    last_training_started: datetime | None
    last_training_completed: datetime | None
    validation_results: dict[str, Any] | None
    canary_status: dict[str, Any] | None


class ReEvaluationStatusResponse(BaseModel):
    """Status of re-evaluation candidates."""

    candidates_count: int
    smart_mode_enabled: bool
    current_model_version: str
    versions_pending_upgrade: list[str]


class TriggerReEvaluationRequest(BaseModel):
    """Request to trigger batch re-evaluation."""

    batch_size: int = 100
    old_model_version: str | None = None
    use_smart_mode: bool = True


class TriggerReEvaluationResponse(BaseModel):
    """Response from triggering re-evaluation."""

    success: bool
    message: str
    jobs_queued: int
    jobs_skipped: int
    errors: list[str]


class TriggerTrainingRequest(BaseModel):
    """Request to manually trigger training."""

    force: bool = False  # Bypass minimum contribution threshold


class TriggerTrainingResponse(BaseModel):
    """Response from triggering training."""

    success: bool
    message: str
    session_id: str | None = None


@router.get(
    "/ai/training/status",
    response_model=TrainingPipelineStatusResponse,
    summary="Get autonomous training pipeline status",
)
async def get_training_status(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> TrainingPipelineStatusResponse:
    """Get the current status of the autonomous training pipeline."""
    from app.services.autonomous_training import AutonomousTrainingPipeline
    from app.config import get_settings

    settings = get_settings()
    pipeline = AutonomousTrainingPipeline(db, settings)
    status = await pipeline.get_status()

    return TrainingPipelineStatusResponse(
        state=status["state"],
        is_enabled=settings.autonomous_training_enabled,
        contributions_since_last_train=status["contributions_since_last_train"],
        min_contributions_threshold=settings.autonomous_training_min_contributions,
        current_model_version=settings.ai_model_version,
        staged_model_version=status.get("staged_model_version"),
        last_training_started=status.get("last_training_started"),
        last_training_completed=status.get("last_training_completed"),
        validation_results=status.get("validation_results"),
        canary_status=status.get("canary_status"),
    )


@router.post(
    "/ai/training/trigger",
    response_model=TriggerTrainingResponse,
    summary="Manually trigger model training",
)
async def trigger_training(
    request: TriggerTrainingRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> TriggerTrainingResponse:
    """Manually trigger the model training pipeline.

    Requires admin permission. Use force=true to bypass the minimum
    contribution threshold check.
    """
    from app.services.autonomous_training import AutonomousTrainingPipeline
    from app.config import get_settings

    settings = get_settings()
    pipeline = AutonomousTrainingPipeline(db, settings)

    try:
        session_id = await pipeline.trigger_training(force=request.force)
        logger.info(
            "admin_triggered_training",
            admin_id=str(admin.id),
            session_id=session_id,
            force=request.force,
        )
        return TriggerTrainingResponse(
            success=True,
            message="Training pipeline triggered successfully",
            session_id=session_id,
        )
    except ValueError as e:
        return TriggerTrainingResponse(
            success=False,
            message=str(e),
            session_id=None,
        )


@router.get(
    "/ai/re-evaluation/status",
    response_model=ReEvaluationStatusResponse,
    summary="Get re-evaluation candidates status",
)
async def get_re_evaluation_status(
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> ReEvaluationStatusResponse:
    """Get the current status of songs pending re-evaluation."""
    from app.services.re_evaluation import ReEvaluationService
    from app.config import get_settings

    settings = get_settings()
    service = ReEvaluationService(db, settings)
    candidates = await service.find_candidates(batch_size=10000)

    # Group by version
    versions = set()
    for c in candidates:
        versions.add(c.current_model_version)

    return ReEvaluationStatusResponse(
        candidates_count=len(candidates),
        smart_mode_enabled=settings.use_smart_reevaluation,
        current_model_version=settings.ai_model_version,
        versions_pending_upgrade=sorted(versions),
    )


@router.post(
    "/ai/re-evaluation/trigger",
    response_model=TriggerReEvaluationResponse,
    summary="Manually trigger batch re-evaluation",
)
async def trigger_re_evaluation(
    request: TriggerReEvaluationRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(RequireAdminDashboard)],
) -> TriggerReEvaluationResponse:
    """Manually trigger re-evaluation of songs processed by older models.

    This will queue AI jobs to re-process songs with the current model version.
    Users who have opted out of automatic re-evaluation will be skipped.
    """
    from app.services.re_evaluation import ReEvaluationService
    from app.config import get_settings

    settings = get_settings()
    service = ReEvaluationService(db, settings)

    result = await service.run_batch_re_evaluation(
        old_model_version=request.old_model_version,
        batch_size=request.batch_size,
        use_smart_mode=request.use_smart_mode,
    )

    logger.info(
        "admin_triggered_re_evaluation",
        admin_id=str(admin.id),
        batch_size=request.batch_size,
        old_model_version=request.old_model_version,
        use_smart_mode=request.use_smart_mode,
        queued=result["queued"],
        skipped=result["skipped"],
    )

    return TriggerReEvaluationResponse(
        success=True,
        message=f"Re-evaluation triggered: {result['queued']} jobs queued",
        jobs_queued=result["queued"],
        jobs_skipped=result["skipped"],
        errors=result.get("errors", []),
    )

