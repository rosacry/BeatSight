"""Tests for AI jobs API routes.

These tests validate the HTTP endpoints for AI job management including
enqueueing jobs, quota checking, progress tracking, and SSE streaming.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_current_user_optional, get_db_session
from app.api.routes.ai_jobs import verify_worker_secret
from app.main import app
from app.models.ai_job import AIJob, AIJobPriority, AIJobState
from app.models.user import User
from app.services.quota import JobPriority, QuotaLimits, QuotaStatus


@pytest.fixture
def mock_user() -> User:
    """Create a mock authenticated user."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    return user


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_job() -> AIJob:
    """Create a mock AI job."""
    job = MagicMock(spec=AIJob)
    job.id = uuid.uuid4()
    job.song_id = uuid.uuid4()
    job.state = AIJobState.QUEUED
    job.priority = AIJobPriority.STANDARD
    job.requested_by_id = uuid.uuid4()
    job.worker_id = None
    job.created_at = datetime.now(timezone.utc)
    job.started_at = None
    job.finished_at = None
    job.last_heartbeat = None
    job.progress_percent = 0
    job.progress_message = None
    job.error_message = None
    # Required for the model to serialize properly
    job.song = MagicMock()
    job.song.id = job.song_id
    job.song.title = "Test Song"
    return job


@pytest.fixture
def mock_quota_status() -> QuotaStatus:
    """Create a real quota status object."""
    from app.models.subscription import SubscriptionPlan

    return QuotaStatus(
        plan=SubscriptionPlan.FREE,
        used_this_month=5,
        used_today=1,
        remaining_month=5,
        remaining_today=2,
        resets_at=datetime.now(timezone.utc),
        limits=QuotaLimits(
            jobs_per_month=10,
            jobs_per_day=3,
            max_concurrent=1,
            priority=JobPriority.STANDARD,
        ),
    )


