"""Tests for file upload utilities."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pytest

from app.utils.file_upload import (
    ALLOWED_AUDIO_TYPES,
    ALLOWED_IMAGE_TYPES,
    FileValidationResult,
    FileValidator,
    ProgressTracker,
    SavedFile,
    TempDirectory,
    TempFile,
    UploadProgress,
    UploadStatus,
    compute_file_hash,
    generate_secure_filename,
    get_file_extension,
    save_upload_sync,
    validate_audio_file,
    validate_image_file,
)


# =============================================================================
# FileValidator Tests
# =============================================================================


class TestFileValidator:
    """Tests for FileValidator class."""

    def test_validate_basic_file(self):
        """Test validating a basic file."""
        validator = FileValidator()
        file = io.BytesIO(b"test content")

        result = validator.validate(file)

        assert result.is_valid is True
        assert result.file_size == 12

    def test_validate_file_too_large(self):
        """Test rejecting oversized file."""
        validator = FileValidator(max_size_bytes=10)
        file = io.BytesIO(b"x" * 100)

        result = validator.validate(file)

        assert result.is_valid is False
        assert any("too large" in e.lower() for e in result.errors)

    def test_validate_file_too_small(self):
        """Test rejecting undersized file."""
        validator = FileValidator(min_size_bytes=100)
        file = io.BytesIO(b"tiny")

        result = validator.validate(file)

        assert result.is_valid is False
        assert any("small" in e.lower() or "empty" in e.lower() for e in result.errors)

    def test_validate_allowed_extension(self):
        """Test extension validation."""
        validator = FileValidator(allowed_extensions={".txt", ".md"})

        file = io.BytesIO(b"content")

        result_good = validator.validate(file, "readme.txt")
        assert result_good.is_valid is True

        result_bad = validator.validate(file, "script.exe")
        assert result_bad.is_valid is False

    def test_validate_magic_bytes_mp3(self):
        """Test MP3 magic byte detection."""
        validator = FileValidator(
            allowed_types=ALLOWED_AUDIO_TYPES,
            check_magic_bytes=True,
        )

        # ID3 tag header (MP3)
        mp3_data = b"ID3" + b"\x00" * 100
        file = io.BytesIO(mp3_data)

        result = validator.validate(file)

        assert result.is_valid is True
        assert result.detected_type == "audio/mpeg"

    def test_validate_magic_bytes_jpeg(self):
        """Test JPEG magic byte detection."""
        validator = FileValidator(
            allowed_types=ALLOWED_IMAGE_TYPES,
            check_magic_bytes=True,
        )

        # JPEG header
        jpeg_data = b"\xff\xd8\xff" + b"\x00" * 100
        file = io.BytesIO(jpeg_data)

        result = validator.validate(file)

        assert result.is_valid is True
        assert result.detected_type == "image/jpeg"

    def test_validate_magic_bytes_png(self):
        """Test PNG magic byte detection."""
        validator = FileValidator(
            allowed_types=ALLOWED_IMAGE_TYPES,
            check_magic_bytes=True,
        )

        # PNG header
        png_data = b"\x89PNG" + b"\x00" * 100
        file = io.BytesIO(png_data)

        result = validator.validate(file)

        assert result.is_valid is True
        assert result.detected_type == "image/png"

    def test_validate_reject_wrong_type(self):
        """Test rejecting file with wrong type."""
        validator = FileValidator(
            allowed_types=frozenset({"image/jpeg"}),
            check_magic_bytes=True,
        )

        # PNG file trying to upload as JPEG
        png_data = b"\x89PNG" + b"\x00" * 100
        file = io.BytesIO(png_data)

        result = validator.validate(file)

        assert result.is_valid is False
        assert any("not allowed" in e.lower() for e in result.errors)

    def test_validate_fallback_to_extension(self):
        """Test falling back to extension when magic bytes don't match."""
        validator = FileValidator(check_magic_bytes=True)

        file = io.BytesIO(b"plain text content")
        result = validator.validate(file, "document.txt")

        assert result.is_valid is True
        assert result.detected_type == "text/plain"


class TestValidateAudioFile:
    """Tests for validate_audio_file helper."""

    def test_valid_mp3_by_magic(self):
        """Test validating MP3 by magic bytes."""
        mp3_data = b"ID3" + b"\x00" * 100
        file = io.BytesIO(mp3_data)

        result = validate_audio_file(file)

        assert result.is_valid is True

    def test_valid_wav_by_magic(self):
        """Test validating WAV by magic bytes."""
        # WAV files are RIFF containers with WAVE format
        wav_data = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 100
        file = io.BytesIO(wav_data)

        result = validate_audio_file(file)

        assert result.is_valid is True

    def test_reject_image_as_audio(self):
        """Test rejecting image file as audio."""
        png_data = b"\x89PNG" + b"\x00" * 100
        file = io.BytesIO(png_data)

        result = validate_audio_file(file)

        assert result.is_valid is False


