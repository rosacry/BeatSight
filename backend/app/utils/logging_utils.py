"""
Logging utilities for structured logging and context management.

Provides utilities for:
- Structured logger configuration
- Logging context managers
- Request/response logging
- Performance logging
- Log filtering and formatting
"""

import asyncio
import functools
import time
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Generator, TypeVar

import structlog
from structlog.types import Processor

# Context variables for logging
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class LogConfig:
    """Configuration for logging setup."""

    level: str = "INFO"
    format: str = "json"  # json, console, or key_value
    timestamp_format: str = "iso"
    add_timestamp: bool = True
    add_level: bool = True
    add_logger_name: bool = True
    add_thread_name: bool = False
    add_process_name: bool = False
    exception_formatter: str = "plain"  # plain or rich

    # Fields to redact from logs
    redact_fields: list[str] = field(
        default_factory=lambda: [
            "password",
            "token",
            "secret",
            "api_key",
            "authorization",
            "credit_card",
            "ssn",
            "private_key",
        ]
    )

    # Fields to include in all logs
    default_context: dict[str, Any] = field(default_factory=dict)


def configure_logging(config: LogConfig | None = None) -> None:
    """
    Configure structlog with standard processors.

    Args:
        config: Logging configuration
    """
    if config is None:
        config = LogConfig()

    # Build processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_context_vars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
    ]

    if config.add_timestamp:
        processors.append(structlog.processors.TimeStamper(fmt=config.timestamp_format))

    if config.redact_fields:
        processors.append(create_redactor(config.redact_fields))

    processors.append(structlog.processors.format_exc_info)

    # Add formatter based on config
    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    elif config.format == "console":
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.KeyValueRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib, config.level.upper(), structlog.stdlib.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def add_context_vars(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Processor to add context variables to log events."""
    request_id = request_id_var.get()
    user_id = user_id_var.get()
    trace_id = trace_id_var.get()

    if request_id:
        event_dict["request_id"] = request_id
    if user_id:
        event_dict["user_id"] = user_id
    if trace_id:
        event_dict["trace_id"] = trace_id

    return event_dict


def create_redactor(fields: list[str]) -> Processor:
    """
    Create a processor that redacts sensitive fields.

    Args:
        fields: List of field names to redact

    Returns:
        Structlog processor
    """
    fields_lower = {f.lower() for f in fields}

    def redactor(
        logger: Any,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        for key in event_dict:
            if key.lower() in fields_lower:
                event_dict[key] = "[REDACTED]"
        return event_dict

    return redactor


# =============================================================================
# Logger Factory
# =============================================================================


def get_logger(
    name: str | None = None, **initial_context: Any
) -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (module name if not provided)
        **initial_context: Initial context to bind

    Returns:
        Configured logger

    Example:
        >>> logger = get_logger(__name__, service="api")
        >>> logger.info("Request received", path="/users")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class LoggerAdapter:
    """
    Adapter that adds consistent context to all log calls.

    Example:
        >>> logger = LoggerAdapter(get_logger(), service="api", version="1.0")
        >>> logger.info("Started")  # Includes service and version
    """

    def __init__(
        self,
        logger: structlog.BoundLogger,
        **context: Any,
    ) -> None:
        """Initialize with base logger and context."""
        self._logger = logger.bind(**context)

    def bind(self, **context: Any) -> "LoggerAdapter":
        """Create new adapter with additional context."""
        return LoggerAdapter(self._logger.bind(**context))

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(event, **kwargs)

    def critical(self, event: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._logger.critical(event, **kwargs)


# =============================================================================
# Context Managers
# =============================================================================


@contextmanager
def log_context(**context: Any) -> Generator[None, None, None]:
    """
    Context manager to add temporary logging context.

    Args:
        **context: Context to add

    Example:
        >>> logger = get_logger()
        >>> with log_context(request_id="abc123"):
        ...     logger.info("Processing")  # Includes request_id
    """
    tokens = []
    try:
        for key, value in context.items():
            token = structlog.contextvars.bind_contextvars(**{key: value})
            tokens.append(token)
        yield
    finally:
        for token in tokens:
            structlog.contextvars.unbind_contextvars(token)


@contextmanager
def request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    trace_id: str | None = None,
) -> Generator[None, None, None]:
    """
    Context manager for request-scoped logging.

    Args:
        request_id: Request identifier
        user_id: User identifier
        trace_id: Distributed trace identifier

    Example:
        >>> with request_context(request_id="req-123"):
        ...     logger.info("Handling request")
    """
    tokens = []

    if request_id:
        tokens.append(request_id_var.set(request_id))
    if user_id:
        tokens.append(user_id_var.set(user_id))
    if trace_id:
        tokens.append(trace_id_var.set(trace_id))

    try:
        yield
    finally:
        for token in tokens:
            # Reset context variables
            if token:
                pass  # ContextVar.reset is not available in all versions


@contextmanager
def timed_log(
    logger: structlog.BoundLogger,
    event: str,
    level: str = "info",
    **context: Any,
) -> Generator[dict[str, Any], None, None]:
    """
    Context manager that logs duration on exit.

    Args:
        logger: Logger instance
        event: Event name
        level: Log level
        **context: Additional context

    Yields:
        Dict to add extra context

    Example:
        >>> logger = get_logger()
        >>> with timed_log(logger, "database_query", table="users") as ctx:
        ...     # Do work
        ...     ctx["rows"] = 100
        # Logs: database_query with duration_ms and rows
    """
    extra_context: dict[str, Any] = {}
    start = time.perf_counter()

    try:
        yield extra_context
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_fn = getattr(logger, level)
        log_fn(
            event,
            duration_ms=round(duration_ms, 2),
            **context,
            **extra_context,
        )


@asynccontextmanager
async def async_timed_log(
    logger: structlog.BoundLogger,
    event: str,
    level: str = "info",
    **context: Any,
):
    """
    Async context manager that logs duration on exit.

    Args:
        logger: Logger instance
        event: Event name
        level: Log level
        **context: Additional context

    Yields:
        Dict to add extra context
    """
    extra_context: dict[str, Any] = {}
    start = time.perf_counter()

    try:
        yield extra_context
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_fn = getattr(logger, level)
        log_fn(
            event,
            duration_ms=round(duration_ms, 2),
            **context,
            **extra_context,
        )


# =============================================================================
# Decorators
# =============================================================================


F = TypeVar("F", bound=Callable[..., Any])


def log_call(
    logger: structlog.BoundLogger | None = None,
    level: str = "debug",
    log_args: bool = True,
    log_result: bool = False,
    log_exceptions: bool = True,
) -> Callable[[F], F]:
    """
    Decorator to log function calls.

    Args:
        logger: Logger to use (creates one if not provided)
        level: Log level for calls
        log_args: Whether to log arguments
        log_result: Whether to log return value
        log_exceptions: Whether to log exceptions

    Returns:
        Decorator function

    Example:
        >>> @log_call()
        ... def process_item(item_id: int) -> dict:
        ...     return {"id": item_id}
    """

    def decorator(func: F) -> F:
        _logger = logger or get_logger(func.__module__)
        log_fn = getattr(_logger, level)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_context: dict[str, Any] = {"function": func.__name__}

            if log_args:
                call_context["args"] = args
                call_context["kwargs"] = kwargs

            log_fn(f"calling_{func.__name__}", **call_context)

            try:
                result = func(*args, **kwargs)

                if log_result:
                    log_fn(f"returned_{func.__name__}", result=result)

                return result

            except Exception as e:
                if log_exceptions:
                    _logger.exception(
                        f"exception_in_{func.__name__}",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            call_context: dict[str, Any] = {"function": func.__name__}

            if log_args:
                call_context["args"] = args
                call_context["kwargs"] = kwargs

            log_fn(f"calling_{func.__name__}", **call_context)

            try:
                result = await func(*args, **kwargs)

                if log_result:
                    log_fn(f"returned_{func.__name__}", result=result)

                return result

            except Exception as e:
                if log_exceptions:
                    _logger.exception(
                        f"exception_in_{func.__name__}",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def log_execution_time(
    logger: structlog.BoundLogger | None = None,
    level: str = "info",
    threshold_ms: float | None = None,
) -> Callable[[F], F]:
    """
    Decorator to log function execution time.

    Args:
        logger: Logger to use
        level: Log level
        threshold_ms: Only log if duration exceeds threshold

    Returns:
        Decorator function

    Example:
        >>> @log_execution_time(threshold_ms=100)
        ... def slow_function():
        ...     time.sleep(0.2)
    """

    def decorator(func: F) -> F:
        _logger = logger or get_logger(func.__module__)
        log_fn = getattr(_logger, level)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                if threshold_ms is None or duration_ms >= threshold_ms:
                    log_fn(
                        f"execution_time_{func.__name__}",
                        duration_ms=round(duration_ms, 2),
                    )

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                if threshold_ms is None or duration_ms >= threshold_ms:
                    log_fn(
                        f"execution_time_{func.__name__}",
                        duration_ms=round(duration_ms, 2),
                    )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# =============================================================================
# Log Level Utilities
# =============================================================================


def should_log(level: str, min_level: str = "DEBUG") -> bool:
    """
    Check if a log level should be logged.

    Args:
        level: Level to check
        min_level: Minimum level to log

    Returns:
        True if level should be logged
    """
    levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }

    return levels.get(level.upper(), 0) >= levels.get(min_level.upper(), 0)


def level_to_int(level: str) -> int:
    """
    Convert log level string to integer.

    Args:
        level: Level string

    Returns:
        Integer level value
    """
    levels = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "WARN": 30,
        "ERROR": 40,
        "CRITICAL": 50,
        "FATAL": 50,
    }
    return levels.get(level.upper(), 0)


# =============================================================================
# Formatters
# =============================================================================


def format_exception(exc: BaseException) -> dict[str, Any]:
    """
    Format exception for logging.

    Args:
        exc: Exception to format

    Returns:
        Dictionary with exception details
    """
    import traceback

    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


def format_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **extra: Any,
) -> dict[str, Any]:
    """
    Format HTTP request for logging.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context

    Returns:
        Dictionary with request details
    """
    return {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        **extra,
    }


def format_sql_query(
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
    duration_ms: float | None = None,
) -> dict[str, Any]:
    """
    Format SQL query for logging.

    Args:
        query: SQL query string
        params: Query parameters
        duration_ms: Query duration

    Returns:
        Dictionary with query details
    """
    result: dict[str, Any] = {
        "query": query[:500],  # Truncate long queries
    }

    if params:
        result["params"] = str(params)[:200]

    if duration_ms is not None:
        result["duration_ms"] = round(duration_ms, 2)

    return result


# =============================================================================
# Log Sampling
# =============================================================================


class SamplingLogger:
    """
    Logger that samples log messages at a configurable rate.

    Example:
        >>> sampler = SamplingLogger(get_logger(), sample_rate=0.1)
        >>> sampler.info("High volume event")  # Only logs 10% of calls
    """

    def __init__(
        self,
        logger: structlog.BoundLogger,
        sample_rate: float = 1.0,
        always_log_errors: bool = True,
    ) -> None:
        """
        Initialize sampling logger.

        Args:
            logger: Base logger
            sample_rate: Fraction of logs to emit (0.0 to 1.0)
            always_log_errors: Whether to always log errors regardless of sampling
        """
        self._logger = logger
        self._sample_rate = sample_rate
        self._always_log_errors = always_log_errors
        self._counter = 0

    def _should_log(self, is_error: bool = False) -> bool:
        """Check if this log should be emitted."""
        if is_error and self._always_log_errors:
            return True

        if self._sample_rate >= 1.0:
            return True

        if self._sample_rate <= 0.0:
            return False

        import random

        return random.random() < self._sample_rate

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log debug message (sampled)."""
        if self._should_log():
            self._logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log info message (sampled)."""
        if self._should_log():
            self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log warning message (sampled)."""
        if self._should_log():
            self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log error message."""
        if self._should_log(is_error=True):
            self._logger.error(event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        """Log exception."""
        if self._should_log(is_error=True):
            self._logger.exception(event, **kwargs)


class RateLimitedLogger:
    """
    Logger that rate limits repeated messages.

    Example:
        >>> logger = RateLimitedLogger(get_logger(), max_per_minute=10)
        >>> for i in range(100):
        ...     logger.warning("rate_limited_event")  # Only logs first 10 per minute
    """

    def __init__(
        self,
        logger: structlog.BoundLogger,
        max_per_minute: int = 60,
    ) -> None:
        """
        Initialize rate limited logger.

        Args:
            logger: Base logger
            max_per_minute: Maximum logs per event per minute
        """
        self._logger = logger
        self._max_per_minute = max_per_minute
        self._counts: dict[str, list[float]] = {}

    def _should_log(self, event: str) -> bool:
        """Check if event should be logged."""
        now = time.time()
        minute_ago = now - 60

        if event not in self._counts:
            self._counts[event] = []

        # Remove old entries
        self._counts[event] = [t for t in self._counts[event] if t > minute_ago]

        if len(self._counts[event]) < self._max_per_minute:
            self._counts[event].append(now)
            return True

        return False

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log debug message (rate limited)."""
        if self._should_log(event):
            self._logger.debug(event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        """Log info message (rate limited)."""
        if self._should_log(event):
            self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log warning message (rate limited)."""
        if self._should_log(event):
            self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """Log error message (rate limited)."""
        if self._should_log(event):
            self._logger.error(event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        """Log exception (rate limited)."""
        if self._should_log(event):
            self._logger.exception(event, **kwargs)


# =============================================================================
# Audit Logging
# =============================================================================


@dataclass
class AuditEvent:
    """Structured audit event."""

    action: str
    actor_id: str
    actor_type: str = "user"
    resource_type: str = ""
    resource_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ip_address: str = ""
    user_agent: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "audit": True,
            "action": self.action,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


class AuditLogger:
    """
    Specialized logger for audit events.

    Example:
        >>> audit = AuditLogger(get_logger("audit"))
        >>> audit.log_action("user.login", actor_id="user-123", ip_address="1.2.3.4")
    """

    def __init__(self, logger: structlog.BoundLogger) -> None:
        """Initialize audit logger."""
        self._logger = logger

    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: Audit event to log
        """
        self._logger.info("audit_event", **event.to_dict())

    def log_action(
        self,
        action: str,
        *,
        actor_id: str,
        actor_type: str = "user",
        resource_type: str = "",
        resource_id: str = "",
        details: dict[str, Any] | None = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> None:
        """
        Log an audit action.

        Args:
            action: Action name (e.g., "user.login", "document.delete")
            actor_id: ID of the actor performing the action
            actor_type: Type of actor
            resource_type: Type of resource being acted upon
            resource_id: ID of the resource
            details: Additional details
            ip_address: Client IP address
            user_agent: Client user agent
        """
        event = AuditEvent(
            action=action,
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.log_event(event)
