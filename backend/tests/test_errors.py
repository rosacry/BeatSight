"""Tests for standardized error handling utilities.

Tests error codes, custom exceptions, helper functions,
and exception handlers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.utils.errors import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    PaymentError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
    api_error_handler,
    http_exception_handler,
    raise_auth_error,
    raise_not_found,
    raise_payment_error,
    raise_permission_error,
    raise_validation_error,
    unhandled_exception_handler,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_auth_error_codes_exist(self):
        """Test authentication error codes exist."""
        assert ErrorCode.AUTH_INVALID_TOKEN.value == "AUTH_INVALID_TOKEN"
        assert ErrorCode.AUTH_EXPIRED_TOKEN.value == "AUTH_EXPIRED_TOKEN"
        assert ErrorCode.AUTH_ACCOUNT_LOCKED.value == "AUTH_ACCOUNT_LOCKED"
        assert ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS.value == "AUTH_INSUFFICIENT_PERMISSIONS"

    def test_validation_error_codes_exist(self):
        """Test validation error codes exist."""
        assert ErrorCode.VAL_INVALID_INPUT.value == "VAL_INVALID_INPUT"
        assert ErrorCode.VAL_PASSWORD_TOO_WEAK.value == "VAL_PASSWORD_TOO_WEAK"
        assert ErrorCode.VAL_FILE_TOO_LARGE.value == "VAL_FILE_TOO_LARGE"

    def test_resource_error_codes_exist(self):
        """Test resource error codes exist."""
        assert ErrorCode.RES_NOT_FOUND.value == "RES_NOT_FOUND"
        assert ErrorCode.RES_SONG_NOT_FOUND.value == "RES_SONG_NOT_FOUND"
        assert ErrorCode.RES_USER_NOT_FOUND.value == "RES_USER_NOT_FOUND"
        assert ErrorCode.RES_ALREADY_EXISTS.value == "RES_ALREADY_EXISTS"

    def test_rate_limit_error_codes_exist(self):
        """Test rate limit error codes exist."""
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == "RATE_LIMIT_EXCEEDED"
        assert ErrorCode.RATE_QUOTA_EXCEEDED.value == "RATE_QUOTA_EXCEEDED"

    def test_payment_error_codes_exist(self):
        """Test payment error codes exist."""
        assert ErrorCode.PAY_INSUFFICIENT_CREDITS.value == "PAY_INSUFFICIENT_CREDITS"
        assert ErrorCode.PAY_PAYMENT_FAILED.value == "PAY_PAYMENT_FAILED"
        assert ErrorCode.PAY_STRIPE_ERROR.value == "PAY_STRIPE_ERROR"

    def test_ai_error_codes_exist(self):
        """Test AI error codes exist."""
        assert ErrorCode.AI_JOB_FAILED.value == "AI_JOB_FAILED"
        assert ErrorCode.AI_MODEL_UNAVAILABLE.value == "AI_MODEL_UNAVAILABLE"
        assert ErrorCode.AI_QUEUE_FULL.value == "AI_QUEUE_FULL"


class TestAPIError:
    """Tests for base APIError exception."""

    def test_api_error_basic(self):
        """Test basic APIError creation."""
        error = APIError(
            message="Test error",
            code=ErrorCode.SRV_INTERNAL_ERROR,
            status_code=500,
        )
        assert error.message == "Test error"
        assert error.code == "SRV_INTERNAL_ERROR"
        assert error.status_code == 500

    def test_api_error_with_details(self):
        """Test APIError with details."""
        error = APIError(
            message="Test error",
            code=ErrorCode.RES_NOT_FOUND,
            status_code=404,
            details={"resource_id": "abc123"},
        )
        assert error.details == {"resource_id": "abc123"}

    def test_api_error_to_response(self):
        """Test APIError to_response method."""
        error = APIError(
            message="Test error",
            code=ErrorCode.VAL_INVALID_INPUT,
            status_code=400,
            details={"field": "email"},
        )
        response = error.to_response(request_id="req_123")

        assert response["error"]["code"] == "VAL_INVALID_INPUT"
        assert response["error"]["message"] == "Test error"
        assert response["error"]["details"] == {"field": "email"}
        assert response["request_id"] == "req_123"
        assert "timestamp" in response

    def test_api_error_with_string_code(self):
        """Test APIError accepts string code."""
        error = APIError(
            message="Custom error",
            code="CUSTOM_ERROR_CODE",
            status_code=400,
        )
        assert error.code == "CUSTOM_ERROR_CODE"


class TestNotFoundError:
    """Tests for NotFoundError exception."""

    def test_not_found_error_defaults(self):
        """Test NotFoundError default values."""
        error = NotFoundError()
        assert error.status_code == 404
        assert error.code == "RES_NOT_FOUND"
        assert error.message == "Resource not found"

    def test_not_found_error_custom_message(self):
        """Test NotFoundError with custom message."""
        error = NotFoundError(
            message="Song not found",
            code=ErrorCode.RES_SONG_NOT_FOUND,
            details={"song_id": "abc123"},
        )
        assert error.message == "Song not found"
        assert error.code == "RES_SONG_NOT_FOUND"
        assert error.details == {"song_id": "abc123"}


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_validation_error_defaults(self):
        """Test ValidationError default values."""
        error = ValidationError()
        assert error.status_code == 422
        assert error.code == "VAL_INVALID_INPUT"

    def test_validation_error_with_field(self):
        """Test ValidationError with field."""
        error = ValidationError(
            message="Email is required",
            field="email",
        )
        assert error.message == "Email is required"
        assert error.details["field"] == "email"


class TestAuthenticationError:
    """Tests for AuthenticationError exception."""

    def test_auth_error_defaults(self):
        """Test AuthenticationError default values."""
        error = AuthenticationError()
        assert error.status_code == 401
        assert error.code == "AUTH_INVALID_TOKEN"

    def test_auth_error_has_www_authenticate_header(self):
        """Test AuthenticationError has WWW-Authenticate header."""
        error = AuthenticationError()
        assert error.headers == {"WWW-Authenticate": "Bearer"}


class TestAuthorizationError:
    """Tests for AuthorizationError exception."""

    def test_authz_error_defaults(self):
        """Test AuthorizationError default values."""
        error = AuthorizationError()
        assert error.status_code == 403
        assert error.code == "AUTH_INSUFFICIENT_PERMISSIONS"


class TestConflictError:
    """Tests for ConflictError exception."""

    def test_conflict_error_defaults(self):
        """Test ConflictError default values."""
        error = ConflictError()
        assert error.status_code == 409
        assert error.code == "RES_CONFLICT"


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_rate_limit_error_defaults(self):
        """Test RateLimitError default values."""
        error = RateLimitError()
        assert error.status_code == 429
        assert error.code == "RATE_LIMIT_EXCEEDED"

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry_after."""
        error = RateLimitError(retry_after=60)
        assert error.headers["Retry-After"] == "60"
        assert error.details["retry_after"] == 60


