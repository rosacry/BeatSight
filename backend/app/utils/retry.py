"""Retry utilities for handling transient failures.

This module provides:
- Configurable retry decorator with exponential backoff
- Retry configuration for different failure types
- Circuit breaker pattern for failing dependencies

Usage:
    from app.utils.retry import retry, RetryConfig

    # Basic retry with defaults
    @retry()
    async def call_external_api():
        ...

    # Custom retry configuration
    @retry(max_attempts=5, base_delay=0.5, max_delay=30.0)
    async def call_flaky_service():
        ...

    # Retry only specific exceptions
    @retry(retry_on=(ConnectionError, TimeoutError))
    async def connect_to_redis():
        ...
"""

from __future__ import annotations

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, TypeVar

from app.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# =============================================================================
# RETRY CONFIGURATION
# =============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including initial try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries (cap for exponential backoff)
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        jitter_factor: Maximum jitter as fraction of delay (0.0-1.0)
        retry_on: Tuple of exception types to retry on
        exclude: Tuple of exception types to NOT retry on
        on_retry: Optional callback called on each retry
    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.25
    retry_on: tuple[type[Exception], ...] = (Exception,)
    exclude: tuple[type[Exception], ...] = ()
    on_retry: Callable[[int, Exception, float], None] | None = None


# Predefined configurations for common scenarios
RETRY_CONFIGS = {
    # Database operations - short delays, few retries
    "database": RetryConfig(
        max_attempts=3,
        base_delay=0.1,
        max_delay=2.0,
        retry_on=(Exception,),
        exclude=(ValueError, TypeError, KeyError),
    ),
    # Redis operations - very short delays
    "redis": RetryConfig(
        max_attempts=3,
        base_delay=0.05,
        max_delay=1.0,
        retry_on=(ConnectionError, TimeoutError, OSError),
    ),
    # External API calls - longer delays, more retries
    "external_api": RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        jitter=True,
    ),
    # Stripe API - respect rate limits
    "stripe": RetryConfig(
        max_attempts=4,
        base_delay=2.0,
        max_delay=60.0,
        jitter=True,
    ),
    # Email sending - moderate retries
    "email": RetryConfig(
        max_attempts=3,
        base_delay=5.0,
        max_delay=60.0,
    ),
    # File operations - quick retries
    "file_io": RetryConfig(
        max_attempts=3,
        base_delay=0.1,
        max_delay=1.0,
        retry_on=(IOError, OSError, PermissionError),
    ),
}


