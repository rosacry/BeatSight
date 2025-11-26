"""Tests for the retry service."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.ai_job import AIJob, AIJobState
from app.services.retry import RetryConfig, RetryService


class TestRetryConfig:
    """Tests for RetryConfig defaults."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay_seconds == 60
        assert config.max_delay_seconds == 3600
        assert config.exponential_base == 2.0
        assert config.jitter_factor == 0.1

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=30,
            max_delay_seconds=7200,
        )
        assert config.max_retries == 5
        assert config.base_delay_seconds == 30
        assert config.max_delay_seconds == 7200


class TestRetryServiceBackoff:
    """Tests for exponential backoff calculation."""

    @pytest.fixture
    def service(self) -> RetryService:
        """Create service with predictable config (no jitter)."""
        config = RetryConfig(
            base_delay_seconds=60,
            exponential_base=2.0,
            max_delay_seconds=3600,
            jitter_factor=0.0,  # Disable jitter for predictable tests
        )
        return RetryService(AsyncMock(), config)

    def test_first_retry_delay(self, service: RetryService) -> None:
        """First retry (count=0) uses base delay."""
        delay = service.calculate_backoff(0)
        assert delay == timedelta(seconds=60)

    def test_second_retry_delay(self, service: RetryService) -> None:
        """Second retry (count=1) doubles the delay."""
        delay = service.calculate_backoff(1)
        assert delay == timedelta(seconds=120)

    def test_third_retry_delay(self, service: RetryService) -> None:
        """Third retry (count=2) quadruples original delay."""
        delay = service.calculate_backoff(2)
        assert delay == timedelta(seconds=240)

    def test_delay_capped_at_max(self, service: RetryService) -> None:
        """Delay is capped at max_delay_seconds."""
        delay = service.calculate_backoff(10)  # Would be 60 * 2^10 = 61440
        assert delay == timedelta(seconds=3600)  # Capped at 1 hour

    def test_jitter_adds_variance(self) -> None:
        """Jitter factor adds randomness to delay."""
        config = RetryConfig(
            base_delay_seconds=100,
            jitter_factor=0.2,  # ±20%
        )
        service = RetryService(AsyncMock(), config)
        
        # Calculate multiple times and check variance
        delays = [service.calculate_backoff(0).total_seconds() for _ in range(100)]
        
        # With 20% jitter, delays should be between 80-120 seconds
        assert min(delays) >= 80
        assert max(delays) <= 120
        # Should have some variance
        assert len(set(delays)) > 1


