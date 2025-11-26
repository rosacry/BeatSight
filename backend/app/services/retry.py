"""Retry service for failed AI jobs with exponential backoff.

Implements E2-005: Job retry logic with configurable backoff strategy.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob, AIJobState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_seconds: int = 60  # 1 minute
    max_delay_seconds: int = 3600  # 1 hour
    exponential_base: float = 2.0
    jitter_factor: float = 0.1  # ±10% random jitter


@dataclass
class RetryResult:
    """Result of a retry attempt."""

    job_id: uuid.UUID
    action: str  # "scheduled", "exhausted", "not_retriable"
    retry_count: int
    next_retry_at: datetime | None = None
    message: str = ""


class RetryService:
    """Handles retry logic for failed AI jobs."""

    def __init__(
        self, session: AsyncSession, config: RetryConfig | None = None
    ) -> None:
        self._session = session
        self._config = config or RetryConfig()

    def calculate_backoff(self, retry_count: int) -> timedelta:
        """Calculate exponential backoff delay with jitter.

        Uses exponential backoff: base_delay * (exponential_base ^ retry_count)
        Capped at max_delay_seconds.

        Args:
            retry_count: Number of retries already attempted (0-based).

        Returns:
            Delay before next retry attempt.
        """
        import random

        # Exponential backoff
        delay = self._config.base_delay_seconds * (
            self._config.exponential_base**retry_count
        )

        # Cap at maximum
        delay = min(delay, self._config.max_delay_seconds)

        # Add jitter (±jitter_factor)
        jitter = delay * self._config.jitter_factor
        delay += random.uniform(-jitter, jitter)

        return timedelta(seconds=max(delay, 0))

    async def schedule_retry(self, job_id: uuid.UUID, error: str) -> RetryResult:
        """Schedule a failed job for retry if retries remain.

        Args:
            job_id: The job that failed.
            error: Error message from the failure.

        Returns:
            RetryResult indicating what action was taken.
        """
        job = await self._session.get(AIJob, job_id)
        if job is None:
            return RetryResult(
                job_id=job_id,
                action="not_retriable",
                retry_count=0,
                message="Job not found",
            )

        # Check if job is in a retriable state
        if job.state not in (AIJobState.PROCESSING, AIJobState.FAILED):
            return RetryResult(
                job_id=job_id,
                action="not_retriable",
                retry_count=job.retry_count,
                message=f"Job in state {job.state} cannot be retried",
            )

        # Check if retries exhausted
        if job.retry_count >= job.max_retries:
            job.state = AIJobState.FAILED
            job.error_message = (
                f"Max retries ({job.max_retries}) exhausted. Last error: {error[:400]}"
            )
            job.finished_at = datetime.now(timezone.utc)
            await self._session.commit()

            logger.warning(
                "Job %s exhausted retries after %d attempts: %s",
                job_id,
                job.retry_count,
                error[:100],
            )

            return RetryResult(
                job_id=job_id,
                action="exhausted",
                retry_count=job.retry_count,
                message=f"Max retries exhausted after {job.retry_count} attempts",
            )

        # Schedule retry with exponential backoff
        delay = self.calculate_backoff(job.retry_count)
        now = datetime.now(timezone.utc)
        next_retry = now + delay

        job.retry_count += 1
        job.next_retry_at = next_retry
        job.last_error = error[:1024] if error else None
        job.state = AIJobState.QUEUED  # Return to queue
        job.worker_id = None
        job.started_at = None
        job.last_heartbeat = None
        job.progress_percent = None
        job.progress_message = f"Retry {job.retry_count}/{job.max_retries} scheduled"

        await self._session.commit()

        logger.info(
            "Job %s scheduled for retry %d/%d at %s (delay: %s)",
            job_id,
            job.retry_count,
            job.max_retries,
            next_retry.isoformat(),
            delay,
        )

        return RetryResult(
            job_id=job_id,
            action="scheduled",
            retry_count=job.retry_count,
            next_retry_at=next_retry,
            message=f"Retry {job.retry_count}/{job.max_retries} scheduled for {next_retry.isoformat()}",
        )

    async def get_jobs_ready_for_retry(self) -> list[AIJob]:
        """Get queued jobs whose next_retry_at has passed.

        Returns:
            List of jobs ready to be claimed by workers.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(
                # Either no next_retry_at (new job) or retry time has passed
                (AIJob.next_retry_at.is_(None)) | (AIJob.next_retry_at <= now)
            )
            .order_by(AIJob.priority.desc(), AIJob.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_retries(self) -> list[AIJob]:
        """Get jobs waiting for their retry time.

        Returns:
            List of jobs with future next_retry_at timestamps.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(AIJob.next_retry_at > now)
            .order_by(AIJob.next_retry_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def reset_stale_jobs(
        self, stale_threshold_seconds: int = 300
    ) -> list[RetryResult]:
        """Find stale jobs and schedule them for retry.

        Args:
            stale_threshold_seconds: How long without heartbeat before job is stale.

        Returns:
            List of retry results for processed stale jobs.
        """
        threshold = datetime.now(timezone.utc) - timedelta(
            seconds=stale_threshold_seconds
        )
        stmt = (
            select(AIJob)
            .where(AIJob.state == AIJobState.PROCESSING)
            .where(AIJob.last_heartbeat < threshold)
        )
        result = await self._session.execute(stmt)
        stale_jobs = list(result.scalars().all())

        results = []
        for job in stale_jobs:
            logger.warning(
                "Job %s is stale (last heartbeat: %s), scheduling retry",
                job.id,
                job.last_heartbeat,
            )
            retry_result = await self.schedule_retry(
                job.id,
                f"Worker timeout (no heartbeat for {stale_threshold_seconds}s)",
            )
            results.append(retry_result)

        return results

    async def get_retry_stats(self) -> dict:
        """Get statistics about job retries.

        Returns:
            Dictionary with retry statistics.
        """
        from sqlalchemy import func

        # Jobs with retries
        stmt_with_retries = (
            select(func.count()).select_from(AIJob).where(AIJob.retry_count > 0)
        )
        result = await self._session.execute(stmt_with_retries)
        jobs_with_retries = result.scalar_one()

        # Total retry count
        stmt_total_retries = select(func.sum(AIJob.retry_count)).select_from(AIJob)
        result = await self._session.execute(stmt_total_retries)
        total_retries = result.scalar_one() or 0

        # Jobs exhausted (failed with retry_count >= max_retries)
        stmt_exhausted = (
            select(func.count())
            .select_from(AIJob)
            .where(AIJob.state == AIJobState.FAILED)
            .where(AIJob.retry_count >= AIJob.max_retries)
        )
        result = await self._session.execute(stmt_exhausted)
        exhausted_count = result.scalar_one()

        # Pending retries
        now = datetime.now(timezone.utc)
        stmt_pending = (
            select(func.count())
            .select_from(AIJob)
            .where(AIJob.state == AIJobState.QUEUED)
            .where(AIJob.next_retry_at > now)
        )
        result = await self._session.execute(stmt_pending)
        pending_retries = result.scalar_one()

        return {
            "jobs_with_retries": jobs_with_retries,
            "total_retry_attempts": total_retries,
            "exhausted_jobs": exhausted_count,
            "pending_retries": pending_retries,
        }
