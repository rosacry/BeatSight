"""Notification service for job completion alerts.

Supports email (SendGrid/SES) and WebPush notifications.
"""

from __future__ import annotations

import asyncio
import html
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""

    EMAIL = "email"
    WEBPUSH = "webpush"


class NotificationEvent(str, Enum):
    """Notification event triggers."""

    JOB_COMPLETE = "job_complete"
    JOB_FAILED = "job_failed"
    JOB_TIMEOUT = "job_timeout"


@dataclass
class NotificationPayload:
    """Payload for a notification."""

    event: NotificationEvent
    user_id: UUID
    user_email: str | None
    song_title: str
    song_artist: str
    job_id: UUID
    result_url: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class NotificationResult:
    """Result of sending a notification."""

    notification_type: NotificationType
    success: bool
    message: str | None = None
    message_id: str | None = None


class NotificationBackend(ABC):
    """Abstract base class for notification backends."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """Send a notification."""
        ...


class EmailBackend(NotificationBackend):
    """Email notification backend using SendGrid or SES."""

    def __init__(self, api_key: str, from_email: str, from_name: str = "BeatSight"):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    def _render_subject(self, payload: NotificationPayload) -> str:
        """Generate email subject line."""
        if payload.event == NotificationEvent.JOB_COMPLETE:
            return f'Your beatmap for "{payload.song_title}" is ready!'
        elif payload.event == NotificationEvent.JOB_FAILED:
            return f'Beatmap generation failed for "{payload.song_title}"'
        elif payload.event == NotificationEvent.JOB_TIMEOUT:
            return f'Beatmap generation timed out for "{payload.song_title}"'
        return "BeatSight notification"

    def _render_body_html(self, payload: NotificationPayload) -> str:
        """Render HTML email body.
        
        All user-provided content is escaped to prevent XSS attacks.
        """
        settings = get_settings()
        base_url = settings.frontend_url or "https://beatsight.io"
        
        # Escape user-provided content to prevent XSS
        safe_title = html.escape(payload.song_title)
        safe_artist = html.escape(payload.song_artist)
        safe_error = html.escape(payload.error_message or "Unknown error")

        if payload.event == NotificationEvent.JOB_COMPLETE:
            return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #6366f1; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f3f4f6; padding: 20px; }}
        .button {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 6px; margin-top: 20px; }}
        .footer {{ color: #6b7280; font-size: 12px; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 Your Beatmap is Ready!</h1>
        </div>
        <div class="content">
            <p>Great news! Your AI-generated beatmap is complete.</p>
            <p><strong>Song:</strong> {safe_title}<br>
               <strong>Artist:</strong> {safe_artist}</p>
            <a href="{payload.result_url or f"{base_url}/jobs/{payload.job_id}"}" class="button">
                View Your Beatmap
            </a>
            <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                You can download and play this beatmap in the BeatSight desktop app.
            </p>
        </div>
        <div class="footer">
            <p>You're receiving this because you generated a beatmap on BeatSight.</p>
            <p><a href="{base_url}/settings/notifications">Manage notification preferences</a></p>
        </div>
    </div>
</body>
</html>
"""
        elif payload.event == NotificationEvent.JOB_FAILED:
            return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #ef4444; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f3f4f6; padding: 20px; }}
        .error {{ background: #fee2e2; border: 1px solid #ef4444; padding: 12px; border-radius: 6px; 
                  font-family: monospace; font-size: 13px; color: #991b1b; }}
        .button {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 6px; margin-top: 20px; }}
        .footer {{ color: #6b7280; font-size: 12px; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Generation Failed</h1>
        </div>
        <div class="content">
            <p>Unfortunately, we couldn't generate a beatmap for your song.</p>
            <p><strong>Song:</strong> {safe_title}<br>
               <strong>Artist:</strong> {safe_artist}</p>
            {f'<div class="error">{safe_error}</div>' if payload.error_message else ""}
            <a href="{base_url}/jobs/{payload.job_id}" class="button">
                View Details & Retry
            </a>
            <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                If this keeps happening, please contact support.
            </p>
        </div>
        <div class="footer">
            <p>You're receiving this because you generated a beatmap on BeatSight.</p>
            <p><a href="{base_url}/settings/notifications">Manage notification preferences</a></p>
        </div>
    </div>
</body>
</html>
"""
        else:  # TIMEOUT
            return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f59e0b; color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f3f4f6; padding: 20px; }}
        .button {{ display: inline-block; background: #6366f1; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 6px; margin-top: 20px; }}
        .footer {{ color: #6b7280; font-size: 12px; padding: 20px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏱️ Generation Timed Out</h1>
        </div>
        <div class="content">
            <p>Your beatmap generation took longer than expected and was cancelled.</p>
            <p><strong>Song:</strong> {safe_title}<br>
               <strong>Artist:</strong> {safe_artist}</p>
            <a href="{base_url}/jobs/{payload.job_id}" class="button">
                Retry Generation
            </a>
            <p style="margin-top: 20px; color: #6b7280; font-size: 14px;">
                This can happen with very long songs or during high traffic periods.
            </p>
        </div>
        <div class="footer">
            <p>You're receiving this because you generated a beatmap on BeatSight.</p>
            <p><a href="{base_url}/settings/notifications">Manage notification preferences</a></p>
        </div>
    </div>
</body>
</html>
"""

    async def send(self, payload: NotificationPayload) -> NotificationResult:
        """Send email notification."""
        if not payload.user_email:
            return NotificationResult(
                notification_type=NotificationType.EMAIL,
                success=False,
                message="No email address available",
            )

        try:
            subject = self._render_subject(payload)
            html_content = self._render_body_html(payload)

            # Check if SendGrid is configured
            if not self.api_key:
                log.warning(
                    "email_not_configured",
                    message="SendGrid API key not configured, logging email instead",
                    to=payload.user_email,
                    subject=subject,
                )
                return NotificationResult(
                    notification_type=NotificationType.EMAIL,
                    success=True,
                    message="Email logged (SendGrid not configured)",
                )

            # Send via SendGrid
            try:
                import sendgrid
                from sendgrid.helpers.mail import Mail, Email, To, Content
            except ImportError:
                log.warning(
                    "sendgrid_not_installed", message="sendgrid package not installed"
                )
                return NotificationResult(
                    notification_type=NotificationType.EMAIL,
                    success=False,
                    message="sendgrid package not installed",
                )

            sg = sendgrid.SendGridAPIClient(api_key=self.api_key)

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(payload.user_email),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            # Run sync SendGrid call in thread pool
            response = await asyncio.to_thread(sg.send, message)

            success = response.status_code < 400
            message_id = response.headers.get("X-Message-Id")

            if success:
                log.info(
                    "email_notification_sent",
                    to=payload.user_email,
                    subject=subject,
                    notification_event=payload.event.value,
                    job_id=str(payload.job_id),
                    message_id=message_id,
                )
            else:
                log.error(
                    "email_notification_failed",
                    to=payload.user_email,
                    status_code=response.status_code,
                    job_id=str(payload.job_id),
                )

            return NotificationResult(
                notification_type=NotificationType.EMAIL,
                success=success,
                message_id=message_id,
                message=None if success else f"SendGrid error: {response.status_code}",
            )

        except Exception as e:
            log.error(
                "email_notification_failed", error=str(e), job_id=str(payload.job_id)
            )
            return NotificationResult(
                notification_type=NotificationType.EMAIL,
                success=False,
                message=str(e),
            )


class WebPushBackend(NotificationBackend):
    """WebPush notification backend."""

    def __init__(self, vapid_private_key: str, vapid_claims: dict[str, str]):
        self.vapid_private_key = vapid_private_key
        self.vapid_claims = vapid_claims

    def _build_payload(self, payload: NotificationPayload) -> dict[str, Any]:
        """Build WebPush notification payload."""
        if payload.event == NotificationEvent.JOB_COMPLETE:
            return {
                "title": "🎵 Beatmap Ready!",
                "body": f'Your beatmap for "{payload.song_title}" is complete.',
                "icon": "/icons/notification.png",
                "badge": "/icons/badge.png",
                "tag": f"job-{payload.job_id}",
                "renotify": True,
                "data": {
                    "url": payload.result_url or f"/jobs/{payload.job_id}",
                    "job_id": str(payload.job_id),
                },
            }
        elif payload.event == NotificationEvent.JOB_FAILED:
            return {
                "title": "⚠️ Generation Failed",
                "body": f'Could not generate beatmap for "{payload.song_title}".',
                "icon": "/icons/notification-error.png",
                "badge": "/icons/badge.png",
                "tag": f"job-{payload.job_id}",
                "renotify": True,
                "data": {
                    "url": f"/jobs/{payload.job_id}",
                    "job_id": str(payload.job_id),
                },
            }
        else:  # TIMEOUT
            return {
                "title": "⏱️ Generation Timed Out",
                "body": f'Beatmap generation for "{payload.song_title}" timed out.',
                "icon": "/icons/notification-warning.png",
                "badge": "/icons/badge.png",
                "tag": f"job-{payload.job_id}",
                "renotify": True,
                "data": {
                    "url": f"/jobs/{payload.job_id}",
                    "job_id": str(payload.job_id),
                },
            }

    async def send(
        self,
        payload: NotificationPayload,
        subscriptions: list[dict] | None = None,
    ) -> NotificationResult:
        """Send WebPush notification.

        Args:
            payload: Notification payload with event and user info
            subscriptions: List of subscription dicts from PushSubscription.to_subscription_info()
                          If not provided, notification will be skipped.
        """
        import json

        if not subscriptions:
            log.info(
                "webpush_no_subscriptions",
                user_id=str(payload.user_id),
                message="User has no push subscriptions registered",
            )
            return NotificationResult(
                notification_type=NotificationType.WEBPUSH,
                success=True,
                message="No push subscriptions registered for user",
            )

        try:
            try:
                from pywebpush import webpush, WebPushException
            except ImportError:
                log.warning(
                    "pywebpush_not_installed", message="pywebpush package not installed"
                )
                return NotificationResult(
                    notification_type=NotificationType.WEBPUSH,
                    success=False,
                    message="pywebpush package not installed",
                )

            notification_data = json.dumps(self._build_payload(payload))
            sent_count = 0
            failed_count = 0

            for subscription_info in subscriptions:
                try:
                    await asyncio.to_thread(
                        webpush,
                        subscription_info=subscription_info,
                        data=notification_data,
                        vapid_private_key=self.vapid_private_key,
                        vapid_claims=self.vapid_claims,
                    )
                    sent_count += 1
                except WebPushException as e:
                    # Log but continue with other subscriptions
                    log.warning(
                        "webpush_subscription_failed",
                        endpoint=subscription_info.get("endpoint", "")[:50],
                        error=str(e),
                    )
                    failed_count += 1

            log.info(
                "webpush_notification_sent",
                user_id=str(payload.user_id),
                notification_event=payload.event.value,
                job_id=str(payload.job_id),
                sent_count=sent_count,
                failed_count=failed_count,
            )

            return NotificationResult(
                notification_type=NotificationType.WEBPUSH,
                success=sent_count > 0,
                message=f"Sent to {sent_count}/{sent_count + failed_count} subscriptions",
            )

        except Exception as e:
            log.error(
                "webpush_notification_failed", error=str(e), job_id=str(payload.job_id)
            )
            return NotificationResult(
                notification_type=NotificationType.WEBPUSH,
                success=False,
                message=str(e),
            )


class NotificationService:
    """Service for sending notifications to users."""

    def __init__(
        self,
        email_backend: EmailBackend | None = None,
        webpush_backend: WebPushBackend | None = None,
    ):
        self.email_backend = email_backend
        self.webpush_backend = webpush_backend
        self._rate_limit_cache: dict[str, list[datetime]] = {}

    def _check_rate_limit(self, user_id: UUID, max_per_hour: int = 10) -> bool:
        """Check if user has exceeded notification rate limit."""
        from datetime import timedelta

        key = str(user_id)
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        if key not in self._rate_limit_cache:
            self._rate_limit_cache[key] = []

        # Clean old entries
        self._rate_limit_cache[key] = [
            ts for ts in self._rate_limit_cache[key] if ts > hour_ago
        ]

        if len(self._rate_limit_cache[key]) >= max_per_hour:
            return False

        self._rate_limit_cache[key].append(now)
        return True

    async def notify_job_complete(
        self,
        user_id: UUID,
        user_email: str | None,
        job_id: UUID,
        song_title: str,
        song_artist: str,
        result_url: str | None = None,
        send_email: bool = True,
        send_push: bool = True,
    ) -> list[NotificationResult]:
        """Send notifications for completed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_COMPLETE,
            user_id=user_id,
            user_email=user_email,
            song_title=song_title,
            song_artist=song_artist,
            job_id=job_id,
            result_url=result_url,
        )
        return await self._send_all(payload, send_email, send_push)

    async def notify_job_failed(
        self,
        user_id: UUID,
        user_email: str | None,
        job_id: UUID,
        song_title: str,
        song_artist: str,
        error_message: str | None = None,
        send_email: bool = True,
        send_push: bool = True,
    ) -> list[NotificationResult]:
        """Send notifications for failed job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_FAILED,
            user_id=user_id,
            user_email=user_email,
            song_title=song_title,
            song_artist=song_artist,
            job_id=job_id,
            error_message=error_message,
        )
        return await self._send_all(payload, send_email, send_push)

    async def notify_job_timeout(
        self,
        user_id: UUID,
        user_email: str | None,
        job_id: UUID,
        song_title: str,
        song_artist: str,
        send_email: bool = True,
        send_push: bool = True,
    ) -> list[NotificationResult]:
        """Send notifications for timed out job."""
        payload = NotificationPayload(
            event=NotificationEvent.JOB_TIMEOUT,
            user_id=user_id,
            user_email=user_email,
            song_title=song_title,
            song_artist=song_artist,
            job_id=job_id,
        )
        return await self._send_all(payload, send_email, send_push)

    async def _send_all(
        self,
        payload: NotificationPayload,
        send_email: bool,
        send_push: bool,
    ) -> list[NotificationResult]:
        """Send notifications through all enabled backends."""
        if not self._check_rate_limit(payload.user_id):
            log.warning(
                "notification_rate_limited",
                user_id=str(payload.user_id),
                job_id=str(payload.job_id),
            )
            return [
                NotificationResult(
                    notification_type=NotificationType.EMAIL,
                    success=False,
                    message="Rate limit exceeded",
                )
            ]

        tasks = []

        if send_email and self.email_backend:
            tasks.append(self.email_backend.send(payload))

        if send_push and self.webpush_backend:
            tasks.append(self.webpush_backend.send(payload))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r
            if isinstance(r, NotificationResult)
            else NotificationResult(
                notification_type=NotificationType.EMAIL,
                success=False,
                message=str(r),
            )
            for r in results
        ]


def get_notification_service() -> NotificationService:
    """Factory function to create notification service."""
    settings = get_settings()

    email_backend = None
    if settings.sendgrid_api_key:
        email_backend = EmailBackend(
            api_key=settings.sendgrid_api_key,
            from_email=settings.email_from or "noreply@beatsight.io",
            from_name="BeatSight",
        )

    webpush_backend = None
    if settings.vapid_private_key:
        webpush_backend = WebPushBackend(
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={
                "sub": f"mailto:{settings.email_from or 'admin@beatsight.io'}",
            },
        )

    return NotificationService(
        email_backend=email_backend,
        webpush_backend=webpush_backend,
    )
