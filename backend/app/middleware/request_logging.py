"""Request logging middleware for API observability.

Logs all incoming requests with timing, status codes, and context
for debugging and monitoring purposes.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests with timing and status information.

    Logs:
    - Request path, method, and query params
    - Response status code
    - Request duration in milliseconds
    - Client IP (X-Forwarded-For aware)
    - User agent
    - Request ID (if available)

    Excludes health check endpoints from logging to reduce noise.
    """

    # Paths to exclude from logging (health checks, metrics)
    EXCLUDED_PATHS = {
        "/health",
        "/health/",
        "/health/live",
        "/health/ready",
        "/metrics",
    }

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Log request and response details."""
        # Skip excluded paths
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Start timing
        start_time = time.perf_counter()

        # Extract client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")[:100]

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Get request ID if available
        request_id = getattr(request.state, "request_id", None)

        # Log based on status code
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
            "user_agent": user_agent,
        }

        if request_id:
            log_data["request_id"] = request_id

        if request.query_params:
            # Redact sensitive query params
            log_data["query_params"] = self._redact_params(dict(request.query_params))

        # Log level based on status code
        if response.status_code >= 500:
            logger.error("http_request_error", **log_data)
        elif response.status_code >= 400:
            logger.warning("http_request_client_error", **log_data)
        elif duration_ms > 5000:  # Slow request warning
            logger.warning("http_request_slow", **log_data)
        else:
            logger.info("http_request", **log_data)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, handling proxies."""
        # Check X-Forwarded-For header (set by load balancers/proxies)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take the first IP in the chain (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _redact_params(self, params: dict) -> dict:
        """Redact sensitive query parameters."""
        sensitive_keys = {"token", "password", "secret", "key", "api_key", "auth"}
        return {
            k: "[REDACTED]" if k.lower() in sensitive_keys else v
            for k, v in params.items()
        }
