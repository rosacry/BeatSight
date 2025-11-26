"""Tests for SSE progress streaming.

These tests validate the Server-Sent Events (SSE) progress streaming
functionality for AI jobs, including the ProgressUpdate dataclass and
Redis channel key generation.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.db.redis import ProgressUpdate, RedisKeys
from app.models.ai_job import AIJob, AIJobState


class TestProgressUpdate:
    """Test cases for ProgressUpdate dataclass."""

    def test_to_json(self) -> None:
        """Test serializing ProgressUpdate to JSON."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        update = ProgressUpdate(
            job_id=job_id,
            percent=50,
            message="Processing...",
            stage="separation",
            timestamp=now,
        )

        json_str = update.to_json()
        data = json.loads(json_str)

        assert data["job_id"] == str(job_id)
        assert data["percent"] == 50
        assert data["message"] == "Processing..."
        assert data["stage"] == "separation"
        assert data["timestamp"] == now.isoformat()

    def test_from_json(self) -> None:
        """Test deserializing ProgressUpdate from JSON."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        json_str = json.dumps(
            {
                "job_id": str(job_id),
                "percent": 75,
                "message": "Almost done",
                "stage": "transcription",
                "timestamp": now.isoformat(),
            }
        )

        update = ProgressUpdate.from_json(json_str)

        assert update.job_id == job_id
        assert update.percent == 75
        assert update.message == "Almost done"
        assert update.stage == "transcription"

    def test_roundtrip(self) -> None:
        """Test JSON serialization roundtrip."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        original = ProgressUpdate(
            job_id=job_id,
            percent=25,
            message="Starting...",
            stage="download",
            timestamp=now,
        )

        json_str = original.to_json()
        restored = ProgressUpdate.from_json(json_str)

        assert restored.job_id == original.job_id
        assert restored.percent == original.percent
        assert restored.message == original.message
        assert restored.stage == original.stage

    def test_optional_fields(self) -> None:
        """Test ProgressUpdate with optional fields omitted."""
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        update = ProgressUpdate(
            job_id=job_id,
            percent=10,
            message=None,
            stage=None,
            timestamp=now,
        )

        json_str = update.to_json()
        data = json.loads(json_str)

        assert data["message"] is None
        assert data["stage"] is None


class TestRedisKeysSSE:
    """Test cases for Redis key generation for SSE channels."""

    def test_job_progress_channel(self) -> None:
        """Test generating Redis channel key for job progress."""
        job_id = uuid.uuid4()

        channel = RedisKeys.job_progress_channel(job_id)

        assert f"progress:{job_id}" in channel
        assert isinstance(channel, str)

    def test_channel_key_uniqueness(self) -> None:
        """Test that different jobs get different channel keys."""
        job_id_1 = uuid.uuid4()
        job_id_2 = uuid.uuid4()

        channel_1 = RedisKeys.job_progress_channel(job_id_1)
        channel_2 = RedisKeys.job_progress_channel(job_id_2)

        assert channel_1 != channel_2


class TestSSEEventGenerator:
    """Test cases for SSE event generation logic.

    These tests validate the core logic without requiring a full HTTP client.
    """

    @pytest.fixture
    def mock_job_queued(self) -> AIJob:
        """Create a mock queued job."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.QUEUED
        job.progress_percent = None
        job.progress_message = None
        job.beatmap_id = None
        job.error_message = None
        return job

    @pytest.fixture
    def mock_job_processing(self) -> AIJob:
        """Create a mock processing job."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.PROCESSING
        job.progress_percent = 25
        job.progress_message = "Separating drums..."
        job.beatmap_id = None
        job.error_message = None
        return job

    @pytest.fixture
    def mock_job_complete(self) -> AIJob:
        """Create a mock complete job."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.COMPLETE
        job.progress_percent = 100
        job.progress_message = "Done!"
        job.beatmap_id = uuid.uuid4()
        job.error_message = None
        return job

    @pytest.fixture
    def mock_job_failed(self) -> AIJob:
        """Create a mock failed job."""
        job = MagicMock(spec=AIJob)
        job.id = uuid.uuid4()
        job.state = AIJobState.FAILED
        job.progress_percent = 45
        job.progress_message = "Processing..."
        job.beatmap_id = None
        job.error_message = "Out of memory"
        return job

    def test_initial_status_format(self, mock_job_queued: AIJob) -> None:
        """Test initial status event format."""
        from app.api.routes.ai_jobs import _json_dumps

        initial_data = {
            "job_id": str(mock_job_queued.id),
            "status": mock_job_queued.state.value,
            "percent": mock_job_queued.progress_percent or 0,
            "message": mock_job_queued.progress_message,
        }

        event_line = f"event: status\ndata: {_json_dumps(initial_data)}\n\n"

        assert "event: status" in event_line
        assert "data:" in event_line
        assert str(mock_job_queued.id) in event_line

    def test_complete_event_format(self, mock_job_complete: AIJob) -> None:
        """Test complete event format includes beatmap_id."""
        from app.api.routes.ai_jobs import _json_dumps

        final_data = {
            "job_id": str(mock_job_complete.id),
            "status": "completed",
            "beatmap_id": str(mock_job_complete.beatmap_id),
        }

        event_line = f"event: complete\ndata: {_json_dumps(final_data)}\n\n"

        assert "event: complete" in event_line
        assert "beatmap_id" in event_line

    def test_error_event_format(self, mock_job_failed: AIJob) -> None:
        """Test error event format includes error message."""
        from app.api.routes.ai_jobs import _json_dumps

        error_data = {
            "job_id": str(mock_job_failed.id),
            "status": "failed",
            "error": mock_job_failed.error_message,
        }

        event_line = f"event: error\ndata: {_json_dumps(error_data)}\n\n"

        assert "event: error" in event_line
        assert "Out of memory" in event_line

    def test_progress_event_format(self, mock_job_processing: AIJob) -> None:
        """Test progress event format."""
        from app.api.routes.ai_jobs import _json_dumps

        now = datetime.now(timezone.utc)
        progress_data = {
            "percent": mock_job_processing.progress_percent,
            "message": mock_job_processing.progress_message,
            "stage": "separation",
            "timestamp": now.isoformat(),
        }

        event_line = f"event: progress\ndata: {_json_dumps(progress_data)}\n\n"

        assert "event: progress" in event_line
        assert "percent" in event_line
        assert "25" in event_line


class TestJsonDumpsHelper:
    """Test the _json_dumps helper function."""

    def test_filters_none_values(self) -> None:
        """Test that None values are filtered out."""
        from app.api.routes.ai_jobs import _json_dumps

        data = {
            "job_id": "123",
            "status": "completed",
            "beatmap_id": None,
            "error": None,
        }

        result = _json_dumps(data)
        parsed = json.loads(result)

        assert "beatmap_id" not in parsed
        assert "error" not in parsed
        assert parsed["job_id"] == "123"
        assert parsed["status"] == "completed"

    def test_preserves_non_none_values(self) -> None:
        """Test that non-None values are preserved."""
        from app.api.routes.ai_jobs import _json_dumps

        data = {
            "percent": 50,
            "message": "Processing...",
            "empty_string": "",
            "zero": 0,
            "false": False,
        }

        result = _json_dumps(data)
        parsed = json.loads(result)

        assert parsed["percent"] == 50
        assert parsed["message"] == "Processing..."
        assert parsed["empty_string"] == ""
        assert parsed["zero"] == 0
        assert parsed["false"] is False
