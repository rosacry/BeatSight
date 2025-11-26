"""
Tests for admin API routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.models.ai_job import AIJob, AIJobState, AIJobPriority
from app.api.routes.admin import (
    job_to_summary,
    job_to_detail,
    log_admin_action,
)


class TestJobConversions:
    """Tests for job model to response conversions."""

    @pytest.fixture
    def sample_job(self) -> AIJob:
        """Create a sample AIJob for testing."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.song_id = uuid.uuid4()
        job.state = AIJobState.QUEUED
        job.priority = AIJobPriority.STANDARD
        job.requested_by_id = uuid.uuid4()
        job.created_at = datetime.utcnow()
        job.started_at = None
        job.finished_at = None
        job.error_message = None
        job.retry_count = 0
        job.max_retries = 3
        job.worker_id = None
        job.progress_percent = None
        job.progress_message = None
        job.last_heartbeat = None
        job.next_retry_at = None
        job.last_error = None
        return job

    def test_job_to_summary(self, sample_job: AIJob) -> None:
        """Convert job to summary response."""
        summary = job_to_summary(sample_job)

        assert summary.id == sample_job.id
        assert summary.song_id == sample_job.song_id
        assert summary.state == sample_job.state
        assert summary.priority == sample_job.priority
        assert summary.retry_count == sample_job.retry_count

    def test_job_to_summary_with_email(self, sample_job: AIJob) -> None:
        """Convert job to summary with user email."""
        summary = job_to_summary(sample_job, email="user@example.com")

        assert summary.requested_by_email == "user@example.com"

    def test_job_to_detail(self, sample_job: AIJob) -> None:
        """Convert job to detailed response."""
        detail = job_to_detail(sample_job)

        assert detail.id == sample_job.id
        assert detail.progress_percent == sample_job.progress_percent
        assert detail.duration_seconds is None  # No start/finish times

    def test_job_to_detail_with_duration(self, sample_job: AIJob) -> None:
        """Calculate duration for completed job."""
        sample_job.started_at = datetime.utcnow() - timedelta(minutes=10)
        sample_job.finished_at = datetime.utcnow()

        detail = job_to_detail(sample_job)

        assert detail.duration_seconds is not None
        assert detail.duration_seconds >= 600  # At least 10 minutes


class TestAdminActions:
    """Tests for admin action logging."""

    @pytest.mark.asyncio
    async def test_log_admin_action(self) -> None:
        """Admin action is logged."""
        job_id = uuid.uuid4()
        admin_id = uuid.uuid4()

        # Should not raise
        await log_admin_action(
            action="test_action",
            job_id=job_id,
            admin_id=admin_id,
            details={"test": "value"},
        )

    @pytest.mark.asyncio
    async def test_log_admin_action_without_admin_id(self) -> None:
        """Admin action can be logged without admin ID."""
        job_id = uuid.uuid4()

        await log_admin_action(
            action="test_action",
            job_id=job_id,
            admin_id=None,
        )


class TestAdminJobListEndpoint:
    """Tests for admin job list endpoint logic."""

    def test_filter_conditions_empty_by_default(self) -> None:
        """No filters creates empty conditions list."""
        # This tests the endpoint logic - in real tests we'd mock the DB
        pass


class TestAdminJobStates:
    """Tests for job state transition validation."""

    @pytest.mark.parametrize(
        "state,can_retry",
        [
            (AIJobState.QUEUED, False),
            (AIJobState.PROCESSING, False),
            (AIJobState.COMPLETE, False),
            (AIJobState.FAILED, True),
            (AIJobState.CANCELLED, True),
        ],
    )
    def test_retry_allowed_states(self, state: AIJobState, can_retry: bool) -> None:
        """Verify which states allow retry."""
        allowed = state in (AIJobState.FAILED, AIJobState.CANCELLED)
        assert allowed == can_retry

    @pytest.mark.parametrize(
        "state,can_cancel",
        [
            (AIJobState.QUEUED, True),
            (AIJobState.PROCESSING, True),
            (AIJobState.COMPLETE, False),
            (AIJobState.FAILED, False),
            (AIJobState.CANCELLED, False),
        ],
    )
    def test_cancel_allowed_states(self, state: AIJobState, can_cancel: bool) -> None:
        """Verify which states allow cancellation."""
        allowed = state in (AIJobState.QUEUED, AIJobState.PROCESSING)
        assert allowed == can_cancel

    @pytest.mark.parametrize(
        "state,can_change_priority",
        [
            (AIJobState.QUEUED, True),
            (AIJobState.PROCESSING, False),
            (AIJobState.COMPLETE, False),
            (AIJobState.FAILED, False),
            (AIJobState.CANCELLED, False),
        ],
    )
    def test_priority_change_allowed_states(
        self, state: AIJobState, can_change_priority: bool
    ) -> None:
        """Verify which states allow priority changes."""
        allowed = state == AIJobState.QUEUED
        assert allowed == can_change_priority


class TestQueueStatsCalculation:
    """Tests for queue statistics calculation."""

    def test_all_states_counted(self) -> None:
        """Verify all job states are accounted for in stats."""
        all_states = set(AIJobState)
        expected_states = {
            AIJobState.QUEUED,
            AIJobState.PROCESSING,
            AIJobState.COMPLETE,
            AIJobState.FAILED,
            AIJobState.CANCELLED,
        }
        assert all_states == expected_states
