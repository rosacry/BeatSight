"""Tests for API versioning utilities."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.utils.api_versioning import (
    APIVersion,
    deprecated,
    get_api_version,
    require_version,
)


class TestAPIVersion:
    """Tests for APIVersion enum."""

    def test_current_version(self) -> None:
        """Test current version is V1."""
        assert APIVersion.current() == APIVersion.V1

    def test_supported_versions(self) -> None:
        """Test supported versions list."""
        supported = APIVersion.supported()
        assert APIVersion.V1 in supported

    def test_version_values(self) -> None:
        """Test version string values."""
        assert APIVersion.V1.value == "v1"
        assert APIVersion.V2.value == "v2"


class TestGetAPIVersion:
    """Tests for get_api_version function."""

    def test_default_version(self) -> None:
        """Test default version when no header provided."""
        version = get_api_version(None, None)
        assert version == APIVersion.current()

    def test_accept_version_header(self) -> None:
        """Test Accept-Version header parsing."""
        version = get_api_version("v1", None)
        assert version == APIVersion.V1

    def test_x_api_version_header(self) -> None:
        """Test X-API-Version header parsing."""
        version = get_api_version(None, "v1")
        assert version == APIVersion.V1

    def test_accept_version_takes_precedence(self) -> None:
        """Test Accept-Version takes precedence over X-API-Version."""
        version = get_api_version("v1", "v2")
        assert version == APIVersion.V1

    def test_unknown_version_defaults_to_current(self) -> None:
        """Test unknown version falls back to current."""
        version = get_api_version("v99", None)
        assert version == APIVersion.current()


class TestDeprecatedDecorator:
    """Tests for deprecated decorator."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app."""
        app = FastAPI()

        @app.get("/deprecated")
        @deprecated(
            sunset_date=date(2025, 12, 31),
            replacement="/api/v2/new-endpoint",
            message="Please migrate to the new endpoint",
        )
        async def deprecated_endpoint() -> dict:
            return {"status": "ok"}

        @app.get("/deprecated-no-replacement")
        @deprecated(sunset_date=date(2025, 6, 1))
        async def deprecated_no_replacement() -> dict:
            return {"data": "value"}

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_deprecated_endpoint_returns_data(self, client: TestClient) -> None:
        """Test deprecated endpoint still returns data."""
        response = client.get("/deprecated")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_deprecated_endpoint_has_deprecation_header(
        self, client: TestClient
    ) -> None:
        """Test deprecated endpoint has Deprecation header."""
        response = client.get("/deprecated")
        assert "Deprecation" in response.headers
        assert response.headers["Deprecation"] == "2025-12-31"

    def test_deprecated_endpoint_has_link_header(self, client: TestClient) -> None:
        """Test deprecated endpoint has Link header with replacement."""
        response = client.get("/deprecated")
        assert "Link" in response.headers
        assert 'rel="successor-version"' in response.headers["Link"]

    def test_deprecated_endpoint_has_notice_header(self, client: TestClient) -> None:
        """Test deprecated endpoint has custom notice header."""
        response = client.get("/deprecated")
        assert "X-Deprecation-Notice" in response.headers

    def test_deprecated_without_replacement(self, client: TestClient) -> None:
        """Test deprecated endpoint without replacement URL."""
        response = client.get("/deprecated-no-replacement")
        assert response.status_code == 200
        assert "Deprecation" in response.headers
        # Link header should not be present without replacement
        assert "Link" not in response.headers or "successor-version" not in response.headers.get("Link", "")


class TestRequireVersionDecorator:
    """Tests for require_version decorator."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app."""
        app = FastAPI()

        @app.get("/v2-only")
        @require_version(APIVersion.V2)
        async def v2_only_endpoint(api_version: APIVersion = APIVersion.V1) -> dict:
            return {"version": api_version.value}

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_require_version_rejects_old_version(self, client: TestClient) -> None:
        """Test endpoint rejects old API version."""
        response = client.get("/v2-only")
        assert response.status_code == 400
        assert "version" in response.json()["detail"].lower()
