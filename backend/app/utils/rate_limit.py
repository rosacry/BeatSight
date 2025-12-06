"""Rate limiting utilities with Redis backend.

Provides flexible rate limiting with multiple strategies:
- Fixed window rate limiting
- Sliding window rate limiting
- Token bucket algorithm
- Leaky bucket algorithm

Usage:
    from app.utils.rate_limit import rate_limiter, RateLimitConfig

    # Check rate limit
    result = await rate_limiter.check(
        key="user:123:api",
        config=RateLimitConfig(requests=100, window=60)
    )
    if not result.allowed:
        raise HTTPException(429, f"Rate limit exceeded. Retry in {result.retry_after}s")

    # Or use the decorator
    @rate_limited(requests=100, window=60, key_func=lambda req: req.client.host)
    async def my_endpoint(request: Request):
        ...
"""

from __future__ import annotations

import functools
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ParamSpec, TypeVar

import structlog

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        requests: Maximum number of requests allowed
        window: Time window in seconds
        strategy: Rate limiting strategy to use
        burst_size: Maximum burst size (for token/leaky bucket)
        key_prefix: Prefix for Redis keys
    """

    requests: int
    window: int  # seconds
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: int | None = None  # For token bucket
    key_prefix: str = "beatsight:ratelimit"

    def __post_init__(self) -> None:
        if self.burst_size is None:
            self.burst_size = self.requests


@dataclass
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed
        remaining: Number of requests remaining
        limit: Maximum number of requests
        reset: Unix timestamp when the limit resets
        retry_after: Seconds until the next request is allowed (if not allowed)
    """

    allowed: bool
    remaining: int
    limit: int
    reset: int
    retry_after: int = 0

    def to_headers(self) -> dict[str, str]:
        """Convert to rate limit HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset),
        }
        if self.retry_after > 0:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class RateLimitStats:
    """Statistics for rate limiting."""

    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def block_rate(self) -> float:
        """Calculate block rate."""
        if self.total_requests == 0:
            return 0.0
        return self.blocked_requests / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "allowed_requests": self.allowed_requests,
            "blocked_requests": self.blocked_requests,
            "block_rate": round(self.block_rate, 4),
            "last_reset": self.last_reset.isoformat(),
        }

    def reset(self) -> None:
        """Reset statistics."""
        self.total_requests = 0
        self.allowed_requests = 0
        self.blocked_requests = 0
        self.last_reset = datetime.now(timezone.utc)


class RateLimiter:
    """Redis-backed rate limiter with multiple strategies.

    Supports:
    - Fixed window: Simple counter per time window
    - Sliding window: More accurate, combines current and previous window
    - Token bucket: Allows bursts up to bucket size
    - Leaky bucket: Smooths out request rate
    """

    def __init__(self) -> None:
        self._redis_getter: Callable[[], Awaitable[Any]] | None = None
        self._stats: dict[str, RateLimitStats] = {}

    def configure(self, redis_getter: Callable[[], Awaitable[Any]]) -> None:
        """Configure the rate limiter with a Redis client getter.

        Args:
            redis_getter: Async function that returns a Redis client
        """
        self._redis_getter = redis_getter

    async def _get_redis(self) -> Any:
        """Get Redis client, raising if not configured."""
        if self._redis_getter is None:
            try:
                from app.db.redis import get_redis

                self._redis_getter = get_redis
            except ImportError:
                raise RuntimeError(
                    "Rate limiter not configured. "
                    "Call rate_limiter.configure(redis_getter) first."
                )
        return await self._redis_getter()

    def _get_stats(self, key: str) -> RateLimitStats:
        """Get or create stats for a key."""
        if key not in self._stats:
            self._stats[key] = RateLimitStats()
        return self._stats[key]

    def _build_key(self, config: RateLimitConfig, key: str) -> str:
        """Build full Redis key."""
        return f"{config.key_prefix}:{key}"

    async def check(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Check if a request is allowed under the rate limit.

        Args:
            key: Unique identifier for the rate limit (e.g., user ID, IP)
            config: Rate limit configuration

        Returns:
            RateLimitResult with allowed status and metadata
        """
        stats = self._get_stats(key)
        stats.total_requests += 1

        try:
            if config.strategy == RateLimitStrategy.FIXED_WINDOW:
                result = await self._check_fixed_window(key, config)
            elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                result = await self._check_sliding_window(key, config)
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                result = await self._check_token_bucket(key, config)
            else:  # LEAKY_BUCKET
                result = await self._check_leaky_bucket(key, config)

            if result.allowed:
                stats.allowed_requests += 1
            else:
                stats.blocked_requests += 1
                logger.warning(
                    "Rate limit exceeded",
                    key=key,
                    strategy=config.strategy.value,
                    remaining=result.remaining,
                    retry_after=result.retry_after,
                )

            return result

        except Exception as e:
            logger.error(
                "Rate limit check failed",
                key=key,
                error=str(e),
            )
            # Fail open - allow request on error
            return RateLimitResult(
                allowed=True,
                remaining=config.requests,
                limit=config.requests,
                reset=int(time.time()) + config.window,
            )

    async def _check_fixed_window(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Fixed window rate limiting.

        Simple counter that resets at the start of each window.
        Efficient but can allow 2x burst at window boundaries.
        """
        redis = await self._get_redis()
        full_key = self._build_key(config, key)
        now = int(time.time())
        window_start = (now // config.window) * config.window
        window_key = f"{full_key}:{window_start}"

        # Increment counter
        count = await redis.incr(window_key)

        # Set expiration on first request
        if count == 1:
            await redis.expire(window_key, config.window)

        reset_time = window_start + config.window
        remaining = config.requests - count

        if count > config.requests:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset=reset_time,
                retry_after=reset_time - now,
            )

        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            limit=config.requests,
            reset=reset_time,
        )

    async def _check_sliding_window(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Sliding window rate limiting.

        Combines current and previous window counts for smoother limiting.
        More accurate than fixed window, prevents boundary bursts.
        """
        redis = await self._get_redis()
        full_key = self._build_key(config, key)
        now = int(time.time())

        # Current and previous window
        current_window = (now // config.window) * config.window
        previous_window = current_window - config.window

        current_key = f"{full_key}:{current_window}"
        previous_key = f"{full_key}:{previous_window}"

        # Get both counts
        current_count = await redis.get(current_key)
        previous_count = await redis.get(previous_key)

        current_count = int(current_count) if current_count else 0
        previous_count = int(previous_count) if previous_count else 0

        # Calculate weighted count
        # Weight of previous window based on how far into current window we are
        elapsed = now - current_window
        previous_weight = 1 - (elapsed / config.window)
        weighted_count = current_count + (previous_count * previous_weight)

        reset_time = current_window + config.window

        if weighted_count >= config.requests:
            # Calculate when we'll have capacity again
            retry_after = max(1, int(config.window - elapsed))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset=reset_time,
                retry_after=retry_after,
            )

        # Increment current window
        new_count = await redis.incr(current_key)
        if new_count == 1:
            await redis.expire(current_key, config.window * 2)

        remaining = int(config.requests - weighted_count - 1)

        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            limit=config.requests,
            reset=reset_time,
        )

    async def _check_token_bucket(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Token bucket rate limiting.

        Tokens are added at a fixed rate up to bucket size.
        Allows bursts while maintaining average rate.
        """
        redis = await self._get_redis()
        full_key = self._build_key(config, key)
        now = time.time()

        bucket_key = f"{full_key}:bucket"
        last_update_key = f"{full_key}:last_update"

        # Get current state
        tokens_str = await redis.get(bucket_key)
        last_update_str = await redis.get(last_update_key)

        # Initialize if needed
        tokens = (
            float(tokens_str)
            if tokens_str
            else float(config.burst_size or config.requests)
        )
        last_update = float(last_update_str) if last_update_str else now

        # Calculate tokens to add based on time elapsed
        elapsed = now - last_update
        refill_rate = config.requests / config.window
        tokens_to_add = elapsed * refill_rate
        tokens = min(config.burst_size or config.requests, tokens + tokens_to_add)

        reset_time = int(now) + config.window

        if tokens < 1:
            # Not enough tokens
            time_for_token = (1 - tokens) / refill_rate
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset=reset_time,
                retry_after=max(1, int(time_for_token)),
            )

        # Consume a token
        tokens -= 1

        # Update state atomically
        async with redis.pipeline() as pipe:
            await pipe.set(bucket_key, str(tokens))
            await pipe.set(last_update_key, str(now))
            await pipe.expire(bucket_key, config.window * 2)
            await pipe.expire(last_update_key, config.window * 2)
            await pipe.execute()

        return RateLimitResult(
            allowed=True,
            remaining=int(tokens),
            limit=config.requests,
            reset=reset_time,
        )

    async def _check_leaky_bucket(
        self,
        key: str,
        config: RateLimitConfig,
    ) -> RateLimitResult:
        """Leaky bucket rate limiting.

        Requests are processed at a fixed rate.
        Smooths out bursty traffic.
        """
        redis = await self._get_redis()
        full_key = self._build_key(config, key)
        now = time.time()

        bucket_key = f"{full_key}:leaky"

        # Get current queue level
        level_str = await redis.get(bucket_key)
        level = float(level_str) if level_str else 0.0

        # Leak rate (requests per second)
        leak_rate = config.requests / config.window

        # Calculate time since last request would have leaked
        if level > 0:
            # Some water has leaked out
            leaked = level - (1 / leak_rate * (now % config.window))
            level = max(0, leaked)

        bucket_size = config.burst_size or config.requests
        reset_time = int(now) + config.window

        if level >= bucket_size:
            # Bucket is full
            drain_time = (level - bucket_size + 1) / leak_rate
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=config.requests,
                reset=reset_time,
                retry_after=max(1, int(drain_time)),
            )

        # Add to bucket
        level += 1
        await redis.setex(bucket_key, config.window * 2, str(level))

        remaining = int(bucket_size - level)

        return RateLimitResult(
            allowed=True,
            remaining=max(0, remaining),
            limit=config.requests,
            reset=reset_time,
        )

    async def reset(self, key: str, config: RateLimitConfig) -> bool:
        """Reset rate limit for a key.

        Args:
            key: The rate limit key to reset
            config: Rate limit configuration

        Returns:
            True if successfully reset
        """
        try:
            redis = await self._get_redis()
            full_key = self._build_key(config, key)

            # Delete all related keys
            pattern = f"{full_key}*"
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break

            logger.info(
                "Rate limit reset",
                key=key,
            )
            return True

        except Exception as e:
            logger.error(
                "Rate limit reset failed",
                key=key,
                error=str(e),
            )
            return False

    def get_stats(self, key: str | None = None) -> dict[str, Any]:
        """Get rate limiting statistics.

        Args:
            key: Specific key or None for all

        Returns:
            Statistics dictionary
        """
        if key:
            return self._get_stats(key).to_dict()

        return {k: stats.to_dict() for k, stats in self._stats.items()}

    def reset_stats(self, key: str | None = None) -> None:
        """Reset statistics.

        Args:
            key: Specific key or None for all
        """
        if key:
            if key in self._stats:
                self._stats[key].reset()
        else:
            for stats in self._stats.values():
                stats.reset()


# Global rate limiter instance
rate_limiter = RateLimiter()


# =============================================================================
# Decorator for FastAPI routes
# =============================================================================


def rate_limited(
    requests: int,
    window: int,
    key_func: Callable[..., str] | None = None,
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW,
    burst_size: int | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to apply rate limiting to an async function.

    Args:
        requests: Maximum requests per window
        window: Time window in seconds
        key_func: Function to extract rate limit key from arguments
        strategy: Rate limiting strategy
        burst_size: Maximum burst size

    Returns:
        Decorated function

    Example:
        @rate_limited(requests=100, window=60)
        async def api_endpoint(request: Request):
            ...
    """
    config = RateLimitConfig(
        requests=requests,
        window=window,
        strategy=strategy,
        burst_size=burst_size,
    )

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: use function name
                key = func.__name__

            # Check rate limit
            result = await rate_limiter.check(key, config)

            if not result.allowed:
                # Import here to avoid circular dependency
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "retry_after": result.retry_after,
                    },
                    headers=result.to_headers(),
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Predefined configurations
# =============================================================================


