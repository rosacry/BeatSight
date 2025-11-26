"""Tests for alert service (E6-003: Alert Thresholds)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alerts import (
    Alert,
    AlertService,
    AlertSeverity,
    AlertThreshold,
    AlertType,
    InMemoryChannel,
    WebhookChannel,
    get_alert_service,
    reset_alert_service,
)


# =============================================================================
# Alert Model Tests
# =============================================================================


class TestAlert:
    """Tests for Alert dataclass."""

    def test_create_alert(self) -> None:
        """Create a basic alert."""
        alert = Alert(
            alert_type=AlertType.JOB_FAILURE_RATE,
            severity=AlertSeverity.WARNING,
            title="High Failure Rate",
            message="Job failure rate is 15%",
            metric_value=15.0,
            threshold_value=10.0,
            source="job_processor",
        )

        assert alert.alert_type == AlertType.JOB_FAILURE_RATE
        assert alert.severity == AlertSeverity.WARNING
        assert alert.metric_value == 15.0
        assert not alert.resolved

    def test_alert_fingerprint_consistent(self) -> None:
        """Fingerprint should be consistent for same alert type/title/source."""
        alert1 = Alert(
            alert_type=AlertType.JOB_FAILURE_RATE,
            title="High Failure Rate",
            source="test",
        )
        alert2 = Alert(
            alert_type=AlertType.JOB_FAILURE_RATE,
            title="High Failure Rate",
            source="test",
            message="Different message",  # Message doesn't affect fingerprint
        )

        assert alert1.fingerprint == alert2.fingerprint

    def test_alert_fingerprint_different(self) -> None:
        """Different alerts should have different fingerprints."""
        alert1 = Alert(
            alert_type=AlertType.JOB_FAILURE_RATE, title="Title 1", source="test"
        )
        alert2 = Alert(alert_type=AlertType.QUEUE_DEPTH, title="Title 2", source="test")

        assert alert1.fingerprint != alert2.fingerprint


class TestAlertThreshold:
    """Tests for AlertThreshold dataclass."""

    def test_create_threshold(self) -> None:
        """Create alert threshold configuration."""
        threshold = AlertThreshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            warning_threshold=10.0,
            critical_threshold=25.0,
            evaluation_window_minutes=15,
            cooldown_minutes=30,
        )

        assert threshold.alert_type == AlertType.JOB_FAILURE_RATE
        assert threshold.warning_threshold == 10.0
        assert threshold.critical_threshold == 25.0
        assert threshold.enabled is True

    def test_threshold_disabled(self) -> None:
        """Create disabled threshold."""
        threshold = AlertThreshold(
            alert_type=AlertType.QUEUE_DEPTH,
            warning_threshold=100,
            critical_threshold=500,
            enabled=False,
        )

        assert threshold.enabled is False


# =============================================================================
# InMemoryChannel Tests
# =============================================================================


class TestInMemoryChannel:
    """Tests for in-memory alert channel."""

    @pytest.mark.asyncio
    async def test_send_alert(self) -> None:
        """Store alert in memory."""
        channel = InMemoryChannel()
        alert = Alert(alert_type=AlertType.CUSTOM, title="Test", message="Test message")

        result = await channel.send(alert)

        assert result.success is True
        assert result.channel == "in_memory"
        assert len(channel.alerts) == 1
        assert channel.alerts[0] == alert

    @pytest.mark.asyncio
    async def test_max_alerts_limit(self) -> None:
        """Channel should trim old alerts when limit exceeded."""
        channel = InMemoryChannel(max_alerts=5)

        for i in range(10):
            alert = Alert(alert_type=AlertType.CUSTOM, title=f"Alert {i}")
            await channel.send(alert)

        assert len(channel.alerts) == 5
        assert channel.alerts[0].title == "Alert 5"  # First kept

    def test_get_recent(self) -> None:
        """Get recent alerts with optional filtering."""
        channel = InMemoryChannel()

        # Add alerts synchronously for testing
        channel.alerts = [
            Alert(
                alert_type=AlertType.CUSTOM, severity=AlertSeverity.INFO, title="Info 1"
            ),
            Alert(
                alert_type=AlertType.CUSTOM,
                severity=AlertSeverity.WARNING,
                title="Warning 1",
            ),
            Alert(
                alert_type=AlertType.CUSTOM,
                severity=AlertSeverity.CRITICAL,
                title="Critical 1",
            ),
        ]

        all_alerts = channel.get_recent(limit=10)
        assert len(all_alerts) == 3

        warnings_only = channel.get_recent(severity=AlertSeverity.WARNING)
        assert len(warnings_only) == 1
        assert warnings_only[0].title == "Warning 1"

    def test_clear(self) -> None:
        """Clear all stored alerts."""
        channel = InMemoryChannel()
        channel.alerts = [Alert(alert_type=AlertType.CUSTOM, title="Test")]

        channel.clear()

        assert len(channel.alerts) == 0


# =============================================================================
# WebhookChannel Tests
# =============================================================================


class TestWebhookChannel:
    """Tests for webhook alert channel."""

    def test_format_slack(self) -> None:
        """Format alert for Slack webhook."""
        channel = WebhookChannel(
            webhook_url="https://hooks.slack.com/test",
            channel_name="slack",
            format_type="slack",
        )
        alert = Alert(
            alert_type=AlertType.JOB_FAILURE_RATE,
            severity=AlertSeverity.CRITICAL,
            title="High Failure Rate",
            message="15% of jobs failing",
            metric_value=15.0,
            threshold_value=10.0,
            source="test",
        )

        payload = channel._format_slack(alert)

        assert "attachments" in payload
        assert payload["attachments"][0]["color"] == "#ff0000"  # Red for critical
        assert "High Failure Rate" in payload["attachments"][0]["title"]

    def test_format_discord(self) -> None:
        """Format alert for Discord webhook."""
        channel = WebhookChannel(
            webhook_url="https://discord.com/api/webhooks/test",
            channel_name="discord",
            format_type="discord",
        )
        alert = Alert(
            alert_type=AlertType.QUEUE_DEPTH,
            severity=AlertSeverity.WARNING,
            title="Queue Depth High",
            message="500 jobs in queue",
            metric_value=500.0,
            source="queue",
        )

        payload = channel._format_discord(alert)

        assert "embeds" in payload
        assert payload["embeds"][0]["color"] == 0xFF9900  # Orange for warning

    def test_format_pagerduty(self) -> None:
        """Format alert for PagerDuty."""
        channel = WebhookChannel(
            webhook_url="test-routing-key",
            channel_name="pagerduty",
            format_type="pagerduty",
        )
        alert = Alert(
            alert_type=AlertType.WORKER_OFFLINE,
            severity=AlertSeverity.CRITICAL,
            title="Worker Offline",
            message="Worker-1 not responding",
            source="worker_monitor",
        )

        payload = channel._format_pagerduty(alert)

        assert payload["routing_key"] == "test-routing-key"
        assert payload["event_action"] == "trigger"
        assert payload["dedup_key"] == alert.fingerprint
        assert payload["payload"]["severity"] == "critical"

    def test_format_generic(self) -> None:
        """Format alert as generic JSON."""
        channel = WebhookChannel(
            webhook_url="https://example.com/webhook",
            format_type="generic",
        )
        alert = Alert(
            alert_type=AlertType.CUSTOM,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            message="Test message",
        )

        payload = channel._format_generic(alert)

        assert payload["type"] == "custom"
        assert payload["severity"] == "info"
        assert payload["title"] == "Test Alert"

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """Successfully send webhook."""
        channel = WebhookChannel(
            webhook_url="https://hooks.slack.com/test",
            format_type="slack",
        )
        alert = Alert(alert_type=AlertType.CUSTOM, title="Test")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await channel.send(alert)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_send_failure(self) -> None:
        """Handle webhook failure."""
        channel = WebhookChannel(
            webhook_url="https://hooks.slack.com/test",
            format_type="slack",
        )
        alert = Alert(alert_type=AlertType.CUSTOM, title="Test")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await channel.send(alert)

            assert result.success is False
            assert "500" in result.message


# =============================================================================
# AlertService Tests
# =============================================================================


class TestAlertService:
    """Tests for main alert service."""

    def test_default_thresholds(self) -> None:
        """Service should have default thresholds."""
        service = AlertService()

        assert AlertType.JOB_FAILURE_RATE in service.thresholds
        assert AlertType.QUEUE_DEPTH in service.thresholds
        assert AlertType.WORKER_OFFLINE in service.thresholds
        assert AlertType.API_ERROR_RATE in service.thresholds

    def test_set_threshold(self) -> None:
        """Set custom threshold."""
        service = AlertService()

        custom_threshold = AlertThreshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            warning_threshold=5.0,  # More sensitive
            critical_threshold=15.0,
        )

        service.set_threshold(custom_threshold)

        assert service.thresholds[AlertType.JOB_FAILURE_RATE].warning_threshold == 5.0

    def test_add_channel(self) -> None:
        """Add alert channel."""
        service = AlertService()
        channel = InMemoryChannel()

        service.add_channel(channel)

        assert len(service.channels) == 1

    @pytest.mark.asyncio
    async def test_send_alert(self) -> None:
        """Send alert through all channels."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = Alert(
            alert_type=AlertType.CUSTOM,
            title="Test Alert",
            message="Test message",
        )

        results = await service.send_alert(alert)

        assert len(results) == 1
        assert results[0].success is True
        assert len(channel.alerts) == 1

    @pytest.mark.asyncio
    async def test_cooldown_prevents_duplicate_alerts(self) -> None:
        """Cooldown should prevent repeated alerts."""
        service = AlertService()
        service.thresholds[AlertType.CUSTOM] = AlertThreshold(
            alert_type=AlertType.CUSTOM,
            warning_threshold=0,
            critical_threshold=0,
            cooldown_minutes=60,
        )
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = Alert(alert_type=AlertType.CUSTOM, title="Test", source="test")

        # First alert should succeed
        results1 = await service.send_alert(alert)
        assert len(results1) == 1

        # Second alert with same fingerprint should be blocked
        results2 = await service.send_alert(alert)
        assert len(results2) == 0

    @pytest.mark.asyncio
    async def test_check_threshold_no_alert_below_threshold(self) -> None:
        """No alert when value is below threshold."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = await service.check_threshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            current_value=5.0,  # Below 10% warning threshold
        )

        assert alert is None
        assert len(channel.alerts) == 0

    @pytest.mark.asyncio
    async def test_check_threshold_warning(self) -> None:
        """Warning alert when value exceeds warning threshold."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = await service.check_threshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            current_value=15.0,  # Above 10% warning, below 25% critical
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING
        assert len(channel.alerts) == 1

    @pytest.mark.asyncio
    async def test_check_threshold_critical(self) -> None:
        """Critical alert when value exceeds critical threshold."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = await service.check_threshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            current_value=30.0,  # Above 25% critical threshold
        )

        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_check_threshold_disabled(self) -> None:
        """No alert when threshold is disabled."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        service.thresholds[AlertType.JOB_FAILURE_RATE].enabled = False

        alert = await service.check_threshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            current_value=50.0,  # Way over threshold
        )

        assert alert is None

    @pytest.mark.asyncio
    async def test_alert_job_failure_rate(self) -> None:
        """Convenience method for job failure rate alert."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = await service.alert_job_failure_rate(
            failure_rate=20.0,
            total_jobs=100,
            failed_jobs=20,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.JOB_FAILURE_RATE
        assert alert.metadata["total_jobs"] == 100
        assert alert.metadata["failed_jobs"] == 20

    @pytest.mark.asyncio
    async def test_alert_queue_depth(self) -> None:
        """Convenience method for queue depth alert."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        alert = await service.alert_queue_depth(
            queue_depth=200,
            queue_name="ai_jobs",
        )

        assert alert is not None
        assert alert.alert_type == AlertType.QUEUE_DEPTH
        assert alert.metadata["queue_name"] == "ai_jobs"

    @pytest.mark.asyncio
    async def test_alert_worker_offline(self) -> None:
        """Convenience method for worker offline alert."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        last_seen = datetime.now(timezone.utc) - timedelta(minutes=10)

        alert = await service.alert_worker_offline(
            worker_id="worker-1",
            last_seen=last_seen,
            offline_workers=2,
        )

        assert alert is not None
        assert alert.alert_type == AlertType.WORKER_OFFLINE
        assert alert.metadata["worker_id"] == "worker-1"

    @pytest.mark.asyncio
    async def test_alert_custom(self) -> None:
        """Send custom alert."""
        service = AlertService()
        channel = InMemoryChannel()
        service.add_channel(channel)

        results = await service.alert_custom(
            title="Custom Alert",
            message="Something happened",
            severity=AlertSeverity.INFO,
            source="test",
            metadata={"key": "value"},
        )

        assert len(results) == 1
        assert results[0].success is True
        assert channel.alerts[0].title == "Custom Alert"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetAlertService:
    """Tests for alert service factory."""

    def test_get_alert_service_singleton(self) -> None:
        """Factory should return singleton instance."""
        reset_alert_service()  # Ensure clean state

        service1 = get_alert_service()
        service2 = get_alert_service()

        assert service1 is service2

        reset_alert_service()  # Clean up

    def test_get_alert_service_with_in_memory_channel(self) -> None:
        """Service should always have in-memory channel."""
        reset_alert_service()

        with patch("app.services.alerts.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                slack_webhook_url=None,
                discord_webhook_url=None,
                pagerduty_routing_key=None,
            )

            service = get_alert_service()

        # Should have at least the in-memory channel
        assert len(service.channels) >= 1
        assert any(isinstance(c, InMemoryChannel) for c in service.channels)

        reset_alert_service()

    def test_reset_alert_service(self) -> None:
        """Reset should clear singleton."""
        service1 = get_alert_service()
        reset_alert_service()
        service2 = get_alert_service()

        assert service1 is not service2

        reset_alert_service()
