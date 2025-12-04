"""Storage API routes for audio and beatmap files.

Provides endpoints for:
- Direct file upload/download
- Presigned URL generation for client-side uploads
- Stem file access
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_optional
from app.services.storage import (
    AudioStorage,
    BeatmapStorage,
    get_storage,
)

router = APIRouter(prefix="/storage", tags=["storage"])


# --- Schemas ---


class UploadResponse(BaseModel):
    """Response after successful upload."""

    key: str = Field(description="Storage key for the uploaded file")
    size: int = Field(description="File size in bytes")
    content_type: str = Field(description="MIME type of the file")


class PresignedUrlRequest(BaseModel):
    """Request for presigned URL generation."""

    content_type: str = Field(
        default="audio/mpeg",
        description="Content type for upload (required for PUT URLs)",
    )
    expires_in: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="URL validity in seconds (1 min to 24 hours)",
    )


class PresignedUrlResponse(BaseModel):
    """Response with presigned URL."""

    url: str = Field(description="Presigned URL for direct access")
    expires_at: str = Field(description="ISO timestamp when URL expires")
    method: str = Field(description="HTTP method to use (GET or PUT)")


# --- Audio Endpoints ---


@router.post(
    "/audio/{song_id}",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload audio file",
)
async def upload_audio(
    song_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="Audio file (MP3, WAV, FLAC)")],
    _user: Annotated[dict | None, Depends(get_current_user_optional)] = None,
) -> UploadResponse:
    """Upload an audio file for a song.

    Accepts MP3, WAV, or FLAC audio files up to 100MB.
    """
    # Validate content type
    allowed_types = {
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/flac",
        "audio/ogg",
    }
    content_type = file.content_type or "audio/mpeg"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format. Allowed: {', '.join(allowed_types)}",
        )

    # Read file content (with size limit)
    max_size = 100 * 1024 * 1024  # 100MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB",
        )

    storage = await get_storage()
    audio_storage = AudioStorage(storage)
    result = await audio_storage.upload_audio(song_id, content, content_type)

    return UploadResponse(
        key=result.key,
        size=result.size,
        content_type=result.content_type,
    )


@router.get(
    "/audio/{song_id}",
    summary="Download audio file",
)
async def download_audio(
    song_id: uuid.UUID,
    extension: Annotated[str, Query(description="Audio format")] = "mp3",
) -> StreamingResponse:
    """Download the original audio file for a song.

    Returns the audio as a streaming response.
    """
    storage = await get_storage()
    audio_storage = AudioStorage(storage)

    try:
        # Stream the file
        async def generate():
            async for chunk in storage.stream_download(
                audio_storage._audio_key(song_id, extension)
            ):
                yield chunk

        content_type = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
        }.get(extension, "application/octet-stream")

        return StreamingResponse(
            generate(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{song_id}.{extension}"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        )


@router.get(
    "/audio/{song_id}/url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for audio download",
)
async def get_audio_download_url(
    song_id: uuid.UUID,
    extension: Annotated[str, Query(description="Audio format")] = "mp3",
    expires_in: Annotated[int, Query(ge=60, le=86400)] = 3600,
) -> PresignedUrlResponse:
    """Get a presigned URL for direct audio download.

    The URL can be used for client-side playback without authentication.
    """
    storage = await get_storage()
    audio_storage = AudioStorage(storage)

    result = await audio_storage.get_audio_url(song_id, extension, expires_in)

    return PresignedUrlResponse(
        url=result.url,
        expires_at=result.expires_at.isoformat(),
        method=result.method,
    )


@router.post(
    "/audio/{song_id}/upload-url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for audio upload",
)
async def get_audio_upload_url(
    song_id: uuid.UUID,
    request: PresignedUrlRequest,
    _user: Annotated[dict | None, Depends(get_current_user_optional)] = None,
) -> PresignedUrlResponse:
    """Get a presigned URL for direct audio upload.

    Use this for large files to upload directly to storage without
    proxying through the API server.
    """
    storage = await get_storage()
    audio_storage = AudioStorage(storage)

    ext = (
        "mp3" if "mpeg" in request.content_type else request.content_type.split("/")[-1]
    )
    key = audio_storage._audio_key(song_id, ext)

    result = await storage.get_presigned_url(
        key,
        method="PUT",
        expires_in=request.expires_in,
        content_type=request.content_type,
    )

    return PresignedUrlResponse(
        url=result.url,
        expires_at=result.expires_at.isoformat(),
        method=result.method,
    )


# --- Stem Endpoints ---


@router.get(
    "/stems/{song_id}/{stem}",
    summary="Download stem file",
)
async def download_stem(
    song_id: uuid.UUID,
    stem: Annotated[str, Path(description="Stem name (drums, bass, vocals, other)")],
) -> StreamingResponse:
    """Download a separated stem file.

    Available stems: drums, bass, vocals, other
    """
    valid_stems = {"drums", "bass", "vocals", "other", "piano", "guitar"}
    if stem not in valid_stems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stem. Available: {', '.join(valid_stems)}",
        )

    storage = await get_storage()
    audio_storage = AudioStorage(storage)

    try:

        async def generate():
            async for chunk in storage.stream_download(
                audio_storage._stem_key(song_id, stem)
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{song_id}_{stem}.wav"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stem '{stem}' not found for this song",
        )


@router.get(
    "/stems/{song_id}/{stem}/url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for stem download",
)
async def get_stem_download_url(
    song_id: uuid.UUID,
    stem: str,
    expires_in: Annotated[int, Query(ge=60, le=86400)] = 3600,
) -> PresignedUrlResponse:
    """Get a presigned URL for direct stem download."""
    # Validate stem parameter to prevent path traversal
    valid_stems = {"drums", "bass", "vocals", "other", "piano", "guitar"}
    if stem not in valid_stems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid stem. Available: {', '.join(valid_stems)}",
        )

    storage = await get_storage()
    audio_storage = AudioStorage(storage)

    result = await audio_storage.get_stem_url(song_id, stem, expires_in)

    return PresignedUrlResponse(
        url=result.url,
        expires_at=result.expires_at.isoformat(),
        method=result.method,
    )


# --- Beatmap Endpoints ---


@router.post(
    "/beatmaps/{map_id}/v{version}",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload beatmap file",
)
async def upload_beatmap(
    map_id: uuid.UUID,
    version: int,
    file: Annotated[UploadFile, File(description="Beatmap JSON file")],
    _user: Annotated[dict | None, Depends(get_current_user_optional)] = None,
) -> UploadResponse:
    """Upload a beatmap file for a specific version.

    The beatmap should be in BeatSight JSON format (.bs).
    """
    # Read content
    max_size = 10 * 1024 * 1024  # 10MB for beatmaps
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB",
        )

    storage = await get_storage()
    beatmap_storage = BeatmapStorage(storage)
    result = await beatmap_storage.upload_beatmap(map_id, version, content)

    return UploadResponse(
        key=result.key,
        size=result.size,
        content_type=result.content_type,
    )


@router.get(
    "/beatmaps/{map_id}/v{version}",
    summary="Download beatmap file",
)
async def download_beatmap(
    map_id: uuid.UUID,
    version: int,
) -> Response:
    """Download a beatmap file.

    Returns the beatmap JSON content.
    """
    storage = await get_storage()
    beatmap_storage = BeatmapStorage(storage)

    try:
        content = await beatmap_storage.download_beatmap(map_id, version)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{map_id}_v{version}.bs"',
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beatmap not found",
        )


@router.get(
    "/beatmaps/{map_id}/v{version}/url",
    response_model=PresignedUrlResponse,
    summary="Get presigned URL for beatmap download",
)
async def get_beatmap_download_url(
    map_id: uuid.UUID,
    version: int,
    expires_in: Annotated[int, Query(ge=60, le=86400)] = 3600,
) -> PresignedUrlResponse:
    """Get a presigned URL for direct beatmap download."""
    storage = await get_storage()
    beatmap_storage = BeatmapStorage(storage)

    result = await beatmap_storage.get_beatmap_url(map_id, version, expires_in)

    return PresignedUrlResponse(
        url=result.url,
        expires_at=result.expires_at.isoformat(),
        method=result.method,
    )


# --- Avatar Endpoints ---


@router.get(
    "/avatars/{user_id}",
    response_class=Response,
    summary="Get user avatar",
)
async def get_avatar(
    user_id: uuid.UUID,
) -> Response:
    """Get a user's avatar image.

    Returns a 256x256 JPEG image.
    If no avatar exists, returns 404.
    """
    storage = await get_storage()
    avatar_key = f"avatars/{user_id}.jpg"

    try:
        content = await storage.retrieve(avatar_key)
        return Response(
            content=content,
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
            },
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )
