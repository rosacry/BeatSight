"""
Circuit breaker pattern utilities.

This module provides utilities for:
- Circuit breaker pattern implementation
- Failure tracking and recovery
- Half-open state with gradual recovery
- Configurable failure thresholds and timeouts
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Set,
    TypeVar,
)


# Type variables
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(Enum):
    """States of the circuit breaker."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""

    pass


class CircuitOpenError(CircuitBreakerError):
    """Raised when circuit is open and request is rejected."""

    def __init__(
        self,
        circuit_name: str,
        remaining_time: float,
    ) -> None:
        self.circuit_name = circuit_name
        self.remaining_time = remaining_time
        super().__init__(
            f"Circuit '{circuit_name}' is open. "
            f"Retry after {remaining_time:.1f} seconds."
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes to close from half-open
    timeout: float = 30.0  # Seconds before attempting recovery
    half_open_max_calls: int = 1  # Max concurrent calls in half-open
    failure_rate_threshold: float = 0.5  # Failure rate to open (0-1)
    slow_call_duration: float = 5.0  # Seconds to consider call slow
    slow_call_rate_threshold: float = 0.5  # Slow call rate to open
    window_size: int = 10  # Rolling window size for rate calculation

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        if self.timeout < 0:
            raise ValueError("timeout must be >= 0")
        if not 0 <= self.failure_rate_threshold <= 1:
            raise ValueError("failure_rate_threshold must be between 0 and 1")
        if not 0 <= self.slow_call_rate_threshold <= 1:
            raise ValueError("slow_call_rate_threshold must be between 0 and 1")


@dataclass
class CallRecord:
    """Record of a single call."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    duration: float = 0.0
    error: Optional[str] = None

    @property
    def is_slow(self) -> bool:
        """Check if call was slow (based on default threshold)."""
        return self.duration > 5.0


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker."""

    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: Optional[datetime] = None
    failure_rate: float = 0.0
    slow_call_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "rejected_calls": self.rejected_calls,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
            "last_state_change": (
                self.last_state_change.isoformat() if self.last_state_change else None
            ),
            "failure_rate": self.failure_rate,
            "slow_call_rate": self.slow_call_rate,
        }


