"""
Real-time events service for BeatSight.

Provides a centralized event system for broadcasting updates across
the application via WebSockets, Server-Sent Events, and Redis pub/sub.

Features:
- Typed event definitions
- Channel-based subscriptions
- User-specific events
- Broadcast events
- Event batching
- Dead letter handling
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.logging import get_logger

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = get_logger(__name__)

# ============================================================================
# Event Types
# ============================================================================


class EventType(str, Enum):
    """Enumeration of all event types in the system."""

    # Job events
    JOB_CREATED = "job:created"
    JOB_PROGRESS = "job:progress"
    JOB_COMPLETED = "job:completed"
    JOB_FAILED = "job:failed"
    JOB_CANCELLED = "job:cancelled"

    # Map events
    MAP_PUBLISHED = "map:published"
    MAP_UPDATED = "map:updated"
    MAP_DELETED = "map:deleted"
    MAP_VOTED = "map:voted"
    MAP_COMMENTED = "map:commented"

    # User events
    USER_FOLLOWED = "user:followed"
    USER_UNFOLLOWED = "user:unfollowed"
    USER_ACHIEVEMENT = "user:achievement"
    USER_LEVEL_UP = "user:level_up"

    # Credit events
    CREDITS_PURCHASED = "credits:purchased"
    CREDITS_USED = "credits:used"
    CREDITS_REFUNDED = "credits:refunded"
    CREDITS_GIFTED = "credits:gifted"

    # Notification events
    NOTIFICATION_NEW = "notification:new"
    NOTIFICATION_READ = "notification:read"

    # System events
    SYSTEM_ANNOUNCEMENT = "system:announcement"
    SYSTEM_MAINTENANCE = "system:maintenance"

    # Presence events
    PRESENCE_ONLINE = "presence:online"
    PRESENCE_OFFLINE = "presence:offline"
    PRESENCE_STATUS = "presence:status"


class EventPriority(str, Enum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Event Models
# ============================================================================


class BaseEvent(BaseModel):
    """Base event model with common fields."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: EventPriority = EventPriority.NORMAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobProgressEvent(BaseEvent):
    """Event for job progress updates."""

    type: EventType = EventType.JOB_PROGRESS
    job_id: str
    progress: float  # 0-100
    stage: str
    message: str | None = None
    eta_seconds: int | None = None


class JobCompletedEvent(BaseEvent):
    """Event for job completion."""

    type: EventType = EventType.JOB_COMPLETED
    job_id: str
    result_url: str | None = None
    processing_time_seconds: float | None = None


class JobFailedEvent(BaseEvent):
    """Event for job failure."""

    type: EventType = EventType.JOB_FAILED
    job_id: str
    error_code: str
    error_message: str
    retry_available: bool = False


class MapPublishedEvent(BaseEvent):
    """Event for map publication."""

    type: EventType = EventType.MAP_PUBLISHED
    map_id: str
    map_name: str
    author_id: str
    author_name: str
    thumbnail_url: str | None = None


class UserAchievementEvent(BaseEvent):
    """Event for user achievement unlock."""

    type: EventType = EventType.USER_ACHIEVEMENT
    user_id: str
    achievement_id: str
    achievement_name: str
    achievement_icon: str
    xp_reward: int = 0


class CreditsEvent(BaseEvent):
    """Event for credit transactions."""

    type: EventType
    user_id: str
    amount: int
    balance_after: int
    description: str | None = None


class NotificationEvent(BaseEvent):
    """Event for new notifications."""

    type: EventType = EventType.NOTIFICATION_NEW
    user_id: str
    notification_id: str
    title: str
    message: str
    action_url: str | None = None
    icon: str | None = None


class PresenceEvent(BaseEvent):
    """Event for user presence updates."""

    type: EventType
    user_id: str
    status: str | None = None  # online, away, dnd, offline
    activity: str | None = None  # What the user is doing


class SystemEvent(BaseEvent):
    """Event for system-wide announcements."""

    type: EventType = EventType.SYSTEM_ANNOUNCEMENT
    title: str
    message: str
    severity: str = "info"  # info, warning, error
    action_url: str | None = None
    expires_at: datetime | None = None


# ============================================================================
# Event Channels
# ============================================================================


@dataclass
class EventChannel:
    """Represents a subscription channel for events."""

    name: str
    pattern: str  # e.g., "job:*" or "user:{user_id}:*"
    description: str = ""


class Channels:
    """Predefined event channels."""

    # Global channels
    SYSTEM = EventChannel("system", "system:*", "System-wide announcements")
    JOBS_ALL = EventChannel("jobs", "job:*", "All job events")
    MAPS_ALL = EventChannel("maps", "map:*", "All map events")

    @staticmethod
    def user(user_id: str) -> EventChannel:
        """Channel for user-specific events."""
        return EventChannel(
            f"user:{user_id}", f"user:{user_id}:*", f"Events for user {user_id}"
        )

    @staticmethod
    def job(job_id: str) -> EventChannel:
        """Channel for specific job events."""
        return EventChannel(
            f"job:{job_id}", f"job:{job_id}", f"Events for job {job_id}"
        )

    @staticmethod
    def map(map_id: str) -> EventChannel:
        """Channel for specific map events."""
        return EventChannel(
            f"map:{map_id}", f"map:{map_id}", f"Events for map {map_id}"
        )