class TestPaymentError:
    """Tests for PaymentError exception."""

    def test_payment_error_defaults(self):
        """Test PaymentError default values."""
        error = PaymentError()
        assert error.status_code == 402
        assert error.code == "PAY_INSUFFICIENT_CREDITS"


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError exception."""

    def test_service_unavailable_defaults(self):
        """Test ServiceUnavailableError default values."""
        error = ServiceUnavailableError()
        assert error.status_code == 503
        assert error.code == "SRV_SERVICE_UNAVAILABLE"

    def test_service_unavailable_with_retry_after(self):
        """Test ServiceUnavailableError with retry_after."""
        error = ServiceUnavailableError(retry_after=300)
        assert error.headers["Retry-After"] == "300"


class TestRaiseNotFound:
    """Tests for raise_not_found helper."""

    def test_raise_not_found_song(self):
        """Test raise_not_found for song."""
        with pytest.raises(NotFoundError) as exc_info:
            raise_not_found("song", uuid4())

        error = exc_info.value
        assert error.code == "RES_SONG_NOT_FOUND"
        assert "song_id" in error.details

    def test_raise_not_found_user(self):
        """Test raise_not_found for user."""
        with pytest.raises(NotFoundError) as exc_info:
            raise_not_found("user", "user123")

        error = exc_info.value
        assert error.code == "RES_USER_NOT_FOUND"

    def test_raise_not_found_map(self):
        """Test raise_not_found for map."""
        with pytest.raises(NotFoundError) as exc_info:
            raise_not_found("map")

        error = exc_info.value
        assert error.code == "RES_MAP_NOT_FOUND"

    def test_raise_not_found_generic(self):
        """Test raise_not_found for unknown resource."""
        with pytest.raises(NotFoundError) as exc_info:
            raise_not_found("widget")

        error = exc_info.value
        assert error.code == "RES_NOT_FOUND"
        assert "Widget not found" in error.message

    def test_raise_not_found_custom_message(self):
        """Test raise_not_found with custom message."""
        with pytest.raises(NotFoundError) as exc_info:
            raise_not_found("song", None, "This song has been deleted")

        error = exc_info.value
        assert error.message == "This song has been deleted"


class TestRaiseValidationError:
    """Tests for raise_validation_error helper."""

    def test_raise_validation_error_basic(self):
        """Test raise_validation_error basic."""
        with pytest.raises(ValidationError) as exc_info:
            raise_validation_error("Invalid email format")

        assert exc_info.value.message == "Invalid email format"

    def test_raise_validation_error_with_field(self):
        """Test raise_validation_error with field."""
        with pytest.raises(ValidationError) as exc_info:
            raise_validation_error("Email is required", field="email")

        error = exc_info.value
        assert error.details["field"] == "email"


class TestRaiseAuthError:
    """Tests for raise_auth_error helper."""

    def test_raise_auth_error_default(self):
        """Test raise_auth_error default."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise_auth_error()

        assert exc_info.value.message == "Authentication required"

    def test_raise_auth_error_custom(self):
        """Test raise_auth_error custom message."""
        with pytest.raises(AuthenticationError) as exc_info:
            raise_auth_error("Token expired", ErrorCode.AUTH_EXPIRED_TOKEN)

        error = exc_info.value
        assert error.message == "Token expired"
        assert error.code == "AUTH_EXPIRED_TOKEN"


