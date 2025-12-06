"""Tests for caching utilities."""

from __future__ import annotations

import json
import time
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.utils.cache import (
    CacheConfig,
    CacheManager,
    CachePresets,
    CacheStats,
    SerializationFormat,
    _build_cache_key,
    cache_aside,
    cache_manager,
    cached,
    cached_sync,
)


# =============================================================================
# CacheStats Tests
# =============================================================================


class TestCacheStats:
    """Tests for CacheStats class."""

    def test_default_values(self):
        """Test default statistics values."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.errors == 0
        assert isinstance(stats.last_reset, datetime)

    def test_hit_rate_empty(self):
        """Test hit rate with no operations."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        """Test hit rate with 100% hits."""
        stats = CacheStats(hits=10, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_all_misses(self):
        """Test hit rate with 0% hits."""
        stats = CacheStats(hits=0, misses=10)
        assert stats.hit_rate == 0.0

    def test_hit_rate_mixed(self):
        """Test hit rate with mixed results."""
        stats = CacheStats(hits=7, misses=3)
        assert stats.hit_rate == 0.7

    def test_to_dict(self):
        """Test conversion to dictionary."""
        stats = CacheStats(
            hits=10,
            misses=5,
            sets=8,
            deletes=2,
            errors=1,
        )
        result = stats.to_dict()

        assert result["hits"] == 10
        assert result["misses"] == 5
        assert result["sets"] == 8
        assert result["deletes"] == 2
        assert result["errors"] == 1
        assert "hit_rate" in result
        assert "last_reset" in result

    def test_reset(self):
        """Test resetting statistics."""
        stats = CacheStats(
            hits=10,
            misses=5,
            sets=8,
            deletes=2,
            errors=1,
        )
        old_reset = stats.last_reset

        # Small delay to ensure different timestamp
        time.sleep(0.01)
        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.errors == 0
        assert stats.last_reset > old_reset


# =============================================================================
# CacheConfig Tests
# =============================================================================


class TestCacheConfig:
    """Tests for CacheConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CacheConfig()

        assert config.ttl == 300
        assert config.namespace == "default"
        assert config.serialize == SerializationFormat.JSON
        assert config.prefix == "beatsight:cache"
        assert config.skip_none is True
        assert config.track_stats is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CacheConfig(
            ttl=600,
            namespace="custom",
            serialize=SerializationFormat.PICKLE,
            skip_none=False,
        )

        assert config.ttl == 600
        assert config.namespace == "custom"
        assert config.serialize == SerializationFormat.PICKLE
        assert config.skip_none is False


# =============================================================================
# CacheManager Tests
# =============================================================================


