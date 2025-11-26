"""
Prometheus metrics service for BeatSight API.

Ticket E6-002: Expose Application Metrics
- /metrics endpoint on all services
- HTTP request metrics (total, duration, in-flight)
- AI job queue metrics (depth, processing time)
- Custom business metrics
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.routing import Match

# =============================================================================
# Registry & Info
# =============================================================================

APP_INFO = Info(
    "beatsight",
    "BeatSight application information",
)

# =============================================================================
# HTTP Metrics
# =============================================================================

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "path"],
)

HTTP_REQUEST_SIZE_BYTES = Histogram(
    "http_request_size_bytes",
    "HTTP request body size in bytes",
    ["method", "path"],
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
)

HTTP_RESPONSE_SIZE_BYTES = Histogram(
    "http_response_size_bytes",
    "HTTP response body size in bytes",
    ["method", "path"],
    buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
)

# =============================================================================
# AI Job Metrics
# =============================================================================

AI_JOBS_QUEUE_DEPTH = Gauge(
    "ai_jobs_queue_depth",
    "Number of AI jobs waiting in queue",
    ["priority"],
)

AI_JOBS_PROCESSING = Gauge(
    "ai_jobs_processing",
    "Number of AI jobs currently being processed",
)

AI_JOBS_TOTAL = Counter(
    "ai_jobs_total",
    "Total AI jobs processed",
    ["status"],  # complete, failed, cancelled
)

AI_JOB_DURATION_SECONDS = Histogram(
    "ai_job_duration_seconds",
    "AI job processing duration in seconds",
    ["stage"],  # total, separation, transcription, beatmap
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600],
)

AI_JOB_ERRORS_TOTAL = Counter(
    "ai_job_errors_total",
    "Total AI job errors",
    ["error_type"],
)

AI_JOB_RETRIES_TOTAL = Counter(
    "ai_job_retries_total",
    "Total AI job retry attempts",
)

# =============================================================================
# Storage Metrics
# =============================================================================

STORAGE_OPERATIONS_TOTAL = Counter(
    "storage_operations_total",
    "Total storage operations",
    ["operation", "backend"],  # operation: upload, download; backend: local, s3, azure
)

STORAGE_OPERATION_DURATION_SECONDS = Histogram(
    "storage_operation_duration_seconds",
    "Storage operation duration in seconds",
    ["operation", "backend"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)

STORAGE_BYTES_TOTAL = Counter(
    "storage_bytes_total",
    "Total bytes transferred",
    ["direction", "backend"],  # direction: upload, download
)

# =============================================================================
# Quota Metrics
# =============================================================================

QUOTA_USAGE = Gauge(
    "quota_usage",
    "Current quota usage",
    ["user_id", "plan", "period"],  # period: daily, monthly
)

QUOTA_EXCEEDED_TOTAL = Counter(
    "quota_exceeded_total",
    "Total times quota was exceeded",
    ["plan"],
)

# =============================================================================
# Notification Metrics
# =============================================================================

NOTIFICATIONS_SENT_TOTAL = Counter(
    "notifications_sent_total",
    "Total notifications sent",
    ["type", "status"],  # type: email, webpush; status: success, failed
)

NOTIFICATION_RATE_LIMITED_TOTAL = Counter(
    "notification_rate_limited_total",
    "Total notifications blocked by rate limiter",
    ["type"],
)

# =============================================================================
# Database Metrics
# =============================================================================

DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],  # select, insert, update, delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# =============================================================================
# Redis Metrics
# =============================================================================

REDIS_OPERATIONS_TOTAL = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation"],
)

REDIS_OPERATION_DURATION_SECONDS = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation duration in seconds",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
)

# =============================================================================
# Metrics Middleware
# =============================================================================


def _get_path_template(request: Request) -> str:
    """
    Get the path template (with path parameters) for a request.
    This normalizes paths like /jobs/123 to /jobs/{job_id}.
    """
    # Try to match against app routes to get path template
    app = request.app
    for route in app.routes:
        match, scope = route.matches(request.scope)
        if match == Match.FULL:
            return getattr(route, "path", request.url.path)
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware to collect HTTP metrics for Prometheus.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _get_path_template(request)

        # Track in-progress requests
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()

        # Track request size
        content_length = request.headers.get("content-length")
        if content_length:
            HTTP_REQUEST_SIZE_BYTES.labels(method=method, path=path).observe(
                int(content_length)
            )

        # Time the request
        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start_time

            # Record metrics
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(
                duration
            )
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()

        # Track response size
        response_size = response.headers.get("content-length")
        if response_size:
            HTTP_RESPONSE_SIZE_BYTES.labels(method=method, path=path).observe(
                int(response_size)
            )

        return response


# =============================================================================
# Metrics Route
# =============================================================================


async def metrics_endpoint() -> Response:
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus exposition format.
    """
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


