"""
Tests for rate limiting middleware.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from starlette.responses import Response

from app.services.rate_limit import (
    RateLimitMiddleware,
    RATE_LIMITS,
    ENDPOINT_LIMITS,
    EXEMPT_ENDPOINTS,
)


class TestRateLimitConfiguration:
    """Tests for rate limit configuration."""

    def test_rate_limits_defined(self):
        """Test that rate limits are defined for all tiers."""
        assert "anonymous" in RATE_LIMITS
        assert "authenticated" in RATE_LIMITS
        assert "premium" in RATE_LIMITS
        assert "admin" in RATE_LIMITS

    def test_rate_limits_hierarchy(self):
        """Test that higher tiers have higher limits."""
        assert RATE_LIMITS["anonymous"] < RATE_LIMITS["authenticated"]
        assert RATE_LIMITS["authenticated"] < RATE_LIMITS["premium"]
        assert RATE_LIMITS["premium"] < RATE_LIMITS["admin"]

    def test_endpoint_limits_exist(self):
        """Test that endpoint-specific limits are defined."""
        assert "/api/ai-jobs" in ENDPOINT_LIMITS
        assert "/api/songs" in ENDPOINT_LIMITS
        assert "/api/auth/login" in ENDPOINT_LIMITS

    def test_exempt_endpoints_include_health(self):
        """Test that health endpoints are exempt."""
        assert "/health" in EXEMPT_ENDPOINTS
        assert "/health/ready" in EXEMPT_ENDPOINTS


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redis = AsyncMock()
        self.redis_getter = AsyncMock(return_value=self.redis)
        self.app = MagicMock()
        self.middleware = RateLimitMiddleware(self.app, self.redis_getter)

    def _create_request(
        self, path: str = "/api/test", auth_header: str = None, client_ip: str = "1.2.3.4"
    ) -> Request:
        """Create a mock request."""
        request = MagicMock(spec=Request)
        request.url.path = path
        request.headers = {}
        if auth_header:
            request.headers["Authorization"] = auth_header
        request.client = MagicMock()
        request.client.host = client_ip
        request.state = MagicMock()
        request.state.user = None
        return request

    @pytest.mark.asyncio
    async def test_exempt_endpoints_bypass_rate_limiting(self):
        """Test that exempt endpoints bypass rate limiting."""
        request = self._create_request(path="/health")
        call_next = AsyncMock(return_value=Response(content="OK"))

        await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once()
        self.redis_getter.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_endpoints_bypass_rate_limiting(self):
        """Test that WebSocket endpoints bypass rate limiting."""
        request = self._create_request(path="/ws/jobs")
        call_next = AsyncMock(return_value=Response(content="OK"))

        await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once()
        self.redis_getter.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_unavailable_allows_request(self):
        """Test that requests are allowed when Redis is unavailable."""
        self.redis_getter.side_effect = Exception("Redis unavailable")
        request = self._create_request(path="/api/test")
        call_next = AsyncMock(return_value=Response(content="OK"))

        await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_headers_added(self):
        """Test that rate limit headers are added to response."""
        request = self._create_request()
        original_response = Response(content="OK")
        call_next = AsyncMock(return_value=original_response)

        # Mock Redis commands
        self.redis.zremrangebyscore = AsyncMock()
        self.redis.zcard = AsyncMock(return_value=5)
        self.redis.zadd = AsyncMock()
        self.redis.expire = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self):
        """Test that exceeding rate limit returns 429."""
        request = self._create_request()
        call_next = AsyncMock(return_value=Response(content="OK"))

        # Mock Redis commands - count exceeds limit
        self.redis.zremrangebyscore = AsyncMock()
        self.redis.zcard = AsyncMock(return_value=999)
        self.redis.zadd = AsyncMock()
        self.redis.expire = AsyncMock()

        response = await self.middleware.dispatch(request, call_next)

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        call_next.assert_not_called()

    def test_get_client_ip_from_direct_connection(self):
        """Test extracting client IP from direct connection."""
        request = self._create_request(client_ip="192.168.1.1")

        ip = self.middleware._get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_from_forwarded_header(self):
        """Test extracting client IP from X-Forwarded-For header."""
        request = self._create_request(client_ip="10.0.0.1")
        request.headers["X-Forwarded-For"] = "203.0.113.50, 70.41.3.18, 150.172.238.178"

        ip = self.middleware._get_client_ip(request)

        assert ip == "203.0.113.50"

    def test_get_limit_uses_endpoint_specific(self):
        """Test that endpoint-specific limits are used."""
        limit = self.middleware._get_limit("/api/ai-jobs", "authenticated")
        
        assert limit == ENDPOINT_LIMITS["/api/ai-jobs"]["authenticated"]

    def test_get_limit_falls_back_to_default(self):
        """Test that default limits are used for unlisted endpoints."""
        limit = self.middleware._get_limit("/api/unknown", "authenticated")
        
        assert limit == RATE_LIMITS["authenticated"]


class TestRateLimitTiers:
    """Tests for rate limit tier detection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redis = AsyncMock()
        self.redis_getter = AsyncMock(return_value=self.redis)
        self.app = MagicMock()
        self.middleware = RateLimitMiddleware(self.app, self.redis_getter)

    @pytest.mark.asyncio
    async def test_anonymous_tier_without_auth(self):
        """Test anonymous tier for unauthenticated requests."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.state = MagicMock()
        request.state.user = None

        tier = await self.middleware._get_user_tier(request, None)

        assert tier == "anonymous"

    @pytest.mark.asyncio
    async def test_authenticated_tier_with_user(self):
        """Test authenticated tier for regular users."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = MagicMock()
        request.state.user.is_admin = False
        request.state.user.subscription_tier = "free"

        tier = await self.middleware._get_user_tier(request, "user-123")

        assert tier == "authenticated"

    @pytest.mark.asyncio
    async def test_premium_tier_for_pro_users(self):
        """Test premium tier for pro subscribers."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = MagicMock()
        request.state.user.is_admin = False
        request.state.user.subscription_tier = "pro"

        tier = await self.middleware._get_user_tier(request, "user-123")

        assert tier == "premium"

    @pytest.mark.asyncio
    async def test_admin_tier_for_admins(self):
        """Test admin tier for admin users."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user = MagicMock()
        request.state.user.is_admin = True

        tier = await self.middleware._get_user_tier(request, "admin-123")

        assert tier == "admin"
