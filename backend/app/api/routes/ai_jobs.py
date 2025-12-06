"""AI job API routes."""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db_session
from app.config import get_settings
from app.db.redis import ProgressUpdate, RedisKeys, get_redis
from app.models.ai_job import AIJobState
from app.models.user import User
from app.schemas.ai_jobs import (
    AIJobCreate,
    AIJobEnqueueResponse,
    AIJobProgressUpdate,
    AIJobRead,
    QuotaStatusRead,
)
from app.schemas.pagination import PaginatedResponse
from app.services.ai_jobs import AIJobService
from app.services.modal_gpu import (
    ModalConnectionError,
    ModalJobError,
    get_modal_service,
)
from app.services.quota import QuotaExceededError, QuotaService, QuotaStatus

router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


# =============================================================================
# Worker Authentication Dependency
# =============================================================================


async def verify_worker_secret(
    x_worker_secret: str = Header(..., alias="X-Worker-Secret"),
) -> bool:
    """Verify worker secret for internal AI worker endpoints.

    This protects worker-only endpoints (claim, heartbeat, progress, release)
    from unauthorized access. Without this, anyone could:
    - Claim jobs meant for legitimate workers
    - Mark jobs as failed to disrupt service
    - Send fake progress updates to deceive users
    """
    settings = get_settings()
    if x_worker_secret != settings.worker_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker secret",
            headers={"WWW-Authenticate": "X-Worker-Secret"},
        )
    return True


def _quota_to_read(status: QuotaStatus) -> QuotaStatusRead:
    """Convert QuotaStatus to Pydantic model."""
    return QuotaStatusRead(
        plan=status.plan.value if status.plan else None,
        used_this_month=status.used_this_month,
        used_today=status.used_today,
        remaining_month=status.remaining_month,
        remaining_today=status.remaining_today,
        limit_month=status.limits.jobs_per_month,
        limit_day=status.limits.jobs_per_day,
        resets_at=status.resets_at,
        priority=int(status.limits.priority),
    )


@router.post(
    "", response_model=AIJobEnqueueResponse, status_code=status.HTTP_202_ACCEPTED
)
async def enqueue_job(
    payload: AIJobCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> AIJobEnqueueResponse:
    """
    Enqueue an AI mapping job.

    Authentication is optional - anonymous users can enqueue jobs but have
    stricter rate limits and lower priority.

    When Modal GPU orchestration is enabled, the job is immediately dispatched
    to Modal's serverless GPU infrastructure. Otherwise, the job is queued
    for processing by local workers.

    Returns 429 Too Many Requests if the user has exceeded their quota.
    """
    user_id = current_user.id if current_user else None

    # Check quota
    quota_service = QuotaService(session)
    try:
        quota_status = await quota_service.check_quota(user_id)
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "AI generation quota exceeded",
                "limit": e.limit,
                "used": e.used,
                "resets_at": e.resets_at.isoformat() if e.resets_at else None,
            },
        )

    # Get priority based on subscription
    priority = await quota_service.get_priority(user_id)

    # Override payload priority with subscription-based priority
    payload.priority = priority

    # Enqueue the job
    ai_service = AIJobService(session)
    job = await ai_service.enqueue(payload, requested_by=user_id)

    # Consume quota (only for authenticated users)
    used_credit = False
    if user_id:
        quota_status, used_credit = await quota_service.consume_quota(user_id, job.id)

    # Try to dispatch to Modal if enabled
    modal_service = get_modal_service()
    if modal_service.is_enabled():
        try:
            # Get presigned audio URL for Modal to download
            from app.services.storage import get_storage, AudioStorage

            storage = await get_storage()
            audio_storage = AudioStorage(storage)

            # Try common audio formats
            audio_url = None
            for ext in ["mp3", "wav", "flac"]:
                try:
                    url_result = await audio_storage.get_audio_url(
                        payload.song_id, ext, expires_in=3600
                    )
                    audio_url = url_result.url
                    break
                except FileNotFoundError:
                    continue

            if audio_url:
                # Convert options to dict for Modal
                modal_options = (
                    payload.options.model_dump(exclude_none=True)
                    if payload.options
                    else None
                )

                result = await modal_service.trigger_job(
                    job_id=str(job.id),
                    audio_url=audio_url,
                    song_id=str(payload.song_id),
                    options=modal_options,
                )

                if result.accepted:
                    # Update job state to processing since Modal will handle it
                    await ai_service.claim_job_directly(
                        job.id,
                        worker_id=uuid.UUID(int=0),  # Special ID for Modal
                    )
            else:
                # No audio file found - job will wait for manual trigger or local worker
                pass

        except (ModalConnectionError, ModalJobError) as e:
            # Modal dispatch failed - job stays queued for local workers
            # This is a graceful degradation, not a failure
            import logging

            logging.getLogger(__name__).warning(
                f"Modal dispatch failed for job {job.id}, falling back to queue: {e}"
            )

    # Get queue position
    position = await ai_service.get_queue_position(job.id)

    # Estimate wait time (rough: ~3 min per job)
    estimated_wait = position * 3 if position is not None else None

    return AIJobEnqueueResponse(
        job=AIJobRead.model_validate(job),
        queue_position=position,
        estimated_wait_minutes=estimated_wait,
        quota=_quota_to_read(quota_status),
    )


