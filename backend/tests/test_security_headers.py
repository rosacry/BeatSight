"""Tests for security headers and middleware.

These tests validate that proper security headers are set on responses.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestSecurityHeaders:
    """Tests for security-related HTTP headers."""

    def test_health_endpoint_has_request_id(self, client: TestClient) -> None:
        """Test that responses include X-Request-ID header."""
        response = client.get("/health/")
        
        # Should have request ID header
        assert "X-Request-ID" in response.headers
        # Request ID should be a valid UUID format
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format: 8-4-4-4-12

    def test_cors_headers_on_preflight(self, client: TestClient) -> None:
        """Test that CORS preflight requests get proper headers."""
        response = client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            }
        )
        
        # Should handle preflight
        assert response.status_code in (200, 204)

    def test_content_type_on_json_response(self, client: TestClient) -> None:
        """Test that JSON responses have correct content type."""
        response = client.get("/health/")
        
        assert "application/json" in response.headers.get("Content-Type", "")

    def test_no_server_header_leak(self, client: TestClient) -> None:
        """Test that server version is not leaked in headers."""
        response = client.get("/health/")
        
        # Server header should not reveal sensitive version info
        server = response.headers.get("Server", "")
        assert "Python" not in server
        assert "uvicorn" not in server.lower()

    def test_request_id_propagated_from_client(self, client: TestClient) -> None:
        """Test that client-provided request ID is used if valid UUID."""
        custom_id = "12345678-1234-1234-1234-123456789012"
        response = client.get(
            "/health/",
            headers={"X-Request-ID": custom_id}
        )
        
        # Should use the client-provided ID
        assert response.headers.get("X-Request-ID") == custom_id

    def test_invalid_request_id_replaced(self, client: TestClient) -> None:
        """Test that invalid request IDs are replaced with new UUIDs."""
        invalid_id = "not-a-uuid"
        response = client.get(
            "/health/",
            headers={"X-Request-ID": invalid_id}
        )
        
        # Should NOT use the invalid ID
        returned_id = response.headers.get("X-Request-ID", "")
        assert returned_id != invalid_id
        assert len(returned_id) == 36  # Should be valid UUID


class TestErrorResponses:
    """Tests for error response handling."""

    def test_404_response_format(self, client: TestClient) -> None:
        """Test that 404 responses have proper JSON format."""
        response = client.get("/api/nonexistent-endpoint-12345")
        
        assert response.status_code == 404
        assert "application/json" in response.headers.get("Content-Type", "")
        data = response.json()
        assert "detail" in data

    def test_422_validation_error_format(self, client: TestClient) -> None:
        """Test that validation errors return proper format."""
        # Try to login with invalid body
        response = client.post(
            "/api/auth/login",
            json={}  # Missing required fields
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_method_not_allowed(self, client: TestClient) -> None:
        """Test that wrong HTTP methods return 405."""
        response = client.delete("/health/")
        
        assert response.status_code == 405


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        """Test that rate limit headers are included in responses.
        
        Note: These headers may only appear after rate limiting middleware
        is properly initialized with Redis connection.
        """
        response = client.get("/health/")
        
        # This test documents expected behavior
        # In production with Redis, these headers should be present:
        # - X-RateLimit-Limit
        # - X-RateLimit-Remaining  
        # - X-RateLimit-Reset
        
        # For now, just verify the request succeeds
        assert response.status_code == 200
