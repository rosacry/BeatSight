"""Webhook utilities for sending HTTP callbacks.

Provides secure, reliable webhook delivery with:
- Payload signing (HMAC-SHA256)
- Automatic retries with exponential backoff
- Request timeouts
- Event logging

Usage:
    from app.utils.webhooks import (
        WebhookClient,
        WebhookPayload,
        sign_webhook_payload,
    )

    client = WebhookClient()
    
    # Send a webhook
    result = await client.send(
        url="https://example.com/webhook",
        event_type="song.created",
        payload={"song_id": "123", "title": "My Song"},
        secret="webhook_secret_key",
    )
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


class WebhookStatus(str, Enum):
    """Webhook delivery status."""
    
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEventType(str, Enum):
    """Standard webhook event types."""
    
    # Song events
    SONG_CREATED = "song.created"
    SONG_UPDATED = "song.updated"
    SONG_DELETED = "song.deleted"
    SONG_PROCESSED = "song.processed"
    
    # Beatmap events
    BEATMAP_CREATED = "beatmap.created"
    BEATMAP_UPDATED = "beatmap.updated"
    BEATMAP_DELETED = "beatmap.deleted"
    BEATMAP_PUBLISHED = "beatmap.published"
    
    # User events
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    
    # Credit events
    CREDITS_PURCHASED = "credits.purchased"
    CREDITS_USED = "credits.used"
    CREDITS_REFUNDED = "credits.refunded"
    
    # Processing events
    PROCESSING_STARTED = "processing.started"
    PROCESSING_COMPLETED = "processing.completed"
    PROCESSING_FAILED = "processing.failed"
    
    # Generic
    TEST = "test"
    CUSTOM = "custom"


class WebhookPayload(BaseModel):
    """Webhook payload structure."""
    
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., alias="eventType")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    api_version: str = Field("2024-01-01", alias="apiVersion")
    data: dict[str, Any] = Field(default_factory=dict)


@dataclass
class WebhookResult:
    """Result of a webhook delivery attempt."""
    
    success: bool
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    attempts: int = 1
    delivery_time_ms: float = 0
    webhook_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class WebhookConfig:
    """Configuration for webhook client."""
    
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0
    max_retry_delay_seconds: float = 60.0
    user_agent: str = "BeatSight-Webhook/1.0"
    verify_ssl: bool = True


# =============================================================================
# Signing functions
# =============================================================================

def sign_webhook_payload(
    payload: str | bytes,
    secret: str,
    timestamp: int | None = None,
) -> tuple[str, int]:
    """Sign a webhook payload with HMAC-SHA256.
    
    Args:
        payload: The payload to sign (JSON string or bytes)
        secret: The secret key for signing
        timestamp: Unix timestamp (uses current time if not provided)
        
    Returns:
        Tuple of (signature, timestamp)
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    if isinstance(payload, str):
        payload = payload.encode()
    
    # Create signature string: timestamp.payload
    signature_payload = f"{timestamp}.".encode() + payload
    
    signature = hmac.new(
        secret.encode(),
        signature_payload,
        hashlib.sha256,
    ).hexdigest()
    
    return signature, timestamp