# ============================================================================
# Event Service
# ============================================================================


class EventService:
    """
    Central service for managing real-time events.

    Handles event publishing, subscription, and delivery via
    Redis pub/sub and WebSocket connections.
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._subscribers: dict[str, list[Callable]] = {}
        self._websockets: dict[str, list["WebSocket"]] = {}
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None
        self._event_buffer: list[BaseEvent] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_interval = 0.1  # 100ms
        self._max_buffer_size = 100

    async def start(self) -> None:
        """Start the event service and Redis listener."""
        self._pubsub = self.redis.pubsub()
        await self._pubsub.psubscribe("beatsight:events:*")
        self._listener_task = asyncio.create_task(self._listen())
        asyncio.create_task(self._flush_buffer_loop())
        logger.info("event_service_started")

    async def stop(self) -> None:
        """Stop the event service."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        logger.info("event_service_stopped")

    async def _listen(self) -> None:
        """Listen for Redis pub/sub messages."""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode()

                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode()

                    try:
                        event_data = json.loads(data)
                        await self._dispatch_event(channel, event_data)
                    except json.JSONDecodeError:
                        logger.warning("invalid_event_data", channel=channel)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("event_listener_error", error=str(e))

    async def _dispatch_event(self, channel: str, event_data: dict) -> None:
        """Dispatch an event to local subscribers and WebSocket connections."""
        # Dispatch to local callbacks
        for pattern, callbacks in self._subscribers.items():
            if self._matches_pattern(channel, pattern):
                for callback in callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event_data)
                        else:
                            callback(event_data)
                    except Exception as e:
                        logger.error(
                            "event_callback_error", error=str(e), channel=channel
                        )

        # Dispatch to WebSocket connections
        await self._broadcast_to_websockets(channel, event_data)

    def _matches_pattern(self, channel: str, pattern: str) -> bool:
        """Check if a channel matches a subscription pattern."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return channel.startswith(pattern[:-1])
        return channel == pattern

    async def _broadcast_to_websockets(self, channel: str, event_data: dict) -> None:
        """Broadcast event to subscribed WebSocket connections."""
        dead_connections = []

        for pattern, websockets in self._websockets.items():
            if self._matches_pattern(channel, pattern):
                for ws in websockets:
                    try:
                        await ws.send_json(event_data)
                    except Exception:
                        dead_connections.append((pattern, ws))

        # Clean up dead connections
        for pattern, ws in dead_connections:
            if pattern in self._websockets:
                self._websockets[pattern] = [
                    w for w in self._websockets[pattern] if w != ws
                ]

    async def publish(
        self,
        event: BaseEvent,
        *,
        channel: str | None = None,
        user_ids: list[str] | None = None,
        broadcast: bool = False,
    ) -> None:
        """
        Publish an event to the event system.

        Args:
            event: The event to publish
            channel: Specific channel to publish to
            user_ids: List of user IDs to send the event to
            broadcast: Whether to broadcast to all connected clients
        """
        event_data = event.model_dump(mode="json")

        # Buffer non-critical events
        if event.priority != EventPriority.CRITICAL:
            async with self._buffer_lock:
                self._event_buffer.append(event)
                if len(self._event_buffer) >= self._max_buffer_size:
                    await self._flush_buffer()
                return

        # Immediate publishing for critical events
        await self._publish_immediate(event_data, channel, user_ids, broadcast)

    async def _publish_immediate(
        self,
        event_data: dict,
        channel: str | None,
        user_ids: list[str] | None,
        broadcast: bool,
    ) -> None:
        """Immediately publish an event without buffering."""
        event_json = json.dumps(event_data)

        if broadcast:
            await self.redis.publish("beatsight:events:broadcast", event_json)
        elif user_ids:
            for user_id in user_ids:
                await self.redis.publish(f"beatsight:events:user:{user_id}", event_json)
        elif channel:
            await self.redis.publish(f"beatsight:events:{channel}", event_json)
        else:
            await self.redis.publish(
                f"beatsight:events:{event_data['type']}", event_json
            )

        logger.debug("event_published", event_type=event_data["type"])

    async def _flush_buffer(self) -> None:
        """Flush buffered events."""
        if not self._event_buffer:
            return

        events = self._event_buffer
        self._event_buffer = []

        # Group events by channel for efficient publishing
        pipeline = self.redis.pipeline()
        for event in events:
            event_data = event.model_dump(mode="json")
            event_json = json.dumps(event_data)
            pipeline.publish(f"beatsight:events:{event.type.value}", event_json)

        await pipeline.execute()
        logger.debug("events_flushed", count=len(events))

    async def _flush_buffer_loop(self) -> None:
        """Periodically flush the event buffer."""
        while True:
            await asyncio.sleep(self._flush_interval)
            async with self._buffer_lock:
                await self._flush_buffer()

    def subscribe(self, pattern: str, callback: Callable) -> Callable[[], None]:
        """
        Subscribe to events matching a pattern.

        Returns an unsubscribe function.
        """
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(callback)

        def unsubscribe():
            if pattern in self._subscribers:
                self._subscribers[pattern] = [
                    cb for cb in self._subscribers[pattern] if cb != callback
                ]

        return unsubscribe

    async def subscribe_websocket(
        self, websocket: "WebSocket", patterns: list[str]
    ) -> None:
        """Subscribe a WebSocket connection to event patterns."""
        for pattern in patterns:
            if pattern not in self._websockets:
                self._websockets[pattern] = []
            self._websockets[pattern].append(websocket)

    def unsubscribe_websocket(self, websocket: "WebSocket") -> None:
        """Unsubscribe a WebSocket connection from all patterns."""
        for pattern in list(self._websockets.keys()):
            self._websockets[pattern] = [
                ws for ws in self._websockets[pattern] if ws != websocket
            ]
            if not self._websockets[pattern]:
                del self._websockets[pattern]


# ============================================================================
# Event Helpers
# ============================================================================


async def publish_job_progress(
    event_service: EventService,
    job_id: str,
    progress: float,
    stage: str,
    user_id: str | None = None,
    message: str | None = None,
    eta_seconds: int | None = None,
) -> None:
    """Helper to publish job progress events."""
    event = JobProgressEvent(
        job_id=job_id,
        progress=progress,
        stage=stage,
        message=message,
        eta_seconds=eta_seconds,
    )
    await event_service.publish(
        event,
        channel=f"job:{job_id}",
        user_ids=[user_id] if user_id else None,
    )


async def publish_job_completed(
    event_service: EventService,
    job_id: str,
    user_id: str | None = None,
    result_url: str | None = None,
    processing_time_seconds: float | None = None,
) -> None:
    """Helper to publish job completed events."""
    event = JobCompletedEvent(
        job_id=job_id,
        result_url=result_url,
        processing_time_seconds=processing_time_seconds,
        priority=EventPriority.HIGH,
    )
    await event_service.publish(
        event,
        channel=f"job:{job_id}",
        user_ids=[user_id] if user_id else None,
    )


async def publish_job_failed(
    event_service: EventService,
    job_id: str,
    error_code: str,
    error_message: str,
    user_id: str | None = None,
    retry_available: bool = False,
) -> None:
    """Helper to publish job failed events."""
    event = JobFailedEvent(
        job_id=job_id,
        error_code=error_code,
        error_message=error_message,
        retry_available=retry_available,
        priority=EventPriority.HIGH,
    )
    await event_service.publish(
        event,
        channel=f"job:{job_id}",
        user_ids=[user_id] if user_id else None,
    )


async def publish_notification(
    event_service: EventService,
    user_id: str,
    notification_id: str,
    title: str,
    message: str,
    action_url: str | None = None,
    icon: str | None = None,
) -> None:
    """Helper to publish notification events."""
    event = NotificationEvent(
        user_id=user_id,
        notification_id=notification_id,
        title=title,
        message=message,
        action_url=action_url,
        icon=icon,
    )
    await event_service.publish(event, user_ids=[user_id])


async def publish_system_announcement(
    event_service: EventService,
    title: str,
    message: str,
    severity: str = "info",
    action_url: str | None = None,
    expires_at: datetime | None = None,
) -> None:
    """Helper to publish system announcements."""
    event = SystemEvent(
        title=title,
        message=message,
        severity=severity,
        action_url=action_url,
        expires_at=expires_at,
        priority=EventPriority.HIGH,
    )
    await event_service.publish(event, broadcast=True)


async def publish_achievement(
    event_service: EventService,
    user_id: str,
    achievement_id: str,
    achievement_name: str,
    achievement_icon: str,
    xp_reward: int = 0,
) -> None:
    """Helper to publish achievement unlock events."""
    event = UserAchievementEvent(
        user_id=user_id,
        achievement_id=achievement_id,
        achievement_name=achievement_name,
        achievement_icon=achievement_icon,
        xp_reward=xp_reward,
        priority=EventPriority.HIGH,
    )
    await event_service.publish(event, user_ids=[user_id])


# ============================================================================
# Dependency
# ============================================================================

_event_service: EventService | None = None


async def get_event_service(redis: Redis) -> EventService:
    """Get or create the event service singleton."""
    global _event_service
    if _event_service is None:
        _event_service = EventService(redis)
        await _event_service.start()
    return _event_service
