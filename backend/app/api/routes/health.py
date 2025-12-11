"""
Health check endpoints for Kubernetes probes and service monitoring.

Provides:
- /health/live: Kubernetes liveness probe
- /health/ready: Kubernetes readiness probe
- /health/detailed: Detailed component health check
"""

from __future__ import annotations

import os
import platform
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session
from app.db.redis import get_redis
from app.services.stripe_service import get_stripe_service

router = APIRouter(prefix="/health", tags=["health"])

# Track service start time
_service_start_time = datetime.now(timezone.utc)


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


class SystemInfo(BaseModel):
    """System information for health reporting."""

    python_version: str
    platform: str
    pid: int
    uptime_seconds: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus
    service: str = "beatsight-api"
    version: str
    environment: str
    timestamp: datetime
    uptime_seconds: float | None = None
    components: dict[str, ComponentHealth] | None = None
    system: SystemInfo | None = None


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool
    service: str = "beatsight-api"
    timestamp: datetime
    checks: dict[str, bool] | None = None


def get_system_info() -> SystemInfo:
    """Get system information."""
    uptime = (datetime.now(timezone.utc) - _service_start_time).total_seconds()
    return SystemInfo(
        python_version=platform.python_version(),
        platform=platform.system(),
        pid=os.getpid(),
        uptime_seconds=round(uptime, 2),
    )


def get_uptime_seconds() -> float:
    """Get service uptime in seconds."""
    return (datetime.now(timezone.utc) - _service_start_time).total_seconds()


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


def check_stripe() -> ComponentHealth:
    """Check Stripe configuration status."""
    try:
        stripe_service = get_stripe_service()
        if not stripe_service.is_configured():
            return ComponentHealth(
                status=HealthStatus.DEGRADED,
                message="Stripe not configured (payments disabled)",
            )
        return ComponentHealth(
            status=HealthStatus.HEALTHY,
            message="Configured",
        )
    except Exception as e:
        return ComponentHealth(
            status=HealthStatus.DEGRADED,
            message=f"Configuration error: {str(e)[:100]}",
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
    settings = get_settings()
    db_health = await check_database(db)
    redis_health = await check_redis()
    stripe_health = check_stripe()

    components = {
        "database": db_health,
        "redis": redis_health,
        "stripe": stripe_health,
    }

    return HealthResponse(
        status=aggregate_status(components),
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(get_uptime_seconds(), 2),
        components=components,
        system=get_system_info(),
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
    settings = get_settings()
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=round(get_uptime_seconds(), 2),
    )


class FeaturesResponse(BaseModel):
    """Feature flags response."""
    cloud_sync: bool
    phone_verification: bool
    two_factor_auth: bool
    stripe_payments: bool


@router.get(
    "/features",
    response_model=FeaturesResponse,
    summary="Get enabled features",
    description="Returns which optional features are enabled on the backend.",
)
async def get_features() -> FeaturesResponse:
    """
    Get enabled features.
    
    Returns which optional features are enabled, allowing the frontend
    to conditionally show/hide functionality and avoid making requests
    to disabled endpoints.
    """
    settings = get_settings()
    return FeaturesResponse(
        cloud_sync=settings.feature_cloud_sync,
        phone_verification=bool(settings.twilio_account_sid and settings.twilio_auth_token),
        two_factor_auth=True,  # Always available
        stripe_payments=bool(settings.stripe_secret_key),
    )
