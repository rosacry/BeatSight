"""File upload utilities for secure file handling.

Provides utilities for:
- File type validation (MIME types, magic bytes)
- File size limits
- Secure file name generation
- Temporary file handling
- Upload progress tracking
- Image validation and resizing

Usage:
    from app.utils.file_upload import (
        FileValidator,
        save_upload,
        generate_secure_filename,
        ALLOWED_AUDIO_TYPES,
    )

    validator = FileValidator(
        allowed_types=ALLOWED_AUDIO_TYPES,
        max_size_bytes=50 * 1024 * 1024,  # 50MB
    )
    
    if validator.validate(file):
        path = await save_upload(file, "uploads/audio")
"""

from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import IO, Any, BinaryIO, Callable

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Common MIME type sets
ALLOWED_AUDIO_TYPES = frozenset({
    "audio/mpeg",       # MP3
    "audio/mp3",        # MP3 (alternate)
    "audio/wav",        # WAV
    "audio/wave",       # WAV (alternate)
    "audio/x-wav",      # WAV (alternate)
    "audio/flac",       # FLAC
    "audio/x-flac",     # FLAC (alternate)
    "audio/ogg",        # OGG
    "audio/aac",        # AAC
    "audio/mp4",        # M4A
    "audio/x-m4a",      # M4A (alternate)
})

ALLOWED_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
})

ALLOWED_DOCUMENT_TYPES = frozenset({
    "application/pdf",
    "text/plain",
    "application/json",
})

# Magic bytes for file type detection
MAGIC_BYTES = {
    # Audio
    b"\xff\xfb": "audio/mpeg",           # MP3
    b"\xff\xfa": "audio/mpeg",           # MP3
    b"\xff\xf3": "audio/mpeg",           # MP3
    b"\xff\xf2": "audio/mpeg",           # MP3
    b"ID3": "audio/mpeg",                # MP3 with ID3 tag
    b"RIFF": "audio/wav",                # WAV
    b"fLaC": "audio/flac",               # FLAC
    b"OggS": "audio/ogg",                # OGG
    # Images
    b"\xff\xd8\xff": "image/jpeg",       # JPEG
    b"\x89PNG": "image/png",             # PNG
    b"GIF8": "image/gif",                # GIF
    b"RIFF": "image/webp",               # WebP (needs further check)
    # Documents
    b"%PDF": "application/pdf",          # PDF
}

# Maximum reasonable magic byte check length
MAX_MAGIC_BYTES_LENGTH = 12

# Default max file sizes
DEFAULT_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
DEFAULT_MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
DEFAULT_MAX_AUDIO_SIZE = 500 * 1024 * 1024  # 500MB


# =============================================================================
# File validation
# =============================================================================