# =============================================================================
# RETRY DECORATOR
# =============================================================================


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay for next retry attempt.

    Uses exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (1-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds before next retry
    """
    # Exponential backoff: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))

    # Cap at max_delay
    delay = min(delay, config.max_delay)

    # Add jitter if enabled
    if config.jitter:
        jitter_range = delay * config.jitter_factor
        delay += random.uniform(-jitter_range, jitter_range)

    # Ensure delay is positive
    return max(0.0, delay)


def should_retry(
    exception: Exception,
    config: RetryConfig,
) -> bool:
    """Determine if exception should trigger retry.

    Args:
        exception: The raised exception
        config: Retry configuration

    Returns:
        True if should retry, False otherwise
    """
    # Check exclusions first
    if isinstance(exception, config.exclude):
        return False

    # Check if it's a retryable exception
    return isinstance(exception, config.retry_on)


def retry(
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool | None = None,
    retry_on: tuple[type[Exception], ...] | None = None,
    exclude: tuple[type[Exception], ...] | None = None,
    config_name: str | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
):
    """Decorator for retrying async functions with exponential backoff.

    Can be used with default settings, custom parameters, or a named config.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay cap
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter
        retry_on: Exception types to retry on
        exclude: Exception types to NOT retry on
        config_name: Name of predefined config to use
        on_retry: Callback called on each retry

    Returns:
        Decorated function with retry behavior

    Examples:
        @retry()
        async def default_retry():
            ...

        @retry(max_attempts=5, base_delay=2.0)
        async def custom_retry():
            ...

        @retry(config_name="stripe")
        async def stripe_call():
            ...
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        # Build configuration
        if config_name:
            base_config = RETRY_CONFIGS.get(config_name, RetryConfig())
        else:
            base_config = RetryConfig()

        # Override with provided parameters
        config = RetryConfig(
            max_attempts=(
                max_attempts if max_attempts is not None else base_config.max_attempts
            ),
            base_delay=(
                base_delay if base_delay is not None else base_config.base_delay
            ),
            max_delay=max_delay if max_delay is not None else base_config.max_delay,
            exponential_base=(
                exponential_base
                if exponential_base is not None
                else base_config.exponential_base
            ),
            jitter=jitter if jitter is not None else base_config.jitter,
            retry_on=retry_on if retry_on is not None else base_config.retry_on,
            exclude=exclude if exclude is not None else base_config.exclude,
            on_retry=on_retry if on_retry is not None else base_config.on_retry,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if not should_retry(e, config):
                        logger.debug(
                            "retry_not_applicable",
                            func=func.__name__,
                            attempt=attempt,
                            error_type=type(e).__name__,
                        )
                        raise

                    # Check if we have more attempts
                    if attempt >= config.max_attempts:
                        logger.warning(
                            "retry_exhausted",
                            func=func.__name__,
                            total_attempts=attempt,
                            error_type=type(e).__name__,
                            error=str(e),
                        )
                        raise

                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)

                    logger.info(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay_seconds=round(delay, 3),
                        error_type=type(e).__name__,
                        error=str(e)[:100],
                    )

                    # Call on_retry callback if provided
                    if config.on_retry:
                        try:
                            config.on_retry(attempt, e, delay)
                        except Exception:
                            pass  # Don't fail on callback errors

                    await asyncio.sleep(delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    exponential_base: float | None = None,
    jitter: bool | None = None,
    retry_on: tuple[type[Exception], ...] | None = None,
    exclude: tuple[type[Exception], ...] | None = None,
    config_name: str | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
):
    """Decorator for retrying synchronous functions with exponential backoff.

    Same as @retry but for sync functions.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Build configuration (same logic as async version)
        if config_name:
            base_config = RETRY_CONFIGS.get(config_name, RetryConfig())
        else:
            base_config = RetryConfig()

        config = RetryConfig(
            max_attempts=(
                max_attempts if max_attempts is not None else base_config.max_attempts
            ),
            base_delay=(
                base_delay if base_delay is not None else base_config.base_delay
            ),
            max_delay=max_delay if max_delay is not None else base_config.max_delay,
            exponential_base=(
                exponential_base
                if exponential_base is not None
                else base_config.exponential_base
            ),
            jitter=jitter if jitter is not None else base_config.jitter,
            retry_on=retry_on if retry_on is not None else base_config.retry_on,
            exclude=exclude if exclude is not None else base_config.exclude,
            on_retry=on_retry if on_retry is not None else base_config.on_retry,
        )

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not should_retry(e, config):
                        raise

                    if attempt >= config.max_attempts:
                        raise

                    delay = calculate_delay(attempt, config)

                    logger.info(
                        "retry_attempt_sync",
                        func=func.__name__,
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        delay_seconds=round(delay, 3),
                        error_type=type(e).__name__,
                    )

                    if config.on_retry:
                        try:
                            config.on_retry(attempt, e, delay)
                        except Exception:
                            pass

                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")

        return wrapper

    return decorator


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker."""

    failures: int = 0
    last_failure_time: datetime | None = None
    state: str = "closed"  # closed, open, half-open
    success_count: int = 0


class CircuitBreaker:
    """Circuit breaker pattern for failing dependencies.

    Prevents cascading failures by temporarily blocking calls
    to a failing service after a threshold of failures.

    States:
    - CLOSED: Normal operation, calls go through
    - OPEN: Failing, calls are blocked
    - HALF-OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker("redis", failure_threshold=5)

        @breaker
        async def call_redis():
            ...
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """Initialize circuit breaker.

        Args:
            name: Name for logging/identification
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            half_open_max_calls: Successful calls to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitBreakerState()

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)."""
        if self._state.state == "closed":
            return False

        if self._state.state == "open":
            # Check if we should transition to half-open
            if self._state.last_failure_time:
                elapsed = (
                    datetime.now(timezone.utc) - self._state.last_failure_time
                ).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state.state = "half-open"
                    self._state.success_count = 0
                    logger.info(
                        "circuit_breaker_half_open",
                        name=self.name,
                    )
                    return False
            return True

        return False  # half-open allows calls

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state.state == "half-open":
            self._state.success_count += 1
            if self._state.success_count >= self.half_open_max_calls:
                self._state.state = "closed"
                self._state.failures = 0
                logger.info(
                    "circuit_breaker_closed",
                    name=self.name,
                )
        elif self._state.state == "closed":
            # Reset failure count on success
            self._state.failures = 0

    def record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._state.failures += 1
        self._state.last_failure_time = datetime.now(timezone.utc)

        if self._state.state == "half-open":
            # Any failure in half-open goes back to open
            self._state.state = "open"
            logger.warning(
                "circuit_breaker_reopened",
                name=self.name,
                error=str(error)[:100],
            )
        elif self._state.failures >= self.failure_threshold:
            self._state.state = "open"
            logger.warning(
                "circuit_breaker_opened",
                name=self.name,
                failures=self._state.failures,
                error=str(error)[:100],
            )

    def __call__(
        self, func: Callable[..., Coroutine[Any, Any, T]]
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        """Decorator to wrap async function with circuit breaker."""

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if self.is_open:
                raise ServiceUnavailableError(
                    f"Circuit breaker open for {self.name}"
                )

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise

        return wrapper

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitBreakerState()
        logger.info("circuit_breaker_reset", name=self.name)


class ServiceUnavailableError(Exception):
    """Raised when circuit breaker is open."""

    pass