class TestValidateImageFile:
    """Tests for validate_image_file helper."""

    def test_valid_jpeg(self):
        """Test validating JPEG."""
        jpeg_data = b"\xff\xd8\xff" + b"\x00" * 100
        file = io.BytesIO(jpeg_data)

        result = validate_image_file(file)

        assert result.is_valid is True

    def test_reject_audio_as_image(self):
        """Test rejecting audio file as image."""
        mp3_data = b"ID3" + b"\x00" * 100
        file = io.BytesIO(mp3_data)

        result = validate_image_file(file)

        assert result.is_valid is False


# =============================================================================
# FileValidationResult Tests
# =============================================================================


class TestFileValidationResult:
    """Tests for FileValidationResult class."""

    def test_success_result(self):
        """Test creating success result."""
        result = FileValidationResult.success(
            detected_type="audio/mpeg",
            file_size=1024,
        )

        assert result.is_valid is True
        assert result.detected_type == "audio/mpeg"
        assert result.file_size == 1024

    def test_failure_result(self):
        """Test creating failure result."""
        result = FileValidationResult.failure(
            "File too large",
            "Invalid type",
        )

        assert result.is_valid is False
        assert len(result.errors) == 2


# =============================================================================
# File Naming Tests
# =============================================================================


class TestGenerateSecureFilename:
    """Tests for generate_secure_filename function."""

    def test_basic_filename(self):
        """Test generating basic filename."""
        filename = generate_secure_filename()

        assert filename is not None
        assert len(filename) == 36  # UUID length

    def test_preserve_extension(self):
        """Test preserving file extension."""
        filename = generate_secure_filename(
            original_filename="song.mp3",
            preserve_extension=True,
        )

        assert filename.endswith(".mp3")

    def test_uppercase_extension_lowercased(self):
        """Test uppercase extension is lowercased."""
        filename = generate_secure_filename(
            original_filename="song.MP3",
            preserve_extension=True,
        )

        assert filename.endswith(".mp3")

    def test_prefix(self):
        """Test adding prefix."""
        filename = generate_secure_filename(
            prefix="audio",
        )

        assert filename.startswith("audio_")

    def test_timestamp(self):
        """Test adding timestamp."""
        filename = generate_secure_filename(
            use_timestamp=True,
            use_uuid=False,
        )

        # Should contain date pattern
        assert "_" in filename or filename.isdigit() or len(filename) > 10

    def test_sanitize_prefix(self):
        """Test sanitizing prefix."""
        filename = generate_secure_filename(
            prefix="path/to/file",
        )

        assert "/" not in filename


class TestGetFileExtension:
    """Tests for get_file_extension function."""

    def test_get_extension(self):
        """Test getting extension."""
        assert get_file_extension("song.mp3") == ".mp3"
        assert get_file_extension("document.pdf") == ".pdf"

    def test_uppercase_lowercased(self):
        """Test extension is lowercased."""
        assert get_file_extension("IMAGE.PNG") == ".png"

    def test_no_extension(self):
        """Test file without extension."""
        assert get_file_extension("filename") == ""

    def test_multiple_dots(self):
        """Test file with multiple dots."""
        assert get_file_extension("my.song.mp3") == ".mp3"


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_sha256_hash(self):
        """Test SHA256 hash computation."""
        content = b"test content"
        file = io.BytesIO(content)

        hash_value = compute_file_hash(file)

        assert len(hash_value) == 64  # SHA256 hex length

    def test_same_content_same_hash(self):
        """Test same content produces same hash."""
        content = b"identical content"

        hash1 = compute_file_hash(io.BytesIO(content))
        hash2 = compute_file_hash(io.BytesIO(content))

        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """Test different content produces different hash."""
        hash1 = compute_file_hash(io.BytesIO(b"content A"))
        hash2 = compute_file_hash(io.BytesIO(b"content B"))

        assert hash1 != hash2

    def test_file_position_reset(self):
        """Test file position is reset after hashing."""
        file = io.BytesIO(b"test content")
        file.seek(5)  # Move to middle

        compute_file_hash(file)

        assert file.tell() == 0


