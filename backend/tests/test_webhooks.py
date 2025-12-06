"""Tests for webhook utilities."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.webhooks import (
    WebhookClient,
    WebhookConfig,
    WebhookEvent,
    WebhookEventType,
    WebhookPayload,
    WebhookResult,
    WebhookStatus,
    WebhookSubscription,
    create_event_payload,
    generate_webhook_headers,
    sign_webhook_payload,
    verify_webhook_signature,
)


# =============================================================================
# WebhookEventType Tests
# =============================================================================


class TestWebhookEventType:
    """Tests for WebhookEventType enum."""

    def test_event_type_values(self):
        """Test event type values."""
        assert WebhookEventType.SONG_CREATED.value == "song.created"
        assert WebhookEventType.BEATMAP_PUBLISHED.value == "beatmap.published"
        assert WebhookEventType.CREDITS_PURCHASED.value == "credits.purchased"

    def test_all_event_types_are_strings(self):
        """Test all event types have string values."""
        for event_type in WebhookEventType:
            assert isinstance(event_type.value, str)
            assert "." in event_type.value or event_type.value in ("test", "custom")


# =============================================================================
# WebhookStatus Tests
# =============================================================================


class TestWebhookStatus:
    """Tests for WebhookStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert WebhookStatus.PENDING.value == "pending"
        assert WebhookStatus.DELIVERED.value == "delivered"
        assert WebhookStatus.FAILED.value == "failed"
        assert WebhookStatus.RETRYING.value == "retrying"


# =============================================================================
# Signing Tests
# =============================================================================


class TestSignWebhookPayload:
    """Tests for sign_webhook_payload function."""

    def test_sign_payload_basic(self):
        """Test basic payload signing."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        signature, timestamp = sign_webhook_payload(payload, secret)

        assert signature is not None
        assert len(signature) == 64  # SHA256 hex is 64 chars
        assert timestamp > 0

    def test_sign_payload_with_timestamp(self):
        """Test signing with custom timestamp."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        custom_timestamp = 1234567890

        signature, timestamp = sign_webhook_payload(payload, secret, custom_timestamp)

        assert timestamp == custom_timestamp

    def test_sign_payload_bytes(self):
        """Test signing bytes payload."""
        payload = b'{"test": "data"}'
        secret = "test_secret"

        signature, _ = sign_webhook_payload(payload, secret)

        assert signature is not None
        assert len(signature) == 64

    def test_same_payload_same_signature(self):
        """Test same payload produces same signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        timestamp = 1234567890

        sig1, _ = sign_webhook_payload(payload, secret, timestamp)
        sig2, _ = sign_webhook_payload(payload, secret, timestamp)

        assert sig1 == sig2

    def test_different_secret_different_signature(self):
        """Test different secrets produce different signatures."""
        payload = '{"test": "data"}'
        timestamp = 1234567890

        sig1, _ = sign_webhook_payload(payload, "secret1", timestamp)
        sig2, _ = sign_webhook_payload(payload, "secret2", timestamp)

        assert sig1 != sig2

    def test_different_payload_different_signature(self):
        """Test different payloads produce different signatures."""
        secret = "test_secret"
        timestamp = 1234567890

        sig1, _ = sign_webhook_payload('{"a": 1}', secret, timestamp)
        sig2, _ = sign_webhook_payload('{"b": 2}', secret, timestamp)

        assert sig1 != sig2


class TestVerifyWebhookSignature:
    """Tests for verify_webhook_signature function."""

    def test_verify_valid_signature(self):
        """Test verifying a valid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        timestamp = int(time.time())

        signature, _ = sign_webhook_payload(payload, secret, timestamp)

        is_valid = verify_webhook_signature(payload, signature, timestamp, secret)

        assert is_valid is True

    def test_reject_invalid_signature(self):
        """Test rejecting invalid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        timestamp = int(time.time())

        is_valid = verify_webhook_signature(
            payload, "invalid_signature", timestamp, secret
        )

        assert is_valid is False

    def test_reject_expired_timestamp(self):
        """Test rejecting expired timestamp."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        old_timestamp = int(time.time()) - 600  # 10 minutes ago

        signature, _ = sign_webhook_payload(payload, secret, old_timestamp)

        is_valid = verify_webhook_signature(
            payload,
            signature,
            old_timestamp,
            secret,
            tolerance_seconds=300,  # 5 minute tolerance
        )

        assert is_valid is False

    def test_accept_timestamp_within_tolerance(self):
        """Test accepting timestamp within tolerance."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        recent_timestamp = int(time.time()) - 60  # 1 minute ago

        signature, _ = sign_webhook_payload(payload, secret, recent_timestamp)

        is_valid = verify_webhook_signature(
            payload,
            signature,
            recent_timestamp,
            secret,
            tolerance_seconds=300,
        )

        assert is_valid is True

    def test_reject_wrong_secret(self):
        """Test rejecting signature with wrong secret."""
        payload = '{"test": "data"}'
        timestamp = int(time.time())

        signature, _ = sign_webhook_payload(payload, "correct_secret", timestamp)

        is_valid = verify_webhook_signature(
            payload, signature, timestamp, "wrong_secret"
        )

        assert is_valid is False


class TestGenerateWebhookHeaders:
    """Tests for generate_webhook_headers function."""

    def test_generate_headers(self):
        """Test generating webhook headers."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        headers = generate_webhook_headers(payload, secret)

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "X-Webhook-Id" in headers
        assert "X-Webhook-Timestamp" in headers
        assert "X-Webhook-Signature" in headers
        assert headers["X-Webhook-Signature"].startswith("sha256=")

    def test_generate_headers_with_webhook_id(self):
        """Test generating headers with custom webhook ID."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        webhook_id = "custom-id-123"

        headers = generate_webhook_headers(payload, secret, webhook_id)

        assert headers["X-Webhook-Id"] == webhook_id


# =============================================================================
# WebhookPayload Tests
# =============================================================================


class TestWebhookPayload:
    """Tests for WebhookPayload class."""

    def test_payload_defaults(self):
        """Test payload default values."""
        payload = WebhookPayload(event_type="test.event")

        assert payload.id is not None
        assert payload.event_type == "test.event"
        assert payload.timestamp is not None
        assert payload.api_version == "2024-01-01"
        assert payload.data == {}

    def test_payload_with_data(self):
        """Test payload with custom data."""
        payload = WebhookPayload(
            event_type="song.created",
            data={"song_id": "123", "title": "Test Song"},
        )

        assert payload.event_type == "song.created"
        assert payload.data["song_id"] == "123"

    def test_payload_serialization(self):
        """Test payload serializes correctly."""
        payload = WebhookPayload(
            id="test-id",
            event_type="test.event",
            data={"key": "value"},
        )

        data = payload.model_dump(by_alias=True)

        assert "eventType" in data
        assert "apiVersion" in data
        assert data["eventType"] == "test.event"


# =============================================================================
# WebhookResult Tests
# =============================================================================


class TestWebhookResult:
    """Tests for WebhookResult class."""

    def test_success_result(self):
        """Test successful webhook result."""
        result = WebhookResult(
            success=True,
            status_code=200,
            response_body="OK",
            attempts=1,
            delivery_time_ms=50.5,
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.error is None

    def test_failure_result(self):
        """Test failed webhook result."""
        result = WebhookResult(
            success=False,
            status_code=500,
            error="Server error",
            attempts=3,
        )

        assert result.success is False
        assert result.error == "Server error"
        assert result.attempts == 3


# =============================================================================
# WebhookConfig Tests
# =============================================================================


class TestWebhookConfig:
    """Tests for WebhookConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WebhookConfig()

        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 1.0
        assert config.retry_backoff_multiplier == 2.0
        assert config.max_retry_delay_seconds == 60.0
        assert config.verify_ssl is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = WebhookConfig(
            timeout_seconds=10.0,
            max_retries=5,
            verify_ssl=False,
        )

        assert config.timeout_seconds == 10.0
        assert config.max_retries == 5
        assert config.verify_ssl is False


# =============================================================================
# WebhookClient Tests
# =============================================================================


class TestWebhookClient:
    """Tests for WebhookClient class."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = WebhookClient()

        assert client.config is not None
        assert client.config.timeout_seconds == 30.0

    def test_client_with_custom_config(self):
        """Test client with custom config."""
        config = WebhookConfig(timeout_seconds=10.0)
        client = WebhookClient(config)

        assert client.config.timeout_seconds == 10.0

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful webhook send."""
        client = WebhookClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.send(
                url="https://example.com/webhook",
                event_type="test.event",
                payload={"test": "data"},
                secret="test_secret",
            )

        assert result.success is True
        assert result.status_code == 200
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_send_client_error_no_retry(self):
        """Test client error (4xx) does not retry."""
        config = WebhookConfig(max_retries=3)
        client = WebhookClient(config)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.send(
                url="https://example.com/webhook",
                event_type="test.event",
                payload={"test": "data"},
            )

        assert result.success is False
        assert result.status_code == 400
        assert result.attempts == 1  # No retries for 4xx


