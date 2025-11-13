"""Map edit proposal and verification decision models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .map_version import MapVersion
    from .user import User


class EditStatus(str, Enum):  # type: ignore[misc]
    """State of a map edit proposal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class VerificationDecision(str, Enum):  # type: ignore[misc]
    """Possible decision outcomes for a verification."""

    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_CHANGES = "needs_changes"


class MapEditProposal(Base):
    """User-submitted adjustments to a map version."""

    __tablename__ = "map_edit_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_versions.id", ondelete="CASCADE")
    )
    proposer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    summary: Mapped[str] = mapped_column(String(255))
    diff_payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[EditStatus] = mapped_column(Enum(EditStatus), default=EditStatus.PENDING, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    map_version: Mapped["MapVersion"] = relationship("MapVersion", back_populates="edit_proposals")
    proposer: Mapped["User"] = relationship("User", back_populates="map_edits")
    decision: Mapped["MapVerificationDecision" | None] = relationship(
        "MapVerificationDecision", back_populates="proposal", uselist=False, cascade="all, delete-orphan"
    )


class MapVerificationDecision(Base):
    """Verifier decision for a map edit."""

    __tablename__ = "map_verification_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("map_edit_proposals.id", ondelete="CASCADE"), unique=True
    )
    verifier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decision: Mapped[VerificationDecision] = mapped_column(Enum(VerificationDecision), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(512))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    proposal: Mapped[MapEditProposal] = relationship("MapEditProposal", back_populates="decision")
    verifier: Mapped["User"] = relationship("User", back_populates="verification_decisions")
