"""Caching utilities with Redis backend.

Provides decorators and utilities for caching function results:
- @cached decorator for async functions
- @cached_sync decorator for sync functions
- Cache invalidation patterns
- TTL management with namespace support
- Cache statistics tracking

Usage:
    from app.utils.cache import cached, cache_manager

    # Simple caching with default TTL
    @cached(namespace="songs")
    async def get_song(song_id: str) -> Song:
        return await db.fetch_song(song_id)
    
    # With custom TTL and key builder
    @cached(namespace="users", ttl=300, key_builder=lambda u: f"user:{u.id}")
    async def get_user_profile(user_id: str) -> Profile:
        ...
    
    # Invalidate specific keys
    await cache_manager.invalidate("songs", "song:123")
    
    # Invalidate entire namespace
    await cache_manager.invalidate_namespace("songs")
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import pickle
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ParamSpec, TypeVar

import structlog

logger = structlog.get_logger(__name__)

# Type variables for generic decorators
P = ParamSpec("P")
T = TypeVar("T")


class SerializationFormat(str, Enum):
    """Serialization formats for cached values."""
    
    JSON = "json"
    PICKLE = "pickle"


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    
    ttl: int = 300  # Default 5 minutes
    namespace: str = "default"
    serialize: SerializationFormat = SerializationFormat.JSON
    prefix: str = "beatsight:cache"
    # Skip caching if value is None
    skip_none: bool = True
    # Stats tracking
    track_stats: bool = True
    # Compression threshold (bytes) - compress if larger
    compress_threshold: int = 1024
    

@dataclass
class CacheStats:
    """Statistics for cache operations."""
    
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": round(self.hit_rate, 4),
            "last_reset": self.last_reset.isoformat(),
        }
    
    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.last_reset = datetime.now(timezone.utc)


class CacheManager:
    """Centralized cache management with Redis backend.
    
    Provides methods for:
    - Getting/setting cached values
    - Invalidating cache keys and namespaces
    - Tracking cache statistics
    - Managing cache health
    """
    
    def __init__(self) -> None:
        self._stats: dict[str, CacheStats] = {}
        self._redis_getter: Callable[[], Awaitable[Any]] | None = None
        
    def configure(self, redis_getter: Callable[[], Awaitable[Any]]) -> None:
        """Configure the cache manager with a Redis client getter.
        
        Args:
            redis_getter: Async function that returns a Redis client
        """
        self._redis_getter = redis_getter
        
    async def _get_redis(self) -> Any:
        """Get Redis client, raising if not configured."""
        if self._redis_getter is None:
            # Try to import and use default
            try:
                from app.db.redis import get_redis
                self._redis_getter = get_redis
            except ImportError:
                raise RuntimeError(
                    "Cache manager not configured. "
                    "Call cache_manager.configure(redis_getter) first."
                )
        return await self._redis_getter()
    
    def _get_stats(self, namespace: str) -> CacheStats:
        """Get or create stats for a namespace."""
        if namespace not in self._stats:
            self._stats[namespace] = CacheStats()
        return self._stats[namespace]
    
    def _build_key(self, config: CacheConfig, key: str) -> str:
        """Build full Redis key from namespace and key."""
        return f"{config.prefix}:{config.namespace}:{key}"
    
    def _serialize(self, value: Any, format: SerializationFormat) -> str | bytes:
        """Serialize a value for storage."""
        if format == SerializationFormat.JSON:
            return json.dumps(value, default=str)
        else:  # PICKLE
            return pickle.dumps(value)
    
    def _deserialize(self, data: str | bytes, format: SerializationFormat) -> Any:
        """Deserialize a stored value."""
        if format == SerializationFormat.JSON:
            return json.loads(data)
        else:  # PICKLE
            return pickle.loads(data if isinstance(data, bytes) else data.encode())
    
    async def get(
        self,
        key: str,
        config: CacheConfig | None = None,
    ) -> tuple[bool, Any]:
        """Get a value from cache.
        
        Args:
            key: Cache key
            config: Cache configuration
            
        Returns:
            Tuple of (hit, value) where hit is True if found
        """
        config = config or CacheConfig()
        stats = self._get_stats(config.namespace)
        full_key = self._build_key(config, key)
        
        try:
            redis = await self._get_redis()
            raw = await redis.get(full_key)
            
            if raw is None:
                stats.misses += 1
                return False, None
            
            stats.hits += 1
            value = self._deserialize(raw, config.serialize)
            return True, value
            
        except Exception as e:
            stats.errors += 1
            logger.warning(
                "Cache get error",
                key=full_key,
                error=str(e),
            )
            return False, None
    
    async def set(
        self,
        key: str,
        value: Any,
        config: CacheConfig | None = None,
    ) -> bool:
        """Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            config: Cache configuration
            
        Returns:
            True if successfully cached
        """
        config = config or CacheConfig()
        stats = self._get_stats(config.namespace)
        full_key = self._build_key(config, key)
        
        # Skip None values if configured
        if value is None and config.skip_none:
            return False
        
        try:
            redis = await self._get_redis()
            serialized = self._serialize(value, config.serialize)
            
            await redis.setex(
                full_key,
                config.ttl,
                serialized,
            )
            stats.sets += 1
            return True
            
        except Exception as e:
            stats.errors += 1
            logger.warning(
                "Cache set error",
                key=full_key,
                error=str(e),
            )
            return False
    
    async def invalidate(self, namespace: str, key: str) -> bool:
        """Invalidate a specific cache key.
        
        Args:
            namespace: Cache namespace
            key: Cache key
            
        Returns:
            True if key was deleted
        """
        config = CacheConfig(namespace=namespace)
        stats = self._get_stats(namespace)
        full_key = self._build_key(config, key)
        
        try:
            redis = await self._get_redis()
            deleted = await redis.delete(full_key)
            stats.deletes += deleted
            return deleted > 0
            
        except Exception as e:
            stats.errors += 1
            logger.warning(
                "Cache invalidate error",
                key=full_key,
                error=str(e),
            )
            return False
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys in a namespace.
        
        WARNING: Uses SCAN which can be slow on large datasets.
        
        Args:
            namespace: Cache namespace to clear
            
        Returns:
            Number of keys deleted
        """
        stats = self._get_stats(namespace)
        pattern = f"beatsight:cache:{namespace}:*"
        deleted_count = 0
        
        try:
            redis = await self._get_redis()
            
            # Use SCAN to find matching keys
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                
                if keys:
                    deleted = await redis.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            stats.deletes += deleted_count
            logger.info(
                "Namespace invalidated",
                namespace=namespace,
                deleted_count=deleted_count,
            )
            return deleted_count
            
        except Exception as e:
            stats.errors += 1
            logger.warning(
                "Cache namespace invalidate error",
                namespace=namespace,
                error=str(e),
            )
            return 0
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern.
        
        WARNING: Uses SCAN which can be slow on large datasets.
        
        Args:
            pattern: Redis pattern (e.g., "beatsight:cache:songs:user_*")
            
        Returns:
            Number of keys deleted
        """
        deleted_count = 0
        
        try:
            redis = await self._get_redis()
            
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                
                if keys:
                    deleted = await redis.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            logger.info(
                "Pattern invalidated",
                pattern=pattern,
                deleted_count=deleted_count,
            )
            return deleted_count
            
        except Exception as e:
            logger.warning(
                "Cache pattern invalidate error",
                pattern=pattern,
                error=str(e),
            )
            return 0
    
    def get_stats(self, namespace: str | None = None) -> dict[str, Any]:
        """Get cache statistics.
        
        Args:
            namespace: Specific namespace or None for all
            
        Returns:
            Statistics dictionary
        """
        if namespace:
            return self._get_stats(namespace).to_dict()
        
        return {
            ns: stats.to_dict()
            for ns, stats in self._stats.items()
        }
    
    def reset_stats(self, namespace: str | None = None) -> None:
        """Reset cache statistics.
        
        Args:
            namespace: Specific namespace or None for all
        """
        if namespace:
            if namespace in self._stats:
                self._stats[namespace].reset()
        else:
            for stats in self._stats.values():
                stats.reset()


# Global cache manager instance
cache_manager = CacheManager()


def _build_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_builder: Callable[..., str] | None = None,
) -> str:
    """Build a cache key from function arguments.
    
    Args:
        func: The decorated function
        args: Positional arguments
        kwargs: Keyword arguments
        key_builder: Optional custom key builder
        
    Returns:
        A string cache key
    """
    if key_builder:
        return key_builder(*args, **kwargs)
    
    # Get function signature for parameter names
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    
    # Build key from sorted arguments
    key_parts = [func.__module__, func.__name__]
    
    for name, value in sorted(bound.arguments.items()):
        # Skip 'self' and 'cls' parameters
        if name in ("self", "cls"):
            continue
        
        # Convert value to string representation
        if hasattr(value, "__dict__"):
            # For objects, use their dict or id
            try:
                value_str = json.dumps(value.__dict__, sort_keys=True, default=str)
            except (TypeError, ValueError):
                value_str = str(id(value))
        else:
            try:
                value_str = json.dumps(value, sort_keys=True, default=str)
            except (TypeError, ValueError):
                value_str = str(value)
        
        key_parts.append(f"{name}={value_str}")
    
    # Create hash for long keys
    key_string = ":".join(key_parts)
    if len(key_string) > 200:
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:32]
        return f"{func.__name__}:{key_hash}"
    
    return key_string


def cached(
    namespace: str = "default",
    ttl: int = 300,
    key_builder: Callable[..., str] | None = None,
    serialize: SerializationFormat = SerializationFormat.JSON,
    skip_none: bool = True,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to cache async function results.
    
    Args:
        namespace: Cache namespace for grouping related keys
        ttl: Time-to-live in seconds
        key_builder: Optional function to build cache key from args
        serialize: Serialization format (JSON or PICKLE)
        skip_none: Whether to skip caching None results
        
    Returns:
        Decorated function
        
    Example:
        @cached(namespace="songs", ttl=600)
        async def get_song(song_id: str) -> Song:
            return await db.fetch_song(song_id)
    """
    config = CacheConfig(
        namespace=namespace,
        ttl=ttl,
        serialize=serialize,
        skip_none=skip_none,
    )
    
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build cache key
            cache_key = _build_cache_key(func, args, kwargs, key_builder)
            
            # Try to get from cache
            hit, cached_value = await cache_manager.get(cache_key, config)
            if hit:
                logger.debug(
                    "Cache hit",
                    namespace=namespace,
                    key=cache_key,
                )
                return cached_value
            
            # Cache miss - call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_manager.set(cache_key, result, config)
            logger.debug(
                "Cache miss - stored",
                namespace=namespace,
                key=cache_key,
                ttl=ttl,
            )
            
            return result
        
        # Add cache control methods to the wrapped function
        async def invalidate(*args: Any, **kwargs: Any) -> bool:
            """Invalidate cache for specific arguments."""
            cache_key = _build_cache_key(func, args, kwargs, key_builder)
            return await cache_manager.invalidate(namespace, cache_key)
        
        wrapper.invalidate = invalidate  # type: ignore
        wrapper.cache_namespace = namespace  # type: ignore
        
        return wrapper
    
    return decorator


