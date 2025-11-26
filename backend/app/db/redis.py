"""Redis connection management and job queue utilities.

Provides async Redis client for:
- Job queue operations (AI generation jobs)
- Caching
- Pub/sub for real-time progress updates
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()

# Global Redis client (initialized on first use)
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection gracefully."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


@asynccontextmanager
async def redis_connection() -> AsyncIterator[Redis]:
    """Context manager for Redis operations."""
    client = await get_redis()
    try:
        yield client
    finally:
        pass  # Connection pooling handles cleanup


# =============================================================================
# Key Prefixes (namespaced to avoid collisions)
# =============================================================================
class RedisKeys:
    """Centralized Redis key management."""

    # Job queues (sorted sets by priority/timestamp)
    JOB_QUEUE = "beatsight:jobs:queue"
    JOB_PROCESSING = "beatsight:jobs:processing"
    JOB_COMPLETED = "beatsight:jobs:completed"
    JOB_FAILED = "beatsight:jobs:failed"

    # Job data (hash per job)
    @staticmethod
    def job_data(job_id: uuid.UUID) -> str:
        return f"beatsight:jobs:data:{job_id}"

    # Progress channels (pub/sub)
    @staticmethod
    def job_progress_channel(job_id: uuid.UUID) -> str:
        return f"beatsight:jobs:progress:{job_id}"

    # User quota tracking
    @staticmethod
    def user_quota(user_id: uuid.UUID, period: str) -> str:
        return f"beatsight:quota:{user_id}:{period}"

    # Rate limiting
    @staticmethod
    def rate_limit(user_id: uuid.UUID | None, endpoint: str) -> str:
        user_part = str(user_id) if user_id else "anon"
        return f"beatsight:ratelimit:{user_part}:{endpoint}"

    # Caching
    @staticmethod
    def cache(namespace: str, key: str) -> str:
        return f"beatsight:cache:{namespace}:{key}"


# =============================================================================
# Job Queue Operations
# =============================================================================
@dataclass
class QueuedJob:
    """Represents a job in the Redis queue."""

    job_id: uuid.UUID
    song_id: uuid.UUID
    user_id: uuid.UUID | None
    priority: int  # Higher = more urgent
    enqueued_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": str(self.job_id),
            "song_id": str(self.song_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "priority": self.priority,
            "enqueued_at": self.enqueued_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedJob":
        return cls(
            job_id=uuid.UUID(data["job_id"]),
            song_id=uuid.UUID(data["song_id"]),
            user_id=uuid.UUID(data["user_id"]) if data.get("user_id") else None,
            priority=data["priority"],
            enqueued_at=datetime.fromisoformat(data["enqueued_at"]),
        )


class JobQueue:
    """Redis-backed job queue with priority support."""

    def __init__(self, client: Redis):
        self._client = client

    async def enqueue(self, job: QueuedJob) -> None:
        """Add a job to the queue with priority scoring.

        Score formula: -priority * 1e12 + timestamp
        This ensures higher priority jobs come first, with FIFO within same priority.
        """
        score = -job.priority * 1_000_000_000_000 + job.enqueued_at.timestamp()

        async with self._client.pipeline() as pipe:
            # Store job data
            await pipe.hset(
                RedisKeys.job_data(job.job_id),
                mapping={
                    k: json.dumps(v) if not isinstance(v, str) else v
                    for k, v in job.to_dict().items()
                },
            )
            # Add to sorted set queue
            await pipe.zadd(RedisKeys.JOB_QUEUE, {str(job.job_id): score})
            await pipe.execute()

    async def dequeue(self) -> QueuedJob | None:
        """Pop the highest priority job from the queue.

        Uses ZPOPMIN for atomic dequeue. Moves job to processing set.
        """
        # Atomically pop from queue
        result = await self._client.zpopmin(RedisKeys.JOB_QUEUE, count=1)
        if not result:
            return None

        job_id_str, _score = result[0]
        job_id = uuid.UUID(job_id_str)

        # Get job data
        data = await self._client.hgetall(RedisKeys.job_data(job_id))
        if not data:
            return None

        # Parse stored JSON values
        parsed = {}
        for k, v in data.items():
            try:
                parsed[k] = json.loads(v)
            except json.JSONDecodeError:
                parsed[k] = v

        # Move to processing set
        await self._client.sadd(RedisKeys.JOB_PROCESSING, job_id_str)

        return QueuedJob.from_dict(parsed)

    async def mark_complete(self, job_id: uuid.UUID) -> None:
        """Move job from processing to completed."""
        job_id_str = str(job_id)
        async with self._client.pipeline() as pipe:
            await pipe.srem(RedisKeys.JOB_PROCESSING, job_id_str)
            await pipe.sadd(RedisKeys.JOB_COMPLETED, job_id_str)
            # Keep completed jobs for 24 hours
            await pipe.expire(RedisKeys.job_data(job_id), 86400)
            await pipe.execute()

    async def mark_failed(self, job_id: uuid.UUID, error: str | None = None) -> None:
        """Move job from processing to failed."""
        job_id_str = str(job_id)
        async with self._client.pipeline() as pipe:
            await pipe.srem(RedisKeys.JOB_PROCESSING, job_id_str)
            await pipe.sadd(RedisKeys.JOB_FAILED, job_id_str)
            if error:
                await pipe.hset(RedisKeys.job_data(job_id), "error", error)
            # Keep failed jobs for 7 days for debugging
            await pipe.expire(RedisKeys.job_data(job_id), 604800)
            await pipe.execute()

    async def requeue(self, job_id: uuid.UUID) -> bool:
        """Move a failed/processing job back to the queue for retry."""
        job_id_str = str(job_id)

        # Get job data
        data = await self._client.hgetall(RedisKeys.job_data(job_id))
        if not data:
            return False

        # Remove from processing/failed
        await self._client.srem(RedisKeys.JOB_PROCESSING, job_id_str)
        await self._client.srem(RedisKeys.JOB_FAILED, job_id_str)

        # Re-add to queue with current timestamp
        now = datetime.now(timezone.utc)
        priority = int(data.get("priority", 0))
        score = -priority * 1_000_000_000_000 + now.timestamp()
        await self._client.zadd(RedisKeys.JOB_QUEUE, {job_id_str: score})

        return True

    async def get_queue_position(self, job_id: uuid.UUID) -> int | None:
        """Get 0-based position of a job in the queue (None if not queued)."""
        rank = await self._client.zrank(RedisKeys.JOB_QUEUE, str(job_id))
        return rank

    async def get_queue_length(self) -> int:
        """Get total number of jobs in queue."""
        return await self._client.zcard(RedisKeys.JOB_QUEUE)

    async def get_processing_count(self) -> int:
        """Get number of jobs currently being processed."""
        return await self._client.scard(RedisKeys.JOB_PROCESSING)


# =============================================================================
# Progress Pub/Sub
# =============================================================================
@dataclass
class ProgressUpdate:
    """Progress update message for pub/sub."""

    job_id: uuid.UUID
    percent: int
    message: str | None
    stage: str | None
    timestamp: datetime

    def to_json(self) -> str:
        return json.dumps(
            {
                "job_id": str(self.job_id),
                "percent": self.percent,
                "message": self.message,
                "stage": self.stage,
                "timestamp": self.timestamp.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "ProgressUpdate":
        parsed = json.loads(data)
        return cls(
            job_id=uuid.UUID(parsed["job_id"]),
            percent=parsed["percent"],
            message=parsed.get("message"),
            stage=parsed.get("stage"),
            timestamp=datetime.fromisoformat(parsed["timestamp"]),
        )


async def publish_progress(client: Redis, update: ProgressUpdate) -> None:
    """Publish a progress update to subscribers."""
    channel = RedisKeys.job_progress_channel(update.job_id)
    await client.publish(channel, update.to_json())


async def subscribe_progress(client: Redis, job_id: uuid.UUID):
    """Subscribe to progress updates for a job. Yields ProgressUpdate objects."""
    pubsub = client.pubsub()
    channel = RedisKeys.job_progress_channel(job_id)
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield ProgressUpdate.from_json(message["data"])
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


# =============================================================================
# Quota Tracking
# =============================================================================
async def get_quota_usage(client: Redis, user_id: uuid.UUID, period: str) -> int:
    """Get current quota usage for a user in a period (e.g., '2025-11')."""
    key = RedisKeys.user_quota(user_id, period)
    value = await client.get(key)
    return int(value) if value else 0


async def increment_quota_usage(
    client: Redis,
    user_id: uuid.UUID,
    period: str,
    amount: int = 1,
    ttl_seconds: int = 2678400,  # ~31 days
) -> int:
    """Increment quota usage and return new total."""
    key = RedisKeys.user_quota(user_id, period)
    new_value = await client.incrby(key, amount)
    await client.expire(key, ttl_seconds)
    return new_value


# =============================================================================
# Caching Utilities
# =============================================================================
async def cache_get(client: Redis, namespace: str, key: str) -> Any | None:
    """Get a cached value."""
    redis_key = RedisKeys.cache(namespace, key)
    value = await client.get(redis_key)
    if value:
        return json.loads(value)
    return None


async def cache_set(
    client: Redis, namespace: str, key: str, value: Any, ttl: int | None = None
) -> None:
    """Set a cached value with optional TTL."""
    redis_key = RedisKeys.cache(namespace, key)
    await client.set(redis_key, json.dumps(value), ex=ttl or settings.cache_default_ttl)


async def cache_delete(client: Redis, namespace: str, key: str) -> None:
    """Delete a cached value."""
    redis_key = RedisKeys.cache(namespace, key)
    await client.delete(redis_key)
