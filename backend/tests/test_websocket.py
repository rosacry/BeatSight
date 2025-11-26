"""
Tests for WebSocket job updates endpoint.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from app.api.routes.websocket import ConnectionManager, publish_job_update


class TestConnectionManager:
    """Tests for the WebSocket connection manager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_adds_to_user_connections(self):
        """Test that connect adds websocket to user connections."""
        ws = AsyncMock(spec=WebSocket)
        user_id = "user-123"

        await self.manager.connect(ws, user_id)

        assert user_id in self.manager.user_connections
        assert ws in self.manager.user_connections[user_id]
        ws.accept.assert_called_once()

    def test_disconnect_removes_from_user_connections(self):
        """Test that disconnect removes websocket from user connections."""
        ws = MagicMock(spec=WebSocket)
        user_id = "user-123"
        self.manager.user_connections[user_id] = [ws]

        self.manager.disconnect(ws, user_id)

        assert user_id not in self.manager.user_connections

    def test_disconnect_removes_from_job_subscriptions(self):
        """Test that disconnect removes websocket from all job subscriptions."""
        ws = MagicMock(spec=WebSocket)
        user_id = "user-123"
        job_id = "job-456"
        self.manager.user_connections[user_id] = [ws]
        self.manager.job_subscriptions[job_id] = [ws]

        self.manager.disconnect(ws, user_id)

        assert job_id not in self.manager.job_subscriptions

    def test_subscribe_to_job(self):
        """Test subscribing a websocket to job updates."""
        ws = MagicMock(spec=WebSocket)
        job_id = "job-123"

        self.manager.subscribe_to_job(ws, job_id)

        assert job_id in self.manager.job_subscriptions
        assert ws in self.manager.job_subscriptions[job_id]

    def test_subscribe_to_job_no_duplicates(self):
        """Test that subscribing twice doesn't create duplicates."""
        ws = MagicMock(spec=WebSocket)
        job_id = "job-123"

        self.manager.subscribe_to_job(ws, job_id)
        self.manager.subscribe_to_job(ws, job_id)

        assert len(self.manager.job_subscriptions[job_id]) == 1

    def test_unsubscribe_from_job(self):
        """Test unsubscribing a websocket from job updates."""
        ws = MagicMock(spec=WebSocket)
        job_id = "job-123"
        self.manager.job_subscriptions[job_id] = [ws]

        self.manager.unsubscribe_from_job(ws, job_id)

        assert ws not in self.manager.job_subscriptions.get(job_id, [])


class TestPublishJobUpdate:
    """Tests for the publish_job_update helper function."""

    @pytest.mark.asyncio
    async def test_publish_progress_update(self):
        """Test publishing a progress update to Redis."""
        redis = AsyncMock()
        user_id = "user-123"
        job_id = "job-456"

        with patch("app.api.routes.websocket.manager") as mock_manager:
            mock_manager.broadcast_job_update = AsyncMock()

            await publish_job_update(
                redis,
                user_id,
                job_id,
                "progress",
                percent=50,
                message="Processing...",
                stage="separation",
            )

            # Verify Redis publish was called
            redis.publish.assert_called_once()
            call_args = redis.publish.call_args
            assert call_args[0][0] == f"user:{user_id}:jobs"

            # Verify broadcast was called
            mock_manager.broadcast_job_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_complete_update(self):
        """Test publishing a job complete update."""
        redis = AsyncMock()
        user_id = "user-123"
        job_id = "job-456"

        with patch("app.api.routes.websocket.manager") as mock_manager:
            mock_manager.broadcast_job_update = AsyncMock()

            await publish_job_update(
                redis,
                user_id,
                job_id,
                "complete",
                song_id="song-789",
                beatmap_id="map-abc",
            )

            redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failed_update(self):
        """Test publishing a job failed update."""
        redis = AsyncMock()
        user_id = "user-123"
        job_id = "job-456"

        with patch("app.api.routes.websocket.manager") as mock_manager:
            mock_manager.broadcast_job_update = AsyncMock()

            await publish_job_update(
                redis,
                user_id,
                job_id,
                "failed",
                error="GPU out of memory",
            )

            redis.publish.assert_called_once()


class TestMultipleConnections:
    """Tests for handling multiple WebSocket connections."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = ConnectionManager()

    @pytest.mark.asyncio
    async def test_multiple_users(self):
        """Test managing connections for multiple users."""
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)

        await self.manager.connect(ws1, "user-1")
        await self.manager.connect(ws2, "user-2")

        assert "user-1" in self.manager.user_connections
        assert "user-2" in self.manager.user_connections
        assert len(self.manager.user_connections) == 2

    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(self):
        """Test multiple connections from the same user (different devices)."""
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        user_id = "user-123"

        await self.manager.connect(ws1, user_id)
        await self.manager.connect(ws2, user_id)

        assert len(self.manager.user_connections[user_id]) == 2
        assert ws1 in self.manager.user_connections[user_id]
        assert ws2 in self.manager.user_connections[user_id]

    def test_disconnect_one_of_multiple(self):
        """Test disconnecting one of multiple connections for same user."""
        ws1 = MagicMock(spec=WebSocket)
        ws2 = MagicMock(spec=WebSocket)
        user_id = "user-123"
        self.manager.user_connections[user_id] = [ws1, ws2]

        self.manager.disconnect(ws1, user_id)

        assert len(self.manager.user_connections[user_id]) == 1
        assert ws2 in self.manager.user_connections[user_id]
