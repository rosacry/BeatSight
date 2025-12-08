"""User and authentication related models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
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
    from .push_subscription import PushSubscription
    from .role import UserRole
    from .song import Song
    from .subscription import Subscription
    from .training_contribution import ContributionConsent, TrainingContribution


class User(Base):
    """Represents an account that can interact with the BeatSight platform."""

    __tablename__ = "users"

    # Index for karma leaderboard queries (ORDER BY karma_score DESC)
    # and rank calculation (COUNT WHERE karma_score > x)
    __table_args__ = (Index("ix_users_karma_score", "karma_score"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
