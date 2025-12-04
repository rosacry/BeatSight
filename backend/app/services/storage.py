"""Cloud storage abstraction layer for audio files and beatmaps.

Provides a unified interface for:
- Local filesystem storage (development)
- AWS S3 (production option)
- Azure Blob Storage (production option)

The storage backend is selected via STORAGE_BACKEND environment variable.
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncIterator, BinaryIO

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Configuration for storage backends."""

    # Backend selection: "local", "s3", "azure"
    backend: str = "local"

    # Local storage
    local_base_path: str = "./storage"

    # AWS S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str | None = None  # For MinIO/LocalStack

    # Azure Blob Storage
    azure_connection_string: str = ""
    azure_container: str = ""
    azure_account_name: str = ""
    azure_account_key: str = ""

    @classmethod
    def from_env(cls) -> "StorageConfig":
        """Load configuration from environment variables."""
        return cls(
            backend=os.getenv("STORAGE_BACKEND", "local"),
            local_base_path=os.getenv("STORAGE_LOCAL_PATH", "./storage"),
            s3_bucket=os.getenv("AWS_S3_BUCKET", ""),
            s3_region=os.getenv("AWS_REGION", "us-east-1"),
            s3_access_key=os.getenv("AWS_ACCESS_KEY_ID", ""),
            s3_secret_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            s3_endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
            azure_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING", ""),
            azure_container=os.getenv("AZURE_STORAGE_CONTAINER", ""),
            azure_account_name=os.getenv("AZURE_STORAGE_ACCOUNT", ""),
            azure_account_key=os.getenv("AZURE_STORAGE_KEY", ""),
        )


@dataclass
class StorageObject:
    """Metadata about a stored object."""

    key: str
    size: int
    content_type: str
    last_modified: datetime
    etag: str | None = None
    metadata: dict[str, str] | None = None


