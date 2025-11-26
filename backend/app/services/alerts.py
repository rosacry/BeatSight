"""Alert service for operational monitoring and thresholds.

Provides configurable alerting for:
- Job failure rate thresholds
- Queue depth thresholds
- System health metrics
- Worker heartbeat monitoring

Supports multiple alert channels:
- Webhook (Slack, Discord, PagerDuty, etc.)
- Email (admin notifications)
- In-app (admin dashboard)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of operational alerts."""

    JOB_FAILURE_RATE = "job_failure_rate"
    QUEUE_DEPTH = "queue_depth"
    WORKER_OFFLINE = "worker_offline"
    SYSTEM_ERROR = "system_error"
    STORAGE_QUOTA = "storage_quota"
    API_ERROR_RATE = "api_error_rate"
    CUSTOM = "custom"


@dataclass
class AlertThreshold:
    """Configuration for an alert threshold."""

    alert_type: AlertType
    warning_threshold: float
    critical_threshold: float
    evaluation_window_minutes: int = 5
    cooldown_minutes: int = 15  # Minimum time between repeated alerts
    enabled: bool = True


@dataclass
class Alert:
    """Represents an operational alert."""

    id: UUID = field(default_factory=uuid4)
    alert_type: AlertType = AlertType.CUSTOM
    severity: AlertSeverity = AlertSeverity.WARNING
    title: str = ""
    message: str = ""
    metric_value: float | None = None
    threshold_value: float | None = None
    source: str = "system"  # Component that triggered the alert
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    resolved_at: datetime | None = None

    @property
    def fingerprint(self) -> str:
        """Generate fingerprint for deduplication."""
        data = f"{self.alert_type.value}:{self.title}:{self.source}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class AlertResult:
    """Result of sending an alert."""

    channel: str
    success: bool
    message: str | None = None
    response_data: dict[str, Any] | None = None


class AlertChannel(ABC):
    """Abstract base class for alert channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name."""
        ...

    @abstractmethod
    async def send(self, alert: Alert) -> AlertResult:
        """Send an alert through this channel."""
        ...


