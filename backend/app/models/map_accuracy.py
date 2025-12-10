"""Map accuracy verification models for multi-verifier consensus system.

This module implements a community-driven beatmap accuracy verification system
where verified users (email + phone verified) can vote on beatmap accuracy.
A beatmap requires consensus from multiple verifiers to be marked as "accurate".

Design rationale:
- REQUIRED_VERIFIERS = 3: Research on crowdsourcing shows 3 independent reviewers
  achieve ~95% accuracy while balancing community participation practicality.
- Users with both email AND phone verified receive karma bonus to reach threshold.
- Prevents single-point-of-failure in verification quality.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .map_version import MapVersion
    from .user import User


# =============================================================================
# Configuration Constants
# =============================================================================

# Number of verifiers required for consensus
REQUIRED_VERIFIERS_FOR_ACCURACY = 3

# Minimum approval ratio (e.g., 2/3 = 0.67 means 67% must approve)
# Using slightly lower than 2/3 to account for floating point
MIN_APPROVAL_RATIO = 2 / 3  # ~0.6667

# Karma bonus for users with both email and phone verified
VERIFIED_USER_KARMA_BONUS = 200


class AccuracyVoteType(str, enum.Enum):
    """Types of accuracy votes a verifier can cast."""

    ACCURATE = "accurate"  # Beatmap accurately represents the song
    INACCURATE = "inaccurate"  # Beatmap has significant errors
    NEEDS_WORK = "needs_work"  # Beatmap is close but needs improvements
    ABSTAIN = "abstain"  # Verifier cannot make determination


class MapAccuracyStatus(str, enum.Enum):
    """Status of beatmap accuracy verification consensus."""

    PENDING = "pending"  # Not enough votes yet
    VERIFIED = "verified"  # Consensus reached: beatmap is accurate
    DISPUTED = "disputed"  # Conflicting votes, no clear consensus
    REJECTED = "rejected"  # Consensus reached: beatmap is inaccurate
    NEEDS_REVISION = "needs_revision"  # Multiple verifiers say needs work


class MapAccuracyVote(Base):
    """Individual verifier vote on beatmap accuracy.
    
    Each verified user (email + phone) can vote once per map version.
    Votes are weighted equally - no reputation weighting to ensure fairness.
    """

    __tablename__ = "map_accuracy_votes"
    __table_args__ = (
        # Each user can only vote once per map version
        UniqueConstraint("map_version_id", "verifier_id", name="uq_accuracy_vote"),
        # Index for querying votes by map version
        Index("ix_accuracy_votes_map_version", "map_version_id"),
        # Index for querying votes by verifier
        Index("ix_accuracy_votes_verifier", "verifier_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    map_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_versions.id", ondelete="CASCADE")
    )
    verifier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    vote: Mapped[AccuracyVoteType] = mapped_column(
        SAEnum(AccuracyVoteType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    confidence_level: Mapped[int] = mapped_column(
        Integer, default=3, nullable=False
    )  # 1-5 scale: 1=uncertain, 5=very confident
    notes: Mapped[str | None] = mapped_column(
        Text
    )  # Optional explanation for the vote
    timestamp_markers: Mapped[str | None] = mapped_column(
        Text
    )  # JSON: specific timestamps where issues were found
    voted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    map_version: Mapped["MapVersion"] = relationship(
        "MapVersion", back_populates="accuracy_votes"
    )
    verifier: Mapped["User"] = relationship(
        "User", back_populates="accuracy_votes"
    )


class MapAccuracyConsensus(Base):
    """Tracks consensus status for a map version's accuracy verification.
    
    This aggregates votes and determines when consensus has been reached.
    Updated automatically when new votes are cast.
    """

    __tablename__ = "map_accuracy_consensus"
    __table_args__ = (
        Index("ix_accuracy_consensus_status", "status"),
        Index("ix_accuracy_consensus_map_version", "map_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    map_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("map_versions.id", ondelete="CASCADE"),
        unique=True,
    )
    status: Mapped[MapAccuracyStatus] = mapped_column(
        SAEnum(MapAccuracyStatus, values_callable=lambda x: [e.value for e in x]),
        default=MapAccuracyStatus.PENDING,
        nullable=False,
    )
    
    # Vote counts
    total_votes: Mapped[int] = mapped_column(Integer, default=0)
    accurate_votes: Mapped[int] = mapped_column(Integer, default=0)
    inaccurate_votes: Mapped[int] = mapped_column(Integer, default=0)
    needs_work_votes: Mapped[int] = mapped_column(Integer, default=0)
    abstain_votes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Average confidence across all votes
    average_confidence: Mapped[float | None] = mapped_column(default=None)
    
    # When consensus was reached (null if still pending)
    consensus_reached_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    map_version: Mapped["MapVersion"] = relationship(
        "MapVersion", back_populates="accuracy_consensus"
    )


class UserVerificationBonus(Base):
    """Tracks karma bonus awarded to users for email + phone verification.
    
    This is a one-time bonus to bring verified users to the karma threshold
    needed for participating in beatmap verification. Prevents duplicate awards.
    """

    __tablename__ = "user_verification_bonuses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,  # Only one bonus per user ever
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bonus_awarded: Mapped[bool] = mapped_column(Boolean, default=False)
    bonus_amount: Mapped[int] = mapped_column(
        Integer, default=VERIFIED_USER_KARMA_BONUS
    )
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="verification_bonus")