def verify_webhook_signature(
    payload: str | bytes,
    signature: str,
    timestamp: int,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify a webhook signature.
    
    Args:
        payload: The received payload
        signature: The signature to verify
        timestamp: The timestamp from the request
        secret: The secret key
        tolerance_seconds: Maximum age of the webhook (default 5 minutes)
        
    Returns:
        True if signature is valid and not expired
    """
    # Check timestamp is within tolerance
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        return False
    
    # Compute expected signature
    expected_signature, _ = sign_webhook_payload(payload, secret, timestamp)
    
    # Compare signatures (timing-safe)
    return hmac.compare_digest(signature, expected_signature)


def generate_webhook_headers(
    payload: str,
    secret: str,
    webhook_id: str | None = None,
) -> dict[str, str]:
    """Generate webhook headers including signature.
    
    Args:
        payload: JSON payload string
        secret: Secret for signing
        webhook_id: Unique webhook ID (generated if not provided)
        
    Returns:
        Dictionary of headers
    """
    if webhook_id is None:
        webhook_id = str(uuid.uuid4())
    
    signature, timestamp = sign_webhook_payload(payload, secret)
    
    return {
        "Content-Type": "application/json",
        "X-Webhook-Id": webhook_id,
        "X-Webhook-Timestamp": str(timestamp),
        "X-Webhook-Signature": f"sha256={signature}",
    }


# =============================================================================
# Webhook Client
# =============================================================================

class WebhookClient:
    """Client for sending webhooks with retries and signing."""
    
    def __init__(self, config: WebhookConfig | None = None):
        """Initialize webhook client.
        
        Args:
            config: Webhook configuration
        """
        self.config = config or WebhookConfig()
        self._log = logger.bind(component="webhook_client")
    
    async def send(
        self,
        url: str,
        event_type: str,
        payload: dict[str, Any],
        secret: str | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> WebhookResult:
        """Send a webhook with automatic retries.
        
        Args:
            url: Target webhook URL
            event_type: Type of event
            payload: Event data
            secret: Secret for signing (optional)
            headers: Additional headers
            idempotency_key: Key for deduplication
            
        Returns:
            WebhookResult with delivery status
        """
        webhook_id = idempotency_key or str(uuid.uuid4())
        
        # Build webhook payload
        webhook_payload = WebhookPayload(
            id=webhook_id,
            event_type=event_type,
            data=payload,
        )
        
        payload_json = webhook_payload.model_dump_json(by_alias=True)
        
        # Build headers
        request_headers = {
            "Content-Type": "application/json",
            "User-Agent": self.config.user_agent,
            "X-Webhook-Id": webhook_id,
        }
        
        if secret:
            sig_headers = generate_webhook_headers(payload_json, secret, webhook_id)
            request_headers.update(sig_headers)
        
        if headers:
            request_headers.update(headers)
        
        # Send with retries
        return await self._send_with_retries(
            url=url,
            payload=payload_json,
            headers=request_headers,
            webhook_id=webhook_id,
            event_type=event_type,
        )
    
    async def _send_with_retries(
        self,
        url: str,
        payload: str,
        headers: dict[str, str],
        webhook_id: str,
        event_type: str,
    ) -> WebhookResult:
        """Send webhook with retry logic.
        
        Args:
            url: Target URL
            payload: JSON payload
            headers: Request headers
            webhook_id: Unique webhook ID
            event_type: Event type for logging
            
        Returns:
            WebhookResult
        """
        attempt = 0
        delay = self.config.retry_delay_seconds
        last_error: str | None = None
        last_status_code: int | None = None
        
        start_time = time.time()
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout_seconds),
            verify=self.config.verify_ssl,
        ) as client:
            while attempt <= self.config.max_retries:
                attempt += 1
                
                try:
                    self._log.debug(
                        "Sending webhook",
                        webhook_id=webhook_id,
                        url=url,
                        event_type=event_type,
                        attempt=attempt,
                    )
                    
                    response = await client.post(
                        url,
                        content=payload,
                        headers=headers,
                    )
                    
                    delivery_time_ms = (time.time() - start_time) * 1000
                    
                    # Success if 2xx
                    if 200 <= response.status_code < 300:
                        self._log.info(
                            "Webhook delivered successfully",
                            webhook_id=webhook_id,
                            url=url,
                            event_type=event_type,
                            status_code=response.status_code,
                            attempts=attempt,
                            delivery_time_ms=delivery_time_ms,
                        )
                        
                        return WebhookResult(
                            success=True,
                            status_code=response.status_code,
                            response_body=response.text[:1000],  # Truncate
                            attempts=attempt,
                            delivery_time_ms=delivery_time_ms,
                            webhook_id=webhook_id,
                        )
                    
                    # Non-retryable client errors (4xx except 429)
                    if 400 <= response.status_code < 500 and response.status_code != 429:
                        self._log.warning(
                            "Webhook failed with client error",
                            webhook_id=webhook_id,
                            url=url,
                            status_code=response.status_code,
                        )
                        
                        return WebhookResult(
                            success=False,
                            status_code=response.status_code,
                            response_body=response.text[:1000],
                            error=f"Client error: {response.status_code}",
                            attempts=attempt,
                            delivery_time_ms=delivery_time_ms,
                            webhook_id=webhook_id,
                        )
                    
                    # Retryable errors (5xx, 429)
                    last_status_code = response.status_code
                    last_error = f"Server error: {response.status_code}"
                    
                except httpx.TimeoutException:
                    last_error = "Request timed out"
                    self._log.warning(
                        "Webhook timeout",
                        webhook_id=webhook_id,
                        url=url,
                        attempt=attempt,
                    )
                    
                except httpx.RequestError as e:
                    last_error = f"Request error: {str(e)}"
                    self._log.warning(
                        "Webhook request error",
                        webhook_id=webhook_id,
                        url=url,
                        error=str(e),
                        attempt=attempt,
                    )
                
                # Retry with backoff
                if attempt <= self.config.max_retries:
                    self._log.debug(
                        "Retrying webhook",
                        webhook_id=webhook_id,
                        delay_seconds=delay,
                        attempt=attempt,
                    )
                    
                    import asyncio
                    await asyncio.sleep(delay)
                    
                    delay = min(
                        delay * self.config.retry_backoff_multiplier,
                        self.config.max_retry_delay_seconds,
                    )
        
        # All retries exhausted
        delivery_time_ms = (time.time() - start_time) * 1000
        
        self._log.error(
            "Webhook delivery failed after all retries",
            webhook_id=webhook_id,
            url=url,
            event_type=event_type,
            attempts=attempt,
            last_error=last_error,
        )
        
        return WebhookResult(
            success=False,
            status_code=last_status_code,
            error=last_error,
            attempts=attempt,
            delivery_time_ms=delivery_time_ms,
            webhook_id=webhook_id,
        )
    
    async def send_batch(
        self,
        webhooks: list[dict[str, Any]],
        concurrency: int = 5,
    ) -> list[WebhookResult]:
        """Send multiple webhooks concurrently.
        
        Args:
            webhooks: List of webhook configs with url, event_type, payload, secret
            concurrency: Maximum concurrent requests
            
        Returns:
            List of WebhookResults
        """
        import asyncio
        
        semaphore = asyncio.Semaphore(concurrency)
        
        async def send_one(webhook: dict[str, Any]) -> WebhookResult:
            async with semaphore:
                return await self.send(
                    url=webhook["url"],
                    event_type=webhook["event_type"],
                    payload=webhook["payload"],
                    secret=webhook.get("secret"),
                    headers=webhook.get("headers"),
                )
        
        tasks = [send_one(w) for w in webhooks]
        return await asyncio.gather(*tasks)


# =============================================================================
# Event system integration
# =============================================================================

class WebhookEvent(BaseModel):
    """Represents a webhook event to be dispatched."""
    
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., alias="eventType")
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Targeting
    user_id: str | None = Field(None, alias="userId")
    resource_id: str | None = Field(None, alias="resourceId")
    resource_type: str | None = Field(None, alias="resourceType")


class WebhookSubscription(BaseModel):
    """Represents a webhook subscription."""
    
    model_config = ConfigDict(populate_by_name=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str
    secret: str
    event_types: list[str] = Field(default_factory=list, alias="eventTypes")
    is_active: bool = Field(True, alias="isActive")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Filtering
    user_id: str | None = Field(None, alias="userId")
    resource_types: list[str] = Field(default_factory=list, alias="resourceTypes")
    
    def matches_event(self, event: WebhookEvent) -> bool:
        """Check if this subscription should receive an event.
        
        Args:
            event: The event to check
            
        Returns:
            True if subscription matches event
        """
        if not self.is_active:
            return False
        
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            # Support wildcard patterns
            matched = False
            for pattern in self.event_types:
                if pattern.endswith(".*"):
                    prefix = pattern[:-1]  # Remove *
                    if event.event_type.startswith(prefix):
                        matched = True
                        break
            if not matched:
                return False
        
        # Check user filter
        if self.user_id and event.user_id and self.user_id != event.user_id:
            return False
        
        # Check resource type filter
        if self.resource_types and event.resource_type:
            if event.resource_type not in self.resource_types:
                return False
        
        return True


# =============================================================================
# Helper functions
# =============================================================================

def create_event_payload(
    event_type: str | WebhookEventType,
    resource_id: str | None = None,
    resource_type: str | None = None,
    user_id: str | None = None,
    **data: Any,
) -> WebhookEvent:
    """Create a webhook event payload.
    
    Args:
        event_type: Type of event
        resource_id: ID of related resource
        resource_type: Type of resource
        user_id: ID of related user
        **data: Additional event data
        
    Returns:
        WebhookEvent ready for dispatch
    """
    if isinstance(event_type, WebhookEventType):
        event_type = event_type.value
    
    return WebhookEvent(
        event_type=event_type,
        resource_id=resource_id,
        resource_type=resource_type,
        user_id=user_id,
        payload=data,
    )
