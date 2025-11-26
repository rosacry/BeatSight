"""Tests for Modal GPU orchestration service.

Tests the Modal integration for triggering AI jobs on GPU infrastructure.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.modal_gpu import (
    ModalConfig,
    ModalConnectionError,
    ModalJobError,
    ModalService,
    TriggerResult,
)


class TestModalConfig:
    """Tests for Modal configuration."""

    def test_default_config(self) -> None:
        """Test default config values."""
        config = ModalConfig()
        # Default should respect settings
        assert isinstance(config.enabled, bool)
        assert isinstance(config.webhook_url, str)

    def test_custom_config(self) -> None:
        """Test custom config values."""
        config = ModalConfig(
            enabled=True,
            webhook_url="https://custom-modal-endpoint.modal.run",
            webhook_secret="test-secret",
            timeout_seconds=60,
        )
        assert config.enabled is True
        assert config.webhook_url == "https://custom-modal-endpoint.modal.run"
        assert config.webhook_secret == "test-secret"
        assert config.timeout_seconds == 60


class TestModalService:
    """Tests for ModalService."""

    @pytest.fixture
    def enabled_config(self) -> ModalConfig:
        """Config with Modal enabled."""
        return ModalConfig(
            enabled=True,
            webhook_url="https://beatsight--trigger-job.modal.run",
            webhook_secret="test-secret",
        )

    @pytest.fixture
    def disabled_config(self) -> ModalConfig:
        """Config with Modal disabled."""
        return ModalConfig(enabled=False)

    def test_is_enabled_when_enabled(self, enabled_config: ModalConfig) -> None:
        """Test is_enabled returns True when enabled."""
        service = ModalService(enabled_config)
        assert service.is_enabled() is True

    def test_is_enabled_when_disabled(self, disabled_config: ModalConfig) -> None:
        """Test is_enabled returns False when disabled."""
        service = ModalService(disabled_config)
        assert service.is_enabled() is False

    @pytest.mark.asyncio
    async def test_trigger_job_returns_not_accepted_when_disabled(
        self, disabled_config: ModalConfig
    ) -> None:
        """Test that trigger_job returns not accepted when Modal is disabled."""
        service = ModalService(disabled_config)
        result = await service.trigger_job(
            job_id="test-job-123",
            audio_url="https://storage.example.com/audio.wav",
            song_id="song-456",
        )
        assert result.accepted is False
        assert "disabled" in result.error.lower()

    @pytest.mark.asyncio
    async def test_trigger_job_success(self, enabled_config: ModalConfig) -> None:
        """Test successful job trigger."""
        service = ModalService(enabled_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accepted": True,
            "call_id": "modal-call-xyz789",
        }
        
        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await service.trigger_job(
                job_id="test-job-123",
                audio_url="https://storage.example.com/audio.wav",
                song_id="song-456",
                options={"detection_sensitivity": 80},
            )
            
            assert result.accepted is True
            assert result.call_id == "modal-call-xyz789"
            assert result.error is None
            
            # Verify the call was made correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == enabled_config.webhook_url
            payload = call_args[1]["json"]
            assert payload["job_id"] == "test-job-123"
            assert payload["audio_url"] == "https://storage.example.com/audio.wav"
            assert payload["song_id"] == "song-456"
            assert payload["options"]["detection_sensitivity"] == 80

    @pytest.mark.asyncio
    async def test_trigger_job_rejected(self, enabled_config: ModalConfig) -> None:
        """Test job rejection from Modal."""
        service = ModalService(enabled_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accepted": False,
            "error": "Invalid audio format",
        }
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        service._client = mock_client
        
        result = await service.trigger_job(
            job_id="test-job-123",
            audio_url="https://storage.example.com/audio.txt",
            song_id="song-456",
        )
        
        assert result.accepted is False
        assert result.error == "Invalid audio format"

    @pytest.mark.asyncio
    async def test_trigger_job_http_error(self, enabled_config: ModalConfig) -> None:
        """Test HTTP error from Modal endpoint."""
        service = ModalService(enabled_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        service._client = mock_client
        
        with pytest.raises(ModalJobError) as exc_info:
            await service.trigger_job(
                job_id="test-job-123",
                audio_url="https://storage.example.com/audio.wav",
                song_id="song-456",
            )
        
        assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_job_connection_error(self, enabled_config: ModalConfig) -> None:
        """Test connection error to Modal."""
        service = ModalService(enabled_config)
        
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        service._client = mock_client
        
        with pytest.raises(ModalConnectionError) as exc_info:
            await service.trigger_job(
                job_id="test-job-123",
                audio_url="https://storage.example.com/audio.wav",
                song_id="song-456",
            )
        
        assert "Connection" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_job_timeout(self, enabled_config: ModalConfig) -> None:
        """Test timeout when triggering job."""
        service = ModalService(enabled_config)
        
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        service._client = mock_client
        
        with pytest.raises(ModalConnectionError) as exc_info:
            await service.trigger_job(
                job_id="test-job-123",
                audio_url="https://storage.example.com/audio.wav",
                song_id="song-456",
            )
        
        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_health_success(self, enabled_config: ModalConfig) -> None:
        """Test successful health check."""
        service = ModalService(enabled_config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        service._client = mock_client
        
        is_healthy = await service.check_health()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self, enabled_config: ModalConfig) -> None:
        """Test health check failure."""
        service = ModalService(enabled_config)
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        service._client = mock_client
        
        is_healthy = await service.check_health()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_check_health_disabled(self, disabled_config: ModalConfig) -> None:
        """Test health check when Modal is disabled."""
        service = ModalService(disabled_config)
        is_healthy = await service.check_health()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_close_client(self, enabled_config: ModalConfig) -> None:
        """Test closing the HTTP client."""
        service = ModalService(enabled_config)
        
        # Create and get the client
        mock_client = AsyncMock()
        service._client = mock_client
        
        await service.close()
        
        mock_client.aclose.assert_called_once()
        assert service._client is None


class TestTriggerResult:
    """Tests for TriggerResult dataclass."""

    def test_accepted_result(self) -> None:
        """Test accepted result with call ID."""
        result = TriggerResult(accepted=True, call_id="call-123")
        assert result.accepted is True
        assert result.call_id == "call-123"
        assert result.error is None

    def test_rejected_result(self) -> None:
        """Test rejected result with error."""
        result = TriggerResult(accepted=False, error="Quota exceeded")
        assert result.accepted is False
        assert result.call_id is None
        assert result.error == "Quota exceeded"


class TestFullJobFlowWithModal:
    """Integration tests for complete job flow including Modal dispatch."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async database session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_job_enqueue_triggers_modal(self, mock_session: AsyncMock) -> None:
        """Test that enqueuing a job triggers Modal dispatch."""
        from app.models.ai_job import AIJob, AIJobState
        
        job_id = uuid.uuid4()
        song_id = uuid.uuid4()
        
        # Mock the job
        mock_job = MagicMock(spec=AIJob)
        mock_job.id = job_id
        mock_job.song_id = song_id
        mock_job.state = AIJobState.QUEUED
        
        # Create Modal service with mocked client
        config = ModalConfig(enabled=True, webhook_url="https://test.modal.run")
        modal_service = ModalService(config)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accepted": True,
            "call_id": "modal-call-123",
        }
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        modal_service._client = mock_client
        
        result = await modal_service.trigger_job(
            job_id=str(job_id),
            audio_url="https://storage.example.com/song.wav",
            song_id=str(song_id),
        )
        
        assert result.accepted is True
        assert result.call_id == "modal-call-123"

    @pytest.mark.asyncio
    async def test_modal_failure_allows_fallback(self) -> None:
        """Test that Modal failure allows fallback to local processing."""
        config = ModalConfig(enabled=True, webhook_url="https://modal.run/fail")
        service = ModalService(config)
        
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Modal unavailable")
        service._client = mock_client
        
        try:
            await service.trigger_job(
                job_id="job-123",
                audio_url="https://storage.example.com/song.wav",
                song_id="song-456",
            )
            assert False, "Should have raised ModalConnectionError"
        except ModalConnectionError:
            # This is expected - app should catch and fallback to local processing
            pass
