"""Tests for retry utilities (app/utils/retry.py).

Tests retry decorator, configuration, and circuit breaker.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.utils.retry import (
    RETRY_CONFIGS,
    CircuitBreaker,
    CircuitBreakerState,
    RetryConfig,
    ServiceUnavailableError,
    calculate_delay,
    retry,
    retry_sync,
    should_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.retry_on == (Exception,)
        assert config.exclude == ()

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            retry_on=(ValueError, TypeError),
        )
        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.retry_on == (ValueError, TypeError)


class TestPredefinedConfigs:
    """Tests for predefined retry configurations."""

    def test_database_config_exists(self):
        """Test database config exists."""
        config = RETRY_CONFIGS["database"]
        assert config.max_attempts == 3
        assert config.base_delay == 0.1

    def test_redis_config_exists(self):
        """Test redis config exists."""
        config = RETRY_CONFIGS["redis"]
        assert config.max_attempts == 3
        assert ConnectionError in config.retry_on

    def test_external_api_config_exists(self):
        """Test external API config exists."""
        config = RETRY_CONFIGS["external_api"]
        assert config.max_attempts == 5
        assert config.jitter is True

    def test_stripe_config_exists(self):
        """Test stripe config exists."""
        config = RETRY_CONFIGS["stripe"]
        assert config.max_attempts == 4
        assert config.base_delay == 2.0


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_first_attempt_delay(self):
        """Test delay for first retry attempt."""
        config = RetryConfig(base_delay=1.0, jitter=False)
        delay = calculate_delay(1, config)
        assert delay == 1.0

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(
            base_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        # Attempt 1: 1.0 * 2^0 = 1.0
        assert calculate_delay(1, config) == 1.0
        # Attempt 2: 1.0 * 2^1 = 2.0
        assert calculate_delay(2, config) == 2.0
        # Attempt 3: 1.0 * 2^2 = 4.0
        assert calculate_delay(3, config) == 4.0

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryConfig(
            base_delay=10.0,
            max_delay=15.0,
            exponential_base=2.0,
            jitter=False,
        )
        # Attempt 3: 10 * 4 = 40, but capped at 15
        delay = calculate_delay(3, config)
        assert delay == 15.0

    def test_jitter_adds_variation(self):
        """Test that jitter adds variation to delay."""
        config = RetryConfig(
            base_delay=10.0,
            jitter=True,
            jitter_factor=0.25,
        )
        delays = [calculate_delay(1, config) for _ in range(10)]
        # With jitter, not all delays should be equal
        assert len(set(delays)) > 1


class TestShouldRetry:
    """Tests for should_retry function."""

    def test_retries_matching_exception(self):
        """Test retries on matching exception type."""
        config = RetryConfig(retry_on=(ValueError,))
        assert should_retry(ValueError(), config) is True

    def test_no_retry_non_matching(self):
        """Test doesn't retry on non-matching exception."""
        config = RetryConfig(retry_on=(ValueError,))
        assert should_retry(TypeError(), config) is False

    def test_exclude_takes_precedence(self):
        """Test exclude takes precedence over retry_on."""
        config = RetryConfig(
            retry_on=(Exception,),
            exclude=(ValueError,),
        )
        assert should_retry(ValueError(), config) is False
        assert should_retry(TypeError(), config) is True


