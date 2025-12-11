"""Social API routes - messaging, blocking, reporting, user search."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db_session
from app.models.social import ReportStatus as ModelReportStatus
from app.models.social import ReportType as ModelReportType
from app.models.user import User
from app.schemas.social import (
    AdminReportResponse,
    AdminReportsResponse,
    AdminUpdateReportRequest,
    BlockedUserResponse,
    BlockedUsersResponse,
    BlockUserRequest,
    ConversationListResponse,
    ConversationSummary,
    MarkReadResponse,
    MessageCreate,
    MessageResponse,
    MessagesResponse,
    ReportCreateResponse,
    ReportResponse,
    ReportStatus,
    ReportType,
    ReportUserRequest,
    UnblockResponse,
    UnreadCountResponse,
    UserPublicProfile,
    UserSearchResponse,
    UserSearchResult,
)
from app.services.social import (
    AlreadyBlockedError,
    BlockedUserError,
    DuplicateReportError,
    NotBlockedError,
    ReportNotFoundError,
    SelfActionError,
    SocialService,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["social"])


def get_social_service(db: AsyncSession = Depends(get_db_session)) -> SocialService:
    """Dependency for SocialService."""
    return SocialService(db)


# =============================================================================
# User Search & Profiles
# =============================================================================


@router.get("/users/search", response_model=UserSearchResponse)
async def search_users(
    q: str = Query(min_length=1, max_length=100, description="Search query"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> UserSearchResponse:
    """Search for users by username.

    Returns users matching the search query, excluding blocked users.
    """
    offset = (page - 1) * page_size
    users, total = await service.search_users(
        query=q,
        current_user_id=current_user.id,
        limit=page_size,
        offset=offset,
    )

    return UserSearchResponse(
        items=[UserSearchResult.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + len(users)) < total,
    )


@router.get("/users/{user_id}", response_model=UserPublicProfile)
async def get_user_profile(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> UserPublicProfile:
    """Get a user's public profile.

    Returns 404 if user is blocked or doesn't exist.
    """
    try:
        user = await service.get_user_profile(
            user_id=user_id,
            current_user_id=current_user.id,
        )
        return UserPublicProfile.model_validate(user)
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except BlockedUserError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


# =============================================================================
# Direct Messaging
# =============================================================================


@router.post("/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> MessageResponse:
    """Send a direct message to another user."""
    try:
        message = await service.send_message(
            sender_id=current_user.id,
            recipient_id=request.recipient_id,
            content=request.content,
        )
        return MessageResponse.model_validate(message)
    except SelfActionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message to yourself",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found",
        )
    except BlockedUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot message this user",
        )


@router.get("/messages/conversations", response_model=ConversationListResponse)
async def get_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> ConversationListResponse:
    """Get list of conversations for the current user.

    Returns conversation summaries with the last message and unread count.
    """
    offset = (page - 1) * page_size
    conversations = await service.get_conversations(
        user_id=current_user.id,
        limit=page_size,
        offset=offset,
    )

    items = []
    for conv in conversations:
        partner_data = UserSearchResult.model_validate(conv['partner'])
        last_msg = (
            MessageResponse.model_validate(conv['last_message'])
            if conv['last_message']
            else None
        )
        items.append(
            ConversationSummary(
                partner=partner_data,
                last_message=last_msg,
                unread_count=conv['unread_count'],
            )
        )

    return ConversationListResponse(items=items)


@router.get("/messages/{partner_id}", response_model=MessagesResponse)
async def get_messages(
    partner_id: UUID,
    before_id: Optional[UUID] = Query(default=None, description="Get messages before this ID"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> MessagesResponse:
    """Get messages with a specific user."""
    messages = await service.get_messages(
        user_id=current_user.id,
        partner_id=partner_id,
        limit=limit + 1,  # Fetch one extra to check if there are more
        before_id=before_id,
    )

    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]

    return MessagesResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        has_more=has_more,
    )


@router.post("/messages/{partner_id}/read", response_model=MarkReadResponse)
async def mark_messages_read(
    partner_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> MarkReadResponse:
    """Mark all messages from a user as read."""
    count = await service.mark_messages_read(
        user_id=current_user.id,
        partner_id=partner_id,
    )
    return MarkReadResponse(marked_count=count)


@router.get("/messages/unread/count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> UnreadCountResponse:
    """Get total unread message count."""
    count = await service.get_unread_count(current_user.id)
    return UnreadCountResponse(count=count)


# =============================================================================
# User Blocking
# =============================================================================


@router.post("/users/{user_id}/block", response_model=BlockedUserResponse, status_code=status.HTTP_201_CREATED)
async def block_user(
    user_id: UUID,
    request: BlockUserRequest,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
    db: AsyncSession = Depends(get_db_session),
) -> BlockedUserResponse:
    """Block a user.

    Blocked users cannot:
    - Send you messages
    - See your profile
    - Appear in your search results
    """
    try:
        block = await service.block_user(
            blocker_id=current_user.id,
            blocked_id=user_id,
            reason=request.reason,
        )
        
        # Get blocked user info
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        blocked_user = result.scalar_one()
        
        return BlockedUserResponse(
            id=block.id,
            blocked_id=user_id,
            blocked_display_name=blocked_user.display_name,
            reason=block.reason,
            created_at=block.created_at,
        )
    except SelfActionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block yourself",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except AlreadyBlockedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already blocked",
        )


@router.delete("/users/{user_id}/block", response_model=UnblockResponse)
async def unblock_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> UnblockResponse:
    """Unblock a user."""
    try:
        await service.unblock_user(
            blocker_id=current_user.id,
            blocked_id=user_id,
        )
        return UnblockResponse(message="User unblocked successfully")
    except NotBlockedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not blocked",
        )


@router.get("/blocked", response_model=BlockedUsersResponse)
async def get_blocked_users(
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> BlockedUsersResponse:
    """Get list of users you've blocked."""
    blocks = await service.get_blocked_users(current_user.id)
    
    items = []
    for block in blocks:
        items.append(
            BlockedUserResponse(
                id=block.id,
                blocked_id=block.blocked_id,
                blocked_display_name=block.blocked.display_name,
                reason=block.reason,
                created_at=block.created_at,
            )
        )
    
    return BlockedUsersResponse(items=items)