class CircuitBreaker:
    """
    A circuit breaker implementation.

    The circuit breaker prevents cascading failures by stopping requests
    to a failing service and allowing it time to recover.

    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Example:
        breaker = CircuitBreaker("external_api", failure_threshold=3)

        try:
            result = await breaker.call(make_api_request, url, data)
        except CircuitOpenError:
            # Handle circuit open (use fallback, return cached data, etc.)
            pass
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        *,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        excluded_exceptions: Optional[Set[type]] = None,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            name: Name of this circuit breaker
            config: Configuration options
            on_state_change: Callback when state changes
            on_open: Callback when circuit opens
            on_close: Callback when circuit closes
            excluded_exceptions: Exceptions that should not count as failures
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._total_calls = 0
        self._rejected_calls = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()
        self._call_records: Deque[CallRecord] = deque(maxlen=self.config.window_size)
        self._on_state_change = on_state_change
        self._on_open = on_open
        self._on_close = on_close
        self._excluded_exceptions = excluded_exceptions or set()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for timeout transition."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if new_state == self._state:
            return

        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            if self._on_close:
                self._on_close()
        elif new_state == CircuitState.OPEN:
            self._half_open_calls = 0
            if self._on_open:
                self._on_open()
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._half_open_calls = 0

        if self._on_state_change:
            self._on_state_change(old_state, new_state)

    def _record_success(self, duration: float) -> None:
        """Record a successful call."""
        self._total_calls += 1
        self._success_count += 1

        self._call_records.append(
            CallRecord(
                success=True,
                duration=duration,
            )
        )

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)

    def _record_failure(self, duration: float, error: Optional[str] = None) -> None:
        """Record a failed call."""
        self._total_calls += 1
        self._failure_count += 1
        self._last_failure_time = time.time()

        self._call_records.append(
            CallRecord(
                success=False,
                duration=duration,
                error=error,
            )
        )

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately opens circuit
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            # Check if we should open the circuit
            if self._should_open():
                self._transition_to(CircuitState.OPEN)

    def _should_open(self) -> bool:
        """Check if circuit should open based on failure metrics."""
        # Check failure count threshold
        if self._failure_count >= self.config.failure_threshold:
            return True

        # Check failure rate in window
        if len(self._call_records) >= self.config.window_size:
            failures = sum(1 for r in self._call_records if not r.success)
            failure_rate = failures / len(self._call_records)
            if failure_rate >= self.config.failure_rate_threshold:
                return True

            # Check slow call rate
            slow_calls = sum(
                1
                for r in self._call_records
                if r.duration > self.config.slow_call_duration
            )
            slow_rate = slow_calls / len(self._call_records)
            if slow_rate >= self.config.slow_call_rate_threshold:
                return True

        return False

    def _can_execute(self) -> bool:
        """Check if a call can be executed."""
        current_state = self.state  # Triggers timeout check

        if current_state == CircuitState.CLOSED:
            return True

        if current_state == CircuitState.HALF_OPEN:
            return self._half_open_calls < self.config.half_open_max_calls

        return False

    def _get_remaining_time(self) -> float:
        """Get remaining time until circuit might close."""
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self.config.timeout - elapsed)

    def call(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of the function

        Raises:
            CircuitOpenError: If circuit is open
        """
        if not self._can_execute():
            self._rejected_calls += 1
            raise CircuitOpenError(self.name, self._get_remaining_time())

        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            self._record_success(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            if not self._is_excluded(e):
                self._record_failure(duration, str(e))
            raise

    async def call_async(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute an async function through the circuit breaker."""
        async with self._lock:
            if not self._can_execute():
                self._rejected_calls += 1
                raise CircuitOpenError(self.name, self._get_remaining_time())

        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            async with self._lock:
                self._record_success(duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            async with self._lock:
                if not self._is_excluded(e):
                    self._record_failure(duration, str(e))
            raise

    def _is_excluded(self, exception: Exception) -> bool:
        """Check if exception type is excluded from failure counting."""
        return type(exception) in self._excluded_exceptions

    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics."""
        failure_rate = 0.0
        slow_rate = 0.0

        if self._call_records:
            failures = sum(1 for r in self._call_records if not r.success)
            failure_rate = failures / len(self._call_records)

            slow = sum(
                1
                for r in self._call_records
                if r.duration > self.config.slow_call_duration
            )
            slow_rate = slow / len(self._call_records)

        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            total_calls=self._total_calls,
            rejected_calls=self._rejected_calls,
            last_failure_time=(
                datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc)
                if self._last_failure_time
                else None
            ),
            last_state_change=datetime.fromtimestamp(
                self._last_state_change,
                tz=timezone.utc,
            ),
            failure_rate=failure_rate,
            slow_call_rate=slow_rate,
        )

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None
        self._last_state_change = time.time()
        self._call_records.clear()

    def force_open(self) -> None:
        """Force the circuit to open state."""
        self._transition_to(CircuitState.OPEN)
        self._last_failure_time = time.time()

    def force_close(self) -> None:
        """Force the circuit to closed state."""
        self._transition_to(CircuitState.CLOSED)


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Example:
        registry = CircuitBreakerRegistry()

        # Get or create breakers
        api_breaker = registry.get("external_api")
        db_breaker = registry.get("database", failure_threshold=3)

        # Get stats for all breakers
        stats = registry.get_all_stats()
    """

    def __init__(
        self,
        default_config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._default_config = default_config or CircuitBreakerConfig()

    def get(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        **kwargs: Any,
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Circuit breaker name
            config: Optional configuration
            **kwargs: Additional kwargs passed to CircuitBreaker

        Returns:
            The circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name,
                config or self._default_config,
                **kwargs,
            )
        return self._breakers[name]

    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def remove(self, name: str) -> None:
        """Remove a circuit breaker."""
        self._breakers.pop(name, None)

    def list_names(self) -> List[str]:
        """List all circuit breaker names."""
        return list(self._breakers.keys())


def circuit_breaker(
    name: str,
    *,
    config: Optional[CircuitBreakerConfig] = None,
    registry: Optional[CircuitBreakerRegistry] = None,
    fallback: Optional[Callable[..., Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to wrap a function with circuit breaker protection.

    Args:
        name: Circuit breaker name
        config: Configuration options
        registry: Optional registry to use
        fallback: Optional fallback function to call when circuit is open

    Example:
        @circuit_breaker("external_api", fallback=get_cached_data)
        async def fetch_data():
            return await external_api.get_data()
    """

    def decorator(func: F) -> F:
        if registry:
            breaker = registry.get(name, config)
        else:
            breaker = CircuitBreaker(name, config)

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return await breaker.call_async(func, *args, **kwargs)
                except CircuitOpenError:
                    if fallback:
                        result = fallback(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            return await result
                        return result
                    raise

            return async_wrapper  # type: ignore
        else:

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return breaker.call(func, *args, **kwargs)
                except CircuitOpenError:
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise

            return sync_wrapper  # type: ignore

    return decorator


# Global registry
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry."""
    global _global_registry
    if _global_registry:
        _global_registry.reset_all()
    _global_registry = None


# Factory functions
def create_circuit_breaker(
    name: str,
    *,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    timeout: float = 30.0,
    **kwargs: Any,
) -> CircuitBreaker:
    """
    Create a circuit breaker with specified parameters.

    Args:
        name: Circuit breaker name
        failure_threshold: Failures before opening
        success_threshold: Successes to close from half-open
        timeout: Seconds before attempting recovery
        **kwargs: Additional parameters

    Returns:
        Configured CircuitBreaker
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        success_threshold=success_threshold,
        timeout=timeout,
        **{k: v for k, v in kwargs.items() if hasattr(CircuitBreakerConfig, k)},
    )
    return CircuitBreaker(
        name,
        config,
        **{k: v for k, v in kwargs.items() if not hasattr(CircuitBreakerConfig, k)},
    )


def create_registry(
    default_config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreakerRegistry:
    """Create a new circuit breaker registry."""
    return CircuitBreakerRegistry(default_config)
