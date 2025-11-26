"""
Modal GPU orchestration service.

Provides integration with Modal.com for GPU-accelerated AI job processing.
This service handles triggering Modal functions when jobs are enqueued
and receiving results via webhooks.

Configuration (in .env or environment):
    MODAL_ENABLED: Set to 'true' to enable Modal integration
    MODAL_APP_NAME: The Modal app name (default: beatsight-ai)
    MODAL_ENVIRONMENT: Modal environment (default: main)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.config import get_settings

settings = get_settings()

# Create module logger
logger = structlog.get_logger(__name__)


@dataclass
class ModalConfig:
    """Modal integration configuration."""

    # Whether Modal integration is enabled (from settings)
    enabled: bool = settings.modal_enabled

    # Modal webhook URL (deployed endpoint) - constructed from app name
    webhook_url: str = os.getenv(
        "MODAL_WEBHOOK_URL",
        f"https://{settings.modal_app_name}--{settings.modal_app_name}-trigger-job.modal.run",
    )

    # Optional shared secret for webhook auth
    webhook_secret: str | None = os.getenv("MODAL_WEBHOOK_SECRET")

    # Timeout for webhook calls
    timeout_seconds: int = int(os.getenv("MODAL_WEBHOOK_TIMEOUT", "30"))


class ModalError(Exception):
    """Base exception for Modal integration errors."""

    pass


class ModalConnectionError(ModalError):
    """Failed to connect to Modal endpoint."""

    pass


class ModalJobError(ModalError):
    """Modal rejected the job request."""

    pass


class ModalService:
    """
    Service for triggering AI jobs on Modal GPU infrastructure.

    Modal provides serverless GPU compute with automatic scaling.
    Jobs are triggered via HTTP webhook and results are returned
    asynchronously via progress updates.

    Usage:
        service = ModalService()

        if service.is_enabled():
            result = await service.trigger_job(
                job_id="...",
                audio_url="https://...",
                song_id="...",
            )

            if result.accepted:
                print(f"Job dispatched: {result.call_id}")
    """

    def __init__(self, config: ModalConfig | None = None):
        self.config = config or ModalConfig()
        self._client: httpx.AsyncClient | None = None

    def is_enabled(self) -> bool:
        """Check if Modal integration is enabled."""
        return self.config.enabled

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {}
            if self.config.webhook_secret:
                headers["X-Webhook-Secret"] = self.config.webhook_secret

            self._client = httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                headers=headers,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def trigger_job(
        self,
        job_id: str,
        audio_url: str,
        song_id: str,
        options: dict[str, Any] | None = None,
    ) -> "TriggerResult":
        """
        Trigger an AI job on Modal.

        This sends a request to the Modal webhook endpoint which
        spawns a GPU worker to process the audio.

        Args:
            job_id: Unique job identifier
            audio_url: Pre-signed URL to download the audio file
            song_id: Song ID for metadata association
            options: Optional processing parameters
                - detection_sensitivity: 0-100
                - quantization_grid: "1/4", "1/8", "1/16", "1/32"
                - use_ml_classifier: bool
                - tempo_hint: Optional BPM hint

        Returns:
            TriggerResult with acceptance status and call ID

        Raises:
            ModalConnectionError: Failed to connect to Modal
            ModalJobError: Modal rejected the request
        """
        if not self.is_enabled():
            logger.warning("Modal integration is disabled, job not triggered")
            return TriggerResult(
                accepted=False,
                error="Modal integration is disabled",
            )

        client = await self._get_client()

        payload = {
            "job_id": job_id,
            "audio_url": audio_url,
            "song_id": song_id,
        }
        if options:
            payload["options"] = options

        try:
            logger.info(
                "Triggering Modal job",
                job_id=job_id,
                webhook_url=self.config.webhook_url,
            )

            response = await client.post(
                self.config.webhook_url,
                json=payload,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("accepted"):
                    logger.info(
                        "Modal job accepted",
                        job_id=job_id,
                        call_id=data.get("call_id"),
                    )
                    return TriggerResult(
                        accepted=True,
                        call_id=data.get("call_id"),
                    )
                else:
                    error = data.get("error", "Unknown error")
                    logger.error("Modal rejected job", job_id=job_id, error=error)
                    return TriggerResult(accepted=False, error=error)
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error("Modal request failed", job_id=job_id, error=error)
                raise ModalJobError(error)

        except httpx.ConnectError as e:
            logger.error("Failed to connect to Modal", error=str(e))
            raise ModalConnectionError(f"Connection failed: {e}") from e
        except httpx.TimeoutException as e:
            logger.error("Modal request timed out", error=str(e))
            raise ModalConnectionError(f"Request timed out: {e}") from e
        except httpx.HTTPError as e:
            logger.error("Modal HTTP error", error=str(e))
            raise ModalConnectionError(f"HTTP error: {e}") from e

    async def check_health(self) -> bool:
        """
        Check if Modal endpoint is healthy.

        Returns:
            True if Modal is reachable and healthy
        """
        if not self.is_enabled():
            return False

        # Health endpoint is at the root
        health_url = self.config.webhook_url.rsplit("/", 1)[0] + "/health"

        try:
            client = await self._get_client()
            response = await client.get(health_url, timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            logger.warning("Modal health check failed", error=str(e))
            return False


@dataclass
class TriggerResult:
    """Result of triggering a Modal job."""

    accepted: bool
    call_id: str | None = None
    error: str | None = None


# Singleton instance
_modal_service: ModalService | None = None


def get_modal_service() -> ModalService:
    """Get the Modal service singleton."""
    global _modal_service
    if _modal_service is None:
        _modal_service = ModalService()
    return _modal_service


async def close_modal_service():
    """Close the Modal service on shutdown."""
    global _modal_service
    if _modal_service:
        await _modal_service.close()
        _modal_service = None
