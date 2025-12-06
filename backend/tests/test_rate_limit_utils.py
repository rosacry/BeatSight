"""Tests for rate limiting utilities (app.utils.rate_limit)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.rate_limit import (
    RateLimitConfig,
    RateLimitPresets,
    RateLimitResult,
    RateLimitStats,
    RateLimitStrategy,
    RateLimiter,
    check_rate_limit_for_request,
    rate_limited,
    rate_limiter,
)


# =============================================================================
# RateLimitResult Tests
# =============================================================================

class TestRateLimitResult:
    """Tests for RateLimitResult class."""
    
    def test_allowed_result(self):
        """Test an allowed rate limit result."""
        result = RateLimitResult(
            allowed=True,
            remaining=9,
            limit=10,
            reset=1234567890,
        )
        
        assert result.allowed is True
        assert result.remaining == 9
        assert result.limit == 10
        assert result.retry_after == 0
    
    def test_blocked_result(self):
        """Test a blocked rate limit result."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            limit=10,
            reset=1234567890,
            retry_after=30,
        )
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after == 30
    
    def test_to_headers_allowed(self):
        """Test header generation for allowed request."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            limit=10,
            reset=1234567890,
        )
        
        headers = result.to_headers()
        
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "5"
        assert headers["X-RateLimit-Reset"] == "1234567890"
        assert "Retry-After" not in headers
    
    def test_to_headers_blocked(self):
        """Test header generation for blocked request."""
        result = RateLimitResult(
            allowed=False,
            remaining=-1,
            limit=10,
            reset=1234567890,
            retry_after=45,
        )
        
        headers = result.to_headers()
        
        assert headers["X-RateLimit-Limit"] == "10"
        assert headers["X-RateLimit-Remaining"] == "0"  # Clamped to 0
        assert headers["Retry-After"] == "45"


# =============================================================================
# RateLimitStats Tests
# =============================================================================

class TestRateLimitStats:
    """Tests for RateLimitStats class."""
    
    def test_default_values(self):
        """Test default statistics values."""
        stats = RateLimitStats()
        
        assert stats.total_requests == 0
        assert stats.allowed_requests == 0
        assert stats.blocked_requests == 0
        assert isinstance(stats.last_reset, datetime)
    
    def test_block_rate_no_requests(self):
        """Test block rate with no requests."""
        stats = RateLimitStats()
        assert stats.block_rate == 0.0
    
    def test_block_rate_all_allowed(self):
        """Test block rate with all allowed."""
        stats = RateLimitStats(
            total_requests=100,
            allowed_requests=100,
            blocked_requests=0,
        )
        assert stats.block_rate == 0.0
    
    def test_block_rate_some_blocked(self):
        """Test block rate with some blocked."""
        stats = RateLimitStats(
            total_requests=100,
            allowed_requests=80,
            blocked_requests=20,
        )
        assert stats.block_rate == 0.2
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = RateLimitStats(
            total_requests=100,
            allowed_requests=90,
            blocked_requests=10,
        )
        result = stats.to_dict()
        
        assert result["total_requests"] == 100
        assert result["allowed_requests"] == 90
        assert result["blocked_requests"] == 10
        assert result["block_rate"] == 0.1
        assert "last_reset" in result
    
    def test_reset(self):
        """Test resetting statistics."""
        stats = RateLimitStats(
            total_requests=100,
            allowed_requests=90,
            blocked_requests=10,
        )
        old_reset = stats.last_reset
        
        time.sleep(0.01)
        stats.reset()
        
        assert stats.total_requests == 0
        assert stats.allowed_requests == 0
        assert stats.blocked_requests == 0
        assert stats.last_reset > old_reset


# =============================================================================
# RateLimitConfig Tests
# =============================================================================

class TestRateLimitConfig:
    """Tests for RateLimitConfig class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        config = RateLimitConfig(requests=100, window=60)
        
        assert config.requests == 100
        assert config.window == 60
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW
        assert config.burst_size == 100  # Defaults to requests
        assert config.key_prefix == "beatsight:ratelimit"
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests=50,
            window=120,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_size=10,
        )
        
        assert config.requests == 50
        assert config.window == 120
        assert config.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert config.burst_size == 10


