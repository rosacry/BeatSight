"""
Event and message utilities for pub/sub patterns and internal messaging.

This module provides a simple but flexible event system for:
- In-process pub/sub with typed events
- Event filtering and routing
- Async event handlers
- Event history and replay
- Dead letter handling
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)
from weakref import WeakSet


# Type variables
T = TypeVar("T")
E = TypeVar("E", bound="Event")
EventHandler = Union[Callable[[Any], None], Callable[[Any], Awaitable[None]]]


class EventPriority(Enum):
    """Priority levels for event handlers."""
    
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class EventStatus(Enum):
    """Status of event processing."""
    
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class Event:
    """Base event class for all events in the system."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def event_type(self) -> str:
        """Get the event type name."""
        return self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }
    
    def with_correlation(self, correlation_id: str) -> Event:
        """Create a copy with correlation ID."""
        self.correlation_id = correlation_id
        return self


@dataclass
class DomainEvent(Event):
    """Base class for domain events with aggregate info."""
    
    aggregate_id: Optional[str] = None
    aggregate_type: Optional[str] = None
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary including domain info."""
        data = super().to_dict()
        data.update({
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
        })
        return data


@dataclass
class EventEnvelope(Generic[E]):
    """Wrapper for events with delivery metadata."""
    
    event: E
    status: EventStatus = EventStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    @property
    def can_retry(self) -> bool:
        """Check if event can be retried."""
        return self.attempts < self.max_attempts and self.status == EventStatus.FAILED
    
    def mark_processing(self) -> None:
        """Mark event as processing."""
        self.status = EventStatus.PROCESSING
        self.attempts += 1
    
    def mark_completed(self) -> None:
        """Mark event as completed."""
        self.status = EventStatus.COMPLETED
        self.processed_at = datetime.now(timezone.utc)
    
    def mark_failed(self, error: str) -> None:
        """Mark event as failed."""
        self.status = EventStatus.FAILED
        self.error = error
        if not self.can_retry:
            self.status = EventStatus.DEAD_LETTER


@dataclass
class Subscription:
    """Represents a subscription to events."""
    
    handler: EventHandler = field(repr=False)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_types: Set[str] = field(default_factory=set)
    filter_func: Optional[Callable[[Event], bool]] = field(default=None, repr=False)
    priority: EventPriority = EventPriority.NORMAL
    is_async: bool = False
    active: bool = True
    
    def matches(self, event: Event) -> bool:
        """Check if subscription matches event."""
        if not self.active:
            return False
        
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Apply filter function
        if self.filter_func and not self.filter_func(event):
            return False
        
        return True


class EventBus:
    """
    Simple in-process event bus for pub/sub messaging.
    
    Example:
        bus = EventBus()
        
        # Subscribe to events
        bus.subscribe(UserCreated, handle_user_created)
        
        # Publish events
        await bus.publish(UserCreated(user_id="123"))
    """
    
    def __init__(
        self,
        max_history: int = 1000,
        enable_history: bool = True,
    ) -> None:
        """Initialize event bus."""
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._global_subscriptions: List[Subscription] = []
        self._history: List[Event] = []
        self._max_history = max_history
        self._enable_history = enable_history
        self._dead_letter_queue: List[EventEnvelope] = []
        self._lock = asyncio.Lock()
    
    def subscribe(
        self,
        event_type: Union[Type[Event], str, None] = None,
        handler: Optional[EventHandler] = None,
        filter_func: Optional[Callable[[Event], bool]] = None,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> Subscription:
        """
        Subscribe to events.
        
        Args:
            event_type: Event class or type name to subscribe to (None for all)
            handler: Callback function to handle events
            filter_func: Optional filter function
            priority: Handler priority
            
        Returns:
            Subscription object
        """
        if handler is None:
            # Decorator usage
            def decorator(fn: EventHandler) -> EventHandler:
                self.subscribe(event_type, fn, filter_func, priority)
                return fn
            return decorator  # type: ignore
        
        # Determine if handler is async
        is_async = asyncio.iscoroutinefunction(handler)
        
        # Get event type name
        event_types: Set[str] = set()
        if event_type is not None:
            if isinstance(event_type, type):
                event_types.add(event_type.__name__)
            else:
                event_types.add(event_type)
        
        subscription = Subscription(
            handler=handler,
            event_types=event_types,
            filter_func=filter_func,
            priority=priority,
            is_async=is_async,
        )
        
        if event_types:
            for et in event_types:
                self._subscriptions[et].append(subscription)
                # Sort by priority (highest first)
                self._subscriptions[et].sort(
                    key=lambda s: s.priority.value, reverse=True
                )
        else:
            self._global_subscriptions.append(subscription)
            self._global_subscriptions.sort(
                key=lambda s: s.priority.value, reverse=True
            )
        
        return subscription
    
    def unsubscribe(self, subscription: Subscription) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscription: Subscription to remove
            
        Returns:
            True if subscription was found and removed
        """
        subscription.active = False
        
        # Remove from specific subscriptions
        for event_type in subscription.event_types:
            if subscription in self._subscriptions[event_type]:
                self._subscriptions[event_type].remove(subscription)
                return True
        
        # Remove from global subscriptions
        if subscription in self._global_subscriptions:
            self._global_subscriptions.remove(subscription)
            return True
        
        return False
    
    async def publish(
        self,
        event: Event,
        wait: bool = True,
    ) -> List[Exception]:
        """
        Publish an event to all subscribers.
        
        Args:
            event: Event to publish
            wait: Whether to wait for handlers to complete
            
        Returns:
            List of exceptions from failed handlers
        """
        # Record in history
        if self._enable_history:
            async with self._lock:
                self._history.append(event)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
        
        # Get matching subscriptions
        subscriptions = self._get_matching_subscriptions(event)
        
        if not subscriptions:
            return []
        
        # Execute handlers
        errors: List[Exception] = []
        
        if wait:
            for sub in subscriptions:
                try:
                    if sub.is_async:
                        await sub.handler(event)
                    else:
                        sub.handler(event)
                except Exception as e:
                    errors.append(e)
        else:
            # Fire and forget
            for sub in subscriptions:
                if sub.is_async:
                    asyncio.create_task(self._safe_call(sub.handler, event))
                else:
                    try:
                        sub.handler(event)
                    except Exception as e:
                        errors.append(e)
        
        return errors
    
    def publish_sync(self, event: Event) -> List[Exception]:
        """
        Synchronously publish an event (only to sync handlers).
        
        Args:
            event: Event to publish
            
        Returns:
            List of exceptions from failed handlers
        """
        # Record in history
        if self._enable_history:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        # Get matching subscriptions
        subscriptions = self._get_matching_subscriptions(event)
        
        errors: List[Exception] = []
        for sub in subscriptions:
            if not sub.is_async:
                try:
                    sub.handler(event)
                except Exception as e:
                    errors.append(e)
        
        return errors
    
    def _get_matching_subscriptions(self, event: Event) -> List[Subscription]:
        """Get all subscriptions matching an event."""
        subscriptions = []
        
        # Get type-specific subscriptions
        type_subs = self._subscriptions.get(event.event_type, [])
        subscriptions.extend(s for s in type_subs if s.matches(event))
        
        # Get global subscriptions
        subscriptions.extend(s for s in self._global_subscriptions if s.matches(event))
        
        # Sort by priority
        subscriptions.sort(key=lambda s: s.priority.value, reverse=True)
        
        return subscriptions
    
    async def _safe_call(
        self,
        handler: EventHandler,
        event: Event,
    ) -> None:
        """Safely call a handler, catching exceptions."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception:
            # Log but don't propagate
            pass
    
    def get_history(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type
            since: Filter events after this time
            limit: Maximum number of events to return
            
        Returns:
            List of historical events
        """
        events = self._history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if since:
            events = [e for e in events if e.timestamp >= since]
        
        return events[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        self._history.clear()
    
    @property
    def dead_letter_queue(self) -> List[EventEnvelope]:
        """Get dead letter queue."""
        return self._dead_letter_queue.copy()
    
    def clear_dead_letters(self) -> None:
        """Clear dead letter queue."""
        self._dead_letter_queue.clear()


class EventEmitter:
    """
    Mixin class for objects that emit events.
    
    Example:
        class User(EventEmitter):
            def __init__(self, bus: EventBus):
                super().__init__(bus)
                
            async def create(self):
                # ... create user ...
                await self.emit(UserCreated(user_id=self.id))
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        """Initialize with optional event bus."""
        self._event_bus = event_bus
        self._pending_events: List[Event] = []
    
    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus."""
        self._event_bus = event_bus
    
    async def emit(self, event: Event, wait: bool = True) -> List[Exception]:
        """
        Emit an event.
        
        Args:
            event: Event to emit
            wait: Whether to wait for handlers
            
        Returns:
            List of exceptions from handlers
        """
        if self._event_bus is None:
            self._pending_events.append(event)
            return []
        
        return await self._event_bus.publish(event, wait=wait)
    
    def emit_sync(self, event: Event) -> List[Exception]:
        """
        Synchronously emit an event.
        
        Args:
            event: Event to emit
            
        Returns:
            List of exceptions from handlers
        """
        if self._event_bus is None:
            self._pending_events.append(event)
            return []
        
        return self._event_bus.publish_sync(event)
    
    async def flush_pending_events(self) -> None:
        """Publish any pending events."""
        if self._event_bus is None:
            return
        
        for event in self._pending_events:
            await self._event_bus.publish(event)
        
        self._pending_events.clear()
    
    @property
    def pending_events(self) -> List[Event]:
        """Get pending events."""
        return self._pending_events.copy()


class EventHandler(ABC):
    """
    Abstract base class for event handlers.
    
    Example:
        class UserCreatedHandler(EventHandler[UserCreated]):
            async def handle(self, event: UserCreated) -> None:
                # Handle the event
                pass
    """
    
    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle the event."""
        pass
    
    def __call__(self, event: Event) -> Awaitable[None]:
        """Allow handler to be used as callable."""
        return self.handle(event)


class EventStore:
    """
    Simple in-memory event store for event sourcing patterns.
    
    Example:
        store = EventStore()
        
        # Append events
        await store.append("user-123", UserCreated(user_id="123"))
        await store.append("user-123", UserUpdated(user_id="123", name="John"))
        
        # Load events for aggregate
        events = await store.load("user-123")
    """
    
    def __init__(self) -> None:
        """Initialize event store."""
        self._streams: Dict[str, List[Event]] = defaultdict(list)
        self._all_events: List[Event] = []
        self._lock = asyncio.Lock()
    
    async def append(
        self,
        stream_id: str,
        event: Event,
        expected_version: Optional[int] = None,
    ) -> int:
        """
        Append an event to a stream.
        
        Args:
            stream_id: Stream identifier (e.g., aggregate ID)
            event: Event to append
            expected_version: Expected stream version for optimistic concurrency
            
        Returns:
            New stream version
            
        Raises:
            ConcurrencyError: If expected version doesn't match
        """
        async with self._lock:
            stream = self._streams[stream_id]
            current_version = len(stream)
            
            if expected_version is not None and current_version != expected_version:
                raise ConcurrencyError(
                    f"Expected version {expected_version}, got {current_version}"
                )
            
            stream.append(event)
            self._all_events.append(event)
            
            return current_version + 1
    
    async def load(
        self,
        stream_id: str,
        from_version: int = 0,
    ) -> List[Event]:
        """
        Load events from a stream.
        
        Args:
            stream_id: Stream identifier
            from_version: Start from this version (0-based)
            
        Returns:
            List of events
        """
        async with self._lock:
            stream = self._streams.get(stream_id, [])
            return stream[from_version:]
    
    async def load_all(
        self,
        event_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[Event]:
        """
        Load all events.
        
        Args:
            event_type: Filter by event type
            since: Filter events after this time
            limit: Maximum events to return
            
        Returns:
            List of events
        """
        async with self._lock:
            events = self._all_events
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if since:
                events = [e for e in events if e.timestamp >= since]
            
            return events[-limit:]
    
    async def get_stream_version(self, stream_id: str) -> int:
        """Get current version of a stream."""
        async with self._lock:
            return len(self._streams.get(stream_id, []))
    
    async def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream."""
        async with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]
                return True
            return False


