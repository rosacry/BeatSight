"""
Metadata API routes for audio identification.

Ticket E1-007: AcoustID Integration
- POST /metadata/identify - Identify uploaded audio
- POST /metadata/identify-url - Identify audio from URL
- GET /metadata/status - Service status
- POST /metadata/identify-with-retry - Identify with automatic retry
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_current_user_optional
from app.logging import get_logger
from app.models.user import User
from app.services.acoustid import (
    get_acoustid_service,
    AcoustIDError,
    FingerprintError,
    LookupError,
)
from app.services.intake_analytics import get_intake_analytics, IntakeEvent
from app.services.rbac import Permission, require_any_permission

router = APIRouter(prefix="/metadata", tags=["metadata"])
logger = get_logger(__name__)

# RBAC dependencies
RequireAdminSystem = require_any_permission(Permission.ADMIN_SYSTEM)


# =============================================================================
# Response Models
# =============================================================================


class MetadataResponse(BaseModel):
    """Audio metadata identification response."""

    title: str | None
    artist: str | None
    album: str | None
    release_date: str | None
    confidence: float
    source: str
    acoustid: str | None = None
    musicbrainz_id: str | None = None


class IdentifyResponse(BaseModel):
    """Full identification response."""

    success: bool
    metadata: MetadataResponse | None
    message: str | None = None


class ServiceStatusResponse(BaseModel):
    """Service status response."""

    available: bool
    has_api_key: bool
    has_chromaprint: bool
    cache_size: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=ServiceStatusResponse)
async def get_metadata_status() -> ServiceStatusResponse:
    """
    Get the status of the metadata identification service.

    Returns information about whether AcoustID is properly configured.
    """
    service = get_acoustid_service()

    return ServiceStatusResponse(
        available=service.is_available,
        has_api_key=bool(service.api_key),
        has_chromaprint=bool(service._fpcalc_path),
        cache_size=len(service._cache),
    )


@router.post("/identify", response_model=IdentifyResponse)
async def identify_audio(
    file: UploadFile = File(..., description="Audio file to identify"),
    min_score: Annotated[
        float, Query(ge=0.0, le=1.0, description="Minimum confidence score")
    ] = 0.5,
    current_user: User | None = Depends(get_current_user_optional),
) -> IdentifyResponse:
    """
    Identify an uploaded audio file.

    Uses AcoustID to fingerprint the audio and look up metadata
    in the MusicBrainz database.

    The confidence score (0-1) indicates how well the audio matches
    the identified recording. Scores above 0.8 are typically very accurate.

    **Rate limits:** 10 requests per minute per user.
    """
    service = get_acoustid_service()

    if not service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio identification service is not available. Check configuration.",
        )

    # Validate file type
    content_type = file.content_type or ""
    if not content_type.startswith("audio/") and not file.filename.lower().endswith(
        (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an audio file",
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        )

    # Size limit: 100MB
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 100MB limit",
        )

    logger.info(
        "Identifying audio file",
        filename=file.filename,
        size=len(content),
        user_id=str(current_user.id) if current_user else None,
    )

    try:
        result = await service.identify_audio_bytes(
            content,
            filename=file.filename or "audio.mp3",
            min_score=min_score,
        )

        if result:
            return IdentifyResponse(
                success=True,
                metadata=MetadataResponse(**result.to_dict()),
            )
        else:
            return IdentifyResponse(
                success=False,
                metadata=None,
                message="No matching recordings found above the confidence threshold",
            )

    except AcoustIDError as e:
        logger.error("Audio identification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/identify-fingerprint", response_model=IdentifyResponse)
async def identify_fingerprint(
    fingerprint: str = Query(..., description="Chromaprint fingerprint (base64)"),
    duration: float = Query(..., gt=0, description="Audio duration in seconds"),
    min_score: Annotated[
        float, Query(ge=0.0, le=1.0, description="Minimum confidence score")
    ] = 0.5,
    current_user: User | None = Depends(get_current_user_optional),
) -> IdentifyResponse:
    """
    Identify audio from a pre-computed fingerprint.

    If you've already generated a Chromaprint fingerprint client-side,
    you can submit it directly without uploading the audio file.

    This is useful for:
    - Mobile apps that generate fingerprints locally
    - Batch processing where fingerprints are cached
    - Reducing bandwidth by not uploading full audio
    """
    from app.services.acoustid import AudioFingerprint, LookupError

    service = get_acoustid_service()

    if not service.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AcoustID API key not configured",
        )

    try:
        fp = AudioFingerprint(duration=duration, fingerprint=fingerprint)
        results = await service.lookup_fingerprint(fp)

        # Find best result above threshold
        for result in results:
            if result.score >= min_score and (result.title or result.artist):
                return IdentifyResponse(
                    success=True,
                    metadata=MetadataResponse(
                        title=result.title,
                        artist=result.artist,
                        album=result.album,
                        release_date=result.release_date,
                        confidence=result.score,
                        source="acoustid",
                        acoustid=result.id,
                        musicbrainz_id=result.musicbrainz_id,
                    ),
                )

        return IdentifyResponse(
            success=False,
            metadata=None,
            message="No matching recordings found above the confidence threshold",
        )

    except LookupError as e:
        logger.error("Fingerprint lookup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/cache",
    dependencies=[Depends(RequireAdminSystem)],
)
async def clear_metadata_cache(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Clear the metadata lookup cache.

    Requires admin:system permission. Admin users can clear the cache
    to force fresh lookups.
    """
    service = get_acoustid_service()
    cleared = service.clear_cache()

    logger.info(
        "Metadata cache cleared",
        entries=cleared,
        user_id=str(current_user.id),
    )

    return {
        "success": True,
        "cleared_entries": cleared,
    }