class TestRaisePermissionError:
    """Tests for raise_permission_error helper."""

    def test_raise_permission_error_default(self):
        """Test raise_permission_error default."""
        with pytest.raises(AuthorizationError) as exc_info:
            raise_permission_error()

        assert "permission" in exc_info.value.message.lower()

    def test_raise_permission_error_with_role(self):
        """Test raise_permission_error with required role."""
        with pytest.raises(AuthorizationError) as exc_info:
            raise_permission_error("Admin access required", required_role="admin")

        error = exc_info.value
        assert error.details["required_role"] == "admin"


class TestRaisePaymentError:
    """Tests for raise_payment_error helper."""

    def test_raise_payment_error_default(self):
        """Test raise_payment_error default."""
        with pytest.raises(PaymentError) as exc_info:
            raise_payment_error()

        assert exc_info.value.message == "Insufficient credits"

    def test_raise_payment_error_with_amounts(self):
        """Test raise_payment_error with amounts."""
        with pytest.raises(PaymentError) as exc_info:
            raise_payment_error(
                "Not enough credits for this operation",
                required=10,
                available=5,
            )

        error = exc_info.value
        assert error.details["required"] == 10
        assert error.details["available"] == 5


class TestExceptionHandlers:
    """Tests for exception handlers."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.headers.get.return_value = "req_test_123"
        request.url.path = "/api/test"
        request.method = "GET"
        return request

    @pytest.mark.asyncio
    async def test_api_error_handler(self, mock_request):
        """Test api_error_handler."""
        error = NotFoundError(
            message="Song not found",
            code=ErrorCode.RES_SONG_NOT_FOUND,
        )

        response = await api_error_handler(mock_request, error)

        assert response.status_code == 404
        body = response.body.decode()
        assert "RES_SONG_NOT_FOUND" in body
        assert "Song not found" in body

    @pytest.mark.asyncio
    async def test_http_exception_handler(self, mock_request):
        """Test http_exception_handler."""
        error = HTTPException(status_code=404, detail="Not found")

        response = await http_exception_handler(mock_request, error)

        assert response.status_code == 404
        body = response.body.decode()
        assert "RES_NOT_FOUND" in body

    @pytest.mark.asyncio
    async def test_unhandled_exception_handler(self, mock_request):
        """Test unhandled_exception_handler."""
        error = RuntimeError("Unexpected error")

        response = await unhandled_exception_handler(mock_request, error)

        assert response.status_code == 500
        body = response.body.decode()
        assert "SRV_INTERNAL_ERROR" in body
        # Should not expose internal error details
        assert "Unexpected error" not in body


class TestErrorResponseFormat:
    """Tests for error response format consistency."""

    def test_response_has_required_fields(self):
        """Test error response has required fields."""
        error = APIError(
            message="Test",
            code=ErrorCode.SRV_INTERNAL_ERROR,
            status_code=500,
        )
        response = error.to_response("req_123")

        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert "request_id" in response
        assert "timestamp" in response

    def test_response_timestamp_is_iso_format(self):
        """Test timestamp is ISO format."""
        error = APIError(
            message="Test",
            code=ErrorCode.SRV_INTERNAL_ERROR,
            status_code=500,
        )
        response = error.to_response()

        # Should be parseable as datetime
        timestamp = response["timestamp"]
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed is not None