class ConcurrencyError(Exception):
    """Raised when there's an optimistic concurrency conflict."""
    pass


# Common event types for typical applications


@dataclass
class EntityCreated(DomainEvent):
    """Event for entity creation."""
    
    entity_id: str = ""
    entity_type: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityUpdated(DomainEvent):
    """Event for entity updates."""
    
    entity_id: str = ""
    entity_type: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    previous: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityDeleted(DomainEvent):
    """Event for entity deletion."""
    
    entity_id: str = ""
    entity_type: str = ""


@dataclass
class CommandExecuted(Event):
    """Event for command execution."""
    
    command_name: str = ""
    command_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class SystemEvent(Event):
    """Base class for system events."""
    
    level: str = "INFO"
    component: str = ""
    message: str = ""


# Message utilities


@dataclass
class Message(Generic[T]):
    """
    Generic message wrapper for typed messaging.
    
    Example:
        msg = Message(payload={"user_id": "123"}, topic="users")
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payload: Optional[T] = None
    topic: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "payload": self.payload,
            "topic": self.topic,
            "headers": self.headers,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
        }


class MessageBroker:
    """
    Simple in-memory message broker for topic-based messaging.
    
    Example:
        broker = MessageBroker()
        
        # Subscribe to topic
        async def handler(msg):
            print(msg.payload)
        
        broker.subscribe("users", handler)
        
        # Publish message
        await broker.publish("users", Message(payload={"name": "John"}))
    """
    
    def __init__(self) -> None:
        """Initialize message broker."""
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._queue: Dict[str, List[Message]] = defaultdict(list)
    
    def subscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
    ) -> None:
        """Subscribe to a topic."""
        self._subscribers[topic].append(handler)
    
    def unsubscribe(
        self,
        topic: str,
        handler: Callable[[Message], Awaitable[None]],
    ) -> bool:
        """Unsubscribe from a topic."""
        if handler in self._subscribers[topic]:
            self._subscribers[topic].remove(handler)
            return True
        return False
    
    async def publish(
        self,
        topic: str,
        message: Message,
        wait: bool = True,
    ) -> None:
        """
        Publish a message to a topic.
        
        Args:
            topic: Topic to publish to
            message: Message to publish
            wait: Whether to wait for handlers
        """
        message.topic = topic
        
        handlers = self._subscribers.get(topic, [])
        
        if not handlers:
            # Queue for later delivery
            self._queue[topic].append(message)
            return
        
        if wait:
            for handler in handlers:
                await handler(message)
        else:
            for handler in handlers:
                asyncio.create_task(handler(message))
    
    async def request(
        self,
        topic: str,
        message: Message,
        timeout: float = 5.0,
    ) -> Optional[Message]:
        """
        Send a request and wait for reply (request-reply pattern).
        
        Args:
            topic: Topic to send to
            message: Request message
            timeout: Timeout in seconds
            
        Returns:
            Reply message or None if timeout
        """
        reply_topic = f"_reply_{message.id}"
        message.reply_to = reply_topic
        
        reply: Optional[Message] = None
        reply_event = asyncio.Event()
        
        async def reply_handler(msg: Message) -> None:
            nonlocal reply
            reply = msg
            reply_event.set()
        
        self.subscribe(reply_topic, reply_handler)
        
        try:
            await self.publish(topic, message)
            await asyncio.wait_for(reply_event.wait(), timeout)
            return reply
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(reply_topic, reply_handler)
    
    def get_queued(self, topic: str) -> List[Message]:
        """Get queued messages for a topic."""
        messages = self._queue.get(topic, [])
        self._queue[topic] = []
        return messages


def create_event_bus(
    max_history: int = 1000,
    enable_history: bool = True,
) -> EventBus:
    """
    Create an event bus instance.
    
    Args:
        max_history: Maximum events to keep in history
        enable_history: Whether to enable event history
        
    Returns:
        EventBus instance
    """
    return EventBus(max_history=max_history, enable_history=enable_history)


def create_event_store() -> EventStore:
    """Create an event store instance."""
    return EventStore()


def create_message_broker() -> MessageBroker:
    """Create a message broker instance."""
    return MessageBroker()


# Convenience decorators


def on_event(
    event_bus: EventBus,
    event_type: Union[Type[Event], str, None] = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> Callable[[EventHandler], EventHandler]:
    """
    Decorator to subscribe a function to events.
    
    Example:
        @on_event(bus, UserCreated)
        async def handle_user_created(event: UserCreated):
            print(f"User {event.user_id} created")
    """
    def decorator(handler: EventHandler) -> EventHandler:
        event_bus.subscribe(event_type, handler, priority=priority)
        return handler
    return decorator


def on_message(
    broker: MessageBroker,
    topic: str,
) -> Callable:
    """
    Decorator to subscribe a function to messages.
    
    Example:
        @on_message(broker, "users")
        async def handle_user_message(message: Message):
            print(f"Received: {message.payload}")
    """
    def decorator(handler: Callable[[Message], Awaitable[None]]) -> Callable:
        broker.subscribe(topic, handler)
        return handler
    return decorator
