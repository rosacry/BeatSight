"""
Rate Limiting Middleware

Redis-backed rate limiting with sliding window algorithm.
Supports per-user, per-IP, and per-endpoint limits.
"""

from __future__ import annotations

import time
import hashlib
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog


logger = structlog.get_logger(__name__)


# ============================================================================
# Rate Limit Configuration
# ============================================================================


class RateLimitConfig:
    """Configuration for a rate limit rule."""

    def __init__(
        self,
        requests: int,
        window_seconds: int,
        key_prefix: str = "rl",
        burst_allowance: int = 0,
    ):
        self.requests = requests
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.burst_allowance = burst_allowance

    @property
    def total_requests(self) -> int:
        """Total requests allowed including burst."""
        return self.requests + self.burst_allowance


# Default rate limits for different endpoint types
class RateLimits:
    """Pre-configured rate limit profiles."""

    # Standard API endpoints
    STANDARD = RateLimitConfig(requests=100, window_seconds=60)

    # Authentication endpoints (stricter)
    AUTH = RateLimitConfig(requests=10, window_seconds=60)

    # Search/listing endpoints
    SEARCH = RateLimitConfig(requests=30, window_seconds=60)

    # Upload endpoints
    UPLOAD = RateLimitConfig(requests=10, window_seconds=300, burst_allowance=2)

    # AI/Transcription endpoints (expensive operations)
    AI_PROCESSING = RateLimitConfig(requests=5, window_seconds=300)

    # Premium users
    PREMIUM = RateLimitConfig(requests=500, window_seconds=60)

    # Admin endpoints
    ADMIN = RateLimitConfig(requests=1000, window_seconds=60)


# ============================================================================
# Rate Limiter Implementation
# ============================================================================