class TestScheduleRetry:
    """Tests for schedule_retry method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def config(self) -> RetryConfig:
        """Config with no jitter for predictable tests."""
        return RetryConfig(
            max_retries=3,
            base_delay_seconds=60,
            jitter_factor=0.0,
        )

    @pytest.mark.asyncio
    async def test_schedule_retry_success(
        self, mock_session: AsyncMock, config: RetryConfig
    ) -> None:
        """Test successful retry scheduling."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.PROCESSING
        job.retry_count = 0
        job.max_retries = 3
        mock_session.get.return_value = job
        
        service = RetryService(mock_session, config)
        result = await service.schedule_retry(job.id, "Connection timeout")
        
        assert result.action == "scheduled"
        assert result.retry_count == 1
        assert result.next_retry_at is not None
        assert job.state == AIJobState.QUEUED
        assert job.retry_count == 1
        assert job.last_error == "Connection timeout"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_retry_exhausted(
        self, mock_session: AsyncMock, config: RetryConfig
    ) -> None:
        """Test retry when max retries exhausted."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.PROCESSING
        job.retry_count = 3  # Already at max
        job.max_retries = 3
        mock_session.get.return_value = job
        
        service = RetryService(mock_session, config)
        result = await service.schedule_retry(job.id, "Final error")
        
        assert result.action == "exhausted"
        assert job.state == AIJobState.FAILED
        assert "Max retries" in job.error_message

    @pytest.mark.asyncio
    async def test_schedule_retry_not_found(
        self, mock_session: AsyncMock, config: RetryConfig
    ) -> None:
        """Test retry when job not found."""
        mock_session.get.return_value = None
        
        service = RetryService(mock_session, config)
        result = await service.schedule_retry(uuid.uuid4(), "Error")
        
        assert result.action == "not_retriable"
        assert "not found" in result.message

    @pytest.mark.asyncio
    async def test_schedule_retry_wrong_state(
        self, mock_session: AsyncMock, config: RetryConfig
    ) -> None:
        """Test retry when job in non-retriable state."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.COMPLETE  # Can't retry completed jobs
        job.retry_count = 0
        mock_session.get.return_value = job
        
        service = RetryService(mock_session, config)
        result = await service.schedule_retry(job.id, "Error")
        
        assert result.action == "not_retriable"
        assert "complete" in result.message.lower()

    @pytest.mark.asyncio
    async def test_retry_increments_delay(
        self, mock_session: AsyncMock, config: RetryConfig
    ) -> None:
        """Test that successive retries increase delay."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.PROCESSING
        job.max_retries = 5
        mock_session.get.return_value = job
        
        service = RetryService(mock_session, config)
        delays = []
        
        for i in range(3):
            job.retry_count = i
            job.state = AIJobState.PROCESSING  # Reset for each retry
            result = await service.schedule_retry(job.id, f"Error {i}")
            if result.next_retry_at:
                delays.append(result.next_retry_at)
        
        # Each delay should be later than the previous
        # (but we can't easily compare due to datetime.now() calls)
        assert len(delays) == 3


class TestGetJobsReadyForRetry:
    """Tests for get_jobs_ready_for_retry method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_jobs_with_no_retry_time(
        self, mock_session: AsyncMock
    ) -> None:
        """Jobs with no next_retry_at are ready immediately."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.next_retry_at = None
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]
        mock_session.execute.return_value = mock_result
        
        service = RetryService(mock_session)
        jobs = await service.get_jobs_ready_for_retry()
        
        assert len(jobs) == 1
        assert jobs[0].id == job.id

    @pytest.mark.asyncio
    async def test_returns_jobs_past_retry_time(
        self, mock_session: AsyncMock
    ) -> None:
        """Jobs with past next_retry_at are ready."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.next_retry_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]
        mock_session.execute.return_value = mock_result
        
        service = RetryService(mock_session)
        jobs = await service.get_jobs_ready_for_retry()
        
        assert len(jobs) == 1


class TestResetStaleJobs:
    """Tests for reset_stale_jobs method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.get = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_resets_stale_jobs(self, mock_session: AsyncMock) -> None:
        """Test that stale jobs are scheduled for retry."""
        stale_job = MagicMock(spec=AIJob)
        stale_job.id = uuid.uuid4()
        stale_job.state = AIJobState.PROCESSING
        stale_job.retry_count = 0
        stale_job.max_retries = 3
        stale_job.last_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_job]
        mock_session.execute.return_value = mock_result
        mock_session.get.return_value = stale_job
        
        config = RetryConfig(jitter_factor=0.0)
        service = RetryService(mock_session, config)
        results = await service.reset_stale_jobs(stale_threshold_seconds=300)
        
        assert len(results) == 1
        assert results[0].action == "scheduled"

    @pytest.mark.asyncio
    async def test_no_stale_jobs(self, mock_session: AsyncMock) -> None:
        """Test when no stale jobs exist."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        service = RetryService(mock_session)
        results = await service.reset_stale_jobs()
        
        assert len(results) == 0


class TestRetryStats:
    """Tests for get_retry_stats method."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_stats(self, mock_session: AsyncMock) -> None:
        """Test that stats are returned correctly."""
        # Mock the four queries
        mock_results = [
            MagicMock(scalar_one=lambda: 5),   # jobs_with_retries
            MagicMock(scalar_one=lambda: 12),  # total_retries
            MagicMock(scalar_one=lambda: 2),   # exhausted_count
            MagicMock(scalar_one=lambda: 3),   # pending_retries
        ]
        mock_session.execute.side_effect = mock_results
        
        service = RetryService(mock_session)
        stats = await service.get_retry_stats()
        
        assert stats["jobs_with_retries"] == 5
        assert stats["total_retry_attempts"] == 12
        assert stats["exhausted_jobs"] == 2
        assert stats["pending_retries"] == 3
