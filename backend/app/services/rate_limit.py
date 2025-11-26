"""
Rate limiting middleware for API endpoints.

Implements sliding window rate limiting using Redis.
Different limits apply based on authentication status and user role.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)


# Rate limit configurations (requests per minute)
RATE_LIMITS = {
    "anonymous": 30,  # Unauthenticated users
    "authenticated": 100,  # Regular authenticated users
    "premium": 500,  # Premium/Pro users
    "admin": 1000,  # Admins (essentially unlimited)
}

# Endpoints with custom limits (more restrictive)
ENDPOINT_LIMITS = {
    "/api/ai-jobs": {"anonymous": 0, "authenticated": 10, "premium": 50},
    "/api/songs": {"anonymous": 10, "authenticated": 30, "premium": 100},
    "/api/auth/login": {"anonymous": 10, "authenticated": 10, "premium": 10},
    "/api/auth/register": {"anonymous": 5, "authenticated": 5, "premium": 5},
}

# Endpoints exempt from rate limiting
EXEMPT_ENDPOINTS = {
    "/health",
    "/health/ready",
    "/health/live",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiting middleware using Redis.

    Features:
    - Per-user and per-IP rate limiting
    - Different limits for authenticated vs anonymous users
    - Endpoint-specific rate limits
    - Premium user higher limits
    - Returns Retry-After header when rate limited
    """

    def __init__(self, app, redis_getter):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            redis_getter: Async function that returns Redis client
        """
        super().__init__(app)
        self._get_redis = redis_getter

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for exempt endpoints
        path = request.url.path
        if path in EXEMPT_ENDPOINTS or path.startswith("/ws"):
            return await call_next(request)

        # Get Redis client
        try:
            redis = await self._get_redis()
        except Exception:
            # If Redis is unavailable, allow request (fail open)
            logger.warning("rate_limit_redis_unavailable")
            return await call_next(request)

        # Determine rate limit key and limit
        user_id = await self._get_user_id(request)
        user_tier = await self._get_user_tier(request, user_id)
        limit = self._get_limit(path, user_tier)

        if limit == 0:
            # Endpoint not allowed for this tier
            return Response(
                content='{"detail": "This endpoint requires authentication"}',
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        # Build rate limit key
        identifier = user_id or self._get_client_ip(request)
        key = f"ratelimit:{identifier}:{path}"

        # Check rate limit using sliding window
        allowed, remaining, reset_at = await self._check_rate_limit(
            redis, key, limit, window=60
        )

        if not allowed:
            retry_after = max(1, int(reset_at - time.time()))
            logger.warning(
                "rate_limit_exceeded",
                user_id=user_id,
                path=path,
                tier=user_tier,
                limit=limit,
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at)),
                },
            )

        # Process request and add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_at))
        return response

    async def _check_rate_limit(
        self, redis: "Redis", key: str, limit: int, window: int = 60
    ) -> tuple[bool, int, float]:
        """
        Check rate limit using sliding window counter.

        Returns:
            Tuple of (allowed, remaining, reset_timestamp)
        """
        now = time.time()
        window_start = now - window

        # Simple implementation using individual commands
        # Remove old entries
        await redis.zremrangebyscore(key, 0, window_start)

        # Count current requests
        current_count = await redis.zcard(key)

        # Check if allowed before adding
        allowed = current_count < limit

        if allowed:
            # Add current request
            await redis.zadd(key, {str(now): now})
            # Set expiry
            await redis.expire(key, window + 1)

        # Calculate remaining and reset time
        remaining = max(0, limit - current_count - 1)
        reset_at = now + window

        allowed = current_count < limit
        return allowed, remaining, reset_at

    async def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request if authenticated."""
        # Check for user set by auth middleware
        if hasattr(request.state, "user") and request.state.user:
            return str(request.state.user.id)

        # Try to decode JWT from header (lightweight check)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # We don't fully validate here - just extract user ID
            # Full validation happens in the endpoint
            try:
                import jwt

                token = auth_header[7:]
                # Decode without verification just to get user ID
                payload = jwt.decode(token, options={"verify_signature": False})
                return payload.get("sub")
            except Exception:
                pass

        return None

    async def _get_user_tier(self, request: Request, user_id: Optional[str]) -> str:
        """Determine user's rate limit tier."""
        if not user_id:
            return "anonymous"

        # Check if user info is already on request
        if hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            if hasattr(user, "is_admin") and user.is_admin:
                return "admin"
            if hasattr(user, "subscription_tier"):
                if user.subscription_tier in ("pro", "premium"):
                    return "premium"

        return "authenticated"

    def _get_limit(self, path: str, tier: str) -> int:
        """Get rate limit for path and tier."""
        # Check endpoint-specific limits
        for endpoint, limits in ENDPOINT_LIMITS.items():
            if path.startswith(endpoint):
                return limits.get(tier, RATE_LIMITS.get(tier, 30))

        # Fall back to default tier limits
        return RATE_LIMITS.get(tier, 30)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxies."""
        # Check X-Forwarded-For header (behind load balancer/proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain (original client)
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


def setup_rate_limiting(app, redis_getter) -> None:
    """
    Set up rate limiting middleware on the FastAPI app.

    Args:
        app: FastAPI application instance
        redis_getter: Async function that returns Redis client
    """
    app.add_middleware(RateLimitMiddleware, redis_getter=redis_getter)
    logger.info("rate_limiting_enabled")
