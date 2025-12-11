"""Social service for user interactions.

This service handles all social-related operations including:
- Direct messaging between users
- User blocking
- User reporting (sent to admin panel)
- User searching
- Profile visibility checks
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.social import (
    DirectMessage,
    ReportStatus,
    ReportType,
    UserBlock,
    UserReport,
)
from app.models.user import RestrictionLevel, User


# =============================================================================
# Exceptions
# =============================================================================


class SocialError(Exception):
    """Base exception for social operations."""
    pass


class UserNotFoundError(SocialError):
    """User does not exist."""
    pass


class BlockedUserError(SocialError):
    """Action blocked due to user block."""
    pass


class SelfActionError(SocialError):
    """Cannot perform this action on yourself."""
    pass


class MessageNotFoundError(SocialError):
    """Message does not exist."""
    pass


class ReportNotFoundError(SocialError):
    """Report does not exist."""
    pass


class AlreadyBlockedError(SocialError):
    """User is already blocked."""
    pass


class NotBlockedError(SocialError):
    """User is not blocked."""
    pass


class DuplicateReportError(SocialError):
    """A pending report already exists for this user."""
    pass


# =============================================================================
# Social Service
# =============================================================================


class SocialService:
    """Service for handling user social interactions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # User Search
    # =========================================================================

    async def search_users(
        self,
        query: str,
        current_user_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        """Search for users by username.

        Args:
            query: Search query (partial username match)
            current_user_id: Current user's ID (to exclude blocked users)
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Tuple of (users list, total count)
        """
        # Base query - search by display_name (case-insensitive)
        search_pattern = f"%{query.lower()}%"
        
        base_query = select(User).where(
            and_(
                func.lower(User.display_name).like(search_pattern),
                User.restriction_level != RestrictionLevel.BANNED.value,
            )
        )

        # Exclude blocked users if current_user_id provided
        if current_user_id:
            # Get IDs of users who blocked the current user
            blocked_by_subquery = select(UserBlock.blocker_id).where(
                UserBlock.blocked_id == current_user_id
            )
            # Get IDs of users the current user blocked
            blocked_subquery = select(UserBlock.blocked_id).where(
                UserBlock.blocker_id == current_user_id
            )
            
            base_query = base_query.where(
                and_(
                    User.id.notin_(blocked_by_subquery),
                    User.id.notin_(blocked_subquery),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        result = await self.db.execute(
            base_query.order_by(User.display_name).offset(offset).limit(limit)
        )
        users = list(result.scalars().all())

        return users, total

    async def get_user_profile(
        self,
        user_id: UUID,
        current_user_id: Optional[UUID] = None,
    ) -> User:
        """Get a user's public profile.

        Args:
            user_id: User ID to fetch
            current_user_id: Current user's ID (to check block status)

        Returns:
            User object

        Raises:
            UserNotFoundError: If user doesn't exist or is inactive
            BlockedUserError: If user is blocked/has blocked current user
        """
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == user_id,
                    User.restriction_level != RestrictionLevel.BANNED.value,
                )
            )
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")

        # Check block status if viewing as authenticated user
        if current_user_id and current_user_id != user_id:
            if await self.is_blocked(current_user_id, user_id):
                raise BlockedUserError("Cannot view this user's profile")

        return user

    # =========================================================================
    # Direct Messaging
    # =========================================================================

    async def send_message(
        self,
        sender_id: UUID,
        recipient_id: UUID,
        content: str,
    ) -> DirectMessage:
        """Send a direct message to another user.

        Args:
            sender_id: Sender's user ID
            recipient_id: Recipient's user ID
            content: Message content

        Returns:
            Created DirectMessage

        Raises:
            SelfActionError: If trying to message yourself
            UserNotFoundError: If recipient doesn't exist
            BlockedUserError: If either user has blocked the other
        """
        if sender_id == recipient_id:
            raise SelfActionError("Cannot send message to yourself")

        # Verify recipient exists
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.id == recipient_id,
                    User.restriction_level != RestrictionLevel.BANNED.value,
                )
            )
        )
        if not result.scalar_one_or_none():
            raise UserNotFoundError(f"User {recipient_id} not found")

        # Check block status
        if await self.is_blocked(sender_id, recipient_id):
            raise BlockedUserError("Cannot message this user")

        message = DirectMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            content=content,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        return message

    async def get_conversations(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get list of conversations for a user.

        Returns the most recent message from each conversation partner.

        Args:
            user_id: User's ID
            limit: Maximum conversations to return
            offset: Pagination offset

        Returns:
            List of conversation summaries with partner info and last message
        """
        # Subquery to get the latest message ID for each conversation
        # A conversation is identified by the pair of users involved
        
        # Get all unique conversation partners
        sent_partners = select(DirectMessage.recipient_id.label('partner_id')).where(
            DirectMessage.sender_id == user_id
        )
        received_partners = select(DirectMessage.sender_id.label('partner_id')).where(
            DirectMessage.recipient_id == user_id
        )
        
        partners_union = sent_partners.union(received_partners).subquery()
        
        # For each partner, get the most recent message
        conversations = []
        partners_result = await self.db.execute(
            select(partners_union.c.partner_id).offset(offset).limit(limit)
        )
        partner_ids = [row[0] for row in partners_result.fetchall()]
        
        for partner_id in partner_ids:
            # Get partner user
            partner_result = await self.db.execute(
                select(User).where(User.id == partner_id)
            )
            partner = partner_result.scalar_one_or_none()
            if not partner:
                continue
                
            # Get most recent message
            msg_result = await self.db.execute(
                select(DirectMessage)
                .where(
                    or_(
                        and_(
                            DirectMessage.sender_id == user_id,
                            DirectMessage.recipient_id == partner_id,
                        ),
                        and_(
                            DirectMessage.sender_id == partner_id,
                            DirectMessage.recipient_id == user_id,
                        ),
                    )
                )
                .order_by(DirectMessage.created_at.desc())
                .limit(1)
            )
            last_message = msg_result.scalar_one_or_none()
            
            # Count unread messages from this partner
            unread_result = await self.db.execute(
                select(func.count(DirectMessage.id)).where(
                    and_(
                        DirectMessage.sender_id == partner_id,
                        DirectMessage.recipient_id == user_id,
                        DirectMessage.read_at.is_(None),
                    )
                )
            )
            unread_count = unread_result.scalar() or 0
            
            conversations.append({
                'partner': partner,
                'last_message': last_message,
                'unread_count': unread_count,
            })
        
        # Sort by most recent message
        conversations.sort(
            key=lambda c: c['last_message'].created_at if c['last_message'] else datetime.min,
            reverse=True,
        )
        
        return conversations

    async def get_messages(
        self,
        user_id: UUID,
        partner_id: UUID,
        limit: int = 50,
        before_id: Optional[UUID] = None,
    ) -> list[DirectMessage]:
        """Get messages between two users.

        Args:
            user_id: Current user's ID
            partner_id: Conversation partner's ID
            limit: Maximum messages to return
            before_id: Get messages before this message ID (for pagination)

        Returns:
            List of messages (most recent first)
        """
        query = select(DirectMessage).where(
            or_(
                and_(
                    DirectMessage.sender_id == user_id,
                    DirectMessage.recipient_id == partner_id,
                ),
                and_(
                    DirectMessage.sender_id == partner_id,
                    DirectMessage.recipient_id == user_id,
                ),
            )
        )

        if before_id:
            # Get the timestamp of the reference message
            ref_result = await self.db.execute(
                select(DirectMessage.created_at).where(DirectMessage.id == before_id)
            )
            ref_time = ref_result.scalar_one_or_none()
            if ref_time:
                query = query.where(DirectMessage.created_at < ref_time)

        result = await self.db.execute(
            query.order_by(DirectMessage.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def mark_messages_read(
        self,
        user_id: UUID,
        partner_id: UUID,
    ) -> int:
        """Mark all messages from a partner as read.

        Args:
            user_id: Current user's ID (recipient)
            partner_id: Sender's ID

        Returns:
            Number of messages marked as read
        """
        from sqlalchemy import update
        
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(DirectMessage)
            .where(
                and_(
                    DirectMessage.sender_id == partner_id,
                    DirectMessage.recipient_id == user_id,
                    DirectMessage.read_at.is_(None),
                )
            )
            .values(read_at=now)
        )
        await self.db.commit()
        return result.rowcount

    async def get_unread_count(self, user_id: UUID) -> int:
        """Get total unread message count for a user.

        Args:
            user_id: User's ID

        Returns:
            Total unread message count
        """
        result = await self.db.execute(
            select(func.count(DirectMessage.id)).where(
                and_(
                    DirectMessage.recipient_id == user_id,
                    DirectMessage.read_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    # =========================================================================
    # User Blocking
    # =========================================================================

    async def block_user(
        self,
        blocker_id: UUID,
        blocked_id: UUID,
        reason: Optional[str] = None,
    ) -> UserBlock:
        """Block a user.

        Args:
            blocker_id: User doing the blocking
            blocked_id: User being blocked
            reason: Optional reason for blocking

        Returns:
            Created UserBlock

        Raises:
            SelfActionError: If trying to block yourself
            UserNotFoundError: If target user doesn't exist
            AlreadyBlockedError: If user is already blocked
        """
        if blocker_id == blocked_id:
            raise SelfActionError("Cannot block yourself")

        # Verify target user exists
        result = await self.db.execute(
            select(User).where(User.id == blocked_id)
        )
        if not result.scalar_one_or_none():
            raise UserNotFoundError(f"User {blocked_id} not found")

        # Check if already blocked
        existing = await self.db.execute(
            select(UserBlock).where(
                and_(
                    UserBlock.blocker_id == blocker_id,
                    UserBlock.blocked_id == blocked_id,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise AlreadyBlockedError("User is already blocked")

        block = UserBlock(
            blocker_id=blocker_id,
            blocked_id=blocked_id,
            reason=reason,
        )
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)

        return block

    async def unblock_user(
        self,
        blocker_id: UUID,
        blocked_id: UUID,
    ) -> None:
        """Unblock a user.

        Args:
            blocker_id: User doing the unblocking
            blocked_id: User being unblocked

        Raises:
            NotBlockedError: If user is not blocked
        """
        result = await self.db.execute(
            select(UserBlock).where(
                and_(
                    UserBlock.blocker_id == blocker_id,
                    UserBlock.blocked_id == blocked_id,
                )
            )
        )
        block = result.scalar_one_or_none()
        
        if not block:
            raise NotBlockedError("User is not blocked")

        await self.db.delete(block)
        await self.db.commit()

    async def is_blocked(
        self,
        user_id: UUID,
        other_user_id: UUID,
    ) -> bool:
        """Check if there's a block between two users.

        Returns True if either user has blocked the other.

        Args:
            user_id: First user's ID
            other_user_id: Second user's ID

        Returns:
            True if a block exists in either direction
        """
        result = await self.db.execute(
            select(UserBlock).where(
                or_(
                    and_(
                        UserBlock.blocker_id == user_id,
                        UserBlock.blocked_id == other_user_id,
                    ),
                    and_(
                        UserBlock.blocker_id == other_user_id,
                        UserBlock.blocked_id == user_id,
                    ),
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_blocked_users(
        self,
        user_id: UUID,
    ) -> list[UserBlock]:
        """Get list of users blocked by a user.

        Args:
            user_id: Blocker's ID

        Returns:
            List of UserBlock records
        """
        result = await self.db.execute(
            select(UserBlock)
            .where(UserBlock.blocker_id == user_id)
            .options(selectinload(UserBlock.blocked))
            .order_by(UserBlock.created_at.desc())
        )
        return list(result.scalars().all())

    # =========================================================================
    # User Reporting
    # =========================================================================

    async def report_user(
        self,
        reporter_id: UUID,
        reported_user_id: UUID,
        report_type: ReportType,
        description: str,
    ) -> UserReport:
        """Report a user for admin review.

        Args:
            reporter_id: User making the report
            reported_user_id: User being reported
            report_type: Type of report
            description: Description of the issue

        Returns:
            Created UserReport

        Raises:
            SelfActionError: If trying to report yourself
            UserNotFoundError: If target user doesn't exist
            DuplicateReportError: If a pending report already exists
        """
        if reporter_id == reported_user_id:
            raise SelfActionError("Cannot report yourself")

        # Verify target user exists
        result = await self.db.execute(
            select(User).where(User.id == reported_user_id)
        )
        if not result.scalar_one_or_none():
            raise UserNotFoundError(f"User {reported_user_id} not found")

        # Check for existing pending report from same reporter
        existing = await self.db.execute(
            select(UserReport).where(
                and_(
                    UserReport.reporter_id == reporter_id,
                    UserReport.reported_user_id == reported_user_id,
                    UserReport.status == ReportStatus.PENDING,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateReportError(
                "You already have a pending report for this user"
            )

        report = UserReport(
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            report_type=report_type,
            description=description,
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)

        return report

    async def get_reports(
        self,
        status: Optional[ReportStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[UserReport], int]:
        """Get user reports (admin only).

        Args:
            status: Filter by status (None for all)
            limit: Maximum reports to return
            offset: Pagination offset

        Returns:
            Tuple of (reports list, total count)
        """
        query = select(UserReport)
        
        if status:
            query = query.where(UserReport.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results with user relationships
        result = await self.db.execute(
            query.options(
                selectinload(UserReport.reporter),
                selectinload(UserReport.reported_user),
                selectinload(UserReport.reviewed_by),
            )
            .order_by(UserReport.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        reports = list(result.scalars().all())

        return reports, total

    async def update_report_status(
        self,
        report_id: UUID,
        admin_id: UUID,
        status: ReportStatus,
        admin_notes: Optional[str] = None,
    ) -> UserReport:
        """Update a report's status (admin only).

        Args:
            report_id: Report ID
            admin_id: Admin user ID
            status: New status
            admin_notes: Admin notes about the resolution

        Returns:
            Updated UserReport

        Raises:
            ReportNotFoundError: If report doesn't exist
        """
        result = await self.db.execute(
            select(UserReport).where(UserReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise ReportNotFoundError(f"Report {report_id} not found")

        report.status = status
        report.reviewed_by_id = admin_id
        report.reviewed_at = datetime.now(timezone.utc)
        if admin_notes:
            report.admin_notes = admin_notes

        await self.db.commit()
        await self.db.refresh(report)

        return report

    async def get_report_by_id(
        self,
        report_id: UUID,
    ) -> UserReport:
        """Get a single report by ID.

        Args:
            report_id: Report ID

        Returns:
            UserReport object

        Raises:
            ReportNotFoundError: If report doesn't exist
        """
        result = await self.db.execute(
            select(UserReport)
            .where(UserReport.id == report_id)
            .options(
                selectinload(UserReport.reporter),
                selectinload(UserReport.reported_user),
                selectinload(UserReport.reviewed_by),
            )
        )
        report = result.scalar_one_or_none()
        
        if not report:
            raise ReportNotFoundError(f"Report {report_id} not found")

        return report