class RateLimiter:
    """
    Redis-backed rate limiter using sliding window algorithm.

    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._local_cache: dict[str, list[float]] = {}

    async def is_allowed(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed and return rate limit info.

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        full_key = f"{config.key_prefix}:{key}"
        now = time.time()
        window_start = now - config.window_seconds

        if self._redis is not None:
            return await self._check_redis(full_key, config, now, window_start)
        else:
            return self._check_local(full_key, config, now, window_start)

    async def _check_redis(
        self,
        key: str,
        config: RateLimitConfig,
        now: float,
        window_start: float,
    ) -> tuple[bool, dict]:
        """Check rate limit using Redis sorted set."""
        try:
            pipe = self._redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current entries
            pipe.zcard(key)

            # Add new entry
            pipe.zadd(key, {str(now): now})

            # Set expiry
            pipe.expire(key, config.window_seconds + 1)

            results = await pipe.execute()
            request_count = results[1]

            remaining = max(0, config.total_requests - request_count - 1)
            reset_time = int(now + config.window_seconds)

            info = {
                "limit": config.total_requests,
                "remaining": remaining,
                "reset": reset_time,
                "window": config.window_seconds,
            }

            is_allowed = request_count < config.total_requests

            if not is_allowed:
                # Remove the entry we just added
                await self._redis.zrem(key, str(now))

            return is_allowed, info

        except Exception as e:
            logger.error("redis_rate_limit_error", error=str(e), key=key)
            # Fall back to allowing the request on Redis errors
            return True, {
                "limit": config.total_requests,
                "remaining": config.total_requests,
                "reset": int(now + config.window_seconds),
                "window": config.window_seconds,
            }

    def _check_local(
        self,
        key: str,
        config: RateLimitConfig,
        now: float,
        window_start: float,
    ) -> tuple[bool, dict]:
        """Check rate limit using in-memory storage (fallback)."""
        if key not in self._local_cache:
            self._local_cache[key] = []

        # Clean old entries
        self._local_cache[key] = [
            ts for ts in self._local_cache[key] if ts > window_start
        ]

        request_count = len(self._local_cache[key])
        is_allowed = request_count < config.total_requests

        if is_allowed:
            self._local_cache[key].append(now)

        remaining = max(
            0, config.total_requests - request_count - (1 if is_allowed else 0)
        )

        return is_allowed, {
            "limit": config.total_requests,
            "remaining": remaining,
            "reset": int(now + config.window_seconds),
            "window": config.window_seconds,
        }

    async def reset(self, key: str, config: RateLimitConfig) -> None:
        """Reset rate limit for a key."""
        full_key = f"{config.key_prefix}:{key}"

        if self._redis is not None:
            await self._redis.delete(full_key)
        elif full_key in self._local_cache:
            del self._local_cache[full_key]


# Global rate limiter instance
rate_limiter = RateLimiter()


# ============================================================================
# Key Extraction Functions
# ============================================================================


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Get first IP in chain
        return forwarded.split(",")[0].strip()

    # Check for real IP header (Nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # Fall back to direct client
    return request.client.host if request.client else "unknown"


def get_rate_limit_key(request: Request, include_path: bool = True) -> str:
    """
    Generate a rate limit key for the request.

    Args:
        request: The incoming request
        include_path: Whether to include the path in the key
    """
    parts = [get_client_ip(request)]

    # Include user ID if authenticated
    if hasattr(request.state, "user") and request.state.user:
        parts.append(f"user:{request.state.user.id}")

    # Include path for endpoint-specific limits
    if include_path:
        path_hash = hashlib.md5(request.url.path.encode()).hexdigest()[:8]
        parts.append(f"path:{path_hash}")

    return ":".join(parts)


# ============================================================================
# Middleware
# ============================================================================


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.

    Applies rate limits based on IP, user, and endpoint.
    """

    def __init__(
        self,
        app,
        default_config: RateLimitConfig = RateLimits.STANDARD,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.default_config = default_config
        self.exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Get rate limit config for this endpoint
        config = self._get_config_for_request(request)

        # Generate rate limit key
        key = get_rate_limit_key(request)

        # Check rate limit
        is_allowed, info = await rate_limiter.is_allowed(key, config)

        if not is_allowed:
            logger.warning(
                "rate_limit_exceeded",
                ip=get_client_ip(request),
                path=request.url.path,
                limit=info["limit"],
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after": info["reset"] - int(time.time()),
                },
                headers=self._rate_limit_headers(info),
            )

        # Process request and add rate limit headers
        response = await call_next(request)

        for header, value in self._rate_limit_headers(info).items():
            response.headers[header] = value

        return response

    def _get_config_for_request(self, request: Request) -> RateLimitConfig:
        """Get appropriate rate limit config based on request."""
        path = request.url.path.lower()

        # Endpoint-specific limits
        if "/auth/" in path or "/login" in path or "/register" in path:
            return RateLimits.AUTH
        elif "/search" in path or "/browse" in path:
            return RateLimits.SEARCH
        elif "/upload" in path:
            return RateLimits.UPLOAD
        elif "/transcribe" in path or "/ai/" in path:
            return RateLimits.AI_PROCESSING
        elif "/admin/" in path:
            return RateLimits.ADMIN

        # Check for premium user
        if hasattr(request.state, "user") and request.state.user:
            if getattr(request.state.user, "is_premium", False):
                return RateLimits.PREMIUM

        return self.default_config

    def _rate_limit_headers(self, info: dict) -> dict[str, str]:
        """Generate rate limit response headers."""
        return {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"]),
            "X-RateLimit-Window": str(info["window"]),
        }


# ============================================================================
# Decorator for Endpoint-Specific Limits
# ============================================================================


def rate_limit(config: RateLimitConfig | None = None):
    """
    Decorator to apply rate limiting to specific endpoints.

    Usage:
        @router.get("/expensive-operation")
        @rate_limit(RateLimits.AI_PROCESSING)
        async def expensive_endpoint():
            ...
    """

    def decorator(func: Callable) -> Callable:
        # Store config on the function for middleware to use
        func._rate_limit_config = config or RateLimits.STANDARD
        return func

    return decorator


# ============================================================================
# Custom Route Class
# ============================================================================


class RateLimitedRoute(APIRoute):
    """
    Custom route class that handles rate limiting per-endpoint.

    Usage:
        router = APIRouter(route_class=RateLimitedRoute)
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def rate_limited_handler(request: Request) -> Response:
            # Check for endpoint-specific rate limit
            config = getattr(self.endpoint, "_rate_limit_config", RateLimits.STANDARD)

            key = get_rate_limit_key(request)
            is_allowed, info = await rate_limiter.is_allowed(key, config)

            if not is_allowed:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Too Many Requests",
                        "retry_after": info["reset"] - int(time.time()),
                    },
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(info["reset"] - int(time.time())),
                    },
                )

            return await original_route_handler(request)

        return rate_limited_handler
