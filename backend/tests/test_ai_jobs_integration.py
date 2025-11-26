"""Integration tests for AI job queue flow.

Tests the complete flow of:
1. Checking quota
2. Enqueuing a job
3. Worker claiming the job
4. Worker sending heartbeats and progress updates
5. Job completion/failure
6. SSE streaming (basic validation)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ai_job import AIJob, AIJobPriority, AIJobState
from app.models.song import Song, SongStatus
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.services.ai_jobs import AIJobService
from app.services.quota import JobPriority, QuotaService


class TestAIJobQueueIntegration:
    """Integration tests for the AI job queue workflow."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def test_user(self) -> User:
        """Create a test user."""
        user = MagicMock(spec=User)
        user.id = uuid.uuid4()
        user.email = "test@example.com"
        user.display_name = "TestUser"
        return user

    @pytest.fixture
    def test_song(self) -> Song:
        """Create a test song."""
        song = MagicMock(spec=Song)
        song.id = uuid.uuid4()
        song.title = "Test Song"
        song.artist = "Test Artist"
        song.status = SongStatus.PENDING
        return song

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_quota_check_before_enqueue(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        test_user: User,
    ) -> None:
        """Test that quota is checked before allowing job enqueue."""
        # Setup: Free user with available quota
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No subscription = FREE
        mock_session.execute.return_value = mock_result

        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [5, 1]  # 5/10 month, 1/3 day

        quota_service = QuotaService(mock_session)
        status = await quota_service.check_quota(test_user.id)

        assert status.can_enqueue is True
        assert status.remaining_month == 5
        assert status.remaining_today == 2

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_quota_exceeded_blocks_enqueue(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
        test_user: User,
    ) -> None:
        """Test that exceeded quota prevents job enqueue."""
        from app.services.quota import QuotaExceededError

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_get_redis.return_value = AsyncMock()
        mock_get_quota_usage.side_effect = [10, 3]  # All limits hit

        quota_service = QuotaService(mock_session)

        with pytest.raises(QuotaExceededError) as exc_info:
            await quota_service.check_quota(test_user.id)

        assert exc_info.value.limit == 10
        assert exc_info.value.used == 10

    @pytest.mark.asyncio
    async def test_job_enqueue_creates_queued_job(
        self,
        mock_session: AsyncMock,
        test_user: User,
        test_song: Song,
    ) -> None:
        """Test that enqueuing a job creates it in QUEUED state."""
        from app.schemas.ai_jobs import AIJobCreate

        # Mock AIJob to avoid SQLAlchemy mapper configuration issues
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = uuid.uuid4()
        mock_job.song_id = test_song.id
        mock_job.state = AIJobState.QUEUED
        mock_job.requested_by_id = test_user.id
        mock_job.created_at = datetime.now(timezone.utc)

        with patch("app.services.ai_jobs.AIJob", return_value=mock_job) as MockAIJob:
            service = AIJobService(mock_session)
            payload = AIJobCreate(song_id=test_song.id, priority=AIJobPriority.STANDARD)

            await service.enqueue(payload, requested_by=test_user.id)

            # Verify AIJob was constructed with correct args
            MockAIJob.assert_called_once()
            call_kwargs = MockAIJob.call_args.kwargs
            assert call_kwargs["song_id"] == test_song.id
            assert call_kwargs["state"] == AIJobState.QUEUED
            assert call_kwargs["requested_by_id"] == test_user.id

            # Verify session operations
            mock_session.add.assert_called_once_with(mock_job)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_job)

    @pytest.mark.asyncio
    async def test_worker_claims_queued_job(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that a worker can claim a queued job."""
        worker_id = uuid.uuid4()
        job_id = uuid.uuid4()

        # Create a mock queued job
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.QUEUED
        mock_job.priority = AIJobPriority.STANDARD

        # Mock get_next_queued_job
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_session.execute.return_value = mock_result

        service = AIJobService(mock_session)
        claimed = await service.claim_job(worker_id)

        assert claimed is not None
        assert mock_job.state == AIJobState.PROCESSING
        assert mock_job.worker_id == worker_id
        assert mock_job.last_heartbeat is not None
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_worker_heartbeat_updates_timestamp(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that heartbeat updates the last_heartbeat timestamp."""
        worker_id = uuid.uuid4()
        job_id = uuid.uuid4()
        old_heartbeat = datetime(2025, 11, 25, 10, 0, 0, tzinfo=timezone.utc)

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.worker_id = worker_id
        mock_job.last_heartbeat = old_heartbeat
        mock_session.get.return_value = mock_job

        service = AIJobService(mock_session)
        await service.heartbeat(job_id, worker_id)

        # Heartbeat should be updated
        assert mock_job.last_heartbeat > old_heartbeat
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.ai_jobs.get_redis")
    @patch("app.services.ai_jobs.publish_progress")
    async def test_progress_update_publishes_to_redis(
        self,
        mock_publish: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that progress updates are published to Redis for SSE."""
        job_id = uuid.uuid4()

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_session.get.return_value = mock_job

        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        service = AIJobService(mock_session)
        await service.update_progress(
            job_id, 50, "Processing audio...", stage="separation"
        )

        # Verify job was updated
        assert mock_job.progress_percent == 50
        assert mock_job.progress_message == "Processing audio..."

        # Verify Redis publish was called
        mock_publish.assert_called_once()
        call_args = mock_publish.call_args
        assert call_args[0][0] == mock_redis
        progress_update = call_args[0][1]
        assert progress_update.job_id == job_id
        assert progress_update.percent == 50
        assert progress_update.stage == "separation"

    @pytest.mark.asyncio
    async def test_job_completion_sets_complete_state(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that marking a job finished sets COMPLETE state."""
        job_id = uuid.uuid4()

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.PROCESSING
        mock_session.get.return_value = mock_job

        service = AIJobService(mock_session)
        await service.mark_finished(job_id)

        assert mock_job.state == AIJobState.COMPLETE
        assert mock_job.finished_at is not None
        assert mock_job.progress_percent == 100

    @pytest.mark.asyncio
    async def test_job_failure_sets_failed_state(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that marking a job finished with error sets FAILED state."""
        job_id = uuid.uuid4()
        error_message = "Pipeline crashed: out of memory"

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.PROCESSING
        mock_session.get.return_value = mock_job

        service = AIJobService(mock_session)
        await service.mark_finished(job_id, error=error_message)

        assert mock_job.state == AIJobState.FAILED
        assert mock_job.error_message == error_message
        assert mock_job.finished_at is not None

    @pytest.mark.asyncio
    async def test_release_job_returns_to_queue(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that releasing a job returns it to QUEUED state."""
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.PROCESSING
        mock_job.worker_id = worker_id
        mock_session.get.return_value = mock_job

        service = AIJobService(mock_session)
        await service.release_job(job_id)

        assert mock_job.state == AIJobState.QUEUED
        assert mock_job.worker_id is None
        assert mock_job.started_at is None
        assert mock_job.progress_percent is None

    @pytest.mark.asyncio
    async def test_find_stale_jobs_returns_old_heartbeats(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that stale jobs are identified correctly."""
        stale_job = MagicMock(spec=AIJob)
        stale_job.id = uuid.uuid4()
        stale_job.state = AIJobState.PROCESSING
        stale_job.last_heartbeat = datetime(2025, 11, 25, 10, 0, 0, tzinfo=timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_job]
        mock_session.execute.return_value = mock_result

        service = AIJobService(mock_session)
        stale = await service.find_stale_jobs(stale_threshold_seconds=300)

        assert len(stale) == 1
        assert stale[0].id == stale_job.id


class TestQueuePositionAndWait:
    """Tests for queue position and wait time estimation."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.get = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_get_queue_length(self, mock_session: AsyncMock) -> None:
        """Test getting total queue length."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 15
        mock_session.execute.return_value = mock_result

        service = AIJobService(mock_session)
        length = await service.get_queue_length()

        assert length == 15

    @pytest.mark.asyncio
    async def test_get_queue_position(self, mock_session: AsyncMock) -> None:
        """Test getting a job's position in queue."""
        job_id = uuid.uuid4()

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.QUEUED
        mock_job.priority = AIJobPriority.STANDARD
        mock_job.created_at = datetime.now(timezone.utc)
        mock_session.get.return_value = mock_job

        # Position query returns 5
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        service = AIJobService(mock_session)
        position = await service.get_queue_position(job_id)

        assert position == 5

    @pytest.mark.asyncio
    async def test_get_queue_position_not_queued(self, mock_session: AsyncMock) -> None:
        """Test getting position for a job that's not queued returns None."""
        job_id = uuid.uuid4()

        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.state = AIJobState.PROCESSING
        mock_session.get.return_value = mock_job

        service = AIJobService(mock_session)
        position = await service.get_queue_position(job_id)

        assert position is None


class TestProPriorityQueue:
    """Tests for priority queue behavior with different subscription tiers."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    @patch("app.services.quota.get_redis")
    @patch("app.services.quota.get_quota_usage")
    async def test_pro_user_gets_high_priority(
        self,
        mock_get_quota_usage: AsyncMock,
        mock_get_redis: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Test that Pro users get HIGH priority."""
        user_id = uuid.uuid4()

        # Pro subscription
        subscription = MagicMock(spec=Subscription)
        subscription.plan_code = SubscriptionPlan.PRO_MONTHLY
        subscription.current_period_end = datetime(2025, 12, 25, tzinfo=timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = subscription
        mock_session.execute.return_value = mock_result

        quota_service = QuotaService(mock_session)
        priority = await quota_service.get_priority(user_id)

        assert priority == JobPriority.HIGH

    @pytest.mark.asyncio
    async def test_anonymous_user_gets_low_priority(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that anonymous users get LOW priority."""
        quota_service = QuotaService(mock_session)
        priority = await quota_service.get_priority(None)

        assert priority == JobPriority.LOW

    @pytest.mark.asyncio
    async def test_free_user_gets_standard_priority(
        self,
        mock_session: AsyncMock,
    ) -> None:
        """Test that free users get STANDARD priority."""
        user_id = uuid.uuid4()

        # No subscription = FREE tier
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        quota_service = QuotaService(mock_session)
        priority = await quota_service.get_priority(user_id)

        assert priority == JobPriority.STANDARD