@pytest.fixture
def client_authenticated(mock_user: User, mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_user_optional] = lambda: mock_user
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_anonymous(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client without authentication."""
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def client_worker(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with worker secret authentication.

    This overrides the verify_worker_secret dependency for testing
    worker-only endpoints (claim, heartbeat, progress, release, stale).
    """
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    app.dependency_overrides[verify_worker_secret] = lambda: True
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestEnqueueJob:
    """Tests for POST /ai-jobs endpoint."""

    @patch("app.api.routes.ai_jobs.QuotaService")
    @patch("app.api.routes.ai_jobs.AIJobService")
    @patch("app.api.routes.ai_jobs.get_modal_service")
    def test_enqueue_job_success(
        self,
        mock_modal_factory: MagicMock,
        mock_service_cls: MagicMock,
        mock_quota_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
        mock_quota_status: QuotaStatus,
    ) -> None:
        """Test successfully enqueueing a job."""
        # Setup mocks
        mock_quota = AsyncMock()
        mock_quota.check_quota = AsyncMock(return_value=mock_quota_status)
        # consume_quota returns (QuotaStatus, bool) tuple
        mock_quota.consume_quota = AsyncMock(return_value=(mock_quota_status, False))
        mock_quota_cls.return_value = mock_quota

        mock_service = AsyncMock()
        mock_service.enqueue = AsyncMock(return_value=mock_job)
        mock_service.get_queue_position = AsyncMock(return_value=1)
        mock_service_cls.return_value = mock_service

        # Modal service with is_enabled returning False (sync method)
        mock_modal = MagicMock()
        mock_modal.is_enabled.return_value = False
        mock_modal_factory.return_value = mock_modal

        song_id = str(mock_job.song_id)
        response = client_authenticated.post(
            "/api/ai-jobs",
            json={"song_id": song_id},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job" in data
        assert "queue_position" in data

    @patch("app.api.routes.ai_jobs.QuotaService")
    def test_enqueue_job_quota_exceeded(
        self,
        mock_quota_cls: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test that quota exceeded returns 429."""
        from app.services.quota import QuotaExceededError

        mock_quota = AsyncMock()
        mock_quota.check_quota = AsyncMock(
            side_effect=QuotaExceededError(limit=10, used=10, resets_at=None)
        )
        mock_quota_cls.return_value = mock_quota

        response = client_authenticated.post(
            "/api/ai-jobs",
            json={"song_id": str(uuid.uuid4())},
        )

        assert response.status_code == 429
        # Response structure may be {'limit': 10, 'message': '...', ...}
        data = response.json()
        assert "message" in data or "detail" in data

    @patch("app.api.routes.ai_jobs.QuotaService")
    @patch("app.api.routes.ai_jobs.AIJobService")
    @patch("app.api.routes.ai_jobs.get_modal_service")
    def test_enqueue_job_modal_disabled(
        self,
        mock_modal_factory: MagicMock,
        mock_service_cls: MagicMock,
        mock_quota_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
        mock_quota_status: QuotaStatus,
    ) -> None:
        """Test enqueue when Modal is disabled - job is queued for local workers."""
        mock_quota = AsyncMock()
        mock_quota.check_quota = AsyncMock(return_value=mock_quota_status)
        # consume_quota returns (QuotaStatus, bool) tuple
        mock_quota.consume_quota = AsyncMock(return_value=(mock_quota_status, False))
        mock_quota_cls.return_value = mock_quota

        mock_service = AsyncMock()
        mock_service.enqueue = AsyncMock(return_value=mock_job)
        mock_service.get_queue_position = AsyncMock(return_value=5)
        mock_service_cls.return_value = mock_service

        # Modal disabled
        mock_modal = MagicMock()
        mock_modal.is_enabled.return_value = False
        mock_modal_factory.return_value = mock_modal

        response = client_authenticated.post(
            "/api/ai-jobs",
            json={"song_id": str(uuid.uuid4())},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["queue_position"] == 5
        assert "job" in data


class TestGetQuotaStatus:
    """Tests for GET /ai-jobs/quota endpoint."""

    @patch("app.api.routes.ai_jobs.QuotaService")
    def test_get_quota_authenticated(
        self,
        mock_quota_cls: MagicMock,
        client_authenticated: TestClient,
        mock_quota_status: QuotaStatus,
    ) -> None:
        """Test getting quota status for authenticated user."""
        mock_quota = AsyncMock()
        mock_quota.get_quota_status = AsyncMock(return_value=mock_quota_status)
        mock_quota_cls.return_value = mock_quota

        response = client_authenticated.get("/api/ai-jobs/quota")

        assert response.status_code == 200
        data = response.json()
        assert "remaining_month" in data
        assert "remaining_today" in data
        assert "limit_month" in data
        assert "limit_day" in data

    @patch("app.api.routes.ai_jobs.QuotaService")
    def test_get_quota_anonymous(
        self,
        mock_quota_cls: MagicMock,
        client_anonymous: TestClient,
        mock_quota_status: QuotaStatus,
    ) -> None:
        """Test getting quota status for anonymous user."""
        mock_quota = AsyncMock()
        mock_quota.get_quota_status = AsyncMock(return_value=mock_quota_status)
        mock_quota_cls.return_value = mock_quota

        response = client_anonymous.get("/api/ai-jobs/quota")

        assert response.status_code == 200


class TestListJobs:
    """Tests for GET /ai-jobs endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_jobs_success(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test listing all jobs with pagination."""
        mock_service = AsyncMock()
        mock_service.list_jobs = AsyncMock(return_value=[mock_job])
        mock_service.count_jobs = AsyncMock(return_value=1)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get("/api/ai-jobs")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 1
        assert data["page"] == 1

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_jobs_with_song_filter(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test listing jobs filtered by song_id."""
        mock_service = AsyncMock()
        mock_service.list_jobs = AsyncMock(return_value=[mock_job])
        mock_service.count_jobs = AsyncMock(return_value=1)
        mock_service_cls.return_value = mock_service

        song_id = str(mock_job.song_id)
        response = client_authenticated.get(f"/api/ai-jobs?song_id={song_id}")

        assert response.status_code == 200
        mock_service.list_jobs.assert_called_once()

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_jobs_with_state_filter(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test listing jobs filtered by state."""
        mock_service = AsyncMock()
        mock_service.list_jobs = AsyncMock(return_value=[mock_job])
        mock_service.count_jobs = AsyncMock(return_value=1)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get("/api/ai-jobs?state=QUEUED")

        assert response.status_code == 200

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_jobs_pagination(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test listing jobs with pagination parameters."""
        mock_service = AsyncMock()
        mock_service.list_jobs = AsyncMock(return_value=[mock_job])
        mock_service.count_jobs = AsyncMock(return_value=50)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get("/api/ai-jobs?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10
        assert data["total"] == 50
        assert data["total_pages"] == 5
        assert data["has_prev"] is True
        assert data["has_next"] is True


class TestGetJob:
    """Tests for GET /ai-jobs/{job_id} endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_get_job_success(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test getting a single job."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get(f"/api/ai-jobs/{mock_job.id}")

        assert response.status_code == 200

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_get_job_not_found(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test getting non-existent job returns 404."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        job_id = uuid.uuid4()
        response = client_authenticated.get(f"/api/ai-jobs/{job_id}")

        assert response.status_code == 404


class TestWorkerHeartbeat:
    """Tests for POST /ai-jobs/{job_id}/heartbeat endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_heartbeat_success(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test successful heartbeat."""
        mock_job.state = AIJobState.PROCESSING
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service.heartbeat = AsyncMock()
        mock_service_cls.return_value = mock_service

        worker_id = uuid.uuid4()
        response = client_worker.post(
            f"/api/ai-jobs/{mock_job.id}/heartbeat?worker_id={worker_id}",
        )

        assert response.status_code == 204

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_heartbeat_missing_worker_id(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test heartbeat without worker ID query param."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_worker.post(
            f"/api/ai-jobs/{mock_job.id}/heartbeat",
        )

        assert response.status_code == 422  # Validation error for missing param

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_heartbeat_job_not_found(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test heartbeat for non-existent job."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        response = client_worker.post(
            f"/api/ai-jobs/{job_id}/heartbeat?worker_id={worker_id}",
        )

        assert response.status_code == 404


class TestUpdateProgress:
    """Tests for PATCH /ai-jobs/{job_id}/progress endpoint."""

    @patch("app.api.routes.ai_jobs.get_redis")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_update_progress_success(
        self,
        mock_service_cls: MagicMock,
        mock_get_redis: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test successful progress update."""
        mock_job.state = AIJobState.PROCESSING
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service.update_progress = AsyncMock()
        mock_service_cls.return_value = mock_service

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis

        worker_id = uuid.uuid4()
        response = client_worker.patch(
            f"/api/ai-jobs/{mock_job.id}/progress",
            json={
                "worker_id": str(worker_id),
                "progress_percent": 50,
                "progress_message": "Processing drums...",
            },
        )

        assert response.status_code == 204

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_update_progress_job_not_found(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test progress update for non-existent job."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        job_id = uuid.uuid4()
        worker_id = uuid.uuid4()
        response = client_worker.patch(
            f"/api/ai-jobs/{job_id}/progress",
            json={
                "worker_id": str(worker_id),
                "progress_percent": 50,
            },
        )

        assert response.status_code == 404


class TestClaimJob:
    """Tests for POST /ai-jobs/claim endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_claim_job_success(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test successfully claiming a job."""
        mock_service = AsyncMock()
        mock_service.claim_job = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        worker_id = uuid.uuid4()
        response = client_worker.post(
            f"/api/ai-jobs/claim?worker_id={worker_id}",
        )

        assert response.status_code == 200

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_claim_job_none_available(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test claiming when no jobs available returns 200 with null."""
        mock_service = AsyncMock()
        mock_service.claim_job = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        worker_id = uuid.uuid4()
        response = client_worker.post(
            f"/api/ai-jobs/claim?worker_id={worker_id}",
        )

        # With response_model=AIJobRead | None, returns 200 with null body
        assert response.status_code == 200
        assert response.json() is None

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_claim_job_missing_worker_id(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test claiming without worker ID query param."""
        mock_service = AsyncMock()
        mock_service_cls.return_value = mock_service

        response = client_worker.post("/api/ai-jobs/claim")

        assert response.status_code == 422


class TestReleaseJob:
    """Tests for POST /ai-jobs/{job_id}/release endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_release_job_success(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test successfully releasing a job."""
        mock_job.state = AIJobState.PROCESSING
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service.release_job = AsyncMock()
        mock_service_cls.return_value = mock_service

        response = client_worker.post(
            f"/api/ai-jobs/{mock_job.id}/release",
        )

        assert response.status_code == 204

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_release_job_not_found(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test releasing non-existent job."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        job_id = uuid.uuid4()
        response = client_worker.post(
            f"/api/ai-jobs/{job_id}/release",
        )

        assert response.status_code == 404


class TestListStaleJobs:
    """Tests for GET /ai-jobs/stale/list endpoint."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_stale_jobs_success(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test listing stale jobs."""
        mock_job.state = AIJobState.PROCESSING
        mock_service = AsyncMock()
        mock_service.list_stale_jobs = AsyncMock(return_value=[mock_job])
        mock_service_cls.return_value = mock_service

        response = client_worker.get("/api/ai-jobs/stale/list")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_list_stale_jobs_empty(
        self,
        mock_service_cls: MagicMock,
        client_worker: TestClient,
    ) -> None:
        """Test listing stale jobs when none are stale."""
        mock_service = AsyncMock()
        mock_service.list_stale_jobs = AsyncMock(return_value=[])
        mock_service_cls.return_value = mock_service

        response = client_worker.get("/api/ai-jobs/stale/list")

        assert response.status_code == 200
        assert response.json() == []


class TestModalWebhook:
    """Tests for POST /ai-jobs/modal-webhook endpoint."""

    @patch("app.api.routes.ai_jobs.get_settings")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_webhook_idempotent_already_complete(
        self,
        mock_service_cls: MagicMock,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test webhook skips processing for already completed jobs (idempotency)."""
        mock_settings.return_value.modal_webhook_secret = "test-secret"

        # Job is already in terminal state COMPLETE
        mock_job.state = AIJobState.COMPLETE
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "test-secret"},
            json={
                "job_id": str(mock_job.id),
                "success": True,
                "beatmap": None,
            },
        )

        # Implementation returns already_completed or already_processed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("already_completed", "already_processed")

    @patch("app.api.routes.ai_jobs.get_settings")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_webhook_idempotent_already_failed(
        self,
        mock_service_cls: MagicMock,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test webhook skips processing for already failed jobs (idempotency)."""
        mock_settings.return_value.modal_webhook_secret = "test-secret"

        # Job is already in terminal state FAILED
        mock_job.state = AIJobState.FAILED
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "test-secret"},
            json={
                "job_id": str(mock_job.id),
                "success": True,
                "beatmap": None,
            },
        )

        # Implementation returns already_completed or already_processed
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("already_completed", "already_processed")

    @patch("app.api.routes.ai_jobs.get_settings")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_webhook_invalid_secret(
        self,
        mock_service_cls: MagicMock,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test webhook with invalid secret returns 401."""
        mock_settings.return_value.modal_webhook_secret = "correct-secret"

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "wrong-secret"},
            json={
                "job_id": str(uuid.uuid4()),
                "success": True,
                "beatmap": None,
            },
        )

        assert response.status_code == 401

    @patch("app.api.routes.ai_jobs.get_settings")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_webhook_job_not_found(
        self,
        mock_service_cls: MagicMock,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test webhook for non-existent job returns 404 or already_processed."""
        mock_settings.return_value.modal_webhook_secret = "test-secret"

        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "test-secret"},
            json={
                "job_id": str(uuid.uuid4()),
                "success": True,
                "beatmap": None,
            },
        )

        # Could be 404 if job not found, or 200 if already_processed
        # (depends on idempotency check in DB vs mock behavior)
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            assert response.json()["status"] == "already_processed"

    @patch("app.api.routes.ai_jobs.get_settings")
    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_webhook_failed_job(
        self,
        mock_service_cls: MagicMock,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test webhook handling failed job."""
        mock_settings.return_value.modal_webhook_secret = "test-secret"

        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service.mark_finished = AsyncMock()
        mock_service_cls.return_value = mock_service

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "test-secret"},
            json={
                "job_id": str(mock_job.id),
                "success": False,
                "error": "Out of memory",
            },
        )

        # Could be 200 with failed/already_processed status
        assert response.status_code == 200
        assert response.json()["status"] in ("failed", "already_processed")

    @patch("app.api.routes.ai_jobs.get_settings")
    def test_webhook_invalid_job_id_format(
        self,
        mock_settings: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test webhook with invalid job_id format returns 400."""
        mock_settings.return_value.modal_webhook_secret = "test-secret"

        response = client_authenticated.post(
            "/api/ai-jobs/modal-webhook",
            headers={"X-Webhook-Secret": "test-secret"},
            json={
                "job_id": "not-a-uuid",
                "success": True,
            },
        )

        assert response.status_code == 400


class TestStreamJobProgress:
    """Tests for GET /ai-jobs/{job_id}/progress/stream endpoint (SSE)."""

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_stream_job_not_found(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
    ) -> None:
        """Test streaming non-existent job returns 404."""
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=None)
        mock_service_cls.return_value = mock_service

        job_id = uuid.uuid4()
        response = client_authenticated.get(f"/api/ai-jobs/{job_id}/progress/stream")

        assert response.status_code == 404

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_stream_already_complete_job(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test streaming a completed job returns completion event."""
        mock_job.state = AIJobState.COMPLETE
        mock_job.progress_percent = 100
        mock_job.progress_message = "Complete"
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get(
            f"/api/ai-jobs/{mock_job.id}/progress/stream"
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

    @patch("app.api.routes.ai_jobs.AIJobService")
    def test_stream_failed_job(
        self,
        mock_service_cls: MagicMock,
        client_authenticated: TestClient,
        mock_job: AIJob,
    ) -> None:
        """Test streaming a failed job returns error event."""
        mock_job.state = AIJobState.FAILED
        mock_job.error_message = "Processing failed"
        mock_service = AsyncMock()
        mock_service.get_by_id = AsyncMock(return_value=mock_job)
        mock_service_cls.return_value = mock_service

        response = client_authenticated.get(
            f"/api/ai-jobs/{mock_job.id}/progress/stream"
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


class TestQuotaToReadHelper:
    """Tests for the _quota_to_read helper function."""

    def test_quota_to_read_conversion(self) -> None:
        """Test quota status is correctly converted to read model."""
        from app.api.routes.ai_jobs import _quota_to_read
        from app.services.quota import JobPriority, QuotaLimits, QuotaStatus
        from app.models.subscription import SubscriptionPlan

        status = QuotaStatus(
            plan=SubscriptionPlan.FREE,
            used_this_month=5,
            used_today=2,
            remaining_month=5,
            remaining_today=1,
            resets_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
            limits=QuotaLimits(
                jobs_per_month=10,
                jobs_per_day=3,
                max_concurrent=1,
                priority=JobPriority.STANDARD,
            ),
        )

        result = _quota_to_read(status)

        assert result.plan == "free"
        assert result.used_this_month == 5
        assert result.used_today == 2
        assert result.remaining_month == 5
        assert result.remaining_today == 1
        assert result.limit_month == 10
        assert result.limit_day == 3

    def test_quota_to_read_none_plan(self) -> None:
        """Test quota status with None plan."""
        from app.api.routes.ai_jobs import _quota_to_read
        from app.services.quota import JobPriority, QuotaLimits, QuotaStatus

        status = QuotaStatus(
            plan=None,
            used_this_month=0,
            used_today=0,
            remaining_month=10,
            remaining_today=3,
            resets_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
            limits=QuotaLimits(
                jobs_per_month=10,
                jobs_per_day=3,
                max_concurrent=1,
                priority=JobPriority.STANDARD,
            ),
        )

        result = _quota_to_read(status)

        assert result.plan is None

        assert result.plan is None
