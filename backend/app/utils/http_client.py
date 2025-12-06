"""
HTTP client utilities for making external API requests.

Provides a standardized HTTP client with retry, timeout, and error handling.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import httpx
import structlog

__all__ = [
    "HTTPClient",
    "HTTPClientConfig",
    "HTTPMethod",
    "HTTPResponse",
    "HTTPError",
    "HTTPTimeoutError",
    "HTTPConnectionError",
    "RateLimitedError",
    "create_client",
    "request",
    "get",
    "post",
    "put",
    "patch",
    "delete",
]

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class HTTPMethod(str, Enum):
    """HTTP methods."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class HTTPError(Exception):
    """Base HTTP error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: Any = None,
        url: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.url = url


class HTTPTimeoutError(HTTPError):
    """HTTP timeout error."""

    pass


class HTTPConnectionError(HTTPError):
    """HTTP connection error."""

    pass


class RateLimitedError(HTTPError):
    """Rate limited (429) error."""

    def __init__(
        self,
        message: str,
        *,
        retry_after: int | None = None,
        **kwargs: Any,
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


@dataclass
class HTTPClientConfig:
    """
    Configuration for HTTP client.

    Attributes:
        base_url: Base URL for all requests
        timeout: Request timeout in seconds
        connect_timeout: Connection timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Initial delay between retries (exponential backoff)
        retry_on_status: HTTP status codes to retry on
        headers: Default headers for all requests
        follow_redirects: Whether to follow redirects
        verify_ssl: Whether to verify SSL certificates
    """

    base_url: str | None = None
    timeout: float = 30.0
    connect_timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_on_status: tuple[int, ...] = (429, 500, 502, 503, 504)
    headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    verify_ssl: bool = True


@dataclass
class HTTPResponse:
    """
    HTTP response wrapper.

    Attributes:
        status_code: HTTP status code
        headers: Response headers
        body: Response body (bytes)
        text: Response body as text
        json_data: Parsed JSON data (if applicable)
        elapsed: Request duration in seconds
        url: Final URL (after redirects)
    """

    status_code: int
    headers: dict[str, str]
    body: bytes
    elapsed: float
    url: str
    _text: str | None = field(default=None, repr=False)
    _json_data: Any = field(default=None, repr=False)
    _json_parsed: bool = field(default=False, repr=False)

    @property
    def text(self) -> str:
        """Get response body as text."""
        if self._text is None:
            self._text = self.body.decode("utf-8", errors="replace")
        return self._text

    @property
    def json_data(self) -> Any:
        """Get parsed JSON data."""
        if not self._json_parsed:
            import json

            try:
                self._json_data = json.loads(self.body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json_data = None
            self._json_parsed = True
        return self._json_data

    @property
    def ok(self) -> bool:
        """Check if status code indicates success (2xx)."""
        return 200 <= self.status_code < 300

    @property
    def is_redirect(self) -> bool:
        """Check if status code indicates redirect (3xx)."""
        return 300 <= self.status_code < 400

    @property
    def is_client_error(self) -> bool:
        """Check if status code indicates client error (4xx)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if status code indicates server error (5xx)."""
        return 500 <= self.status_code < 600

    def raise_for_status(self) -> None:
        """
        Raise HTTPError if response indicates an error.

        Raises:
            RateLimitedError: If 429 status
            HTTPError: If 4xx or 5xx status
        """
        if self.ok:
            return

        if self.status_code == 429:
            retry_after = self.headers.get("retry-after")
            raise RateLimitedError(
                f"Rate limited: {self.url}",
                status_code=self.status_code,
                response_body=self.json_data or self.text,
                url=self.url,
                retry_after=int(retry_after)
                if retry_after and retry_after.isdigit()
                else None,
            )

        raise HTTPError(
            f"HTTP {self.status_code}: {self.url}",
            status_code=self.status_code,
            response_body=self.json_data or self.text,
            url=self.url,
        )


class HTTPClient:
    """
    Async HTTP client with retry and error handling.

    Example:
        async with HTTPClient(base_url="https://api.example.com") as client:
            response = await client.get("/users/1")
            user = response.json_data
    """

    def __init__(
        self,
        config: HTTPClientConfig | None = None,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize HTTP client.

        Args:
            config: Full configuration object
            base_url: Base URL (shorthand for config)
            timeout: Request timeout (shorthand for config)
            max_retries: Max retries (shorthand for config)
            headers: Default headers (shorthand for config)
        """
        if config:
            self.config = config
        else:
            self.config = HTTPClientConfig(
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
                headers=headers or {},
            )

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> HTTPClient:
        """Enter async context manager."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Exit async context manager."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            timeout = httpx.Timeout(
                timeout=self.config.timeout,
                connect=self.config.connect_timeout,
            )
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url or "",
                timeout=timeout,
                headers=self.config.headers,
                follow_redirects=self.config.follow_redirects,
                verify=self.config.verify_ssl,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: HTTPMethod | str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        content: bytes | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        raise_for_status: bool = False,
    ) -> HTTPResponse:
        """
        Make an HTTP request with retry support.

        Args:
            method: HTTP method
            url: Request URL (relative to base_url if set)
            params: Query parameters
            headers: Additional headers
            json: JSON body (will be serialized)
            data: Form data
            content: Raw body content
            timeout: Override timeout for this request
            max_retries: Override max retries for this request
            raise_for_status: Raise exception on error status

        Returns:
            HTTPResponse object

        Raises:
            HTTPTimeoutError: On timeout
            HTTPConnectionError: On connection error
            HTTPError: On error status (if raise_for_status=True)
        """
        client = await self._ensure_client()

        method_str = method.value if isinstance(method, HTTPMethod) else method.upper()
        retries = max_retries if max_retries is not None else self.config.max_retries
        delay = self.config.retry_delay
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                start_time = time.perf_counter()

                response = await client.request(
                    method=method_str,
                    url=url,
                    params=params,
                    headers=dict(headers) if headers else None,
                    json=json,
                    data=data,
                    content=content,
                    timeout=timeout,
                )

                elapsed = time.perf_counter() - start_time

                result = HTTPResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    body=response.content,
                    elapsed=elapsed,
                    url=str(response.url),
                )

                # Check if we should retry on this status
                if (
                    attempt < retries
                    and response.status_code in self.config.retry_on_status
                ):
                    # Special handling for rate limiting
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after")
                        if retry_after and retry_after.isdigit():
                            delay = float(retry_after)

                    logger.warning(
                        "Retrying request",
                        method=method_str,
                        url=url,
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue

                if raise_for_status:
                    result.raise_for_status()

                return result

            except httpx.TimeoutException as e:
                last_error = HTTPTimeoutError(
                    f"Request timed out: {url}",
                    url=url,
                )
                if attempt < retries:
                    logger.warning(
                        "Request timeout, retrying",
                        url=url,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise last_error from e

            except httpx.ConnectError as e:
                last_error = HTTPConnectionError(
                    f"Connection error: {url}",
                    url=url,
                )
                if attempt < retries:
                    logger.warning(
                        "Connection error, retrying",
                        url=url,
                        attempt=attempt + 1,
                        delay=delay,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue
                raise last_error from e

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise HTTPError(f"Request failed: {url}")

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a GET request."""
        return await self.request(
            HTTPMethod.GET,
            url,
            params=params,
            headers=headers,
            **kwargs,
        )

    async def post(
        self,
        url: str,
        *,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a POST request."""
        return await self.request(
            HTTPMethod.POST,
            url,
            json=json,
            data=data,
            headers=headers,
            **kwargs,
        )

    async def put(
        self,
        url: str,
        *,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a PUT request."""
        return await self.request(
            HTTPMethod.PUT,
            url,
            json=json,
            data=data,
            headers=headers,
            **kwargs,
        )

    async def patch(
        self,
        url: str,
        *,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a PATCH request."""
        return await self.request(
            HTTPMethod.PATCH,
            url,
            json=json,
            data=data,
            headers=headers,
            **kwargs,
        )

    async def delete(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> HTTPResponse:
        """Make a DELETE request."""
        return await self.request(
            HTTPMethod.DELETE,
            url,
            params=params,
            headers=headers,
            **kwargs,
        )


def create_client(
    base_url: str | None = None,
    *,
    timeout: float = 30.0,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> HTTPClient:
    """
    Create a new HTTP client instance.

    Args:
        base_url: Base URL for all requests
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        headers: Default headers

    Returns:
        HTTPClient instance

    Example:
        client = create_client("https://api.example.com")
        async with client:
            response = await client.get("/users")
    """
    return HTTPClient(
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        headers=headers,
    )


# Convenience functions for one-off requests
async def request(
    method: HTTPMethod | str,
    url: str,
    **kwargs: Any,
) -> HTTPResponse:
    """
    Make a one-off HTTP request.

    Args:
        method: HTTP method
        url: Full URL
        **kwargs: Additional arguments for HTTPClient.request

    Returns:
        HTTPResponse object
    """
    async with HTTPClient() as client:
        return await client.request(method, url, **kwargs)


async def get(url: str, **kwargs: Any) -> HTTPResponse:
    """Make a one-off GET request."""
    return await request(HTTPMethod.GET, url, **kwargs)


async def post(url: str, **kwargs: Any) -> HTTPResponse:
    """Make a one-off POST request."""
    return await request(HTTPMethod.POST, url, **kwargs)


async def put(url: str, **kwargs: Any) -> HTTPResponse:
    """Make a one-off PUT request."""
    return await request(HTTPMethod.PUT, url, **kwargs)


async def patch(url: str, **kwargs: Any) -> HTTPResponse:
    """Make a one-off PATCH request."""
    return await request(HTTPMethod.PATCH, url, **kwargs)


async def delete(url: str, **kwargs: Any) -> HTTPResponse:
    """Make a one-off DELETE request."""
    return await request(HTTPMethod.DELETE, url, **kwargs)