def setup_metrics(app: FastAPI) -> None:
    """
    Set up Prometheus metrics for a FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Set app info
    APP_INFO.info(
        {
            "version": "0.1.0",
            "service": "beatsight-api",
        }
    )

    # Add middleware
    app.add_middleware(PrometheusMiddleware)

    # Add metrics endpoint
    app.add_api_route(
        "/metrics",
        metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
        tags=["monitoring"],
    )


# =============================================================================
# Context Managers for Manual Instrumentation
# =============================================================================


@contextmanager
def track_ai_job_stage(stage: str) -> Generator[None, None, None]:
    """
    Context manager to track AI job stage duration.

    Args:
        stage: Name of the processing stage

    Example:
        with track_ai_job_stage("separation"):
            await run_separation()
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        AI_JOB_DURATION_SECONDS.labels(stage=stage).observe(duration)


@contextmanager
def track_storage_operation(
    operation: str, backend: str
) -> Generator[None, None, None]:
    """
    Context manager to track storage operation duration.

    Args:
        operation: Type of operation (upload, download, delete)
        backend: Storage backend (local, s3, azure)
    """
    start_time = time.perf_counter()
    try:
        yield
        STORAGE_OPERATIONS_TOTAL.labels(operation=operation, backend=backend).inc()
    finally:
        duration = time.perf_counter() - start_time
        STORAGE_OPERATION_DURATION_SECONDS.labels(
            operation=operation, backend=backend
        ).observe(duration)


@contextmanager
def track_db_query(operation: str) -> Generator[None, None, None]:
    """
    Context manager to track database query duration.

    Args:
        operation: Type of operation (select, insert, update, delete)
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        DB_QUERY_DURATION_SECONDS.labels(operation=operation).observe(duration)


# =============================================================================
# Helper Functions
# =============================================================================


def record_ai_job_complete(status: str) -> None:
    """Record an AI job completion."""
    AI_JOBS_TOTAL.labels(status=status).inc()


def record_ai_job_error(error_type: str) -> None:
    """Record an AI job error."""
    AI_JOB_ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_ai_job_retry() -> None:
    """Record an AI job retry."""
    AI_JOB_RETRIES_TOTAL.inc()


def update_queue_depth(standard: int, priority: int) -> None:
    """Update AI job queue depth gauges."""
    AI_JOBS_QUEUE_DEPTH.labels(priority="standard").set(standard)
    AI_JOBS_QUEUE_DEPTH.labels(priority="priority").set(priority)


def update_processing_count(count: int) -> None:
    """Update AI jobs processing count."""
    AI_JOBS_PROCESSING.set(count)


def record_storage_bytes(direction: str, backend: str, bytes_count: int) -> None:
    """Record bytes transferred to/from storage."""
    STORAGE_BYTES_TOTAL.labels(direction=direction, backend=backend).inc(bytes_count)


def record_notification_sent(notification_type: str, success: bool) -> None:
    """Record a notification send attempt."""
    status = "success" if success else "failed"
    NOTIFICATIONS_SENT_TOTAL.labels(type=notification_type, status=status).inc()


def record_notification_rate_limited(notification_type: str) -> None:
    """Record a rate-limited notification."""
    NOTIFICATION_RATE_LIMITED_TOTAL.labels(type=notification_type).inc()


def record_quota_exceeded(plan: str) -> None:
    """Record a quota exceeded event."""
    QUOTA_EXCEEDED_TOTAL.labels(plan=plan).inc()


def update_db_connections(count: int) -> None:
    """Update active database connection count."""
    DB_CONNECTIONS_ACTIVE.set(count)


def record_redis_operation(operation: str, duration: float) -> None:
    """Record a Redis operation."""
    REDIS_OPERATIONS_TOTAL.labels(operation=operation).inc()
    REDIS_OPERATION_DURATION_SECONDS.observe(duration)
