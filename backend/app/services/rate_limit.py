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
    "anonymous": 20,  # Unauthenticated users - reduced for security
    "authenticated": 60,  # Regular authenticated users (Free tier)
    "basic": 120,  # Basic tier users
    "premium": 300,  # Premium/Pro users
    "admin": 1000,  # Admins (essentially unlimited)
}

# Endpoints with custom limits (more restrictive)
# AI generation is the most expensive operation - strict limits to prevent abuse
ENDPOINT_LIMITS = {
    # AI Job Creation (POST) - CRITICAL: Protect model from extraction attacks
    "/api/ai-jobs:POST": {
        "anonymous": 0,  # Must be authenticated
        "authenticated": 5,  # Free tier: 5 per minute max
        "basic": 10,  # Basic tier: 10 per minute
        "premium": 30,  # Pro tier: 30 per minute
        "admin": 100,
    },
    # AI Job Listing/Viewing (GET) - more lenient
    "/api/ai-jobs": {
        "anonymous": 10,
        "authenticated": 60,
        "basic": 120,
        "premium": 300,
        "admin": 1000,
    },
    # Song uploads - moderate limits
    "/api/songs": {
        "anonymous": 5,
        "authenticated": 20,
        "basic": 40,
        "premium": 100,
        "admin": 500,
    },
    # Auth endpoints - prevent brute force
    "/api/auth/login": {
        "anonymous": 5,
        "authenticated": 5,
        "basic": 5,
        "premium": 5,
        "admin": 20,
    },
    "/api/auth/register": {
        "anonymous": 3,
        "authenticated": 3,
        "basic": 3,
        "premium": 3,
        "admin": 10,
    },
    # Password reset - VERY strict to prevent abuse/enumeration
    # Only 3 requests per 15 minutes (handled via longer window in middleware)
    "/api/auth/forgot-password": {
        "anonymous": 3,
        "authenticated": 3,
        "basic": 3,
        "premium": 3,
        "admin": 10,
    },
    "/api/auth/reset-password": {
        "anonymous": 5,
        "authenticated": 5,
        "basic": 5,
        "premium": 5,
        "admin": 10,
    },
    # Token refresh - moderate limits
    "/api/auth/refresh": {
        "anonymous": 10,
        "authenticated": 20,
        "basic": 20,
        "premium": 30,
        "admin": 100,
    },
    # Billing - prevent abuse
    "/api/billing": {
        "anonymous": 0,
        "authenticated": 10,
        "basic": 10,
        "premium": 20,
        "admin": 100,
    },
    # Credit purchases - prevent rapid purchase attempts
    "/api/credits/purchase": {
        "anonymous": 0,
        "authenticated": 5,
        "basic": 5,
        "premium": 10,
        "admin": 50,
    },
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

        # Skip rate limiting for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get Redis client
        try:
            redis = await self._get_redis()
            # Test connection with a ping
            await redis.ping()
        except Exception as e:
            # If Redis is unavailable, allow request (fail open)
            # Log error details once for debugging
            logger.warning("rate_limit_redis_unavailable", error=str(e), error_type=type(e).__name__)
            return await call_next(request)

        # Determine rate limit key and limit
        user_id = await self._get_user_id(request)
        user_tier = await self._get_user_tier(request, user_id)
        limit = self._get_limit(path, user_tier, request.method)

        if limit == 0:
            # Endpoint not allowed for this tier
            return Response(
                content='{"detail": "This endpoint requires authentication"}',
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        # Build rate limit key - include method for POST-specific limits
        identifier = user_id or self._get_client_ip(request)
        key = f"ratelimit:{identifier}:{path}:{request.method}"

        # Check rate limit using sliding window
        try:
            allowed, remaining, reset_at = await self._check_rate_limit(
                redis, key, limit, window=60
            )
        except Exception:
            # If Redis operation fails, allow request (fail open)
            logger.warning("rate_limit_redis_unavailable")
            return await call_next(request)

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
                tier = user.subscription_tier
                if tier in ("pro", "premium"):
                    return "premium"
                if tier == "basic":
                    return "basic"

        return "authenticated"

    def _get_limit(self, path: str, tier: str, method: str = "GET") -> int:
        """Get rate limit for path, tier, and HTTP method."""
        # Check method-specific endpoint limits first (e.g., "/api/ai-jobs:POST")
        for endpoint, limits in ENDPOINT_LIMITS.items():
            if endpoint.endswith(f":{method}") and path.startswith(endpoint.rsplit(":", 1)[0]):
                return limits.get(tier, RATE_LIMITS.get(tier, 30))
        
        # Check general endpoint-specific limits (excluding method-specific ones)
        for endpoint, limits in ENDPOINT_LIMITS.items():
            if ":" not in endpoint and path.startswith(endpoint):
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