class TestCacheManager:
    """Tests for CacheManager class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock(return_value=1)
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest.fixture
    def manager(self, mock_redis):
        """Create a configured cache manager."""
        mgr = CacheManager()
        mgr.configure(AsyncMock(return_value=mock_redis))
        return mgr

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, manager, mock_redis):
        """Test cache miss returns (False, None)."""
        mock_redis.get.return_value = None

        hit, value = await manager.get("test_key")

        assert hit is False
        assert value is None

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, manager, mock_redis):
        """Test cache hit returns (True, value)."""
        mock_redis.get.return_value = json.dumps({"foo": "bar"})

        hit, value = await manager.get("test_key")

        assert hit is True
        assert value == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_get_updates_stats_hit(self, manager, mock_redis):
        """Test cache hit increments hit counter."""
        mock_redis.get.return_value = json.dumps("value")
        config = CacheConfig(namespace="test")

        await manager.get("key", config)

        stats = manager.get_stats("test")
        assert stats["hits"] == 1
        assert stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_get_updates_stats_miss(self, manager, mock_redis):
        """Test cache miss increments miss counter."""
        mock_redis.get.return_value = None
        config = CacheConfig(namespace="test")

        await manager.get("key", config)

        stats = manager.get_stats("test")
        assert stats["hits"] == 0
        assert stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_caches_value(self, manager, mock_redis):
        """Test setting a cache value."""
        config = CacheConfig(ttl=600, namespace="test")

        result = await manager.set("key", {"data": "value"}, config)

        assert result is True
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "beatsight:cache:test:key"
        assert call_args[0][1] == 600

    @pytest.mark.asyncio
    async def test_set_skips_none(self, manager, mock_redis):
        """Test that None values are skipped by default."""
        result = await manager.set("key", None)

        assert result is False
        mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_allows_none_when_configured(self, manager, mock_redis):
        """Test that None values can be cached when skip_none=False."""
        config = CacheConfig(skip_none=False)

        result = await manager.set("key", None, config)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_key(self, manager, mock_redis):
        """Test invalidating a specific key."""
        mock_redis.delete.return_value = 1

        result = await manager.invalidate("test", "key")

        assert result is True
        mock_redis.delete.assert_called_once_with("beatsight:cache:test:key")

    @pytest.mark.asyncio
    async def test_invalidate_key_not_found(self, manager, mock_redis):
        """Test invalidating a non-existent key."""
        mock_redis.delete.return_value = 0

        result = await manager.invalidate("test", "nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_namespace(self, manager, mock_redis):
        """Test invalidating an entire namespace."""
        mock_redis.scan.return_value = (0, ["key1", "key2", "key3"])
        mock_redis.delete.return_value = 3

        count = await manager.invalidate_namespace("test")

        assert count == 3

    @pytest.mark.asyncio
    async def test_invalidate_namespace_empty(self, manager, mock_redis):
        """Test invalidating an empty namespace."""
        mock_redis.scan.return_value = (0, [])

        count = await manager.invalidate_namespace("empty")

        assert count == 0

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, manager, mock_redis):
        """Test invalidating keys by pattern."""
        mock_redis.scan.return_value = (
            0,
            ["beatsight:cache:test:a", "beatsight:cache:test:b"],
        )
        mock_redis.delete.return_value = 2

        count = await manager.invalidate_pattern("beatsight:cache:test:*")

        assert count == 2

    def test_get_stats_single_namespace(self, manager):
        """Test getting stats for a single namespace."""
        # Manually set stats
        manager._stats["test"] = CacheStats(hits=5, misses=3)

        stats = manager.get_stats("test")

        assert stats["hits"] == 5
        assert stats["misses"] == 3

    def test_get_stats_all_namespaces(self, manager):
        """Test getting stats for all namespaces."""
        manager._stats["ns1"] = CacheStats(hits=5)
        manager._stats["ns2"] = CacheStats(hits=10)

        all_stats = manager.get_stats()

        assert "ns1" in all_stats
        assert "ns2" in all_stats
        assert all_stats["ns1"]["hits"] == 5
        assert all_stats["ns2"]["hits"] == 10

    def test_reset_stats_single_namespace(self, manager):
        """Test resetting stats for a single namespace."""
        manager._stats["test"] = CacheStats(hits=10)

        manager.reset_stats("test")

        assert manager._stats["test"].hits == 0

    def test_reset_stats_all_namespaces(self, manager):
        """Test resetting stats for all namespaces."""
        manager._stats["ns1"] = CacheStats(hits=5)
        manager._stats["ns2"] = CacheStats(hits=10)

        manager.reset_stats()

        assert manager._stats["ns1"].hits == 0
        assert manager._stats["ns2"].hits == 0

    @pytest.mark.asyncio
    async def test_get_handles_redis_error(self, manager, mock_redis):
        """Test graceful handling of Redis errors on get."""
        mock_redis.get.side_effect = Exception("Redis connection failed")
        config = CacheConfig(namespace="test")

        hit, value = await manager.get("key", config)

        assert hit is False
        assert value is None
        assert manager._stats["test"].errors == 1

    @pytest.mark.asyncio
    async def test_set_handles_redis_error(self, manager, mock_redis):
        """Test graceful handling of Redis errors on set."""
        mock_redis.setex.side_effect = Exception("Redis connection failed")
        config = CacheConfig(namespace="test")

        result = await manager.set("key", "value", config)

        assert result is False
        assert manager._stats["test"].errors == 1


# =============================================================================
# Cache Key Building Tests
# =============================================================================


class TestCacheKeyBuilding:
    """Tests for cache key generation."""

    def test_simple_function(self):
        """Test key building for simple function."""

        def my_func(a: int, b: str) -> str:
            return f"{a}-{b}"

        key = _build_cache_key(my_func, (1, "test"), {})

        assert "my_func" in key
        assert "1" in key
        assert "test" in key

    def test_with_kwargs(self):
        """Test key building with keyword arguments."""

        def my_func(x: int, y: int = 10) -> int:
            return x + y

        key = _build_cache_key(my_func, (5,), {"y": 20})

        assert "5" in key
        assert "20" in key

    def test_custom_key_builder(self):
        """Test key building with custom builder."""

        def my_func(item_id: str) -> dict:
            return {}

        key = _build_cache_key(
            my_func,
            ("abc123",),
            {},
            key_builder=lambda item_id: f"custom:{item_id}",
        )

        assert key == "custom:abc123"

    def test_long_key_gets_hashed(self):
        """Test that long keys get hashed."""

        def my_func(data: str) -> str:
            return data

        long_arg = "x" * 500
        key = _build_cache_key(my_func, (long_arg,), {})

        # Should be shortened with hash
        assert len(key) < 200
        assert "my_func" in key

    def test_excludes_self_parameter(self):
        """Test that 'self' parameter is excluded from key."""

        class MyClass:
            def my_method(self, x: int) -> int:
                return x

        obj = MyClass()
        # When method is bound, self is not passed explicitly
        key = _build_cache_key(obj.my_method, (42,), {})

        assert "self" not in key
        assert "42" in key


# =============================================================================
# @cached Decorator Tests
# =============================================================================


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture(autouse=True)
    def setup_cache_manager(self, mock_redis):
        """Configure cache manager with mock Redis."""
        cache_manager.configure(AsyncMock(return_value=mock_redis))
        cache_manager._stats.clear()
        yield

    @pytest.mark.asyncio
    async def test_caches_result(self, mock_redis):
        """Test that function result is cached."""
        call_count = 0

        @cached(namespace="test", ttl=60)
        async def my_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - cache miss
        result1 = await my_func(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - should use cache (but mock returns None, so it calls again)
        # In real scenario, Redis would return cached value
        mock_redis.get.return_value = json.dumps(10)
        result2 = await my_func(5)
        assert result2 == 10

    @pytest.mark.asyncio
    async def test_different_args_different_cache_keys(self, mock_redis):
        """Test that different arguments create different cache keys."""

        @cached(namespace="test")
        async def my_func(x: int) -> int:
            return x * 2

        await my_func(1)
        await my_func(2)

        # Should have called setex twice with different keys
        assert mock_redis.setex.call_count == 2
        calls = mock_redis.setex.call_args_list
        assert calls[0][0][0] != calls[1][0][0]

    @pytest.mark.asyncio
    async def test_custom_key_builder(self, mock_redis):
        """Test decorator with custom key builder."""

        @cached(namespace="test", key_builder=lambda x: f"num:{x}")
        async def my_func(x: int) -> int:
            return x * 2

        await my_func(42)

        call_args = mock_redis.setex.call_args
        assert "num:42" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_invalidate_method(self, mock_redis):
        """Test the invalidate method on cached function."""
        mock_redis.delete = AsyncMock(return_value=1)

        @cached(namespace="test")
        async def my_func(x: int) -> int:
            return x * 2

        result = await my_func.invalidate(5)

        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_namespace_attribute(self, mock_redis):
        """Test that cached function has namespace attribute."""

        @cached(namespace="my_namespace")
        async def my_func() -> str:
            return "test"

        assert my_func.cache_namespace == "my_namespace"


# =============================================================================
# @cached_sync Decorator Tests
# =============================================================================


class TestCachedSyncDecorator:
    """Tests for @cached_sync decorator."""

    def test_caches_result(self):
        """Test that sync function result is cached."""
        call_count = 0

        @cached_sync(ttl=60)
        def my_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = my_func(5)
        assert result1 == 10
        assert call_count == 1

        result2 = my_func(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

    def test_different_args_not_cached(self):
        """Test that different arguments bypass cache."""
        call_count = 0

        @cached_sync(ttl=60)
        def my_func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        my_func(1)
        my_func(2)

        assert call_count == 2

    def test_ttl_expiration(self):
        """Test that cached values expire."""
        call_count = 0

        @cached_sync(ttl=0.05)  # 50ms TTL
        def my_func() -> int:
            nonlocal call_count
            call_count += 1
            return 42

        my_func()
        assert call_count == 1

        time.sleep(0.1)  # Wait for expiration
        my_func()
        assert call_count == 2

    def test_clear_cache_method(self):
        """Test clear_cache method."""

        @cached_sync()
        def my_func(x: int) -> int:
            return x * 2

        my_func(1)
        my_func(2)

        assert my_func.cache_size() == 2

        my_func.clear_cache()

        assert my_func.cache_size() == 0

    def test_skip_none_by_default(self):
        """Test that None values are not cached by default."""
        call_count = 0

        @cached_sync()
        def my_func() -> None:
            nonlocal call_count
            call_count += 1
            return None

        my_func()
        my_func()

        assert call_count == 2  # Called twice because None wasn't cached

    def test_cache_none_when_configured(self):
        """Test caching None when skip_none=False."""
        call_count = 0

        @cached_sync(skip_none=False)
        def my_func() -> None:
            nonlocal call_count
            call_count += 1
            return None

        my_func()
        my_func()

        assert call_count == 1  # Only called once


# =============================================================================
# cache_aside Function Tests
# =============================================================================


class TestCacheAside:
    """Tests for cache_aside function."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture(autouse=True)
    def setup_cache_manager(self, mock_redis):
        """Configure cache manager with mock Redis."""
        cache_manager.configure(AsyncMock(return_value=mock_redis))
        yield

    @pytest.mark.asyncio
    async def test_fetches_on_miss(self, mock_redis):
        """Test that fetcher is called on cache miss."""
        fetch_count = 0

        async def fetcher() -> str:
            nonlocal fetch_count
            fetch_count += 1
            return "data"

        result = await cache_aside("key", fetcher)

        assert result == "data"
        assert fetch_count == 1
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_cached_on_hit(self, mock_redis):
        """Test that cached value is returned on hit."""
        mock_redis.get.return_value = json.dumps("cached_data")
        fetch_count = 0

        async def fetcher() -> str:
            nonlocal fetch_count
            fetch_count += 1
            return "fresh_data"

        result = await cache_aside("key", fetcher)

        assert result == "cached_data"
        assert fetch_count == 0
        mock_redis.setex.assert_not_called()


