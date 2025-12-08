"""User account moderation and history models.

Inspired by osu!'s moderation system, this tracks all moderation actions
taken on user accounts including silences, restrictions, bans, and notes.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .user import User


class ModerationAction(str, enum.Enum):
    """Types of moderation actions that can be taken on an account."""
    
    NOTE = "note"  # Admin note (no punishment)
    SILENCE = "silence"  # Temporary inability to post/comment
    RESTRICTION = "restriction"  # Hidden from leaderboards, limited visibility
    BAN = "ban"  # Full account ban
    UNSILENCE = "unsilence"  # Removal of silence
    UNRESTRICT = "unrestrict"  # Removal of restriction
    UNBAN = "unban"  # Removal of ban


class UserAccountHistory(Base):
    """Tracks all moderation actions taken on a user account.
    
    This provides a full audit trail of moderation decisions,
    similar to osu!'s osu_user_banhistory table.
    """

    __tablename__ = "user_account_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # The user this action was taken against
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    
    # The admin who performed this action
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    action: Mapped[ModerationAction] = mapped_column(
        SAEnum(
            ModerationAction,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    
    # Duration in hours (0 = permanent, null = no duration applicable e.g. notes)
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Reason shown to the user
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Internal admin notes (not shown to user)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Supporting URL (e.g., link to offending content)
    supporting_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="account_history",
        foreign_keys=[user_id],
    )
    actor: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[actor_id],
    )

    @classmethod
    def add_note(
        cls,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        admin_notes: Optional[str] = None,
    ) -> "UserAccountHistory":
        """Create a note entry for a user."""
        return cls(
            user_id=user_id,
            actor_id=actor_id,
            action=ModerationAction.NOTE,
            reason=reason,
            admin_notes=admin_notes,
        )

    @classmethod
    def add_silence(
        cls,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        duration_hours: int,
        reason: str,
        admin_notes: Optional[str] = None,
    ) -> "UserAccountHistory":
        """Create a silence entry for a user."""
        return cls(
            user_id=user_id,
            actor_id=actor_id,
            action=ModerationAction.SILENCE,
            duration_hours=duration_hours,
            reason=reason,
            admin_notes=admin_notes,
        )

    @classmethod
    def add_restriction(
        cls,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        duration_hours: Optional[int],
        reason: str,
        admin_notes: Optional[str] = None,
    ) -> "UserAccountHistory":
        """Create a restriction entry for a user."""
        return cls(
            user_id=user_id,
            actor_id=actor_id,
            action=ModerationAction.RESTRICTION,
            duration_hours=duration_hours,
            reason=reason,
            admin_notes=admin_notes,
        )

    @classmethod
    def add_ban(
        cls,
        user_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
        permanent: bool = False,
        duration_hours: Optional[int] = None,
        admin_notes: Optional[str] = None,
    ) -> "UserAccountHistory":
        """Create a ban entry for a user."""
        return cls(
            user_id=user_id,
            actor_id=actor_id,
            action=ModerationAction.BAN,
            duration_hours=0 if permanent else duration_hours,
            reason=reason,
            admin_notes=admin_notes,
        )

    @property
    def is_permanent(self) -> bool:
        """Check if this action is permanent."""
        return self.duration_hours == 0

    @property
    def action_display(self) -> str:
        """Human-readable action name."""
        return {
            ModerationAction.NOTE: "Note",
            ModerationAction.SILENCE: "Silence",
            ModerationAction.RESTRICTION: "Restriction",
            ModerationAction.BAN: "Ban",
            ModerationAction.UNSILENCE: "Silence Removed",
            ModerationAction.UNRESTRICT: "Restriction Removed",
            ModerationAction.UNBAN: "Ban Removed",
        }.get(self.action, self.action.value.title())