class WebhookChannel(AlertChannel):
    """Generic webhook channel for Slack, Discord, PagerDuty, etc."""

    def __init__(
        self,
        webhook_url: str,
        channel_name: str = "webhook",
        format_type: str = "slack",  # slack, discord, pagerduty, generic
        headers: dict[str, str] | None = None,
    ):
        self.webhook_url = webhook_url
        self._channel_name = channel_name
        self.format_type = format_type
        self.headers = headers or {}

    @property
    def name(self) -> str:
        return self._channel_name

    def _format_slack(self, alert: Alert) -> dict[str, Any]:
        """Format alert for Slack webhook."""
        color = {
            AlertSeverity.INFO: "#36a64f",  # Green
            AlertSeverity.WARNING: "#ff9900",  # Orange
            AlertSeverity.CRITICAL: "#ff0000",  # Red
        }.get(alert.severity, "#808080")

        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
        }.get(alert.severity, "❓")

        fields = []
        if alert.metric_value is not None:
            fields.append({
                "title": "Current Value",
                "value": f"{alert.metric_value:.2f}",
                "short": True,
            })
        if alert.threshold_value is not None:
            fields.append({
                "title": "Threshold",
                "value": f"{alert.threshold_value:.2f}",
                "short": True,
            })
        fields.append({
            "title": "Source",
            "value": alert.source,
            "short": True,
        })
        fields.append({
            "title": "Alert Type",
            "value": alert.alert_type.value,
            "short": True,
        })

        return {
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} {alert.title}",
                    "text": alert.message,
                    "fields": fields,
                    "footer": "BeatSight Alert System",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }

    def _format_discord(self, alert: Alert) -> dict[str, Any]:
        """Format alert for Discord webhook."""
        color = {
            AlertSeverity.INFO: 0x36A64F,  # Green
            AlertSeverity.WARNING: 0xFF9900,  # Orange
            AlertSeverity.CRITICAL: 0xFF0000,  # Red
        }.get(alert.severity, 0x808080)

        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
        }.get(alert.severity, "❓")

        fields = []
        if alert.metric_value is not None:
            fields.append({
                "name": "Current Value",
                "value": f"{alert.metric_value:.2f}",
                "inline": True,
            })
        if alert.threshold_value is not None:
            fields.append({
                "name": "Threshold",
                "value": f"{alert.threshold_value:.2f}",
                "inline": True,
            })
        fields.append({"name": "Source", "value": alert.source, "inline": True})

        return {
            "embeds": [
                {
                    "title": f"{emoji} {alert.title}",
                    "description": alert.message,
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "BeatSight Alert System"},
                    "timestamp": alert.timestamp.isoformat(),
                }
            ]
        }

    def _format_pagerduty(self, alert: Alert) -> dict[str, Any]:
        """Format alert for PagerDuty Events API v2."""
        severity = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.CRITICAL: "critical",
        }.get(alert.severity, "warning")

        return {
            "routing_key": self.webhook_url,  # For PD, webhook_url is routing key
            "event_action": "trigger",
            "dedup_key": alert.fingerprint,
            "payload": {
                "summary": f"[{alert.severity.value.upper()}] {alert.title}",
                "source": alert.source,
                "severity": severity,
                "custom_details": {
                    "message": alert.message,
                    "metric_value": alert.metric_value,
                    "threshold_value": alert.threshold_value,
                    "alert_type": alert.alert_type.value,
                    **alert.metadata,
                },
            },
        }

    def _format_generic(self, alert: Alert) -> dict[str, Any]:
        """Format alert as generic JSON."""
        return {
            "id": str(alert.id),
            "type": alert.alert_type.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "metric_value": alert.metric_value,
            "threshold_value": alert.threshold_value,
            "source": alert.source,
            "metadata": alert.metadata,
            "timestamp": alert.timestamp.isoformat(),
        }

    async def send(self, alert: Alert) -> AlertResult:
        """Send alert via webhook."""
        try:
            # Format payload based on type
            if self.format_type == "slack":
                payload = self._format_slack(alert)
            elif self.format_type == "discord":
                payload = self._format_discord(alert)
            elif self.format_type == "pagerduty":
                payload = self._format_pagerduty(alert)
            else:
                payload = self._format_generic(alert)

            async with httpx.AsyncClient(timeout=10.0) as client:
                # For PagerDuty, use the Events API endpoint
                url = (
                    "https://events.pagerduty.com/v2/enqueue"
                    if self.format_type == "pagerduty"
                    else self.webhook_url
                )

                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json", **self.headers},
                )

                if response.status_code < 400:
                    log.info(
                        "alert_sent",
                        channel=self.name,
                        alert_type=alert.alert_type.value,
                        severity=alert.severity.value,
                    )
                    return AlertResult(
                        channel=self.name,
                        success=True,
                        response_data={"status_code": response.status_code},
                    )
                else:
                    log.error(
                        "alert_send_failed",
                        channel=self.name,
                        status_code=response.status_code,
                        response=response.text[:200],
                    )
                    return AlertResult(
                        channel=self.name,
                        success=False,
                        message=f"HTTP {response.status_code}: {response.text[:100]}",
                    )

        except Exception as e:
            log.error("alert_send_error", channel=self.name, error=str(e))
            return AlertResult(
                channel=self.name,
                success=False,
                message=str(e),
            )


class InMemoryChannel(AlertChannel):
    """In-memory channel for testing and admin dashboard."""

    def __init__(self, max_alerts: int = 1000):
        self.alerts: list[Alert] = []
        self.max_alerts = max_alerts

    @property
    def name(self) -> str:
        return "in_memory"

    async def send(self, alert: Alert) -> AlertResult:
        """Store alert in memory."""
        self.alerts.append(alert)
        
        # Trim if over limit
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts :]
        
        return AlertResult(channel=self.name, success=True)

    def get_recent(self, limit: int = 50, severity: AlertSeverity | None = None) -> list[Alert]:
        """Get recent alerts, optionally filtered by severity."""
        alerts = self.alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:limit]

    def clear(self) -> None:
        """Clear all alerts."""
        self.alerts = []


