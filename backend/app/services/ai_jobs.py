"""Service utilities for AI job lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import ProgressUpdate, get_redis, publish_progress
from app.models.ai_job import AIJob, AIJobState
from app.schemas.ai_jobs import AIJobCreate


class DuplicateType(str, Enum):
    """Types of duplicate detection results."""
    
    NONE = "none"  # No duplicate found
    QUEUED = "queued"  # Same song already has a job in queue
    PROCESSING = "processing"  # Same song is currently being processed
    COMPLETED = "completed"  # Same song has a completed job with same/newer model


@dataclass
class DuplicateCheckResult:
    """Result of a duplicate detection check."""
    
    duplicate_type: DuplicateType
    existing_job: AIJob | None = None
    message: str | None = None


class AIJobService:
    """Encapsulates persistence and state transitions for AI jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check_duplicate(
        self,
        song_id: uuid.UUID,
        model_version: str | None = None,
    ) -> DuplicateCheckResult:
        """Check if a duplicate job exists for this song.
        
        Duplicate detection rules:
        1. If a QUEUED job exists for this song → QUEUED duplicate
        2. If a PROCESSING job exists for this song → PROCESSING duplicate
        3. If a COMPLETED job exists with same or newer model version → COMPLETED duplicate
        
        Args:
            song_id: The song ID to check for duplicates.
            model_version: Current AI model version for comparison.
            
        Returns:
            DuplicateCheckResult with duplicate type and existing job if found.
        """
        # Check for queued or processing job
        stmt = (
            select(AIJob)
            .where(AIJob.song_id == song_id)
            .where(AIJob.state.in_([AIJobState.QUEUED, AIJobState.PROCESSING]))
            .order_by(AIJob.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        active_job = result.scalar_one_or_none()
        
        if active_job:
            if active_job.state == AIJobState.QUEUED:
                return DuplicateCheckResult(
                    duplicate_type=DuplicateType.QUEUED,
                    existing_job=active_job,
                    message="A job for this song is already in the queue",
                )
            else:
                return DuplicateCheckResult(
                    duplicate_type=DuplicateType.PROCESSING,
                    existing_job=active_job,
                    message="A job for this song is currently processing",
                )
        
        # Check for completed job with same/newer model version
        if model_version:
            stmt = (
                select(AIJob)
                .where(AIJob.song_id == song_id)
                .where(AIJob.state == AIJobState.COMPLETE)
                .where(AIJob.model_version.isnot(None))
                .order_by(AIJob.finished_at.desc())
                .limit(1)
            )
            result = await self._session.execute(stmt)
            completed_job = result.scalar_one_or_none()
            
            if completed_job and completed_job.model_version:
                # Simple version comparison (assumes semver-like: v5.0.0 < v5.1.0)
                if self._compare_versions(completed_job.model_version, model_version) >= 0:
                    return DuplicateCheckResult(
                        duplicate_type=DuplicateType.COMPLETED,
                        existing_job=completed_job,
                        message=f"Song already has a beatmap from model {completed_job.model_version}",
                    )
        
        return DuplicateCheckResult(duplicate_type=DuplicateType.NONE)

    def _compare_versions(self, version_a: str, version_b: str) -> int:
        """Compare two version strings.
        
        Returns:
            -1 if a < b, 0 if a == b, 1 if a > b
        """
        def parse_version(v: str) -> tuple:
            # Strip 'v' prefix if present
            v = v.lstrip('vV')
            parts = v.split('.')
            return tuple(int(p) if p.isdigit() else 0 for p in parts)
        
        try:
            a_parts = parse_version(version_a)
            b_parts = parse_version(version_b)
            
            # Pad shorter version with zeros
            max_len = max(len(a_parts), len(b_parts))
            a_parts = a_parts + (0,) * (max_len - len(a_parts))
            b_parts = b_parts + (0,) * (max_len - len(b_parts))
            
            if a_parts < b_parts:
                return -1
            elif a_parts > b_parts:
                return 1
            return 0
        except (ValueError, AttributeError):
            return 0  # Treat unparseable versions as equal

    async def enqueue(
        self, payload: AIJobCreate, requested_by: uuid.UUID | None
    ) -> AIJob:
        job = AIJob(
            song_id=payload.song_id,
            priority=payload.priority,
            requested_by_id=requested_by,
            state=AIJobState.QUEUED,
        )
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def enqueue_with_duplicate_check(
        self,
        payload: AIJobCreate,
        requested_by: uuid.UUID | None,
        model_version: str | None = None,
        skip_queue_check: bool = False,
    ) -> tuple[AIJob | None, DuplicateCheckResult]:
        """Enqueue a job with duplicate detection.
        
        This method checks for duplicates before creating a new job:
        - If a QUEUED or PROCESSING job exists, returns the existing job
        - If a COMPLETED job exists with the same/newer model, returns it
        - Otherwise creates a new job
        
        Args:
            payload: Job creation data
            requested_by: User ID requesting the job
            model_version: Current AI model version
            skip_queue_check: If True, skip queue duplicate check (for re-evaluation)
            
        Returns:
            Tuple of (created job or None, duplicate check result)
        """
        # Check for duplicates first
        duplicate_result = await self.check_duplicate(payload.song_id, model_version)
        
        if duplicate_result.duplicate_type == DuplicateType.NONE:
            # No duplicate - create new job
            job = AIJob(
                song_id=payload.song_id,
                priority=payload.priority,
                requested_by_id=requested_by,
                state=AIJobState.QUEUED,
                model_version=model_version,  # Track which model version will process this
            )
            self._session.add(job)
            await self._session.commit()
            await self._session.refresh(job)
            return job, duplicate_result
        
        if duplicate_result.duplicate_type in (DuplicateType.QUEUED, DuplicateType.PROCESSING):
            if skip_queue_check:
                # Re-evaluation case - create new job anyway
                job = AIJob(
                    song_id=payload.song_id,
                    priority=payload.priority,
                    requested_by_id=requested_by,
                    state=AIJobState.QUEUED,
                    model_version=model_version,
                )
                self._session.add(job)
                await self._session.commit()
                await self._session.refresh(job)
                return job, DuplicateCheckResult(duplicate_type=DuplicateType.NONE)
            # Return existing job - don't charge credit
            return None, duplicate_result
        
        # COMPLETED duplicate - don't create new job
        return None, duplicate_result

    async def find_songs_for_re_evaluation(
        self,
        old_model_version: str,
        new_model_version: str,
        limit: int = 100,
    ) -> list[uuid.UUID]:
        """Find song IDs that could benefit from re-evaluation.
        
        Returns songs where:
        - The most recent completed job used an older model version
        - The song has at least one unverified map
        
        Args:
            old_model_version: Previous model version to look for
            new_model_version: New model version to upgrade to
            limit: Maximum songs to return
            
        Returns:
            List of song IDs eligible for re-evaluation
        """
        
        # Find songs with completed jobs from older model
        subquery = (
            select(AIJob.song_id)
            .where(AIJob.state == AIJobState.COMPLETE)
            .where(AIJob.model_version.isnot(None))
            .group_by(AIJob.song_id)
        )
        
        # Get songs with unverified maps that were processed by old model
        stmt = (
            select(AIJob.song_id)
            .where(AIJob.song_id.in_(subquery))
            .where(AIJob.state == AIJobState.COMPLETE)
            .where(AIJob.model_version == old_model_version)
            .group_by(AIJob.song_id)
            .limit(limit)
        )
        
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_jobs(
        self,
        song_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AIJob]:
        """List AI jobs with pagination.

        Args:
            song_id: Filter by song ID.
            user_id: Filter by requesting user ID.
            limit: Maximum number of jobs to return.
            offset: Number of jobs to skip.
        """
        stmt = (
            select(AIJob).order_by(AIJob.created_at.desc()).limit(limit).offset(offset)
        )
        if song_id:
            stmt = stmt.where(AIJob.song_id == song_id)
        if user_id:
            stmt = stmt.where(AIJob.requested_by_id == user_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().unique())

    async def count_jobs(
        self,
        song_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> int:
        """Count total AI jobs for pagination metadata."""
        stmt = select(func.count()).select_from(AIJob)
        if song_id:
            stmt = stmt.where(AIJob.song_id == song_id)
        if user_id:
            stmt = stmt.where(AIJob.requested_by_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def get_job(self, job_id: uuid.UUID) -> AIJob | None:
        """Get a job by ID."""
        return await self._session.get(AIJob, job_id)

    async def mark_started(self, job_id: uuid.UUID, worker_id: uuid.UUID) -> None:
        """Mark a job as started by a worker."""
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.state = AIJobState.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.worker_id = worker_id
        job.last_heartbeat = datetime.now(timezone.utc)
        job.progress_percent = 0
        job.progress_message = "Starting..."
        await self._session.commit()

    async def update_progress(
        self,
        job_id: uuid.UUID,
        progress_percent: int,
        progress_message: str | None = None,
        stage: str | None = None,
    ) -> AIJob:
        """Update job progress and publish to Redis pub/sub.

        Args:
            job_id: The job ID.
            progress_percent: Progress percentage (0-100).
            progress_message: Optional status message.
            stage: Optional pipeline stage name.

        Returns:
            The updated AIJob instance.
        """
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")

        now = datetime.now(timezone.utc)
        job.last_heartbeat = now
        job.progress_percent = progress_percent
        job.progress_message = progress_message
        await self._session.commit()
        await self._session.refresh(job)

        # Publish progress update to Redis for SSE streaming
        try:
            redis = await get_redis()
            update = ProgressUpdate(
                job_id=job_id,
                percent=progress_percent,
                message=progress_message,
                stage=stage,
                timestamp=now,
            )
            await publish_progress(redis, update)
        except Exception:
            # Don't fail the update if Redis publish fails
            pass

        return job

    async def mark_finished(
        self, job_id: uuid.UUID, *, error: str | None = None
    ) -> None:
        """Mark a job as complete or failed."""
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.finished_at = datetime.now(timezone.utc)
        job.progress_percent = 100 if not error else job.progress_percent
        job.progress_message = (
            "Complete" if not error else error[:255] if error else None
        )
        if error:
            job.state = AIJobState.FAILED
            job.error_message = error
        else:
            job.state = AIJobState.COMPLETE
        await self._session.commit()

    async def cancel_job(self, job_id: uuid.UUID) -> None:
        """Cancel a queued or processing job."""
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        if job.state not in (AIJobState.QUEUED, AIJobState.PROCESSING):
            raise ValueError(f"Cannot cancel job in state {job.state}")
        job.state = AIJobState.CANCELLED
        job.finished_at = datetime.now(timezone.utc)
        job.progress_message = "Cancelled"
        await self._session.commit()

    async def get_next_queued_job(self) -> AIJob | None:
        """Get the next queued job for processing (priority then FIFO).

        Only returns jobs that are ready to process (no pending retry delay).
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(
                # Either no next_retry_at (new job) or retry time has passed
                or_(AIJob.next_retry_at.is_(None), AIJob.next_retry_at <= now)
            )
            .order_by(AIJob.priority.desc(), AIJob.created_at.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, job_id: uuid.UUID) -> AIJob | None:
        """Get a job by ID (alias for get_job for API compatibility)."""
        return await self.get_job(job_id)

    async def heartbeat(self, job_id: uuid.UUID, worker_id: uuid.UUID) -> None:
        """Update heartbeat timestamp for a processing job."""
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.worker_id = worker_id
        job.last_heartbeat = datetime.now(timezone.utc)
        await self._session.commit()

    async def claim_job(self, worker_id: uuid.UUID) -> AIJob | None:
        """Claim the next available queued job for processing (atomic).

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions where multiple
        workers could claim the same job simultaneously.
        """

        now = datetime.now(timezone.utc)

        # First, atomically select and lock a job
        # FOR UPDATE SKIP LOCKED ensures only one worker gets each job
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(or_(AIJob.next_retry_at.is_(None), AIJob.next_retry_at <= now))
            .order_by(AIJob.priority.desc(), AIJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        # Now update the locked job
        job.state = AIJobState.PROCESSING
        job.started_at = now
        job.worker_id = worker_id
        job.last_heartbeat = now
        job.progress_percent = 0
        job.progress_message = "Starting..."
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def claim_job_directly(
        self, job_id: uuid.UUID, worker_id: uuid.UUID
    ) -> AIJob:
        """Claim a specific job by ID for processing.

        Used for Modal GPU orchestration where we know the job ID upfront.

        Args:
            job_id: The job ID to claim.
            worker_id: The worker ID (or Modal pseudo-ID).

        Returns:
            The updated AIJob instance.

        Raises:
            ValueError: If job not found or not in QUEUED state.
        """
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        if job.state != AIJobState.QUEUED:
            raise ValueError(f"Cannot claim job in state {job.state}")

        job.state = AIJobState.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.worker_id = worker_id
        job.last_heartbeat = datetime.now(timezone.utc)
        job.progress_percent = 0
        job.progress_message = "Dispatched to GPU..."
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def release_job(self, job_id: uuid.UUID) -> None:
        """Release a job back to the queue for retry."""
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.state = AIJobState.QUEUED
        job.worker_id = None
        job.started_at = None
        job.last_heartbeat = None
        job.progress_percent = None
        job.progress_message = None
        await self._session.commit()

    async def find_stale_jobs(self, stale_threshold_seconds: int = 300) -> list[AIJob]:
        """Find processing jobs with stale heartbeats."""
        threshold = datetime.now(timezone.utc) - timedelta(
            seconds=stale_threshold_seconds
        )
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.PROCESSING)
            .where(AIJob.last_heartbeat < threshold)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_queue_length(self) -> int:
        """Get total number of jobs in the queue."""
        stmt = (
            select(func.count())
            .select_from(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_queue_position(self, job_id: uuid.UUID) -> int | None:
        """Get 0-based position of a job in the queue (None if not queued)."""
        job = await self._session.get(AIJob, job_id)
        if job is None or job.state != AIJobState.QUEUED:
            return None

        # Count jobs with higher priority or same priority but earlier creation
        stmt = (
            select(func.count())
            .select_from(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(
                or_(
                    AIJob.priority > job.priority,
                    and_(
                        AIJob.priority == job.priority,
                        AIJob.created_at < job.created_at,
                    ),
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
