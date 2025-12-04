"""
WebSocket endpoint for real-time job progress updates.

Clients can subscribe to job updates and receive progress messages
as jobs move through the AI pipeline.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from redis.asyncio import Redis

from app.api.deps import get_current_user_ws, get_redis
from app.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for job updates."""

    def __init__(self) -> None:
        # Map of user_id -> list of active connections
        self.user_connections: dict[str, list[WebSocket]] = {}
        # Map of job_id -> list of subscribed connections
        self.job_subscriptions: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(websocket)
        logger.info("websocket_connected", user_id=user_id)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove a disconnected WebSocket."""
        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                ws for ws in self.user_connections[user_id] if ws != websocket
            ]
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

        # Remove from all job subscriptions
        for job_id in list(self.job_subscriptions.keys()):
            self.job_subscriptions[job_id] = [
                ws for ws in self.job_subscriptions[job_id] if ws != websocket
            ]
            if not self.job_subscriptions[job_id]:
                del self.job_subscriptions[job_id]

        logger.info("websocket_disconnected", user_id=user_id)

    def subscribe_to_job(self, websocket: WebSocket, job_id: str) -> None:
        """Subscribe a connection to job updates."""
        if job_id not in self.job_subscriptions:
            self.job_subscriptions[job_id] = []
        if websocket not in self.job_subscriptions[job_id]:
            self.job_subscriptions[job_id].append(websocket)
            logger.debug("job_subscribed", job_id=job_id)

    def unsubscribe_from_job(self, websocket: WebSocket, job_id: str) -> None:
        """Unsubscribe a connection from job updates."""
        if job_id in self.job_subscriptions:
            self.job_subscriptions[job_id] = [
                ws for ws in self.job_subscriptions[job_id] if ws != websocket
            ]

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connections for a user."""
        if user_id in self.user_connections:
            dead_connections = []
            for ws in self.user_connections[user_id]:
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)

            # Clean up dead connections
            for ws in dead_connections:
                self.disconnect(ws, user_id)

    async def broadcast_job_update(self, job_id: str, message: dict) -> None:
        """Broadcast a job update to all subscribed connections."""
        if job_id in self.job_subscriptions:
            dead_connections = []
            for ws in self.job_subscriptions[job_id]:
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)

            # Remove dead connections from subscription
            for ws in dead_connections:
                self.job_subscriptions[job_id] = [
                    w for w in self.job_subscriptions[job_id] if w != ws
                ]


manager = ConnectionManager()


async def listen_to_redis(redis: Redis, user_id: str, websocket: WebSocket) -> None:
    """Listen to Redis pub/sub for job updates relevant to this user."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"user:{user_id}:jobs")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(f"user:{user_id}:jobs")
        await pubsub.close()


@router.websocket("/ws/jobs")
async def websocket_jobs(
    websocket: WebSocket,
    user: User = Depends(get_current_user_ws),
    redis: Redis = Depends(get_redis),
) -> None:
    """
    WebSocket endpoint for real-time job updates.

    ## Connection
    Connect with a valid JWT token as query parameter:
    ```
    ws://host/ws/jobs?token=<access_token>
    ```

    ## Messages

    ### Subscribe to a job
    ```json
    {"type": "subscribe", "job_id": "uuid"}
    ```

    ### Unsubscribe from a job
    ```json
    {"type": "unsubscribe", "job_id": "uuid"}
    ```

    ### Server messages
    ```json
    {
        "type": "job_progress",
        "job_id": "uuid",
        "percent": 45,
        "message": "Separating drum stems...",
        "stage": "separation"
    }
    ```

    ```json
    {
        "type": "job_complete",
        "job_id": "uuid",
        "song_id": "uuid",
        "beatmap_id": "uuid"
    }
    ```

    ```json
    {
        "type": "job_failed",
        "job_id": "uuid",
        "error": "Out of GPU memory"
    }
    ```
    """
    user_id = str(user.id)
    await manager.connect(websocket, user_id)

    # Start Redis listener in background
    redis_task = asyncio.create_task(listen_to_redis(redis, user_id, websocket))

    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "subscribe":
                job_id = data.get("job_id")
                if job_id:
                    manager.subscribe_to_job(websocket, job_id)
                    await websocket.send_json(
                        {
                            "type": "subscribed",
                            "job_id": job_id,
                        }
                    )

            elif msg_type == "unsubscribe":
                job_id = data.get("job_id")
                if job_id:
                    manager.unsubscribe_from_job(websocket, job_id)
                    await websocket.send_json(
                        {
                            "type": "unsubscribed",
                            "job_id": job_id,
                        }
                    )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        redis_task.cancel()
        manager.disconnect(websocket, user_id)


# Helper function for workers to publish job updates
async def publish_job_update(
    redis: Redis,
    user_id: str,
    job_id: str,
    update_type: str,
    **kwargs: object,
) -> None:
    """
    Publish a job update to Redis for real-time delivery.

    Args:
        redis: Redis connection
        user_id: Owner of the job
        job_id: The job ID
        update_type: One of 'progress', 'complete', 'failed'
        **kwargs: Additional fields (percent, message, stage, error, etc.)
    """
    message = {
        "type": f"job_{update_type}",
        "job_id": job_id,
        **kwargs,
    }
    await redis.publish(f"user:{user_id}:jobs", json.dumps(message))

    # Also broadcast to direct subscribers
    await manager.broadcast_job_update(job_id, message)
