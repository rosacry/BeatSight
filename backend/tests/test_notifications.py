"""Tests for notification service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notifications import (
    EmailBackend,
    NotificationEvent,
    NotificationPayload,
    NotificationResult,
    NotificationService,
    NotificationType,
    WebPushBackend,
)


class TestNotificationPayload:
    """Tests for NotificationPayload dataclass."""

    def test_create_payload_complete(self) -> None:
        """Test creating a complete notification payload."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="Test Song",
            song_artist="Test Artist",
            job_id=uuid.uuid4(),
            result_url="https://beatsight.io/beatmaps/123",
        )
        assert payload.event == NotificationEvent.JOB_COMPLETE
        assert payload.user_email == "test@example.com"

    def test_create_payload_failed(self) -> None:
        """Test creating a failure notification payload."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_FAILED,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="Test Song",
            song_artist="Test Artist",
            job_id=uuid.uuid4(),
            error_message="Model inference failed",
        )
        assert payload.event == NotificationEvent.JOB_FAILED
        assert payload.error_message == "Model inference failed"


class TestEmailBackend:
    """Tests for email notification backend."""

    @pytest.fixture
    def backend(self) -> EmailBackend:
        """Create email backend instance."""
        return EmailBackend(
            api_key="test-api-key",
            from_email="noreply@beatsight.io",
            from_name="BeatSight",
        )

    def test_render_subject_complete(self, backend: EmailBackend) -> None:
        """Test subject line for completed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="My Song",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        subject = backend._render_subject(payload)
        assert "My Song" in subject
        assert "ready" in subject.lower()

    def test_render_subject_failed(self, backend: EmailBackend) -> None:
        """Test subject line for failed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_FAILED,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="My Song",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        subject = backend._render_subject(payload)
        assert "My Song" in subject
        assert "failed" in subject.lower()

    def test_render_body_html_contains_song_info(self, backend: EmailBackend) -> None:
        """Test HTML body contains song information."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="My Test Song",
            song_artist="Test Artist",
            job_id=uuid.uuid4(),
        )
        html = backend._render_body_html(payload)
        assert "My Test Song" in html
        assert "Test Artist" in html

    @pytest.mark.asyncio
    async def test_send_without_email_returns_failure(self, backend: EmailBackend) -> None:
        """Test sending without email address returns failure."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email=None,  # No email
            song_title="Test",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        result = await backend.send(payload)
        assert result.success is False
        assert "No email" in result.message

    @pytest.mark.asyncio
    async def test_send_success_without_api_key(self) -> None:
        """Test email logs successfully when API key not configured."""
        backend = EmailBackend(
            api_key=None,  # No API key - logs instead of sending
            from_email="noreply@beatsight.io",
            from_name="BeatSight",
        )
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="Test",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        result = await backend.send(payload)
        assert result.success is True
        assert result.notification_type == NotificationType.EMAIL
        assert "logged" in result.message.lower()
    
    @pytest.mark.asyncio
    async def test_send_with_mocked_sendgrid(self, backend: EmailBackend) -> None:
        """Test successful email send via SendGrid (mocked)."""
        from unittest.mock import MagicMock, patch
        
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            song_title="Test",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        
        # Mock the sendgrid module
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "test-message-id"}
        
        with patch("sendgrid.SendGridAPIClient") as mock_client:
            mock_client.return_value.send.return_value = mock_response
            result = await backend.send(payload)
        
        assert result.success is True
        assert result.notification_type == NotificationType.EMAIL


class TestWebPushBackend:
    """Tests for WebPush notification backend."""

    @pytest.fixture
    def backend(self) -> WebPushBackend:
        """Create WebPush backend instance."""
        return WebPushBackend(
            vapid_private_key="test-private-key",
            vapid_claims={"sub": "mailto:admin@beatsight.io"},
        )

    def test_build_payload_complete(self, backend: WebPushBackend) -> None:
        """Test building WebPush payload for completed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email=None,
            song_title="My Song",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        push_payload = backend._build_payload(payload)
        assert "Beatmap Ready" in push_payload["title"]
        assert "My Song" in push_payload["body"]

    def test_build_payload_failed(self, backend: WebPushBackend) -> None:
        """Test building WebPush payload for failed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_FAILED,
            user_id=uuid.uuid4(),
            user_email=None,
            song_title="My Song",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        push_payload = backend._build_payload(payload)
        assert "Failed" in push_payload["title"]

    @pytest.mark.asyncio
    async def test_send_success(self, backend: WebPushBackend) -> None:
        """Test successful WebPush send (stub implementation)."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=uuid.uuid4(),
            user_email=None,
            song_title="Test",
            song_artist="Artist",
            job_id=uuid.uuid4(),
        )
        result = await backend.send(payload)
        assert result.success is True
        assert result.notification_type == NotificationType.WEBPUSH


