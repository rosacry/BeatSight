"""Tests for HTTP client utilities."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.utils.http_client import (
    HTTPClient,
    HTTPClientConfig,
    HTTPConnectionError,
    HTTPError,
    HTTPMethod,
    HTTPResponse,
    HTTPTimeoutError,
    RateLimitedError,
    create_client,
    delete,
    get,
    patch as http_patch,
    post,
    put,
    request,
)


class TestHTTPMethod:
    """Tests for HTTPMethod enum."""

    def test_methods(self):
        """Test HTTP method values."""
        assert HTTPMethod.GET.value == "GET"
        assert HTTPMethod.POST.value == "POST"
        assert HTTPMethod.PUT.value == "PUT"
        assert HTTPMethod.PATCH.value == "PATCH"
        assert HTTPMethod.DELETE.value == "DELETE"
        assert HTTPMethod.HEAD.value == "HEAD"
        assert HTTPMethod.OPTIONS.value == "OPTIONS"


class TestHTTPError:
    """Tests for HTTP error classes."""

    def test_http_error(self):
        """Test HTTPError."""
        error = HTTPError(
            "Test error",
            status_code=404,
            response_body={"error": "Not found"},
            url="https://example.com",
        )
        assert str(error) == "Test error"
        assert error.status_code == 404
        assert error.response_body == {"error": "Not found"}
        assert error.url == "https://example.com"

    def test_http_timeout_error(self):
        """Test HTTPTimeoutError."""
        error = HTTPTimeoutError("Timeout", url="https://example.com")
        assert isinstance(error, HTTPError)
        assert str(error) == "Timeout"

    def test_http_connection_error(self):
        """Test HTTPConnectionError."""
        error = HTTPConnectionError("Connection failed", url="https://example.com")
        assert isinstance(error, HTTPError)

    def test_rate_limited_error(self):
        """Test RateLimitedError."""
        error = RateLimitedError(
            "Rate limited",
            status_code=429,
            retry_after=60,
            url="https://example.com",
        )
        assert isinstance(error, HTTPError)
        assert error.status_code == 429
        assert error.retry_after == 60


class TestHTTPClientConfig:
    """Tests for HTTPClientConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = HTTPClientConfig()
        assert config.base_url is None
        assert config.timeout == 30.0
        assert config.connect_timeout == 10.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0
        assert 429 in config.retry_on_status
        assert 503 in config.retry_on_status
        assert config.follow_redirects is True
        assert config.verify_ssl is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = HTTPClientConfig(
            base_url="https://api.example.com",
            timeout=60.0,
            max_retries=5,
            headers={"X-API-Key": "secret"},
        )
        assert config.base_url == "https://api.example.com"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.headers == {"X-API-Key": "secret"}