# =============================================================================
# CachePresets Tests
# =============================================================================


class TestCachePresets:
    """Tests for predefined cache configurations."""

    def test_short_preset(self):
        """Test SHORT preset values."""
        assert CachePresets.SHORT.ttl == 60
        assert CachePresets.SHORT.namespace == "short"

    def test_standard_preset(self):
        """Test STANDARD preset values."""
        assert CachePresets.STANDARD.ttl == 300
        assert CachePresets.STANDARD.namespace == "standard"

    def test_long_preset(self):
        """Test LONG preset values."""
        assert CachePresets.LONG.ttl == 3600
        assert CachePresets.LONG.namespace == "long"

    def test_static_preset(self):
        """Test STATIC preset values."""
        assert CachePresets.STATIC.ttl == 86400
        assert CachePresets.STATIC.namespace == "static"

    def test_user_preset(self):
        """Test USER preset values."""
        assert CachePresets.USER.namespace == "users"

    def test_songs_preset(self):
        """Test SONGS preset values."""
        assert CachePresets.SONGS.namespace == "songs"

    def test_api_preset(self):
        """Test API preset values."""
        assert CachePresets.API.namespace == "api"

    def test_search_preset(self):
        """Test SEARCH preset values."""
        assert CachePresets.SEARCH.namespace == "search"


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for cache value serialization."""

    @pytest.fixture
    def manager(self):
        """Create a cache manager."""
        return CacheManager()

    def test_json_serialize_dict(self, manager):
        """Test JSON serialization of dict."""
        data = {"name": "test", "value": 123}
        serialized = manager._serialize(data, SerializationFormat.JSON)

        assert isinstance(serialized, str)
        assert json.loads(serialized) == data

    def test_json_serialize_list(self, manager):
        """Test JSON serialization of list."""
        data = [1, 2, 3, "four"]
        serialized = manager._serialize(data, SerializationFormat.JSON)

        assert json.loads(serialized) == data

    def test_json_deserialize(self, manager):
        """Test JSON deserialization."""
        serialized = '{"key": "value"}'
        result = manager._deserialize(serialized, SerializationFormat.JSON)

        assert result == {"key": "value"}

    def test_pickle_serialize_complex_object(self, manager):
        """Test PICKLE serialization of complex object."""
        data = {"set": {1, 2, 3}, "tuple": (1, 2)}
        serialized = manager._serialize(data, SerializationFormat.PICKLE)

        assert isinstance(serialized, bytes)

    def test_pickle_deserialize(self, manager):
        """Test PICKLE deserialization."""
        import pickle

        data = {"complex": object}
        serialized = pickle.dumps(data)

        result = manager._deserialize(serialized, SerializationFormat.PICKLE)

        assert result == data


# =============================================================================
# Integration Tests
# =============================================================================


class TestCacheIntegration:
    """Integration tests for caching system."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis with realistic behavior."""
        storage = {}

        async def mock_get(key):
            return storage.get(key)

        async def mock_setex(key, ttl, value):
            storage[key] = value

        async def mock_delete(*keys):
            count = 0
            for key in keys:
                if key in storage:
                    del storage[key]
                    count += 1
            return count

        redis = AsyncMock()
        redis.get = AsyncMock(side_effect=mock_get)
        redis.setex = AsyncMock(side_effect=mock_setex)
        redis.delete = AsyncMock(side_effect=mock_delete)
        redis._storage = storage

        return redis

    @pytest.fixture(autouse=True)
    def setup_cache_manager(self, mock_redis):
        """Configure cache manager."""
        cache_manager.configure(AsyncMock(return_value=mock_redis))
        cache_manager._stats.clear()
        yield

    @pytest.mark.asyncio
    async def test_full_cache_cycle(self, mock_redis):
        """Test complete cache workflow."""
        call_count = 0

        @cached(namespace="integration", ttl=300)
        async def get_user_data(user_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": f"User {user_id}"}

        # First call - cache miss
        result1 = await get_user_data("123")
        assert result1 == {"id": "123", "name": "User 123"}
        assert call_count == 1

        # Second call - cache hit
        result2 = await get_user_data("123")
        assert result2 == {"id": "123", "name": "User 123"}
        assert call_count == 1  # Not called again

        # Different argument - cache miss
        result3 = await get_user_data("456")
        assert result3 == {"id": "456", "name": "User 456"}
        assert call_count == 2

        # Invalidate
        await get_user_data.invalidate("123")

        # After invalidation - cache miss
        await get_user_data("123")
        assert call_count == 3