# =============================================================================
# File Saving Tests
# =============================================================================


class TestSaveUploadSync:
    """Tests for save_upload_sync function."""

    def test_save_file(self):
        """Test saving a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            content = b"test file content"
            file = io.BytesIO(content)

            result = save_upload_sync(
                file,
                temp_dir,
                filename="test.txt",
            )

            assert result.path.exists()
            assert result.filename == "test.txt"
            assert result.size_bytes == len(content)
            assert result.content_hash is not None

    def test_save_generates_filename(self):
        """Test filename is generated if not provided."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file = io.BytesIO(b"content")

            result = save_upload_sync(file, temp_dir)

            assert result.filename is not None
            assert len(result.filename) > 0

    def test_save_creates_directory(self):
        """Test directory is created if needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = Path(temp_dir) / "nested" / "path"
            file = io.BytesIO(b"content")

            result = save_upload_sync(
                file,
                nested_dir,
                create_dirs=True,
            )

            assert result.path.exists()

    def test_save_no_overwrite(self):
        """Test overwrite protection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file = io.BytesIO(b"content")

            # Save first file
            save_upload_sync(file, temp_dir, filename="test.txt")

            # Try to save again
            file.seek(0)
            with pytest.raises(FileExistsError):
                save_upload_sync(
                    file,
                    temp_dir,
                    filename="test.txt",
                    overwrite=False,
                )

    def test_save_with_overwrite(self):
        """Test allowing overwrite."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save first file
            file1 = io.BytesIO(b"original")
            save_upload_sync(file1, temp_dir, filename="test.txt")

            # Overwrite
            file2 = io.BytesIO(b"updated")
            result = save_upload_sync(
                file2,
                temp_dir,
                filename="test.txt",
                overwrite=True,
            )

            content = result.path.read_bytes()
            assert content == b"updated"


class TestSavedFile:
    """Tests for SavedFile class."""

    def test_size_mb(self):
        """Test size in MB calculation."""
        saved = SavedFile(
            path=Path("/test/file.txt"),
            filename="file.txt",
            size_bytes=5 * 1024 * 1024,  # 5MB
        )

        assert saved.size_mb == 5.0


# =============================================================================
# Temporary File Tests
# =============================================================================


class TestTempFile:
    """Tests for TempFile context manager."""

    def test_creates_temp_file(self):
        """Test temp file is created."""
        with TempFile(suffix=".txt") as temp:
            assert temp.path.exists()
            assert temp.path.suffix == ".txt"

    def test_deletes_on_exit(self):
        """Test temp file is deleted on exit."""
        path = None
        with TempFile() as temp:
            path = temp.path
            assert path.exists()

        assert not path.exists()

    def test_preserves_if_delete_false(self):
        """Test temp file preserved if delete=False."""
        path = None
        with TempFile(delete=False) as temp:
            path = temp.path

        try:
            assert path.exists()
        finally:
            path.unlink()  # Clean up

    def test_write_data(self):
        """Test writing data to temp file."""
        with TempFile() as temp:
            temp.write(b"test data")

            content = temp.path.read_bytes()
            assert content == b"test data"

    def test_write_from_file(self):
        """Test writing from file-like object."""
        source = io.BytesIO(b"source content")

        with TempFile() as temp:
            bytes_written = temp.write_from(source)

            assert bytes_written == 14
            assert temp.path.read_bytes() == b"source content"

    @pytest.mark.asyncio
    async def test_async_context(self):
        """Test async context manager."""
        async with TempFile(suffix=".txt") as temp:
            assert temp.path.exists()


class TestTempDirectory:
    """Tests for TempDirectory context manager."""

    def test_creates_temp_dir(self):
        """Test temp directory is created."""
        with TempDirectory() as temp:
            assert temp.path.exists()
            assert temp.path.is_dir()

    def test_deletes_on_exit(self):
        """Test temp directory is deleted on exit."""
        path = None
        with TempDirectory() as temp:
            path = temp.path
            (path / "file.txt").write_text("content")

        assert not path.exists()

    def test_preserves_if_delete_false(self):
        """Test directory preserved if delete=False."""
        path = None
        with TempDirectory(delete=False) as temp:
            path = temp.path

        try:
            assert path.exists()
        finally:
            import shutil

            shutil.rmtree(path)

    @pytest.mark.asyncio
    async def test_async_context(self):
        """Test async context manager."""
        async with TempDirectory() as temp:
            assert temp.path.exists()


# =============================================================================
# Upload Progress Tests
# =============================================================================


class TestUploadProgress:
    """Tests for UploadProgress class."""

    def test_initial_state(self):
        """Test initial progress state."""
        progress = UploadProgress(total_bytes=1000)

        assert progress.status == UploadStatus.PENDING
        assert progress.uploaded_bytes == 0
        assert progress.progress_percent == 0.0

    def test_progress_percent(self):
        """Test progress percentage calculation."""
        progress = UploadProgress(
            total_bytes=1000,
            uploaded_bytes=500,
        )

        assert progress.progress_percent == 50.0

    def test_progress_percent_zero_total(self):
        """Test progress with zero total bytes."""
        progress = UploadProgress(total_bytes=0)

        assert progress.progress_percent == 0.0

    def test_is_complete(self):
        """Test completion check."""
        progress = UploadProgress()

        assert progress.is_complete is False

        progress.status = UploadStatus.COMPLETED
        assert progress.is_complete is True

        progress.status = UploadStatus.FAILED
        assert progress.is_complete is True

    def test_update(self):
        """Test progress update."""
        progress = UploadProgress(total_bytes=1000)

        progress.update(
            uploaded_bytes=500,
            status=UploadStatus.UPLOADING,
        )

        assert progress.uploaded_bytes == 500
        assert progress.status == UploadStatus.UPLOADING
        assert progress.started_at is not None

    def test_to_dict(self):
        """Test conversion to dictionary."""
        progress = UploadProgress(
            total_bytes=1000,
            filename="test.mp3",
        )

        data = progress.to_dict()

        assert data["total_bytes"] == 1000
        assert data["filename"] == "test.mp3"
        assert data["progress_percent"] == 0.0


class TestProgressTracker:
    """Tests for ProgressTracker class."""

    def test_create_upload(self):
        """Test creating new upload tracker."""
        tracker = ProgressTracker()

        progress = tracker.create(total_bytes=1000, filename="test.mp3")

        assert progress.upload_id is not None
        assert progress.total_bytes == 1000

    def test_get_upload(self):
        """Test getting upload by ID."""
        tracker = ProgressTracker()
        progress = tracker.create(total_bytes=1000)

        retrieved = tracker.get(progress.upload_id)

        assert retrieved is not None
        assert retrieved.upload_id == progress.upload_id

    def test_get_nonexistent(self):
        """Test getting nonexistent upload."""
        tracker = ProgressTracker()

        assert tracker.get("nonexistent") is None

    def test_update_upload(self):
        """Test updating upload progress."""
        tracker = ProgressTracker()
        progress = tracker.create(total_bytes=1000)

        tracker.update(
            progress.upload_id,
            uploaded_bytes=500,
            status=UploadStatus.UPLOADING,
        )

        updated = tracker.get(progress.upload_id)
        assert updated.uploaded_bytes == 500

    def test_remove_upload(self):
        """Test removing upload."""
        tracker = ProgressTracker()
        progress = tracker.create(total_bytes=1000)

        removed = tracker.remove(progress.upload_id)

        assert removed is True
        assert tracker.get(progress.upload_id) is None

    def test_remove_nonexistent(self):
        """Test removing nonexistent upload."""
        tracker = ProgressTracker()

        assert tracker.remove("nonexistent") is False

    def test_cleanup_completed(self):
        """Test cleaning up completed uploads."""
        tracker = ProgressTracker()

        p1 = tracker.create(total_bytes=100)
        p2 = tracker.create(total_bytes=200)
        p3 = tracker.create(total_bytes=300)

        p1.status = UploadStatus.COMPLETED
        p2.status = UploadStatus.FAILED
        # p3 stays pending

        removed = tracker.cleanup_completed()

        assert removed == 2
        assert tracker.get(p1.upload_id) is None
        assert tracker.get(p2.upload_id) is None
        assert tracker.get(p3.upload_id) is not None

    def test_list_active(self):
        """Test listing active uploads."""
        tracker = ProgressTracker()

        p1 = tracker.create(total_bytes=100)
        p2 = tracker.create(total_bytes=200)

        p1.status = UploadStatus.UPLOADING
        p2.status = UploadStatus.COMPLETED

        active = tracker.list_active()

        assert len(active) == 1
        assert active[0].upload_id == p1.upload_id


class TestUploadStatus:
    """Tests for UploadStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert UploadStatus.PENDING.value == "pending"
        assert UploadStatus.UPLOADING.value == "uploading"
        assert UploadStatus.COMPLETED.value == "completed"
        assert UploadStatus.FAILED.value == "failed"
