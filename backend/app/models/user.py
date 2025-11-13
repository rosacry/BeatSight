"""User and authentication related models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from .ai_job import AIJob
    from .karma import KarmaLedger
    from .map_edit import MapEditProposal, MapVerificationDecision
    from .role import UserRole
    from .song import Song
    from .subscription import Subscription


class User(Base):
    """Represents an account that can interact with the BeatSight platform."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone_number: Mapped[str | None] = mapped_column(String(32))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_provider_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    karma_score: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    karma_events: Mapped[list["KarmaLedger"]] = relationship(
        "KarmaLedger", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user")
    ai_jobs: Mapped[list["AIJob"]] = relationship("AIJob", back_populates="requester")
    map_edits: Mapped[list["MapEditProposal"]] = relationship("MapEditProposal", back_populates="proposer")
    verification_decisions: Mapped[list["MapVerificationDecision"]] = relationship(
        "MapVerificationDecision", back_populates="verifier"
    )
    songs: Mapped[list["Song"]] = relationship("Song", back_populates="creator")
