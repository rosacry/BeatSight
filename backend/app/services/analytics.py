"""
Analytics and Metrics Collection

Lightweight analytics tracking for user engagement and feature usage.
Integrates with existing Prometheus metrics and provides async event tracking.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from collections import defaultdict

from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# Event Types
# ============================================================================


class EventCategory(str, Enum):
    """Categories of trackable events."""

    # User events
    USER_SIGNUP = "user.signup"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_PROFILE_UPDATE = "user.profile_update"

    # Content events
    SONG_UPLOAD = "song.upload"
    SONG_PLAY = "song.play"
    SONG_DOWNLOAD = "song.download"
    SONG_FAVORITE = "song.favorite"

    # Map events
    MAP_CREATE = "map.create"
    MAP_EDIT = "map.edit"
    MAP_PUBLISH = "map.publish"
    MAP_PLAY = "map.play"
    MAP_RATE = "map.rate"
    MAP_DOWNLOAD = "map.download"

    # AI/Transcription events
    TRANSCRIPTION_START = "transcription.start"
    TRANSCRIPTION_COMPLETE = "transcription.complete"
    TRANSCRIPTION_FAILED = "transcription.failed"

    # Credit events
    CREDITS_PURCHASE = "credits.purchase"
    CREDITS_SPEND = "credits.spend"
    CREDITS_GIFT = "credits.gift"

    # Social events
    FOLLOW_USER = "social.follow"
    UNFOLLOW_USER = "social.unfollow"
    COMMENT_CREATE = "social.comment"
    VOTE_CAST = "social.vote"

    # Achievement events
    ACHIEVEMENT_UNLOCK = "achievement.unlock"
    LEVEL_UP = "achievement.level_up"

    # Search/Discovery
    SEARCH_QUERY = "discovery.search"
    BROWSE_CATEGORY = "discovery.browse"

    # System events
    ERROR_OCCURRED = "system.error"
    FEATURE_FLAG_CHECK = "system.feature_flag"


class EventPriority(str, Enum):
    """Event priority for processing."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Event Models
# ============================================================================


class AnalyticsEvent(BaseModel):
    """A single analytics event."""

    event_type: EventCategory
    user_id: str | None = None
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    properties: dict[str, Any] = Field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL

    # Context
    ip_address: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    country: str | None = None
    device_type: str | None = None


class AggregatedMetric(BaseModel):
    """Aggregated metric for reporting."""

    metric_name: str
    value: float
    period_start: datetime
    period_end: datetime
    dimensions: dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Analytics Tracker
# ============================================================================


