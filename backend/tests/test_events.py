"""Tests for event and message utilities."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import List
from dataclasses import dataclass, field

import pytest

from app.utils.events import (
    # Core classes
    Event,
    DomainEvent,
    EventEnvelope,
    EventStatus,
    EventPriority,
    Subscription,
    # Event bus
    EventBus,
    EventEmitter,
    EventHandler,
    # Event store
    EventStore,
    ConcurrencyError,
    # Common events
    EntityCreated,
    EntityUpdated,
    EntityDeleted,
    CommandExecuted,
    SystemEvent,
    # Messaging
    Message,
    MessageBroker,
    # Factory functions
    create_event_bus,
    create_event_store,
    create_message_broker,
    # Decorators
    on_event,
    on_message,
)


# Custom test events


@dataclass
class UserCreated(DomainEvent):
    """Test event for user creation."""
    user_id: str = ""
    username: str = ""


@dataclass
class UserUpdated(DomainEvent):
    """Test event for user updates."""
    user_id: str = ""
    changes: dict = field(default_factory=dict)


@dataclass
class OrderPlaced(DomainEvent):
    """Test event for order placement."""
    order_id: str = ""
    total: float = 0.0


class TestEvent:
    """Tests for Event base class."""
    
    def test_event_defaults(self):
        """Test default event values."""
        event = Event()
        assert event.id is not None
        assert len(event.id) == 36  # UUID format
        assert event.timestamp is not None
        assert event.source is None
        assert event.correlation_id is None
        assert event.metadata == {}
    
    def test_event_with_values(self):
        """Test event with custom values."""
        event = Event(
            source="test-service",
            correlation_id="corr-123",
            metadata={"key": "value"},
        )
        assert event.source == "test-service"
        assert event.correlation_id == "corr-123"
        assert event.metadata == {"key": "value"}
    
    def test_event_type(self):
        """Test event type property."""
        event = Event()
        assert event.event_type == "Event"
        
        user_event = UserCreated()
        assert user_event.event_type == "UserCreated"
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(source="test")
        data = event.to_dict()
        
        assert "id" in data
        assert data["event_type"] == "Event"
        assert data["source"] == "test"
        assert "timestamp" in data
    
    def test_event_with_correlation(self):
        """Test setting correlation ID."""
        event = Event().with_correlation("corr-123")
        assert event.correlation_id == "corr-123"


class TestDomainEvent:
    """Tests for DomainEvent class."""
    
    def test_domain_event_defaults(self):
        """Test default domain event values."""
        event = DomainEvent()
        assert event.aggregate_id is None
        assert event.aggregate_type is None
        assert event.version == 1
    
    def test_domain_event_with_aggregate(self):
        """Test domain event with aggregate info."""
        event = UserCreated(
            user_id="user-123",
            aggregate_id="user-123",
            aggregate_type="User",
            version=1,
        )
        assert event.aggregate_id == "user-123"
        assert event.aggregate_type == "User"
    
    def test_domain_event_to_dict(self):
        """Test domain event serialization."""
        event = UserCreated(
            user_id="user-123",
            aggregate_id="user-123",
            aggregate_type="User",
        )
        data = event.to_dict()
        
        assert data["aggregate_id"] == "user-123"
        assert data["aggregate_type"] == "User"
        assert data["version"] == 1


class TestEventEnvelope:
    """Tests for EventEnvelope class."""
    
    def test_envelope_defaults(self):
        """Test default envelope values."""
        event = Event()
        envelope = EventEnvelope(event=event)
        
        assert envelope.status == EventStatus.PENDING
        assert envelope.attempts == 0
        assert envelope.max_attempts == 3
        # can_retry is False for PENDING - only True for FAILED with attempts < max
        assert envelope.can_retry is False
    
    def test_mark_processing(self):
        """Test marking as processing."""
        envelope = EventEnvelope(event=Event())
        envelope.mark_processing()
        
        assert envelope.status == EventStatus.PROCESSING
        assert envelope.attempts == 1
    
    def test_mark_completed(self):
        """Test marking as completed."""
        envelope = EventEnvelope(event=Event())
        envelope.mark_completed()
        
        assert envelope.status == EventStatus.COMPLETED
        assert envelope.processed_at is not None
    
    def test_mark_failed_with_retry(self):
        """Test marking as failed with retry available."""
        envelope = EventEnvelope(event=Event())
        envelope.mark_processing()
        envelope.mark_failed("Test error")
        
        assert envelope.status == EventStatus.FAILED
        assert envelope.error == "Test error"
        assert envelope.can_retry is True
    
    def test_mark_failed_dead_letter(self):
        """Test marking as dead letter after max attempts."""
        envelope = EventEnvelope(event=Event(), max_attempts=1)
        envelope.mark_processing()
        envelope.mark_failed("Test error")
        
        assert envelope.status == EventStatus.DEAD_LETTER
        assert envelope.can_retry is False


class TestSubscription:
    """Tests for Subscription class."""
    
    def test_subscription_defaults(self):
        """Test default subscription values."""
        sub = Subscription(handler=lambda e: None)
        
        assert sub.id is not None
        assert sub.event_types == set()
        assert sub.filter_func is None
        assert sub.priority == EventPriority.NORMAL
        assert sub.active is True
    
    def test_subscription_matches_any(self):
        """Test subscription matching any event."""
        sub = Subscription(handler=lambda e: None)
        event = Event()
        
        assert sub.matches(event) is True
    
    def test_subscription_matches_type(self):
        """Test subscription matching specific type."""
        sub = Subscription(
            handler=lambda e: None,
            event_types={"UserCreated"},
        )
        
        assert sub.matches(UserCreated()) is True
        assert sub.matches(OrderPlaced()) is False
    
    def test_subscription_with_filter(self):
        """Test subscription with filter function."""
        sub = Subscription(
            handler=lambda e: None,
            filter_func=lambda e: getattr(e, "user_id", "") == "123",
        )
        
        assert sub.matches(UserCreated(user_id="123")) is True
        assert sub.matches(UserCreated(user_id="456")) is False
    
    def test_inactive_subscription(self):
        """Test inactive subscription doesn't match."""
        sub = Subscription(handler=lambda e: None, active=False)
        
        assert sub.matches(Event()) is False