# =============================================================================
# User Reporting
# =============================================================================


@router.post("/users/{user_id}/report", response_model=ReportCreateResponse, status_code=status.HTTP_201_CREATED)
async def report_user(
    user_id: UUID,
    request: ReportUserRequest,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> ReportCreateResponse:
    """Report a user for admin review.

    Reports are reviewed by administrators. You can only have one pending
    report per user at a time.
    """
    try:
        # Convert schema enum to model enum
        model_report_type = ModelReportType(request.report_type.value)
        
        report = await service.report_user(
            reporter_id=current_user.id,
            reported_user_id=user_id,
            report_type=model_report_type,
            description=request.description,
        )
        return ReportCreateResponse(
            id=report.id,
            message="Report submitted successfully. Our team will review it.",
        )
    except SelfActionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot report yourself",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except DuplicateReportError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending report for this user",
        )


# =============================================================================
# Admin Routes (Reports Management)
# =============================================================================


@router.get("/admin/reports", response_model=AdminReportsResponse)
async def get_reports_admin(
    status_filter: Optional[ReportStatus] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> AdminReportsResponse:
    """Get user reports (admin only).

    Optionally filter by status.
    """
    # Check if user is admin
    # Simple admin check - you may want to use your RBAC system
    is_admin = any(role.name == "admin" for role in current_user.roles) if current_user.roles else False
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    # Convert schema enum to model enum if provided
    model_status = ModelReportStatus(status_filter.value) if status_filter else None

    offset = (page - 1) * page_size
    reports, total = await service.get_reports(
        status=model_status,
        limit=page_size,
        offset=offset,
    )

    items = []
    for report in reports:
        items.append(
            AdminReportResponse(
                id=report.id,
                reporter=UserSearchResult.model_validate(report.reporter),
                reported_user=UserSearchResult.model_validate(report.reported_user),
                report_type=ReportType(report.report_type.value),
                description=report.description,
                status=ReportStatus(report.status.value),
                admin_notes=report.admin_notes,
                reviewed_by=(
                    UserSearchResult.model_validate(report.reviewed_by)
                    if report.reviewed_by
                    else None
                ),
                created_at=report.created_at,
                reviewed_at=report.reviewed_at,
            )
        )

    return AdminReportsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + len(reports)) < total,
    )


@router.get("/admin/reports/{report_id}", response_model=AdminReportResponse)
async def get_report_admin(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> AdminReportResponse:
    """Get a single report by ID (admin only)."""
    # Check if user is admin
    is_admin = any(role.name == "admin" for role in current_user.roles) if current_user.roles else False
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        report = await service.get_report_by_id(report_id)
        return AdminReportResponse(
            id=report.id,
            reporter=UserSearchResult.model_validate(report.reporter),
            reported_user=UserSearchResult.model_validate(report.reported_user),
            report_type=ReportType(report.report_type.value),
            description=report.description,
            status=ReportStatus(report.status.value),
            admin_notes=report.admin_notes,
            reviewed_by=(
                UserSearchResult.model_validate(report.reviewed_by)
                if report.reviewed_by
                else None
            ),
            created_at=report.created_at,
            reviewed_at=report.reviewed_at,
        )
    except ReportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )


@router.patch("/admin/reports/{report_id}", response_model=AdminReportResponse)
async def update_report_admin(
    report_id: UUID,
    request: AdminUpdateReportRequest,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> AdminReportResponse:
    """Update a report's status (admin only)."""
    # Check if user is admin
    is_admin = any(role.name == "admin" for role in current_user.roles) if current_user.roles else False
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    try:
        # Convert schema enum to model enum
        model_status = ModelReportStatus(request.status.value)
        
        report = await service.update_report_status(
            report_id=report_id,
            admin_id=current_user.id,
            status=model_status,
            admin_notes=request.admin_notes,
        )
        
        # Refresh to get relationships
        report = await service.get_report_by_id(report_id)
        
        return AdminReportResponse(
            id=report.id,
            reporter=UserSearchResult.model_validate(report.reporter),
            reported_user=UserSearchResult.model_validate(report.reported_user),
            report_type=ReportType(report.report_type.value),
            description=report.description,
            status=ReportStatus(report.status.value),
            admin_notes=report.admin_notes,
            reviewed_by=(
                UserSearchResult.model_validate(report.reviewed_by)
                if report.reviewed_by
                else None
            ),
            created_at=report.created_at,
            reviewed_at=report.reviewed_at,
        )
    except ReportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
