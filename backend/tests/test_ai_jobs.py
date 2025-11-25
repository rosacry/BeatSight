"""Tests for AI job service operations.

These tests validate job lifecycle management including enqueueing,
state transitions, and filtering operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
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
        payload = AIJobCreate(song_id=song_id, priority=AIJobPriority.HIGH)

        result = await service.enqueue(payload, requested_by=user_id)

        mock_session.add.assert_called_once()
        added_job = mock_session.add.call_args[0][0]
        assert added_job.song_id == song_id
        assert added_job.priority == AIJobPriority.HIGH
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

        result = await service.enqueue(payload, requested_by=None)

        added_job = mock_session.add.call_args[0][0]
        assert added_job.requested_by_id is None

    @pytest.mark.asyncio
    async def test_enqueue_job_default_priority(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that jobs default to standard priority."""
        payload = AIJobCreate(song_id=uuid.uuid4())

        result = await service.enqueue(payload, requested_by=None)

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
        job = AIJob(
            id=job_id,
            song_id=uuid.uuid4(),
            state=AIJobState.QUEUED,
        )
        mock_session.get.return_value = job

        await service.mark_started(job_id)

        assert job.state == AIJobState.PROCESSING
        assert job.started_at is not None
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_started_job_not_found(
        self, service: AIJobService, mock_session: AsyncMock
    ) -> None:
        """Test that marking non-existent job raises ValueError."""
        mock_session.get.return_value = None

        with pytest.raises(ValueError, match="Job not found"):
            await service.mark_started(uuid.uuid4())

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

        # Simulate enqueue
        payload = AIJobCreate(song_id=song_id, priority=AIJobPriority.HIGH)
        await service.enqueue(payload, requested_by=None)

        # Create a job object to simulate database state
        job = AIJob(
            id=job_id,
            song_id=song_id,
            state=AIJobState.QUEUED,
            priority=AIJobPriority.HIGH,
        )
        mock_session.get.return_value = job

        # Start processing
        await service.mark_started(job_id)
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
        await service.mark_started(job_id)
        assert job.state == AIJobState.PROCESSING

        # Fail with error
        await service.mark_finished(job_id, error="Model inference timeout")
        assert job.state == AIJobState.FAILED
        assert "timeout" in job.error_message.lower()