class AlertService:
    """Service for managing operational alerts."""

    def __init__(self) -> None:
        self.channels: list[AlertChannel] = []
        self.thresholds: dict[AlertType, AlertThreshold] = {}
        self._cooldowns: dict[str, datetime] = {}  # fingerprint -> last alert time
        self._metrics_cache: dict[str, list[tuple[datetime, float]]] = {}
        
        # Default thresholds
        self._set_default_thresholds()

    def _set_default_thresholds(self) -> None:
        """Set default alert thresholds."""
        self.thresholds = {
            AlertType.JOB_FAILURE_RATE: AlertThreshold(
                alert_type=AlertType.JOB_FAILURE_RATE,
                warning_threshold=10.0,  # 10% failure rate
                critical_threshold=25.0,  # 25% failure rate
                evaluation_window_minutes=15,
                cooldown_minutes=30,
            ),
            AlertType.QUEUE_DEPTH: AlertThreshold(
                alert_type=AlertType.QUEUE_DEPTH,
                warning_threshold=100,  # 100 jobs in queue
                critical_threshold=500,  # 500 jobs in queue
                evaluation_window_minutes=5,
                cooldown_minutes=15,
            ),
            AlertType.WORKER_OFFLINE: AlertThreshold(
                alert_type=AlertType.WORKER_OFFLINE,
                warning_threshold=1,  # 1 worker offline
                critical_threshold=3,  # 3+ workers offline
                evaluation_window_minutes=5,
                cooldown_minutes=10,
            ),
            AlertType.API_ERROR_RATE: AlertThreshold(
                alert_type=AlertType.API_ERROR_RATE,
                warning_threshold=5.0,  # 5% error rate
                critical_threshold=15.0,  # 15% error rate
                evaluation_window_minutes=5,
                cooldown_minutes=15,
            ),
            AlertType.STORAGE_QUOTA: AlertThreshold(
                alert_type=AlertType.STORAGE_QUOTA,
                warning_threshold=80.0,  # 80% storage used
                critical_threshold=95.0,  # 95% storage used
                evaluation_window_minutes=60,
                cooldown_minutes=60,
            ),
        }

    def add_channel(self, channel: AlertChannel) -> None:
        """Add an alert channel."""
        self.channels.append(channel)
        log.info("alert_channel_added", channel=channel.name)

    def set_threshold(self, threshold: AlertThreshold) -> None:
        """Set or update an alert threshold."""
        self.thresholds[threshold.alert_type] = threshold
        log.info(
            "alert_threshold_set",
            alert_type=threshold.alert_type.value,
            warning=threshold.warning_threshold,
            critical=threshold.critical_threshold,
        )

    def get_threshold(self, alert_type: AlertType) -> AlertThreshold | None:
        """Get threshold configuration for an alert type."""
        return self.thresholds.get(alert_type)

    def _is_in_cooldown(self, fingerprint: str, cooldown_minutes: int) -> bool:
        """Check if alert is in cooldown period."""
        if fingerprint not in self._cooldowns:
            return False
        
        cooldown_end = self._cooldowns[fingerprint] + timedelta(minutes=cooldown_minutes)
        return datetime.now(timezone.utc) < cooldown_end

    def _set_cooldown(self, fingerprint: str) -> None:
        """Set cooldown for an alert fingerprint."""
        self._cooldowns[fingerprint] = datetime.now(timezone.utc)

    async def send_alert(self, alert: Alert) -> list[AlertResult]:
        """Send an alert through all configured channels."""
        # Check cooldown
        threshold = self.thresholds.get(alert.alert_type)
        if threshold:
            cooldown = threshold.cooldown_minutes
            if self._is_in_cooldown(alert.fingerprint, cooldown):
                log.debug(
                    "alert_in_cooldown",
                    fingerprint=alert.fingerprint,
                    alert_type=alert.alert_type.value,
                )
                return []

        if not self.channels:
            log.warning("no_alert_channels_configured")
            return []

        # Send through all channels
        tasks = [channel.send(alert) for channel in self.channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Set cooldown
        self._set_cooldown(alert.fingerprint)

        return [
            r if isinstance(r, AlertResult)
            else AlertResult(channel="unknown", success=False, message=str(r))
            for r in results
        ]

    async def check_threshold(
        self,
        alert_type: AlertType,
        current_value: float,
        source: str = "system",
        title: str | None = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Alert | None:
        """
        Check if a metric exceeds its threshold and send alert if needed.
        
        Returns the Alert if one was triggered, None otherwise.
        """
        threshold = self.thresholds.get(alert_type)
        if not threshold or not threshold.enabled:
            return None

        # Determine severity
        if current_value >= threshold.critical_threshold:
            severity = AlertSeverity.CRITICAL
            threshold_value = threshold.critical_threshold
        elif current_value >= threshold.warning_threshold:
            severity = AlertSeverity.WARNING
            threshold_value = threshold.warning_threshold
        else:
            return None  # Below all thresholds

        # Build alert
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            title=title or f"{alert_type.value.replace('_', ' ').title()} Alert",
            message=message or f"Metric {current_value:.2f} exceeds threshold {threshold_value:.2f}",
            metric_value=current_value,
            threshold_value=threshold_value,
            source=source,
            metadata=metadata or {},
        )

        # Send alert
        await self.send_alert(alert)
        return alert

    # Convenience methods for common alerts

    async def alert_job_failure_rate(
        self,
        failure_rate: float,
        total_jobs: int,
        failed_jobs: int,
    ) -> Alert | None:
        """Alert on job failure rate threshold."""
        return await self.check_threshold(
            alert_type=AlertType.JOB_FAILURE_RATE,
            current_value=failure_rate,
            source="job_processor",
            title="High Job Failure Rate",
            message=f"Job failure rate is {failure_rate:.1f}% ({failed_jobs}/{total_jobs} jobs)",
            metadata={"total_jobs": total_jobs, "failed_jobs": failed_jobs},
        )

    async def alert_queue_depth(
        self,
        queue_depth: int,
        queue_name: str = "default",
    ) -> Alert | None:
        """Alert on queue depth threshold."""
        return await self.check_threshold(
            alert_type=AlertType.QUEUE_DEPTH,
            current_value=float(queue_depth),
            source="queue_monitor",
            title="Queue Depth High",
            message=f"Queue '{queue_name}' has {queue_depth} pending jobs",
            metadata={"queue_name": queue_name},
        )

    async def alert_worker_offline(
        self,
        worker_id: str,
        last_seen: datetime,
        offline_workers: int = 1,
    ) -> Alert | None:
        """Alert on worker going offline."""
        return await self.check_threshold(
            alert_type=AlertType.WORKER_OFFLINE,
            current_value=float(offline_workers),
            source="worker_monitor",
            title="Worker Offline",
            message=f"Worker '{worker_id}' has not responded since {last_seen.isoformat()}",
            metadata={
                "worker_id": worker_id,
                "last_seen": last_seen.isoformat(),
                "offline_workers": offline_workers,
            },
        )

    async def alert_api_error_rate(
        self,
        error_rate: float,
        total_requests: int,
        error_count: int,
        endpoint: str | None = None,
    ) -> Alert | None:
        """Alert on API error rate threshold."""
        return await self.check_threshold(
            alert_type=AlertType.API_ERROR_RATE,
            current_value=error_rate,
            source="api_monitor",
            title="High API Error Rate",
            message=f"API error rate is {error_rate:.1f}% ({error_count}/{total_requests} requests)",
            metadata={
                "total_requests": total_requests,
                "error_count": error_count,
                "endpoint": endpoint,
            },
        )

    async def alert_custom(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        source: str = "custom",
        metadata: dict[str, Any] | None = None,
    ) -> list[AlertResult]:
        """Send a custom alert."""
        alert = Alert(
            alert_type=AlertType.CUSTOM,
            severity=severity,
            title=title,
            message=message,
            source=source,
            metadata=metadata or {},
        )
        return await self.send_alert(alert)


# Singleton instance
_alert_service: AlertService | None = None


def get_alert_service() -> AlertService:
    """Get or create the global alert service instance."""
    global _alert_service
    
    if _alert_service is None:
        _alert_service = AlertService()
        
        # Configure channels from settings
        settings = get_settings()
        
        if settings.slack_webhook_url:
            _alert_service.add_channel(
                WebhookChannel(
                    webhook_url=settings.slack_webhook_url,
                    channel_name="slack",
                    format_type="slack",
                )
            )
        
        if settings.discord_webhook_url:
            _alert_service.add_channel(
                WebhookChannel(
                    webhook_url=settings.discord_webhook_url,
                    channel_name="discord",
                    format_type="discord",
                )
            )
        
        if settings.pagerduty_routing_key:
            _alert_service.add_channel(
                WebhookChannel(
                    webhook_url=settings.pagerduty_routing_key,
                    channel_name="pagerduty",
                    format_type="pagerduty",
                )
            )
        
        # Always add in-memory channel for admin dashboard
        _alert_service.add_channel(InMemoryChannel())
        
        log.info("alert_service_initialized", channels=len(_alert_service.channels))
    
    return _alert_service


def reset_alert_service() -> None:
    """Reset the global alert service (for testing)."""
    global _alert_service
    _alert_service = None