class IdentifyWithRetryResponse(BaseModel):
    """Response for identify with retry endpoint."""

    success: bool
    metadata: MetadataResponse | None
    message: str | None = None
    attempts: int = 1
    retry_exhausted: bool = False


@router.post("/identify-with-retry", response_model=IdentifyWithRetryResponse)
async def identify_audio_with_retry(
    file: UploadFile = File(..., description="Audio file to identify"),
    min_score: Annotated[
        float, Query(ge=0.0, le=1.0, description="Minimum confidence score")
    ] = 0.5,
    max_retries: Annotated[
        int, Query(ge=1, le=5, description="Maximum retry attempts")
    ] = 3,
    session_id: Annotated[
        str | None, Query(description="Session ID for analytics")
    ] = None,
    current_user: User | None = Depends(get_current_user_optional),
) -> IdentifyWithRetryResponse:
    """
    Identify an uploaded audio file with automatic retry on transient failures.

    This endpoint will retry fingerprinting and lookup up to `max_retries` times
    if transient errors occur (network issues, rate limits, etc.).

    Use this for more reliable identification when immediate response isn't critical.

    **Analytics:** Provides session_id to track intake funnel events.
    """
    service = get_acoustid_service()
    analytics = get_intake_analytics()
    user_id = current_user.id if current_user else None

    if not service.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio identification service is not available. Check configuration.",
        )

    # Validate file type
    content_type = file.content_type or ""
    if not content_type.startswith("audio/") and not file.filename.lower().endswith(
        (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an audio file",
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        if session_id:
            analytics.track_upload_failed(session_id, str(e), user_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        )

    # Size limit: 100MB
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 100MB limit",
        )

    if session_id:
        analytics.track(
            IntakeEvent.FINGERPRINT_STARTED,
            session_id=session_id,
            user_id=user_id,
        )

    # Retry loop with exponential backoff
    last_error: str | None = None
    for attempt in range(1, max_retries + 1):
        try:
            result = await service.identify_audio_bytes(
                content,
                filename=file.filename or "audio.mp3",
                min_score=min_score,
            )

            if result:
                if session_id:
                    analytics.track_metadata_found(
                        session_id=session_id,
                        song_id=uuid.uuid4(),  # Placeholder - would use actual song ID
                        source=result.source,
                        confidence=result.confidence,
                        user_id=user_id,
                    )

                return IdentifyWithRetryResponse(
                    success=True,
                    metadata=MetadataResponse(**result.to_dict()),
                    attempts=attempt,
                )
            else:
                # No match found - not a retriable error
                if session_id:
                    analytics.track_metadata_not_found(session_id, user_id=user_id)

                return IdentifyWithRetryResponse(
                    success=False,
                    metadata=None,
                    message="No matching recordings found above the confidence threshold",
                    attempts=attempt,
                )

        except (FingerprintError, LookupError) as e:
            last_error = str(e)

            if session_id and attempt < max_retries:
                analytics.track_fingerprint_retried(
                    session_id=session_id,
                    song_id=uuid.uuid4(),  # Placeholder
                    retry_count=attempt,
                    user_id=user_id,
                )

            if attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s...
                backoff = 2 ** (attempt - 1)
                logger.warning(
                    "Fingerprint attempt failed, retrying",
                    attempt=attempt,
                    max_retries=max_retries,
                    backoff_seconds=backoff,
                    error=str(e),
                )
                await asyncio.sleep(backoff)
            else:
                logger.error(
                    "Fingerprint failed after all retries",
                    attempts=attempt,
                    error=str(e),
                )

        except Exception as e:
            # Unexpected error - don't retry
            last_error = str(e)
            logger.error("Unexpected identification error", error=str(e))
            break

    # All retries exhausted
    if session_id:
        analytics.track_fingerprint_failed(
            session_id=session_id,
            error=last_error,
            retry_count=max_retries,
            user_id=user_id,
        )

    return IdentifyWithRetryResponse(
        success=False,
        metadata=None,
        message=f"Identification failed after {max_retries} attempts: {last_error}",
        attempts=max_retries,
        retry_exhausted=True,
    )


class ManualMetadataInput(BaseModel):
    """Manual metadata entry for songs that couldn't be identified."""

    title: str
    artist: str
    album: str | None = None
    release_date: str | None = None


class ManualMetadataResponse(BaseModel):
    """Response for manual metadata entry."""

    success: bool
    metadata: MetadataResponse


@router.post("/manual", response_model=ManualMetadataResponse)
async def submit_manual_metadata(
    input_data: ManualMetadataInput,
    session_id: Annotated[
        str | None, Query(description="Session ID for analytics")
    ] = None,
    current_user: User | None = Depends(get_current_user_optional),
) -> ManualMetadataResponse:
    """
    Submit manual metadata when automatic identification fails.

    This is the fallback path when AcoustID/MusicBrainz cannot identify
    the audio. The user provides the song information directly.

    **Analytics:** Tracks manual entry in the intake funnel.
    """
    analytics = get_intake_analytics()
    user_id = current_user.id if current_user else None

    if session_id:
        analytics.track_metadata_manual(
            session_id=session_id,
            song_id=uuid.uuid4(),  # Placeholder - would be actual song ID
            user_id=user_id,
        )

    logger.info(
        "Manual metadata submitted",
        title=input_data.title,
        artist=input_data.artist,
        user_id=str(user_id) if user_id else None,
    )

    return ManualMetadataResponse(
        success=True,
        metadata=MetadataResponse(
            title=input_data.title,
            artist=input_data.artist,
            album=input_data.album,
            release_date=input_data.release_date,
            confidence=1.0,  # User-provided is 100% confidence
            source="manual",
        ),
    )
