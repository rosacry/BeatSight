"""Map voting model for community-driven map quality control."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover
    from .song import Map
    from .user import User


class VoteType(int, enum.Enum):
    """Vote direction."""

    DOWNVOTE = -1
    UPVOTE = 1


class MapVote(Base):
    """Tracks user votes on maps for community curation.

    Each user can cast one vote per map. Votes affect:
    - Map visibility/ranking
    - Map creator's karma (via KarmaLedger)
    - Map verification consideration
    """

    __tablename__ = "map_votes"
    __table_args__ = (
        # Each user can only vote once per map
        Index("ix_map_vote_user_map", "user_id", "map_id", unique=True),
        # For efficient vote counting per map
        Index("ix_map_vote_map", "map_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("maps.id", ondelete="CASCADE"), nullable=False
    )
    vote_type: Mapped[VoteType] = mapped_column(SAEnum(VoteType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="map_votes")
    map: Mapped["Map"] = relationship("Map", back_populates="votes")