@dataclass
class PresignedUrl:
    """A presigned URL for direct upload/download."""

    url: str
    expires_at: datetime
    method: str  # "GET" or "PUT"


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        """Upload data to storage.

        Args:
            key: Storage path/key for the object.
            data: Bytes or file-like object to upload.
            content_type: MIME type of the content.
            metadata: Optional key-value metadata.

        Returns:
            StorageObject with metadata about the upload.
        """
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download an object from storage.

        Args:
            key: Storage path/key for the object.

        Returns:
            Object contents as bytes.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        ...

    @abstractmethod
    async def stream_download(
        self, key: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        """Stream download an object in chunks.

        Args:
            key: Storage path/key for the object.
            chunk_size: Size of chunks to yield.

        Yields:
            Chunks of object data.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object from storage.

        Args:
            key: Storage path/key for the object.
        """
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if an object exists.

        Args:
            key: Storage path/key for the object.

        Returns:
            True if object exists, False otherwise.
        """
        ...

    @abstractmethod
    async def get_metadata(self, key: str) -> StorageObject:
        """Get metadata for an object without downloading.

        Args:
            key: Storage path/key for the object.

        Returns:
            StorageObject with metadata.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        ...

    @abstractmethod
    async def list_objects(
        self, prefix: str = "", limit: int = 1000
    ) -> list[StorageObject]:
        """List objects with a given prefix.

        Args:
            prefix: Key prefix to filter by.
            limit: Maximum number of objects to return.

        Returns:
            List of StorageObject metadata.
        """
        ...

    @abstractmethod
    async def get_presigned_url(
        self,
        key: str,
        method: str = "GET",
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> PresignedUrl:
        """Generate a presigned URL for direct access.

        Args:
            key: Storage path/key for the object.
            method: HTTP method ("GET" for download, "PUT" for upload).
            expires_in: URL validity in seconds.
            content_type: Required content type for PUT operations.

        Returns:
            PresignedUrl with the URL and expiration.
        """
        ...


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend for development."""

    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        """Resolve a storage key to a filesystem path."""
        # Prevent path traversal attacks - strip leading slashes and remove ..
        safe_key = key.lstrip("/\\")
        # Remove any path components that try to escape
        parts = []
        for part in Path(safe_key).parts:
            if part == ".." or part == ".":
                continue
            parts.append(part)
        safe_key = "/".join(parts) if parts else "unnamed"
        return self._base_path / safe_key

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, bytes):
            path.write_bytes(data)
            size = len(data)
        else:
            content = data.read()
            path.write_bytes(content)
            size = len(content)

        # Store metadata in a sidecar file
        if metadata:
            import json

            meta_path = path.with_suffix(path.suffix + ".meta")
            meta_path.write_text(
                json.dumps(
                    {
                        "content_type": content_type,
                        "metadata": metadata,
                    }
                )
            )

        return StorageObject(
            key=key,
            size=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
            etag=None,
            metadata=metadata,
        )

    async def download(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    async def stream_download(
        self, key: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")

        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    async def delete(self, key: str) -> None:
        path = self._resolve_path(key)
        if path.exists():
            path.unlink()
        # Also delete metadata sidecar
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            meta_path.unlink()

    async def exists(self, key: str) -> bool:
        return self._resolve_path(key).exists()

    async def get_metadata(self, key: str) -> StorageObject:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")

        stat = path.stat()
        content_type = "application/octet-stream"
        metadata = None

        # Check for metadata sidecar
        meta_path = path.with_suffix(path.suffix + ".meta")
        if meta_path.exists():
            import json

            meta = json.loads(meta_path.read_text())
            content_type = meta.get("content_type", content_type)
            metadata = meta.get("metadata")

        return StorageObject(
            key=key,
            size=stat.st_size,
            content_type=content_type,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            metadata=metadata,
        )

    async def list_objects(
        self, prefix: str = "", limit: int = 1000
    ) -> list[StorageObject]:
        results = []
        prefix_path = self._resolve_path(prefix) if prefix else self._base_path

        # Handle both file and directory prefixes
        search_dir = prefix_path.parent if prefix_path.is_file() else prefix_path
        if not search_dir.exists():
            search_dir = self._base_path

        for path in search_dir.rglob("*"):
            if path.is_file() and not path.suffix == ".meta":
                relative = path.relative_to(self._base_path)
                key = str(relative).replace("\\", "/")
                if key.startswith(prefix):
                    stat = path.stat()
                    results.append(
                        StorageObject(
                            key=key,
                            size=stat.st_size,
                            content_type="application/octet-stream",
                            last_modified=datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ),
                        )
                    )
                    if len(results) >= limit:
                        break

        return results

    async def get_presigned_url(
        self,
        key: str,
        method: str = "GET",
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> PresignedUrl:
        # Local storage doesn't support presigned URLs in the same way
        # Return a file:// URL for development
        path = self._resolve_path(key)
        return PresignedUrl(
            url=f"file://{path.absolute()}",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            method=method,
        )


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(self, config: StorageConfig) -> None:
        self._bucket = config.s3_bucket
        self._region = config.s3_region
        self._client = None
        self._config = config

    async def _get_client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            try:
                import aioboto3
            except ImportError:
                raise ImportError(
                    "aioboto3 is required for S3 storage. Install with: pip install aioboto3"
                )

            session = aioboto3.Session(
                aws_access_key_id=self._config.s3_access_key or None,
                aws_secret_access_key=self._config.s3_secret_key or None,
                region_name=self._region,
            )

            kwargs = {}
            if self._config.s3_endpoint_url:
                kwargs["endpoint_url"] = self._config.s3_endpoint_url

            self._client = await session.client("s3", **kwargs).__aenter__()
        return self._client

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        client = await self._get_client()

        kwargs = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
        }
        if metadata:
            kwargs["Metadata"] = metadata

        response = await client.put_object(**kwargs)

        size = len(data) if isinstance(data, bytes) else data.seek(0, 2)

        return StorageObject(
            key=key,
            size=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
            etag=response.get("ETag", "").strip('"'),
            metadata=metadata,
        )

    async def download(self, key: str) -> bytes:
        client = await self._get_client()

        try:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            return await response["Body"].read()
        except client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Object not found: {key}")

    async def stream_download(
        self, key: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        client = await self._get_client()

        try:
            response = await client.get_object(Bucket=self._bucket, Key=key)
            async for chunk in response["Body"].iter_chunks(chunk_size):
                yield chunk
        except client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Object not found: {key}")

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3.
        
        Returns True if object exists, False if not found.
        Raises StorageError for other failures (network, permissions, etc.)
        """
        client = await self._get_client()
        try:
            await client.head_object(Bucket=self._bucket, Key=key)
            return True
        except client.exceptions.NoSuchKey:
            return False
        except client.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            # Other errors (permissions, network) should not silently return False
            import logging
            logging.getLogger(__name__).error(f"S3 exists check failed for {key}: {e}")
            raise StorageError(f"Failed to check existence of {key}: {e}")

    async def get_metadata(self, key: str) -> StorageObject:
        client = await self._get_client()

        try:
            response = await client.head_object(Bucket=self._bucket, Key=key)
            return StorageObject(
                key=key,
                size=response["ContentLength"],
                content_type=response.get("ContentType", "application/octet-stream"),
                last_modified=response["LastModified"],
                etag=response.get("ETag", "").strip('"'),
                metadata=response.get("Metadata"),
            )
        except client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"Object not found: {key}")

    async def list_objects(
        self, prefix: str = "", limit: int = 1000
    ) -> list[StorageObject]:
        client = await self._get_client()

        results = []
        paginator = client.get_paginator("list_objects_v2")

        async for page in paginator.paginate(
            Bucket=self._bucket, Prefix=prefix, MaxKeys=limit
        ):
            for obj in page.get("Contents", []):
                results.append(
                    StorageObject(
                        key=obj["Key"],
                        size=obj["Size"],
                        content_type="application/octet-stream",  # HEAD required for type
                        last_modified=obj["LastModified"],
                        etag=obj.get("ETag", "").strip('"'),
                    )
                )
                if len(results) >= limit:
                    return results

        return results

    async def get_presigned_url(
        self,
        key: str,
        method: str = "GET",
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> PresignedUrl:
        client = await self._get_client()

        params = {"Bucket": self._bucket, "Key": key}
        if method == "PUT" and content_type:
            params["ContentType"] = content_type

        client_method = "get_object" if method == "GET" else "put_object"
        url = await client.generate_presigned_url(
            client_method,
            Params=params,
            ExpiresIn=expires_in,
        )

        return PresignedUrl(
            url=url,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            method=method,
        )


class AzureBlobStorageBackend(StorageBackend):
    """Azure Blob Storage backend."""

    def __init__(self, config: StorageConfig) -> None:
        self._container = config.azure_container
        self._client = None
        self._config = config

    async def _get_client(self):
        """Lazy initialization of Azure Blob client."""
        if self._client is None:
            try:
                from azure.storage.blob.aio import BlobServiceClient
            except ImportError:
                raise ImportError(
                    "azure-storage-blob is required for Azure storage. "
                    "Install with: pip install azure-storage-blob aiohttp"
                )

            if self._config.azure_connection_string:
                self._client = BlobServiceClient.from_connection_string(
                    self._config.azure_connection_string
                )
            else:
                account_url = (
                    f"https://{self._config.azure_account_name}.blob.core.windows.net"
                )
                from azure.identity.aio import DefaultAzureCredential

                self._client = BlobServiceClient(
                    account_url, credential=DefaultAzureCredential()
                )

        return self._client

    async def _get_blob_client(self, key: str):
        """Get a blob client for a specific key."""
        service = await self._get_client()
        return service.get_blob_client(self._container, key)

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StorageObject:
        from azure.storage.blob import ContentSettings

        blob = await self._get_blob_client(key)

        content_settings = ContentSettings(content_type=content_type)
        await blob.upload_blob(
            data,
            overwrite=True,
            content_settings=content_settings,
            metadata=metadata,
        )

        size = len(data) if isinstance(data, bytes) else data.seek(0, 2)

        return StorageObject(
            key=key,
            size=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
            metadata=metadata,
        )

    async def download(self, key: str) -> bytes:
        from azure.core.exceptions import ResourceNotFoundError

        blob = await self._get_blob_client(key)

        try:
            download = await blob.download_blob()
            return await download.readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Object not found: {key}")

    async def stream_download(
        self, key: str, chunk_size: int = 8192
    ) -> AsyncIterator[bytes]:
        from azure.core.exceptions import ResourceNotFoundError

        blob = await self._get_blob_client(key)

        try:
            download = await blob.download_blob()
            async for chunk in download.chunks():
                yield chunk
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Object not found: {key}")

    async def delete(self, key: str) -> None:
        blob = await self._get_blob_client(key)
        await blob.delete_blob()

    async def exists(self, key: str) -> bool:
        blob = await self._get_blob_client(key)
        return await blob.exists()

    async def get_metadata(self, key: str) -> StorageObject:
        from azure.core.exceptions import ResourceNotFoundError

        blob = await self._get_blob_client(key)

        try:
            props = await blob.get_blob_properties()
            return StorageObject(
                key=key,
                size=props.size,
                content_type=props.content_settings.content_type
                or "application/octet-stream",
                last_modified=props.last_modified,
                etag=props.etag,
                metadata=props.metadata,
            )
        except ResourceNotFoundError:
            raise FileNotFoundError(f"Object not found: {key}")

    async def list_objects(
        self, prefix: str = "", limit: int = 1000
    ) -> list[StorageObject]:
        service = await self._get_client()
        container = service.get_container_client(self._container)

        results = []
        async for blob in container.list_blobs(name_starts_with=prefix):
            results.append(
                StorageObject(
                    key=blob.name,
                    size=blob.size,
                    content_type=blob.content_settings.content_type
                    if blob.content_settings
                    else "application/octet-stream",
                    last_modified=blob.last_modified,
                    etag=blob.etag,
                )
            )
            if len(results) >= limit:
                break

        return results

    async def get_presigned_url(
        self,
        key: str,
        method: str = "GET",
        expires_in: int = 3600,
        content_type: str | None = None,
    ) -> PresignedUrl:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        permissions = (
            BlobSasPermissions(read=True)
            if method == "GET"
            else BlobSasPermissions(write=True)
        )
        expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        sas_token = generate_blob_sas(
            account_name=self._config.azure_account_name,
            container_name=self._container,
            blob_name=key,
            account_key=self._config.azure_account_key,
            permission=permissions,
            expiry=expiry,
        )

        url = f"https://{self._config.azure_account_name}.blob.core.windows.net/{self._container}/{key}?{sas_token}"

        return PresignedUrl(
            url=url,
            expires_at=expiry,
            method=method,
        )


def create_storage_backend(config: StorageConfig | None = None) -> StorageBackend:
    """Factory function to create the appropriate storage backend.

    Args:
        config: Optional configuration. If not provided, loads from environment.

    Returns:
        Configured StorageBackend instance.
    """
    if config is None:
        config = StorageConfig.from_env()

    if config.backend == "local":
        logger.info("Using local filesystem storage at %s", config.local_base_path)
        return LocalStorageBackend(config.local_base_path)
    elif config.backend == "s3":
        logger.info("Using AWS S3 storage (bucket: %s)", config.s3_bucket)
        return S3StorageBackend(config)
    elif config.backend == "azure":
        logger.info("Using Azure Blob Storage (container: %s)", config.azure_container)
        return AzureBlobStorageBackend(config)
    else:
        raise ValueError(f"Unknown storage backend: {config.backend}")


# Singleton instance
_storage_backend: StorageBackend | None = None


async def get_storage() -> StorageBackend:
    """Get the global storage backend instance."""
    global _storage_backend
    if _storage_backend is None:
        _storage_backend = create_storage_backend()
    return _storage_backend


# Helper functions for common audio/beatmap operations
class AudioStorage:
    """High-level API for audio file storage."""

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    def _audio_key(self, song_id: uuid.UUID, extension: str = "mp3") -> str:
        """Generate storage key for audio files."""
        return f"audio/{song_id}.{extension}"

    def _stem_key(self, song_id: uuid.UUID, stem: str, extension: str = "wav") -> str:
        """Generate storage key for stem files."""
        return f"stems/{song_id}/{stem}.{extension}"

    async def upload_audio(
        self,
        song_id: uuid.UUID,
        data: bytes | BinaryIO,
        content_type: str = "audio/mpeg",
    ) -> StorageObject:
        """Upload original audio file."""
        ext = "mp3" if "mpeg" in content_type else content_type.split("/")[-1]
        key = self._audio_key(song_id, ext)
        return await self._backend.upload(key, data, content_type)

    async def download_audio(self, song_id: uuid.UUID, extension: str = "mp3") -> bytes:
        """Download original audio file."""
        key = self._audio_key(song_id, extension)
        return await self._backend.download(key)

    async def get_audio_url(
        self,
        song_id: uuid.UUID,
        extension: str = "mp3",
        expires_in: int = 3600,
    ) -> PresignedUrl:
        """Get presigned URL for audio download."""
        key = self._audio_key(song_id, extension)
        return await self._backend.get_presigned_url(key, "GET", expires_in)

    async def upload_stem(
        self,
        song_id: uuid.UUID,
        stem: str,
        data: bytes | BinaryIO,
    ) -> StorageObject:
        """Upload a separated stem (drums, bass, etc.)."""
        key = self._stem_key(song_id, stem)
        return await self._backend.upload(key, data, "audio/wav")

    async def get_stem_url(
        self,
        song_id: uuid.UUID,
        stem: str,
        expires_in: int = 3600,
    ) -> PresignedUrl:
        """Get presigned URL for stem download."""
        key = self._stem_key(song_id, stem)
        return await self._backend.get_presigned_url(key, "GET", expires_in)


class BeatmapStorage:
    """High-level API for beatmap file storage."""

    def __init__(self, backend: StorageBackend) -> None:
        self._backend = backend

    def _beatmap_key(self, map_id: uuid.UUID, version: int) -> str:
        """Generate storage key for beatmap files."""
        return f"beatmaps/{map_id}/v{version}.bs"

    async def upload_beatmap(
        self,
        map_id: uuid.UUID,
        version: int,
        data: bytes | BinaryIO,
    ) -> StorageObject:
        """Upload a beatmap file."""
        key = self._beatmap_key(map_id, version)
        return await self._backend.upload(key, data, "application/json")

    async def download_beatmap(self, map_id: uuid.UUID, version: int) -> bytes:
        """Download a beatmap file."""
        key = self._beatmap_key(map_id, version)
        return await self._backend.download(key)

    async def get_beatmap_url(
        self,
        map_id: uuid.UUID,
        version: int,
        expires_in: int = 3600,
    ) -> PresignedUrl:
        """Get presigned URL for beatmap download."""
        key = self._beatmap_key(map_id, version)
        return await self._backend.get_presigned_url(key, "GET", expires_in)
