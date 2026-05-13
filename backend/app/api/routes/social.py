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
    ReportStatus,
    ReportType,
    ReportUserRequest,
    UnblockResponse,
    UnreadCountResponse,
    UserPublicProfile,
    UserSearchResponse,
    UserSearchResult,
    # Friend schemas
    FriendResponse,
    FriendsListResponse,
    AddFriendResponse,
    RemoveFriendResponse,
    FriendshipStatusResponse,
    # Subscription schemas
    SubscriptionResponse,
    SubscriptionsListResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    RemoveSubscriptionResponse,
    SubscriptionStatusResponse,
    UpdateSubscriptionRequest,
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
    # Friend/subscription errors
    AlreadyFriendsError,
    NotFriendsError,
    AlreadySubscribedError,
    NotSubscribedError,
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
    is_admin = any(ur.role.code == "admin" for ur in current_user.roles if ur.role) if current_user.roles else False
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
    is_admin = any(ur.role.code == "admin" for ur in current_user.roles if ur.role) if current_user.roles else False
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
    is_admin = any(ur.role.code == "admin" for ur in current_user.roles if ur.role) if current_user.roles else False
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


# =============================================================================
# User Friendships (osu!-style)
# =============================================================================


@router.post("/users/{user_id}/friend", response_model=AddFriendResponse, status_code=status.HTTP_201_CREATED)
async def add_friend(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> AddFriendResponse:
    """Add a user as a friend (follow them).

    If the other user also adds you, you become mutual friends.
    """
    try:
        friendship, is_mutual = await service.add_friend(
            user_id=current_user.id,
            friend_id=user_id,
        )
        return AddFriendResponse(
            id=friendship.id,
            friend_id=user_id,
            is_mutual=is_mutual,
            message="Friend added successfully" + (" - You are now mutual friends!" if is_mutual else ""),
        )
    except SelfActionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add yourself as a friend",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except AlreadyFriendsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already following this user",
        )
    except BlockedUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot add this user as a friend",
        )


@router.delete("/users/{user_id}/friend", response_model=RemoveFriendResponse)
async def remove_friend(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> RemoveFriendResponse:
    """Remove a user from friends (unfollow them)."""
    try:
        await service.remove_friend(
            user_id=current_user.id,
            friend_id=user_id,
        )
        return RemoveFriendResponse(message="Friend removed successfully")
    except NotFriendsError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this user",
        )


@router.get("/friends", response_model=FriendsListResponse)
async def get_friends(
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> FriendsListResponse:
    """Get list of users you are following."""
    friends = await service.get_friends(current_user.id)
    return FriendsListResponse(
        items=[FriendResponse(**f) for f in friends],
        total=len(friends),
    )


@router.get("/users/{user_id}/friendship", response_model=FriendshipStatusResponse)
async def get_friendship_status(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> FriendshipStatusResponse:
    """Check friendship status with a user."""
    status_data = await service.get_friendship_status(
        user_id=current_user.id,
        target_user_id=user_id,
    )
    return FriendshipStatusResponse(**status_data)


# =============================================================================
# User Subscriptions (Bell notifications)
# =============================================================================


@router.post("/users/{user_id}/subscribe", response_model=CreateSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_user(
    user_id: UUID,
    request: CreateSubscriptionRequest = CreateSubscriptionRequest(),
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> CreateSubscriptionResponse:
    """Subscribe to notifications when a user uploads new beatmaps.

    Click the bell icon to get notified when this user uploads.
    """
    try:
        subscription = await service.subscribe_to_user(
            subscriber_id=current_user.id,
            target_user_id=user_id,
            notify_on_map_upload=request.notify_on_map_upload,
            notify_on_map_ranked=request.notify_on_map_ranked,
        )
        return CreateSubscriptionResponse(
            id=subscription.id,
            target_user_id=user_id,
            message="Subscribed! You'll be notified when this user uploads new beatmaps.",
        )
    except SelfActionError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot subscribe to yourself",
        )
    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    except AlreadySubscribedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already subscribed to this user",
        )
    except BlockedUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot subscribe to this user",
        )


@router.delete("/users/{user_id}/subscribe", response_model=RemoveSubscriptionResponse)
async def unsubscribe_from_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> RemoveSubscriptionResponse:
    """Unsubscribe from a user's notifications."""
    try:
        await service.unsubscribe_from_user(
            subscriber_id=current_user.id,
            target_user_id=user_id,
        )
        return RemoveSubscriptionResponse(message="Unsubscribed successfully")
    except NotSubscribedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not subscribed to this user",
        )


@router.patch("/users/{user_id}/subscribe", response_model=SubscriptionResponse)
async def update_subscription(
    user_id: UUID,
    request: UpdateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
    db: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Update subscription notification preferences."""
    try:
        subscription = await service.update_subscription(
            subscriber_id=current_user.id,
            target_user_id=user_id,
            notify_on_map_upload=request.notify_on_map_upload,
            notify_on_map_ranked=request.notify_on_map_ranked,
        )
        
        # Get target user info
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        target_user = result.scalar_one()
        
        return SubscriptionResponse(
            id=subscription.id,
            target_user_id=subscription.target_user_id,
            target_user_display_name=target_user.display_name,
            target_user_avatar_url=target_user.avatar_url,
            target_user_number=target_user.user_number,
            notify_on_map_upload=subscription.notify_on_map_upload,
            notify_on_map_ranked=subscription.notify_on_map_ranked,
            created_at=subscription.created_at,
        )
    except NotSubscribedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not subscribed to this user",
        )


@router.get("/subscriptions", response_model=SubscriptionsListResponse)
async def get_subscriptions(
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> SubscriptionsListResponse:
    """Get list of users you are subscribed to."""
    subscriptions = await service.get_subscriptions(current_user.id)
    return SubscriptionsListResponse(
        items=[SubscriptionResponse(**s) for s in subscriptions],
        total=len(subscriptions),
    )


@router.get("/users/{user_id}/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    service: SocialService = Depends(get_social_service),
) -> SubscriptionStatusResponse:
    """Check subscription status for a user."""
    status_data = await service.get_subscription_status(
        subscriber_id=current_user.id,
        target_user_id=user_id,
    )
    return SubscriptionStatusResponse(**status_data)