class TestHTTPResponse:
    """Tests for HTTPResponse."""

    def test_basic_response(self):
        """Test basic response properties."""
        response = HTTPResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b'{"name": "test"}',
            elapsed=0.5,
            url="https://example.com/api",
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert response.elapsed == 0.5
        assert response.url == "https://example.com/api"

    def test_text_property(self):
        """Test text property."""
        response = HTTPResponse(
            status_code=200,
            headers={},
            body=b"Hello World",
            elapsed=0.1,
            url="https://example.com",
        )
        assert response.text == "Hello World"
        # Cached
        assert response.text == "Hello World"

    def test_json_data_property(self):
        """Test json_data property."""
        response = HTTPResponse(
            status_code=200,
            headers={},
            body=b'{"key": "value", "count": 42}',
            elapsed=0.1,
            url="https://example.com",
        )
        assert response.json_data == {"key": "value", "count": 42}
        # Cached
        assert response.json_data == {"key": "value", "count": 42}

    def test_json_data_invalid(self):
        """Test json_data with invalid JSON."""
        response = HTTPResponse(
            status_code=200,
            headers={},
            body=b"not json",
            elapsed=0.1,
            url="https://example.com",
        )
        assert response.json_data is None

    def test_ok_property(self):
        """Test ok property."""
        for status in [200, 201, 204, 299]:
            response = HTTPResponse(
                status_code=status,
                headers={},
                body=b"",
                elapsed=0.1,
                url="https://example.com",
            )
            assert response.ok is True

        for status in [400, 404, 500]:
            response = HTTPResponse(
                status_code=status,
                headers={},
                body=b"",
                elapsed=0.1,
                url="https://example.com",
            )
            assert response.ok is False

    def test_is_redirect_property(self):
        """Test is_redirect property."""
        for status in [301, 302, 307, 308]:
            response = HTTPResponse(
                status_code=status,
                headers={},
                body=b"",
                elapsed=0.1,
                url="https://example.com",
            )
            assert response.is_redirect is True

    def test_is_client_error_property(self):
        """Test is_client_error property."""
        for status in [400, 401, 403, 404, 422]:
            response = HTTPResponse(
                status_code=status,
                headers={},
                body=b"",
                elapsed=0.1,
                url="https://example.com",
            )
            assert response.is_client_error is True

    def test_is_server_error_property(self):
        """Test is_server_error property."""
        for status in [500, 502, 503, 504]:
            response = HTTPResponse(
                status_code=status,
                headers={},
                body=b"",
                elapsed=0.1,
                url="https://example.com",
            )
            assert response.is_server_error is True

    def test_raise_for_status_ok(self):
        """Test raise_for_status with OK status."""
        response = HTTPResponse(
            status_code=200,
            headers={},
            body=b"",
            elapsed=0.1,
            url="https://example.com",
        )
        response.raise_for_status()  # Should not raise

    def test_raise_for_status_error(self):
        """Test raise_for_status with error status."""
        response = HTTPResponse(
            status_code=404,
            headers={},
            body=b'{"error": "Not found"}',
            elapsed=0.1,
            url="https://example.com/api",
        )
        with pytest.raises(HTTPError) as exc_info:
            response.raise_for_status()
        assert exc_info.value.status_code == 404

    def test_raise_for_status_rate_limited(self):
        """Test raise_for_status with 429 status."""
        response = HTTPResponse(
            status_code=429,
            headers={"retry-after": "60"},
            body=b"",
            elapsed=0.1,
            url="https://example.com",
        )
        with pytest.raises(RateLimitedError) as exc_info:
            response.raise_for_status()
        assert exc_info.value.retry_after == 60