class TestNotificationService:
    """Tests for the notification service."""

    @pytest.fixture
    def email_backend(self) -> EmailBackend:
        """Create mock email backend."""
        backend = EmailBackend("key", "from@test.com")
        return backend

    @pytest.fixture
    def webpush_backend(self) -> WebPushBackend:
        """Create mock WebPush backend."""
        return WebPushBackend("private-key", {"sub": "mailto:test@test.com"})

    @pytest.fixture
    def service(
        self, email_backend: EmailBackend, webpush_backend: WebPushBackend
    ) -> NotificationService:
        """Create notification service with backends."""
        return NotificationService(
            email_backend=email_backend,
            webpush_backend=webpush_backend,
        )

    @pytest.mark.asyncio
    async def test_notify_job_complete(self, service: NotificationService) -> None:
        """Test sending job complete notifications."""
        results = await service.notify_job_complete(
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test Song",
            song_artist="Test Artist",
            result_url="https://beatsight.io/beatmaps/123",
        )
        assert len(results) == 2  # Email + WebPush
        assert any(r.notification_type == NotificationType.EMAIL for r in results)
        assert any(r.notification_type == NotificationType.WEBPUSH for r in results)

    @pytest.mark.asyncio
    async def test_notify_job_failed(self, service: NotificationService) -> None:
        """Test sending job failed notifications."""
        results = await service.notify_job_failed(
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test Song",
            song_artist="Test Artist",
            error_message="Model timeout",
        )
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_notify_job_timeout(self, service: NotificationService) -> None:
        """Test sending job timeout notifications."""
        results = await service.notify_job_timeout(
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test Song",
            song_artist="Test Artist",
        )
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_notify_email_only(self, service: NotificationService) -> None:
        """Test sending email notification only."""
        results = await service.notify_job_complete(
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test Song",
            song_artist="Test Artist",
            send_push=False,
        )
        assert len(results) == 1
        assert results[0].notification_type == NotificationType.EMAIL

    @pytest.mark.asyncio
    async def test_notify_push_only(self, service: NotificationService) -> None:
        """Test sending push notification only."""
        results = await service.notify_job_complete(
            user_id=uuid.uuid4(),
            user_email=None,
            job_id=uuid.uuid4(),
            song_title="Test Song",
            song_artist="Test Artist",
            send_email=False,
        )
        assert len(results) == 1
        assert results[0].notification_type == NotificationType.WEBPUSH

    def test_rate_limit_allows_normal_usage(self, service: NotificationService) -> None:
        """Test rate limiter allows normal usage."""
        user_id = uuid.uuid4()
        for _ in range(5):
            assert service._check_rate_limit(user_id) is True

    def test_rate_limit_blocks_excessive_usage(
        self, service: NotificationService
    ) -> None:
        """Test rate limiter blocks excessive notifications."""
        user_id = uuid.uuid4()
        # Fill up rate limit
        for _ in range(10):
            service._check_rate_limit(user_id)
        # Should now be blocked
        assert service._check_rate_limit(user_id) is False

    @pytest.mark.asyncio
    async def test_rate_limited_user_gets_error(
        self, service: NotificationService
    ) -> None:
        """Test rate limited users receive error response."""
        user_id = uuid.uuid4()
        # Fill up rate limit
        for _ in range(10):
            service._check_rate_limit(user_id)

        results = await service.notify_job_complete(
            user_id=user_id,
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test",
            song_artist="Artist",
        )
        assert len(results) == 1
        assert results[0].success is False
        assert "rate limit" in results[0].message.lower()

    @pytest.mark.asyncio
    async def test_service_without_backends(self) -> None:
        """Test service with no backends configured."""
        service = NotificationService()
        results = await service.notify_job_complete(
            user_id=uuid.uuid4(),
            user_email="test@example.com",
            job_id=uuid.uuid4(),
            song_title="Test",
            song_artist="Artist",
        )
        assert len(results) == 0