class AnalyticsTracker:
    """
    Async analytics event tracker.

    Collects events and batches them for efficient storage/forwarding.
    Thread-safe and non-blocking for minimal performance impact.
    """

    def __init__(
        self,
        batch_size: int = 100,
        flush_interval_seconds: float = 30.0,
    ):
        self._batch_size = batch_size
        self._flush_interval = flush_interval_seconds
        self._event_buffer: list[AnalyticsEvent] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
        self._handlers: list[callable] = []

        # In-memory counters for real-time metrics
        self._counters: defaultdict[str, int] = defaultdict(int)
        self._counter_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the background flush task."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._periodic_flush())
            logger.info("analytics_tracker_started")

    async def stop(self) -> None:
        """Stop the tracker and flush remaining events."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush()
        logger.info("analytics_tracker_stopped")

    def add_handler(self, handler: callable) -> None:
        """Add an event handler for processing batches."""
        self._handlers.append(handler)

    async def track(
        self,
        event_type: EventCategory,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        properties: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Track an analytics event.

        This method is non-blocking and safe to call from request handlers.
        """
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            properties=properties or {},
            priority=priority,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        async with self._buffer_lock:
            self._event_buffer.append(event)

            # Increment counter
            async with self._counter_lock:
                self._counters[event_type.value] += 1

            # Flush if buffer is full
            if len(self._event_buffer) >= self._batch_size:
                await self._flush()

    async def track_conversion(
        self,
        user_id: str,
        conversion_type: str,
        value: float,
        currency: str = "USD",
        **extra_properties,
    ) -> None:
        """Track a conversion event (purchase, signup, etc.)."""
        await self.track(
            EventCategory.CREDITS_PURCHASE,
            user_id=user_id,
            priority=EventPriority.HIGH,
            properties={
                "conversion_type": conversion_type,
                "value": value,
                "currency": currency,
                **extra_properties,
            },
        )

    async def track_error(
        self,
        error_type: str,
        error_message: str,
        *,
        user_id: str | None = None,
        stack_trace: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Track an error event."""
        await self.track(
            EventCategory.ERROR_OCCURRED,
            user_id=user_id,
            priority=EventPriority.CRITICAL,
            properties={
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": stack_trace,
                "endpoint": endpoint,
            },
        )

    async def get_counter(self, event_type: EventCategory) -> int:
        """Get the current count for an event type."""
        async with self._counter_lock:
            return self._counters[event_type.value]

    async def get_all_counters(self) -> dict[str, int]:
        """Get all current counters."""
        async with self._counter_lock:
            return dict(self._counters)

    async def _flush(self) -> None:
        """Flush buffered events to handlers."""
        async with self._buffer_lock:
            if not self._event_buffer:
                return

            events = self._event_buffer.copy()
            self._event_buffer.clear()

        # Send to all handlers
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(events)
                else:
                    handler(events)
            except Exception as e:
                logger.error(
                    "analytics_handler_error",
                    handler=handler.__name__,
                    error=str(e),
                    event_count=len(events),
                )

    async def _periodic_flush(self) -> None:
        """Background task to periodically flush events."""
        while True:
            await asyncio.sleep(self._flush_interval)
            await self._flush()


# ============================================================================
# Real-time Metrics
# ============================================================================


class RealTimeMetrics:
    """
    Real-time metrics aggregation for dashboards.

    Provides rolling window metrics for monitoring.
    """

    def __init__(self, window_size_seconds: int = 300):
        self._window_size = window_size_seconds
        self._events: list[tuple[datetime, str]] = []
        self._lock = asyncio.Lock()

    async def record(self, metric_name: str) -> None:
        """Record a metric event."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            self._events.append((now, metric_name))
            await self._cleanup()

    async def get_rate(self, metric_name: str) -> float:
        """Get events per second for a metric in the current window."""
        async with self._lock:
            await self._cleanup()
            count = sum(1 for _, name in self._events if name == metric_name)
            return count / self._window_size

    async def get_count(self, metric_name: str) -> int:
        """Get total count for a metric in the current window."""
        async with self._lock:
            await self._cleanup()
            return sum(1 for _, name in self._events if name == metric_name)

    async def get_all_counts(self) -> dict[str, int]:
        """Get counts for all metrics in the current window."""
        async with self._lock:
            await self._cleanup()
            counts: defaultdict[str, int] = defaultdict(int)
            for _, name in self._events:
                counts[name] += 1
            return dict(counts)

    async def _cleanup(self) -> None:
        """Remove events outside the window."""
        cutoff = datetime.now(timezone.utc).timestamp() - self._window_size
        self._events = [
            (ts, name) for ts, name in self._events if ts.timestamp() > cutoff
        ]


# ============================================================================
# Singleton Instance
# ============================================================================

# Global analytics tracker instance
analytics = AnalyticsTracker()

# Global real-time metrics instance
realtime_metrics = RealTimeMetrics()


# ============================================================================
# Convenience Functions
# ============================================================================


async def track_event(
    event_type: EventCategory,
    user_id: str | None = None,
    **properties,
) -> None:
    """Convenience function for tracking events."""
    await analytics.track(
        event_type,
        user_id=user_id,
        properties=properties,
    )


async def track_user_action(
    action: str,
    user_id: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    **extra,
) -> None:
    """Track a user action with standard properties."""
    # Map common actions to event types
    action_mapping = {
        "play": EventCategory.MAP_PLAY,
        "upload": EventCategory.SONG_UPLOAD,
        "download": EventCategory.MAP_DOWNLOAD,
        "favorite": EventCategory.SONG_FAVORITE,
        "rate": EventCategory.MAP_RATE,
        "follow": EventCategory.FOLLOW_USER,
        "comment": EventCategory.COMMENT_CREATE,
    }

    event_type = action_mapping.get(action.lower(), EventCategory.USER_PROFILE_UPDATE)

    await analytics.track(
        event_type,
        user_id=user_id,
        properties={
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            **extra,
        },
    )
