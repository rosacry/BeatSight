"""
Request ID Middleware for request tracing and debugging.

Attaches a unique request ID to each incoming request, making it available
throughout the request lifecycle for logging and error tracking.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable for request ID - accessible throughout the request lifecycle
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Header names
REQUEST_ID_HEADER = "X-Request-ID"

# UUID pattern for validation (prevents log injection attacks)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def get_request_id() -> str | None:
    """Get the current request ID from context.

    Returns:
        The request ID for the current request, or None if not in a request context.
    """
    return request_id_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that attaches a unique request ID to each request.

    Features:
    - Generates a new UUID for each request if not provided
    - Accepts client-provided request ID via X-Request-ID header (UUID format only)
    - Makes request ID available via context variable for logging
    - Returns request ID in response header for client correlation

    Security:
    - Only accepts UUID-formatted request IDs to prevent log injection attacks
    - Invalid or malformed request IDs are ignored and replaced with new UUIDs

    Usage in logging:
        from app.middleware.request_id import get_request_id

        logger.info("processing_request", request_id=get_request_id())

    Client usage:
        # Client can provide their own request ID (must be UUID format)
        curl -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" /api/...

        # Response will include the same ID
        # X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with request ID tracking."""

        # Use client-provided request ID or generate new one
        # SECURITY: Only accept UUID format to prevent log injection attacks
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id or not UUID_PATTERN.match(request_id):
            request_id = str(uuid.uuid4())

        # Store in context for access throughout request lifecycle
        token = request_id_var.set(request_id)

        # Attach to request state for handler access
        request.state.request_id = request_id

        try:
            response = await call_next(request)

            # Add request ID to response headers
            response.headers[REQUEST_ID_HEADER] = request_id

            return response
        finally:
            # Reset context variable
            request_id_var.reset(token)
