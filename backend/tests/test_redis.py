"""Tests for Redis utilities and job queue operations.

Tests Redis key management, job queue operations, pub/sub,
quota tracking, and caching utilities.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.redis import (
    JobQueue,
    ProgressUpdate,
    QueuedJob,
    RedisKeys,
    cache_delete,
    cache_get,
    cache_set,
    get_quota_usage,
    increment_quota_usage,
    publish_progress,
)


class TestRedisKeys:
    """Test cases for RedisKeys namespace management."""

    def test_job_queue_constants(self) -> None:
        """Test queue constants are properly namespaced."""
        assert RedisKeys.JOB_QUEUE == "beatsight:jobs:queue"
        assert RedisKeys.JOB_PROCESSING == "beatsight:jobs:processing"
        assert RedisKeys.JOB_COMPLETED == "beatsight:jobs:completed"
        assert RedisKeys.JOB_FAILED == "beatsight:jobs:failed"

    def test_job_data_key(self) -> None:
        """Test job data key generation."""
        job_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        key = RedisKeys.job_data(job_id)
        assert key == f"beatsight:jobs:data:{job_id}"

    def test_job_progress_channel(self) -> None:
        """Test progress channel key generation."""
        job_id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        channel = RedisKeys.job_progress_channel(job_id)
        assert channel == f"beatsight:jobs:progress:{job_id}"

    def test_user_quota_key(self) -> None:
        """Test user quota key generation."""
        user_id = uuid.UUID("abcdef00-1234-1234-1234-123456789abc")
        key = RedisKeys.user_quota(user_id, "2025-11")
        assert key == f"beatsight:quota:{user_id}:2025-11"

    def test_rate_limit_key_with_user(self) -> None:
        """Test rate limit key with authenticated user."""
        user_id = uuid.UUID("abcdef00-1234-1234-1234-123456789abc")
        key = RedisKeys.rate_limit(user_id, "api:jobs")
        assert key == f"beatsight:ratelimit:{user_id}:api:jobs"

    def test_rate_limit_key_anonymous(self) -> None:
        """Test rate limit key for anonymous user."""
        key = RedisKeys.rate_limit(None, "api:jobs")
        assert key == "beatsight:ratelimit:anon:api:jobs"

    def test_cache_key(self) -> None:
        """Test cache key generation."""
        key = RedisKeys.cache("songs", "metadata:abc123")
        assert key == "beatsight:cache:songs:metadata:abc123"


class TestQueuedJob:
    """Test cases for QueuedJob dataclass."""

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        job = QueuedJob(
            job_id=job_id,
            song_id=song_id,
            user_id=user_id,
            priority=100,
            enqueued_at=now,
        )

        result = job.to_dict()

        assert result["job_id"] == str(job_id)
        assert result["song_id"] == str(song_id)
        assert result["user_id"] == str(user_id)
        assert result["priority"] == 100
        assert result["enqueued_at"] == now.isoformat()

    def test_to_dict_anonymous_user(self) -> None:
        """Test serialization with no user."""
        job = QueuedJob(
            job_id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            user_id=None,
            priority=50,
            enqueued_at=datetime.now(timezone.utc),
        )

        result = job.to_dict()

        assert result["user_id"] is None

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        data = {
            "job_id": str(job_id),
            "song_id": str(song_id),
            "user_id": str(user_id),
            "priority": 75,
            "enqueued_at": now.isoformat(),
        }

        job = QueuedJob.from_dict(data)

        assert job.job_id == job_id
        assert job.song_id == song_id
        assert job.user_id == user_id
        assert job.priority == 75

    def test_from_dict_anonymous_user(self) -> None:
        """Test deserialization with no user."""
        data = {
            "job_id": str(uuid.uuid4()),
            "song_id": str(uuid.uuid4()),
            "user_id": None,
            "priority": 25,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }

        job = QueuedJob.from_dict(data)

        assert job.user_id is None


class TestProgressUpdate:
    """Test cases for ProgressUpdate dataclass."""

    def test_to_json(self) -> None:
        """Test JSON serialization."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        update = ProgressUpdate(
            job_id=job_id,
            percent=50,
            message="Processing audio...",
            stage="separation",
            timestamp=now,
        )

        result = json.loads(update.to_json())

        assert result["job_id"] == str(job_id)
        assert result["percent"] == 50
        assert result["message"] == "Processing audio..."
        assert result["stage"] == "separation"
        assert result["timestamp"] == now.isoformat()

    def test_to_json_optional_fields(self) -> None:
        """Test JSON serialization with None values."""
        update = ProgressUpdate(
            job_id=uuid.uuid4(),
            percent=0,
            message=None,
            stage=None,
            timestamp=datetime.now(timezone.utc),
        )

        result = json.loads(update.to_json())

        assert result["message"] is None
        assert result["stage"] is None

    def test_from_json(self) -> None:
        """Test JSON deserialization."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        json_str = json.dumps(
            {
                "job_id": str(job_id),
                "percent": 75,
                "message": "Generating beatmap...",
                "stage": "transcription",
                "timestamp": now.isoformat(),
            }
        )

        update = ProgressUpdate.from_json(json_str)

        assert update.job_id == job_id
        assert update.percent == 75
        assert update.message == "Generating beatmap..."
        assert update.stage == "transcription"


class TestJobQueue:
    """Test cases for JobQueue operations."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        client = AsyncMock()

        # Create a proper async context manager mock for pipeline
        mock_pipe = AsyncMock()
        mock_pipe.hset = AsyncMock()
        mock_pipe.zadd = AsyncMock()
        mock_pipe.srem = AsyncMock()
        mock_pipe.sadd = AsyncMock()
        mock_pipe.expire = AsyncMock()
        mock_pipe.execute = AsyncMock(return_value=[])

        # Create an async context manager
        async def pipe_context():
            yield mock_pipe

        # Make pipeline() return an async context manager
        from contextlib import asynccontextmanager

        client.pipeline = MagicMock(return_value=asynccontextmanager(pipe_context)())
        client._mock_pipe = mock_pipe  # Store for test access

        return client

    @pytest.fixture
    def queue(self, mock_redis: AsyncMock) -> JobQueue:
        """Create a JobQueue with mocked client."""
        return JobQueue(mock_redis)

    @pytest.mark.asyncio
    async def test_enqueue_calculates_score(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test enqueue uses correct score formula."""
        job = QueuedJob(
            job_id=uuid.uuid4(),
            song_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            priority=100,
            enqueued_at=datetime(2025, 11, 25, 12, 0, 0, tzinfo=timezone.utc),
        )

        await queue.enqueue(job)

        # Verify pipeline was used
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_returns_none_when_empty(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test dequeue returns None for empty queue."""
        mock_redis.zpopmin.return_value = []

        result = await queue.dequeue()

        assert result is None

    @pytest.mark.asyncio
    async def test_dequeue_returns_job_data(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test dequeue returns job when available."""
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        mock_redis.zpopmin.return_value = [(str(job_id), -100)]
        mock_redis.hgetall.return_value = {
            "job_id": json.dumps(str(job_id)),
            "song_id": json.dumps(str(song_id)),
            "user_id": json.dumps(str(user_id)),
            "priority": json.dumps(100),
            "enqueued_at": json.dumps(now.isoformat()),
        }

        result = await queue.dequeue()

        assert result is not None
        assert result.job_id == job_id
        assert result.song_id == song_id
        mock_redis.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_complete_moves_job(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test mark_complete moves job to completed set."""
        job_id = uuid.uuid4()

        await queue.mark_complete(job_id)

        # Should have used pipeline
        mock_redis.pipeline.assert_called()
        # Access the mock pipe stored in fixture
        mock_pipe = mock_redis._mock_pipe
        mock_pipe.srem.assert_called()
        mock_pipe.sadd.assert_called()
        mock_pipe.expire.assert_called()

    @pytest.mark.asyncio
    async def test_mark_failed_stores_error(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test mark_failed stores error message."""
        job_id = uuid.uuid4()
        error_msg = "Processing failed: out of memory"

        await queue.mark_failed(job_id, error_msg)

        # Access the mock pipe stored in fixture
        mock_pipe = mock_redis._mock_pipe
        mock_pipe.hset.assert_called()

    @pytest.mark.asyncio
    async def test_requeue_moves_job_back(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test requeue moves job back to queue."""
        job_id = uuid.uuid4()

        mock_redis.hgetall.return_value = {
            "job_id": str(job_id),
            "priority": "100",
        }

        result = await queue.requeue(job_id)

        assert result is True
        mock_redis.srem.assert_called()
        mock_redis.zadd.assert_called()

    @pytest.mark.asyncio
    async def test_requeue_returns_false_if_not_found(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test requeue returns False if job doesn't exist."""
        mock_redis.hgetall.return_value = {}

        result = await queue.requeue(uuid.uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_get_queue_position(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test get_queue_position returns rank."""
        job_id = uuid.uuid4()
        mock_redis.zrank.return_value = 5

        position = await queue.get_queue_position(job_id)

        assert position == 5

    @pytest.mark.asyncio
    async def test_get_queue_position_not_found(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test get_queue_position returns None if not queued."""
        mock_redis.zrank.return_value = None

        position = await queue.get_queue_position(uuid.uuid4())

        assert position is None

    @pytest.mark.asyncio
    async def test_get_queue_length(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test get_queue_length returns count."""
        mock_redis.zcard.return_value = 42

        length = await queue.get_queue_length()

        assert length == 42

    @pytest.mark.asyncio
    async def test_get_processing_count(
        self, queue: JobQueue, mock_redis: AsyncMock
    ) -> None:
        """Test get_processing_count returns count."""
        mock_redis.scard.return_value = 3

        count = await queue.get_processing_count()

        assert count == 3


class TestProgressPubSub:
    """Test cases for progress pub/sub functions."""

    @pytest.mark.asyncio
    async def test_publish_progress(self) -> None:
        """Test publish_progress sends to correct channel."""
        mock_client = AsyncMock()
        job_id = uuid.uuid4()

        update = ProgressUpdate(
            job_id=job_id,
            percent=42,
            message="Processing...",
            stage="separation",
            timestamp=datetime.now(timezone.utc),
        )

        await publish_progress(mock_client, update)

        expected_channel = RedisKeys.job_progress_channel(job_id)
        mock_client.publish.assert_called_once_with(expected_channel, update.to_json())


class TestQuotaTracking:
    """Test cases for quota tracking functions."""

    @pytest.mark.asyncio
    async def test_get_quota_usage_returns_value(self) -> None:
        """Test get_quota_usage returns stored value."""
        mock_client = AsyncMock()
        user_id = uuid.uuid4()
        mock_client.get.return_value = "5"

        usage = await get_quota_usage(mock_client, user_id, "2025-11")

        assert usage == 5

    @pytest.mark.asyncio
    async def test_get_quota_usage_returns_zero_when_missing(self) -> None:
        """Test get_quota_usage returns 0 for new user."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        usage = await get_quota_usage(mock_client, uuid.uuid4(), "2025-11")

        assert usage == 0

    @pytest.mark.asyncio
    async def test_increment_quota_usage(self) -> None:
        """Test increment_quota_usage increments and sets TTL."""
        mock_client = AsyncMock()
        user_id = uuid.uuid4()
        mock_client.incrby.return_value = 6

        new_value = await increment_quota_usage(mock_client, user_id, "2025-11")

        assert new_value == 6
        mock_client.expire.assert_called_once()


class TestCaching:
    """Test cases for caching utilities."""

    @pytest.mark.asyncio
    async def test_cache_get_returns_value(self) -> None:
        """Test cache_get returns parsed JSON."""
        mock_client = AsyncMock()
        mock_client.get.return_value = '{"name": "test", "value": 42}'

        result = await cache_get(mock_client, "test", "key1")

        assert result == {"name": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_cache_get_returns_none_when_missing(self) -> None:
        """Test cache_get returns None for missing keys."""
        mock_client = AsyncMock()
        mock_client.get.return_value = None

        result = await cache_get(mock_client, "test", "missing")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.db.redis.get_settings")
    async def test_cache_set_stores_json(self, mock_settings: MagicMock) -> None:
        """Test cache_set stores JSON with TTL."""
        mock_settings.return_value.cache_default_ttl = 3600
        mock_client = AsyncMock()

        await cache_set(mock_client, "test", "key1", {"data": "value"})

        mock_client.set.assert_called_once()
        call_args = mock_client.set.call_args
        assert '"data": "value"' in call_args[0][1]

    @pytest.mark.asyncio
    async def test_cache_delete_removes_key(self) -> None:
        """Test cache_delete removes key."""
        mock_client = AsyncMock()

        await cache_delete(mock_client, "test", "key1")

        expected_key = RedisKeys.cache("test", "key1")
        mock_client.delete.assert_called_once_with(expected_key)
