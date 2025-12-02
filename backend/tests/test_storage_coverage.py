"""Additional tests for storage service to improve coverage.

Covers S3StorageBackend, AzureBlobStorageBackend, and edge cases.
"""

from __future__ import annotations

import os
import io
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import (
    AzureBlobStorageBackend,
    AudioStorage,
    BeatmapStorage,
    LocalStorageBackend,
    PresignedUrl,
    S3StorageBackend,
    StorageConfig,
    create_storage_backend,
    get_storage,
)


class TestStorageConfigFromEnv:
    """Tests for StorageConfig.from_env covering Azure configs."""

    def test_azure_config_from_env(self) -> None:
        """Test loading Azure config from environment."""
        with patch.dict(
            os.environ,
            {
                "STORAGE_BACKEND": "azure",
                "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;...",
                "AZURE_STORAGE_CONTAINER": "beatmaps",
                "AZURE_STORAGE_ACCOUNT": "beatstorageacct",
                "AZURE_STORAGE_KEY": "supersecretkey123",
            },
        ):
            config = StorageConfig.from_env()

            assert config.backend == "azure"
            assert (
                config.azure_connection_string == "DefaultEndpointsProtocol=https;..."
            )
            assert config.azure_container == "beatmaps"
            assert config.azure_account_name == "beatstorageacct"
            assert config.azure_account_key == "supersecretkey123"

    def test_s3_endpoint_url_from_env(self) -> None:
        """Test S3 endpoint URL for MinIO/LocalStack."""
        with patch.dict(
            os.environ,
            {
                "STORAGE_BACKEND": "s3",
                "AWS_S3_BUCKET": "mybucket",
                "AWS_S3_ENDPOINT_URL": "http://localhost:9000",
            },
        ):
            config = StorageConfig.from_env()

            assert config.s3_endpoint_url == "http://localhost:9000"


