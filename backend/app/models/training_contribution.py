"""Training contribution model for collaborative beatmap refinement.

This module implements the data collection infrastructure for the collaborative
beatmap refinement feature. User corrections to AI-generated beatmaps can be
contributed back to improve the model (with user consent).

The workflow is:
1. AI generates beatmap with confidence scores per onset
2. Users fix errors in low-confidence sections
3. Corrections (with consent) are submitted as training contributions
4. Verifiers review high-impact corrections
5. Approved contributions are exported for model training
6. Model improves over time from community corrections
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false as sa_false,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .map_version import MapVersion
    from .user import User


class ContributionStatus(str, enum.Enum):
    """State of a training contribution."""

    PENDING = "pending"  # Awaiting verifier review
    APPROVED = "approved"  # Verifier approved for training
    REJECTED = "rejected"  # Verifier rejected (spam, incorrect, etc.)
    EXPORTED = "exported"  # Already exported to training data


class CorrectionType(str, enum.Enum):
    """Type of correction made."""

    COMPONENT_CHANGE = "component_change"  # e.g., snare -> hi-hat
    TIMING_ADJUSTMENT = "timing_adjustment"  # Onset time shifted
    NOTE_ADDITION = "note_addition"  # Missing note added
    NOTE_REMOVAL = "note_removal"  # False positive removed
    VELOCITY_CHANGE = "velocity_change"  # Hit strength adjusted


class TrainingContribution(Base):
    """User correction submitted for model training improvement.

    Each contribution represents a single onset correction - changing
    the component type, adjusting timing, or adding/removing notes.

    Quality gates:
    - User must have consent_to_training enabled
    - User must meet minimum karma threshold (configurable)
    - High-impact corrections require verifier approval
    - Statistical validation rejects outliers
    """

    __tablename__ = "training_contributions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Who made the contribution
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Which beatmap version
    map_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("map_versions.id", ondelete="CASCADE"),
        index=True,
    )

    # Correction details
    onset_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    correction_type: Mapped[CorrectionType] = mapped_column(
        SAEnum(CorrectionType), nullable=False
    )

    # Original AI prediction
    original_component: Mapped[str] = mapped_column(String(50), nullable=False)
    original_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # User's correction
    corrected_component: Mapped[str] = mapped_column(String(50), nullable=False)
    corrected_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    corrected_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # User's explanation (optional but encouraged)
    correction_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Review status
    status: Mapped[ContributionStatus] = mapped_column(
        SAEnum(ContributionStatus),
        default=ContributionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Verifier review (if required)
    verifier_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    verifier_notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Training export tracking
    exported_to_training: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    exported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    export_batch_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="training_contributions"
    )
    verifier: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verifier_id],
    )
    map_version: Mapped["MapVersion"] = relationship(
        "MapVersion", back_populates="training_contributions"
    )

    # Constraints
    __table_args__ = (
        # Prevent duplicate corrections for same onset by same user
        UniqueConstraint(
            "map_version_id",
            "onset_time_ms",
            "user_id",
            name="uq_contribution_per_onset",
        ),
        # Index for pending review queue
        Index(
            "idx_contributions_pending_review",
            "status",
            postgresql_where=(status == ContributionStatus.PENDING),
        ),
        # Index for export queue
        Index(
            "idx_contributions_export_ready",
            "exported_to_training",
            "status",
            postgresql_where=(
                (exported_to_training == sa_false())
                & (status == ContributionStatus.APPROVED)
            ),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TrainingContribution {self.id} "
            f"{self.original_component}->{self.corrected_component} "
            f"@{self.onset_time_ms}ms status={self.status.value}>"
        )


class ContributionBatchImpact(Base):
    """Tracks the measured impact of a contribution batch on model accuracy.

    When contributions are exported and used for training, this table records
    the before/after accuracy metrics to measure their impact.
    """

    __tablename__ = "contribution_batch_impacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Batch identification
    batch_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    # Sample counts
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Accuracy metrics (before and after training)
    baseline_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    post_training_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_delta: Mapped[float] = mapped_column(Float, nullable=False)

    baseline_top3_accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    post_training_top3_accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    top3_accuracy_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Calibration error (lower is better)
    baseline_calibration_error: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    post_training_calibration_error: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    # Per-class impact (JSON serialized)
    per_class_deltas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    most_improved_classes: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )
    most_degraded_classes: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True
    )

    # Efficiency metric (accuracy gain per 1000 samples)
    contribution_efficiency: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # Model versions
    baseline_model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    post_training_model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Timestamps
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<ContributionBatchImpact batch={self.batch_id} "
            f"delta={self.accuracy_delta:+.4f} samples={self.sample_count}>"
        )


class ContributionConsent(Base):
    """User consent settings for training contributions.

    Tracks whether a user has opted in to contributing their corrections
    to model training, along with any preferences about how their
    contributions are used.
    """

    __tablename__ = "contribution_consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Main consent toggle
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Granular preferences
    allow_anonymous_export: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="If true, contributions exported without user attribution",
    )
    allow_public_credit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="If true, user can be credited in release notes/acknowledgments",
    )

    # Timestamps
    consented_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="contribution_consent")

    def __repr__(self) -> str:
        status = "consented" if self.consent_given else "not consented"
        return f"<ContributionConsent user={self.user_id} {status}>"