def cached_sync(
    namespace: str = "default",
    ttl: int = 300,
    key_builder: Callable[..., str] | None = None,
    serialize: SerializationFormat = SerializationFormat.JSON,
    skip_none: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to cache sync function results (uses in-memory cache).
    
    NOTE: This uses a simple in-memory dict cache, not Redis.
    For sync functions that need Redis, make them async.
    
    Args:
        namespace: Cache namespace (for organization)
        ttl: Time-to-live in seconds
        key_builder: Optional function to build cache key from args
        serialize: Ignored for sync cache
        skip_none: Whether to skip caching None results
        
    Returns:
        Decorated function
    """
    # In-memory cache with TTL
    cache: dict[str, tuple[float, Any]] = {}
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Build cache key
            cache_key = _build_cache_key(func, args, kwargs, key_builder)
            
            # Check cache
            if cache_key in cache:
                expires_at, value = cache[cache_key]
                if time.time() < expires_at:
                    return value
                else:
                    del cache[cache_key]
            
            # Call function
            result = func(*args, **kwargs)
            
            # Store in cache
            if result is not None or not skip_none:
                cache[cache_key] = (time.time() + ttl, result)
            
            return result
        
        def clear_cache() -> None:
            """Clear all cached values."""
            cache.clear()
        
        def cache_size() -> int:
            """Get number of cached items."""
            return len(cache)
        
        wrapper.clear_cache = clear_cache  # type: ignore
        wrapper.cache_size = cache_size  # type: ignore
        
        return wrapper
    
    return decorator


# =============================================================================
# Utility functions for common patterns
# =============================================================================

async def cache_aside(
    key: str,
    fetcher: Callable[[], Awaitable[T]],
    namespace: str = "default",
    ttl: int = 300,
) -> T:
    """Cache-aside pattern for manual cache management.
    
    Checks cache first, falls back to fetcher function on miss.
    
    Args:
        key: Cache key
        fetcher: Async function to fetch data on cache miss
        namespace: Cache namespace
        ttl: Time-to-live in seconds
        
    Returns:
        Cached or freshly fetched value
        
    Example:
        async def get_user_data(user_id: str) -> UserData:
            return await cache_aside(
                key=f"user:{user_id}",
                fetcher=lambda: db.fetch_user(user_id),
                namespace="users",
                ttl=600,
            )
    """
    config = CacheConfig(namespace=namespace, ttl=ttl)
    
    # Try cache
    hit, value = await cache_manager.get(key, config)
    if hit:
        return value
    
    # Fetch and cache
    result = await fetcher()
    await cache_manager.set(key, result, config)
    
    return result


async def cached_get_or_set(
    key: str,
    default_factory: Callable[[], Awaitable[T]],
    namespace: str = "default",
    ttl: int = 300,
) -> T:
    """Get a cached value or set it using the factory.
    
    Alias for cache_aside with clearer naming.
    """
    return await cache_aside(key, default_factory, namespace, ttl)


# =============================================================================
# Predefined cache configurations
# =============================================================================

class CachePresets:
    """Predefined cache configurations for common use cases."""
    
    # Short-lived caches
    SHORT = CacheConfig(ttl=60, namespace="short")  # 1 minute
    
    # Standard caches
    STANDARD = CacheConfig(ttl=300, namespace="standard")  # 5 minutes
    
    # Long-lived caches
    LONG = CacheConfig(ttl=3600, namespace="long")  # 1 hour
    
    # Very long caches (static-ish data)
    STATIC = CacheConfig(ttl=86400, namespace="static")  # 24 hours
    
    # User-specific caches
    USER = CacheConfig(ttl=300, namespace="users")
    
    # Song/music data
    SONGS = CacheConfig(ttl=600, namespace="songs")
    
    # API response caches
    API = CacheConfig(ttl=60, namespace="api")
    
    # Search results
    SEARCH = CacheConfig(ttl=120, namespace="search")
