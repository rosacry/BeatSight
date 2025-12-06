"""Standardized error handling for the BeatSight API.

This module provides:
- Standardized error codes for consistent API responses
- Custom exception classes mapped to HTTP status codes
- Error response schemas for OpenAPI documentation
- Exception handlers for automatic error formatting

Usage:
    from app.utils.errors import (
        NotFoundError,
        ValidationError,
        AuthenticationError,
        raise_not_found,
    )

    # Raise a standardized error
    raise NotFoundError("Song not found", code="SONG_NOT_FOUND")

    # Use helper function
    raise_not_found("song", song_id)
"""

from __future__ import annotations

from dataclasses import field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# ERROR CODES
# =============================================================================


class ErrorCode(str, Enum):
    """Standardized error codes for API responses.

    Format: CATEGORY_DESCRIPTION
    Categories:
    - AUTH: Authentication/authorization errors
    - VAL: Validation errors
    - RES: Resource errors (not found, conflict)
    - RATE: Rate limiting errors
    - SRV: Server/service errors
    - PAY: Payment/billing errors
    - AI: AI processing errors
    """

    # Authentication errors (401, 403)
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_MISSING_TOKEN = "AUTH_MISSING_TOKEN"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_ACCOUNT_LOCKED = "AUTH_ACCOUNT_LOCKED"
    AUTH_ACCOUNT_DISABLED = "AUTH_ACCOUNT_DISABLED"
    AUTH_EMAIL_NOT_VERIFIED = "AUTH_EMAIL_NOT_VERIFIED"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    AUTH_OAUTH_FAILED = "AUTH_OAUTH_FAILED"

    # Validation errors (400, 422)
    VAL_INVALID_INPUT = "VAL_INVALID_INPUT"
    VAL_MISSING_FIELD = "VAL_MISSING_FIELD"
    VAL_INVALID_FORMAT = "VAL_INVALID_FORMAT"
    VAL_PASSWORD_TOO_WEAK = "VAL_PASSWORD_TOO_WEAK"
    VAL_EMAIL_INVALID = "VAL_EMAIL_INVALID"
    VAL_FILE_TOO_LARGE = "VAL_FILE_TOO_LARGE"
    VAL_INVALID_FILE_TYPE = "VAL_INVALID_FILE_TYPE"

    # Resource errors (404, 409)
    RES_NOT_FOUND = "RES_NOT_FOUND"
    RES_USER_NOT_FOUND = "RES_USER_NOT_FOUND"
    RES_SONG_NOT_FOUND = "RES_SONG_NOT_FOUND"
    RES_MAP_NOT_FOUND = "RES_MAP_NOT_FOUND"
    RES_JOB_NOT_FOUND = "RES_JOB_NOT_FOUND"
    RES_ALREADY_EXISTS = "RES_ALREADY_EXISTS"
    RES_CONFLICT = "RES_CONFLICT"
    RES_VERSION_CONFLICT = "RES_VERSION_CONFLICT"

    # Rate limiting errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_TOO_MANY_REQUESTS = "RATE_TOO_MANY_REQUESTS"
    RATE_QUOTA_EXCEEDED = "RATE_QUOTA_EXCEEDED"

    # Server errors (500, 502, 503)
    SRV_INTERNAL_ERROR = "SRV_INTERNAL_ERROR"
    SRV_DATABASE_ERROR = "SRV_DATABASE_ERROR"
    SRV_REDIS_ERROR = "SRV_REDIS_ERROR"
    SRV_STORAGE_ERROR = "SRV_STORAGE_ERROR"
    SRV_SERVICE_UNAVAILABLE = "SRV_SERVICE_UNAVAILABLE"
    SRV_DEPENDENCY_FAILED = "SRV_DEPENDENCY_FAILED"

    # Payment errors (402, 400)
    PAY_INSUFFICIENT_CREDITS = "PAY_INSUFFICIENT_CREDITS"
    PAY_PAYMENT_FAILED = "PAY_PAYMENT_FAILED"
    PAY_SUBSCRIPTION_EXPIRED = "PAY_SUBSCRIPTION_EXPIRED"
    PAY_INVALID_COUPON = "PAY_INVALID_COUPON"
    PAY_STRIPE_ERROR = "PAY_STRIPE_ERROR"

    # AI processing errors (400, 500, 503)
    AI_JOB_FAILED = "AI_JOB_FAILED"
    AI_MODEL_UNAVAILABLE = "AI_MODEL_UNAVAILABLE"
    AI_PROCESSING_ERROR = "AI_PROCESSING_ERROR"
    AI_INVALID_AUDIO = "AI_INVALID_AUDIO"
    AI_QUEUE_FULL = "AI_QUEUE_FULL"


# =============================================================================
# ERROR RESPONSE SCHEMA
# =============================================================================