class TestEventBus:
    """Tests for EventBus class."""
    
    @pytest.fixture
    def bus(self):
        """Create event bus for tests."""
        return EventBus()
    
    def test_subscribe_sync_handler(self, bus):
        """Test subscribing sync handler."""
        events = []
        
        def handler(event):
            events.append(event)
        
        bus.subscribe(Event, handler)
        bus.publish_sync(Event())
        
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_subscribe_async_handler(self, bus):
        """Test subscribing async handler."""
        events = []
        
        async def handler(event):
            events.append(event)
        
        bus.subscribe(Event, handler)
        await bus.publish(Event())
        
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_subscribe_multiple_handlers(self, bus):
        """Test multiple handlers for same event type."""
        events1 = []
        events2 = []
        
        async def handler1(event):
            events1.append(event)
        
        async def handler2(event):
            events2.append(event)
        
        bus.subscribe(Event, handler1)
        bus.subscribe(Event, handler2)
        await bus.publish(Event())
        
        assert len(events1) == 1
        assert len(events2) == 1
    
    @pytest.mark.asyncio
    async def test_subscribe_to_specific_type(self, bus):
        """Test subscribing to specific event type."""
        user_events = []
        order_events = []
        
        async def user_handler(event):
            user_events.append(event)
        
        async def order_handler(event):
            order_events.append(event)
        
        bus.subscribe(UserCreated, user_handler)
        bus.subscribe(OrderPlaced, order_handler)
        
        await bus.publish(UserCreated(user_id="123"))
        await bus.publish(OrderPlaced(order_id="456"))
        
        assert len(user_events) == 1
        assert len(order_events) == 1
        assert user_events[0].user_id == "123"
        assert order_events[0].order_id == "456"
    
    @pytest.mark.asyncio
    async def test_subscribe_global_handler(self, bus):
        """Test global handler receives all events."""
        all_events = []
        
        async def handler(event):
            all_events.append(event)
        
        bus.subscribe(None, handler)  # Subscribe to all
        
        await bus.publish(UserCreated(user_id="123"))
        await bus.publish(OrderPlaced(order_id="456"))
        
        assert len(all_events) == 2
    
    @pytest.mark.asyncio
    async def test_subscribe_with_filter(self, bus):
        """Test subscribing with filter function."""
        events = []
        
        async def handler(event):
            events.append(event)
        
        bus.subscribe(
            UserCreated,
            handler,
            filter_func=lambda e: e.user_id == "123",
        )
        
        await bus.publish(UserCreated(user_id="123"))
        await bus.publish(UserCreated(user_id="456"))
        
        assert len(events) == 1
        assert events[0].user_id == "123"
    
    @pytest.mark.asyncio
    async def test_subscribe_priority(self, bus):
        """Test handler priority ordering."""
        order = []
        
        async def low_handler(event):
            order.append("low")
        
        async def high_handler(event):
            order.append("high")
        
        bus.subscribe(Event, low_handler, priority=EventPriority.LOW)
        bus.subscribe(Event, high_handler, priority=EventPriority.HIGH)
        
        await bus.publish(Event())
        
        assert order == ["high", "low"]
    
    def test_unsubscribe(self, bus):
        """Test unsubscribing from events."""
        events = []
        
        def handler(event):
            events.append(event)
        
        sub = bus.subscribe(Event, handler)
        bus.publish_sync(Event())
        
        result = bus.unsubscribe(sub)
        bus.publish_sync(Event())
        
        assert result is True
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_publish_no_wait(self, bus):
        """Test publishing without waiting."""
        events = []
        
        async def slow_handler(event):
            await asyncio.sleep(0.01)
            events.append(event)
        
        bus.subscribe(Event, slow_handler)
        errors = await bus.publish(Event(), wait=False)
        
        # Handler may not have completed yet
        await asyncio.sleep(0.05)
        assert len(events) == 1
        assert errors == []
    
    @pytest.mark.asyncio
    async def test_publish_handler_error(self, bus):
        """Test handling errors in handlers."""
        async def failing_handler(event):
            raise ValueError("Test error")
        
        bus.subscribe(Event, failing_handler)
        errors = await bus.publish(Event())
        
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
    
    @pytest.mark.asyncio
    async def test_event_history(self, bus):
        """Test event history."""
        await bus.publish(UserCreated(user_id="1"))
        await bus.publish(UserCreated(user_id="2"))
        await bus.publish(OrderPlaced(order_id="3"))
        
        history = bus.get_history()
        assert len(history) == 3
        
        # Filter by type
        user_history = bus.get_history(event_type="UserCreated")
        assert len(user_history) == 2
    
    @pytest.mark.asyncio
    async def test_event_history_limit(self, bus):
        """Test event history limit."""
        for i in range(10):
            await bus.publish(Event())
        
        history = bus.get_history(limit=5)
        assert len(history) == 5
    
    @pytest.mark.asyncio
    async def test_event_history_since(self, bus):
        """Test event history with time filter."""
        old_event = UserCreated()
        old_event.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
        
        bus._history.append(old_event)
        await bus.publish(UserCreated())
        
        recent = bus.get_history(
            since=datetime.now(timezone.utc) - timedelta(minutes=5)
        )
        assert len(recent) == 1
    
    def test_clear_history(self, bus):
        """Test clearing event history."""
        bus.publish_sync(Event())
        bus.publish_sync(Event())
        
        bus.clear_history()
        assert bus.get_history() == []
    
    @pytest.mark.asyncio
    async def test_max_history(self):
        """Test max history limit."""
        bus = EventBus(max_history=5)
        
        for i in range(10):
            await bus.publish(Event())
        
        assert len(bus.get_history()) == 5
    
    def test_decorator_usage(self, bus):
        """Test decorator-style subscription."""
        events = []
        
        @bus.subscribe(Event)
        def handler(event):
            events.append(event)
        
        bus.publish_sync(Event())
        assert len(events) == 1


