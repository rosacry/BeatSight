"""
Session verification model for sensitive action verification.

Implements osu!-style session verification where users must verify their identity
via email code or link before accessing sensitive areas like settings, credit balances,
etc. after a period of inactivity.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from .user import User


# Constants for verification
VERIFICATION_CODE_LENGTH = 8  # 8 hex characters (e.g., "b8672ff1")
VERIFICATION_CODE_EXPIRY_MINUTES = 15  # Code expires after 15 minutes
VERIFICATION_LINK_EXPIRY_MINUTES = 15  # Link expires after 15 minutes
SESSION_VERIFICATION_TIMEOUT_MINUTES = 30  # Session verified state expires after 30 minutes of inactivity
MAX_VERIFICATION_ATTEMPTS = 5  # Max wrong attempts before new code issued


class SessionVerification(Base):
    """
    Tracks session verification state for sensitive actions.
    
    Similar to osu!'s session verification, this requires users to verify
    via email when accessing settings or other sensitive areas.
    """

    __tablename__ = "session_verifications"

    __table_args__ = (
        Index("ix_session_verifications_user_id", "user_id"),
        Index("ix_session_verifications_session_token", "session_token"),
        Index("ix_session_verifications_link_key", "link_key"),
        Index("ix_session_verifications_verification_code", "verification_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    # The user this verification is for
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    
    # Session identifier (JWT token hash or session ID)
    # This links the verification to a specific session/device
    session_token: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Verification code sent via email (8 hex chars like osu!)
    verification_code: Mapped[str | None] = mapped_column(String(16))
    
    # Unique key for verification link (longer, URL-safe)
    link_key: Mapped[str | None] = mapped_column(String(128))
    
    # Whether the session has been verified
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # When the verification code/link was issued
    code_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # When the session was verified
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Number of failed verification attempts (for rate limiting)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    
    # Country/region where verification was requested (for security awareness)
    request_country: Mapped[str | None] = mapped_column(String(64))
    
    # IP address where verification was requested
    request_ip: Mapped[str | None] = mapped_column(String(64))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="session_verifications")

    @classmethod
    def generate_code(cls) -> str:
        """Generate a random 8-character hex verification code (like osu!)."""
        return secrets.token_hex(4)  # 4 bytes = 8 hex chars

    @classmethod
    def generate_link_key(cls) -> str:
        """Generate a URL-safe link key for email verification link."""
        return secrets.token_urlsafe(48)  # Long enough for security

    def is_code_expired(self) -> bool:
        """Check if the verification code has expired."""
        if self.code_issued_at is None:
            return True
        expiry = self.code_issued_at + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)
        return datetime.now(timezone.utc) > expiry

    def is_session_verification_expired(self) -> bool:
        """Check if the session's verified state has expired due to inactivity."""
        if not self.is_verified or self.verified_at is None:
            return True
        expiry = self.verified_at + timedelta(minutes=SESSION_VERIFICATION_TIMEOUT_MINUTES)
        return datetime.now(timezone.utc) > expiry

    def issue_new_code(self) -> tuple[str, str]:
        """
        Issue a new verification code and link key.
        Returns (code, link_key) tuple.
        """
        self.verification_code = self.generate_code()
        self.link_key = self.generate_link_key()
        self.code_issued_at = datetime.now(timezone.utc)
        self.failed_attempts = 0
        return (self.verification_code, self.link_key)

    def verify_code(self, submitted_code: str) -> bool:
        """
        Verify a submitted code.
        Returns True if code matches and is valid.
        """
        # Normalize: remove spaces, lowercase
        normalized = submitted_code.replace(" ", "").lower()
        
        if self.is_code_expired():
            return False
        
        if self.verification_code and self.verification_code.lower() == normalized:
            self.is_verified = True
            self.verified_at = datetime.now(timezone.utc)
            return True
        
        # Track failed attempt
        self.failed_attempts += 1
        return False

    def verify_link(self, submitted_key: str) -> bool:
        """
        Verify a submitted link key.
        Returns True if key matches and is valid.
        """
        if self.is_code_expired():
            return False
        
        if self.link_key and self.link_key == submitted_key:
            self.is_verified = True
            self.verified_at = datetime.now(timezone.utc)
            return True
        
        return False

    def mark_verified(self) -> None:
        """Mark this session as verified."""
        self.is_verified = True
        self.verified_at = datetime.now(timezone.utc)
        # Clear sensitive data
        self.verification_code = None
        self.link_key = None

    def requires_reissue(self) -> bool:
        """Check if too many failed attempts require reissuing the code."""
        return self.failed_attempts >= MAX_VERIFICATION_ATTEMPTS


class SensitiveActionLog(Base):
    """
    Audit log for sensitive actions that required verification.
    Useful for security review and debugging.
    """

    __tablename__ = "sensitive_action_logs"

    __table_args__ = (
        Index("ix_sensitive_action_logs_user_id", "user_id"),
        Index("ix_sensitive_action_logs_action_type", "action_type"),
        Index("ix_sensitive_action_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    
    # Type of sensitive action (e.g., "settings_access", "credit_view", "password_change")
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    
    # Additional details about the action
    action_details: Mapped[str | None] = mapped_column(Text)
    
    # Whether verification was required
    verification_required: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # How the user verified (code, link, totp, or skip if already verified)
    verification_method: Mapped[str | None] = mapped_column(String(32))
    
    # IP and location info
    ip_address: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
