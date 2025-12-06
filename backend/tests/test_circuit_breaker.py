"""Tests for circuit breaker utilities in app/utils/circuit_breaker.py."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.utils.circuit_breaker import (
    # Core classes
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitState,
    CallRecord,
    # Exceptions
    CircuitOpenError,
    # Decorator
    circuit_breaker,
    # Global functions
    get_registry,
    reset_registry,
    create_circuit_breaker,
    create_registry,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.timeout == 30.0
        assert config.half_open_max_calls == 1
        assert config.failure_rate_threshold == 0.5

    def test_custom_config(self):
        """Test custom configuration."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout=60.0,
        )

        assert config.failure_threshold == 3
        assert config.success_threshold == 2
        assert config.timeout == 60.0

    def test_invalid_failure_threshold(self):
        """Test validation rejects invalid failure_threshold."""
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreakerConfig(failure_threshold=0)

    def test_invalid_success_threshold(self):
        """Test validation rejects invalid success_threshold."""
        with pytest.raises(ValueError, match="success_threshold"):
            CircuitBreakerConfig(success_threshold=0)

    def test_invalid_timeout(self):
        """Test validation rejects negative timeout."""
        with pytest.raises(ValueError, match="timeout"):
            CircuitBreakerConfig(timeout=-1)

    def test_invalid_failure_rate_threshold(self):
        """Test validation rejects invalid failure_rate_threshold."""
        with pytest.raises(ValueError, match="failure_rate_threshold"):
            CircuitBreakerConfig(failure_rate_threshold=1.5)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_state_values(self):
        """Test state enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCallRecord:
    """Tests for CallRecord class."""

    def test_call_record_creation(self):
        """Test creating a call record."""
        record = CallRecord(success=True, duration=0.1)

        assert record.success
        assert record.duration == 0.1
        assert record.timestamp is not None

    def test_call_record_slow_check(self):
        """Test slow call detection."""
        fast_record = CallRecord(duration=1.0)
        slow_record = CallRecord(duration=10.0)

        assert not fast_record.is_slow
        assert slow_record.is_slow


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_closed(self):
        """Test circuit starts in closed state."""
        breaker = CircuitBreaker("test")

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open

    def test_successful_calls(self):
        """Test successful calls pass through."""
        breaker = CircuitBreaker("test")

        def success_func():
            return "success"

        result = breaker.call(success_func)

        assert result == "success"
        assert breaker.is_closed

    def test_failures_open_circuit(self):
        """Test failures open the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        def fail_func():
            raise ValueError("error")

        # Fail 3 times to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(fail_func)

        assert breaker.is_open

    def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Force failure to open
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        # Next call should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            breaker.call(lambda: "success")

        assert exc_info.value.circuit_name == "test"
        assert exc_info.value.remaining_time > 0

    def test_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert breaker.is_open

        # Wait for timeout
        time.sleep(0.15)

        # Should be half-open now
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        """Test success in half-open closes circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout=0.1,
        )
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        # Wait for timeout
        time.sleep(0.15)

        # Successful call in half-open should close
        result = breaker.call(lambda: "success")

        assert result == "success"
        assert breaker.is_closed

    def test_half_open_failure_reopens(self):
        """Test failure in half-open reopens circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.1,
        )
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        # Wait for timeout
        time.sleep(0.15)

        # Fail in half-open
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert breaker.is_open

    def test_excluded_exceptions(self):
        """Test excluded exceptions don't count as failures."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(
            "test",
            config,
            excluded_exceptions={ValueError},
        )

        def raise_value_error():
            raise ValueError("not a failure")

        # These shouldn't open the circuit
        for _ in range(5):
            with pytest.raises(ValueError):
                breaker.call(raise_value_error)

        assert breaker.is_closed

    def test_state_change_callback(self):
        """Test state change callback is called."""
        config = CircuitBreakerConfig(failure_threshold=1)
        state_changes = []

        def on_change(old, new):
            state_changes.append((old, new))

        breaker = CircuitBreaker("test", config, on_state_change=on_change)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert len(state_changes) == 1
        assert state_changes[0] == (CircuitState.CLOSED, CircuitState.OPEN)

    def test_on_open_callback(self):
        """Test on_open callback is called."""
        config = CircuitBreakerConfig(failure_threshold=1)
        opened = []

        breaker = CircuitBreaker("test", config, on_open=lambda: opened.append(True))

        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert len(opened) == 1

    def test_on_close_callback(self):
        """Test on_close callback is called."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=1,
            timeout=0.1,
        )
        closed = []

        breaker = CircuitBreaker("test", config, on_close=lambda: closed.append(True))

        # Open then close
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        time.sleep(0.15)
        breaker.call(lambda: "success")

        assert len(closed) == 1

    def test_reset(self):
        """Test resetting circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert breaker.is_open

        breaker.reset()

        assert breaker.is_closed

    def test_force_open(self):
        """Test forcing circuit open."""
        breaker = CircuitBreaker("test")

        breaker.force_open()

        assert breaker.is_open

    def test_force_close(self):
        """Test forcing circuit closed."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        breaker.force_close()

        assert breaker.is_closed

    def test_get_stats(self):
        """Test getting circuit breaker statistics."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker("test", config)

        # Make some calls
        breaker.call(lambda: "success")
        breaker.call(lambda: "success")
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        stats = breaker.get_stats()

        assert stats.state == CircuitState.CLOSED
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.total_calls == 3

    @pytest.mark.asyncio
    async def test_async_call(self):
        """Test async call method."""
        breaker = CircuitBreaker("test")

        async def async_func():
            await asyncio.sleep(0.01)
            return "success"

        result = await breaker.call_async(async_func)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_failures(self):
        """Test async failures open circuit."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def async_fail():
            raise ValueError("error")

        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call_async(async_fail)

        assert breaker.is_open

    def test_failure_rate_opens_circuit(self):
        """Test failure rate threshold opens circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High so it doesn't trigger
            failure_rate_threshold=0.5,
            window_size=4,
        )
        breaker = CircuitBreaker("test", config)

        # 2 success, 2 failures = 50% failure rate
        breaker.call(lambda: "success")
        breaker.call(lambda: "success")
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert breaker.is_open


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    def test_get_creates_breaker(self):
        """Test getting creates a new breaker."""
        registry = CircuitBreakerRegistry()

        breaker = registry.get("test")

        assert breaker.name == "test"

    def test_get_returns_same_instance(self):
        """Test getting same name returns same instance."""
        registry = CircuitBreakerRegistry()

        breaker1 = registry.get("test")
        breaker2 = registry.get("test")

        assert breaker1 is breaker2

    def test_get_with_config(self):
        """Test getting with custom config."""
        registry = CircuitBreakerRegistry()
        config = CircuitBreakerConfig(failure_threshold=10)

        breaker = registry.get("test", config)

        assert breaker.config.failure_threshold == 10

    def test_get_all_stats(self):
        """Test getting stats for all breakers."""
        registry = CircuitBreakerRegistry()
        registry.get("api")
        registry.get("db")

        stats = registry.get_all_stats()

        assert "api" in stats
        assert "db" in stats

    def test_reset_all(self):
        """Test resetting all breakers."""
        config = CircuitBreakerConfig(failure_threshold=1)
        registry = CircuitBreakerRegistry(default_config=config)

        breaker = registry.get("test")

        # Open it
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        assert breaker.is_open

        registry.reset_all()

        assert breaker.is_closed

    def test_remove(self):
        """Test removing a breaker."""
        registry = CircuitBreakerRegistry()
        registry.get("test")

        assert "test" in registry.list_names()

        registry.remove("test")

        assert "test" not in registry.list_names()

    def test_list_names(self):
        """Test listing breaker names."""
        registry = CircuitBreakerRegistry()
        registry.get("api")
        registry.get("db")
        registry.get("cache")

        names = registry.list_names()

        assert sorted(names) == ["api", "cache", "db"]


class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator."""

    def test_decorator_sync(self):
        """Test decorator with sync function."""

        @circuit_breaker("test_sync")
        def my_func():
            return "success"

        result = my_func()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_async(self):
        """Test decorator with async function."""

        @circuit_breaker("test_async")
        async def my_func():
            return "success"

        result = await my_func()

        assert result == "success"

    def test_decorator_with_fallback(self):
        """Test decorator with fallback function."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=100)
        registry = CircuitBreakerRegistry()

        def fallback():
            return "fallback_value"

        @circuit_breaker(
            "test_fallback", config=config, registry=registry, fallback=fallback
        )
        def my_func():
            raise ValueError("error")

        # First call fails and opens circuit
        with pytest.raises(ValueError):
            my_func()

        # Second call uses fallback
        result = my_func()

        assert result == "fallback_value"

    @pytest.mark.asyncio
    async def test_decorator_async_fallback(self):
        """Test decorator with async fallback."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=100)
        registry = CircuitBreakerRegistry()

        async def fallback():
            return "async_fallback"

        @circuit_breaker(
            "test_async_fb", config=config, registry=registry, fallback=fallback
        )
        async def my_func():
            raise ValueError("error")

        # Open circuit
        with pytest.raises(ValueError):
            await my_func()

        # Use fallback
        result = await my_func()

        assert result == "async_fallback"


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def setup_method(self):
        """Reset global registry before each test."""
        reset_registry()

    def teardown_method(self):
        """Clean up global registry."""
        reset_registry()

    def test_get_registry_creates_singleton(self):
        """Test get_registry creates singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_reset_registry(self):
        """Test resetting global registry."""
        registry = get_registry()
        registry.get("test")  # Create a breaker

        reset_registry()

        new_registry = get_registry()
        assert new_registry is not registry


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_circuit_breaker(self):
        """Test create_circuit_breaker function."""
        breaker = create_circuit_breaker(
            "test",
            failure_threshold=3,
            success_threshold=2,
            timeout=60.0,
        )

        assert breaker.name == "test"
        assert breaker.config.failure_threshold == 3
        assert breaker.config.success_threshold == 2
        assert breaker.config.timeout == 60.0

    def test_create_registry(self):
        """Test create_registry function."""
        registry = create_registry()

        assert isinstance(registry, CircuitBreakerRegistry)


class TestCircuitBreakerStats:
    """Tests for CircuitBreakerStats class."""

    def test_stats_to_dict(self):
        """Test stats serialization."""
        stats = CircuitBreakerStats(
            state=CircuitState.CLOSED,
            failure_count=5,
            success_count=10,
            total_calls=15,
        )

        data = stats.to_dict()

        assert data["state"] == "closed"
        assert data["failure_count"] == 5
        assert data["success_count"] == 10
        assert data["total_calls"] == 15


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_multiple_rapid_failures(self):
        """Test handling multiple rapid failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        for _ in range(10):
            try:
                breaker.call(lambda: 1 / 0)
            except (ZeroDivisionError, CircuitOpenError):
                pass

        assert breaker.is_open

    def test_slow_calls_tracking(self):
        """Test slow calls are tracked in call records.

        Note: In the current implementation, slow but successful calls
        are recorded but don't directly trigger circuit opening.
        The slow_call_rate is used for monitoring/metrics, and the circuit
        only opens based on actual failures.
        """
        config = CircuitBreakerConfig(
            slow_call_duration=0.01,  # Very short threshold
            slow_call_rate_threshold=0.5,
            window_size=4,
            failure_threshold=100,  # High to not trigger
            failure_rate_threshold=1.0,  # Disable failure rate
        )
        breaker = CircuitBreaker("test", config)

        # Slow calls (>10ms) - but they're successful
        def slow_func():
            time.sleep(0.02)
            return "slow"

        # All 4 calls are slow = 100% slow rate
        for _ in range(4):
            breaker.call(slow_func)

        # Verify slow calls are being tracked in the window
        assert len(breaker._call_records) == 4
        slow_count = sum(
            1 for r in breaker._call_records if r.duration > config.slow_call_duration
        )
        assert slow_count == 4  # All calls should be marked as slow

        # Circuit stays closed because slow successful calls
        # don't trigger opening (only failures do)
        assert breaker.is_closed

    def test_circuit_open_error_message(self):
        """Test CircuitOpenError message."""
        error = CircuitOpenError("my_circuit", 15.5)

        assert "my_circuit" in str(error)
        assert "15.5" in str(error)

    def test_half_open_max_calls(self):
        """Test half-open limits concurrent calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.1,
            half_open_max_calls=1,
        )
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        with pytest.raises(ZeroDivisionError):
            breaker.call(lambda: 1 / 0)

        time.sleep(0.15)

        # First call in half-open should succeed
        assert breaker.state == CircuitState.HALF_OPEN

        # Simulate the internal counter being at max
        breaker._half_open_calls = 1

        # Next call should be rejected
        with pytest.raises(CircuitOpenError):
            breaker.call(lambda: "test")