# =============================================================================
# RateLimiter Tests
# =============================================================================

class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client with storage."""
        storage = {}
        
        async def mock_get(key):
            return storage.get(key)
        
        async def mock_set(key, value):
            storage[key] = value
        
        async def mock_setex(key, ttl, value):
            storage[key] = value
        
        async def mock_incr(key):
            current = int(storage.get(key, 0))
            storage[key] = str(current + 1)
            return current + 1
        
        async def mock_expire(key, ttl):
            pass
        
        async def mock_delete(*keys):
            count = 0
            for key in keys:
                if key in storage:
                    del storage[key]
                    count += 1
            return count
        
        async def mock_scan(cursor, match, count):
            matching = [k for k in storage.keys() if match.replace("*", "") in k]
            return (0, matching)
        
        # Mock pipeline
        class MockPipeline:
            def __init__(self):
                self.commands = []
            
            async def set(self, key, value):
                storage[key] = value
            
            async def expire(self, key, ttl):
                pass
            
            async def execute(self):
                return []
            
            async def __aenter__(self):
                return self
            
            async def __aexit__(self, *args):
                pass
        
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=mock_get)
        redis.set = AsyncMock(side_effect=mock_set)
        redis.setex = AsyncMock(side_effect=mock_setex)
        redis.incr = AsyncMock(side_effect=mock_incr)
        redis.expire = AsyncMock(side_effect=mock_expire)
        redis.delete = AsyncMock(side_effect=mock_delete)
        redis.scan = AsyncMock(side_effect=mock_scan)
        redis.pipeline = MagicMock(return_value=MockPipeline())
        redis._storage = storage
        
        return redis
    
    @pytest.fixture
    def limiter(self, mock_redis):
        """Create a configured rate limiter."""
        limiter = RateLimiter()
        limiter.configure(AsyncMock(return_value=mock_redis))
        return limiter
    
    @pytest.mark.asyncio
    async def test_fixed_window_allows_under_limit(self, limiter):
        """Test fixed window allows requests under limit."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        result = await limiter.check("test_key", config)
        
        assert result.allowed is True
        assert result.remaining == 9
        assert result.limit == 10
    
    @pytest.mark.asyncio
    async def test_fixed_window_blocks_over_limit(self, limiter, mock_redis):
        """Test fixed window blocks requests over limit."""
        config = RateLimitConfig(
            requests=2,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        # Make 3 requests
        await limiter.check("test_key", config)
        await limiter.check("test_key", config)
        result = await limiter.check("test_key", config)
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_sliding_window_allows_under_limit(self, limiter):
        """Test sliding window allows requests under limit."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
        )
        
        result = await limiter.check("test_key", config)
        
        assert result.allowed is True
        assert result.remaining >= 8  # May vary due to weighted calculation
    
    @pytest.mark.asyncio
    async def test_sliding_window_blocks_over_limit(self, limiter):
        """Test sliding window blocks requests over limit."""
        config = RateLimitConfig(
            requests=2,
            window=60,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
        )
        
        # Make multiple requests
        await limiter.check("test_key", config)
        await limiter.check("test_key", config)
        result = await limiter.check("test_key", config)
        
        assert result.allowed is False
        assert result.remaining == 0
    
    @pytest.mark.asyncio
    async def test_token_bucket_allows_burst(self, limiter):
        """Test token bucket allows burst up to bucket size."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_size=5,
        )
        
        # First request should be allowed
        result = await limiter.check("test_key", config)
        
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_token_bucket_blocks_when_empty(self, limiter, mock_redis):
        """Test token bucket blocks when tokens depleted."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_size=2,
        )
        
        # Manually set bucket to empty
        mock_redis._storage["beatsight:ratelimit:test_key:bucket"] = "0"
        mock_redis._storage["beatsight:ratelimit:test_key:last_update"] = str(time.time())
        
        result = await limiter.check("test_key", config)
        
        assert result.allowed is False
        assert result.retry_after > 0
    
    @pytest.mark.asyncio
    async def test_leaky_bucket_allows_under_capacity(self, limiter):
        """Test leaky bucket allows requests under capacity."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.LEAKY_BUCKET,
            burst_size=5,
        )
        
        result = await limiter.check("test_key", config)
        
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_different_keys_independent(self, limiter):
        """Test that different keys have independent limits."""
        config = RateLimitConfig(
            requests=2,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        # Max out key1
        await limiter.check("key1", config)
        await limiter.check("key1", config)
        result_key1 = await limiter.check("key1", config)
        
        # key2 should still be allowed
        result_key2 = await limiter.check("key2", config)
        
        assert result_key1.allowed is False
        assert result_key2.allowed is True
    
    @pytest.mark.asyncio
    async def test_reset_clears_limit(self, limiter, mock_redis):
        """Test that reset clears the rate limit."""
        config = RateLimitConfig(
            requests=2,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        # Max out
        await limiter.check("test_key", config)
        await limiter.check("test_key", config)
        
        # Reset
        success = await limiter.reset("test_key", config)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, limiter):
        """Test that statistics are tracked."""
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        await limiter.check("stats_test", config)
        await limiter.check("stats_test", config)
        
        stats = limiter.get_stats("stats_test")
        
        assert stats["total_requests"] == 2
        assert stats["allowed_requests"] == 2
        assert stats["blocked_requests"] == 0
    
    def test_get_stats_all(self, limiter):
        """Test getting all statistics."""
        limiter._stats["key1"] = RateLimitStats(total_requests=10)
        limiter._stats["key2"] = RateLimitStats(total_requests=20)
        
        all_stats = limiter.get_stats()
        
        assert "key1" in all_stats
        assert "key2" in all_stats
    
    def test_reset_stats_single(self, limiter):
        """Test resetting stats for single key."""
        limiter._stats["test"] = RateLimitStats(total_requests=10)
        
        limiter.reset_stats("test")
        
        assert limiter._stats["test"].total_requests == 0
    
    def test_reset_stats_all(self, limiter):
        """Test resetting all stats."""
        limiter._stats["key1"] = RateLimitStats(total_requests=10)
        limiter._stats["key2"] = RateLimitStats(total_requests=20)
        
        limiter.reset_stats()
        
        assert limiter._stats["key1"].total_requests == 0
        assert limiter._stats["key2"].total_requests == 0
    
    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self, limiter, mock_redis):
        """Test graceful handling of Redis errors."""
        mock_redis.incr = AsyncMock(side_effect=Exception("Redis error"))
        
        config = RateLimitConfig(
            requests=10,
            window=60,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        
        # Should fail open (allow request)
        result = await limiter.check("test_key", config)
        
        assert result.allowed is True


# =============================================================================
# Decorator Tests
# =============================================================================

class TestRateLimitedDecorator:
    """Tests for @rate_limited decorator."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        storage = {}
        
        async def mock_get(key):
            return storage.get(key)
        
        async def mock_incr(key):
            current = int(storage.get(key, 0))
            storage[key] = str(current + 1)
            return current + 1
        
        async def mock_expire(key, ttl):
            pass
        
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=mock_get)
        redis.incr = AsyncMock(side_effect=mock_incr)
        redis.expire = AsyncMock(side_effect=mock_expire)
        redis._storage = storage
        
        return redis
    
    @pytest.fixture(autouse=True)
    def setup_rate_limiter(self, mock_redis):
        """Configure global rate limiter."""
        rate_limiter.configure(AsyncMock(return_value=mock_redis))
        rate_limiter._stats.clear()
        yield
    
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        """Test decorator allows requests under limit."""
        @rate_limited(requests=10, window=60)
        async def my_endpoint() -> str:
            return "success"
        
        result = await my_endpoint()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, mock_redis):
        """Test decorator blocks requests over limit."""
        # Pre-fill to over limit
        now = int(time.time())
        window_start = (now // 60) * 60
        mock_redis._storage[f"beatsight:ratelimit:limited_func:{window_start}"] = "10"
        
        @rate_limited(requests=2, window=60)
        async def limited_func() -> str:
            return "success"
        
        # This should raise HTTPException
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await limited_func()
        
        assert exc_info.value.status_code == 429
        assert "rate_limit_exceeded" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_custom_key_func(self):
        """Test decorator with custom key function."""
        call_count = 0
        
        @rate_limited(
            requests=10,
            window=60,
            key_func=lambda user_id: f"user:{user_id}",
        )
        async def my_endpoint(user_id: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"success for {user_id}"
        
        result = await my_endpoint("123")
        assert result == "success for 123"
        assert call_count == 1


# =============================================================================
# Presets Tests
# =============================================================================

class TestRateLimitPresets:
    """Tests for predefined rate limit configurations."""
    
    def test_api_standard(self):
        """Test API_STANDARD preset."""
        assert RateLimitPresets.API_STANDARD.requests == 100
        assert RateLimitPresets.API_STANDARD.window == 60
    
    def test_api_strict(self):
        """Test API_STRICT preset."""
        assert RateLimitPresets.API_STRICT.requests == 10
        assert RateLimitPresets.API_STRICT.window == 60
    
    def test_auth(self):
        """Test AUTH preset."""
        assert RateLimitPresets.AUTH.requests == 5
        assert RateLimitPresets.AUTH.window == 60
        assert RateLimitPresets.AUTH.strategy == RateLimitStrategy.FIXED_WINDOW
    
    def test_password_reset(self):
        """Test PASSWORD_RESET preset."""
        assert RateLimitPresets.PASSWORD_RESET.requests == 3
        assert RateLimitPresets.PASSWORD_RESET.window == 3600
    
    def test_ai_generation(self):
        """Test AI_GENERATION preset."""
        assert RateLimitPresets.AI_GENERATION.requests == 10
        assert RateLimitPresets.AI_GENERATION.window == 3600
        assert RateLimitPresets.AI_GENERATION.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert RateLimitPresets.AI_GENERATION.burst_size == 5
    
    def test_upload(self):
        """Test UPLOAD preset."""
        assert RateLimitPresets.UPLOAD.requests == 20
        assert RateLimitPresets.UPLOAD.strategy == RateLimitStrategy.LEAKY_BUCKET
    
    def test_webhook(self):
        """Test WEBHOOK preset."""
        assert RateLimitPresets.WEBHOOK.requests == 1000
        assert RateLimitPresets.WEBHOOK.burst_size == 100
    
    def test_search(self):
        """Test SEARCH preset."""
        assert RateLimitPresets.SEARCH.requests == 60
        assert RateLimitPresets.SEARCH.window == 60


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        storage = {}
        
        async def mock_get(key):
            return storage.get(key)
        
        async def mock_incr(key):
            current = int(storage.get(key, 0))
            storage[key] = str(current + 1)
            return current + 1
        
        async def mock_expire(key, ttl):
            pass
        
        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=mock_get)
        redis.incr = AsyncMock(side_effect=mock_incr)
        redis.expire = AsyncMock(side_effect=mock_expire)
        
        return redis
    
    @pytest.fixture(autouse=True)
    def setup_rate_limiter(self, mock_redis):
        """Configure global rate limiter."""
        rate_limiter.configure(AsyncMock(return_value=mock_redis))
        rate_limiter._stats.clear()
        yield
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_for_request(self):
        """Test check_rate_limit_for_request helper."""
        config = RateLimitConfig(requests=100, window=60)
        
        result = await check_rate_limit_for_request("192.168.1.1", config)
        
        assert result.allowed is True
        assert result.limit == 100


# =============================================================================
# Strategy Tests
# =============================================================================

class TestRateLimitStrategy:
    """Tests for rate limit strategy enum."""
    
    def test_strategy_values(self):
        """Test strategy enum values."""
        assert RateLimitStrategy.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW.value == "sliding_window"
        assert RateLimitStrategy.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitStrategy.LEAKY_BUCKET.value == "leaky_bucket"
    
    def test_strategy_count(self):
        """Test we have all expected strategies."""
        assert len(RateLimitStrategy) == 4
