"""Phone verification models.

Stores pending phone verification codes with expiry and attempt tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .user import User


class PhoneVerificationCode(Base):
    """Stores pending phone verification codes.
    
    Each user can have at most one pending verification code at a time.
    Codes expire after a configurable TTL (default 10 minutes).
    """

    __tablename__ = "phone_verification_codes"

    __table_args__ = (
        # Index for looking up codes by user
        Index("ix_phone_verification_codes_user_id", "user_id"),
        # Index for cleanup of expired codes
        Index("ix_phone_verification_codes_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Phone number in E.164 format"
    )
    code_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Hashed verification code"
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, comment="Number of verification attempts"
    )
    is_used: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Whether code has been successfully used"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="When the code expires"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="phone_verification_codes")


class PhoneVerificationAttempt(Base):
    """Tracks phone verification attempts for rate limiting.
    
    Used to prevent abuse of the SMS sending endpoint.
    """

    __tablename__ = "phone_verification_attempts"

    __table_args__ = (
        # Index for rate limiting queries
        Index("ix_phone_verification_attempts_user_created", "user_id", "created_at"),
        Index("ix_phone_verification_attempts_phone_created", "phone_number", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Phone number attempted"
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), comment="IP address of the request"
    )
    success: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="Whether verification succeeded"
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(128), comment="Reason for failure if applicable"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
