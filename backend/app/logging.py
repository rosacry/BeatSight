"""Logging configuration utilities."""

from __future__ import annotations

import logging

import structlog

from .config import get_settings


def add_request_id(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Add request ID to log entries if available.

    This processor automatically includes the current request ID in all log
    entries when called within a request context.
    """
    try:
        from app.middleware.request_id import get_request_id

        request_id = get_request_id()
        if request_id:
            event_dict["request_id"] = request_id
    except ImportError:
        # Middleware not available (e.g., during tests)
        pass

    return event_dict


def configure_logging() -> None:
    """Configure structlog and standard logging."""

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        add_request_id,  # Automatically add request ID to all logs
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.logging_json:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            cache_logger_on_first_use=True,
        )
    else:
        # Don't include format_exc_info with ConsoleRenderer as it handles exceptions
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            cache_logger_on_first_use=True,
        )

    logging.basicConfig(level=log_level, format="%(message)s")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""

    return structlog.get_logger(name)
