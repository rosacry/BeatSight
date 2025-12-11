"""Social interaction models for user messaging, blocking, and reporting.

Provides:
- Direct messages between users
- User blocking functionality
- User reporting system (reports go to admin panel)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text, Boolean, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


# =============================================================================
# Direct Messages
# =============================================================================


class DirectMessage(Base):
    """Direct message between users."""

    __tablename__ = "direct_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Sender (null if system message or deleted user)
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Recipient
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Message content
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Read status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft delete flags (for sender/recipient)
    deleted_by_sender: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_by_recipient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Reply tracking (for conversation threading)
    reply_to_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("direct_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="sent_messages",
        foreign_keys=[sender_id],
    )
    recipient: Mapped["User"] = relationship(
        "User",
        back_populates="received_messages",
        foreign_keys=[recipient_id],
    )
    reply_to: Mapped[Optional["DirectMessage"]] = relationship(
        "DirectMessage",
        remote_side=[id],
        foreign_keys=[reply_to_id],
    )

    __table_args__ = (
        Index("ix_direct_messages_recipient_created", "recipient_id", "created_at"),
        Index("ix_direct_messages_sender_created", "sender_id", "created_at"),
    )


# =============================================================================
# User Blocks
# =============================================================================


class UserBlock(Base):
    """Represents a user blocking another user.
    
    When user A blocks user B:
    - B cannot send messages to A
    - B's content may be hidden from A
    - B cannot see A's profile (optional)
    """

    __tablename__ = "user_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # The user who initiated the block
    blocker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The user being blocked
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Optional reason (for user's reference)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    blocker: Mapped["User"] = relationship(
        "User",
        back_populates="blocks_given",
        foreign_keys=[blocker_id],
    )
    blocked: Mapped["User"] = relationship(
        "User",
        back_populates="blocks_received",
        foreign_keys=[blocked_id],
    )

    __table_args__ = (
        Index("ix_user_blocks_blocker_blocked", "blocker_id", "blocked_id", unique=True),
    )


# =============================================================================
# User Reports
# =============================================================================


class ReportType(str, enum.Enum):
    """Standard report reasons."""
    
    SPAM = "spam"
    HARASSMENT = "harassment"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    CHEATING = "cheating"
    IMPERSONATION = "impersonation"
    COPYRIGHT = "copyright"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    """Report processing status."""
    
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class UserReport(Base):
    """Report of a user submitted by another user.
    
    Reports are sent to the admin panel for review and action.
    """

    __tablename__ = "user_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Who submitted the report
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Who is being reported
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Report details
    report_type: Mapped[ReportType] = mapped_column(
        SAEnum(
            ReportType,
            name="reporttype",
            values_callable=lambda e: [r.value for r in e],
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Processing status
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(
            ReportStatus,
            name="reportstatus",
            values_callable=lambda e: [s.value for s in e],
        ),
        default=ReportStatus.PENDING,
        nullable=False,
    )

    # Admin who reviewed the report
    reviewed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Admin's notes
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    reporter: Mapped["User"] = relationship(
        "User",
        back_populates="reports_submitted",
        foreign_keys=[reporter_id],
    )
    reported_user: Mapped["User"] = relationship(
        "User",
        back_populates="reports_received",
        foreign_keys=[reported_user_id],
    )
    reviewed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewed_by_id],
    )

    __table_args__ = (
        Index("ix_user_reports_status_created", "status", "created_at"),
    )
