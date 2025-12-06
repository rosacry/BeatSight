"""Tests for account security service (login attempts and lockout)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services.account_security import (
    AccountSecurityService,
    get_account_security_service,
    MAX_FAILED_ATTEMPTS,
)


class TestAccountSecurityService:
    """Test cases for AccountSecurityService."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        return redis

    @pytest.fixture
    def service(self) -> AccountSecurityService:
        """Create a fresh service instance."""
        return AccountSecurityService()

    @pytest.mark.asyncio
    async def test_record_first_failed_attempt(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test recording the first failed login attempt."""
        with patch.object(service, "_get_redis", return_value=mock_redis):
            result = await service.record_failed_attempt(
                "test@example.com", "192.168.1.1"
            )

        assert result["locked"] is False
        assert result["attempts"] == 1
        assert result["remaining_attempts"] == MAX_FAILED_ATTEMPTS - 1
        assert result["lockout_until"] is None

        # Verify Redis calls
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failed_attempt_triggers_lockout(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test that max failed attempts triggers account lockout."""
        mock_redis.incr = AsyncMock(return_value=MAX_FAILED_ATTEMPTS)

        with patch.object(service, "_get_redis", return_value=mock_redis):
            result = await service.record_failed_attempt(
                "test@example.com", "192.168.1.1"
            )

        assert result["locked"] is True
        assert result["attempts"] == MAX_FAILED_ATTEMPTS
        assert result["remaining_attempts"] == 0
        assert result["lockout_until"] is not None

    @pytest.mark.asyncio
    async def test_is_account_locked_returns_false_when_not_locked(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test checking lock status for unlocked account."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch.object(service, "_get_redis", return_value=mock_redis):
            is_locked, unlock_time = await service.is_account_locked("test@example.com")

        assert is_locked is False
        assert unlock_time is None

    @pytest.mark.asyncio
    async def test_is_account_locked_returns_true_when_locked(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test checking lock status for locked account."""
        from datetime import timedelta

        future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
        mock_redis.get = AsyncMock(return_value=future_time.isoformat())

        with patch.object(service, "_get_redis", return_value=mock_redis):
            is_locked, unlock_time = await service.is_account_locked("test@example.com")

        assert is_locked is True
        assert unlock_time is not None

    @pytest.mark.asyncio
    async def test_is_account_locked_clears_expired_lockout(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test that expired lockouts are automatically cleared."""
        from datetime import timedelta

        past_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        mock_redis.get = AsyncMock(return_value=past_time.isoformat())

        with patch.object(service, "_get_redis", return_value=mock_redis):
            is_locked, unlock_time = await service.is_account_locked("test@example.com")

        assert is_locked is False
        assert unlock_time is None
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_failed_attempts(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test clearing failed attempts after successful login."""
        with patch.object(service, "_get_redis", return_value=mock_redis):
            await service.clear_failed_attempts("test@example.com")

        # Should delete both attempt counter and lockout counter
        assert mock_redis.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_manually_unlock_account(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test admin manually unlocking an account."""
        mock_redis.delete = AsyncMock(return_value=1)

        with patch.object(service, "_get_redis", return_value=mock_redis):
            was_locked = await service.manually_unlock_account("test@example.com")

        assert was_locked is True
        # Should delete lockout, attempts, and progressive counter
        assert mock_redis.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_manually_unlock_account_not_locked(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test unlocking an account that wasn't locked."""
        mock_redis.delete = AsyncMock(return_value=0)

        with patch.object(service, "_get_redis", return_value=mock_redis):
            was_locked = await service.manually_unlock_account("test@example.com")

        assert was_locked is False

    @pytest.mark.asyncio
    async def test_get_attempt_status(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test getting current attempt status."""
        mock_redis.get = AsyncMock(side_effect=["3", None])  # 3 attempts, not locked

        with patch.object(service, "_get_redis", return_value=mock_redis):
            status = await service.get_attempt_status("test@example.com")

        assert status["attempts"] == 3
        assert status["remaining_attempts"] == MAX_FAILED_ATTEMPTS - 3
        assert status["is_locked"] is False

    @pytest.mark.asyncio
    async def test_redis_unavailable_fails_open(
        self, service: AccountSecurityService
    ) -> None:
        """Test that service fails open when Redis is unavailable."""
        with patch.object(service, "_get_redis", return_value=None):
            result = await service.record_failed_attempt(
                "test@example.com", "192.168.1.1"
            )

        # Should allow login when Redis is down
        assert result["locked"] is False
        assert result["remaining_attempts"] == MAX_FAILED_ATTEMPTS

    @pytest.mark.asyncio
    async def test_email_case_insensitivity(
        self, service: AccountSecurityService, mock_redis: AsyncMock
    ) -> None:
        """Test that email keys are case-insensitive."""
        with patch.object(service, "_get_redis", return_value=mock_redis):
            await service.record_failed_attempt("TEST@Example.COM", "192.168.1.1")

        # Key should be lowercased
        call_args = mock_redis.incr.call_args[0][0]
        assert "test@example.com" in call_args.lower()


class TestGetAccountSecurityService:
    """Test singleton accessor."""

    def test_returns_singleton(self) -> None:
        """Test that get_account_security_service returns singleton."""
        service1 = get_account_security_service()
        service2 = get_account_security_service()
        assert service1 is service2

    def test_returns_correct_type(self) -> None:
        """Test that service is correct type."""
        service = get_account_security_service()
        assert isinstance(service, AccountSecurityService)
