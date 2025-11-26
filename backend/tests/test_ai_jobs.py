"""Tests for AI job service operations.

These tests validate job lifecycle management including enqueueing,
state transitions, filtering operations, and worker coordination.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.ai_job import AIJob, AIJobPriority, AIJobState
from app.schemas.ai_jobs import AIJobCreate
from app.services.ai_jobs import AIJobService


class TestAIJobService:
    """Test cases for AIJobService."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> AIJobService:
        """Create an AIJobService with mocked session."""
        return AIJobService(mock_session)

    @pytest.mark.asyncio
    async def test_enqueue_job_success(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test successfully enqueueing a new AI job."""
        song_id = uuid.uuid4()
        user_id = uuid.uuid4()
        payload = AIJobCreate(song_id=song_id, priority=AIJobPriority.PRIORITY)

        await service.enqueue(payload, requested_by=user_id)

        mock_session.add.assert_called_once()
        added_job = mock_session.add.call_args[0][0]
        assert added_job.song_id == song_id
        assert added_job.priority == AIJobPriority.PRIORITY
        assert added_job.requested_by_id == user_id
        assert added_job.state == AIJobState.QUEUED
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_job_anonymous(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test enqueueing a job without authenticated user."""
        song_id = uuid.uuid4()
        payload = AIJobCreate(song_id=song_id)

        await service.enqueue(payload, requested_by=None)

        added_job = mock_session.add.call_args[0][0]
        assert added_job.requested_by_id is None

    @pytest.mark.asyncio
    async def test_enqueue_job_default_priority(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that jobs default to standard priority."""
        payload = AIJobCreate(song_id=uuid.uuid4())

        await service.enqueue(payload, requested_by=None)

        added_job = mock_session.add.call_args[0][0]
        assert added_job.priority == AIJobPriority.STANDARD

    @pytest.mark.asyncio
    async def test_list_jobs_returns_all(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test listing all jobs without filter."""
        job1 = AIJob(
            id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            state=AIJobState.QUEUED,
        )
        job2 = AIJob(
            id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            state=AIJobState.COMPLETE,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value = [job1, job2]
        mock_session.execute.return_value = mock_result

        result = await service.list_jobs()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_filtered_by_song(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test listing jobs filtered by song_id."""
        song_id = uuid.uuid4()
        job = AIJob(id=uuid.uuid4(), song_id=song_id, state=AIJobState.QUEUED)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value = [job]
        mock_session.execute.return_value = mock_result

        result = await service.list_jobs(song_id=song_id)

        assert len(result) == 1
        assert result[0].song_id == song_id

    @pytest.mark.asyncio
    async def test_mark_started_success(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test marking a job as started."""
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.QUEUED,
        )
        mock_session.get.return_value = job

        await service.mark_started(job_id, worker_id)

        assert job.state == AIJobState.PROCESSING
        assert job.started_at is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_started_job_not_found(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that marking non-existent job raises ValueError."""
        mock_session.get.return_value = None
        worker_id = uuid.uuid4()

        with pytest.raises(ValueError, match="Job not found"):
            await service.mark_started(uuid.uuid4(), worker_id)

    @pytest.mark.asyncio
    async def test_mark_finished_success(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test marking a job as successfully completed."""
        job_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
        )
        mock_session.get.return_value = job

        await service.mark_finished(job_id)

        assert job.state == AIJobState.COMPLETE
        assert job.finished_at is not None
        assert job.error_message is None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_finished_with_error(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test marking a job as failed with error message."""
        job_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
        )
        mock_session.get.return_value = job

        error_msg = "Demucs separation failed: out of memory"
        await service.mark_finished(job_id, error=error_msg)

        assert job.state == AIJobState.FAILED
        assert job.finished_at is not None
        assert job.error_message == error_msg

    @pytest.mark.asyncio
    async def test_mark_finished_job_not_found(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that finishing non-existent job raises ValueError."""
        mock_session.get.return_value = None

        with pytest.raises(ValueError, match="Job not found"):
            await service.mark_finished(uuid.uuid4())


class TestAIJobLifecycle:
    """Integration-style tests for full job lifecycle scenarios."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> AIJobService:
        """Create an AIJobService with mocked session."""
        return AIJobService(mock_session)

    @pytest.mark.asyncio
    async def test_full_success_lifecycle(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test complete lifecycle: enqueue → start → finish."""
        song_id = uuid.uuid4()
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()

        # Simulate enqueue
        payload = AIJobCreate(song_id=song_id, priority=AIJobPriority.PRIORITY)
        await service.enqueue(payload, requested_by=None)

        # Create a job object to simulate database state
        job = AIJob(
            id=job_id,
            song_id=song_id,
            state=AIJobState.QUEUED,
            priority=AIJobPriority.PRIORITY,
        )
        mock_session.get.return_value = job

        # Start processing
        await service.mark_started(job_id, worker_id)
        assert job.state == AIJobState.PROCESSING

        # Complete successfully
        await service.mark_finished(job_id)
        assert job.state == AIJobState.COMPLETE

    @pytest.mark.asyncio
    async def test_full_failure_lifecycle(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test lifecycle with failure: enqueue → start → fail."""
        song_id = uuid.uuid4()
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()

        # Simulate enqueue
        payload = AIJobCreate(song_id=song_id)
        await service.enqueue(payload, requested_by=None)

        # Create a job object to simulate database state
        job = AIJob(
            id=job_id,
            song_id=song_id,
            state=AIJobState.QUEUED,
        )
        mock_session.get.return_value = job

        # Start processing
        await service.mark_started(job_id, worker_id)
        assert job.state == AIJobState.PROCESSING

        # Fail with error
        await service.mark_finished(job_id, error="Model inference timeout")
        assert job.state == AIJobState.FAILED
        assert "timeout" in job.error_message.lower()


class TestWorkerCoordination:
    """Tests for worker heartbeat and coordination functionality."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_session: AsyncMock) -> AIJobService:
        """Create an AIJobService with mocked session."""
        return AIJobService(mock_session)

    @pytest.mark.asyncio
    async def test_heartbeat_updates_timestamp(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that heartbeat updates worker_id and last_heartbeat."""
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
        )
        mock_session.get.return_value = job

        await service.heartbeat(job_id, worker_id)

        assert job.worker_id == worker_id
        assert job.last_heartbeat is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_job_not_found(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that heartbeat for non-existent job raises ValueError."""
        mock_session.get.return_value = None

        with pytest.raises(ValueError, match="Job not found"):
            await service.heartbeat(uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_progress_sets_values(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that update_progress sets percent and message."""
        job_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
        )
        mock_session.get.return_value = job

        await service.update_progress(job_id, 75, "Separating drums...")

        assert job.progress_percent == 75
        assert job.progress_message == "Separating drums..."
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_progress_message_only(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that update_progress works with message only."""
        job_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
            progress_percent=50,
        )
        mock_session.get.return_value = job

        await service.update_progress(job_id, 50, "Still processing...")

        assert job.progress_percent == 50
        assert job.progress_message == "Still processing..."

    @pytest.mark.asyncio
    async def test_claim_job_returns_oldest_queued(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that claim_job returns oldest queued job."""
        worker_id = uuid.uuid4()
        oldest_job = AIJob(
            id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            state=AIJobState.QUEUED,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = oldest_job
        mock_session.execute.return_value = mock_result

        result = await service.claim_job(worker_id)

        assert result == oldest_job
        assert oldest_job.state == AIJobState.PROCESSING
        assert oldest_job.worker_id == worker_id
        assert oldest_job.started_at is not None
        assert oldest_job.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_claim_job_returns_none_when_empty(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that claim_job returns None when no jobs available."""
        worker_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await service.claim_job(worker_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_release_job_resets_state(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that release_job resets job to queued state."""
        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
            worker_id=worker_id,
            last_heartbeat=datetime.now(timezone.utc),
            progress_percent=50,
            progress_message="Halfway done",
        )
        mock_session.get.return_value = job

        await service.release_job(job_id)

        assert job.state == AIJobState.QUEUED
        assert job.worker_id is None
        assert job.started_at is None
        assert job.last_heartbeat is None
        assert job.progress_percent is None
        assert job.progress_message is None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_job_not_found(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that release_job for non-existent job raises ValueError."""
        mock_session.get.return_value = None

        with pytest.raises(ValueError, match="Job not found"):
            await service.release_job(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_find_stale_jobs_filters_by_threshold(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that find_stale_jobs returns jobs with old heartbeats."""
        now = datetime.now(timezone.utc)
        stale_job = AIJob(
            id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            state=AIJobState.PROCESSING,
            last_heartbeat=now - timedelta(minutes=10),
        )
        # Note: fresh_job would have last_heartbeat=now - timedelta(minutes=2)
        # but we only test that stale jobs are returned

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stale_job]
        mock_session.execute.return_value = mock_result

        result = await service.find_stale_jobs(stale_threshold_seconds=300)  # 5 minutes

        assert len(result) == 1
        assert result[0] == stale_job
