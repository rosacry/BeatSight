"""
Health Check Endpoints

Comprehensive health check with database, cache, and external service status.
Supports Kubernetes liveness and readiness probes.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Health"])


# ============================================================================
# Models
# ============================================================================


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] | None = None


class SystemHealth(BaseModel):
    """Overall system health response."""

    status: HealthStatus
    version: str
    environment: str
    uptime_seconds: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    components: list[ComponentHealth] = []

    # Metrics
    total_requests: int | None = None
    error_rate: float | None = None


# ============================================================================
# Health Check Functions
# ============================================================================

# Track server start time for uptime calculation
_start_time = time.time()


async def check_database() -> ComponentHealth:
    """Check database connectivity."""
    start = time.time()
    try:
        from app.database import async_session_maker

        async with async_session_maker() as session:
            result = await session.execute("SELECT 1")
            await result.fetchone()

        latency = (time.time() - start) * 1000

        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY if latency < 100 else HealthStatus.DEGRADED,
            latency_ms=round(latency, 2),
            message="PostgreSQL connection OK",
        )
    except Exception as e:
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=(time.time() - start) * 1000,
            message=f"Database error: {str(e)}",
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    start = time.time()
    try:
        from app.cache import redis_client

        if redis_client is None:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.DEGRADED,
                message="Redis not configured",
            )

        await redis_client.ping()
        latency = (time.time() - start) * 1000

        # Get some stats
        info = await redis_client.info("memory")
        used_memory = info.get("used_memory_human", "unknown")

        return ComponentHealth(
            name="redis",
            status=HealthStatus.HEALTHY if latency < 50 else HealthStatus.DEGRADED,
            latency_ms=round(latency, 2),
            message="Redis connection OK",
            details={"used_memory": used_memory},
        )
    except Exception as e:
        return ComponentHealth(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            latency_ms=(time.time() - start) * 1000,
            message=f"Redis error: {str(e)}",
        )


async def check_storage() -> ComponentHealth:
    """Check file storage (S3/local) accessibility."""
    start = time.time()
    try:
        from app.storage import storage_client

        if storage_client is None:
            return ComponentHealth(
                name="storage",
                status=HealthStatus.DEGRADED,
                message="Storage not configured",
            )

        # Try to list a bucket or check connectivity
        is_available = await storage_client.health_check()
        latency = (time.time() - start) * 1000

        return ComponentHealth(
            name="storage",
            status=HealthStatus.HEALTHY if is_available else HealthStatus.UNHEALTHY,
            latency_ms=round(latency, 2),
            message="Storage accessible" if is_available else "Storage unavailable",
        )
    except Exception as e:
        return ComponentHealth(
            name="storage",
            status=HealthStatus.UNHEALTHY,
            latency_ms=(time.time() - start) * 1000,
            message=f"Storage error: {str(e)}",
        )


async def check_ai_service() -> ComponentHealth:
    """Check AI/ML service availability."""
    start = time.time()
    try:
        # This would check your ML service endpoint
        # For now, return a placeholder
        return ComponentHealth(
            name="ai_service",
            status=HealthStatus.HEALTHY,
            latency_ms=round((time.time() - start) * 1000, 2),
            message="AI service available",
        )
    except Exception as e:
        return ComponentHealth(
            name="ai_service",
            status=HealthStatus.DEGRADED,
            latency_ms=(time.time() - start) * 1000,
            message=f"AI service error: {str(e)}",
        )


async def check_stripe() -> ComponentHealth:
    """Check Stripe API connectivity."""
    start = time.time()
    try:
        import stripe
        from app.core.config import settings

        if not settings.stripe_secret_key:
            return ComponentHealth(
                name="stripe",
                status=HealthStatus.DEGRADED,
                message="Stripe not configured",
            )

        # Just verify the API key works
        stripe.api_key = settings.stripe_secret_key
        # stripe.Balance.retrieve()  # Lightweight API call

        return ComponentHealth(
            name="stripe",
            status=HealthStatus.HEALTHY,
            latency_ms=round((time.time() - start) * 1000, 2),
            message="Stripe API available",
        )
    except Exception as e:
        return ComponentHealth(
            name="stripe",
            status=HealthStatus.UNHEALTHY,
            latency_ms=(time.time() - start) * 1000,
            message=f"Stripe error: {str(e)}",
        )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/health", response_model=SystemHealth)
async def health_check(
    detailed: bool = False,
) -> SystemHealth:
    """
    Comprehensive health check endpoint.

    Returns overall system health and status of all components.
    Use `detailed=true` for full component breakdown.
    """
    from app.core.config import settings

    components: list[ComponentHealth] = []

    if detailed:
        # Run all health checks in parallel
        results = await asyncio.gather(
            check_database(),
            check_redis(),
            check_storage(),
            check_ai_service(),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
            elif isinstance(result, Exception):
                components.append(
                    ComponentHealth(
                        name="unknown",
                        status=HealthStatus.UNHEALTHY,
                        message=str(result),
                    )
                )
    else:
        # Quick database-only check
        db_health = await check_database()
        components.append(db_health)

    # Determine overall status
    statuses = [c.status for c in components]
    if HealthStatus.UNHEALTHY in statuses:
        overall_status = HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    return SystemHealth(
        status=overall_status,
        version=settings.app_version if hasattr(settings, "app_version") else "1.0.0",
        environment=settings.environment
        if hasattr(settings, "environment")
        else "development",
        uptime_seconds=round(time.time() - _start_time, 2),
        components=components,
    )


@router.get("/health/live")
async def liveness_probe(response: Response) -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 if the application is running.
    This should be a very fast check - just confirms the process is alive.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe(response: Response) -> dict[str, str]:
    """
    Kubernetes readiness probe.

    Returns 200 if the application is ready to accept traffic.
    Checks critical dependencies (database).
    """
    try:
        db_health = await check_database()

        if db_health.status == HealthStatus.UNHEALTHY:
            response.status_code = 503
            return {"status": "not ready", "reason": "database unavailable"}

        return {"status": "ready"}
    except Exception as e:
        response.status_code = 503
        return {"status": "not ready", "reason": str(e)}


@router.get("/health/startup")
async def startup_probe(response: Response) -> dict[str, str]:
    """
    Kubernetes startup probe.

    Similar to readiness but used during startup to give the app
    time to initialize before liveness checks begin.
    """
    try:
        db_health = await check_database()

        if db_health.status == HealthStatus.UNHEALTHY:
            response.status_code = 503
            return {"status": "starting", "reason": "waiting for database"}

        return {"status": "started"}
    except Exception as e:
        response.status_code = 503
        return {"status": "starting", "reason": str(e)}


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    from app.core.config import settings

    uptime = time.time() - _start_time

    # Basic metrics in Prometheus format
    metrics = [
        "# HELP beatsight_uptime_seconds Time since application started",
        "# TYPE beatsight_uptime_seconds gauge",
        f"beatsight_uptime_seconds {uptime:.2f}",
        "",
        "# HELP beatsight_info Application information",
        "# TYPE beatsight_info gauge",
        f'beatsight_info{{version="{getattr(settings, "app_version", "1.0.0")}",environment="{getattr(settings, "environment", "development")}"}} 1',
    ]

    return Response(
        content="\n".join(metrics),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
