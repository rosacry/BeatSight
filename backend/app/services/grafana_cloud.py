"""
Grafana Cloud metrics pusher for BeatSight.

This service periodically pushes Prometheus metrics to Grafana Cloud
using the OTLP HTTP endpoint.

Configuration via environment variables:
- GRAFANA_CLOUD_ENABLED: Set to "true" to enable pushing (default: false)
- GRAFANA_CLOUD_INSTANCE_ID: Your Grafana Cloud instance ID
- GRAFANA_CLOUD_API_KEY: Your Grafana Cloud API key
- GRAFANA_CLOUD_PUSH_INTERVAL: Seconds between pushes (default: 60)
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import httpx
from prometheus_client import REGISTRY
from prometheus_client.parser import text_string_to_metric_families

logger = logging.getLogger(__name__)

# Grafana Cloud OTLP endpoint
GRAFANA_CLOUD_OTLP_HOST = "https://otlp-gateway-prod-us-east-2.grafana.net"


class GrafanaCloudPusher:
    """Pushes Prometheus metrics to Grafana Cloud."""

    def __init__(
        self,
        instance_id: str,
        api_key: str,
        push_interval: int = 60,
        enabled: bool = True,
    ):
        self.instance_id = instance_id
        self.api_key = api_key
        self.push_interval = push_interval
        self.enabled = enabled
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

        # Build auth header
        auth_pair = f"{instance_id}:{api_key}"
        encoded = base64.b64encode(auth_pair.encode()).decode()
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded}",
        }

    async def start(self) -> None:
        """Start the background metrics pusher."""
        if not self.enabled:
            logger.info("Grafana Cloud pusher disabled")
            return

        logger.info(
            f"Starting Grafana Cloud metrics pusher (interval: {self.push_interval}s)"
        )
        self._client = httpx.AsyncClient(timeout=30.0)
        self._task = asyncio.create_task(self._push_loop())

    async def stop(self) -> None:
        """Stop the background metrics pusher."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("Grafana Cloud metrics pusher stopped")

    async def _push_loop(self) -> None:
        """Background loop that pushes metrics periodically."""
        while True:
            try:
                await self._push_metrics()
            except Exception as e:
                logger.error(f"Error pushing metrics to Grafana Cloud: {e}")

            await asyncio.sleep(self.push_interval)

    async def _push_metrics(self) -> None:
        """Push current metrics to Grafana Cloud."""
        if not self._client:
            return

        # Convert Prometheus metrics to OTLP format
        otlp_payload = self._prometheus_to_otlp()

        url = f"{GRAFANA_CLOUD_OTLP_HOST}/otlp/v1/metrics"

        try:
            response = await self._client.post(
                url,
                headers=self._headers,
                json=otlp_payload,
            )

            if response.status_code == 200:
                logger.debug("Successfully pushed metrics to Grafana Cloud")
            else:
                logger.warning(
                    f"Grafana Cloud returned {response.status_code}: {response.text}"
                )
        except httpx.RequestError as e:
            logger.error(f"Failed to push metrics to Grafana Cloud: {e}")

    def _prometheus_to_otlp(self) -> dict[str, Any]:
        """Convert Prometheus metrics to OTLP JSON format."""
        from prometheus_client import generate_latest, REGISTRY

        # Get current metrics in Prometheus text format
        metrics_text = generate_latest(REGISTRY).decode("utf-8")

        # Parse and convert to OTLP
        metrics_list = []
        current_time_ns = int(time.time() * 1_000_000_000)

        for family in text_string_to_metric_families(metrics_text):
            for sample in family.samples:
                # Skip internal metrics
                if sample.name.startswith("python_") or sample.name.startswith(
                    "process_"
                ):
                    continue

                # Build attributes from labels
                attributes = [
                    {"key": k, "value": {"stringValue": str(v)}}
                    for k, v in (sample.labels or {}).items()
                ]

                # Determine metric type and build data point
                if family.type == "gauge":
                    metric = {
                        "name": sample.name,
                        "unit": "",
                        "description": family.documentation or "",
                        "gauge": {
                            "dataPoints": [
                                {
                                    "asDouble": sample.value,
                                    "timeUnixNano": current_time_ns,
                                    "attributes": attributes,
                                }
                            ]
                        },
                    }
                elif family.type in ("counter", "summary", "histogram"):
                    metric = {
                        "name": sample.name,
                        "unit": "",
                        "description": family.documentation or "",
                        "sum": {
                            "dataPoints": [
                                {
                                    "asDouble": sample.value,
                                    "timeUnixNano": current_time_ns,
                                    "attributes": attributes,
                                }
                            ],
                            "isMonotonic": family.type == "counter",
                            "aggregationTemporality": 2,  # CUMULATIVE
                        },
                    }
                else:
                    # Default to gauge for unknown types
                    metric = {
                        "name": sample.name,
                        "unit": "",
                        "description": family.documentation or "",
                        "gauge": {
                            "dataPoints": [
                                {
                                    "asDouble": sample.value,
                                    "timeUnixNano": current_time_ns,
                                    "attributes": attributes,
                                }
                            ]
                        },
                    }

                metrics_list.append(metric)

        return {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "beatsight-backend"}},
                            {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {"name": "beatsight"},
                            "metrics": metrics_list,
                        }
                    ],
                }
            ]
        }


# Global instance (initialized in app startup)
_pusher: GrafanaCloudPusher | None = None


async def start_grafana_cloud_pusher(
    instance_id: str,
    api_key: str,
    push_interval: int = 60,
    enabled: bool = True,
) -> None:
    """Start the global Grafana Cloud metrics pusher."""
    global _pusher
    _pusher = GrafanaCloudPusher(
        instance_id=instance_id,
        api_key=api_key,
        push_interval=push_interval,
        enabled=enabled,
    )
    await _pusher.start()


async def stop_grafana_cloud_pusher() -> None:
    """Stop the global Grafana Cloud metrics pusher."""
    global _pusher
    if _pusher:
        await _pusher.stop()
        _pusher = None