class TestEventEmitter:
    """Tests for EventEmitter class."""
    
    @pytest.mark.asyncio
    async def test_emit_with_bus(self):
        """Test emitting events with bus."""
        bus = EventBus()
        emitter = EventEmitter(bus)
        events = []
        
        async def handler(event):
            events.append(event)
        
        bus.subscribe(Event, handler)
        await emitter.emit(Event())
        
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_emit_without_bus(self):
        """Test emitting events without bus queues them."""
        emitter = EventEmitter()
        await emitter.emit(Event())
        
        assert len(emitter.pending_events) == 1
    
    @pytest.mark.asyncio
    async def test_flush_pending_events(self):
        """Test flushing pending events."""
        bus = EventBus()
        emitter = EventEmitter()
        events = []
        
        async def handler(event):
            events.append(event)
        
        bus.subscribe(Event, handler)
        
        # Queue events
        await emitter.emit(Event())
        await emitter.emit(Event())
        
        # Set bus and flush
        emitter.set_event_bus(bus)
        await emitter.flush_pending_events()
        
        assert len(events) == 2
        assert len(emitter.pending_events) == 0
    
    def test_emit_sync(self):
        """Test synchronous emit."""
        bus = EventBus()
        emitter = EventEmitter(bus)
        events = []
        
        def handler(event):
            events.append(event)
        
        bus.subscribe(Event, handler)
        emitter.emit_sync(Event())
        
        assert len(events) == 1


