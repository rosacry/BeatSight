"""Tests for quota service operations.

Tests quota limits, usage tracking, subscription-based priorities,
and quota enforcement.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.subscription import Subscription, SubscriptionPlan
from app.services.quota import (
    JobPriority,
    QuotaExceededError,
    QuotaLimits,
    QuotaService,
    QuotaStatus,
)


class TestQuotaLimits:
    """Test cases for QuotaLimits configuration."""

    def test_free_plan_limits(self) -> None:
        """Test FREE plan quota limits."""
        limits = QuotaLimits.for_plan(SubscriptionPlan.FREE)
        
        assert limits.jobs_per_month == 10
        assert limits.jobs_per_day == 3
        assert limits.max_concurrent == 1
        assert limits.priority == JobPriority.STANDARD

    def test_pro_monthly_plan_limits(self) -> None:
        """Test PRO_MONTHLY plan quota limits."""
        limits = QuotaLimits.for_plan(SubscriptionPlan.PRO_MONTHLY)
        
        assert limits.jobs_per_month == 100
        assert limits.jobs_per_day == 20
        assert limits.max_concurrent == 3
        assert limits.priority == JobPriority.HIGH

    def test_pro_yearly_plan_limits(self) -> None:
        """Test PRO_YEARLY plan quota limits (same as monthly)."""
        limits = QuotaLimits.for_plan(SubscriptionPlan.PRO_YEARLY)
        
        assert limits.jobs_per_month == 100
        assert limits.jobs_per_day == 20
        assert limits.max_concurrent == 3
        assert limits.priority == JobPriority.HIGH

    def test_anonymous_limits(self) -> None:
        """Test anonymous user quota limits."""
        limits = QuotaLimits.anonymous()
        
        assert limits.jobs_per_month == 3
        assert limits.jobs_per_day == 1
        assert limits.max_concurrent == 1
        assert limits.priority == JobPriority.LOW


class TestQuotaStatus:
    """Test cases for QuotaStatus behavior."""

    def test_can_enqueue_with_remaining_quota(self) -> None:
        """Test can_enqueue returns True when quota available."""
        status = QuotaStatus(
            plan=SubscriptionPlan.FREE,
            limits=QuotaLimits.for_plan(SubscriptionPlan.FREE),
            used_this_month=5,
            used_today=1,
            remaining_month=5,
            remaining_today=2,
            resets_at=datetime.now(timezone.utc),
        )
        
        assert status.can_enqueue is True

    def test_cannot_enqueue_monthly_exhausted(self) -> None:
        """Test can_enqueue returns False when monthly quota exhausted."""
        status = QuotaStatus(
            plan=SubscriptionPlan.FREE,
            limits=QuotaLimits.for_plan(SubscriptionPlan.FREE),
            used_this_month=10,
            used_today=1,
            remaining_month=0,
            remaining_today=2,
            resets_at=datetime.now(timezone.utc),
        )
        
        assert status.can_enqueue is False

    def test_cannot_enqueue_daily_exhausted(self) -> None:
        """Test can_enqueue returns False when daily quota exhausted."""
        status = QuotaStatus(
            plan=SubscriptionPlan.FREE,
            limits=QuotaLimits.for_plan(SubscriptionPlan.FREE),
            used_this_month=2,
            used_today=3,
            remaining_month=8,
            remaining_today=0,
            resets_at=datetime.now(timezone.utc),
        )
        
        assert status.can_enqueue is False


class TestQuotaExceededError:
    """Test cases for QuotaExceededError."""

    def test_error_attributes(self) -> None:
        """Test error contains limit and usage info."""
        resets_at = datetime(2025, 12, 1, tzinfo=timezone.utc)
        error = QuotaExceededError(limit=10, used=10, resets_at=resets_at)
        
        assert error.limit == 10
        assert error.used == 10
        assert error.resets_at == resets_at
        assert "10/10" in str(error)

    def test_error_without_reset_time(self) -> None:
        """Test error works without reset time."""
        error = QuotaExceededError(limit=5, used=5)
        
        assert error.resets_at is None


class TestQuotaService:
    """Test cases for QuotaService."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> QuotaService:
        """Create a QuotaService with mocked session."""
        return QuotaService(mock_session)

    @pytest.mark.asyncio
    async def test_get_quota_status_anonymous(self, service: QuotaService) -> None:
        """Test quota status for anonymous users."""
        status = await service.get_quota_status(None)
        
        assert status.plan is None
        assert status.limits.jobs_per_month == 3
        assert status.limits.jobs_per_day == 1
        assert status.used_this_month == 0
        assert status.used_today == 0
        assert status.can_enqueue is True

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_get_quota_status_free_user(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test quota status for free tier user."""
        user_id = uuid.uuid4()
        
        # No subscription found -> defaults to FREE
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Mock Redis usage
        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [5, 2]  # month, day
        
        status = await service.get_quota_status(user_id)
        
        assert status.plan == SubscriptionPlan.FREE
        assert status.used_this_month == 5
        assert status.used_today == 2
        assert status.remaining_month == 5
        assert status.remaining_today == 1

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_get_quota_status_pro_user(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test quota status for pro tier user."""
        user_id = uuid.uuid4()
        
        # Create mock subscription
        subscription = MagicMock(spec=Subscription)
        subscription.plan_code = SubscriptionPlan.PRO_MONTHLY
        subscription.current_period_end = datetime(2025, 12, 25, tzinfo=timezone.utc)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = subscription
        mock_session.execute.return_value = mock_result
        
        # Mock Redis usage
        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [50, 10]  # month, day
        
        status = await service.get_quota_status(user_id)
        
        assert status.plan == SubscriptionPlan.PRO_MONTHLY
        assert status.limits.jobs_per_month == 100
        assert status.used_this_month == 50
        assert status.remaining_month == 50
        assert status.resets_at == subscription.current_period_end

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_check_quota_passes_when_available(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test check_quota returns status when quota available."""
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [5, 1]
        
        status = await service.check_quota(user_id)
        
        assert status.can_enqueue is True

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_check_quota_raises_when_exceeded(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test check_quota raises QuotaExceededError when limit reached."""
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [10, 3]  # Both limits hit
        
        with pytest.raises(QuotaExceededError) as exc_info:
            await service.check_quota(user_id)
        
        assert exc_info.value.limit == 10
        assert exc_info.value.used == 10

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.increment_quota_usage")
    @patch("app.services.quota.get_quota_usage")
    async def test_consume_quota_increments_counters(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_increment: AsyncMock,
        mock_get_redis: AsyncMock,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test consume_quota increments both monthly and daily counters."""
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_get_quota_usage.side_effect = [6, 2]  # After increment
        
        await service.consume_quota(user_id)
        
        # Should have called increment twice (month and day)
        assert mock_increment.call_count == 2

    @pytest.mark.asyncio
    async def test_get_priority_anonymous(self, service: QuotaService) -> None:
        """Test anonymous users get LOW priority."""
        priority = await service.get_priority(None)
        
        assert priority == JobPriority.LOW

    @pytest.mark.asyncio
    async def test_get_priority_free_user(
        self,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test free users get STANDARD priority."""
        user_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        priority = await service.get_priority(user_id)
        
        assert priority == JobPriority.STANDARD

    @pytest.mark.asyncio
    async def test_get_priority_pro_user(
        self,
        service: QuotaService,
        mock_session: AsyncMock,
    ) -> None:
        """Test pro users get HIGH priority."""
        user_id = uuid.uuid4()
        
        subscription = MagicMock(spec=Subscription)
        subscription.plan_code = SubscriptionPlan.PRO_MONTHLY
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = subscription
        mock_session.execute.return_value = mock_result
        
        priority = await service.get_priority(user_id)
        
        assert priority == JobPriority.HIGH
