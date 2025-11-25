"""AI job API routes."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db_session
from app.models.user import User
from app.schemas.ai_jobs import AIJobCreate, AIJobRead
from app.services.ai_jobs import AIJobService

router = APIRouter(prefix="/ai-jobs", tags=["ai-jobs"])


@router.post("", response_model=AIJobRead, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_job(
    payload: AIJobCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> AIJobRead:
    """
    Enqueue an AI mapping job.

    Authentication is optional - anonymous users can enqueue jobs but won't
    have them associated with their account for tracking.
    """
    service = AIJobService(session)
    requested_by = current_user.id if current_user else None
    job = await service.enqueue(payload, requested_by=requested_by)
    return AIJobRead.model_validate(job)


@router.get("", response_model=list[AIJobRead])
async def list_jobs(
    song_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[AIJobRead]:
    """List AI jobs, optionally filtered by song."""

    service = AIJobService(session)
    jobs = await service.list_jobs(song_id=song_id)
    return [AIJobRead.model_validate(job) for job in jobs]