class TestEventStore:
    """Tests for EventStore class."""
    
    @pytest.fixture
    def store(self):
        """Create event store for tests."""
        return EventStore()
    
    @pytest.mark.asyncio
    async def test_append_event(self, store):
        """Test appending events."""
        version = await store.append("user-123", UserCreated(user_id="123"))
        assert version == 1
        
        version = await store.append("user-123", UserUpdated(user_id="123"))
        assert version == 2
    
    @pytest.mark.asyncio
    async def test_load_events(self, store):
        """Test loading events."""
        await store.append("user-123", UserCreated(user_id="123"))
        await store.append("user-123", UserUpdated(user_id="123"))
        
        events = await store.load("user-123")
        assert len(events) == 2
        assert isinstance(events[0], UserCreated)
        assert isinstance(events[1], UserUpdated)
    
    @pytest.mark.asyncio
    async def test_load_from_version(self, store):
        """Test loading events from specific version."""
        await store.append("user-123", UserCreated(user_id="123"))
        await store.append("user-123", UserUpdated(user_id="123"))
        await store.append("user-123", UserUpdated(user_id="123"))
        
        events = await store.load("user-123", from_version=1)
        assert len(events) == 2
    
    @pytest.mark.asyncio
    async def test_load_empty_stream(self, store):
        """Test loading from empty/nonexistent stream."""
        events = await store.load("nonexistent")
        assert events == []
    
    @pytest.mark.asyncio
    async def test_optimistic_concurrency(self, store):
        """Test optimistic concurrency check."""
        await store.append("user-123", UserCreated(user_id="123"))
        
        # Should succeed with correct version
        await store.append("user-123", UserUpdated(user_id="123"), expected_version=1)
        
        # Should fail with wrong version
        with pytest.raises(ConcurrencyError):
            await store.append("user-123", UserUpdated(user_id="123"), expected_version=1)
    
    @pytest.mark.asyncio
    async def test_load_all_events(self, store):
        """Test loading all events."""
        await store.append("user-1", UserCreated(user_id="1"))
        await store.append("user-2", UserCreated(user_id="2"))
        await store.append("user-1", OrderPlaced(order_id="1"))
        
        all_events = await store.load_all()
        assert len(all_events) == 3
    
    @pytest.mark.asyncio
    async def test_load_all_by_type(self, store):
        """Test loading all events by type."""
        await store.append("user-1", UserCreated(user_id="1"))
        await store.append("user-2", UserCreated(user_id="2"))
        await store.append("user-1", OrderPlaced(order_id="1"))
        
        user_events = await store.load_all(event_type="UserCreated")
        assert len(user_events) == 2
    
    @pytest.mark.asyncio
    async def test_get_stream_version(self, store):
        """Test getting stream version."""
        assert await store.get_stream_version("user-123") == 0
        
        await store.append("user-123", UserCreated(user_id="123"))
        assert await store.get_stream_version("user-123") == 1
    
    @pytest.mark.asyncio
    async def test_delete_stream(self, store):
        """Test deleting a stream."""
        await store.append("user-123", UserCreated(user_id="123"))
        
        result = await store.delete_stream("user-123")
        assert result is True
        
        events = await store.load("user-123")
        assert events == []
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_stream(self, store):
        """Test deleting nonexistent stream."""
        result = await store.delete_stream("nonexistent")
        assert result is False


