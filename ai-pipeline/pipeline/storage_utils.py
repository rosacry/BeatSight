"""
Cloud storage utilities for AI pipeline worker.

Handles downloading audio from and uploading beatmaps to S3/Azure/R2 storage.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageClient:
    """
    Unified storage client supporting multiple backends.
    
    Supported URI schemes:
    - s3://bucket/key - Amazon S3 or S3-compatible (R2, MinIO)
    - az://container/blob - Azure Blob Storage
    - gs://bucket/object - Google Cloud Storage
    - http(s):// - Direct HTTP download
    - file:// or local paths - Local filesystem
    """
    
    def __init__(
        self,
        backend: str = "auto",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        s3_endpoint_url: Optional[str] = None,
        azure_connection_string: Optional[str] = None,
    ):
        """
        Initialize storage client.
        
        Args:
            backend: Storage backend ("s3", "azure", "gcs", "local", or "auto")
            aws_access_key_id: AWS access key (or from env AWS_ACCESS_KEY_ID)
            aws_secret_access_key: AWS secret key (or from env AWS_SECRET_ACCESS_KEY)
            aws_region: AWS region (or from env AWS_REGION)
            s3_endpoint_url: Custom S3 endpoint for R2/MinIO (or from env S3_ENDPOINT_URL)
            azure_connection_string: Azure connection string (or from env AZURE_STORAGE_CONNECTION_STRING)
        """
        self.backend = backend
        
        # S3 configuration
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self.s3_endpoint_url = s3_endpoint_url or os.getenv("S3_ENDPOINT_URL")
        
        # Azure configuration
        self.azure_connection_string = azure_connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        
        # Lazy-loaded clients
        self._s3_client = None
        self._azure_client = None
    
    @property
    def s3_client(self):
        """Lazy-load boto3 S3 client."""
        if self._s3_client is None:
            try:
                import boto3
                from botocore.config import Config
                
                config = Config(
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    connect_timeout=10,
                    read_timeout=60,
                )
                
                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.aws_region,
                    endpoint_url=self.s3_endpoint_url,
                    config=config,
                )
            except ImportError:
                raise StorageError("boto3 is required for S3 storage. Install with: pip install boto3")
        
        return self._s3_client
    
    @property
    def azure_blob_service(self):
        """Lazy-load Azure Blob service client."""
        if self._azure_client is None:
            try:
                from azure.storage.blob import BlobServiceClient
                
                if not self.azure_connection_string:
                    raise StorageError("AZURE_STORAGE_CONNECTION_STRING required for Azure storage")
                
                self._azure_client = BlobServiceClient.from_connection_string(
                    self.azure_connection_string
                )
            except ImportError:
                raise StorageError(
                    "azure-storage-blob is required for Azure storage. "
                    "Install with: pip install azure-storage-blob"
                )
        
        return self._azure_client
    
    def _parse_uri(self, uri: str) -> tuple[str, str, str]:
        """
        Parse a storage URI into (scheme, bucket/container, key/blob).
        
        Returns:
            Tuple of (scheme, bucket_or_container, key_or_blob)
        """
        parsed = urlparse(uri)
        scheme = parsed.scheme.lower()
        
        if scheme in ("s3", "az", "gs"):
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            return scheme, bucket, key
        elif scheme in ("http", "https"):
            return scheme, "", uri
        elif scheme == "file" or not scheme:
            # Local file
            path = parsed.path if scheme == "file" else uri
            return "file", "", path
        else:
            raise StorageError(f"Unsupported URI scheme: {scheme}")
    
    async def download(self, uri: str, destination: Path) -> Path:
        """
        Download a file from storage.
        
        Args:
            uri: Storage URI (s3://, az://, http://, or local path)
            destination: Local path to save the file
            
        Returns:
            Path to downloaded file
        """
        import asyncio
        
        scheme, bucket, key = self._parse_uri(uri)
        
        logger.info("Downloading from storage", uri=uri, scheme=scheme)
        
        if scheme == "s3":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._download_s3, bucket, key, destination
            )
        elif scheme == "az":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._download_azure, bucket, key, destination
            )
        elif scheme in ("http", "https"):
            return await self._download_http(uri, destination)
        elif scheme == "file":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._copy_local, key, destination
            )
        else:
            raise StorageError(f"Unsupported scheme for download: {scheme}")
    
    async def upload(self, source: Path, uri: str) -> str:
        """
        Upload a file to storage.
        
        Args:
            source: Local path to the file
            uri: Storage URI (s3://, az://)
            
        Returns:
            Public URL or URI of uploaded file
        """
        import asyncio
        
        scheme, bucket, key = self._parse_uri(uri)
        
        logger.info("Uploading to storage", uri=uri, scheme=scheme, size=source.stat().st_size)
        
        if scheme == "s3":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._upload_s3, source, bucket, key
            )
        elif scheme == "az":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._upload_azure, source, bucket, key
            )
        elif scheme == "file":
            return await asyncio.get_event_loop().run_in_executor(
                None, self._copy_local, source, Path(key)
            )
        else:
            raise StorageError(f"Unsupported scheme for upload: {scheme}")
    
    def _download_s3(self, bucket: str, key: str, destination: Path) -> Path:
        """Download from S3."""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.s3_client.download_file(bucket, key, str(destination))
            logger.info("S3 download complete", bucket=bucket, key=key)
            return destination
        except Exception as e:
            raise StorageError(f"S3 download failed: {e}") from e
    
    def _upload_s3(self, source: Path, bucket: str, key: str) -> str:
        """Upload to S3."""
        try:
            # Determine content type
            content_type = "application/octet-stream"
            if source.suffix == ".json" or source.suffix == ".bsm":
                content_type = "application/json"
            elif source.suffix in (".mp3", ".wav", ".flac", ".ogg"):
                content_type = f"audio/{source.suffix[1:]}"
            
            self.s3_client.upload_file(
                str(source),
                bucket,
                key,
                ExtraArgs={"ContentType": content_type}
            )
            
            logger.info("S3 upload complete", bucket=bucket, key=key)
            return f"s3://{bucket}/{key}"
        except Exception as e:
            raise StorageError(f"S3 upload failed: {e}") from e
    
    def _download_azure(self, container: str, blob: str, destination: Path) -> Path:
        """Download from Azure Blob Storage."""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            blob_client = self.azure_blob_service.get_blob_client(container, blob)
            
            with open(destination, "wb") as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
            
            logger.info("Azure download complete", container=container, blob=blob)
            return destination
        except Exception as e:
            raise StorageError(f"Azure download failed: {e}") from e
    
    def _upload_azure(self, source: Path, container: str, blob: str) -> str:
        """Upload to Azure Blob Storage."""
        try:
            blob_client = self.azure_blob_service.get_blob_client(container, blob)
            
            with open(source, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)
            
            logger.info("Azure upload complete", container=container, blob=blob)
            return f"az://{container}/{blob}"
        except Exception as e:
            raise StorageError(f"Azure upload failed: {e}") from e
    
    async def _download_http(self, url: str, destination: Path) -> Path:
        """Download from HTTP(S) URL."""
        try:
            import httpx
            
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                with open(destination, "wb") as f:
                    f.write(response.content)
            
            logger.info("HTTP download complete", url=url)
            return destination
        except Exception as e:
            raise StorageError(f"HTTP download failed: {e}") from e
    
    def _copy_local(self, source: Path, destination: Path) -> Path:
        """Copy local file."""
        import shutil
        
        source = Path(source)
        destination = Path(destination)
        
        if not source.exists():
            raise StorageError(f"Local file not found: {source}")
        
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        
        logger.info("Local copy complete", source=str(source), destination=str(destination))
        return destination
    
    def generate_presigned_url(
        self, 
        uri: str, 
        expires_in: int = 3600,
        operation: str = "get"
    ) -> str:
        """
        Generate a presigned URL for S3.
        
        Args:
            uri: S3 URI (s3://bucket/key)
            expires_in: Expiration time in seconds
            operation: "get" for download, "put" for upload
            
        Returns:
            Presigned URL string
        """
        scheme, bucket, key = self._parse_uri(uri)
        
        if scheme != "s3":
            raise StorageError("Presigned URLs only supported for S3")
        
        client_method = "get_object" if operation == "get" else "put_object"
        
        url = self.s3_client.generate_presigned_url(
            ClientMethod=client_method,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        
        return url


# Singleton instance for convenience
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """Get or create the singleton storage client."""
    global _storage_client
    
    if _storage_client is None:
        _storage_client = StorageClient()
    
    return _storage_client