class ErrorDetail(BaseModel):
    """Detailed error information for API responses."""

    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standardized error response format.

    Example:
        {
            "error": {
                "code": "RES_SONG_NOT_FOUND",
                "message": "Song not found",
                "details": {"song_id": "abc-123"}
            },
            "request_id": "req_xyz",
            "timestamp": "2025-01-01T00:00:00Z"
        }
    """

    error: ErrorDetail
    request_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================


class APIError(HTTPException):
    """Base exception for all API errors.

    Provides consistent error formatting and logging.
    """

    def __init__(
        self,
        message: str,
        code: ErrorCode | str = ErrorCode.SRV_INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message
        self.code = code if isinstance(code, str) else code.value
        self.details = details
        super().__init__(
            status_code=status_code,
            detail=message,
            headers=headers,
        )

    def to_response(self, request_id: str | None = None) -> dict[str, Any]:
        """Convert to standardized error response dict."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class NotFoundError(APIError):
    """Resource not found (404)."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: ErrorCode | str = ErrorCode.RES_NOT_FOUND,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(APIError):
    """Validation error (400/422)."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: ErrorCode | str = ErrorCode.VAL_INVALID_INPUT,
        details: dict[str, Any] | None = None,
        field: str | None = None,
    ):
        if field:
            details = details or {}
            details["field"] = field
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AuthenticationError(APIError):
    """Authentication error (401)."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: ErrorCode | str = ErrorCode.AUTH_INVALID_TOKEN,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(APIError):
    """Authorization error (403)."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        code: ErrorCode | str = ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ConflictError(APIError):
    """Resource conflict (409)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: ErrorCode | str = ErrorCode.RES_CONFLICT,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class RateLimitError(APIError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: ErrorCode | str = ErrorCode.RATE_LIMIT_EXCEEDED,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
            details = details or {}
            details["retry_after"] = retry_after
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
            headers=headers if headers else None,
        )


class PaymentError(APIError):
    """Payment/billing error (402)."""

    def __init__(
        self,
        message: str = "Payment required",
        code: ErrorCode | str = ErrorCode.PAY_INSUFFICIENT_CREDITS,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            details=details,
        )


class ServiceUnavailableError(APIError):
    """Service unavailable (503)."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        code: ErrorCode | str = ErrorCode.SRV_SERVICE_UNAVAILABLE,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
            headers=headers if headers else None,
        )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def raise_not_found(
    resource_type: str,
    resource_id: str | UUID | None = None,
    message: str | None = None,
) -> None:
    """Raise a standardized NotFoundError.

    Args:
        resource_type: Type of resource (e.g., "song", "user", "map")
        resource_id: Optional ID of the resource
        message: Optional custom message

    Raises:
        NotFoundError: Always raises

    Example:
        raise_not_found("song", song_id)
        raise_not_found("user", user_id, "User account has been deleted")
    """
    code_map = {
        "song": ErrorCode.RES_SONG_NOT_FOUND,
        "user": ErrorCode.RES_USER_NOT_FOUND,
        "map": ErrorCode.RES_MAP_NOT_FOUND,
        "beatmap": ErrorCode.RES_MAP_NOT_FOUND,
        "job": ErrorCode.RES_JOB_NOT_FOUND,
        "ai_job": ErrorCode.RES_JOB_NOT_FOUND,
    }

    error_code = code_map.get(resource_type.lower(), ErrorCode.RES_NOT_FOUND)
    default_message = f"{resource_type.title()} not found"

    details = {}
    if resource_id:
        details[f"{resource_type}_id"] = str(resource_id)

    raise NotFoundError(
        message=message or default_message,
        code=error_code,
        details=details if details else None,
    )


def raise_validation_error(
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Raise a standardized ValidationError.

    Args:
        message: Error message
        field: Optional field name that failed validation
        details: Optional additional details

    Raises:
        ValidationError: Always raises
    """
    raise ValidationError(
        message=message,
        field=field,
        details=details,
    )


def raise_auth_error(
    message: str = "Authentication required",
    code: ErrorCode = ErrorCode.AUTH_INVALID_TOKEN,
) -> None:
    """Raise a standardized AuthenticationError.

    Args:
        message: Error message
        code: Error code

    Raises:
        AuthenticationError: Always raises
    """
    raise AuthenticationError(message=message, code=code)


def raise_permission_error(
    message: str = "You don't have permission to perform this action",
    required_role: str | None = None,
) -> None:
    """Raise a standardized AuthorizationError.

    Args:
        message: Error message
        required_role: Optional role required for the action

    Raises:
        AuthorizationError: Always raises
    """
    details = {"required_role": required_role} if required_role else None
    raise AuthorizationError(message=message, details=details)


def raise_payment_error(
    message: str = "Insufficient credits",
    required: int | None = None,
    available: int | None = None,
) -> None:
    """Raise a standardized PaymentError.

    Args:
        message: Error message
        required: Required credits/amount
        available: Available credits/amount

    Raises:
        PaymentError: Always raises
    """
    details = {}
    if required is not None:
        details["required"] = required
    if available is not None:
        details["available"] = available

    raise PaymentError(
        message=message,
        code=ErrorCode.PAY_INSUFFICIENT_CREDITS,
        details=details if details else None,
    )


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions and return standardized JSON response."""
    request_id = request.headers.get("X-Request-ID")

    # Log the error
    logger.warning(
        "api_error",
        error_code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(request_id),
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTPExceptions and convert to standardized format."""
    request_id = request.headers.get("X-Request-ID")

    # Map common status codes to error codes
    status_to_code = {
        400: ErrorCode.VAL_INVALID_INPUT,
        401: ErrorCode.AUTH_INVALID_TOKEN,
        403: ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
        404: ErrorCode.RES_NOT_FOUND,
        409: ErrorCode.RES_CONFLICT,
        422: ErrorCode.VAL_INVALID_INPUT,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.SRV_INTERNAL_ERROR,
        502: ErrorCode.SRV_DEPENDENCY_FAILED,
        503: ErrorCode.SRV_SERVICE_UNAVAILABLE,
    }

    error_code = status_to_code.get(exc.status_code, ErrorCode.SRV_INTERNAL_ERROR)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code.value,
                "message": exc.detail or "An error occurred",
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions with standardized error response."""
    request_id = request.headers.get("X-Request-ID")

    # Log the full exception
    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        path=str(request.url.path),
        method=request.method,
        error_type=type(exc).__name__,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": ErrorCode.SRV_INTERNAL_ERROR.value,
                "message": "An unexpected error occurred",
            },
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def register_exception_handlers(app) -> None:
    """Register exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    logger.info("error_handlers_registered")