# =============================================================================
# WebhookEvent Tests
# =============================================================================


class TestWebhookEvent:
    """Tests for WebhookEvent class."""

    def test_event_creation(self):
        """Test event creation."""
        event = WebhookEvent(
            event_type="song.created",
            payload={"song_id": "123"},
        )

        assert event.id is not None
        assert event.event_type == "song.created"
        assert event.payload["song_id"] == "123"

    def test_event_with_targeting(self):
        """Test event with targeting info."""
        event = WebhookEvent(
            event_type="song.created",
            payload={"title": "Test"},
            user_id="user-123",
            resource_id="song-456",
            resource_type="song",
        )

        assert event.user_id == "user-123"
        assert event.resource_id == "song-456"
        assert event.resource_type == "song"


# =============================================================================
# WebhookSubscription Tests
# =============================================================================


class TestWebhookSubscription:
    """Tests for WebhookSubscription class."""

    def test_subscription_creation(self):
        """Test subscription creation."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            event_types=["song.created", "song.updated"],
        )

        assert sub.id is not None
        assert sub.url == "https://example.com/webhook"
        assert sub.is_active is True
        assert len(sub.event_types) == 2

    def test_matches_event_by_type(self):
        """Test subscription matches event by type."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            event_types=["song.created", "song.updated"],
        )

        matching_event = WebhookEvent(event_type="song.created", payload={})
        non_matching_event = WebhookEvent(event_type="beatmap.created", payload={})

        assert sub.matches_event(matching_event) is True
        assert sub.matches_event(non_matching_event) is False

    def test_matches_wildcard_event_type(self):
        """Test subscription matches wildcard event types."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            event_types=["song.*"],
        )

        event1 = WebhookEvent(event_type="song.created", payload={})
        event2 = WebhookEvent(event_type="song.updated", payload={})
        event3 = WebhookEvent(event_type="beatmap.created", payload={})

        assert sub.matches_event(event1) is True
        assert sub.matches_event(event2) is True
        assert sub.matches_event(event3) is False

    def test_inactive_subscription_no_match(self):
        """Test inactive subscription doesn't match."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            event_types=["song.created"],
            is_active=False,
        )

        event = WebhookEvent(event_type="song.created", payload={})

        assert sub.matches_event(event) is False

    def test_matches_user_filter(self):
        """Test subscription filters by user."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            user_id="user-123",
        )

        matching_event = WebhookEvent(
            event_type="song.created",
            payload={},
            user_id="user-123",
        )
        non_matching_event = WebhookEvent(
            event_type="song.created",
            payload={},
            user_id="user-456",
        )

        assert sub.matches_event(matching_event) is True
        assert sub.matches_event(non_matching_event) is False

    def test_matches_resource_type_filter(self):
        """Test subscription filters by resource type."""
        sub = WebhookSubscription(
            url="https://example.com/webhook",
            secret="test_secret",
            resource_types=["song", "beatmap"],
        )

        matching_event = WebhookEvent(
            event_type="test.event",
            payload={},
            resource_type="song",
        )
        non_matching_event = WebhookEvent(
            event_type="test.event",
            payload={},
            resource_type="user",
        )

        assert sub.matches_event(matching_event) is True
        assert sub.matches_event(non_matching_event) is False


# =============================================================================
# create_event_payload Tests
# =============================================================================


class TestCreateEventPayload:
    """Tests for create_event_payload function."""

    def test_create_basic_event(self):
        """Test creating basic event."""
        event = create_event_payload(
            event_type="test.event",
            test_key="test_value",
        )

        assert event.event_type == "test.event"
        assert event.payload["test_key"] == "test_value"

    def test_create_event_with_enum(self):
        """Test creating event with enum type."""
        event = create_event_payload(
            event_type=WebhookEventType.SONG_CREATED,
            song_id="123",
        )

        assert event.event_type == "song.created"
        assert event.payload["song_id"] == "123"

    def test_create_event_with_targeting(self):
        """Test creating event with targeting."""
        event = create_event_payload(
            event_type="song.created",
            resource_id="song-123",
            resource_type="song",
            user_id="user-456",
            title="Test Song",
        )

        assert event.resource_id == "song-123"
        assert event.resource_type == "song"
        assert event.user_id == "user-456"
        assert event.payload["title"] == "Test Song"
