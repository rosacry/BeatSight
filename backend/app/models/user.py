"""User and authentication related models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from .achievement import UserAchievement
    from .ai_job import AIJob
    from .credits import CreditBalance, CreditPurchase, CreditTransaction
    from .karma import KarmaLedger
    from .map_accuracy import MapAccuracyVote, UserVerificationBonus
    from .map_edit import MapEditProposal, MapVerificationDecision
    from .map_vote import MapVote
    from .moderation import UserAccountHistory
    from .phone_verification import PhoneVerificationCode
    from .push_subscription import PushSubscription
    from .role import UserRole
    from .social import DirectMessage, UserBlock, UserReport
    from .song import Song
    from .subscription import Subscription
    from .training_contribution import ContributionConsent, TrainingContribution
    from .user_settings import UserSettings
    from .user_tag import UserTag


class RestrictionLevel(str, enum.Enum):
    """User account restriction levels."""
    
    NONE = "none"  # Normal account
    SILENCED = "silenced"  # Cannot post/comment but can play
    RESTRICTED = "restricted"  # Hidden from leaderboards, limited interaction
    BANNED = "banned"  # Full account ban


class User(Base):
    """Represents an account that can interact with the BeatSight platform."""

    __tablename__ = "users"

    # Index for karma leaderboard queries (ORDER BY karma_score DESC)
    # and rank calculation (COUNT WHERE karma_score > x)
    __table_args__ = (
        Index("ix_users_karma_score", "karma_score"),
        Index("ix_users_user_number", "user_number", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Human-friendly numeric ID like osu! (e.g., 9792512 instead of UUID)
    user_number: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512))  # URL to avatar image
    auth_provider_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    karma_score: Mapped[int] = mapped_column(default=0)
    # Timestamp when the current karma_score was first achieved (for tie-breaking on leaderboards)
    karma_score_achieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Account moderation fields (inspired by osu!)
    restriction_level: Mapped[str] = mapped_column(
        String(20), default=RestrictionLevel.NONE.value
    )
    restriction_reason: Mapped[str | None] = mapped_column(String(512))
    restriction_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restricted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    restricted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_warnings: Mapped[int] = mapped_column(Integer, default=0)  # Warning count
    
    # Two-Factor Authentication fields
    totp_secret: Mapped[str | None] = mapped_column(String(64))  # Encrypted TOTP secret
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_backup_codes: Mapped[str | None] = mapped_column(Text)  # JSON array of hashed backup codes
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    karma_events: Mapped[list["KarmaLedger"]] = relationship(
        "KarmaLedger", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user"
    )
    ai_jobs: Mapped[list["AIJob"]] = relationship("AIJob", back_populates="requester")
    map_edits: Mapped[list["MapEditProposal"]] = relationship(
        "MapEditProposal", back_populates="proposer"
    )
    verification_decisions: Mapped[list["MapVerificationDecision"]] = relationship(
        "MapVerificationDecision", back_populates="verifier"
    )
    songs: Mapped[list["Song"]] = relationship("Song", back_populates="creator")
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(
        "PushSubscription", back_populates="user", cascade="all, delete-orphan"
    )
    map_votes: Mapped[list["MapVote"]] = relationship(
        "MapVote", back_populates="user", cascade="all, delete-orphan"
    )

    # Credit system relationships
    credit_balance: Mapped["CreditBalance | None"] = relationship(
        "CreditBalance",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    credit_purchases: Mapped[list["CreditPurchase"]] = relationship(
        "CreditPurchase", back_populates="user", cascade="all, delete-orphan"
    )
    credit_transactions: Mapped[list["CreditTransaction"]] = relationship(
        "CreditTransaction", back_populates="user", cascade="all, delete-orphan"
    )

    # Training contribution relationships
    training_contributions: Mapped[list["TrainingContribution"]] = relationship(
        "TrainingContribution",
        back_populates="user",
        foreign_keys="TrainingContribution.user_id",
        cascade="all, delete-orphan",
    )
    contribution_consent: Mapped["ContributionConsent | None"] = relationship(
        "ContributionConsent",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Achievement relationships
    achievements: Mapped[list["UserAchievement"]] = relationship(
        "UserAchievement", back_populates="user", cascade="all, delete-orphan"
    )

    # Map accuracy verification relationships
    accuracy_votes: Mapped[list["MapAccuracyVote"]] = relationship(
        "MapAccuracyVote", back_populates="verifier", cascade="all, delete-orphan"
    )
    verification_bonus: Mapped["UserVerificationBonus | None"] = relationship(
        "UserVerificationBonus",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Phone verification relationships
    phone_verification_codes: Mapped[list["PhoneVerificationCode"]] = relationship(
        "PhoneVerificationCode", back_populates="user", cascade="all, delete-orphan"
    )

    # Account moderation history
    account_history: Mapped[list["UserAccountHistory"]] = relationship(
        "UserAccountHistory",
        back_populates="user",
        foreign_keys="UserAccountHistory.user_id",
        cascade="all, delete-orphan",
        order_by="desc(UserAccountHistory.created_at)",
    )

    # User settings (privacy, preferences)
    settings: Mapped["UserSettings | None"] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Social: Messages
    sent_messages: Mapped[list["DirectMessage"]] = relationship(
        "DirectMessage",
        back_populates="sender",
        foreign_keys="DirectMessage.sender_id",
        cascade="all, delete-orphan",
    )
    received_messages: Mapped[list["DirectMessage"]] = relationship(
        "DirectMessage",
        back_populates="recipient",
        foreign_keys="DirectMessage.recipient_id",
        cascade="all, delete-orphan",
    )

    # Social: Blocks
    blocks_given: Mapped[list["UserBlock"]] = relationship(
        "UserBlock",
        back_populates="blocker",
        foreign_keys="UserBlock.blocker_id",
        cascade="all, delete-orphan",
    )
    blocks_received: Mapped[list["UserBlock"]] = relationship(
        "UserBlock",
        back_populates="blocked",
        foreign_keys="UserBlock.blocked_id",
        cascade="all, delete-orphan",
    )

    # Social: Reports
    reports_submitted: Mapped[list["UserReport"]] = relationship(
        "UserReport",
        back_populates="reporter",
        foreign_keys="UserReport.reporter_id",
        cascade="all, delete-orphan",
    )
    reports_received: Mapped[list["UserReport"]] = relationship(
        "UserReport",
        back_populates="reported_user",
        foreign_keys="UserReport.reported_user_id",
        cascade="all, delete-orphan",
    )

    # Custom profile tags (like osu!'s DEV, VIP, etc.)
    tags: Mapped[list["UserTag"]] = relationship(
        "UserTag",
        back_populates="user",
        foreign_keys="UserTag.user_id",
        cascade="all, delete-orphan",
        order_by="UserTag.display_order",
    )

    @property
    def is_restricted(self) -> bool:
        """Check if user has any active restriction."""
        if self.restriction_level == RestrictionLevel.NONE.value:
            return False
        # Check if restriction has expired
        if self.restriction_expires_at and self.restriction_expires_at < datetime.now(self.restriction_expires_at.tzinfo):
            return False
        return True

    @property
    def is_banned(self) -> bool:
        """Check if user is fully banned."""
        return self.is_restricted and self.restriction_level == RestrictionLevel.BANNED.value

    @property
    def is_silenced(self) -> bool:
        """Check if user is silenced (cannot post/comment)."""
        return self.is_restricted and self.restriction_level in [
            RestrictionLevel.SILENCED.value,
            RestrictionLevel.RESTRICTED.value,
            RestrictionLevel.BANNED.value,
        ]

    @property
    def can_post(self) -> bool:
        """Check if user can create forum posts/comments."""
        return not self.is_silenced
