"""
Health check endpoints for Kubernetes probes and service monitoring.

Provides:
- /health/live: Kubernetes liveness probe
- /health/ready: Kubernetes readiness probe
- /health/detailed: Detailed component health check
"""

from __future__ import annotations

import time
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.redis import get_redis

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(str, Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: HealthStatus
    message: str | None = None
    latency_ms: float | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus
    service: str = "beatsight-api"
    version: str = "0.1.0"
    timestamp: datetime
    components: dict[str, ComponentHealth] | None = None


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    service: str = "beatsight-api"
    timestamp: datetime
    checks: dict[str, bool] | None = None


async def check_database(db: AsyncSession) -> ComponentHealth:
    """Check database connectivity."""
    start = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Connected",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.UNHEALTHY,
            message=f"Connection failed: {str(e)[:100]}",
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity."""
    start = time.perf_counter()
    try:
        redis = await get_redis()
        if redis is None:
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message="Redis not configured",
            )
        await redis.ping()
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Connected",
            latency_ms=round(latency, 2),
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.DEGRADED,
            message=f"Connection failed: {str(e)[:100]}",
        )


def aggregate_status(components: dict[str, ComponentHealth]) -> HealthStatus:
    """Aggregate component statuses into overall status."""
    statuses = [c.status for c in components.values()]

    if all(s == HealthStatus.HEALTHY for s in statuses):
        return HealthStatus.HEALTHY
    elif any(s == HealthStatus.UNHEALTHY for s in statuses):
        return HealthStatus.UNHEALTHY
    else:
        return HealthStatus.DEGRADED


@router.get("/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 OK if the service is running.
    This is a fast check that doesn't verify dependencies.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready"},
    },
)
async def ready(
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Kubernetes readiness probe.

    Returns 200 OK if the service is ready to handle requests.
    Checks database connectivity as the minimum requirement.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available",
        )

    return {"status": "ready"}


@router.get(
    "/detailed",
    response_model=HealthResponse,
    summary="Detailed health check",
    description="Returns detailed health status of all components.",
)
async def detailed_health_check(
    db: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """
    Detailed health check.

    Returns health status of all components including latency information.
    Useful for debugging and monitoring dashboards.
    """
    db_health = await check_database(db)
    redis_health = await check_redis()

    components = {
        "database": db_health,
        "redis": redis_health,
    }

    return HealthResponse(
        status=aggregate_status(components),
        timestamp=datetime.utcnow(),
        components=components,
    )


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Basic health check",
)
async def health_check() -> HealthResponse:
    """
    Basic health check without dependency verification.

    Returns service health status quickly.
    Use /health/detailed for full component checks.
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        timestamp=datetime.utcnow(),
    )