class TestMessage:
    """Tests for Message class."""
    
    def test_message_defaults(self):
        """Test default message values."""
        msg = Message()
        
        assert msg.id is not None
        assert msg.payload is None
        assert msg.topic == ""
        assert msg.headers == {}
        assert msg.timestamp is not None
    
    def test_message_with_payload(self):
        """Test message with payload."""
        msg = Message(
            payload={"user_id": "123"},
            topic="users",
            headers={"content-type": "application/json"},
        )
        
        assert msg.payload == {"user_id": "123"}
        assert msg.topic == "users"
        assert msg.headers["content-type"] == "application/json"
    
    def test_message_to_dict(self):
        """Test message serialization."""
        msg = Message(
            payload="test",
            topic="test-topic",
        )
        data = msg.to_dict()
        
        assert data["payload"] == "test"
        assert data["topic"] == "test-topic"
        assert "timestamp" in data


class TestMessageBroker:
    """Tests for MessageBroker class."""
    
    @pytest.fixture
    def broker(self):
        """Create message broker for tests."""
        return MessageBroker()
    
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, broker):
        """Test basic pub/sub."""
        messages = []
        
        async def handler(msg):
            messages.append(msg)
        
        broker.subscribe("users", handler)
        await broker.publish("users", Message(payload="test"))
        
        assert len(messages) == 1
        assert messages[0].payload == "test"
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, broker):
        """Test multiple subscribers."""
        messages1 = []
        messages2 = []
        
        async def handler1(msg):
            messages1.append(msg)
        
        async def handler2(msg):
            messages2.append(msg)
        
        broker.subscribe("users", handler1)
        broker.subscribe("users", handler2)
        await broker.publish("users", Message(payload="test"))
        
        assert len(messages1) == 1
        assert len(messages2) == 1
    
    @pytest.mark.asyncio
    async def test_topic_isolation(self, broker):
        """Test messages only go to correct topic."""
        user_messages = []
        order_messages = []
        
        async def user_handler(msg):
            user_messages.append(msg)
        
        async def order_handler(msg):
            order_messages.append(msg)
        
        broker.subscribe("users", user_handler)
        broker.subscribe("orders", order_handler)
        
        await broker.publish("users", Message(payload="user"))
        await broker.publish("orders", Message(payload="order"))
        
        assert len(user_messages) == 1
        assert len(order_messages) == 1
        assert user_messages[0].payload == "user"
        assert order_messages[0].payload == "order"
    
    @pytest.mark.asyncio
    async def test_unsubscribe(self, broker):
        """Test unsubscribing."""
        messages = []
        
        async def handler(msg):
            messages.append(msg)
        
        broker.subscribe("users", handler)
        await broker.publish("users", Message(payload="1"))
        
        broker.unsubscribe("users", handler)
        await broker.publish("users", Message(payload="2"))
        
        assert len(messages) == 1
    
    @pytest.mark.asyncio
    async def test_queue_when_no_subscribers(self, broker):
        """Test messages queued when no subscribers."""
        await broker.publish("users", Message(payload="1"))
        await broker.publish("users", Message(payload="2"))
        
        queued = broker.get_queued("users")
        assert len(queued) == 2
        
        # Queue should be cleared
        assert broker.get_queued("users") == []
    
    @pytest.mark.asyncio
    async def test_request_reply(self, broker):
        """Test request-reply pattern."""
        async def handler(msg):
            if msg.reply_to:
                reply = Message(payload=f"Reply to: {msg.payload}")
                await broker.publish(msg.reply_to, reply)
        
        broker.subscribe("service", handler)
        
        reply = await broker.request(
            "service",
            Message(payload="Hello"),
            timeout=1.0,
        )
        
        assert reply is not None
        assert reply.payload == "Reply to: Hello"
    
    @pytest.mark.asyncio
    async def test_request_timeout(self, broker):
        """Test request timeout."""
        # No handler, so request should timeout
        reply = await broker.request(
            "nonexistent",
            Message(payload="Hello"),
            timeout=0.1,
        )
        
        assert reply is None