class TestLocalStorageEdgeCases:
    """Edge case tests for LocalStorageBackend."""

    @pytest.fixture
    def temp_dir(self) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def backend(self, temp_dir: str) -> LocalStorageBackend:
        return LocalStorageBackend(temp_dir)

    @pytest.mark.asyncio
    async def test_upload_file_like_object(self, backend: LocalStorageBackend) -> None:
        """Test uploading from a file-like object."""
        data = io.BytesIO(b"file content from buffer")

        result = await backend.upload("buffer_test.txt", data, "text/plain")

        assert result.size == len(b"file content from buffer")

    @pytest.mark.asyncio
    async def test_stream_download_not_found(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test stream download raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            async for _ in backend.stream_download("nonexistent.bin"):
                pass

    @pytest.mark.asyncio
    async def test_get_metadata_not_found(self, backend: LocalStorageBackend) -> None:
        """Test get_metadata raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await backend.get_metadata("missing.txt")

    @pytest.mark.asyncio
    async def test_get_metadata_without_sidecar(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test get_metadata works without .meta sidecar file."""
        await backend.upload("no_meta.bin", b"data")

        # Delete the sidecar if it exists
        path = backend._resolve_path("no_meta.bin")
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            meta_path.unlink()

        result = await backend.get_metadata("no_meta.bin")

        assert result.content_type == "application/octet-stream"
        assert result.metadata is None

    @pytest.mark.asyncio
    async def test_delete_with_metadata_sidecar(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test that delete removes metadata sidecar file."""
        metadata = {"key": "value"}
        await backend.upload("with_meta.txt", b"data", "text/plain", metadata)

        path = backend._resolve_path("with_meta.txt")
        meta_path = path.with_suffix(path.suffix + ".meta")

        assert path.exists()
        assert meta_path.exists()

        await backend.delete("with_meta.txt")

        assert not path.exists()
        assert not meta_path.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_is_noop(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test that deleting nonexistent file doesn't raise."""
        # Should not raise
        await backend.delete("definitely_not_there.txt")

    @pytest.mark.asyncio
    async def test_list_objects_empty_prefix(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test listing all objects with empty prefix."""
        await backend.upload("a.txt", b"a")
        await backend.upload("folder/b.txt", b"b")

        results = await backend.list_objects()
        keys = [r.key for r in results]

        assert "a.txt" in keys
        assert "folder/b.txt" in keys

    @pytest.mark.asyncio
    async def test_list_objects_nonexistent_prefix(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test listing with prefix that doesn't exist."""
        results = await backend.list_objects("nonexistent/")

        # Should return empty or scan from base
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_path_traversal_double_dots(
        self, backend: LocalStorageBackend
    ) -> None:
        """Test path traversal with .. is prevented."""
        await backend.upload("../../escape.txt", b"data")

        # Should be stored safely
        base = Path(backend._base_path)
        assert not (base.parent.parent / "escape.txt").exists()

    @pytest.mark.asyncio
    async def test_presigned_url_for_put(self, backend: LocalStorageBackend) -> None:
        """Test presigned URL for PUT method."""
        result = await backend.get_presigned_url(
            "upload.txt",
            method="PUT",
            expires_in=1800,
            content_type="text/plain",
        )

        assert result.method == "PUT"
        assert result.url.startswith("file://")


class TestS3StorageBackend:
    """Tests for S3StorageBackend."""

    @pytest.fixture
    def config(self) -> StorageConfig:
        return StorageConfig(
            backend="s3",
            s3_bucket="test-bucket",
            s3_region="us-west-2",
            s3_access_key="AKIATEST",
            s3_secret_key="secretkey",
        )

    @pytest.fixture
    def backend(self, config: StorageConfig) -> S3StorageBackend:
        return S3StorageBackend(config)

    @pytest.mark.asyncio
    async def test_get_client_requires_aioboto3(
        self, backend: S3StorageBackend
    ) -> None:
        """Test that missing aioboto3 raises ImportError."""
        with patch.dict("sys.modules", {"aioboto3": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ImportError, match="aioboto3"):
                    await backend._get_client()

    @pytest.mark.asyncio
    async def test_get_client_with_endpoint_url(self) -> None:
        """Test client creation with custom endpoint URL."""
        pytest.importorskip("aioboto3")

        config = StorageConfig(
            backend="s3",
            s3_bucket="test-bucket",
            s3_endpoint_url="http://localhost:9000",
        )
        backend = S3StorageBackend(config)

        mock_session = MagicMock()
        mock_client = AsyncMock()
        mock_session.client.return_value.__aenter__ = AsyncMock(
            return_value=mock_client
        )

        with patch("aioboto3.Session", return_value=mock_session):
            _client = await backend._get_client()

        # Verify endpoint_url was passed
        mock_session.client.assert_called()
        call_kwargs = mock_session.client.call_args[1]
        assert call_kwargs.get("endpoint_url") == "http://localhost:9000"

    @pytest.mark.asyncio
    async def test_upload(self, backend: S3StorageBackend) -> None:
        """Test S3 upload."""
        mock_client = AsyncMock()
        mock_client.put_object.return_value = {"ETag": '"abc123"'}

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.upload(
                "test/file.txt",
                b"hello world",
                "text/plain",
                {"custom": "metadata"},
            )

        assert result.key == "test/file.txt"
        assert result.etag == "abc123"
        assert result.metadata == {"custom": "metadata"}

    @pytest.mark.asyncio
    async def test_download(self, backend: S3StorageBackend) -> None:
        """Test S3 download."""
        mock_client = AsyncMock()
        mock_body = AsyncMock()
        mock_body.read.return_value = b"downloaded content"
        mock_client.get_object.return_value = {"Body": mock_body}

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.download("test/file.txt")

        assert result == b"downloaded content"

    @pytest.mark.asyncio
    async def test_download_not_found(self, backend: S3StorageBackend) -> None:
        """Test S3 download raises FileNotFoundError."""
        mock_client = AsyncMock()
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchKey = Exception
        mock_client.get_object.side_effect = mock_client.exceptions.NoSuchKey()

        with patch.object(backend, "_get_client", return_value=mock_client):
            with pytest.raises(FileNotFoundError):
                await backend.download("missing.txt")

    @pytest.mark.asyncio
    async def test_stream_download(self, backend: S3StorageBackend) -> None:
        """Test S3 stream download."""
        pytest.importorskip("aioboto3")

        mock_client = AsyncMock()
        mock_body = MagicMock()
        # iter_chunks returns an async iterator directly (not a coroutine)
        mock_body.iter_chunks = lambda chunk_size: AsyncIteratorMock(
            [b"chunk1", b"chunk2"]
        )
        mock_client.get_object = AsyncMock(return_value={"Body": mock_body})

        with patch.object(backend, "_get_client", return_value=mock_client):
            chunks = []
            async for chunk in backend.stream_download("file.bin"):
                chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]

    @pytest.mark.asyncio
    async def test_delete(self, backend: S3StorageBackend) -> None:
        """Test S3 delete."""
        mock_client = AsyncMock()

        with patch.object(backend, "_get_client", return_value=mock_client):
            await backend.delete("test.txt")

        mock_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists_true(self, backend: S3StorageBackend) -> None:
        """Test S3 exists returns True."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {}

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.exists("existing.txt")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, backend: S3StorageBackend) -> None:
        """Test S3 exists returns False on exception."""
        mock_client = AsyncMock()
        mock_client.head_object.side_effect = Exception("Not found")

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.exists("missing.txt")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_metadata(self, backend: S3StorageBackend) -> None:
        """Test S3 get_metadata."""
        mock_client = AsyncMock()
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/json",
            "LastModified": datetime.now(timezone.utc),
            "ETag": '"etag123"',
            "Metadata": {"key": "value"},
        }

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.get_metadata("data.json")

        assert result.size == 1024
        assert result.content_type == "application/json"
        assert result.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_list_objects(self, backend: S3StorageBackend) -> None:
        """Test S3 list_objects with pagination."""
        pytest.importorskip("aioboto3")

        # Mock client should be MagicMock since get_paginator is sync
        mock_client = MagicMock()

        # Create an async generator for paginate
        async def paginate_gen(**kwargs):
            yield {
                "Contents": [
                    {
                        "Key": "prefix/file1.txt",
                        "Size": 100,
                        "LastModified": datetime.now(timezone.utc),
                        "ETag": '"etag1"',
                    },
                    {
                        "Key": "prefix/file2.txt",
                        "Size": 200,
                        "LastModified": datetime.now(timezone.utc),
                    },
                ]
            }

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_gen
        mock_client.get_paginator.return_value = mock_paginator

        # _get_client is async, so use AsyncMock to mock it
        async def mock_get_client():
            return mock_client

        with patch.object(backend, "_get_client", mock_get_client):
            results = await backend.list_objects("prefix/")

        assert len(results) == 2
        assert results[0].key == "prefix/file1.txt"

    @pytest.mark.asyncio
    async def test_get_presigned_url_get(self, backend: S3StorageBackend) -> None:
        """Test S3 presigned URL for GET."""
        mock_client = AsyncMock()
        mock_client.generate_presigned_url.return_value = (
            "https://s3.example.com/signed"
        )

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.get_presigned_url("file.txt", "GET", 3600)

        assert result.url == "https://s3.example.com/signed"
        assert result.method == "GET"

    @pytest.mark.asyncio
    async def test_get_presigned_url_put_with_content_type(
        self, backend: S3StorageBackend
    ) -> None:
        """Test S3 presigned URL for PUT with content type."""
        mock_client = AsyncMock()
        mock_client.generate_presigned_url.return_value = (
            "https://s3.example.com/upload"
        )

        with patch.object(backend, "_get_client", return_value=mock_client):
            result = await backend.get_presigned_url(
                "upload.bin",
                "PUT",
                1800,
                content_type="application/octet-stream",
            )

        assert result.method == "PUT"
        # Verify content type was passed
        call_args = mock_client.generate_presigned_url.call_args
        assert call_args[1]["Params"]["ContentType"] == "application/octet-stream"


class TestAzureBlobStorageBackend:
    """Tests for AzureBlobStorageBackend."""

    @pytest.fixture
    def config(self) -> StorageConfig:
        return StorageConfig(
            backend="azure",
            azure_connection_string="DefaultEndpointsProtocol=https;AccountName=test",
            azure_container="testcontainer",
            azure_account_name="testaccount",
            azure_account_key="testkey123",
        )

    @pytest.fixture
    def backend(self, config: StorageConfig) -> AzureBlobStorageBackend:
        return AzureBlobStorageBackend(config)

    @pytest.mark.asyncio
    async def test_get_client_requires_azure_sdk(
        self, backend: AzureBlobStorageBackend
    ) -> None:
        """Test that missing azure-storage-blob raises ImportError."""
        with patch.dict("sys.modules", {"azure.storage.blob.aio": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ImportError, match="azure-storage-blob"):
                    await backend._get_client()

    @pytest.mark.asyncio
    async def test_get_client_with_connection_string(
        self, backend: AzureBlobStorageBackend
    ) -> None:
        """Test client creation with connection string."""
        pytest.importorskip("azure.storage.blob")

        mock_client = MagicMock()

        with patch("azure.storage.blob.aio.BlobServiceClient") as MockClient:
            MockClient.from_connection_string.return_value = mock_client

            _client = await backend._get_client()

        MockClient.from_connection_string.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_default_credential(self) -> None:
        """Test client creation with DefaultAzureCredential."""
        pytest.importorskip("azure.storage.blob")
        pytest.importorskip("azure.identity")

        config = StorageConfig(
            backend="azure",
            azure_connection_string="",  # Empty = use default credential
            azure_container="container",
            azure_account_name="account",
        )
        backend = AzureBlobStorageBackend(config)

        mock_client = MagicMock()
        mock_credential = MagicMock()

        with (
            patch("azure.storage.blob.aio.BlobServiceClient") as MockClient,
            patch(
                "azure.identity.aio.DefaultAzureCredential",
                return_value=mock_credential,
            ),
        ):
            MockClient.return_value = mock_client

            await backend._get_client()

        MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure upload."""
        pytest.importorskip("azure.storage.blob")

        mock_blob = AsyncMock()

        with (
            patch.object(backend, "_get_blob_client", return_value=mock_blob),
            patch("azure.storage.blob.ContentSettings"),
        ):
            result = await backend.upload(
                "test.txt",
                b"hello azure",
                "text/plain",
                {"key": "value"},
            )

        mock_blob.upload_blob.assert_called_once()
        assert result.key == "test.txt"

    @pytest.mark.asyncio
    async def test_download(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure download."""
        pytest.importorskip("azure.storage.blob")

        mock_blob = AsyncMock()
        mock_download = AsyncMock()
        mock_download.readall.return_value = b"azure content"
        mock_blob.download_blob.return_value = mock_download

        with (
            patch.object(backend, "_get_blob_client", return_value=mock_blob),
            patch("azure.core.exceptions.ResourceNotFoundError", Exception),
        ):
            result = await backend.download("test.txt")

        assert result == b"azure content"

    @pytest.mark.asyncio
    async def test_download_not_found(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure download raises FileNotFoundError."""
        pytest.importorskip("azure.storage.blob")

        mock_blob = AsyncMock()

        # Create a mock ResourceNotFoundError
        class MockResourceNotFoundError(Exception):
            pass

        mock_blob.download_blob.side_effect = MockResourceNotFoundError()

        with (
            patch.object(backend, "_get_blob_client", return_value=mock_blob),
            patch(
                "azure.core.exceptions.ResourceNotFoundError", MockResourceNotFoundError
            ),
        ):
            with pytest.raises(FileNotFoundError):
                await backend.download("missing.txt")

    @pytest.mark.asyncio
    async def test_stream_download(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure stream download."""
        pytest.importorskip("azure.storage.blob")

        mock_blob = AsyncMock()
        mock_download = MagicMock()
        # chunks() returns an async iterator directly
        mock_download.chunks = lambda: AsyncIteratorMock([b"c1", b"c2"])
        mock_blob.download_blob = AsyncMock(return_value=mock_download)

        with (
            patch.object(backend, "_get_blob_client", return_value=mock_blob),
            patch("azure.core.exceptions.ResourceNotFoundError", Exception),
        ):
            chunks = []
            async for chunk in backend.stream_download("file.bin"):
                chunks.append(chunk)

        assert chunks == [b"c1", b"c2"]

    @pytest.mark.asyncio
    async def test_delete(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure delete."""
        mock_blob = AsyncMock()

        with patch.object(backend, "_get_blob_client", return_value=mock_blob):
            await backend.delete("test.txt")

        mock_blob.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_exists(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure exists."""
        mock_blob = AsyncMock()
        mock_blob.exists.return_value = True

        with patch.object(backend, "_get_blob_client", return_value=mock_blob):
            result = await backend.exists("test.txt")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_metadata(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure get_metadata."""
        pytest.importorskip("azure.storage.blob")

        mock_blob = AsyncMock()
        mock_props = MagicMock()
        mock_props.size = 2048
        mock_props.content_settings.content_type = "application/pdf"
        mock_props.last_modified = datetime.now(timezone.utc)
        mock_props.etag = '"azure-etag"'
        mock_props.metadata = {"author": "test"}
        mock_blob.get_blob_properties.return_value = mock_props

        with (
            patch.object(backend, "_get_blob_client", return_value=mock_blob),
            patch("azure.core.exceptions.ResourceNotFoundError", Exception),
        ):
            result = await backend.get_metadata("doc.pdf")

        assert result.size == 2048
        assert result.content_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_list_objects(self, backend: AzureBlobStorageBackend) -> None:
        """Test Azure list_objects."""
        pytest.importorskip("azure.storage.blob")

        # Mock client should be MagicMock since get_container_client is sync
        mock_client = MagicMock()
        mock_container = MagicMock()

        # Mock blob list
        mock_blob1 = MagicMock()
        mock_blob1.name = "prefix/file1.txt"
        mock_blob1.size = 100
        mock_blob1.content_settings = MagicMock()
        mock_blob1.content_settings.content_type = "text/plain"
        mock_blob1.last_modified = datetime.now(timezone.utc)
        mock_blob1.etag = "etag1"

        # Create a proper async iterator for list_blobs
        async def list_blobs_gen(*args, **kwargs):
            yield mock_blob1

        mock_container.list_blobs = list_blobs_gen
        mock_client.get_container_client.return_value = mock_container

        # _get_client is async, so use an async function to mock it
        async def mock_get_client():
            return mock_client

        with patch.object(backend, "_get_client", mock_get_client):
            results = await backend.list_objects("prefix/")

        assert len(results) == 1
        assert results[0].key == "prefix/file1.txt"

    @pytest.mark.asyncio
    async def test_get_presigned_url_get(
        self, backend: AzureBlobStorageBackend
    ) -> None:
        """Test Azure presigned URL for GET."""
        pytest.importorskip("azure.storage.blob")

        with (
            patch("azure.storage.blob.BlobSasPermissions") as MockPerms,
            patch("azure.storage.blob.generate_blob_sas", return_value="sas_token"),
        ):
            MockPerms.return_value = MagicMock()

            result = await backend.get_presigned_url("file.txt", "GET", 3600)

        assert "sas_token" in result.url
        assert result.method == "GET"

    @pytest.mark.asyncio
    async def test_get_presigned_url_put(
        self, backend: AzureBlobStorageBackend
    ) -> None:
        """Test Azure presigned URL for PUT."""
        pytest.importorskip("azure.storage.blob")

        with (
            patch("azure.storage.blob.BlobSasPermissions") as MockPerms,
            patch("azure.storage.blob.generate_blob_sas", return_value="write_sas"),
        ):
            MockPerms.return_value = MagicMock()

            result = await backend.get_presigned_url("upload.bin", "PUT", 1800)

        assert result.method == "PUT"


class TestCreateStorageBackend:
    """Tests for create_storage_backend factory."""

    def test_creates_s3_backend(self) -> None:
        """Test creating S3 backend."""
        config = StorageConfig(backend="s3", s3_bucket="test")

        with patch("app.services.storage.logger"):
            backend = create_storage_backend(config)

        assert isinstance(backend, S3StorageBackend)

    def test_creates_azure_backend(self) -> None:
        """Test creating Azure backend."""
        config = StorageConfig(backend="azure", azure_container="test")

        with patch("app.services.storage.logger"):
            backend = create_storage_backend(config)

        assert isinstance(backend, AzureBlobStorageBackend)

    def test_loads_config_from_env_if_none(self) -> None:
        """Test that config is loaded from env if not provided."""
        with (
            patch.dict(
                os.environ,
                {"STORAGE_BACKEND": "local", "STORAGE_LOCAL_PATH": "/tmp/test"},
            ),
            patch("app.services.storage.logger"),
        ):
            backend = create_storage_backend(None)

        assert isinstance(backend, LocalStorageBackend)


class TestGetStorage:
    """Tests for get_storage singleton."""

    @pytest.mark.asyncio
    async def test_returns_singleton(self) -> None:
        """Test that get_storage returns same instance."""
        import app.services.storage as module

        module._storage_backend = None

        with patch.object(module, "create_storage_backend") as mock_create:
            mock_backend = MagicMock()
            mock_create.return_value = mock_backend

            result1 = await get_storage()
            result2 = await get_storage()

        assert result1 is result2
        mock_create.assert_called_once()


class TestAudioStorageHelpers:
    """Tests for AudioStorage helper methods."""

    def test_audio_key_generation(self) -> None:
        """Test audio key generation."""
        mock_backend = AsyncMock()
        storage = AudioStorage(mock_backend)
        song_id = uuid.uuid4()

        key = storage._audio_key(song_id, "wav")

        assert key == f"audio/{song_id}.wav"

    def test_stem_key_generation(self) -> None:
        """Test stem key generation."""
        mock_backend = AsyncMock()
        storage = AudioStorage(mock_backend)
        song_id = uuid.uuid4()

        key = storage._stem_key(song_id, "drums", "wav")

        assert key == f"stems/{song_id}/drums.wav"

    @pytest.mark.asyncio
    async def test_get_stem_url(self) -> None:
        """Test get_stem_url calls backend correctly."""
        mock_backend = AsyncMock()
        mock_backend.get_presigned_url.return_value = PresignedUrl(
            url="https://example.com/stem",
            expires_at=datetime.now(timezone.utc),
            method="GET",
        )

        storage = AudioStorage(mock_backend)
        song_id = uuid.uuid4()

        result = await storage.get_stem_url(song_id, "vocals", expires_in=7200)

        mock_backend.get_presigned_url.assert_called_once()
        assert result.url == "https://example.com/stem"


class TestBeatmapStorageHelpers:
    """Tests for BeatmapStorage helper methods."""

    def test_beatmap_key_generation(self) -> None:
        """Test beatmap key generation."""
        mock_backend = AsyncMock()
        storage = BeatmapStorage(mock_backend)
        map_id = uuid.uuid4()

        key = storage._beatmap_key(map_id, 3)

        assert key == f"beatmaps/{map_id}/v3.bs"


# Helper class for async iteration in mocks
class AsyncIteratorMock:
    """Mock async iterator for testing."""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