@router.get("/quota", response_model=QuotaStatusRead)
async def get_quota_status(
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> QuotaStatusRead:
    """
    Get current AI generation quota status.

    Returns quota limits and usage for the current user or anonymous limits.
    """
    user_id = current_user.id if current_user else None
    quota_service = QuotaService(session)
    status = await quota_service.get_quota_status(user_id)
    return _quota_to_read(status)


@router.get("", response_model=PaginatedResponse[AIJobRead])
async def list_jobs(
    song_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> PaginatedResponse[AIJobRead]:
    """List AI jobs with pagination, optionally filtered by song.

    Authenticated users see their own jobs, anonymous users see public jobs.
    """
    service = AIJobService(session)
    user_id = current_user.id if current_user else None

    # Calculate offset
    offset = (page - 1) * page_size

    # Fetch jobs and total count in parallel
    jobs_task = service.list_jobs(
        song_id=song_id, user_id=user_id, limit=page_size, offset=offset
    )
    count_task = service.count_jobs(song_id=song_id, user_id=user_id)
    jobs, total = await asyncio.gather(jobs_task, count_task)

    items = [AIJobRead.model_validate(job) for job in jobs]
    return PaginatedResponse.create(
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{job_id}", response_model=AIJobRead)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AIJobRead:
    """Get a specific AI job by ID."""
    service = AIJobService(session)
    job = await service.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return AIJobRead.model_validate(job)


@router.post(
    "/{job_id}/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(verify_worker_secret)],
)
async def worker_heartbeat(
    job_id: uuid.UUID,
    worker_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Worker heartbeat to indicate job is still being processed.

    Workers should call this every 30-60 seconds while processing a job.
    Jobs without a heartbeat for 5 minutes are considered stale and can
    be reclaimed by other workers.

    **Requires X-Worker-Secret header for authentication.**
    """
    service = AIJobService(session)
    job = await service.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    if job.worker_id and job.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job is being processed by another worker",
        )
    await service.heartbeat(job_id, worker_id)


@router.patch(
    "/{job_id}/progress",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(verify_worker_secret)],
)
async def update_progress(
    job_id: uuid.UUID,
    payload: AIJobProgressUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Update job progress.

    Workers should call this to report progress during long-running jobs.
    Progress is visible to users in the queue UI.

    **Requires X-Worker-Secret header for authentication.**
    """
    service = AIJobService(session)
    job = await service.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    await service.update_progress(
        job_id, payload.progress_percent, payload.progress_message
    )


@router.post(
    "/claim",
    response_model=AIJobRead | None,
    dependencies=[Depends(verify_worker_secret)],
)
async def claim_job(
    worker_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AIJobRead | None:
    """
    Claim the next available job for processing.

    Returns the oldest queued job and marks it as processing by this worker.
    Returns null if no jobs are available.
    """
    service = AIJobService(session)
    job = await service.claim_job(worker_id)
    if not job:
        return None
    return AIJobRead.model_validate(job)


@router.post(
    "/{job_id}/release",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    dependencies=[Depends(verify_worker_secret)],
)
async def release_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """
    Release a job back to the queue for retry.

    Use this when a worker encounters a recoverable error and wants to
    allow another worker to retry the job.

    **Requires X-Worker-Secret header for authentication.**
    """
    service = AIJobService(session)
    job = await service.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    await service.release_job(job_id)


@router.get(
    "/stale/list",
    response_model=list[AIJobRead],
    dependencies=[Depends(verify_worker_secret)],
)
async def list_stale_jobs(
    threshold_seconds: int = 300,
    session: AsyncSession = Depends(get_db_session),
) -> list[AIJobRead]:
    """
    List jobs with stale heartbeats.

    Used by orchestration to identify and reclaim jobs from failed workers.
    Default threshold is 5 minutes (300 seconds).

    **Requires X-Worker-Secret header for authentication.**
    """
    service = AIJobService(session)
    jobs = await service.find_stale_jobs(threshold_seconds)
    return [AIJobRead.model_validate(job) for job in jobs]


# =============================================================================
# SSE Streaming Endpoints (E2-004)
# =============================================================================


async def _progress_event_generator(
    job_id: uuid.UUID,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for job progress updates.

    Yields events in the format:
        event: progress
        data: {"percent": 50, "message": "Processing...", "stage": "separation"}

        event: complete
        data: {"job_id": "...", "status": "completed"}

        event: error
        data: {"message": "Job failed", "error": "..."}
    """
    service = AIJobService(session)

    # First, send current job status
    job = await service.get_by_id(job_id)
    if not job:
        yield 'event: error\ndata: {"message": "Job not found"}\n\n'
        return

    # Send initial state
    initial_data = {
        "job_id": str(job.id),
        "status": job.state.value,
        "percent": job.progress_percent or 0,
        "message": job.progress_message,
    }
    yield f"event: status\ndata: {_json_dumps(initial_data)}\n\n"

    # If job is already complete or failed, just return
    if job.state in (AIJobState.COMPLETE, AIJobState.FAILED, AIJobState.CANCELLED):
        final_data = {"job_id": str(job.id), "status": job.state.value}
        yield f"event: complete\ndata: {_json_dumps(final_data)}\n\n"
        return

    # Subscribe to progress updates via Redis pub/sub
    redis = await get_redis()
    channel = RedisKeys.job_progress_channel(job_id)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        # Also check periodically in case messages are missed
        last_check = datetime.now(timezone.utc)
        check_interval = 5.0  # seconds
        timeout = 0.5  # seconds for message wait
        max_idle = 300  # 5 minutes max idle time
        idle_since = datetime.now(timezone.utc)

        while True:
            # Check for messages with timeout
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True), timeout=timeout
                )
            except asyncio.TimeoutError:
                message = None

            if message and message["type"] == "message":
                # Got a progress update
                idle_since = datetime.now(timezone.utc)
                update = ProgressUpdate.from_json(message["data"])
                progress_data = {
                    "percent": update.percent,
                    "message": update.message,
                    "stage": update.stage,
                    "timestamp": update.timestamp.isoformat(),
                }
                yield f"event: progress\ndata: {_json_dumps(progress_data)}\n\n"

            # Periodically check job status directly
            now = datetime.now(timezone.utc)
            if (now - last_check).total_seconds() >= check_interval:
                last_check = now
                job = await service.get_by_id(job_id)

                if not job:
                    yield 'event: error\ndata: {"message": "Job deleted"}\n\n'
                    break

                if job.state == AIJobState.COMPLETE:
                    final_data = {
                        "job_id": str(job.id),
                        "status": "completed",
                        "beatmap_id": str(job.beatmap_id) if job.beatmap_id else None,
                    }
                    yield f"event: complete\ndata: {_json_dumps(final_data)}\n\n"
                    break

                if job.state == AIJobState.FAILED:
                    error_data = {
                        "job_id": str(job.id),
                        "status": "failed",
                        "error": job.error_message,
                    }
                    yield f"event: error\ndata: {_json_dumps(error_data)}\n\n"
                    break

                if job.state == AIJobState.CANCELLED:
                    yield f'event: complete\ndata: {{"job_id": "{job.id}", "status": "cancelled"}}\n\n'
                    break

                # Send keepalive/heartbeat
                yield f": keepalive {now.isoformat()}\n\n"

            # Check idle timeout
            if (now - idle_since).total_seconds() >= max_idle:
                yield 'event: timeout\ndata: {"message": "Connection timed out due to inactivity"}\n\n'
                break

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


def _json_dumps(data: dict) -> str:
    """JSON serialize data, handling None values."""
    return json.dumps({k: v for k, v in data.items() if v is not None})


@router.get("/{job_id}/progress/stream")
async def stream_job_progress(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """
    Stream real-time progress updates for a job via Server-Sent Events (SSE).

    The stream sends the following event types:

    - `status`: Initial job status when connecting
    - `progress`: Progress updates (percent, message, stage)
    - `complete`: Job completed successfully (includes beatmap_id)
    - `error`: Job failed or was cancelled
    - `timeout`: Connection closed due to inactivity

    The stream automatically closes when the job completes, fails, or times out.

    Example client usage:
    ```javascript
    const eventSource = new EventSource('/api/v1/ai-jobs/{job_id}/progress/stream');

    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        console.log(`Progress: ${data.percent}% - ${data.message}`);
    });

    eventSource.addEventListener('complete', (e) => {
        console.log('Job completed!');
        eventSource.close();
    });
    ```
    """
    # Verify job exists first
    service = AIJobService(session)
    job = await service.get_by_id(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return StreamingResponse(
        _progress_event_generator(job_id, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# =============================================================================
# Modal Webhook (Receive results from GPU processing)
# =============================================================================


class ModalJobResult(BaseModel):
    """Result payload from Modal GPU processing."""

    job_id: str = Field(description="The job UUID")
    success: bool = Field(description="Whether processing succeeded")
    beatmap: str | None = Field(
        default=None, description="Base64-encoded .bsm file content"
    )
    beatmap_size: int | None = Field(
        default=None, description="Size of beatmap in bytes"
    )
    debug: str | None = Field(default=None, description="Base64-encoded debug payload")
    processing_time_seconds: float | None = Field(default=None)
    error: str | None = Field(default=None, description="Error message if failed")


@router.post(
    "/modal-webhook",
    status_code=status.HTTP_200_OK,
    summary="Receive job results from Modal",
    include_in_schema=False,  # Internal endpoint
)
async def modal_webhook(
    result: ModalJobResult,
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Webhook endpoint for Modal to report job completion.

    This is called by the Modal function when processing completes.
    It handles:
    1. Decoding the beatmap content
    2. Uploading to S3 storage
    3. Creating a map_version record
    4. Marking the job as complete
    5. Triggering notifications

    Security: Verifies shared secret from Modal.
    Idempotency: Uses ProcessedWebhookEvent to prevent duplicate processing.
    """
    import logging

    logger = logging.getLogger(__name__)

    # Verify webhook secret
    settings = get_settings()
    if x_webhook_secret != settings.modal_webhook_secret:
        logger.warning("Invalid webhook secret received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )

    # Parse job ID
    try:
        job_id = uuid.UUID(result.job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid job_id format",
        )

    # Idempotency check - use job_id as event_id for Modal webhooks
    from app.models.webhook_event import ProcessedWebhookEvent
    from sqlalchemy import select
    
    event_id = f"modal_job_{result.job_id}"
    existing_event = await session.execute(
        select(ProcessedWebhookEvent).where(
            ProcessedWebhookEvent.provider == "modal",
            ProcessedWebhookEvent.event_id == event_id,
        )
    )
    if existing_event.scalar_one_or_none():
        logger.info(f"Modal webhook already processed for job {result.job_id}, skipping")
        return {"status": "already_processed", "job_id": result.job_id}

    # Get the job
    ai_service = AIJobService(session)
    job = await ai_service.get_by_id(job_id)
    if not job:
        logger.warning(f"Modal webhook received for unknown job: {job_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    
    # Check if job is already in a terminal state (additional safety)
    if job.state in (AIJobState.COMPLETE, AIJobState.FAILED, AIJobState.CANCELLED):
        logger.info(f"Job {job_id} already in terminal state {job.state}, skipping webhook")
        return {"status": "already_completed", "job_id": result.job_id, "state": job.state.value}

    if result.success and result.beatmap:
        try:
            # Decode beatmap content
            beatmap_content = base64.b64decode(result.beatmap)

            # Upload to storage
            from app.services.storage import get_storage

            storage = await get_storage()

            # Create a map and version for this beatmap
            from app.models.song import Map, MapState
            from app.models.map_version import MapVersion

            # Find or create a map for this song
            from sqlalchemy import select

            stmt = select(Map).where(
                Map.song_id == job.song_id,
                Map.difficulty_label == "AI Generated",
            )
            result_map = await session.execute(stmt)
            ai_map = result_map.scalar_one_or_none()

            if not ai_map:
                # Create new map
                ai_map = Map(
                    song_id=job.song_id,
                    difficulty_label="AI Generated",
                    is_canonical=False,
                    state=MapState.UNVERIFIED,
                )
                session.add(ai_map)
                await session.flush()  # Get the map ID

            # Upload beatmap to storage
            storage_key = f"beatmaps/{job.song_id}/{ai_map.id}/v1.bsm"
            await storage.upload(
                storage_key, beatmap_content, "application/octet-stream"
            )

            # Create new version
            new_version = MapVersion(
                map_id=ai_map.id,
                version_number=1,
                storage_uri=storage_key,
                generation_job_id=job.id,
                created_by_id=job.requested_by_id,
            )
            session.add(new_version)
            await session.flush()

            # Update map to point to this version
            ai_map.current_version_id = new_version.id

            # Mark job complete with beatmap reference
            job.state = AIJobState.COMPLETE
            job.finished_at = datetime.now(timezone.utc)
            job.progress_percent = 100
            job.progress_message = "Complete"

            # Associate beatmap with job (if we have a beatmap_id field)
            # For now, the relationship is through map_version.generation_job_id

            await session.commit()

            logger.info(
                f"Job {job_id} completed successfully, beatmap stored at {storage_key}"
            )

            # Check and award achievements (best effort)
            try:
                from app.services.achievements import (
                    check_beatmap_generation_achievements,
                )

                awarded = await check_beatmap_generation_achievements(
                    session, job.requester_id
                )
                if awarded:
                    await session.commit()
                    logger.info(
                        f"Awarded achievements to user {job.requester_id}: {awarded}"
                    )
            except Exception as e:
                logger.warning(f"Failed to check achievements for job {job_id}: {e}")

            # Trigger notification (best effort)
            try:
                from app.services.notifications import get_notification_service

                notification_service = get_notification_service()
                await notification_service.notify_job_complete(job)
            except Exception as e:
                logger.warning(f"Failed to send notification for job {job_id}: {e}")

            # Record webhook as processed for idempotency
            processed_event = ProcessedWebhookEvent(
                provider="modal",
                event_id=event_id,
                event_type="job_complete",
            )
            session.add(processed_event)
            await session.commit()

            return {"status": "success", "map_version_id": str(new_version.id)}

        except Exception as e:
            logger.exception(f"Failed to process Modal result for job {job_id}")
            await ai_service.mark_finished(job_id, error=f"Failed to save results: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process results: {e}",
            )
    else:
        # Job failed
        error_msg = result.error or "Unknown error from Modal"
        await ai_service.mark_finished(job_id, error=error_msg)
        logger.warning(f"Job {job_id} failed in Modal: {error_msg}")

        # Record webhook as processed for idempotency
        processed_event = ProcessedWebhookEvent(
            provider="modal",
            event_id=event_id,
            event_type="job_failed",
        )
        session.add(processed_event)
        await session.commit()

        return {"status": "failed", "error": error_msg}