class TestRetryDecorator:
    """Tests for async retry decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_without_retry(self):
        """Test function that succeeds on first try."""
        call_count = 0

        @retry(max_attempts=3)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Test function retries on transient failure."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, jitter=False)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"

        result = await fail_then_succeed()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries(self):
        """Test raises after exhausting retries."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, jitter=False)
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_respects_exclude(self):
        """Test doesn't retry excluded exceptions."""
        call_count = 0

        @retry(max_attempts=3, exclude=(ValueError,))
        async def excluded_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Excluded")

        with pytest.raises(ValueError):
            await excluded_error()

        # Should only be called once (no retry)
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_uses_named_config(self):
        """Test uses named configuration."""
        call_count = 0

        @retry(config_name="redis")
        async def redis_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "connected"

        result = await redis_call()
        assert result == "connected"

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test on_retry callback is called."""
        callback_calls = []

        def on_retry(attempt, error, delay):
            callback_calls.append((attempt, type(error).__name__))

        @retry(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        async def with_callback():
            if len(callback_calls) < 2:
                raise ValueError("Error")
            return "done"

        await with_callback()
        assert len(callback_calls) == 2
        assert callback_calls[0][0] == 1  # First retry attempt


class TestRetrySyncDecorator:
    """Tests for sync retry decorator."""

    def test_sync_succeeds(self):
        """Test sync function succeeds."""
        call_count = 0

        @retry_sync(max_attempts=3)
        def sync_success():
            nonlocal call_count
            call_count += 1
            return "success"

        result = sync_success()
        assert result == "success"
        assert call_count == 1

    def test_sync_retries(self):
        """Test sync function retries."""
        call_count = 0

        @retry_sync(max_attempts=3, base_delay=0.01, jitter=False)
        def sync_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Error")
            return "success"

        result = sync_retry()
        assert result == "success"
        assert call_count == 2


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState."""

    def test_initial_state(self):
        """Test initial state is closed."""
        state = CircuitBreakerState()
        assert state.state == "closed"
        assert state.failures == 0

    def test_state_attributes(self):
        """Test state has required attributes."""
        state = CircuitBreakerState(
            failures=3,
            state="open",
        )
        assert state.failures == 3
        assert state.state == "open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self):
        """Test circuit starts closed."""
        breaker = CircuitBreaker("test")
        assert breaker.is_open is False

    def test_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            breaker.record_failure(Exception("Error"))

        assert breaker.is_open is True

    def test_success_resets_failures(self):
        """Test success resets failure count."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        breaker.record_failure(Exception("Error"))
        breaker.record_failure(Exception("Error"))
        breaker.record_success()

        # Should be back to 0 failures
        assert breaker._state.failures == 0

    def test_half_open_after_recovery_timeout(self):
        """Test transitions to half-open after timeout."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.01,
        )

        breaker.record_failure(Exception("Error"))
        assert breaker._state.state == "open"

        # Wait for recovery timeout
        import time

        time.sleep(0.02)

        # Check is_open triggers half-open transition
        assert breaker.is_open is False
        assert breaker._state.state == "half-open"

    def test_closes_after_successful_half_open(self):
        """Test closes after successful calls in half-open."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.01,
            half_open_max_calls=2,
        )

        # Open the circuit
        breaker.record_failure(Exception("Error"))

        # Wait and trigger half-open
        import time

        time.sleep(0.02)
        breaker.is_open  # Triggers transition

        # Record successes
        breaker.record_success()
        breaker.record_success()

        assert breaker._state.state == "closed"

    def test_reopens_on_half_open_failure(self):
        """Test reopens on failure during half-open."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.01,
        )

        breaker.record_failure(Exception("Error"))

        import time

        time.sleep(0.02)
        breaker.is_open  # Triggers half-open

        # Failure in half-open
        breaker.record_failure(Exception("Error again"))

        assert breaker._state.state == "open"

    @pytest.mark.asyncio
    async def test_decorator_usage(self):
        """Test circuit breaker as decorator."""
        breaker = CircuitBreaker("test", failure_threshold=2)
        call_count = 0

        @breaker
        async def protected_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await protected_call()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_blocks_when_open(self):
        """Test blocks calls when circuit is open."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        # Force circuit open
        breaker.record_failure(Exception("Error"))

        @breaker
        async def blocked_call():
            return "success"

        with pytest.raises(ServiceUnavailableError):
            await blocked_call()

    def test_reset(self):
        """Test manual reset."""
        breaker = CircuitBreaker("test", failure_threshold=1)
        breaker.record_failure(Exception("Error"))
        assert breaker._state.state == "open"

        breaker.reset()
        assert breaker._state.state == "closed"
        assert breaker._state.failures == 0


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError."""

    def test_exception_message(self):
        """Test exception stores message."""
        error = ServiceUnavailableError("Redis unavailable")
        assert str(error) == "Redis unavailable"
