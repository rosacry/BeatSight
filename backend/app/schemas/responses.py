"""
Enhanced API Response Utilities

Provides rich API responses with:
- Consistent response envelope
- Performance metadata (timing, cache status)
- HATEOAS-style links for discoverability
- Detailed error responses
- Rate limit information
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from functools import wraps

from fastapi import Request, Response
from pydantic import BaseModel, Field

T = TypeVar("T")


# ============================================================================
# Response Metadata
# ============================================================================


class CacheStatus(str, Enum):
    """Cache hit/miss status for transparency."""

    HIT = "hit"
    MISS = "miss"
    STALE = "stale"
    BYPASS = "bypass"


class ResponseMeta(BaseModel):
    """Metadata included in every API response."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server timestamp when response was generated",
    )
    request_id: str | None = Field(
        default=None, description="Unique request ID for tracing"
    )
    processing_time_ms: float | None = Field(
        default=None, description="Server processing time in milliseconds"
    )
    api_version: str = Field(default="v1", description="API version")
    deprecation_warning: str | None = Field(
        default=None, description="Deprecation notice if this endpoint is deprecated"
    )


class CacheMeta(BaseModel):
    """Cache-related metadata."""

    status: CacheStatus = Field(description="Cache hit/miss status")
    ttl_seconds: int | None = Field(
        default=None, description="Time-to-live in seconds if cached"
    )
    cached_at: datetime | None = Field(
        default=None, description="When the data was cached"
    )
    cache_key: str | None = Field(default=None, description="Cache key for debugging")


class RateLimitMeta(BaseModel):
    """Rate limiting information."""

    limit: int = Field(description="Maximum requests allowed in window")
    remaining: int = Field(description="Requests remaining in current window")
    reset_at: datetime = Field(description="When the rate limit resets")
    retry_after_seconds: int | None = Field(
        default=None, description="Seconds to wait before retrying (if rate limited)"
    )


class Link(BaseModel):
    """HATEOAS-style link for API discoverability."""

    href: str = Field(description="URL of the linked resource")
    rel: str = Field(description="Relationship type (self, next, prev, etc.)")
    method: str = Field(default="GET", description="HTTP method for this link")
    title: str | None = Field(default=None, description="Human-readable title")


# ============================================================================
# Standard Response Envelope
# ============================================================================


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    Provides consistent structure across all endpoints with:
    - Data payload
    - Metadata (timing, request ID)
    - Optional links for navigation
    - Optional cache info
    """

    success: bool = Field(description="Whether the request succeeded")
    data: T | None = Field(description="Response payload")
    meta: ResponseMeta = Field(
        default_factory=ResponseMeta, description="Response metadata"
    )
    links: list[Link] | None = Field(
        default=None, description="Related links for navigation"
    )
    cache: CacheMeta | None = Field(default=None, description="Cache metadata")

    @classmethod
    def ok(
        cls,
        data: T,
        *,
        request_id: str | None = None,
        processing_time_ms: float | None = None,
        links: list[Link] | None = None,
        cache: CacheMeta | None = None,
    ) -> "APIResponse[T]":
        """Create a successful response."""
        return cls(
            success=True,
            data=data,
            meta=ResponseMeta(
                request_id=request_id,
                processing_time_ms=processing_time_ms,
            ),
            links=links,
            cache=cache,
        )

    @classmethod
    def created(
        cls,
        data: T,
        location: str | None = None,
        *,
        request_id: str | None = None,
    ) -> "APIResponse[T]":
        """Create a response for newly created resource."""
        links = []
        if location:
            links.append(Link(href=location, rel="self", title="Created resource"))

        return cls(
            success=True,
            data=data,
            meta=ResponseMeta(request_id=request_id),
            links=links if links else None,
        )


# ============================================================================
# Error Response
# ============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information."""

    field: str | None = Field(
        default=None, description="Field that caused the error (for validation errors)"
    )
    message: str = Field(description="Human-readable error message")
    code: str = Field(description="Machine-readable error code")


