"""Service utilities for AI job lifecycle."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_job import AIJob, AIJobPriority, AIJobState
from app.schemas.ai_jobs import AIJobCreate


class AIJobService:
    """Encapsulates persistence and state transitions for AI jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, payload: AIJobCreate, requested_by: uuid.UUID | None) -> AIJob:
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

    async def list_jobs(self, song_id: uuid.UUID | None = None) -> list[AIJob]:
        stmt = select(AIJob).order_by(AIJob.created_at.desc())
        if song_id:
            stmt = stmt.where(AIJob.song_id == song_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().unique())

    async def mark_started(self, job_id: uuid.UUID) -> None:
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.state = AIJobState.PROCESSING
        job.started_at = datetime.utcnow()
        await self._session.commit()

    async def mark_finished(self, job_id: uuid.UUID, *, error: str | None = None) -> None:
        job = await self._session.get(AIJob, job_id)
        if job is None:
            raise ValueError("Job not found")
        job.finished_at = datetime.utcnow()
        if error:
            job.state = AIJobState.FAILED
            job.error_message = error
        else:
            job.state = AIJobState.COMPLETE
        await self._session.commit()
