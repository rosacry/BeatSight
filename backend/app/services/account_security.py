"""
Account security service for login attempt tracking and account lockout.

Implements:
- Failed login attempt tracking (Redis-based for speed)
- Account lockout after configurable failed attempts
- Automatic unlock after lockout period
- Security event logging
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.redis import get_redis
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Security configuration
MAX_FAILED_ATTEMPTS = 5  # Lock after 5 failed attempts
LOCKOUT_DURATION_MINUTES = 15  # Lock for 15 minutes
ATTEMPT_WINDOW_MINUTES = 15  # Track attempts within 15-minute window
PROGRESSIVE_LOCKOUT = True  # Double lockout time for repeat offenders


class AccountSecurityService:
    """Service for managing account security and login attempts."""

    def __init__(self):
        self._redis: Optional[object] = None

    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    def _get_attempt_key(self, email: str) -> str:
        """Get Redis key for tracking login attempts."""
        return f"login_attempts:{email.lower()}"

    def _get_lockout_key(self, email: str) -> str:
        """Get Redis key for account lockout status."""
        return f"account_lockout:{email.lower()}"

    def _get_lockout_count_key(self, email: str) -> str:
        """Get Redis key for counting consecutive lockouts (progressive)."""
        return f"lockout_count:{email.lower()}"

    async def record_failed_attempt(self, email: str, ip_address: str) -> dict:
        """
        Record a failed login attempt.
        
        Returns:
            dict with keys:
            - locked: bool - whether account is now locked
            - attempts: int - current attempt count
            - remaining_attempts: int - attempts before lockout
            - lockout_until: datetime | None - when lockout expires
        """
        redis = await self._get_redis()
        if redis is None:
            # Redis unavailable - log and allow (fail open for availability)
            logger.warning("Redis unavailable for login attempt tracking")
            return {
                "locked": False,
                "attempts": 0,
                "remaining_attempts": MAX_FAILED_ATTEMPTS,
                "lockout_until": None,
            }

        attempt_key = self._get_attempt_key(email)
        
        # Increment attempt counter
        attempts = await redis.incr(attempt_key)
        
        # Set expiry on first attempt
        if attempts == 1:
            await redis.expire(attempt_key, ATTEMPT_WINDOW_MINUTES * 60)

        logger.warning(
            "failed_login_attempt",
            extra={
                "email": email[:3] + "***",  # Partial email for privacy
                "ip_address": ip_address,
                "attempts": attempts,
                "max_attempts": MAX_FAILED_ATTEMPTS,
            }
        )

        # Check if we should lock the account
        if attempts >= MAX_FAILED_ATTEMPTS:
            lockout_until = await self._lock_account(email)
            return {
                "locked": True,
                "attempts": attempts,
                "remaining_attempts": 0,
                "lockout_until": lockout_until,
            }

        return {
            "locked": False,
            "attempts": attempts,
            "remaining_attempts": MAX_FAILED_ATTEMPTS - attempts,
            "lockout_until": None,
        }

    async def _lock_account(self, email: str) -> datetime:
        """Lock an account and return when it will unlock."""
        redis = await self._get_redis()
        lockout_key = self._get_lockout_key(email)
        lockout_count_key = self._get_lockout_count_key(email)

        # Get lockout count for progressive lockout
        lockout_count = 1
        if PROGRESSIVE_LOCKOUT:
            count_str = await redis.get(lockout_count_key)
            if count_str:
                lockout_count = min(int(count_str) + 1, 4)  # Max 4x multiplier
            await redis.set(lockout_count_key, str(lockout_count), ex=86400)  # 24hr expiry

        # Calculate lockout duration (progressive: 15, 30, 60, 120 minutes)
        duration_minutes = LOCKOUT_DURATION_MINUTES * lockout_count
        lockout_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)

        # Set lockout flag
        await redis.set(lockout_key, lockout_until.isoformat(), ex=duration_minutes * 60)

        # Clear attempt counter
        await redis.delete(self._get_attempt_key(email))

        logger.warning(
            "account_locked",
            extra={
                "email": email[:3] + "***",
                "duration_minutes": duration_minutes,
                "lockout_count": lockout_count,
                "unlock_at": lockout_until.isoformat(),
            }
        )

        return lockout_until

    async def is_account_locked(self, email: str) -> tuple[bool, Optional[datetime]]:
        """
        Check if an account is currently locked.
        
        Returns:
            Tuple of (is_locked, unlock_time)
        """
        redis = await self._get_redis()
        if redis is None:
            return False, None

        lockout_key = self._get_lockout_key(email)
        lockout_until_str = await redis.get(lockout_key)

        if lockout_until_str is None:
            return False, None

        try:
            lockout_until = datetime.fromisoformat(lockout_until_str)
            if datetime.now(timezone.utc) >= lockout_until:
                # Lockout expired - clean up
                await redis.delete(lockout_key)
                return False, None
            return True, lockout_until
        except ValueError:
            # Invalid date format - clean up
            await redis.delete(lockout_key)
            return False, None

    async def clear_failed_attempts(self, email: str) -> None:
        """Clear failed login attempts after successful login."""
        redis = await self._get_redis()
        if redis is None:
            return

        attempt_key = self._get_attempt_key(email)
        lockout_count_key = self._get_lockout_count_key(email)

        # Clear attempt counter
        await redis.delete(attempt_key)
        
        # Reset progressive lockout counter on successful login
        await redis.delete(lockout_count_key)

        logger.info(
            "login_success_attempts_cleared",
            extra={"email": email[:3] + "***"}
        )

    async def get_attempt_status(self, email: str) -> dict:
        """Get current attempt status for an account."""
        redis = await self._get_redis()
        if redis is None:
            return {
                "attempts": 0,
                "remaining_attempts": MAX_FAILED_ATTEMPTS,
                "is_locked": False,
                "lockout_until": None,
            }

        attempt_key = self._get_attempt_key(email)
        attempts_str = await redis.get(attempt_key)
        attempts = int(attempts_str) if attempts_str else 0

        is_locked, lockout_until = await self.is_account_locked(email)

        return {
            "attempts": attempts,
            "remaining_attempts": max(0, MAX_FAILED_ATTEMPTS - attempts),
            "is_locked": is_locked,
            "lockout_until": lockout_until,
        }

    async def manually_unlock_account(self, email: str) -> bool:
        """
        Manually unlock an account (admin action).
        
        Returns True if account was locked and is now unlocked.
        """
        redis = await self._get_redis()
        if redis is None:
            return False

        lockout_key = self._get_lockout_key(email)
        was_locked = await redis.delete(lockout_key)

        # Also clear attempt counter and progressive lockout
        await redis.delete(self._get_attempt_key(email))
        await redis.delete(self._get_lockout_count_key(email))

        if was_locked:
            logger.info(
                "account_manually_unlocked",
                extra={"email": email[:3] + "***"}
            )

        return bool(was_locked)


# Singleton instance
_security_service: Optional[AccountSecurityService] = None


def get_account_security_service() -> AccountSecurityService:
    """Get the account security service singleton."""
    global _security_service
    if _security_service is None:
        _security_service = AccountSecurityService()
    return _security_service