class ErrorResponse(BaseModel):
    """
    Structured error response.

    Provides detailed error information for debugging and user feedback.
    """

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(description="Error type/category")
    message: str = Field(description="Human-readable error description")
    details: list[ErrorDetail] | None = Field(
        default=None, description="Detailed error information"
    )
    meta: ResponseMeta = Field(
        default_factory=ResponseMeta, description="Response metadata"
    )
    suggestion: str | None = Field(
        default=None, description="Suggested action to resolve the error"
    )
    docs_url: str | None = Field(
        default=None, description="Link to relevant documentation"
    )

    @classmethod
    def validation_error(
        cls,
        errors: list[dict[str, Any]],
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a validation error response."""
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in e.get("loc", [])),
                message=e.get("msg", "Validation error"),
                code="validation_error",
            )
            for e in errors
        ]

        return cls(
            error="validation_error",
            message="Request validation failed",
            details=details,
            meta=ResponseMeta(request_id=request_id),
            suggestion="Check the field-specific errors and correct your request",
        )

    @classmethod
    def not_found(
        cls,
        resource: str,
        identifier: Any = None,
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a not found error response."""
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with ID '{identifier}' not found"

        return cls(
            error="not_found",
            message=message,
            meta=ResponseMeta(request_id=request_id),
            suggestion=f"Verify the {resource.lower()} ID and try again",
        )

    @classmethod
    def unauthorized(
        cls,
        message: str = "Authentication required",
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create an unauthorized error response."""
        return cls(
            error="unauthorized",
            message=message,
            meta=ResponseMeta(request_id=request_id),
            suggestion="Include a valid authentication token in your request",
            docs_url="/docs#section/Authentication",
        )

    @classmethod
    def forbidden(
        cls,
        message: str = "You don't have permission to perform this action",
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a forbidden error response."""
        return cls(
            error="forbidden",
            message=message,
            meta=ResponseMeta(request_id=request_id),
            suggestion="Check your permissions or contact support",
        )

    @classmethod
    def rate_limited(
        cls,
        retry_after: int,
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a rate limit error response."""
        return cls(
            error="rate_limited",
            message=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            meta=ResponseMeta(request_id=request_id),
            suggestion="Reduce your request frequency or upgrade your plan",
        )

    @classmethod
    def server_error(
        cls,
        message: str = "An unexpected error occurred",
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create a server error response."""
        return cls(
            error="server_error",
            message=message,
            meta=ResponseMeta(request_id=request_id),
            suggestion="Try again later. If the problem persists, contact support.",
        )

    @classmethod
    def insufficient_credits(
        cls,
        required: int,
        available: int,
        *,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create an insufficient credits error response."""
        return cls(
            error="insufficient_credits",
            message=f"This action requires {required} credits, but you only have {available}",
            meta=ResponseMeta(request_id=request_id),
            suggestion="Purchase more credits to continue",
            docs_url="/docs#section/Credits",
        )


# ============================================================================
# Response Timing Decorator
# ============================================================================


def with_timing(func):
    """
    Decorator that adds processing time to API responses.

    Usage:
        @router.get("/items")
        @with_timing
        async def get_items(request: Request):
            ...
            return APIResponse.ok(data, request_id=request.state.request_id)
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        # Find request in args/kwargs
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        if not request:
            request = kwargs.get("request")

        result = await func(*args, **kwargs)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Add timing to response if it's an APIResponse
        if isinstance(result, APIResponse):
            result.meta.processing_time_ms = round(processing_time, 2)
            if request and hasattr(request.state, "request_id"):
                result.meta.request_id = request.state.request_id

        return result

    return wrapper


# ============================================================================
# Response Headers Utility
# ============================================================================


def set_cache_headers(
    response: Response,
    max_age: int = 0,
    private: bool = True,
    stale_while_revalidate: int | None = None,
) -> None:
    """
    Set appropriate cache headers on response.

    Args:
        response: FastAPI Response object
        max_age: Max age in seconds (0 = no cache)
        private: If True, cache is private (user-specific)
        stale_while_revalidate: Allow stale content while revalidating
    """
    if max_age == 0:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return

    directives = []
    directives.append("private" if private else "public")
    directives.append(f"max-age={max_age}")

    if stale_while_revalidate:
        directives.append(f"stale-while-revalidate={stale_while_revalidate}")

    response.headers["Cache-Control"] = ", ".join(directives)


def set_rate_limit_headers(
    response: Response,
    limit: int,
    remaining: int,
    reset_timestamp: int,
) -> None:
    """Set rate limit headers on response."""
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_timestamp)

    if remaining == 0:
        response.headers["Retry-After"] = str(reset_timestamp - int(time.time()))