class RateLimitPresets:
    """Predefined rate limit configurations."""

    # Standard API rate limits
    API_STANDARD = RateLimitConfig(
        requests=100,
        window=60,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
    )

    # Strict rate limit for sensitive operations
    API_STRICT = RateLimitConfig(
        requests=10,
        window=60,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
    )

    # Very strict for login/auth
    AUTH = RateLimitConfig(
        requests=5,
        window=60,
        strategy=RateLimitStrategy.FIXED_WINDOW,
    )

    # Password reset
    PASSWORD_RESET = RateLimitConfig(
        requests=3,
        window=3600,  # 1 hour
        strategy=RateLimitStrategy.FIXED_WINDOW,
    )

    # AI generation (expensive operations)
    AI_GENERATION = RateLimitConfig(
        requests=10,
        window=3600,  # 1 hour
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        burst_size=5,
    )

    # File uploads
    UPLOAD = RateLimitConfig(
        requests=20,
        window=3600,  # 1 hour
        strategy=RateLimitStrategy.LEAKY_BUCKET,
    )

    # Webhook delivery
    WEBHOOK = RateLimitConfig(
        requests=1000,
        window=60,
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        burst_size=100,
    )

    # Search/browse operations
    SEARCH = RateLimitConfig(
        requests=60,
        window=60,
        strategy=RateLimitStrategy.SLIDING_WINDOW,
    )


# =============================================================================
# Middleware helper
# =============================================================================


async def check_rate_limit_for_request(
    identifier: str,
    config: RateLimitConfig,
) -> RateLimitResult:
    """Check rate limit for an incoming request.

    Convenience function for use in middleware.

    Args:
        identifier: Unique identifier (IP, user ID, API key)
        config: Rate limit configuration

    Returns:
        RateLimitResult
    """
    return await rate_limiter.check(identifier, config)