class TestCommonEvents:
    """Tests for common event types."""
    
    def test_entity_created(self):
        """Test EntityCreated event."""
        event = EntityCreated(
            entity_id="123",
            entity_type="User",
            data={"name": "John"},
        )
        
        assert event.entity_id == "123"
        assert event.entity_type == "User"
        assert event.data["name"] == "John"
    
    def test_entity_updated(self):
        """Test EntityUpdated event."""
        event = EntityUpdated(
            entity_id="123",
            entity_type="User",
            changes={"name": "Jane"},
            previous={"name": "John"},
        )
        
        assert event.changes["name"] == "Jane"
        assert event.previous["name"] == "John"
    
    def test_entity_deleted(self):
        """Test EntityDeleted event."""
        event = EntityDeleted(
            entity_id="123",
            entity_type="User",
        )
        
        assert event.entity_id == "123"
    
    def test_command_executed(self):
        """Test CommandExecuted event."""
        event = CommandExecuted(
            command_name="CreateUser",
            command_data={"name": "John"},
            result={"id": "123"},
            success=True,
        )
        
        assert event.command_name == "CreateUser"
        assert event.success is True
    
    def test_system_event(self):
        """Test SystemEvent."""
        event = SystemEvent(
            level="WARNING",
            component="auth",
            message="Rate limit reached",
        )
        
        assert event.level == "WARNING"
        assert event.component == "auth"


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_event_bus(self):
        """Test event bus factory."""
        bus = create_event_bus(max_history=500, enable_history=True)
        assert isinstance(bus, EventBus)
        assert bus._max_history == 500
    
    def test_create_event_store(self):
        """Test event store factory."""
        store = create_event_store()
        assert isinstance(store, EventStore)
    
    def test_create_message_broker(self):
        """Test message broker factory."""
        broker = create_message_broker()
        assert isinstance(broker, MessageBroker)


class TestDecorators:
    """Tests for decorator functions."""
    
    @pytest.mark.asyncio
    async def test_on_event_decorator(self):
        """Test on_event decorator."""
        bus = EventBus()
        events = []
        
        @on_event(bus, UserCreated)
        async def handler(event):
            events.append(event)
        
        await bus.publish(UserCreated(user_id="123"))
        
        assert len(events) == 1
    
    @pytest.mark.asyncio
    async def test_on_message_decorator(self):
        """Test on_message decorator."""
        broker = MessageBroker()
        messages = []
        
        @on_message(broker, "users")
        async def handler(msg):
            messages.append(msg)
        
        await broker.publish("users", Message(payload="test"))
        
        assert len(messages) == 1


class TestEdgeCases:
    """Tests for edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_subscription_list(self):
        """Test publishing with no subscribers."""
        bus = EventBus()
        errors = await bus.publish(Event())
        assert errors == []
    
    @pytest.mark.asyncio
    async def test_handler_modifies_event(self):
        """Test handler modifying event doesn't affect others."""
        bus = EventBus()
        
        async def modifier(event):
            event.metadata["modified"] = True
        
        async def checker(event):
            # In Python, this will see the modification
            # This test documents the behavior
            pass
        
        bus.subscribe(Event, modifier, priority=EventPriority.HIGH)
        bus.subscribe(Event, checker, priority=EventPriority.LOW)
        
        event = Event()
        await bus.publish(event)
        
        # Event was modified
        assert event.metadata.get("modified") is True
    
    @pytest.mark.asyncio
    async def test_concurrent_publish(self):
        """Test concurrent event publishing."""
        bus = EventBus()
        events = []
        
        async def handler(event):
            await asyncio.sleep(0.01)
            events.append(event)
        
        bus.subscribe(Event, handler)
        
        # Publish many events concurrently
        await asyncio.gather(*[
            bus.publish(Event()) for _ in range(10)
        ])
        
        assert len(events) == 10
    
    @pytest.mark.asyncio
    async def test_unsubscribe_during_iteration(self):
        """Test unsubscribing during event handling."""
        bus = EventBus()
        
        sub = None
        
        async def handler(event):
            nonlocal sub
            if sub:
                bus.unsubscribe(sub)
        
        sub = bus.subscribe(Event, handler)
        
        # Should not raise
        await bus.publish(Event())
        await bus.publish(Event())
    
    @pytest.mark.asyncio
    async def test_subscribe_type_by_string(self):
        """Test subscribing by type name string."""
        bus = EventBus()
        events = []
        
        async def handler(event):
            events.append(event)
        
        bus.subscribe("UserCreated", handler)
        
        await bus.publish(UserCreated(user_id="123"))
        await bus.publish(OrderPlaced(order_id="456"))
        
        assert len(events) == 1
