"""
Session verification service for sensitive action verification.

Implements osu!-style session verification that requires users to verify 
their identity via email code or link before accessing sensitive areas
(settings, credits, etc.) after a period of inactivity.

Key features:
- Session-based verification state (tied to JWT token)
- Email verification codes (8 hex characters like osu!)
- One-click email verification links
- Automatic expiry after inactivity period
- Country/IP tracking for security awareness
- Rate limiting on failed attempts
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session_verification import (
    SensitiveActionLog,
    SessionVerification,
)

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)


class SessionVerificationService:
    """
    Service for managing session verification for sensitive actions.
    
    This implements osu!-style verification where users must verify their
    identity (via email code or link) before accessing sensitive areas.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    def _hash_token(self, token: str) -> str:
        """
        Hash a JWT token to create a session identifier.
        We don't store the full token for security reasons.
        """
        return hashlib.sha256(token.encode()).hexdigest()[:64]

    async def get_or_create_verification(
        self,
        user: "User",
        access_token: str,
        request_ip: str | None = None,
        request_country: str | None = None,
    ) -> SessionVerification:
        """
        Get existing session verification or create a new one.
        
        Args:
            user: The user requesting access
            access_token: The current JWT access token
            request_ip: Client IP address
            request_country: Detected country from IP
            
        Returns:
            SessionVerification object
        """
        session_token = self._hash_token(access_token)
        
        # Look for existing verification for this session
        result = await self.session.execute(
            select(SessionVerification).where(
                and_(
                    SessionVerification.user_id == user.id,
                    SessionVerification.session_token == session_token,
                )
            )
        )
        verification = result.scalar_one_or_none()
        
        if verification is None:
            # Create new verification record
            verification = SessionVerification(
                user_id=user.id,
                session_token=session_token,
                request_ip=request_ip,
                request_country=request_country,
            )
            self.session.add(verification)
            await self.session.flush()
            logger.info(f"Created new session verification for user {user.id}")
        
        return verification

    async def is_session_verified(
        self,
        user: "User",
        access_token: str,
    ) -> bool:
        """
        Check if the current session is verified for sensitive actions.
        
        Returns True if:
        - Session has been verified within the timeout period
        
        Returns False if:
        - Session has never been verified
        - Session verification has expired
        """
        session_token = self._hash_token(access_token)
        
        result = await self.session.execute(
            select(SessionVerification).where(
                and_(
                    SessionVerification.user_id == user.id,
                    SessionVerification.session_token == session_token,
                )
            )
        )
        verification = result.scalar_one_or_none()
        
        if verification is None:
            return False
        
        if not verification.is_verified:
            return False
        
        # Check if verification has expired
        return not verification.is_session_verification_expired()

    async def initiate_verification(
        self,
        user: "User",
        access_token: str,
        request_ip: str | None = None,
        request_country: str | None = None,
    ) -> tuple[str, str, str]:
        """
        Initiate the verification process by generating code and link.
        
        Args:
            user: The user needing verification
            access_token: Current JWT token
            request_ip: Client IP
            request_country: Detected country
            
        Returns:
            Tuple of (verification_code, link_key, obscured_email)
        """
        verification = await self.get_or_create_verification(
            user, access_token, request_ip, request_country
        )
        
        # Issue new code (or reissue if expired/too many attempts)
        code, link_key = verification.issue_new_code()
        verification.request_ip = request_ip
        verification.request_country = request_country
        
        await self.session.commit()
        
        # Obscure email for display (like osu!)
        obscured_email = self._obscure_email(user.email)
        
        logger.info(
            f"Initiated verification for user {user.id} from {request_country or 'unknown'}"
        )
        
        return (code, link_key, obscured_email)

    async def verify_code(
        self,
        user: "User",
        access_token: str,
        submitted_code: str,
    ) -> tuple[bool, str | None]:
        """
        Verify a submitted code.
        
        Args:
            user: The user
            access_token: Current JWT token
            submitted_code: The code submitted by user
            
        Returns:
            Tuple of (success, error_message)
        """
        session_token = self._hash_token(access_token)
        
        result = await self.session.execute(
            select(SessionVerification).where(
                and_(
                    SessionVerification.user_id == user.id,
                    SessionVerification.session_token == session_token,
                )
            )
        )
        verification = result.scalar_one_or_none()
        
        if verification is None:
            return (False, "No verification in progress")
        
        if verification.is_code_expired():
            # Reissue code
            verification.issue_new_code()
            await self.session.commit()
            return (False, "Code expired. A new code has been sent.")
        
        # Normalize and verify
        if verification.verify_code(submitted_code):
            await self.session.commit()
            logger.info(f"User {user.id} verified session via code")
            return (True, None)
        
        # Check if too many failed attempts
        if verification.requires_reissue():
            verification.issue_new_code()
            await self.session.commit()
            return (False, "Too many incorrect attempts. A new code has been sent.")
        
        await self.session.commit()
        return (False, "Incorrect verification code")

    async def verify_link(
        self,
        link_key: str,
    ) -> tuple[bool, UUID | None, str | None]:
        """
        Verify using the email link key.
        
        Args:
            link_key: The key from the verification link
            
        Returns:
            Tuple of (success, user_id, error_message)
        """
        result = await self.session.execute(
            select(SessionVerification).where(
                SessionVerification.link_key == link_key
            )
        )
        verification = result.scalar_one_or_none()
        
        if verification is None:
            logger.warning("Invalid verification link attempted")
            return (False, None, "Invalid or expired verification link")
        
        if verification.is_code_expired():
            return (False, verification.user_id, "Verification link has expired")
        
        if verification.verify_link(link_key):
            await self.session.commit()
            logger.info(f"User {verification.user_id} verified session via link")
            return (True, verification.user_id, None)
        
        return (False, verification.user_id, "Invalid verification link")

    async def reissue_code(
        self,
        user: "User",
        access_token: str,
    ) -> tuple[str, str]:
        """
        Reissue verification code (e.g., user clicked "resend").
        
        Returns:
            Tuple of (new_code, new_link_key)
        """
        verification = await self.get_or_create_verification(user, access_token)
        code, link_key = verification.issue_new_code()
        await self.session.commit()
        
        logger.info(f"Reissued verification code for user {user.id}")
        return (code, link_key)

    async def clear_verification(
        self,
        user: "User",
        access_token: str,
    ) -> None:
        """
        Clear verification state (e.g., on logout).
        """
        session_token = self._hash_token(access_token)
        
        result = await self.session.execute(
            select(SessionVerification).where(
                and_(
                    SessionVerification.user_id == user.id,
                    SessionVerification.session_token == session_token,
                )
            )
        )
        verification = result.scalar_one_or_none()
        
        if verification:
            await self.session.delete(verification)
            await self.session.commit()

    async def log_sensitive_action(
        self,
        user: "User",
        action_type: str,
        action_details: str | None = None,
        verification_required: bool = False,
        verification_method: str | None = None,
        ip_address: str | None = None,
        country: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Log a sensitive action for audit purposes.
        """
        log_entry = SensitiveActionLog(
            user_id=user.id,
            action_type=action_type,
            action_details=action_details,
            verification_required=verification_required,
            verification_method=verification_method,
            ip_address=ip_address,
            country=country,
            user_agent=user_agent,
        )
        self.session.add(log_entry)
        await self.session.commit()

    @staticmethod
    def _obscure_email(email: str) -> str:
        """
        Obscure an email address for display (like osu!'s h***@gmail.com).
        Shows first character and domain.
        """
        if "@" not in email:
            return email
        
        local, domain = email.rsplit("@", 1)
        if len(local) <= 1:
            return f"*@{domain}"
        
        return f"{local[0]}***@{domain}"

    async def cleanup_expired_verifications(self) -> int:
        """
        Clean up old/expired verification records.
        Should be run periodically as a background task.
        
        Returns number of records deleted.
        """
        # Delete verifications older than 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        result = await self.session.execute(
            select(SessionVerification).where(
                SessionVerification.created_at < cutoff
            )
        )
        old_verifications = result.scalars().all()
        
        count = 0
        for v in old_verifications:
            await self.session.delete(v)
            count += 1
        
        if count > 0:
            await self.session.commit()
            logger.info(f"Cleaned up {count} expired session verifications")
        
        return count


# Singleton getter
_verification_service: SessionVerificationService | None = None


def get_session_verification_service(
    session: AsyncSession,
) -> SessionVerificationService:
    """Get session verification service instance."""
    return SessionVerificationService(session)
