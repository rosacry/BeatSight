"""Tests for cloud storage service."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import (
    AudioStorage,
    BeatmapStorage,
    LocalStorageBackend,
    PresignedUrl,
    StorageConfig,
    StorageObject,
    create_storage_backend,
)


class TestStorageConfig:
    """Tests for StorageConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = StorageConfig()
        assert config.backend == "local"
        assert config.local_base_path == "./storage"
        assert config.s3_region == "us-east-1"

    def test_from_env(self) -> None:
        """Test loading from environment variables."""
        with patch.dict(os.environ, {
            "STORAGE_BACKEND": "s3",
            "AWS_S3_BUCKET": "test-bucket",
            "AWS_REGION": "eu-west-1",
        }):
            config = StorageConfig.from_env()
            assert config.backend == "s3"
            assert config.s3_bucket == "test-bucket"
            assert config.s3_region == "eu-west-1"


class TestLocalStorageBackend:
    """Tests for local filesystem storage."""

    @pytest.fixture
    def temp_dir(self) -> str:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def backend(self, temp_dir: str) -> LocalStorageBackend:
        """Create a local storage backend."""
        return LocalStorageBackend(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_bytes(self, backend: LocalStorageBackend) -> None:
        """Test uploading bytes."""
        data = b"Hello, World!"
        result = await backend.upload("test/hello.txt", data, "text/plain")
        
        assert result.key == "test/hello.txt"
        assert result.size == len(data)
        assert result.content_type == "text/plain"

    @pytest.mark.asyncio
    async def test_upload_with_metadata(self, backend: LocalStorageBackend) -> None:
        """Test uploading with metadata."""
        data = b"test data"
        metadata = {"song_id": "123", "version": "1"}
        result = await backend.upload("test.bin", data, "application/octet-stream", metadata)
        
        assert result.metadata == metadata

    @pytest.mark.asyncio
    async def test_download(self, backend: LocalStorageBackend) -> None:
        """Test downloading files."""
        data = b"Download test"
        await backend.upload("download/test.txt", data)
        
        result = await backend.download("download/test.txt")
        assert result == data

    @pytest.mark.asyncio
    async def test_download_not_found(self, backend: LocalStorageBackend) -> None:
        """Test downloading non-existent file."""
        with pytest.raises(FileNotFoundError):
            await backend.download("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_stream_download(self, backend: LocalStorageBackend) -> None:
        """Test streaming download."""
        data = b"A" * 10000
        await backend.upload("stream.bin", data)
        
        chunks = []
        async for chunk in backend.stream_download("stream.bin", chunk_size=1000):
            chunks.append(chunk)
        
        assert b"".join(chunks) == data
        assert len(chunks) == 10

    @pytest.mark.asyncio
    async def test_delete(self, backend: LocalStorageBackend) -> None:
        """Test deleting files."""
        await backend.upload("delete_me.txt", b"delete")
        
        assert await backend.exists("delete_me.txt")
        await backend.delete("delete_me.txt")
        assert not await backend.exists("delete_me.txt")

    @pytest.mark.asyncio
    async def test_exists(self, backend: LocalStorageBackend) -> None:
        """Test existence check."""
        assert not await backend.exists("new.txt")
        await backend.upload("new.txt", b"new")
        assert await backend.exists("new.txt")

    @pytest.mark.asyncio
    async def test_get_metadata(self, backend: LocalStorageBackend) -> None:
        """Test getting metadata."""
        data = b"metadata test"
        metadata = {"key": "value"}
        await backend.upload("meta.txt", data, "text/plain", metadata)
        
        result = await backend.get_metadata("meta.txt")
        
        assert result.key == "meta.txt"
        assert result.size == len(data)
        assert result.content_type == "text/plain"
        assert result.metadata == metadata

    @pytest.mark.asyncio
    async def test_list_objects(self, backend: LocalStorageBackend) -> None:
        """Test listing objects."""
        await backend.upload("list/a.txt", b"a")
        await backend.upload("list/b.txt", b"b")
        await backend.upload("other/c.txt", b"c")
        
        results = await backend.list_objects("list/")
        keys = [r.key for r in results]
        
        assert "list/a.txt" in keys
        assert "list/b.txt" in keys
        assert "other/c.txt" not in keys

    @pytest.mark.asyncio
    async def test_list_objects_with_limit(self, backend: LocalStorageBackend) -> None:
        """Test listing objects with limit."""
        for i in range(10):
            await backend.upload(f"many/{i}.txt", b"x")
        
        results = await backend.list_objects("many/", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_presigned_url(self, backend: LocalStorageBackend) -> None:
        """Test presigned URL generation (local returns file:// URL)."""
        await backend.upload("presign.txt", b"content")
        
        result = await backend.get_presigned_url("presign.txt", "GET", 3600)
        
        assert result.url.startswith("file://")
        assert result.method == "GET"
        assert result.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_path_traversal_prevention(self, backend: LocalStorageBackend) -> None:
        """Test that path traversal is prevented."""
        # Attempt to escape the base directory
        await backend.upload("../escape.txt", b"escaped")
        
        # Should be stored safely within base path
        assert await backend.exists("escape.txt")
        
        # Verify it didn't escape
        base = Path(backend._base_path)
        assert not (base.parent / "escape.txt").exists()

    @pytest.mark.asyncio
    async def test_nested_directories(self, backend: LocalStorageBackend) -> None:
        """Test creating nested directories."""
        await backend.upload("a/b/c/d/deep.txt", b"deep")
        
        assert await backend.exists("a/b/c/d/deep.txt")
        result = await backend.download("a/b/c/d/deep.txt")
        assert result == b"deep"


class TestCreateStorageBackend:
    """Tests for the factory function."""

    def test_creates_local_backend(self) -> None:
        """Test creating local backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StorageConfig(backend="local", local_base_path=tmpdir)
            backend = create_storage_backend(config)
            assert isinstance(backend, LocalStorageBackend)

    def test_raises_on_unknown_backend(self) -> None:
        """Test error on unknown backend."""
        config = StorageConfig(backend="unknown")
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage_backend(config)


class TestAudioStorage:
    """Tests for AudioStorage helper."""

    @pytest.fixture
    def mock_backend(self) -> AsyncMock:
        """Create mock storage backend."""
        backend = AsyncMock()
        backend.upload.return_value = StorageObject(
            key="audio/test.mp3",
            size=1000,
            content_type="audio/mpeg",
            last_modified=datetime.now(timezone.utc),
        )
        backend.download.return_value = b"audio data"
        backend.get_presigned_url.return_value = PresignedUrl(
            url="https://example.com/audio",
            expires_at=datetime.now(timezone.utc),
            method="GET",
        )
        return backend

    @pytest.fixture
    def audio_storage(self, mock_backend: AsyncMock) -> AudioStorage:
        """Create audio storage instance."""
        return AudioStorage(mock_backend)

    @pytest.mark.asyncio
    async def test_upload_audio(
        self, audio_storage: AudioStorage, mock_backend: AsyncMock
    ) -> None:
        """Test uploading audio file."""
        song_id = uuid.uuid4()
        data = b"audio content"
        
        result = await audio_storage.upload_audio(song_id, data)
        
        mock_backend.upload.assert_called_once()
        call_args = mock_backend.upload.call_args
        assert f"audio/{song_id}.mp3" == call_args[0][0]

    @pytest.mark.asyncio
    async def test_download_audio(
        self, audio_storage: AudioStorage, mock_backend: AsyncMock
    ) -> None:
        """Test downloading audio file."""
        song_id = uuid.uuid4()
        
        result = await audio_storage.download_audio(song_id)
        
        mock_backend.download.assert_called_once()
        assert result == b"audio data"

    @pytest.mark.asyncio
    async def test_get_audio_url(
        self, audio_storage: AudioStorage, mock_backend: AsyncMock
    ) -> None:
        """Test getting presigned URL for audio."""
        song_id = uuid.uuid4()
        
        result = await audio_storage.get_audio_url(song_id)
        
        mock_backend.get_presigned_url.assert_called_once()
        assert result.url == "https://example.com/audio"

    @pytest.mark.asyncio
    async def test_upload_stem(
        self, audio_storage: AudioStorage, mock_backend: AsyncMock
    ) -> None:
        """Test uploading stem file."""
        song_id = uuid.uuid4()
        data = b"drum stem"
        
        await audio_storage.upload_stem(song_id, "drums", data)
        
        mock_backend.upload.assert_called_once()
        call_args = mock_backend.upload.call_args
        assert "drums.wav" in call_args[0][0]


class TestBeatmapStorage:
    """Tests for BeatmapStorage helper."""

    @pytest.fixture
    def mock_backend(self) -> AsyncMock:
        """Create mock storage backend."""
        backend = AsyncMock()
        backend.upload.return_value = StorageObject(
            key="beatmaps/test.bs",
            size=500,
            content_type="application/json",
            last_modified=datetime.now(timezone.utc),
        )
        backend.download.return_value = b'{"notes": []}'
        backend.get_presigned_url.return_value = PresignedUrl(
            url="https://example.com/beatmap",
            expires_at=datetime.now(timezone.utc),
            method="GET",
        )
        return backend

    @pytest.fixture
    def beatmap_storage(self, mock_backend: AsyncMock) -> BeatmapStorage:
        """Create beatmap storage instance."""
        return BeatmapStorage(mock_backend)

    @pytest.mark.asyncio
    async def test_upload_beatmap(
        self, beatmap_storage: BeatmapStorage, mock_backend: AsyncMock
    ) -> None:
        """Test uploading beatmap file."""
        map_id = uuid.uuid4()
        data = b'{"notes": []}'
        
        result = await beatmap_storage.upload_beatmap(map_id, 1, data)
        
        mock_backend.upload.assert_called_once()
        call_args = mock_backend.upload.call_args
        assert f"beatmaps/{map_id}/v1.bs" == call_args[0][0]

    @pytest.mark.asyncio
    async def test_download_beatmap(
        self, beatmap_storage: BeatmapStorage, mock_backend: AsyncMock
    ) -> None:
        """Test downloading beatmap file."""
        map_id = uuid.uuid4()
        
        result = await beatmap_storage.download_beatmap(map_id, 1)
        
        mock_backend.download.assert_called_once()
        assert result == b'{"notes": []}'

    @pytest.mark.asyncio
    async def test_get_beatmap_url(
        self, beatmap_storage: BeatmapStorage, mock_backend: AsyncMock
    ) -> None:
        """Test getting presigned URL for beatmap."""
        map_id = uuid.uuid4()
        
        result = await beatmap_storage.get_beatmap_url(map_id, 1)
        
        mock_backend.get_presigned_url.assert_called_once()
        assert result.url == "https://example.com/beatmap"
