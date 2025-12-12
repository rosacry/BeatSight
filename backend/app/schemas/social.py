"""Schemas for social features - messaging, blocking, reporting."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Enums (mirror the model enums)
# =============================================================================


class ReportType(str, Enum):
    """Types of user reports."""

    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    CHEATING = "cheating"
    IMPERSONATION = "impersonation"
    COPYRIGHT = "copyright"
    OTHER = "other"


class ReportStatus(str, Enum):
    """Status of a user report."""

    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# =============================================================================
# User Search & Profile
# =============================================================================


class UserPublicProfile(BaseModel):
    """Public user profile information."""

    id: UUID
    user_number: int
    display_name: str
    avatar_url: Optional[str] = None
    karma_score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UserSearchResult(BaseModel):
    """Search result item."""

    id: UUID
    user_number: int
    display_name: str
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class UserSearchResponse(BaseModel):
    """Paginated user search response."""

    items: list[UserSearchResult]
    total: int
    page: int
    page_size: int
    has_next: bool


# =============================================================================
# Direct Messaging
# =============================================================================


class MessageCreate(BaseModel):
    """Request to send a message."""

    recipient_id: UUID
    content: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Direct message response."""

    id: UUID
    sender_id: UUID
    recipient_id: UUID
    content: str
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    """Summary of a conversation with another user."""

    partner: UserSearchResult
    last_message: Optional[MessageResponse] = None
    unread_count: int


class ConversationListResponse(BaseModel):
    """List of conversations."""

    items: list[ConversationSummary]


class MessagesResponse(BaseModel):
    """List of messages in a conversation."""

    items: list[MessageResponse]
    has_more: bool


class UnreadCountResponse(BaseModel):
    """Unread message count."""

    count: int


class MarkReadResponse(BaseModel):
    """Response from marking messages as read."""

    marked_count: int


# =============================================================================
# User Blocking
# =============================================================================


class BlockUserRequest(BaseModel):
    """Request to block a user."""

    reason: Optional[str] = Field(None, max_length=500)


class BlockedUserResponse(BaseModel):
    """Blocked user information."""

    id: UUID
    blocked_id: UUID
    blocked_display_name: str
    reason: Optional[str] = None
    created_at: datetime


class BlockedUsersResponse(BaseModel):
    """List of blocked users."""

    items: list[BlockedUserResponse]


class UnblockResponse(BaseModel):
    """Response from unblocking a user."""

    message: str


# =============================================================================
# User Reporting
# =============================================================================


class ReportUserRequest(BaseModel):
    """Request to report a user."""

    report_type: ReportType
    description: str = Field(min_length=10, max_length=2000)


class ReportResponse(BaseModel):
    """User report response."""

    id: UUID
    reporter_id: UUID
    reported_user_id: UUID
    report_type: ReportType
    description: str
    status: ReportStatus
    admin_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReportCreateResponse(BaseModel):
    """Response from creating a report."""

    id: UUID
    message: str


# Admin-only schemas
class AdminReportResponse(BaseModel):
    """Report response for admins with full details."""

    id: UUID
    reporter: UserSearchResult
    reported_user: UserSearchResult
    report_type: ReportType
    description: str
    status: ReportStatus
    admin_notes: Optional[str] = None
    reviewed_by: Optional[UserSearchResult] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class AdminReportsResponse(BaseModel):
    """Paginated reports for admin."""

    items: list[AdminReportResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class AdminUpdateReportRequest(BaseModel):
    """Admin request to update a report."""

    status: ReportStatus
    admin_notes: Optional[str] = Field(None, max_length=2000)


# =============================================================================
# User Friendships (osu!-style)
# =============================================================================


class FriendResponse(BaseModel):
    """Friend/following relationship information."""

    id: UUID
    friend_id: UUID
    friend_display_name: str
    friend_avatar_url: Optional[str] = None
    friend_user_number: int
    is_mutual: bool  # True if both users have added each other
    created_at: datetime


class FriendsListResponse(BaseModel):
    """List of friends/following."""

    items: list[FriendResponse]
    total: int


class AddFriendResponse(BaseModel):
    """Response from adding a friend."""

    id: UUID
    friend_id: UUID
    is_mutual: bool
    message: str


class RemoveFriendResponse(BaseModel):
    """Response from removing a friend."""

    message: str


class FriendshipStatusResponse(BaseModel):
    """Check friendship status between current user and target user."""

    is_following: bool  # Current user follows target
    is_followed_by: bool  # Target follows current user
    is_mutual: bool  # Both follow each other


# =============================================================================
# User Subscriptions (Bell notifications)
# =============================================================================


class SubscriptionResponse(BaseModel):
    """Subscription to a user's uploads."""

    id: UUID
    target_user_id: UUID
    target_user_display_name: str
    target_user_avatar_url: Optional[str] = None
    target_user_number: int
    notify_on_map_upload: bool
    notify_on_map_ranked: bool
    created_at: datetime


class SubscriptionsListResponse(BaseModel):
    """List of subscriptions."""

    items: list[SubscriptionResponse]
    total: int


class CreateSubscriptionRequest(BaseModel):
    """Request to subscribe to a user."""

    notify_on_map_upload: bool = True
    notify_on_map_ranked: bool = False


class UpdateSubscriptionRequest(BaseModel):
    """Request to update subscription preferences."""

    notify_on_map_upload: Optional[bool] = None
    notify_on_map_ranked: Optional[bool] = None


class CreateSubscriptionResponse(BaseModel):
    """Response from creating a subscription."""

    id: UUID
    target_user_id: UUID
    message: str


class RemoveSubscriptionResponse(BaseModel):
    """Response from removing a subscription."""

    message: str


class SubscriptionStatusResponse(BaseModel):
    """Check if subscribed to a user."""

    is_subscribed: bool
    notify_on_map_upload: bool
    notify_on_map_ranked: bool