class FileValidationError(Exception):
    """Exception raised for file validation errors."""
    
    def __init__(self, message: str, code: str = "validation_error"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class FileValidationResult:
    """Result of file validation."""
    
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    detected_type: str | None = None
    file_size: int = 0
    
    @classmethod
    def success(
        cls,
        detected_type: str | None = None,
        file_size: int = 0,
    ) -> "FileValidationResult":
        """Create a successful validation result."""
        return cls(
            is_valid=True,
            detected_type=detected_type,
            file_size=file_size,
        )
    
    @classmethod
    def failure(cls, *errors: str) -> "FileValidationResult":
        """Create a failed validation result."""
        return cls(is_valid=False, errors=list(errors))


@dataclass
class FileValidator:
    """Validator for uploaded files."""
    
    allowed_types: frozenset[str] | None = None
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE
    min_size_bytes: int = 0
    allowed_extensions: set[str] | None = None
    check_magic_bytes: bool = True
    
    def validate(
        self,
        file: BinaryIO,
        filename: str | None = None,
    ) -> FileValidationResult:
        """Validate an uploaded file.
        
        Args:
            file: File-like object to validate
            filename: Original filename for extension check
            
        Returns:
            FileValidationResult
        """
        errors = []
        
        # Get file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to start
        
        # Check size limits
        if file_size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            errors.append(f"File too large. Maximum size is {max_mb:.1f}MB")
        
        if file_size < self.min_size_bytes:
            errors.append("File is too small or empty")
        
        # Check extension if required
        if self.allowed_extensions and filename:
            ext = ""
            if "." in filename:
                ext = "." + filename.rsplit(".", 1)[-1].lower()
            if ext not in self.allowed_extensions:
                allowed = ", ".join(sorted(self.allowed_extensions))
                errors.append(f"File extension not allowed. Allowed: {allowed}")
        
        # Detect MIME type
        detected_type = None
        
        if self.check_magic_bytes:
            header = file.read(MAX_MAGIC_BYTES_LENGTH)
            file.seek(0)
            detected_type = self._detect_type_from_magic(header)
        
        # Fall back to extension-based detection
        if not detected_type and filename:
            detected_type, _ = mimetypes.guess_type(filename)
        
        # Check allowed types
        if self.allowed_types and detected_type:
            if detected_type not in self.allowed_types:
                allowed = ", ".join(sorted(self.allowed_types))
                errors.append(
                    f"File type '{detected_type}' not allowed. "
                    f"Allowed: {allowed}"
                )
        
        if errors:
            return FileValidationResult.failure(*errors)
        
        return FileValidationResult.success(
            detected_type=detected_type,
            file_size=file_size,
        )
    
    def _detect_type_from_magic(self, header: bytes) -> str | None:
        """Detect file type from magic bytes.
        
        Args:
            header: First bytes of the file
            
        Returns:
            Detected MIME type or None
        """
        # Special handling for RIFF container (WAV and WebP)
        if header.startswith(b"RIFF"):
            if b"WEBP" in header:
                return "image/webp"
            elif b"WAVE" in header:
                return "audio/wav"
            # Unknown RIFF format
            return None
        
        for magic, mime_type in MAGIC_BYTES.items():
            if magic == b"RIFF":
                continue  # Already handled above
            if header.startswith(magic):
                return mime_type
        
        return None


def validate_audio_file(
    file: BinaryIO,
    filename: str | None = None,
    max_size_bytes: int = DEFAULT_MAX_AUDIO_SIZE,
) -> FileValidationResult:
    """Validate an audio file.
    
    Args:
        file: File to validate
        filename: Original filename
        max_size_bytes: Maximum file size
        
    Returns:
        FileValidationResult
    """
    validator = FileValidator(
        allowed_types=ALLOWED_AUDIO_TYPES,
        max_size_bytes=max_size_bytes,
        allowed_extensions={".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    )
    return validator.validate(file, filename)


def validate_image_file(
    file: BinaryIO,
    filename: str | None = None,
    max_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE,
) -> FileValidationResult:
    """Validate an image file.
    
    Args:
        file: File to validate
        filename: Original filename
        max_size_bytes: Maximum file size
        
    Returns:
        FileValidationResult
    """
    validator = FileValidator(
        allowed_types=ALLOWED_IMAGE_TYPES,
        max_size_bytes=max_size_bytes,
        allowed_extensions={".jpg", ".jpeg", ".png", ".gif", ".webp"},
    )
    return validator.validate(file, filename)


# =============================================================================
# File naming
# =============================================================================

def generate_secure_filename(
    original_filename: str | None = None,
    *,
    preserve_extension: bool = True,
    prefix: str = "",
    use_uuid: bool = True,
    use_timestamp: bool = False,
) -> str:
    """Generate a secure, unique filename.
    
    Args:
        original_filename: Original filename to extract extension from
        preserve_extension: Whether to preserve the original extension
        prefix: Prefix to add to filename
        use_uuid: Use UUID for uniqueness
        use_timestamp: Use timestamp for uniqueness
        
    Returns:
        Secure filename
    """
    parts = []
    
    if prefix:
        # Sanitize prefix
        prefix = prefix.replace("/", "_").replace("\\", "_")
        parts.append(prefix)
    
    if use_timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        parts.append(timestamp)
    
    if use_uuid:
        parts.append(str(uuid.uuid4()))
    
    filename = "_".join(parts) if parts else str(uuid.uuid4())
    
    # Add extension
    if preserve_extension and original_filename and "." in original_filename:
        ext = original_filename.rsplit(".", 1)[-1].lower()
        # Only allow alphanumeric extensions
        if ext.isalnum() and len(ext) <= 10:
            filename = f"{filename}.{ext}"
    
    return filename


def get_file_extension(filename: str) -> str:
    """Get file extension from filename.
    
    Args:
        filename: Filename to extract extension from
        
    Returns:
        Extension including the dot (e.g., ".mp3"), or empty string
    """
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


def compute_file_hash(
    file: BinaryIO,
    algorithm: str = "sha256",
    chunk_size: int = 8192,
) -> str:
    """Compute hash of file contents.
    
    Args:
        file: File to hash
        algorithm: Hash algorithm (sha256, md5, sha1)
        chunk_size: Read chunk size
        
    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)
    
    file.seek(0)
    while chunk := file.read(chunk_size):
        hasher.update(chunk)
    file.seek(0)
    
    return hasher.hexdigest()


# =============================================================================
# File saving
# =============================================================================

@dataclass
class SavedFile:
    """Information about a saved file."""
    
    path: Path
    filename: str
    size_bytes: int
    content_hash: str | None = None
    content_type: str | None = None
    
    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)


async def save_upload(
    file: BinaryIO,
    destination_dir: str | Path,
    filename: str | None = None,
    *,
    compute_hash: bool = True,
    overwrite: bool = False,
    create_dirs: bool = True,
) -> SavedFile:
    """Save an uploaded file to disk.
    
    Args:
        file: File-like object to save
        destination_dir: Directory to save to
        filename: Filename to use (generated if not provided)
        compute_hash: Compute SHA256 hash
        overwrite: Allow overwriting existing files
        create_dirs: Create destination directory if needed
        
    Returns:
        SavedFile with file information
        
    Raises:
        FileExistsError: If file exists and overwrite is False
        OSError: If directory creation fails
    """
    dest_path = Path(destination_dir)
    
    if create_dirs:
        dest_path.mkdir(parents=True, exist_ok=True)
    
    if not filename:
        filename = generate_secure_filename()
    
    file_path = dest_path / filename
    
    if file_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {file_path}")
    
    # Get file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    # Compute hash if requested
    file_hash = None
    if compute_hash:
        file_hash = compute_file_hash(file)
    
    # Save file
    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(file, out_file)
    
    logger.info(
        "File saved",
        path=str(file_path),
        size_bytes=file_size,
        hash=file_hash[:16] if file_hash else None,
    )
    
    return SavedFile(
        path=file_path,
        filename=filename,
        size_bytes=file_size,
        content_hash=file_hash,
    )


def save_upload_sync(
    file: BinaryIO,
    destination_dir: str | Path,
    filename: str | None = None,
    *,
    compute_hash: bool = True,
    overwrite: bool = False,
    create_dirs: bool = True,
) -> SavedFile:
    """Synchronous version of save_upload.
    
    Args:
        file: File-like object to save
        destination_dir: Directory to save to
        filename: Filename to use
        compute_hash: Compute SHA256 hash
        overwrite: Allow overwriting
        create_dirs: Create directory if needed
        
    Returns:
        SavedFile with file information
    """
    dest_path = Path(destination_dir)
    
    if create_dirs:
        dest_path.mkdir(parents=True, exist_ok=True)
    
    if not filename:
        filename = generate_secure_filename()
    
    file_path = dest_path / filename
    
    if file_path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {file_path}")
    
    # Get file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    # Compute hash if requested
    file_hash = None
    if compute_hash:
        file_hash = compute_file_hash(file)
    
    # Save file
    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(file, out_file)
    
    return SavedFile(
        path=file_path,
        filename=filename,
        size_bytes=file_size,
        content_hash=file_hash,
    )


# =============================================================================
# Temporary files
# =============================================================================

class TempFile:
    """Context manager for temporary file handling.
    
    Usage:
        async with TempFile(suffix=".mp3") as temp:
            await temp.write(data)
            process(temp.path)
    """
    
    def __init__(
        self,
        suffix: str = "",
        prefix: str = "beatsight_",
        dir: str | Path | None = None,
        delete: bool = True,
    ):
        """Initialize temp file handler.
        
        Args:
            suffix: File suffix (extension)
            prefix: Filename prefix
            dir: Directory for temp file
            delete: Delete file on context exit
        """
        self.suffix = suffix
        self.prefix = prefix
        self.dir = dir
        self.delete = delete
        self._fd: int | None = None
        self._path: Path | None = None
    
    @property
    def path(self) -> Path:
        """Path to the temp file."""
        if self._path is None:
            raise RuntimeError("TempFile not initialized")
        return self._path
    
    def __enter__(self) -> "TempFile":
        """Enter context manager."""
        self._fd, path_str = tempfile.mkstemp(
            suffix=self.suffix,
            prefix=self.prefix,
            dir=self.dir,
        )
        self._path = Path(path_str)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
        
        if self.delete and self._path and self._path.exists():
            try:
                self._path.unlink()
            except OSError:
                pass
        
        return False
    
    async def __aenter__(self) -> "TempFile":
        """Async enter context manager."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit context manager."""
        return self.__exit__(exc_type, exc_val, exc_tb)
    
    def write(self, data: bytes) -> int:
        """Write data to temp file.
        
        Args:
            data: Bytes to write
            
        Returns:
            Number of bytes written
        """
        if self._fd is None:
            raise RuntimeError("TempFile not initialized")
        return os.write(self._fd, data)
    
    def write_from(self, source: BinaryIO, chunk_size: int = 8192) -> int:
        """Write data from a file-like object.
        
        Args:
            source: Source file
            chunk_size: Read chunk size
            
        Returns:
            Total bytes written
        """
        total = 0
        while chunk := source.read(chunk_size):
            total += self.write(chunk)
        return total


class TempDirectory:
    """Context manager for temporary directory handling.
    
    Usage:
        async with TempDirectory() as temp_dir:
            file_path = temp_dir.path / "file.txt"
            file_path.write_text("content")
    """
    
    def __init__(
        self,
        prefix: str = "beatsight_",
        dir: str | Path | None = None,
        delete: bool = True,
    ):
        """Initialize temp directory handler.
        
        Args:
            prefix: Directory name prefix
            dir: Parent directory
            delete: Delete directory on exit
        """
        self.prefix = prefix
        self.dir = dir
        self.delete = delete
        self._path: Path | None = None
    
    @property
    def path(self) -> Path:
        """Path to the temp directory."""
        if self._path is None:
            raise RuntimeError("TempDirectory not initialized")
        return self._path
    
    def __enter__(self) -> "TempDirectory":
        """Enter context manager."""
        self._path = Path(tempfile.mkdtemp(
            prefix=self.prefix,
            dir=self.dir,
        ))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if self.delete and self._path and self._path.exists():
            try:
                shutil.rmtree(self._path)
            except OSError:
                pass
        return False
    
    async def __aenter__(self) -> "TempDirectory":
        """Async enter context manager."""
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit context manager."""
        return self.__exit__(exc_type, exc_val, exc_tb)


# =============================================================================
# Upload progress tracking
# =============================================================================

class UploadStatus(str, Enum):
    """Status of file upload."""
    
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UploadProgress:
    """Tracks upload progress."""
    
    upload_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: UploadStatus = UploadStatus.PENDING
    total_bytes: int = 0
    uploaded_bytes: int = 0
    filename: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    @property
    def progress_percent(self) -> float:
        """Upload progress as percentage."""
        if self.total_bytes == 0:
            return 0.0
        return (self.uploaded_bytes / self.total_bytes) * 100
    
    @property
    def is_complete(self) -> bool:
        """Check if upload is complete."""
        return self.status in (
            UploadStatus.COMPLETED,
            UploadStatus.FAILED,
            UploadStatus.CANCELLED,
        )
    
    def update(
        self,
        uploaded_bytes: int | None = None,
        status: UploadStatus | None = None,
        error: str | None = None,
    ) -> None:
        """Update progress state."""
        if uploaded_bytes is not None:
            self.uploaded_bytes = uploaded_bytes
        if status is not None:
            self.status = status
            if status == UploadStatus.UPLOADING and self.started_at is None:
                self.started_at = datetime.now(timezone.utc)
            elif status in (UploadStatus.COMPLETED, UploadStatus.FAILED):
                self.completed_at = datetime.now(timezone.utc)
        if error is not None:
            self.error = error
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "upload_id": self.upload_id,
            "status": self.status.value,
            "total_bytes": self.total_bytes,
            "uploaded_bytes": self.uploaded_bytes,
            "progress_percent": round(self.progress_percent, 1),
            "filename": self.filename,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ProgressTracker:
    """Tracks progress of multiple uploads."""
    
    def __init__(self):
        self._uploads: dict[str, UploadProgress] = {}
    
    def create(
        self,
        total_bytes: int,
        filename: str | None = None,
    ) -> UploadProgress:
        """Create a new upload progress tracker.
        
        Args:
            total_bytes: Total file size
            filename: Original filename
            
        Returns:
            UploadProgress instance
        """
        progress = UploadProgress(
            total_bytes=total_bytes,
            filename=filename,
        )
        self._uploads[progress.upload_id] = progress
        return progress
    
    def get(self, upload_id: str) -> UploadProgress | None:
        """Get upload progress by ID.
        
        Args:
            upload_id: Upload ID
            
        Returns:
            UploadProgress or None
        """
        return self._uploads.get(upload_id)
    
    def update(
        self,
        upload_id: str,
        **kwargs,
    ) -> UploadProgress | None:
        """Update upload progress.
        
        Args:
            upload_id: Upload ID
            **kwargs: Fields to update
            
        Returns:
            Updated UploadProgress or None
        """
        progress = self._uploads.get(upload_id)
        if progress:
            progress.update(**kwargs)
        return progress
    
    def remove(self, upload_id: str) -> bool:
        """Remove completed upload from tracking.
        
        Args:
            upload_id: Upload ID
            
        Returns:
            True if removed
        """
        if upload_id in self._uploads:
            del self._uploads[upload_id]
            return True
        return False
    
    def cleanup_completed(self) -> int:
        """Remove all completed uploads.
        
        Returns:
            Number of uploads removed
        """
        to_remove = [
            uid for uid, progress in self._uploads.items()
            if progress.is_complete
        ]
        for uid in to_remove:
            del self._uploads[uid]
        return len(to_remove)
    
    def list_active(self) -> list[UploadProgress]:
        """List all active (non-complete) uploads.
        
        Returns:
            List of active uploads
        """
        return [
            progress for progress in self._uploads.values()
            if not progress.is_complete
        ]
