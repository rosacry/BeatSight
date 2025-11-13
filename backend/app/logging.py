"""Logging configuration utilities."""

from __future__ import annotations

import logging
from typing import Any

import structlog

from .config import get_settings


def configure_logging() -> None:
    """Configure structlog and standard logging."""

    settings = get_settings()
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.logging_json:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.upper()),
            cache_logger_on_first_use=True,
        )
    else:
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.upper()),
            cache_logger_on_first_use=True,
        )

    logging.basicConfig(level=settings.log_level.upper(), format="%(message)s")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""

    return structlog.get_logger(name)