class TestHTTPClient:
    """Tests for HTTPClient."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        client = HTTPClient()
        async with client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_init_with_config(self):
        """Test initialization with config."""
        config = HTTPClientConfig(
            base_url="https://api.example.com",
            timeout=60.0,
        )
        client = HTTPClient(config=config)
        assert client.config.base_url == "https://api.example.com"
        assert client.config.timeout == 60.0

    @pytest.mark.asyncio
    async def test_init_with_kwargs(self):
        """Test initialization with kwargs."""
        client = HTTPClient(
            base_url="https://api.example.com",
            timeout=45.0,
            max_retries=5,
        )
        assert client.config.base_url == "https://api.example.com"
        assert client.config.timeout == 45.0
        assert client.config.max_retries == 5

    @pytest.mark.asyncio
    async def test_successful_get_request(self):
        """Test successful GET request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = b'{"success": true}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.get("https://example.com/api")
            
            assert response.status_code == 200
            assert response.json_data == {"success": True}
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_post_request(self):
        """Test successful POST request."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.content = b'{"id": 1}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.post(
                    "https://example.com/api",
                    json={"name": "test"},
                )
            
            assert response.status_code == 201
            assert response.json_data == {"id": 1}

    @pytest.mark.asyncio
    async def test_request_with_headers(self):
        """Test request with custom headers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b""
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient(headers={"Authorization": "Bearer token"}) as client:
                await client.get(
                    "https://example.com/api",
                    headers={"X-Custom": "value"},
                )
            
            # Check that request was called with custom headers
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["headers"] == {"X-Custom": "value"}

    @pytest.mark.asyncio
    async def test_request_with_params(self):
        """Test request with query parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b""
        mock_response.url = "https://example.com/api?page=1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                await client.get(
                    "https://example.com/api",
                    params={"page": 1, "limit": 10},
                )
            
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["params"] == {"page": 1, "limit": 10}

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test timeout error handling."""
        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Timeout")
            
            async with HTTPClient(max_retries=0) as client:
                with pytest.raises(HTTPTimeoutError):
                    await client.get("https://example.com/api")

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test connection error handling."""
        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = httpx.ConnectError("Connection refused")
            
            async with HTTPClient(max_retries=0) as client:
                with pytest.raises(HTTPConnectionError):
                    await client.get("https://example.com/api")

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self):
        """Test retry on server error."""
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        mock_response_503.headers = {}
        mock_response_503.content = b""
        mock_response_503.url = "https://example.com/api"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.headers = {}
        mock_response_200.content = b'{"success": true}'
        mock_response_200.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_response_503, mock_response_200]
            
            config = HTTPClientConfig(retry_delay=0.01, max_retries=2)
            async with HTTPClient(config=config) as client:
                response = await client.get("https://example.com/api")
            
            assert response.status_code == 200
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry on timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b""
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                httpx.TimeoutException("Timeout"),
                mock_response,
            ]
            
            config = HTTPClientConfig(retry_delay=0.01, max_retries=2)
            async with HTTPClient(config=config) as client:
                response = await client.get("https://example.com/api")
            
            assert response.status_code == 200
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_raise_for_status_on_request(self):
        """Test raise_for_status parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.content = b'{"error": "Not found"}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient(max_retries=0) as client:
                with pytest.raises(HTTPError) as exc_info:
                    await client.get(
                        "https://example.com/api",
                        raise_for_status=True,
                    )
                assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_put_request(self):
        """Test PUT request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"updated": true}'
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.put(
                    "https://example.com/api/1",
                    json={"name": "updated"},
                )
            
            assert response.status_code == 200
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["method"] == "PUT"

    @pytest.mark.asyncio
    async def test_patch_request(self):
        """Test PATCH request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"patched": true}'
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.patch(
                    "https://example.com/api/1",
                    json={"field": "value"},
                )
            
            assert response.status_code == 200
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["method"] == "PATCH"

    @pytest.mark.asyncio
    async def test_delete_request(self):
        """Test DELETE request."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.content = b""
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.delete("https://example.com/api/1")
            
            assert response.status_code == 204
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_rate_limit_retry_with_retry_after(self):
        """Test retry with Retry-After header."""
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"retry-after": "1"}
        mock_response_429.content = b""
        mock_response_429.url = "https://example.com/api"

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.headers = {}
        mock_response_200.content = b"{}"
        mock_response_200.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_response_429, mock_response_200]
            
            config = HTTPClientConfig(retry_delay=0.01, max_retries=2)
            async with HTTPClient(config=config) as client:
                response = await client.get("https://example.com/api")
            
            assert response.status_code == 200


class TestCreateClient:
    """Tests for create_client function."""

    def test_create_with_defaults(self):
        """Test creating client with defaults."""
        client = create_client()
        assert client.config.base_url is None
        assert client.config.timeout == 30.0

    def test_create_with_base_url(self):
        """Test creating client with base URL."""
        client = create_client("https://api.example.com")
        assert client.config.base_url == "https://api.example.com"

    def test_create_with_options(self):
        """Test creating client with options."""
        client = create_client(
            "https://api.example.com",
            timeout=60.0,
            max_retries=5,
            headers={"Authorization": "Bearer token"},
        )
        assert client.config.timeout == 60.0
        assert client.config.max_retries == 5
        assert client.config.headers == {"Authorization": "Bearer token"}


class TestConvenienceFunctions:
    """Tests for convenience request functions."""

    @pytest.mark.asyncio
    async def test_get_function(self):
        """Test get() convenience function."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{"key": "value"}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await get("https://example.com/api")
            
            assert response.status_code == 200
            assert response.json_data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_post_function(self):
        """Test post() convenience function."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.content = b'{"id": 1}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await post(
                "https://example.com/api",
                json={"name": "test"},
            )
            
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_put_function(self):
        """Test put() convenience function."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await put(
                "https://example.com/api/1",
                json={"name": "updated"},
            )
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_patch_function(self):
        """Test patch() convenience function (http_patch)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await http_patch(
                "https://example.com/api/1",
                json={"field": "value"},
            )
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_function(self):
        """Test delete() convenience function."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}
        mock_response.content = b''
        mock_response.url = "https://example.com/api/1"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await delete("https://example.com/api/1")
            
            assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_request_function(self):
        """Test request() convenience function."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            response = await request(
                HTTPMethod.OPTIONS,
                "https://example.com/api",
            )
            
            assert response.status_code == 200


class TestHTTPMethodString:
    """Tests for using string methods."""

    @pytest.mark.asyncio
    async def test_string_method(self):
        """Test using string instead of HTTPMethod enum."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b'{}'
        mock_response.url = "https://example.com/api"

        with patch.object(httpx.AsyncClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            async with HTTPClient() as client:
                response = await client.request("get", "https://example.com/api")
            
            assert response.status_code == 200
            call_kwargs = mock_request.call_args.kwargs
            assert call_kwargs["method"] == "GET"
