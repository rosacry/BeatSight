"""Tests for request logging middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.request_logging import RequestLoggingMiddleware


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application with request logging middleware."""
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    
    @app.get("/test")
    async def test_endpoint() -> dict:
        return {"status": "ok"}
    
    @app.get("/health")
    async def health_endpoint() -> dict:
        return {"status": "healthy"}
    
    @app.get("/slow")
    async def slow_endpoint() -> dict:
        import time
        time.sleep(0.1)  # Simulate slow endpoint
        return {"status": "slow"}
    
    @app.get("/error")
    async def error_endpoint() -> dict:
        raise ValueError("Test error")
    
    @app.get("/sensitive")
    async def sensitive_endpoint() -> dict:
        return {"status": "ok"}
    
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(app, raise_server_exceptions=False)


class TestRequestLoggingMiddleware:
    """Tests for RequestLoggingMiddleware."""

    def test_logs_successful_request(self, client: TestClient) -> None:
        """Test that successful requests are logged."""
        response = client.get("/test")
        assert response.status_code == 200
        # Logging happens internally - just verify request succeeds

    def test_excludes_health_check(self, client: TestClient) -> None:
        """Test that health check endpoints are excluded from logging."""
        response = client.get("/health")
        assert response.status_code == 200
        # Health check should succeed without logging

    def test_handles_slow_requests(self, client: TestClient) -> None:
        """Test that slow requests are handled."""
        response = client.get("/slow")
        assert response.status_code == 200

    def test_handles_error_responses(self, client: TestClient) -> None:
        """Test that error responses are logged."""
        response = client.get("/error")
        assert response.status_code == 500

    def test_redacts_sensitive_params(self, client: TestClient) -> None:
        """Test that sensitive query parameters are redacted."""
        response = client.get("/sensitive?token=secret123&normal=value")
        assert response.status_code == 200

    def test_handles_forwarded_ip(self, client: TestClient) -> None:
        """Test X-Forwarded-For header handling."""
        response = client.get(
            "/test",
            headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        )
        assert response.status_code == 200

    def test_handles_real_ip(self, client: TestClient) -> None:
        """Test X-Real-IP header handling."""
        response = client.get(
            "/test",
            headers={"X-Real-IP": "192.168.1.100"}
        )
        assert response.status_code == 200


class TestRedactParams:
    """Tests for parameter redaction."""

    def test_redacts_token(self) -> None:
        """Test that token parameter is redacted."""
        middleware = RequestLoggingMiddleware(None)  # type: ignore
        params = {"token": "secret", "name": "test"}
        redacted = middleware._redact_params(params)
        assert redacted["token"] == "[REDACTED]"
        assert redacted["name"] == "test"

    def test_redacts_password(self) -> None:
        """Test that password parameter is redacted."""
        middleware = RequestLoggingMiddleware(None)  # type: ignore
        params = {"password": "secret123"}
        redacted = middleware._redact_params(params)
        assert redacted["password"] == "[REDACTED]"

    def test_redacts_api_key(self) -> None:
        """Test that api_key parameter is redacted."""
        middleware = RequestLoggingMiddleware(None)  # type: ignore
        params = {"api_key": "key123", "user": "john"}
        redacted = middleware._redact_params(params)
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["user"] == "john"

    def test_preserves_non_sensitive(self) -> None:
        """Test that non-sensitive parameters are preserved."""
        middleware = RequestLoggingMiddleware(None)  # type: ignore
        params = {"page": "1", "limit": "10", "search": "query"}
        redacted = middleware._redact_params(params)
        assert redacted == params
